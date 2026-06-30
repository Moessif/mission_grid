"""
任务代码生成器模块
==================

将网格配置和路径规划结果导出为可部署到机载电脑的 Python 任务脚本。

本模块包含：
- export_mission(): 主入口函数，生成完整任务包
- _build_waypoints(): 构建航点数据列表
- _generate_mission_script(): 生成 Python 任务脚本（含触发条件逻辑）
- _generate_action_code(): 为单个动作生成 Python 代码片段
- _generate_shell_script(): 生成 Shell 启动脚本（source ROS + 启动驱动）

依赖关系：
    models ← 本模块（GridConfig, CellAction）
    path_planner ← 本模块（plan_path 路径规划）
    本模块 → main_window（被 MainWindow._export 调用）

生成的任务包结构：
    mission_grid_YYYYMMDD_HHMMSS/
    ├── generated_mission.py    # Python 任务脚本
    ├── run_mission.sh          # Shell 启动脚本
    └── mission_config.json     # 航点和动作配置（JSON）

生成的 Python 脚本特性：
    - 使用 uav_ctrl_tools.CtrlTools 接口控制无人机
    - 坐标转换：网格坐标 → MAVROS 坐标（通过 init_yaw 旋转）
    - 触发条件系统：visit_counts + visit_totals + main_done
    - 主线任务追踪：visited_main >= main_task_set 判断
    - 动作执行计数：executed defaultdict 追踪各类动作执行次数
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .models import CellAction, GridConfig
from .path_planner import plan_path


# ============================================================
# 航点构建
# ============================================================

def _build_waypoints(config: GridConfig, path: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
    """
    将路径坐标序列转换为航点数据列表。

    每个航点包含：
    - col, row: 网格坐标
    - grid_x, grid_y: 物理坐标（米）
    - altitude: 飞行高度
    - actions: 该格子的动作列表（含类型、触发条件、参数）
    """
    waypoints = []
    for col, row in path:
        gx, gy = config.grid_to_xy(col, row)
        actions = config.actions.get((col, row), [])
        wp = {
            "col": col,
            "row": row,
            "grid_x": round(gx, 4),
            "grid_y": round(gy, 4),
            "altitude": config.flight_altitude,
            "actions": [{"type": a.action_type, "triggers": a.triggers, **a.params} for a in actions],
        }
        waypoints.append(wp)
    return waypoints


# ============================================================
# Python 任务脚本生成
# ============================================================

def _generate_mission_script(config: GridConfig, waypoints: List[Dict]) -> str:
    """
    生成完整的 Python 任务脚本。

    脚本结构：
    1. 导入和配置加载
    2. _check_main_done() 函数（主线任务完成判断）
    3. main() 函数：
       - RC 解锁等待
       - 起飞
       - 记录起飞原点和初始航向
       - 按路径顺序执行航点（含坐标转换和触发条件判断）
       - 降落

    触发条件逻辑：
    - always: 无条件执行
    - first_visit: visit_counts[格子] == 1
    - last_visit: visit_counts[格子] == visit_totals[格子]
    - main_task_done: main_done 全局变量为 True
    - 多条件使用 Python and 运算符连接
    """
    # 确定主线任务格子（如果未设置则默认为所有有动作的格子）
    main_cells = config.main_task_cells
    if not main_cells:
        main_cells = {(wp['col'], wp['row']) for wp in waypoints if wp.get('actions')}
    main_cells_code = ", ".join(f"({c}, {r})" for c, r in sorted(main_cells))
    global_conditions = config.main_task_conditions

    # 检查是否有降落动作
    has_land_action = any(
        action.get("type") == "land"
        for wp in waypoints
        for action in wp.get("actions", [])
    )

    # 获取起飞点坐标
    takeoff_col = config.takeoff_col
    takeoff_row = config.takeoff_row
    takeoff_gx, takeoff_gy = config.grid_to_xy(takeoff_col, takeoff_row)

    # 统计各类动作总数（用于执行计数检查）
    action_totals: Dict[str, int] = {}
    for wp in waypoints:
        for action in wp.get("actions", []):
            atype = action.get("type", "")
            if atype == "land":
                continue
            action_totals[atype] = action_totals.get(atype, 0) + 1

    # 动作类型 → 执行计数键名映射
    action_type_labels = {
        "yolo_detect": "detect", "qr_scan": "qr", "photo": "photo",
    }
    totals_code_parts = []
    for atype, total in action_totals.items():
        key = action_type_labels.get(atype, atype)
        totals_code_parts.append(f'"{key}": {total}')
    action_totals_code = ", ".join(totals_code_parts)

    # 为每个航点生成代码块
    action_blocks = []
    for i, wp in enumerate(waypoints):
        block = f"    # Waypoint {i}: {config.cell_label(wp['col'], wp['row'])}\n"
        block += f"    gx, gy = {wp['grid_x']}, {wp['grid_y']}\n"
        # 坐标转换：网格 → MAVROS（通过 init_yaw 旋转）
        block += f"    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)\n"
        block += f"    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)\n"
        block += f"    uav.set_point(mx, my, {wp['altitude']})\n"
        block += f"    while not uav.get_state(mx, my, {wp['altitude']}):\n"
        block += f"        rospy.sleep(0.2)\n"
        # 记录访问次数
        block += f"    visit_counts[({wp['col']}, {wp['row']})] += 1\n"
        block += f"    if ({wp['col']}, {wp['row']}) in main_task_set:\n"
        block += f"        visited_main.add(({wp['col']}, {wp['row']}))\n"
        # 生成动作代码（含触发条件判断）
        for action in wp.get("actions", []):
            atype = action.get("type", "")
            triggers = action.get("triggers", ["always"])
            conditions = []
            for t in triggers:
                if t == "first_visit":
                    conditions.append(f"visit_counts[({wp['col']}, {wp['row']})] == 1")
                elif t == "last_visit":
                    conditions.append(f"visit_counts[({wp['col']}, {wp['row']})] == visit_totals[({wp['col']}, {wp['row']})]")
                elif t == "main_task_done":
                    conditions.append("main_done")
                elif t == "always":
                    conditions.append("True")
            action_code = _generate_action_code(action)
            if atype != "land" and atype in action_type_labels:
                key = action_type_labels[atype]
                action_code = action_code.rstrip("\n") + f'\n    executed["{key}"] += 1\n'
            if conditions:
                block += f"    if {' and '.join(conditions)}:\n"
                for line in action_code.rstrip("\n").split("\n"):
                    block += f"        {line}\n"
            else:
                block += action_code
        all_wp_count = len(waypoints)
        block += f"    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, {all_wp_count})\n"
        block += "\n"
        action_blocks.append(block)
    actions_code = "\n".join(action_blocks) if action_blocks else "    pass"

    # 预计算每个格子的访问总次数（用于 last_visit 判断）
    visit_totals_code = ", ".join(
        f"({wp['col']}, {wp['row']}): {sum(1 for w2 in waypoints if w2['col'] == wp['col'] and w2['row'] == wp['row'])}"
        for wp in {f"{w['col']},{w['row']}": w for w in waypoints}.values()
    )

    # 模板字符串生成完整脚本
    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import math
import os
import sys
import cv2
import rospy
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import uav_ctrl_tools as ctrl_tools

CONFIG = json.loads((SCRIPT_DIR / "mission_config.json").read_text(encoding="utf-8"))


def _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, all_wp_count):
    global main_done
    if not (visited_main >= main_task_set):
        main_done = False
        return
    for cond in global_conditions:
        if cond == "all_visited":
            if len(visit_counts) < all_wp_count:
                main_done = False
                return
        elif cond == "all_actions_done":
            for key, total in action_totals.items():
                if executed.get(key, 0) < total:
                    main_done = False
                    return
        elif cond == "all_detect_done":
            if executed.get("detect", 0) < action_totals.get("detect", 0):
                main_done = False
                return
        elif cond == "all_qr_done":
            if executed.get("qr", 0) < action_totals.get("qr", 0):
                main_done = False
                return
        elif cond == "all_photo_done":
            if executed.get("photo", 0) < action_totals.get("photo", 0):
                main_done = False
                return
    main_done = True


def main():
    global main_done
    rospy.init_node("mission_grid")
    # 设置虚拟航点参数（CtrlTools 构造函数要求至少一个 ~point_N 参数）
    rospy.set_param("~point_0", [0.0, 0.0, 0.0])
    uav = ctrl_tools.CtrlTools()
    rospy.loginfo("Waiting for RC unlock...")
    rc_ok = uav.set_rc_to_start()
    if not rc_ok:
        rospy.logerr("RC unlock failed")
        return
    uav.ctrl_buzzer(1)
    rospy.sleep(3.0)
    takeoff_ok = uav.uav_takeoff()
    if not takeoff_ok:
        rospy.logerr("Takeoff failed")
        return
    rospy.sleep(2.0)

    origin_x, origin_y, _ = uav.get_local()
    init_yaw = uav.init_yaw
    rospy.loginfo(f"Origin: ({{origin_x:.2f}}, {{origin_y:.2f}}), yaw: {{math.degrees(init_yaw):.1f}}")

    visit_counts = defaultdict(int)
    visit_totals = {{{visit_totals_code}}}
    main_task_set = {{{main_cells_code}}}
    visited_main = set()
    main_done = False
    global_conditions = {global_conditions!r}
    executed = defaultdict(int)
    action_totals = {{{action_totals_code}}}

{actions_code}

    # 检查是否需要返回起飞点降落
    has_land = {has_land_action!r}
    if not has_land:
        # 没有设置降落动作，返回起飞点降落
        rospy.loginfo("No land action set, returning to takeoff point...")
        takeoff_gx, takeoff_gy = {takeoff_gx}, {takeoff_gy}
        takeoff_mx = origin_x + takeoff_gy * math.cos(init_yaw) - takeoff_gx * math.sin(init_yaw)
        takeoff_my = origin_y + takeoff_gy * math.sin(init_yaw) + takeoff_gx * math.cos(init_yaw)
        uav.set_point(takeoff_mx, takeoff_my, {config.flight_altitude})
        while not uav.get_state(takeoff_mx, takeoff_my, {config.flight_altitude}):
            rospy.sleep(0.2)
        rospy.sleep(1.0)
        rospy.loginfo("Mission complete, landing...")
        uav.uav_land()
        rospy.sleep(5.0)
    else:
        rospy.loginfo("Mission complete (land action already executed)")


if __name__ == "__main__":
    main()
'''


# ============================================================
# 单个动作代码生成
# ============================================================

def _generate_action_code(action: Dict) -> str:
    """
    为单个动作生成 Python 代码片段。

    支持的动作类型及其生成的代码：
    - photo: 调用 uav.get_img() + cv2.imwrite() 保存图片
    - qr_scan: 调用 pyzbar 解码二维码 + 保存图片
    - yolo_detect: 加载 YOLO 模型 + predict + 按类别保存
    - h_land: H 点识别降落（占位）
    - land: 直接降落
    - set_yaw: 设置航向角
    - buzzer: 蜂鸣器响铃
    - servo: 舵机开关
    - laser: 激光开关
    """
    atype = action["type"]
    if atype == "photo":
        save_dir = action.get("save_dir", "/home/orangepi/Desktop/captures")
        prefix = action.get("prefix", "photo")
        return f"""    frame = uav.get_img()
    os.makedirs("{save_dir}", exist_ok=True)
    ts = int(rospy.get_time() * 1000)
    cv2.imwrite(os.path.join("{save_dir}", f"{prefix}_{{ts}}.jpg"), frame)
    rospy.loginfo("Photo saved")
