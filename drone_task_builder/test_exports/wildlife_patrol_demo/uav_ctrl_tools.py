#!/usr/bin/python3
# -*- coding: utf-8 -*-

import tf
import cv2
import math
import time
import numpy as np
from collections import deque
from typing import NamedTuple
from cv_bridge import CvBridge

import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import Image, NavSatFix
from geographic_msgs.msg import GeoPointStamped
from mavros_msgs.msg import RCIn, State, PositionTarget, PlayTuneV2
from mavros_msgs.srv import SetMode, SetModeResponse, SetModeRequest
from mavros_msgs.srv import CommandTOL, CommandTOLResponse, CommandTOLRequest
from mavros_msgs.srv import CommandLong, CommandLongResponse, CommandLongRequest
from mavros_msgs.srv import CommandBool, CommandBoolResponse, CommandBoolRequest
from mavros_msgs.srv import CommandHome, CommandHomeResponse, CommandHomeRequest



TARGET_POINT_TOPIC = '/mavros/setpoint_raw/local'
EKF_ORIGIN = "/mavros/global_position/set_gp_origin"
BUZZER_TOPIC = "/mavros/play_tune"
WAIT_LOCAL_TOPIC = "/mavros/local_position/odom"
WAIT_RC_TOPIC = "/mavros/rc/in"



class Point(NamedTuple):
    x: float
    y: float
    z: float
    task_flag: int
    

