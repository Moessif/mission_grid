#!/bin/bash
# 编译 ROS 包脚本
# 在 OrangePi 上运行此脚本

echo "=========================================="
echo "编译 ROS 包脚本"
echo "=========================================="
echo ""

# Source ROS 环境
echo "[1/4] Source ROS 环境..."
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend 2>/dev/null || true
source /home/orangepi/livox_ws/devel/setup.bash --extend 2>/dev/null || true
source /home/orangepi/ctrl_ws/devel/setup.bash --extend 2>/dev/null || true
export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1
echo "✓ ROS 环境加载完成"
echo ""

# 编译 livox_ws（激光雷达驱动）
echo "[2/4] 编译 livox_ws（激光雷达驱动）..."
cd /home/orangepi/livox_ws
if [ -f "devel/setup.bash" ]; then
    echo "livox_ws 已编译，检查节点..."
    LIVOX_NODE=$(find devel/lib/livox_ros_driver2 -name "livox_ros_driver2_node" -type f 2>/dev/null)
    if [ -z "$LIVOX_NODE" ]; then
        echo "节点不存在，重新编译..."
        catkin_make
    else
        echo "✓ 节点存在: $LIVOX_NODE"
    fi
else
    echo "首次编译 livox_ws..."
    catkin_make
fi
echo ""

# 编译 tools_ws（SLAM 等）
echo "[3/4] 编译 tools_ws（SLAM 等）..."
cd /home/orangepi/tools_ws
if [ -f "devel/setup.bash" ]; then
    echo "tools_ws 已编译，检查节点..."
    SLAM_NODE=$(find devel/lib/fast_lio -name "fastlio_mapping" -type f 2>/dev/null)
    if [ -z "$SLAM_NODE" ]; then
        echo "SLAM 节点不存在，重新编译..."
        catkin_make
    else
        echo "✓ SLAM 节点存在: $SLAM_NODE"
    fi
else
    echo "首次编译 tools_ws..."
    catkin_make
fi
echo ""

# 编译 ctrl_ws（竞赛包）
echo "[4/4] 编译 ctrl_ws（竞赛包）..."
cd /home/orangepi/ctrl_ws
if [ -f "devel/setup.bash" ]; then
    echo "ctrl_ws 已编译，检查节点..."
    COMP_NODE=$(find devel/lib/competition_pkg -name "node_manage.py" -type f 2>/dev/null)
    if [ -z "$COMP_NODE" ]; then
        echo "竞赛包节点不存在，重新编译..."
        catkin_make
    else
        echo "✓ 竞赛包节点存在: $COMP_NODE"
    fi
else
    echo "首次编译 ctrl_ws..."
    catkin_make
fi
echo ""

echo "=========================================="
echo "编译完成"
echo "=========================================="
echo ""

# 验证编译结果
echo "验证编译结果:"
echo ""

echo "1. Livox 激光雷达驱动:"
LIVOX_NODE=$(find /home/orangepi/livox_ws/devel/lib/livox_ros_driver2 -name "livox_ros_driver2_node" -type f 2>/dev/null)
if [ -n "$LIVOX_NODE" ]; then
    echo "   ✓ $LIVOX_NODE"
else
    echo "   ✗ 节点未找到"
fi
echo ""

echo "2. SLAM (fast_lio):"
SLAM_NODE=$(find /home/orangepi/tools_ws/devel/lib/fast_lio -name "fastlio_mapping" -type f 2>/dev/null)
if [ -n "$SLAM_NODE" ]; then
    echo "   ✓ $SLAM_NODE"
else
    echo "   ✗ 节点未找到"
fi
echo ""

echo "3. 竞赛包 (competition_pkg):"
COMP_NODE=$(find /home/orangepi/ctrl_ws/devel/lib/competition_pkg -name "node_manage.py" -type f 2>/dev/null)
if [ -n "$COMP_NODE" ]; then
    echo "   ✓ $COMP_NODE"
else
    echo "   ✗ 节点未找到"
fi
echo ""

echo "=========================================="
echo "下一步"
echo "=========================================="
echo ""
echo "编译完成后，重新运行原厂脚本:"
echo "bash self_start.sh"
echo ""