"""
    elif atype == "qr_scan":
        save_dir = action.get("save_dir", "/home/orangepi/Desktop/qr_results")
        return f"""    import pyzbar.pyzbar as pyzbar
    frame = uav.get_img()
    decoded = pyzbar.decode(frame)
    for d in decoded:
        rospy.loginfo(f"QR: {{d.data.decode()}}")
    os.makedirs("{save_dir}", exist_ok=True)
    ts = int(rospy.get_time() * 1000)
    cv2.imwrite(os.path.join("{save_dir}", f"qr_{{ts}}.jpg"), frame)
"""
    elif atype == "yolo_detect":
        model_path = action.get("model_path", "/home/orangepi/ctrl_ws/src/competition_pkg/scripts/animal82.onnx")
        save_dir = action.get("save_dir", "/home/orangepi/Desktop/yolo_results")
        conf = action.get("confidence", 0.6)
        return f"""    from ultralytics import YOLO
    model = YOLO("{model_path}")
    frame = uav.get_img()
    results = model.predict(frame, save=False, imgsz=800, conf={conf})
    os.makedirs("{save_dir}", exist_ok=True)
    for r in results:
        for box in r.boxes:
            cls_name = r.names[int(box.cls[0])]
            cls_dir = os.path.join("{save_dir}", cls_name)
            os.makedirs(cls_dir, exist_ok=True)
            ts = int(rospy.get_time() * 1000)
            cv2.imwrite(os.path.join(cls_dir, f"{{cls_name}}_{{ts}}.jpg"), frame)
            rospy.loginfo(f"Detected: {{cls_name}}")
