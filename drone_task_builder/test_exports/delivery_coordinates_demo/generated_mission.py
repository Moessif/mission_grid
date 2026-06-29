#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
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


def vertical_half_span(height_m):
    effective_height = max(0.05, height_m + float(CONFIG["height_bias"]))
    return float(CONFIG["reference_half_vertical"]) * (effective_height / float(CONFIG["reference_altitude"]))


def horizontal_half_span(height_m, frame_shape):
    img_h, img_w = frame_shape[:2]
    return vertical_half_span(height_m) * float(img_w) / float(img_h)


def estimate_ground_target(uav_ctrl, frame_shape, center_px):
    map_x, map_y, map_z = uav_ctrl.get_local()
    img_h, img_w = frame_shape[:2]
    meter_per_pixel_y = (2.0 * vertical_half_span(map_z)) / float(img_h)
    meter_per_pixel_x = (2.0 * horizontal_half_span(map_z, frame_shape)) / float(img_w)
    pixel_dx = center_px[0] - (img_w / 2.0)
    pixel_dy = center_px[1] - (img_h / 2.0)

    body_x = -pixel_dy * meter_per_pixel_y + float(CONFIG["camera_forward_offset"])
    body_y = -pixel_dx * meter_per_pixel_x + float(CONFIG["camera_left_offset"])

    yaw_rad = uav_ctrl.current_yaw
    local_dx = body_x * math.cos(yaw_rad) - body_y * math.sin(yaw_rad)
    local_dy = body_x * math.sin(yaw_rad) + body_y * math.cos(yaw_rad)
    world_x, world_y = map_to_world(uav_ctrl, map_x + local_dx, map_y + local_dy)
    return world_x, world_y


def build_axis_samples(axis_origin, axis_length, step):
    if axis_length <= step:
        return [axis_origin + axis_length / 2.0]
    values = []
    current = axis_origin + step / 2.0
    upper = axis_origin + axis_length - step / 2.0
    while current <= upper + 1e-6:
        values.append(round(current, 4))
        current += step
    if values[-1] < upper:
        values.append(round(upper, 4))
    return values


def build_search_waypoints():
    lane_spacing = float(CONFIG["lane_spacing"])
    cell_step = max(0.4, lane_spacing)
    x_list = build_axis_samples(float(CONFIG["search_origin_x"]), float(CONFIG["search_length"]), cell_step)
    y_list = build_axis_samples(float(CONFIG["search_origin_y"]), float(CONFIG["search_width"]), cell_step)
    waypoints = []
    for row_index, y_value in enumerate(y_list):
        row_x = x_list if row_index % 2 == 0 else list(reversed(x_list))
        for x_value in row_x:
            waypoints.append((x_value, y_value, float(CONFIG["cruise_altitude"])))
    return waypoints


def classify_shape(contour):
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 1e-6:
        return None
    approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
    vertices = len(approx)
    if vertices == 3:
        return "triangle"
    if vertices == 4:
        x, y, w, h = cv2.boundingRect(approx)
        ratio = w / float(max(h, 1))
        return "square" if 0.75 <= ratio <= 1.35 else "rectangle"
    area = cv2.contourArea(contour)
    circularity = 4.0 * math.pi * area / max(perimeter * perimeter, 1e-6)
    if circularity >= 0.7:
        return "circle"
    return None


