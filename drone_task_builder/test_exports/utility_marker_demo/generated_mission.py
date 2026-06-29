#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
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
import uav_img_tools as img_tools


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


def map_to_world(uav_ctrl, map_x, map_y):
    yaw0 = uav_ctrl.init_yaw
    world_x = map_x * math.cos(yaw0) - map_y * math.sin(yaw0)
    world_y = map_x * math.sin(yaw0) + map_y * math.cos(yaw0)
    return world_x, world_y


def vertical_half_span(height_m):
    effective_height = max(0.05, height_m + float(CONFIG.get("height_bias", 0.0)))
    return float(CONFIG.get("reference_half_vertical", 0.3)) * (
        effective_height / float(CONFIG.get("reference_altitude", 0.5))
    )


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

    body_x = -pixel_dy * meter_per_pixel_y + float(CONFIG.get("camera_forward_offset", 0.0))
    body_y = -pixel_dx * meter_per_pixel_x + float(CONFIG.get("camera_left_offset", 0.0))

    yaw_rad = uav_ctrl.current_yaw
    local_dx = body_x * math.cos(yaw_rad) - body_y * math.sin(yaw_rad)
    local_dy = body_x * math.sin(yaw_rad) + body_y * math.cos(yaw_rad)
    world_x, world_y = map_to_world(uav_ctrl, map_x + local_dx, map_y + local_dy)
    return world_x, world_y


def save_frame(frame, save_dir, prefix):
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = Path(save_dir) / f"{prefix}_{stamp}.png"
    cv2.imwrite(str(path), frame)
    return str(path)