"""
    elif atype == "h_land":
        return """    rospy.loginfo("H-landing: searching for H marker...")
    rospy.sleep(1.0)
"""
    elif atype == "land":
        return """    uav.uav_land()
    rospy.sleep(5.0)
"""
    elif atype == "set_yaw":
        yaw = action.get("yaw_deg", 90)
        return f"    uav.set_yaw(math.radians({yaw}))\n    rospy.sleep(1.0)\n"
    elif atype == "buzzer":
        audio_id = action.get("audio_id", 1)
        return f"    uav.ctrl_buzzer({audio_id})\n    rospy.sleep(0.5)\n"
    elif atype == "servo":
        servo_id = action.get("servo_id", 1)
        state = "True" if action.get("open_servo", True) else "False"
        return f"    uav.ctrl_servo({servo_id}, {state})\n    rospy.sleep(0.5)\n"
    elif atype == "laser":
        state = "True" if action.get("laser_on", True) else "False"
        duration = action.get("duration_sec", 0.5)
        return f"    uav.ctrl_laser({state})\n    rospy.sleep({duration})\n    uav.ctrl_laser(False)\n"
    return f"    rospy.loginfo('Unknown action: {atype}')\n"


# ============================================================
# Shell 启动脚本生成
# ============================================================

def _generate_shell_script(config: GridConfig) -> str:
    """
    生成 Shell 启动脚本。

    脚本功能：
    1. Source ROS 和所有工作空间（tools_ws → livox_ws → ctrl_ws）
    2. 设置 LD_PRELOAD（PyTorch 需要）
    3. 按顺序启动 ROS 节点（MAVROS → Livox → 相机）
    4. 启动 SLAM 并等待定位稳定（node_manage.py）
    5. 运行生成的 Python 任务脚本
    6. 退出时清理所有后台进程
    """
    return f"""#!/bin/bash