class CtrlTools:
    def __init__(self):
        """
        初始化无人机控制工具类：
        - 加载航点参数
        - 初始化 ROS 发布器/订阅器/服务客户端
        - 设置 EKF 原点
        - 等待初始定位数据
        """
        self.target_points = deque()
        self.bridge = CvBridge()
        
        self.nav_pub = rospy.Publisher(TARGET_POINT_TOPIC, PositionTarget, queue_size=1, latch=True) # 发布目标航点
        self.set_ekf_origin_pub = rospy.Publisher(EKF_ORIGIN, GeoPointStamped, queue_size=1, latch=True) # 设置ekf原点
        self.buzzer_pub = rospy.Publisher(BUZZER_TOPIC, PlayTuneV2, queue_size=1, latch=True) # 调用蜂鸣器
        self.image_pub_circle = rospy.Publisher('/image_circle', Image, queue_size=1, latch=True)
        
        self.wait_local_sub = rospy.Subscriber(WAIT_LOCAL_TOPIC, Odometry, self._pos_callback, queue_size=10) # 订阅定位数据
        self.rc_sub = rospy.Subscriber(WAIT_RC_TOPIC, RCIn, self._rc_callback, queue_size=10) # 订阅遥控器数据
        
        self.command_client = rospy.ServiceProxy('/mavros/cmd/command', CommandLong)
        self.mode_client = rospy.ServiceProxy("/mavros/set_mode", SetMode)
        self.takeoff_client = rospy.ServiceProxy("/mavros/cmd/takeoff", CommandTOL)
        self.arming_client = rospy.ServiceProxy("/mavros/cmd/arming", CommandBool)
        
        self.ekf_origin_msg = GeoPointStamped()
        self.ekf_origin_msg.position.latitude = 34.8069498
        self.ekf_origin_msg.position.longitude = 113.5129698
        self.ekf_origin_msg.position.altitude = 110.0
        self.set_ekf_origin_pub.publish(self.ekf_origin_msg)

        # 初始化遥控器，定位，偏航等数据
        self.current_rc = [0,0,0,0,0,0,0,0]        
        self.current_pos = Odometry()              
        self.current_yaw = 0.0   
        self.init_yaw = 0.0                 
        self.last_ch8 = 2000

        # home pose
        self.home_pose_x = 0.0      
        self.home_pose_y = 0.0
        self.home_pose_z = 0.0
        
        self.target_point_cmd = PositionTarget()

        rospy.loginfo("wait pose ...")
        rospy.sleep(10)
        cur_pose = rospy.wait_for_message("/mavros/local_position/odom",Odometry, timeout=None)
        self.current_pos = cur_pose
        euler_rad = tf.transformations.euler_from_quaternion([cur_pose.pose.pose.orientation.x, 
                                                              cur_pose.pose.pose.orientation.y, 
                                                              cur_pose.pose.pose.orientation.z, 
                                                              cur_pose.pose.pose.orientation.w])
        self.current_yaw = euler_rad[2]
        self.init_yaw = euler_rad[2]
        rospy.loginfo(self.current_pos)
        rospy.loginfo(self.current_yaw)
        
        # 加载航点
        point_count = 0
        try:
            while True:
                self.target_points.append(Point(*rospy.get_param(f"~point_{point_count}")))
                point_count += 1
        except KeyError:
            n = len(self.target_points)
            rospy.loginfo(f"{n} points")
            if n == 0:
                raise ValueError("no point")
    
                
    def _rc_callback(self, rc_data):
        """遥控器数据回调"""
        self.current_rc = rc_data.channels
        
        
    def _pos_callback(self, msg):
        """定位数据回调，更新偏航角"""
        self.current_pos = msg
        euler_rad = tf.transformations.euler_from_quaternion([msg.pose.pose.orientation.x, 
                                                              msg.pose.pose.orientation.y, 
                                                              msg.pose.pose.orientation.z, 
                                                              msg.pose.pose.orientation.w])
        self.current_yaw = euler_rad[2]
        
        
    def _wrap_angle(self, angle):
        """将角度归一化到 [-π, π]"""
        return (angle + math.pi) % (2 * math.pi) - math.pi
        
        
    def _world_to_drifted_map(self, world_x, world_y):
        """将真实世界坐标点转换到存在初始偏航偏差的定位坐标系中"""
        c = math.cos(self.init_yaw)
        s = math.sin(self.init_yaw)
        x_map = world_x * c + world_y * s
        y_map = -world_x * s + world_y * c
        return x_map, y_map
        
        
    def set_rc_to_start(self):
        '''
        遥控器一键起飞    ch5<1800  ch8 l->h（>1800）  thr=1500+-30
        用于阻塞程序执行，直到收到遥控器起飞指令才通过阻塞(油门中位、ch5不是H位、ch8从L位->H位)
        '''
        rospy.sleep(0.5)
        rospy.loginfo("wait RC ...")
        self.ctrl_buzzer(1)
        while not rospy.is_shutdown():
            if len(self.current_rc) == 0:
                rospy.logwarn_throttle(10, "[len(self.current_rc) == 0]Waiting for remote control connection")
                continue
            # [roll,pitch,thr,yaw,ch5,ch6,ch7,ch8]
            thr = self.current_rc[2]
            ch5 = self.current_rc[4]
            ch7 = self.current_rc[6]
            ch8 = self.current_rc[7]
            if ch7<1800 and ch7>1200:
                rospy.logwarn_throttle(10, "[ch7<1800 and ch7>1200]Waiting for remote control connection")
                continue
            if (self.last_ch8<1800 and ch8>1800 and ch5<1800 and thr<1530 and thr>1470):
                print("last_ch8 = ", str(self.last_ch8))
                print("curr_ch8 = ", str(ch8))
                return True
                break
            self.last_ch8 = ch8
            rospy.sleep(0.2)
        return False        


    def uav_takeoff(self):
        """起飞功能函数"""
        self.home_pose_x, self.home_pose_y, self.home_pose_z = self.get_local()
    
        now_state = rospy.wait_for_message("/mavros/state",State, timeout=None)
        if (now_state.armed == True):
            return False
        print(f"now_state.mode: {now_state.mode}") 
        if (now_state.mode != "GUIDED"):
            print(f"to GUIDED") 
            mode_srv = SetModeRequest()
            mode_srv.base_mode = 1
            mode_srv.custom_mode = "GUIDED"
            mode_response = self.mode_client.call(mode_srv)
            rospy.sleep(0.1)
            if (mode_response.mode_sent == False):
                print(f"to GUIDED error") 
                return False
                
        # request takeoff
        arm_srv = CommandBoolRequest()
        arm_srv.value = True
        arm_response = self.arming_client.call(arm_srv)
        if arm_response.success == False:
            print(f"arming_client error") 
            return False
        else:
            now_pose = rospy.wait_for_message("/mavros/global_position/global",NavSatFix, timeout=None)
            rospy.sleep(2)
            takeoff_srv = CommandTOLRequest()
            takeoff_srv.latitude = now_pose.latitude
            takeoff_srv.longitude = now_pose.longitude
            takeoff_srv.altitude = 1.0
            takeoff_response = self.takeoff_client.call(takeoff_srv)
            if takeoff_response.success == False:
                print(f"takeoff_client error") 
                return False
            else:
                while not rospy.is_shutdown():
                    cur_x, cur_y, cur_z = self.get_local()
                    if (abs(cur_z - 1.0) <= 0.2):
                        return True
                    rospy.sleep(0.1)
                return False
               
                
    def uav_land(self, is_adjust=False):
        """
        降落功能函数
        :param is_adjust: 是否打开降落校准，该校准基于position_calibration函数，圆识别实现
        """
        if is_adjust == True:
            # 获取识别结果
            c_x, c_y, c_z = self.get_local()
            c_frame = self.get_img()
            have_circle, offset_x, offset_y = self.position_calibration(c_frame, c_z + 0.06) # 高度额外加上摄像头与地面的距离
            # 有识别结果才校准，不然直接结束校准，开始正常降落
            if have_circle == True: 
                rospy.loginfo("uav_land calibration start")
                # 计算目标位置
                target_x = c_x + offset_x + 0.11  # x轴额外加上摄像头到无人机中心的距离
                target_y = c_y + offset_y
                rospy.loginfo(f"uav_land calibration: [target_x: {target_x}] [target_y: {target_y}]")
                # 前往目标位置
                self.set_point(target_x, target_y, c_z)
                while not rospy.is_shutdown():
                    rospy.sleep(0.2)
                    # ---等待无人机到达航点---
                    bool_state = self.get_state(target_x, target_y, c_z, 0.1)
                    if bool_state == True:
                        rospy.loginfo("uav_land calibration end")
                        break
        # 开始降落
        rospy.loginfo("land start")
        mode_srv = SetModeRequest()
        mode_srv.base_mode = 1
        mode_srv.custom_mode = "Land"
        mode_response = self.mode_client.call(mode_srv)
        if (mode_response.mode_sent == False):
            return False
        else:
            return True
            
            
    def position_calibration(self, frame, height):
        """
        获取摄像头视野内的圆心与摄像头中心在ros坐标系的偏差值
        :param frame: 从get_img()函数得到的图像帧
        :param height: 摄像头当前的高度
        :return: (True, offset_x, offset_y)，是否有圆（有识别结果），ros坐标系下的x轴偏差，ros坐标系下的y轴偏差
        # 计算时可直接拿无人机当前位置加上该函数返回结果得到目标位置
        """
        PIX_SIZE = 3          # 3um微米                       # HBVCAM-F2619HD V11
        PIX_EFL = 3.2 * 1000  # 3.2mm毫米，乘1000统一到微米   # HBVCAM-F2619HD V11
        # 转换系数
        coefficient = (PIX_SIZE) / (PIX_EFL * height)  # 一个像素点代表的实际距离大小
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kernel = np.ones((4, 4), np.uint8)
        opening = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)  # 形态学开运算
        bila = cv2.bilateralFilter(opening, 10, 100, 200)  # 双边滤波消除噪声
        edges = cv2.Canny(bila, 60, 100)  # 边缘识别
        cv2.imwrite("/home/orangepi/ctrl_ws/src/competition_pkg/scripts/test_image/uav_ctrl_tools_position_calibration_1.jpg", opening)
        cv2.imwrite("/home/orangepi/ctrl_ws/src/competition_pkg/scripts/test_image/uav_ctrl_tools_position_calibration_2.jpg", bila)
        cv2.imwrite("/home/orangepi/ctrl_ws/src/competition_pkg/scripts/test_image/uav_ctrl_tools_position_calibration_3.jpg", edges)
        circles = cv2.HoughCircles(edges, cv2.HOUGH_GRADIENT, dp=1.0, minDist=50, param1=20, param2=20, minRadius=40, maxRadius=200) # 霍夫圆检测
        if circles is not None and len(circles[0]) > 0:
            # 读取圆
            x, y, r = circles[0][0].astype(int)
            # 绘制圆
            vis_frame = frame.copy()
            cv2.circle(vis_frame, (x, y), r, (0, 255, 0), 2)
            cv2.circle(vis_frame, (x, y), 5, (0, 0, 255), -1)
            # 发布
            self.image_pub_circle.publish(self.bridge.cv2_to_imgmsg(vis_frame, "bgr8"))
            
            # 计算实际偏差
            temp_x = coefficient*(x - (frame.shape[1]/2)) # 单位：米
            temp_y = coefficient*(y - (frame.shape[0]/2))
            # 将偏差从图像坐标系转为ros坐标系
            offset_x = - temp_y
            offset_y = - temp_x 
            rospy.logwarn("have circle")
            return True, offset_x, offset_y
        else:
            rospy.logwarn("No circle detected.")   
            return False, 0.0, 0.0
        
            
    def add_point(self,add_x, add_y, add_z, add_task_flag):
        """向队列尾部添加航点"""
        self.target_points.append(Point(add_x, add_y, add_z, add_task_flag))
        
        
    def get_point(self):
        """
        从队列头部取出一个航点
        :return: (have_point, x, y, z, task_flag)
        """
        if len(self.target_points) == 0:
            return False, 0.0,0.0,0.0, 0
        cur_point :Point = self.target_points.popleft()
        return True, cur_point.x, cur_point.y, cur_point.z, cur_point.task_flag   
        
        
    def set_point(self,p_x,p_y,p_z):
        """设置期望目标点"""
        p_x, p_y = self._world_to_drifted_map(p_x, p_y)
        print(f"x_map: {p_x}   y_map: {p_y}")
        self.target_point_cmd.header.stamp = rospy.Time.now()
        self.target_point_cmd.coordinate_frame = self.target_point_cmd.FRAME_LOCAL_NED
        self.target_point_cmd.type_mask = PositionTarget.IGNORE_VX | PositionTarget.IGNORE_VY | PositionTarget.IGNORE_VZ | PositionTarget.IGNORE_AFX | PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ | PositionTarget.IGNORE_YAW_RATE
        self.target_point_cmd.position.x = p_x 
        self.target_point_cmd.position.y = p_y
        self.target_point_cmd.position.z = p_z
        self.target_point_cmd.yaw = 0.0
        self.nav_pub.publish(self.target_point_cmd)


    def set_yaw(self, target_yaw, step_rad = 0.05):  # rad  90degrees = 1.57
        """设置期望偏航角，阻塞等待直到偏航角误差 < 0.05 rad"""
        cur_yaw = self._wrap_angle(self.current_yaw)
        target_yaw = self._wrap_angle(target_yaw)
        error_yaw = self._wrap_angle(target_yaw - cur_yaw)
        print(f"cur_yaw: {cur_yaw:.4f}   target_yaw: {target_yaw:.4f}   error_yaw: {error_yaw:.4f}")
        if abs(error_yaw) < 0.01:
            rospy.loginfo("abs(error_yaw) < 0.01")
            return True
        # 计算中间角度序列
        steps = max(1, int(abs(error_yaw) / step_rad))
        step_size = error_yaw / steps
        yaw_sequence = [self._wrap_angle(cur_yaw + step_size * i) for i in range(1, steps + 1)]
        try:
            # 发布中间点
            cur_pose = self.current_pos.pose.pose.position
            for yaw in yaw_sequence:
                #print(yaw)
                self.target_point_cmd.header.stamp = rospy.Time.now()
                self.target_point_cmd.coordinate_frame = self.target_point_cmd.FRAME_LOCAL_NED
                self.target_point_cmd.type_mask = (
                    PositionTarget.IGNORE_VX | PositionTarget.IGNORE_VY | PositionTarget.IGNORE_VZ |
                    PositionTarget.IGNORE_AFX | PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ |
                    PositionTarget.IGNORE_YAW_RATE
                )
                self.target_point_cmd.position.x = cur_pose.x
                self.target_point_cmd.position.y = cur_pose.y
                self.target_point_cmd.position.z = cur_pose.z
                self.target_point_cmd.yaw = yaw
                self.nav_pub.publish(self.target_point_cmd)
                rospy.sleep(0.1)
            # 阻塞等待到达
            while not rospy.is_shutdown():
                error = abs(self._wrap_angle(self.current_yaw - target_yaw))
                print(f"current_yaw: {self.current_yaw:.4f}   target_yaw: {target_yaw:.4f}   error: {error:.4f}")
                if error < 0.05:
                    rospy.logwarn("Turn done!!!")
                    return True
                rospy.sleep(0.1)
        except Exception as e:
            print(e)
        return True


    def get_local(self):
        """获取当前位置"""
        x = self.current_pos.pose.pose.position.x
        y = self.current_pos.pose.pose.position.y
        z = self.current_pos.pose.pose.position.z
        return x,y,z
        
        
    def get_state(self, x, y, z, precision_value = 0.2):
        """判断是否到达x, y, z 以及判断精度precision_value"""
        current_x,current_y,current_z = self.get_local()
        x, y = self._world_to_drifted_map(x, y)
        if (abs(current_x-x)<=precision_value and abs(current_y-y)<=precision_value and abs(current_z-z)<=0.3):
            return True
        return False
        
        
    def get_img(self):
        """获取/image话题图像"""  
        img_data = rospy.wait_for_message("/image", Image, timeout=None)
        img_raw = self.bridge.imgmsg_to_cv2(img_data, "bgr8")
        return img_raw
        
    '''
    def get_img2(self):
        """获取/image2话题图像"""  
        img_data = rospy.wait_for_message("/image2", Image, timeout=None)
        img_raw = self.bridge.imgmsg_to_cv2(img_data, "bgr8")
        return img_raw
    '''
        
    def get_rc_data(self):
        """获取遥控器rc数据""" 
        return self.current_rc
        
        
    def ctrl_servo(self, servo_id, is_open):
        """
        控制舵机
        :param servo_id: 舵机编号1,2,3
        :param is_open: True=2000us（打开），False=1000us（关闭）
        """
        if servo_id not in [1,2,3]:
            rospy.logwarn("servo_id error!!")
            return False
        pwm_out = 1000 if is_open == False else 2000
        pwm_srv = CommandLongRequest()
        pwm_srv.broadcast = False
        pwm_srv.command = 183
        pwm_srv.confirmation = 0
        pwm_srv.param1 = servo_id + 4
        pwm_srv.param2 = pwm_out
        pwm_response = self.command_client.call(pwm_srv)
        if (pwm_response.success == True):
            rospy.logwarn("send ctrl_servo success!!!")
            return True
        else:
            rospy.logerr("send ctrl_servo Fail!!!")
            return False


    def ctrl_buzzer(self, audio_id, audio_str = ""):
        """
        控制蜂鸣器播放预设或自定义音调
        :param audio_id: 1=短促重复, 2=升调, 3=降调, 其他=使用 audio_str
        :param audio_str: 自定义 RTTTL 字符串
        """
        if audio_id == 1:
            # 短促重复
            tune_str  = "T500O4L4CP4CP4CP4"          
        elif audio_id == 2:
            # 升调
            tune_str  = "T600O4L4CDEFG"       
        elif audio_id == 3:
            # 降调
            tune_str  = "T600O4L4GFEDC"           
        else:
            tune_str  = audio_str
        PlayTune = PlayTuneV2()
        PlayTune.tune = tune_str
        self.buzzer_pub.publish(PlayTune)
        
        
    def ctrl_laser(self, is_open):
        """
        控制激光笔亮灭
        :param is_open: True= 打开激光笔，False= 关闭激光笔
        """
        laser_out = 1 if is_open == True else 0
        laser_srv = CommandLongRequest()
        laser_srv.broadcast = False
        laser_srv.command = 181
        laser_srv.confirmation = 0
        laser_srv.param1 = 0
        laser_srv.param2 = laser_out
        laser_response = self.command_client.call(laser_srv)
        if (laser_response.success == True):
            rospy.logwarn("send ctrl_laser success!!!")
            return True
        else:
            rospy.logerr("send ctrl_laser Fail!!!")
            return False
