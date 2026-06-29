#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pyzbar.pyzbar as pyzbar
import rospy


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


def clamp(value, low, high):
    return max(low, min(high, value))


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


def decode_qrs(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    decoded = pyzbar.decode(gray)
    annotated = frame.copy()
    entries = []
    for barcode in decoded:
        text = barcode.data.decode("utf-8") if barcode.data else "null"
        polygon = [(point.x, point.y) for point in barcode.polygon] if barcode.polygon else []
        if polygon:
            np_pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(annotated, [np_pts], True, (0, 0, 255), 2)
            center_x = sum(point[0] for point in polygon) / float(len(polygon))
            center_y = sum(point[1] for point in polygon) / float(len(polygon))
        else:
            rect = barcode.rect
            center_x = rect.left + rect.width / 2.0
            center_y = rect.top + rect.height / 2.0
            cv2.rectangle(
                annotated,
                (rect.left, rect.top),
                (rect.left + rect.width, rect.top + rect.height),
                (0, 0, 255),
                2,
            )
        cv2.circle(annotated, (int(center_x), int(center_y)), 5, (0, 255, 0), -1)
        cv2.putText(
            annotated,
            text,
            (int(center_x) + 5, int(center_y) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        entries.append({"text": text, "center_px": (center_x, center_y)})
    return entries, annotated


def face_slot_name(face_name, center_px, frame_shape, margin_ratio):
    img_h, img_w = frame_shape[:2]
    margin_x = img_w * margin_ratio
    margin_y = img_h * margin_ratio
    usable_x = clamp((center_px[0] - margin_x) / max(1.0, img_w - 2.0 * margin_x), 0.0, 0.9999)
    usable_y = clamp((center_px[1] - margin_y) / max(1.0, img_h - 2.0 * margin_y), 0.0, 0.9999)
    col = min(2, int(usable_x * 3.0))
    row = min(1, int(usable_y * 2.0))
    slot_index = row * 3 + col + 1
    return f"{face_name}{slot_index}"


class InventoryMission:
    def __init__(self):
        rospy.init_node("generated_inventory_mission")
        rospy.set_param("~point_0", [0.0, 0.0, max(1.0, CONFIG.get("takeoff_altitude", 1.2)), 0])
        self.uav_ctrl = ctrl_tools.CtrlTools()
        self.face_points = CONFIG["face_points"]
        self.scan_seconds = float(CONFIG["scan_seconds"])
        self.arrive_precision = float(CONFIG["arrive_precision"])
        self.pause_after_detect = float(CONFIG["pause_after_detect"])
        self.slot_margin_ratio = float(CONFIG["slot_margin_ratio"])
        self.laser_on_detect = bool(CONFIG["laser_on_detect"])
        self.laser_seconds = float(CONFIG["laser_seconds"])
        self.wait_rc = bool(CONFIG["wait_rc"])
        self.return_home = bool(CONFIG["return_home"])
        self.auto_land = bool(CONFIG["auto_land"])
        self.target_qr_text = str(CONFIG.get("target_qr_text", "")).strip()
        self.stop_after_found = bool(CONFIG["stop_after_found"])
        self.output_dir = Path(CONFIG["result_dir"]) / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir = self.output_dir / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.records = []
        self.detected_keys = set()
        self.target_record = None

    def save_records(self):
        json_path = self.output_dir / "inventory_records.json"
        csv_path = self.output_dir / "inventory_records.csv"
        json_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=[
                    "face",
                    "slot",
                    "qr_text",
                    "detect_time",
                    "uav_map_x",
                    "uav_map_y",
                    "uav_map_z",
                    "yaw_deg",
                    "image_file",
                    "annotated_file",
                ],
            )
            writer.writeheader()
            writer.writerows(self.records)

    def flash_laser(self):
        if not self.laser_on_detect:
            return
        try:
            self.uav_ctrl.ctrl_laser(True)
            rospy.sleep(self.laser_seconds)
        finally:
            self.uav_ctrl.ctrl_laser(False)

    def goto_face(self, face_cfg):
        target_x = float(face_cfg["x"])
        target_y = float(face_cfg["y"])
        target_z = float(face_cfg["z"])
        self.uav_ctrl.set_point(target_x, target_y, target_z)
        while not rospy.is_shutdown():
            if self.uav_ctrl.get_state(target_x, target_y, target_z, self.arrive_precision):
                break
            rospy.sleep(0.2)
        yaw_deg = face_cfg.get("yaw_deg")
        if yaw_deg is not None:
            self.uav_ctrl.set_yaw(math.radians(float(yaw_deg)))
            rospy.sleep(0.5)

    def scan_face(self, face_cfg):
        face_name = str(face_cfg["face"]).strip().upper()
        start_time = time.time()
        while not rospy.is_shutdown() and time.time() - start_time <= self.scan_seconds:
            frame = self.uav_ctrl.get_img()
            entries, annotated = decode_qrs(frame)
            for entry in entries:
                slot_name = face_slot_name(face_name, entry["center_px"], frame.shape, self.slot_margin_ratio)
                key = (slot_name, entry["text"])
                if key in self.detected_keys:
                    continue

                self.detected_keys.add(key)
                self.flash_laser()
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                raw_name = f"{stamp}_{slot_name}_raw.png"
                ann_name = f"{stamp}_{slot_name}_ann.png"
                cv2.imwrite(str(self.image_dir / raw_name), frame)
                cv2.imwrite(str(self.image_dir / ann_name), annotated)

                map_x, map_y, map_z = self.uav_ctrl.get_local()
                record = {
                    "face": face_name,
                    "slot": slot_name,
                    "qr_text": entry["text"],
                    "detect_time": stamp,
                    "uav_map_x": round(map_x, 3),
                    "uav_map_y": round(map_y, 3),
                    "uav_map_z": round(map_z, 3),
                    "yaw_deg": round(math.degrees(self.uav_ctrl.current_yaw), 2),
                    "image_file": raw_name,
                    "annotated_file": ann_name,
                }
                self.records.append(record)
                self.save_records()
                rospy.logwarn("inventory detected: %s -> %s", record["slot"], record["qr_text"])

                if self.target_qr_text and entry["text"] == self.target_qr_text:
                    self.target_record = record
                    if self.stop_after_found:
                        return True

                rospy.sleep(self.pause_after_detect)
            rospy.sleep(0.2)
        return False

    def return_and_land(self):
        if self.return_home:
            home_world_x, home_world_y = map_to_world(self.uav_ctrl, self.uav_ctrl.home_pose_x, self.uav_ctrl.home_pose_y)
            current_z = self.uav_ctrl.get_local()[2]
            self.uav_ctrl.set_point(home_world_x, home_world_y, max(current_z, float(CONFIG["takeoff_altitude"])))
            for _ in range(80):
                if self.uav_ctrl.get_state(home_world_x, home_world_y, max(current_z, float(CONFIG["takeoff_altitude"])), self.arrive_precision):
                    break
                rospy.sleep(0.2)
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
        for face_cfg in self.face_points:
            self.goto_face(face_cfg)
            if self.scan_face(face_cfg):
                break

        self.return_and_land()


if __name__ == "__main__":
    InventoryMission().run()
