#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cleanup() { for pid in $(jobs -p); do kill "$pid" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT

source /opt/ros/noetic/setup.bash --extend
[ -f /home/orangepi/tools_ws/devel/setup.bash ] && source /home/orangepi/tools_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/livox_ws/devel/setup.bash ] && source /home/orangepi/livox_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/ctrl_ws/devel/setup.bash ] && source /home/orangepi/ctrl_ws/devel/setup.bash --extend || true
export LD_PRELOAD="${LD_PRELOAD:-/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1}"

roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 &
sleep 30
roslaunch livox_ros_driver2 msg_MID360s.launch &
sleep 10
roslaunch cam_pkg cam_pub.launch &
sleep 5

# 启动 SLAM 并等待定位稳定
rosrun competition_pkg node_manage.py &
sleep 15

python3 "$SCRIPT_DIR/generated_mission.py" "$@"
