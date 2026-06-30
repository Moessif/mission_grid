#!/bin/bash
# MissionGrid 全服务启动脚本
# 在 OrangePi 上运行，启动所有地面站需要的服务

echo "=========================================="
echo "  MissionGrid 服务启动"
echo "=========================================="
echo ""

# Source ROS 和工作空间
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend
source /home/orangepi/livox_ws/devel/setup.bash --extend
source /home/orangepi/ctrl_ws/devel/setup.bash --extend
export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1

IP=$(hostname -I | awk '{print $1}')
echo "本机 IP: $IP"
echo ""

# 1. MAVROS（遥测）
echo "[1/5] 启动 MAVROS（遥测）..."
roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 & sleep 30
echo "✓ MAVROS 已启动"

# 2. Livox 激光雷达
echo "[2/5] 启动 Livox 激光雷达..."
roslaunch livox_ros_driver2 msg_MID360s.launch & sleep 10
echo "✓ Livox 激光雷达已启动"

# 3. SLAM（FAST_LIO）
echo "[3/5] 启动 SLAM..."
rosrun manage_bridge_node manage_bridge_node & sleep 5
echo "✓ SLAM 已启动"

# 4. 摄像头
echo "[4/5] 启动摄像头..."
roslaunch cam_pkg cam_pub.launch & sleep 5
echo "✓ 摄像头已启动"

# 5. web_video_server（摄像头 HTTP 流）
echo "[5/5] 启动 web_video_server..."
rosrun web_video_server web_video_server & sleep 3
echo "✓ web_video_server 已启动"

echo ""
echo "=========================================="
echo "  所有服务已启动！"
echo "=========================================="
echo ""
echo "摄像头地址: http://$IP:8080/stream?topic=/camera/color/image_raw"
echo ""
echo "如需点云服务，请在新终端运行:"
echo "  ./start_rosbridge.sh"
echo ""
echo "点云地址: ws://$IP:9090"
echo ""

wait
exit 0
