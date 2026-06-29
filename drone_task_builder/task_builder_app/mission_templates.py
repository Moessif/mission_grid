from __future__ import annotations

from textwrap import dedent
from typing import Dict


def render_generic_startup_shell(runtime: Dict) -> str:
    use_mavros = "1" if runtime.get("use_mavros", True) else "0"
    use_camera = "1" if runtime.get("use_camera", True) else "0"
    use_livox = "1" if runtime.get("use_fast_lio", False) else "0"

    return dedent(
        f"""\
        #!/bin/bash

        set -euo pipefail

        SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

        cleanup() {{
            local pid
            for pid in $(jobs -p); do
                kill "$pid" >/dev/null 2>&1 || true
            done
        }}

        trap cleanup EXIT

        source /opt/ros/noetic/setup.bash --extend
        [ -f /home/orangepi/tools_ws/devel/setup.bash ] && source /home/orangepi/tools_ws/devel/setup.bash --extend || true
        [ -f /home/orangepi/livox_ws/devel/setup.bash ] && source /home/orangepi/livox_ws/devel/setup.bash --extend || true
        [ -f /home/orangepi/ctrl_ws/devel/setup.bash ] && source /home/orangepi/ctrl_ws/devel/setup.bash --extend || true

        export COMPETITION_PKG_SCRIPT_DIR="${{COMPETITION_PKG_SCRIPT_DIR:-/home/orangepi/ctrl_ws/src/competition_pkg/scripts}}"
        export START_MAVROS="{use_mavros}"
        export START_CAMERA="{use_camera}"
        export START_LIVOX="{use_livox}"

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
        """
    )


def render_inventory_mission() -> str:
    return dedent(
        """\
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
        """
    )


def render_utility_mission() -> str:
    return dedent(
        """\
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
        """
    )


def render_delivery_mission() -> str:
    return dedent(
        """\
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
        """
    )


def render_wildlife_mission() -> str:
    return dedent(
        """\
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
        """
    )
