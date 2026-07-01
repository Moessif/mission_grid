#!/bin/bash
# 摄像头诊断脚本
# 在 OrangePi 上运行此脚本，自动检测摄像头问题

echo "=========================================="
echo "摄像头诊断脚本"
echo "=========================================="
echo ""

# 1. 检查 USB 设备
echo "[1/6] 检查 USB 设备..."
echo "----------------------------------------"
lsusb
echo ""
if lsusb | grep -qi "intel\|realsense\|camera"; then
    echo "✓ 检测到摄像头设备"
else
    echo "✗ 未检测到摄像头设备"
    echo "  请检查摄像头是否已连接到 USB 端口"
fi
echo ""

# 2. 检查视频设备
echo "[2/6] 检查视频设备..."
echo "----------------------------------------"
if ls /dev/video* 2>/dev/null; then
    echo "✓ 视频设备存在"
else
    echo "✗ 未找到视频设备"
fi
echo ""

# 3. 检查 ROS 环境
echo "[3/6] 检查 ROS 环境..."
echo "----------------------------------------"
if [ -z "$ROS_DISTRO" ]; then
    echo "✗ ROS 环境未加载"
    echo "  正在 source ROS..."
    source /opt/ros/noetic/setup.bash --extend 2>/dev/null || true
    [ -f /home/orangepi/tools_ws/devel/setup.bash ] && source /home/orangepi/tools_ws/devel/setup.bash --extend 2>/dev/null || true
    [ -f /home/orangepi/livox_ws/devel/setup.bash ] && source /home/orangepi/livox_ws/devel/setup.bash --extend 2>/dev/null || true
    [ -f /home/orangepi/ctrl_ws/devel/setup.bash ] && source /home/orangepi/ctrl_ws/devel/setup.bash --extend 2>/dev/null || true
else
    echo "✓ ROS 环境已加载: $ROS_DISTRO"
fi
echo ""

# 4. 检查 ROS Master
echo "[4/6] 检查 ROS Master..."
echo "----------------------------------------"
if rostopic list > /dev/null 2>&1; then
    echo "✓ ROS Master 运行中"
else
    echo "✗ ROS Master 未运行"
    echo "  正在启动 roscore..."
    roscore &
    sleep 5
fi
echo ""

# 5. 检查可用的摄像头包
echo "[5/6] 检查可用的摄像头包..."
echo "----------------------------------------"
echo "已安装的 ROS 包:"
rospack list | grep -i "cam\|camera\|realsense" || echo "  未找到摄像头相关包"
echo ""

# 检查 cam_pkg
if rospack find cam_pkg > /dev/null 2>&1; then
    echo "✓ cam_pkg 包存在: $(rospack find cam_pkg)"
    echo "  包内容:"
    ls -la $(rospack find cam_pkg)/scripts/ 2>/dev/null || echo "    scripts 目录不存在"
else
    echo "✗ cam_pkg 包不存在"
fi

# 检查 realsense2_camera
if rospack find realsense2_camera > /dev/null 2>&1; then
    echo "✓ realsense2_camera 包存在: $(rospack find realsense2_camera)"
else
    echo "✗ realsense2_camera 包不存在"
fi

# 检查 usb_cam
if rospack find usb_cam > /dev/null 2>&1; then
    echo "✓ usb_cam 包存在: $(rospack find usb_cam)"
else
    echo "✗ usb_cam 包不存在"
fi
echo ""

# 6. 检查摄像头话题
echo "[6/6] 检查摄像头话题..."
echo "----------------------------------------"
echo "所有 ROS 话题:"
rostopic list 2>/dev/null | head -20
echo ""

CAM_TOPICS=$(rostopic list 2>/dev/null | grep -i "camera\|image\|video")
if [ -n "$CAM_TOPICS" ]; then
    echo "✓ 找到摄像头相关话题:"
    echo "$CAM_TOPICS"
else
    echo "✗ 未找到摄像头相关话题"
fi
echo ""

# 7. 生成建议
echo "=========================================="
echo "诊断结果和建议"
echo "=========================================="
echo ""

if ! lsusb | grep -qi "intel\|realsense\|camera"; then
    echo "❌ 问题：未检测到摄像头硬件"
    echo ""
    echo "解决方案："
    echo "1. 将 RealSense 摄像头连接到 OrangePi 的 USB 端口"
    echo "2. 等待几秒钟让系统识别设备"
    echo "3. 重新运行此脚本"
    echo ""
    exit 1
fi

if ! rospack find cam_pkg > /dev/null 2>&1; then
    echo "❌ 问题：cam_pkg 包不存在"
    echo ""
    echo "解决方案："
    echo "1. 安装 RealSense ROS 驱动："
    echo "   sudo apt-get update"
    echo "   sudo apt-get install ros-noetic-realsense2-camera"
    echo ""
    echo "2. 或者使用 usb_cam："
    echo "   sudo apt-get install ros-noetic-usb-cam"
    echo ""
fi

if [ -z "$CAM_TOPICS" ]; then
    echo "❌ 问题：摄像头话题未发布"
    echo ""
    echo "解决方案："
    echo "1. 启动摄像头驱动："
    echo ""
    echo "   # 如果使用 RealSense："
    echo "   roslaunch realsense2_camera rs_camera.launch &"
    echo ""
    echo "   # 如果使用 usb_cam："
    echo "   roslaunch usb_cam usb_cam-test.launch &"
    echo ""
    echo "2. 等待 5 秒后检查话题："
    echo "   rostopic list | grep camera"
    echo ""
fi

echo "=========================================="
echo "快速启动命令"
echo "=========================================="
echo ""
echo "如果摄像头已连接，请尝试以下命令："
echo ""
echo "# 安装 RealSense 驱动（如果未安装）"
echo "sudo apt-get install ros-noetic-realsense2-camera"
echo ""
echo "# 启动摄像头"
echo "roslaunch realsense2_camera rs_camera.launch &"
echo "sleep 5"
echo ""
echo "# 启动 web_video_server"
echo "rosrun web_video_server web_video_server"
echo ""
echo "=========================================="
