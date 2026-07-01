#!/bin/bash
# 修复节点权限脚本
# 在 OrangePi 上运行此脚本

echo "=========================================="
echo "修复节点权限脚本"
echo "=========================================="
echo ""

# Source ROS 环境
echo "[1/5] Source ROS 环境..."
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend
source /home/orangepi/livox_ws/devel/setup.bash --extend
source /home/orangepi/ctrl_ws/devel/setup.bash --extend
export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1
echo "✓ ROS 环境加载完成"
echo ""

# 修复 cam_pkg/display.py 权限
echo "[2/5] 修复 cam_pkg/display.py 权限..."
CAM_PKG_PATH=$(rospack find cam_pkg 2>/dev/null)
if [ -n "$CAM_PKG_PATH" ]; then
    echo "cam_pkg 路径: $CAM_PKG_PATH"
    if [ -f "$CAM_PKG_PATH/scripts/display.py" ]; then
        echo "找到 display.py，正在添加执行权限..."
        chmod +x $CAM_PKG_PATH/scripts/display.py
        echo "✓ display.py 权限已修复"
    else
        echo "✗ display.py 不存在"
        echo "检查 scripts 目录内容:"
        ls -la $CAM_PKG_PATH/scripts/ 2>/dev/null || echo "  scripts 目录不存在"
    fi
else
    echo "✗ cam_pkg 包不存在"
fi
echo ""

# 修复 livox_ros_driver2_node 权限
echo "[3/5] 修复 livox_ros_driver2_node 权限..."
LIVOX_PKG_PATH=$(rospack find livox_ros_driver2 2>/dev/null)
if [ -n "$LIVOX_PKG_PATH" ]; then
    echo "livox_ros_driver2 路径: $LIVOX_PKG_PATH"
    LIVOX_NODE=$(find $LIVOX_PKG_PATH -name "livox_ros_driver2_node" -type f 2>/dev/null)
    if [ -n "$LIVOX_NODE" ]; then
        echo "找到 livox_ros_driver2_node，正在添加执行权限..."
        chmod +x $LIVOX_NODE
        echo "✓ livox_ros_driver2_node 权限已修复"
    else
        echo "✗ livox_ros_driver2_node 不存在"
        echo "检查包内容:"
        find $LIVOX_PKG_PATH -type f -name "*node*" 2>/dev/null
    fi
else
    echo "✗ livox_ros_driver2 包不存在"
fi
echo ""

# 修复 node_manage.py 权限
echo "[4/5] 修复 node_manage.py 权限..."
NODE_MANAGE_PATH="/home/orangepi/ctrl_ws/src/competition_pkg/scripts/node_manage.py"
if [ -f "$NODE_MANAGE_PATH" ]; then
    echo "找到 node_manage.py，正在添加执行权限..."
    chmod +x $NODE_MANAGE_PATH
    echo "✓ node_manage.py 权限已修复"
else
    echo "✗ node_manage.py 不存在"
fi
echo ""

# 检查所有节点文件权限
echo "[5/5] 检查所有节点文件权限..."
echo ""

echo "cam_pkg 节点文件:"
CAM_PKG_PATH=$(rospack find cam_pkg 2>/dev/null)
if [ -n "$CAM_PKG_PATH" ]; then
    ls -la $CAM_PKG_PATH/scripts/ 2>/dev/null || echo "  scripts 目录不存在"
fi
echo ""

echo "livox_ros_driver2 节点文件:"
LIVOX_PKG_PATH=$(rospack find livox_ros_driver2 2>/dev/null)
if [ -n "$LIVOX_PKG_PATH" ]; then
    find $LIVOX_PKG_PATH -type f -name "*node*" -exec ls -la {} \; 2>/dev/null
fi
echo ""

echo "competition_pkg 节点文件:"
ls -la /home/orangepi/ctrl_ws/src/competition_pkg/scripts/ 2>/dev/null | head -10
echo ""

echo "=========================================="
echo "修复完成"
echo "=========================================="
echo ""
echo "现在可以重新运行 self_start.sh 测试:"
echo "bash self_start.sh"
echo ""
