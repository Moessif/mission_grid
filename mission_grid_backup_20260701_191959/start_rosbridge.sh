#!/bin/bash
# 启动 rosbridge_server（点云 WebSocket 服务）
# 用于 MissionGrid 地面站 3D 点云可视化

source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend
source /home/orangepi/livox_ws/devel/setup.bash --extend

echo "启动 rosbridge_server..."
echo "WebSocket 地址: ws://$(hostname -I | awk '{print $1}'):9090"
echo ""

roslaunch rosbridge_server rosbridge_websocket.launch

exit 0
