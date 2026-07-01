#!/usr/bin/env python3
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
    rospy.loginfo(f"Origin: ({origin_x:.2f}, {origin_y:.2f}), yaw: {math.degrees(init_yaw):.1f}")

    visit_counts = defaultdict(int)
    visit_totals = {(8, 0): 2, (7, 1): 1, (7, 2): 1, (7, 3): 1, (8, 2): 1, (8, 1): 1}
    main_task_set = {(7, 3), (8, 0)}
    visited_main = set()
    main_done = False
    global_conditions = []
    executed = defaultdict(int)
    action_totals = {"takeoff": 2, "photo": 1}

    # Waypoint 0: A9B1
    gx, gy = 0.0, 0.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(8, 0)] += 1
    if (8, 0) in main_task_set:
        visited_main.add((8, 0))
    if True:
            rospy.loginfo('Unknown action: takeoff')
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)


    # Waypoint 1: A8B2
    gx, gy = 0.5, 0.5
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(7, 1)] += 1
    if (7, 1) in main_task_set:
        visited_main.add((7, 1))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)


    # Waypoint 2: A8B3
    gx, gy = 0.5, 1.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(7, 2)] += 1
    if (7, 2) in main_task_set:
        visited_main.add((7, 2))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)


    # Waypoint 3: A8B4
    gx, gy = 0.5, 1.5
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(7, 3)] += 1
    if (7, 3) in main_task_set:
        visited_main.add((7, 3))
    if True:
            frame = uav.get_img()
            os.makedirs("/home/orangepi/Desktop/captures", exist_ok=True)
            ts = int(rospy.get_time() * 1000)
            cv2.imwrite(os.path.join("/home/orangepi/Desktop/captures", f"photo_{ts}.jpg"), frame)
            rospy.loginfo("Photo saved")
            executed["photo"] += 1
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)


    # Waypoint 4: A9B3
    gx, gy = 0.0, 1.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(8, 2)] += 1
    if (8, 2) in main_task_set:
        visited_main.add((8, 2))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)


    # Waypoint 5: A9B2
    gx, gy = 0.0, 0.5
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(8, 1)] += 1
    if (8, 1) in main_task_set:
        visited_main.add((8, 1))
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)


    # Waypoint 6: A9B1
    gx, gy = 0.0, 0.0
    mx = origin_x + gy * math.cos(init_yaw) - gx * math.sin(init_yaw)
    my = origin_y + gy * math.sin(init_yaw) + gx * math.cos(init_yaw)
    uav.set_point(mx, my, 1.2)
    while not uav.get_state(mx, my, 1.2):
        rospy.sleep(0.2)
    visit_counts[(8, 0)] += 1
    if (8, 0) in main_task_set:
        visited_main.add((8, 0))
    if True:
            rospy.loginfo('Unknown action: takeoff')
    _check_main_done(visit_counts, visited_main, main_task_set, global_conditions, executed, action_totals, 7)



    # 降落：路径规划已包含返回起飞点的逻辑
    has_land = False
    if has_land:
        rospy.loginfo("Mission complete (land action already executed)")
    else:
        rospy.loginfo("Mission complete, returning to takeoff and landing...")
        takeoff_gx, takeoff_gy = 0.0, 0.0
        takeoff_mx = origin_x + takeoff_gy * math.cos(init_yaw) - takeoff_gx * math.sin(init_yaw)
        takeoff_my = origin_y + takeoff_gy * math.sin(init_yaw) + takeoff_gx * math.cos(init_yaw)
        uav.set_point(takeoff_mx, takeoff_my, 1.2)
        while not uav.get_state(takeoff_mx, takeoff_my, 1.2):
            rospy.sleep(0.2)
        rospy.sleep(1.0)
    rospy.loginfo("Landing...")
    uav.uav_land()
    rospy.sleep(5.0)


if __name__ == "__main__":
    main()