set -euo pipefail
SCRIPT_DIR=\"$(cd \"$(dirname \"${{BASH_SOURCE[0]}}\")\" && pwd)\"
cleanup() {{ for pid in $(jobs -p); do kill \"$pid\" >/dev/null 2>&1 || true; done; }}
trap cleanup EXIT

source /opt/ros/noetic/setup.bash --extend
[ -f /home/orangepi/tools_ws/devel/setup.bash ] && source /home/orangepi/tools_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/livox_ws/devel/setup.bash ] && source /home/orangepi/livox_ws/devel/setup.bash --extend || true
[ -f /home/orangepi/ctrl_ws/devel/setup.bash ] && source /home/orangepi/ctrl_ws/devel/setup.bash --extend || true
export LD_PRELOAD=\"${{LD_PRELOAD:-/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1}}\"

roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 &
sleep 30
roslaunch livox_ros_driver2 msg_MID360s.launch &
sleep 10
roslaunch cam_pkg cam_pub.launch &
sleep 5

# 启动 SLAM 并等待定位稳定
rosrun competition_pkg node_manage.py &
sleep 15

python3 \"$SCRIPT_DIR/generated_mission.py\" \"$@\"
"""


# ============================================================
# 导出主入口
# ============================================================

def export_mission(config: GridConfig, output_dir: str) -> str:
    """
    导出完整任务包到指定目录。

    步骤：
    1. 获取路径（手动航点 或 自动规划）
    2. 构建航点数据
    3. 生成 Python 任务脚本
    4. 生成 Shell 启动脚本
    5. 生成 JSON 配置文件
    6. 写入目标目录

    参数:
        config: 网格配置
        output_dir: 输出目录路径

    返回:
        生成的 Shell 脚本路径（可用于直接执行）

    异常:
        ValueError: 无有效路径时抛出
    """
    if config.custom_waypoints:
        path = list(config.custom_waypoints)
    else:
        path = plan_path(config)
    if not path:
        raise ValueError("No path found. Check no-fly zones and action cells.")
    waypoints = _build_waypoints(config, path)
    mission_name = f"mission_grid_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bundle_dir = Path(output_dir) / mission_name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    mission_script = _generate_mission_script(config, waypoints)
    (bundle_dir / "generated_mission.py").write_text(mission_script, encoding="utf-8")
    shell_script = _generate_shell_script(config)
    run_sh = bundle_dir / "run_mission.sh"
    run_sh.write_text(shell_script, encoding="utf-8")
    mission_config = {
        "takeoff_col": config.takeoff_col,
        "takeoff_row": config.takeoff_row,
        "flight_altitude": config.flight_altitude,
        "main_task_cells": [list(c) for c in sorted(config.main_task_cells)],
        "main_task_conditions": list(config.main_task_conditions),
        "waypoints": waypoints,
    }
    (bundle_dir / "mission_config.json").write_text(
        json.dumps(mission_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(run_sh)
