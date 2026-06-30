#!/bin/bash
# 摄像头启动脚本（基于原厂配置）
# 在 OrangePi 上运行此脚本

echo "=========================================="
echo "摄像头监控启动脚本（基于原厂配置）"
echo "=========================================="
echo ""

# Source ROS 和工作空间（与原厂一致）
echo "[1/5] Source ROS 环境..."
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend
source /home/orangepi/livox_ws/devel/setup.bash --extend
source /home/orangepi/ctrl_ws/devel/setup.bash --extend
export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1
echo "✓ ROS 环境加载完成"
echo ""

# 检查 cam_pkg 包
echo "[2/5] 检查 cam_pkg 包..."
CAM_PKG_PATH=$(rospack find cam_pkg 2>/dev/null)
if [ -z "$CAM_PKG_PATH" ]; then
    echo "✗ cam_pkg 包不存在"
    exit 1
fi
echo "✓ cam_pkg 包路径: $CAM_PKG_PATH"
echo ""

# 列出 cam_pkg 包内容
echo "[3/5] 检查 cam_pkg 包内容..."
echo "scripts 目录:"
ls -la $CAM_PKG_PATH/scripts/ 2>/dev/null || echo "  scripts 目录不存在"
echo ""
echo "launch 目录:"
ls -la $CAM_PKG_PATH/launch/ 2>/dev/null || echo "  launch 目录不存在"
echo ""

# 检查 launch 文件
echo "[4/5] 检查 launch 文件..."
if [ -f "$CAM_PKG_PATH/launch/cam_pub.launch" ]; then
    echo "✓ cam_pub.launch 存在"
    echo "launch 文件内容:"
    cat $CAM_PKG_PATH/launch/cam_pub.launch
else
    echo "✗ cam_pub.launch 不存在"
    echo "尝试查找其他 launch 文件:"
    find $CAM_PKG_PATH -name "*.launch" -type f 2>/dev/null
fi
echo ""

# 启动摄像头
echo "[5/5] 启动摄像头..."
echo ""

# 检查 roscore
if ! rostopic list > /dev/null 2>&1; then
    echo "启动 ROS Master..."
    roscore &
    sleep 5
fi

# 尝试启动摄像头
echo "尝试启动 cam_pkg..."
echo ""

# 方法 1：使用 roslaunch
if [ -f "$CAM_PKG_PATH/launch/cam_pub.launch" ]; then
    echo "使用 roslaunch cam_pkg cam_pub.launch"
    roslaunch cam_pkg cam_pub.launch &
    sleep 5
fi

# 检查摄像头话题
echo ""
echo "检查摄像头话题..."
CAM_TOPICS=$(rostopic list 2>/dev/null | grep -i "camera\|image")
if [ -n "$CAM_TOPICS" ]; then
    echo "✓ 摄像头话题已发布:"
    echo "$CAM_TOPICS"
    echo ""
    echo "=========================================="
    echo "启动 web_video_server"
    echo "=========================================="
    echo ""
    IP_ADDR=$(hostname -I | awk '{print $1}')
    echo "视频流地址: http://${IP_ADDR}:8080/stream?topic=/camera/color/image_raw"
    echo ""
    echo "按 Ctrl+C 停止"
    echo ""
    rosrun web_video_server web_video_server
else
    echo "✗ 摄像头话题未发布"
    echo ""
    echo "=========================================="
    echo "故障排除"
    echo "=========================================="
    echo ""
    echo "1. 检查摄像头是否连接:"
    echo "   lsusb | grep -i intel"
    echo ""
    echo "2. 检查视频设备:"
    echo "   ls -la /dev/video*"
    echo ""
    echo "3. 手动启动摄像头节点:"
    echo "   # 查看 cam_pkg 包中的可执行文件"
    echo "   ls -la $CAM_PKG_PATH/scripts/"
    echo ""
    echo "   # 如果有 display.py，检查权限"
    echo "   chmod +x $CAM_PKG_PATH/scripts/display.py"
    echo ""
    echo "   # 手动运行"
    echo "   rosrun cam_pkg display.py"
    echo ""
    echo "4. 或者使用 RealSense 官方驱动:"
    echo "   sudo apt-get install ros-noetic-realsense2-camera"
    echo "   roslaunch realsense2_camera rs_camera.launch"
    echo ""
fi
