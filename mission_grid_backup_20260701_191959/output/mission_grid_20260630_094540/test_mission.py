#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
不起飞测试版本 - 用于验证任务脚本逻辑
不实际飞行，只打印执行步骤
"""
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
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
    print("=" * 60)
    print("不起飞测试模式 - 只验证逻辑，不实际飞行")
    print("=" * 60)
    print()

    # 模拟起飞（不实际执行）
    print("[模拟] 起飞...")
    print("[模拟] 等待 RC 解锁...")
    print("[模拟] 蜂鸣器响...")
    print()

    # 模拟获取位置
    origin_x, origin_y = 0.0, 0.0
    init_yaw = 0.0
    print(f"[模拟] 起飞位置: ({origin_x:.2f}, {origin_y:.2f})")
    print(f"[模拟] 初始航向: {math.degrees(init_yaw):.1f}°")
    print()

    visit_counts = defaultdict(int)
    visit_totals = {(8, 0): 2, (7, 1): 1, (7, 2): 1, (7, 3): 1, (8, 2): 1, (8, 1): 1}
    main_task_set = {(7, 3), (8, 0)}
    visited_main = set()
    main_done = False
    global_conditions = []
    executed = defaultdict(int)
    action_totals = {"takeoff": 2, "photo": 1}

    # Waypoint 0: A9B1
    print("Waypoint 0: A9B1")
    gx, gy = 0.0, 0.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(8, 0)] += 1
    if (8, 0) in main_task_set:
        visited_main.add((8, 0))
    print("  [动作] Unknown action: takeoff")
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # Waypoint 1: A8B2
    print("Waypoint 1: A8B2")
    gx, gy = 0.5, 0.5
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(7, 1)] += 1
    if (7, 1) in main_task_set:
        visited_main.add((7, 1))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # Waypoint 2: A8B3
    print("Waypoint 2: A8B3")
    gx, gy = 0.5, 1.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(7, 2)] += 1
    if (7, 2) in main_task_set:
        visited_main.add((7, 2))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # Waypoint 3: A8B4
    print("Waypoint 3: A8B4")
    gx, gy = 0.5, 1.5
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(7, 3)] += 1
    if (7, 3) in main_task_set:
        visited_main.add((7, 3))
    print("  [动作] 拍照保存")
    print("    - 保存目录: /home/orangepi/Desktop/captures")
    print("    - 文件名: photo_{timestamp}.jpg")
    executed["photo"] += 1
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # Waypoint 4: A9B3
    print("Waypoint 4: A9B3")
    gx, gy = 0.0, 1.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(8, 2)] += 1
    if (8, 2) in main_task_set:
        visited_main.add((8, 2))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # Waypoint 5: A9B2
    print("Waypoint 5: A9B2")
    gx, gy = 0.0, 0.5
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(8, 1)] += 1
    if (8, 1) in main_task_set:
        visited_main.add((8, 1))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # Waypoint 6: A9B1
    print("Waypoint 6: A9B1")
    gx, gy = 0.0, 0.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    print(f"  [飞行] 飞到 ({mx:.2f}, {my:.2f}, 1.2)")
    visit_counts[(8, 0)] += 1
    if (8, 0) in main_task_set:
        visited_main.add((8, 0))
    print("  [动作] Unknown action: takeoff")
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)
    print()

    # 降落
    print("=" * 60)
    print("降落阶段")
    print("=" * 60)
    has_land = False
    if has_land:
        print("[降落] 降落动作已执行")
    else:
        print("[降落] 返回起飞点降落...")
        takeoff_gx, takeoff_gy = 0.0, 0.0
        takeoff_mx = origin_x + takeoff_gy * math.cos(init_yaw) - takeoff_gx * math.sin(init_yaw)
        takeoff_my = origin_y + takeoff_gy * math.sin(init_yaw) + takeoff_gx * math.cos(init_yaw)
        print(f"  [飞行] 飞到起飞点 ({takeoff_mx:.2f}, {takeoff_my:.2f}, 1.2)")
    print("[降落] 执行降落...")
    print("[降落] 等待 5 秒...")
    print()

    # 统计
    print("=" * 60)
    print("测试完成统计")
    print("=" * 60)
    print(f"访问格子数: {len(visit_counts)}")
    print(f"主线任务格子: {main_task_set}")
    print(f"已访问主线格子: {visited_main}")
    print(f"主线任务完成: {main_done}")
    print(f"执行动作统计: {dict(executed)}")
    print()


if __name__ == "__main__":
    main()
