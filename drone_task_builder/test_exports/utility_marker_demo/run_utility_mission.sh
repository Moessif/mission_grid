#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
    local pid
    for pid in $(jobs -p); do
        kill "$pid" >/dev/null 2>&1 || true
    done
}

trap cleanup EXIT

source /opt/ros/noetic/setup.bash --extend
[ -f /home/orangepi/tools_ws/devel/setup.bash ] && source /home/orangepi/tools_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/livox_ws/devel/setup.bash ] && source /home/orangepi/livox_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/ctrl_ws/devel/setup.bash ] && source /home/orangepi/ctrl_ws/devel/setup.bash --extend || true

export COMPETITION_PKG_SCRIPT_DIR="${COMPETITION_PKG_SCRIPT_DIR:-/home/orangepi/ctrl_ws/src/competition_pkg/scripts}"
export START_MAVROS="1"
export START_CAMERA="1"
export START_LIVOX="0"

if [ "$START_MAVROS" = "1" ]; then
    roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 &
    sleep 25
fi

if [ "$START_LIVOX" = "1" ]; then
    roslaunch livox_ros_driver2 msg_MID360s.launch &
    sleep 8
fi

if [ "$START_CAMERA" = "1" ]; then
    roslaunch cam_pkg cam_pub.launch &
    sleep 5
fi

python3 "$SCRIPT_DIR/generated_mission.py" "$@"