def detect_feature_targets(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    masks = {
        "red": (
            cv2.inRange(hsv, np.array([0, 70, 70]), np.array([10, 255, 255])) |
            cv2.inRange(hsv, np.array([160, 70, 70]), np.array([180, 255, 255]))
        ),
        "blue": cv2.inRange(hsv, np.array([90, 80, 60]), np.array([130, 255, 255])),
    }

    results = []
    annotated = frame.copy()
    for color_name, mask in masks.items():
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 1800:
                continue
            shape = classify_shape(contour)
            if shape not in {"triangle", "square", "circle"}:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            center_px = (x + w / 2.0, y + h / 2.0)
            label = f"{color_name}_{shape}"
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                label,
                (x, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            results.append({"label": label, "center_px": center_px})
    return results, annotated


class DeliveryMission:
    def __init__(self):
        rospy.init_node("generated_delivery_mission")
        rospy.set_param("~point_0", [0.0, 0.0, max(1.0, CONFIG.get("cruise_altitude", 1.5)), 0])
        self.uav_ctrl = ctrl_tools.CtrlTools()
        self.mode = CONFIG["mode"]
        self.wait_rc = bool(CONFIG["wait_rc"])
        self.arrive_precision = float(CONFIG["arrive_precision"])
        self.cruise_altitude = float(CONFIG["cruise_altitude"])
        self.drop_altitude = float(CONFIG["drop_altitude"])
        self.hover_seconds = float(CONFIG["hover_seconds"])
        self.servo_id = int(CONFIG["servo_id"])
        self.servo_open_seconds = float(CONFIG["servo_open_seconds"])
        self.return_home = bool(CONFIG["return_home"])
        self.auto_land = bool(CONFIG["auto_land"])
        self.laser_during_delivery = bool(CONFIG["laser_during_delivery"])
        self.targets = list(CONFIG.get("targets", []))
        self.target_features = list(CONFIG.get("target_features", []))
        self.discovered_targets = {}
        self.output_dir = Path(CONFIG["result_dir"]) / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir = self.output_dir / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.records = []

    def save_records(self):
        json_path = self.output_dir / "delivery_records.json"
        csv_path = self.output_dir / "delivery_records.csv"
        json_path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=[
                    "stage",
                    "target_name",
                    "target_x",
                    "target_y",
                    "detect_time",
                    "image_file",
                    "annotated_file",
                ],
            )
            writer.writeheader()
            writer.writerows(self.records)

    def goto_point(self, world_x, world_y, world_z):
        self.uav_ctrl.set_point(world_x, world_y, world_z)
        while not rospy.is_shutdown():
            if self.uav_ctrl.get_state(world_x, world_y, world_z, self.arrive_precision):
                break
            rospy.sleep(0.2)

    def perform_release(self):
        if self.laser_during_delivery:
            self.uav_ctrl.ctrl_laser(True)
        self.uav_ctrl.ctrl_servo(self.servo_id, True)
        rospy.sleep(self.servo_open_seconds)
        self.uav_ctrl.ctrl_servo(self.servo_id, False)
        rospy.sleep(self.hover_seconds)
        if self.laser_during_delivery:
            self.uav_ctrl.ctrl_laser(False)

    def deliver_targets(self, targets):
        for target in targets:
            target_name = str(target.get("name", "target"))
            target_x = float(target["x"])
            target_y = float(target["y"])
            self.goto_point(target_x, target_y, self.cruise_altitude)
            self.goto_point(target_x, target_y, self.drop_altitude)
            self.perform_release()
            self.goto_point(target_x, target_y, self.cruise_altitude)
            self.records.append(
                {
                    "stage": "delivered",
                    "target_name": target_name,
                    "target_x": round(target_x, 3),
                    "target_y": round(target_y, 3),
                    "detect_time": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
                    "image_file": "",
                    "annotated_file": "",
                }
            )
            self.save_records()

    def search_targets(self):
        target_set = set(self.target_features)
        for world_x, world_y, world_z in build_search_waypoints():
            if target_set.issubset(set(self.discovered_targets)):
                break
            self.goto_point(world_x, world_y, world_z)
            frame = self.uav_ctrl.get_img()
            detections, annotated = detect_feature_targets(frame)
            for detection in detections:
                label = detection["label"]
                if label not in target_set or label in self.discovered_targets:
                    continue
                est_x, est_y = estimate_ground_target(self.uav_ctrl, frame.shape, detection["center_px"])
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                raw_name = f"{stamp}_{label}_raw.png"
                ann_name = f"{stamp}_{label}_ann.png"
                cv2.imwrite(str(self.image_dir / raw_name), frame)
                cv2.imwrite(str(self.image_dir / ann_name), annotated)
                self.discovered_targets[label] = {"name": label, "x": est_x, "y": est_y}
                self.records.append(
                    {
                        "stage": "detected",
                        "target_name": label,
                        "target_x": round(est_x, 3),
                        "target_y": round(est_y, 3),
                        "detect_time": stamp,
                        "image_file": raw_name,
                        "annotated_file": ann_name,
                    }
                )
                self.save_records()
            rospy.sleep(0.2)
        ordered = []
        for label in self.target_features:
            if label in self.discovered_targets:
                ordered.append(self.discovered_targets[label])
        return ordered

    def return_and_land(self):
        if self.return_home:
            home_world_x, home_world_y = map_to_world(self.uav_ctrl, self.uav_ctrl.home_pose_x, self.uav_ctrl.home_pose_y)
            self.goto_point(home_world_x, home_world_y, self.cruise_altitude)
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
        if self.mode == "coordinates":
            targets = self.targets
        else:
            targets = self.search_targets()
        if targets:
            self.deliver_targets(targets)
        else:
            rospy.logwarn("no delivery target found")
        self.return_and_land()


if __name__ == "__main__":
    DeliveryMission().run()