def detect_letter_marker(frame, marker_label):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if binary.mean() > 127:
        binary = cv2.bitwise_not(binary)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 800:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 20 or h < 20:
            continue
        center_x = x + w / 2.0
        center_y = y + h / 2.0
        if best is None or area > best["area"]:
            best = {
                "label": marker_label,
                "center_px": (center_x, center_y),
                "bbox": (x, y, w, h),
                "area": area,
            }
    if best is None:
        return None
    annotated = frame.copy()
    x, y, w, h = best["bbox"]
    cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 220, 0), 2)
    cv2.putText(annotated, marker_label, (x, max(22, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 220, 0), 2)
    best["annotated"] = annotated
    return best


def detect_circle_marker(uav_img, frame, marker_label):
    result = uav_img.detect_circle(frame.copy())
    if result[0] is None:
        return None
    center_x, center_y, radius = result
    annotated = frame.copy()
    cv2.circle(annotated, (int(center_x), int(center_y)), int(radius), (0, 255, 255), 2)
    cv2.putText(annotated, marker_label, (int(center_x) - 20, int(center_y) - int(radius) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    return {
        "label": marker_label,
        "center_px": (float(center_x), float(center_y)),
        "annotated": annotated,
        "area": float(radius * radius * 3.14159),
    }


def detect_qr_marker(frame, marker_qr_text):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    decoded = pyzbar.decode(gray)
    for barcode in decoded:
        text = barcode.data.decode("utf-8") if barcode.data else ""
        if marker_qr_text and text != marker_qr_text:
            continue
        polygon = [(point.x, point.y) for point in barcode.polygon] if barcode.polygon else []
        if polygon:
            center_x = sum(point[0] for point in polygon) / float(len(polygon))
            center_y = sum(point[1] for point in polygon) / float(len(polygon))
            annotated = frame.copy()
            for idx in range(len(polygon)):
                p1 = polygon[idx]
                p2 = polygon[(idx + 1) % len(polygon)]
                cv2.line(annotated, p1, p2, (0, 255, 0), 2)
        else:
            rect = barcode.rect
            center_x = rect.left + rect.width / 2.0
            center_y = rect.top + rect.height / 2.0
            annotated = frame.copy()
            cv2.rectangle(annotated, (rect.left, rect.top), (rect.left + rect.width, rect.top + rect.height), (0, 255, 0), 2)
        cv2.putText(annotated, text or "QR", (int(center_x) + 6, int(center_y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return {
            "label": text or "QR",
            "center_px": (float(center_x), float(center_y)),
            "annotated": annotated,
            "area": 1.0,
        }
    return None


class UtilityMission:
    def __init__(self):
        rospy.init_node("generated_utility_mission")
        rospy.set_param("~point_0", [0.0, 0.0, max(1.0, CONFIG.get("takeoff_altitude", 1.2)), 0])
        self.uav_ctrl = ctrl_tools.CtrlTools()
        self.uav_img = img_tools.ImgTools()
        self.wait_rc = bool(CONFIG.get("wait_rc", True))
        self.takeoff_needed = bool(CONFIG.get("takeoff_needed", False))
        self.auto_land = bool(CONFIG.get("auto_land", False))
        self.return_home = bool(CONFIG.get("return_home", False))
        self.arrive_precision = float(CONFIG.get("arrive_precision", 0.2))
        self.target_result = None

    def goto_point(self, world_x, world_y, world_z):
        self.uav_ctrl.set_point(world_x, world_y, world_z)
        while not rospy.is_shutdown():
            if self.uav_ctrl.get_state(world_x, world_y, world_z, self.arrive_precision):
                break
            rospy.sleep(0.2)

    def detect_marker(self):
        frame = self.uav_ctrl.get_img()
        marker_type = str(CONFIG.get("marker_type", "letter_h"))
        marker_label = str(CONFIG.get("marker_label", "H"))
        marker_qr_text = str(CONFIG.get("marker_qr_text", ""))

        if marker_type in {"letter_h", "letter_a", "letter_custom"}:
            result = detect_letter_marker(frame, marker_label)
        elif marker_type == "circle":
            result = detect_circle_marker(self.uav_img, frame, marker_label)
        elif marker_type == "qr_text":
            result = detect_qr_marker(frame, marker_qr_text)
        else:
            result = None

        if result is None:
            return None
        result["world_xy"] = estimate_ground_target(self.uav_ctrl, frame.shape, result["center_px"])
        result["saved_path"] = save_frame(result["annotated"], CONFIG.get("marker_save_dir", "/home/orangepi/Desktop/marker_results"), "marker")
        return result

    def execute(self):
        wait_pose_stable(
            self.uav_ctrl,
            int(CONFIG.get("check_count", 5)),
            float(CONFIG.get("position_error", 0.1)),
            float(CONFIG.get("yaw_error", 2.0)),
        )

        if self.wait_rc:
            if self.uav_ctrl.set_rc_to_start() is False:
                rospy.logerr("remote start failed")
                return

        if self.takeoff_needed:
            if self.uav_ctrl.uav_takeoff() is False:
                rospy.logerr("takeoff failed")
                return
            rospy.sleep(2.0)

        for action in CONFIG.get("actions", []):
            action_type = action["type"]
            if action_type == "goto_point":
                self.goto_point(float(action["x"]), float(action["y"]), float(action["z"]))
            elif action_type == "set_yaw":
                self.uav_ctrl.set_yaw(math.radians(float(action["yaw_deg"])), math.radians(float(action["step_deg"])))
            elif action_type == "capture_image":
                frame = self.uav_ctrl.get_img()
                save_frame(frame, action["save_dir"], action["prefix"])
            elif action_type == "laser":
                self.uav_ctrl.ctrl_laser(bool(action["laser_on"]))
                rospy.sleep(float(action["duration_sec"]))
                if bool(action["laser_on"]):
                    self.uav_ctrl.ctrl_laser(False)
            elif action_type == "buzzer":
                self.uav_ctrl.ctrl_buzzer(int(action["audio_id"]), str(action["audio_text"]))
            elif action_type == "servo":
                self.uav_ctrl.ctrl_servo(int(action["servo_id"]), bool(action["open_servo"]))
                rospy.sleep(float(action["hold_sec"]))
                if bool(action["open_servo"]):
                    self.uav_ctrl.ctrl_servo(int(action["servo_id"]), False)
            elif action_type == "detect_circle":
                frame = self.uav_ctrl.get_img()
                annotated = frame.copy()
                result = self.uav_img.detect_circle(annotated)
                save_frame(annotated, action["save_dir"], "circle")
            elif action_type == "detect_digit":
                frame = self.uav_ctrl.get_img()
                _ = self.uav_img.num_recognition(frame.copy())
                save_frame(frame, action["save_dir"], "digit")
            elif action_type == "detect_marker":
                self.target_result = self.detect_marker()
            elif action_type == "land_on_marker":
                if self.target_result is None:
                    self.target_result = self.detect_marker()
                if self.target_result is not None and bool(action["land_enabled"]):
                    world_x, world_y = self.target_result["world_xy"]
                    current_z = self.uav_ctrl.get_local()[2]
                    self.goto_point(world_x, world_y, current_z)
                    self.uav_ctrl.uav_land()
                    return

        if self.return_home:
            home_world_x, home_world_y = map_to_world(self.uav_ctrl, self.uav_ctrl.home_pose_x, self.uav_ctrl.home_pose_y)
            current_z = self.uav_ctrl.get_local()[2]
            self.goto_point(home_world_x, home_world_y, current_z)

        if self.auto_land:
            self.uav_ctrl.uav_land()


if __name__ == "__main__":
    UtilityMission().execute()
