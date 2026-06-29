#!/usr/bin/python3
# -*- coding: utf-8 -*-

import rospy
import torch
import torch.nn as nn
import torch.nn.functional as F
import cv2
import numpy as np
import pyzbar.pyzbar as pyzbar
import time
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
import sys


# cnn网络,用于识别手写数字
class CNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 10, kernel_size=5)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(320, 50)
        self.fc2 = nn.Linear(50, 10)

    def forward(self, cnn_x):
        cnn_x = F.relu(F.max_pool2d(self.conv1(cnn_x), 2))
        cnn_x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(cnn_x)), 2))
        cnn_x = cnn_x.view(-1, 320)
        cnn_x = F.relu(self.fc1(cnn_x))
        cnn_x = self.fc2(cnn_x)
        out = F.log_softmax(cnn_x,dim=1)
        pred = out.argmax(dim=1)
        return pred.item()
        
        
class ImgTools:
    def __init__(self):
        # 加载训练好的CNN模型
        self.cnn = CNN()
        self.cnn.load_state_dict(torch.load('/home/orangepi/ctrl_ws/src/competition_pkg/scripts/model.pt', map_location='cpu'))
        self.cnn.eval()  # 设置为评估模式

        # 图像处理参数
        self.thresValue = 160
        self.kernel = np.ones((4, 4), np.uint8)
        self.bridge = CvBridge()

        # ROS发布
        self.image_pub_cnn = rospy.Publisher('/image_cnn', Image, queue_size=1, latch=True)
        self.image_pub_qr = rospy.Publisher('/image_qr', Image, queue_size=1, latch=True)
        self.image_pub_circle = rospy.Publisher('/image_circle', Image, queue_size=1, latch=True)
        
    def num(self, frame):
        """
        手写数字识别
        输入：图像
        输出：CNN 预测的数字
        """
        # 转灰度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 形态学膨胀
        dilated = cv2.morphologyEx(gray, cv2.MORPH_DILATE, self.kernel)
        # 双边滤波去噪
        filtered = cv2.bilateralFilter(dilated, 10, 100, 200)
        # 二值化
        _, thresh = cv2.threshold(filtered, self.thresValue, 255, cv2.THRESH_BINARY_INV)
        # 缩放到 28x28
        resized = cv2.resize(thresh, (28, 28), interpolation=cv2.INTER_AREA)
        # 转为 tensor [1, 1, 28, 28]
        tensor = torch.tensor(resized).float().unsqueeze(0).unsqueeze(0) / 255.0
        self.image_pub_cnn.publish(self.bridge.cv2_to_imgmsg(resized, "mono8"))
        # 推理
        with torch.no_grad():
            result = self.cnn(tensor)
        return result
    
    def qr_code(self, frame):
        """
        二维码识别
        输入：图像
        输出：二维码的文本内容，若未检测到则返回 "null"
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        decoded = pyzbar.decode(gray)
        text = "null"
        for barcode in decoded:
            pts = np.array([p for p in barcode.polygon], np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], True, (0, 0, 255), 2)
            text = barcode.data.decode("utf-8")
            x, y = barcode.polygon[0]
            cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        self.image_pub_qr.publish(self.bridge.cv2_to_imgmsg(frame, "bgr8"))
        return text  

    def detect_circle(self, frame):
        """
        检测图像中的第一个圆并返回其圆心和半径。
        输入：图像
        输出：(x, y, radius) 第一个圆的圆心坐标和半径；如果没有检测到圆则返回 (None, None, None)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        opening = cv2.morphologyEx(gray, cv2.MORPH_OPEN, self.kernel)  # 形态学开运算
        bila = cv2.bilateralFilter(opening, 10, 100, 200)  # 双边滤波消除噪声
        edges = cv2.Canny(bila, 60, 100)  # 边缘识别
        cv2.imwrite("/home/orangepi/ctrl_ws/src/competition_pkg/scripts/test_image/uav_img_tools_detect_circle_1.jpg", opening)
        cv2.imwrite("/home/orangepi/ctrl_ws/src/competition_pkg/scripts/test_image/uav_img_tools_detect_circle_2.jpg", bila)
        cv2.imwrite("/home/orangepi/ctrl_ws/src/competition_pkg/scripts/test_image/uav_img_tools_detect_circle_3.jpg", edges)
        circles = cv2.HoughCircles(edges, cv2.HOUGH_GRADIENT, dp=1.0, minDist=50, param1=20, param2=20, minRadius=40, maxRadius=200)
        if circles is not None and len(circles[0]) > 0:
            x, y, r = circles[0][0].astype(int)
            # 绘制圆
            vis_frame = frame.copy()
            cv2.circle(vis_frame, (x, y), r, (0, 255, 0), 2)
            cv2.circle(vis_frame, (x, y), 5, (0, 0, 255), -1)
            # 发布
            rospy.logwarn("have circle.") 
            self.image_pub_circle.publish(self.bridge.cv2_to_imgmsg(vis_frame, "bgr8"))
            return x, y, r
        else:
            # 发布原始图表示无圆
            self.image_pub_circle.publish(self.bridge.cv2_to_imgmsg(frame, "bgr8"))
            rospy.logwarn("No circle detected.")   
            return None, None, None
        
    def num_recognition(self, frame):
        """
        园内的手写数字识别
        1. 检测图像中的圆形区域
        2. 提取圆的内接正方形作为 ROI
        3. 对 ROI 进行数字识别
        4. 可视化结果并返回识别数字
        输入：图像
        输出：int: 识别出的数字（0~9）；若失败或未检测到圆，返回 99
        """
        # 翻转图像
        #frame = cv2.flip(frame, -1)
        
        # 检测圆形
        x, y, r = self.detect_circle(frame)
        
        if x is None or y is None or r is None:
            return 99  # 未检测到圆返回默认值
        
        # 计算圆的内接正方形ROI
        side = int(np.sqrt(2) * r)
        x1 = max(0, x - side // 2)
        y1 = max(0, y - side // 2)
        x2 = min(frame.shape[1], x + side // 2)
        y2 = min(frame.shape[0], y + side // 2)
    
        try:
            roi = frame[y1:y2, x1:x2]
            digit = self.num(roi)
            rospy.loginfo(f"Recognized digit: {digit}")
            
            # 绘制 ROI 和圆心
            cv2.rectangle(frame, (x1, y1), (x2, y2), (153, 153, 0), 2)
            cv2.circle(frame, (x, y), 6, (255, 255, 0), -1)
            text = f"x:{x} y:{y} num:{digit}"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_PLAIN, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
            
            # 发布到 self.image_pub_circle
            self.image_pub_circle.publish(self.bridge.cv2_to_imgmsg(frame, "bgr8"))
            
        except Exception as e:
            rospy.logwarn(f"Digit recognition failed: {e}")
            digit = 99
            
        return digit