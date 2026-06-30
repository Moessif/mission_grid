#!/bin/bash
# MissionGrid 摄像头和点云服务启动脚本
# 在 OrangePi 上运行此脚本，启动 web_video_server 和 rosbridge_server

echo "=== MissionGrid 服务启动脚本 ==="
echo ""

# Source ROS 和工作空间
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend
source /home/orangepi/livox_ws/devel/setup.bash --extend
source /home/orangepi/ctrl_ws/devel/setup.bash --extend

echo "[1/4] 启动 MAVROS..."
roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 & sleep 30
echo "✓ MAVROS 已启动"

echo "[2/4] 启动 Livox 激光雷达..."
roslaunch livox_ros_driver2 msg_MID360s.launch & sleep 10
echo "✓ Livox 激光雷达已启动"

echo "[3/4] 启动摄像头..."
roslaunch cam_pkg cam_pub.launch & sleep 5
echo "✓ 摄像头已启动"

echo "[4/4] 启动 web_video_server (摄像头流)..."
rosrun web_video_server web_video_server & sleep 3
echo "✓ web_video_server 已启动 (端口 8080)"

echo ""
echo "=== 服务启动完成 ==="
echo ""
echo "摄像头视频流地址: http://$(hostname -I | awk '{print $1}'):8080/stream?topic=/camera/color/image_raw"
echo ""
echo "如需启动点云服务，请运行:"
echo "  roslaunch rosbridge_server rosbridge_websocket.launch"
echo ""
echo "点云 WebSocket 地址: ws://$(hostname -I | awk '{print $1}'):9090"
echo ""

wait
exit 0
