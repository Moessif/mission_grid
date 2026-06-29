#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import rospy
from ultralytics import YOLO


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG = json.loads((SCRIPT_DIR / "generated_runtime_config.json").read_text(encoding="utf-8"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
COMPETITION_DIR = Path(
    os.environ.get("COMPETITION_PKG_SCRIPT_DIR", CONFIG.get("competition_pkg_script_dir", "/home/orangepi/ctrl_ws/src/competition_pkg/scripts"))
)
if str(COMPETITION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPETITION_DIR))

import uav_ctrl_tools as ctrl_tools


def map_to_world(uav_ctrl, map_x, map_y):
    yaw0 = uav_ctrl.init_yaw
    world_x = map_x * math.cos(yaw0) - map_y * math.sin(yaw0)
    world_y = map_x * math.sin(yaw0) + map_y * math.cos(yaw0)
    return world_x, world_y


def wait_pose_stable(uav_ctrl, check_count, position_error, yaw_error_deg):
    if check_count <= 0:
        return True
    stable_count = 0
    last_pose = None
    last_yaw = None
    yaw_error = math.radians(yaw_error_deg)
    while not rospy.is_shutdown():
        pose = uav_ctrl.get_local()
        yaw = uav_ctrl.current_yaw
        if last_pose is None:
            stable_count = 1
        else:
            delta_pos = math.sqrt(
                (pose[0] - last_pose[0]) ** 2 +
                (pose[1] - last_pose[1]) ** 2 +
                (pose[2] - last_pose[2]) ** 2
            )
            delta_yaw = abs(((yaw - last_yaw) + math.pi) % (2.0 * math.pi) - math.pi)
            if delta_pos <= position_error and delta_yaw <= yaw_error:
                stable_count += 1
            else:
                stable_count = 1
        last_pose = pose
        last_yaw = yaw
        if stable_count >= check_count:
            return True
        rospy.sleep(0.2)
    return False


def build_grid_waypoints():
    cols = int(CONFIG["grid_cols"])
    rows = int(CONFIG["grid_rows"])
    cell_size = float(CONFIG["cell_size"])
    origin_x = float(CONFIG["origin_x"])
    origin_y = float(CONFIG["origin_y"])
    forbidden = set(CONFIG["forbidden_cells"])
    points = []
    for row in range(rows):
        row_points = []
        for col in range(cols):
            cell_name = f"{chr(ord('A') + col)}{row + 1}"
            if cell_name in forbidden:
                continue
            world_x = origin_x + (col + 0.5) * cell_size
            world_y = origin_y + (row + 0.5) * cell_size
            row_points.append((cell_name, world_x, world_y, float(CONFIG["patrol_altitude"])))
        if row % 2 == 1:
            row_points.reverse()
        points.extend(row_points)
    return points


class WildlifeMission:
    def __init__(self):
        rospy.init_node("generated_wildlife_mission")
        rospy.set_param("~point_0", [0.0, 0.0, max(1.0, CONFIG.get("patrol_altitude", 1.2)), 0])
        self.uav_ctrl = ctrl_tools.CtrlTools()
        model_path = Path(CONFIG["model_path"])
        if not model_path.is_absolute():
            model_path = SCRIPT_DIR / model_path
        self.model = YOLO(str(model_path))
        self.wait_rc = bool(CONFIG["wait_rc"])
        self.arrive_precision = float(CONFIG["arrive_precision"])
        self.hover_seconds = float(CONFIG["hover_seconds"])
        self.return_home = bool(CONFIG["return_home"])
        self.auto_land = bool(CONFIG["auto_land"])
        self.output_dir = Path(CONFIG["result_dir"]) / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir = self.output_dir / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.records = []
        self.species_counter = Counter()
        self.waypoints = build_grid_waypoints()

    def save_records(self):
        json_path = self.output_dir / "wildlife_records.json"
        csv_path = self.output_dir / "wildlife_records.csv"
        summary_path = self.output_dir / "wildlife_summary.json"
        json_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=["cell", "species", "confidence", "detect_time", "image_file"],
            )
            writer.writeheader()
            writer.writerows(self.records)
        summary_path.write_text(
            json.dumps(
                {
                    "species_counter": dict(self.species_counter),
                    "scanned_cells": [item[0] for item in self.waypoints],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def goto_point(self, world_x, world_y, world_z):
        self.uav_ctrl.set_point(world_x, world_y, world_z)
        while not rospy.is_shutdown():
            if self.uav_ctrl.get_state(world_x, world_y, world_z, self.arrive_precision):
                break
            rospy.sleep(0.2)

    def inspect_cell(self, cell_name):
        rospy.sleep(self.hover_seconds)
        frame = self.uav_ctrl.get_img()
        results = self.model.predict(frame, save=False, imgsz=800, conf=float(CONFIG["confidence"]))
        if not results:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        annotated = results[0].plot()
        image_name = f"{stamp}_{cell_name}.png"
        cv2.imwrite(str(self.image_dir / image_name), annotated)
        names = results[0].names
        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            species = str(names.get(cls_id, cls_id))
            self.species_counter[species] += 1
            self.records.append(
                {
                    "cell": cell_name,
                    "species": species,
                    "confidence": round(confidence, 3),
                    "detect_time": stamp,
                    "image_file": image_name,
                }
            )
        self.save_records()

    def return_and_land(self):
        if self.return_home:
            home_world_x, home_world_y = map_to_world(self.uav_ctrl, self.uav_ctrl.home_pose_x, self.uav_ctrl.home_pose_y)
            self.goto_point(home_world_x, home_world_y, float(CONFIG["patrol_altitude"]))
        if self.auto_land:
            self.uav_ctrl.uav_land()

    def run(self):
        wait_pose_stable(
            self.uav_ctrl,
            int(CONFIG["check_count"]),
            float(CONFIG["position_error"]),
            float(CONFIG["yaw_error"]),
        )

        if self.wait_rc:
            if self.uav_ctrl.set_rc_to_start() is False:
                rospy.logerr("remote start failed")
                return

        if self.uav_ctrl.uav_takeoff() is False:
            rospy.logerr("takeoff failed")
            return

        rospy.sleep(2.0)
        for cell_name, world_x, world_y, world_z in self.waypoints:
            self.goto_point(world_x, world_y, world_z)
            self.inspect_cell(cell_name)
        self.return_and_land()


if __name__ == "__main__":
    WildlifeMission().run()
