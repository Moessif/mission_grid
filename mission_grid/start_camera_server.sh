#!/bin/bash
# 摄像头监控启动脚本
# 用于在 OrangePi 上启动摄像头和 web_video_server

set -e

echo "=========================================="
echo "摄像头监控启动脚本"
echo "=========================================="

# Source ROS 和工作空间
echo "[1/4] Source ROS 环境..."
source /opt/ros/noetic/setup.bash --extend
[ -f /home/orangepi/tools_ws/devel/setup.bash ] && source /home/orangepi/tools_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/livox_ws/devel/setup.bash ] && source /home/orangepi/livox_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/ctrl_ws/devel/setup.bash ] && source /home/orangepi/ctrl_ws/devel/setup.bash --extend || true

# 设置 LD_PRELOAD（PyTorch 需要）
export LD_PRELOAD="${LD_PRELOAD:-/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1}"

# 检查 roscore 是否运行
echo "[2/4] 检查 ROS Master..."
if ! rostopic list > /dev/null 2>&1; then
    echo "  ROS Master 未运行，正在启动..."
    roscore &
    sleep 5
else
    echo "  ROS Master 已运行"
fi

# 启动摄像头驱动
echo "[3/4] 启动摄像头驱动..."
roslaunch cam_pkg cam_pub.launch &
sleep 5

# 检查摄像头话题
echo "[4/4] 检查摄像头话题..."
if rostopic list | grep -q "/camera/color/image_raw"; then
    echo "  ✓ 摄像头话题已发布"
else
    echo "  ✗ 摄像头话题未找到"
    echo "  请检查摄像头连接"
fi

# 启动 web_video_server
echo ""
echo "=========================================="
echo "启动 web_video_server"
echo "=========================================="
echo ""
echo "视频流地址: http://$(hostname -I | awk '{print $1}'):8080/stream?topic=/camera/color/image_raw"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

rosrun web_video_server web_video_server
