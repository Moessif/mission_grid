#!/bin/bash
# 快速启动摄像头监控
# 在 OrangePi 上直接运行此脚本

echo "启动摄像头监控..."

# Source ROS 环境
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend 2>/dev/null || true
source /home/orangepi/livox_ws/devel/setup.bash --extend 2>/dev/null || true
source /home/orangepi/ctrl_ws/devel/setup.bash --extend 2>/dev/null || true

# 设置 LD_PRELOAD
export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1

# 启动 roscore（如果没有运行）
if ! rostopic list > /dev/null 2>&1; then
    echo "启动 ROS Master..."
    roscore &
    sleep 5
fi

# 启动摄像头驱动
echo "启动摄像头驱动..."
roslaunch cam_pkg cam_pub.launch &
sleep 5

# 启动 web_video_server
echo "启动 web_video_server..."
echo ""
echo "=========================================="
echo "视频流地址: http://10.209.49.217:8080/stream?topic=/camera/color/image_raw"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止"
echo ""

rosrun web_video_server web_video_server
