from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from .mission_templates import (
    render_delivery_mission,
    render_generic_startup_shell,
    render_inventory_mission,
    render_utility_mission,
    render_wildlife_mission,
)
from .models import ExportResult, MissionPlan


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = _project_root()
QR_REFERENCE_DIR = PROJECT_ROOT / "TIdown"
POSITION_REFERENCE_DIR = PROJECT_ROOT / "TIdown"
COMPETITION_SCRIPT_DIR = PROJECT_ROOT / "TIdown" / "ctrl_ws" / "src" / "competition_pkg" / "scripts"

POSITION_TASK_ID = "monitor_position"
ENV_START_TASK_ID = "env_start"
WAIT_MAPPING_TASK_ID = "wait_mapping"
TAKEOFF_TASK_ID = "takeoff"
RETURN_HOME_TASK_ID = "return_home"
LAND_TASK_ID = "land"

UTILITY_TASK_IDS = {
    "goto_point",
    "set_yaw_task",
    "capture_current_image",
    "detect_circle_target",
    "detect_digit_target",
    "detect_visual_marker",
    "estimate_visual_marker_coord",
    "land_on_marker",
    "laser_control_task",
    "buzzer_control_task",
    "servo_control_task",
}

PATROL_TASK_ID = "patrol_area"
DETECT_QR_TASK_ID = "detect_qr"
CAPTURE_QR_TASK_ID = "capture_qr"
ESTIMATE_QR_TASK_ID = "estimate_qr_coord"

INVENTORY_ROUTE_TASK_ID = "inventory_route"
INVENTORY_SCAN_TASK_ID = "inventory_scan_qr"
INVENTORY_QUERY_TASK_ID = "inventory_target_query"
INVENTORY_LASER_TASK_ID = "inventory_laser_hint"

DELIVERY_COORD_TASK_ID = "delivery_coordinates"
DELIVERY_SEARCH_TASK_ID = "delivery_search_targets"
DELIVERY_RELEASE_TASK_ID = "delivery_release_cargo"

WILDLIFE_GRID_TASK_ID = "wildlife_grid_patrol"
WILDLIFE_DETECT_TASK_ID = "wildlife_detect_animals"


def validate_mission_plan(plan: MissionPlan) -> Tuple[List[str], List[str]]:
    task_ids = [task.task_id for task in plan.tasks]
    task_set = set(task_ids)
    errors: List[str] = []
    warnings: List[str] = []

    if not plan.tasks:
        errors.append("当前任务流为空，至少需要加入一个任务。")
        return errors, warnings

    if POSITION_TASK_ID in task_set:
        if len(task_ids) > 1:
            errors.append("“位置监控”当前只能单独导出。")
        return errors, warnings

    if _is_inventory_bundle(plan):
        _validate_inventory_bundle(task_set, errors, warnings)
        return errors, warnings

    if _is_delivery_bundle(plan):
        _validate_delivery_bundle(task_set, errors, warnings)
        return errors, warnings

    if _is_wildlife_bundle(plan):
        _validate_wildlife_bundle(task_set, errors, warnings)
        return errors, warnings

    if _is_qr_patrol_bundle(plan):
        _validate_qr_patrol_bundle(task_set, errors, warnings)
        return errors, warnings

    if _is_utility_bundle(plan):
        _validate_utility_bundle(task_set, errors, warnings)
        return errors, warnings

    errors.append("当前任务组合没有对应的导出器。")
    return errors, warnings


def export_mission_bundle(plan: MissionPlan, output_dir: str) -> ExportResult:
    errors, warnings = validate_mission_plan(plan)
    if errors:
        raise ValueError("\n".join(errors))

    out_root = Path(output_dir)
    bundle_dir = out_root / plan.mission_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    generated_files: List[str] = []
    mission_json = _write_plan_json(plan, bundle_dir)
    generated_files.append(str(mission_json))

    if _is_position_monitor_bundle(plan):
        generated_files.extend(_export_position_monitor_bundle(plan, bundle_dir))
        bundle_type = "position_monitor"
        entry_script = str(bundle_dir / "run_monitor.sh")
    elif _is_inventory_bundle(plan):
        generated_files.extend(_export_inventory_bundle(plan, bundle_dir))
        bundle_type = "inventory_mission"
        entry_script = str(bundle_dir / "run_inventory_mission.sh")
    elif _is_delivery_bundle(plan):
        generated_files.extend(_export_delivery_bundle(plan, bundle_dir))
        bundle_type = "delivery_mission"
        entry_script = str(bundle_dir / "run_delivery_mission.sh")
    elif _is_wildlife_bundle(plan):
        generated_files.extend(_export_wildlife_bundle(plan, bundle_dir))
        bundle_type = "wildlife_mission"
        entry_script = str(bundle_dir / "run_wildlife_mission.sh")
    elif _is_qr_patrol_bundle(plan):
        generated_files.extend(_export_qr_patrol_bundle(plan, bundle_dir))
        bundle_type = "patrol_mission"
        entry_script = str(bundle_dir / "run_generated_mission.sh")
    else:
        generated_files.extend(_export_utility_bundle(plan, bundle_dir))
        bundle_type = "utility_mission"
        entry_script = str(bundle_dir / "run_utility_mission.sh")

    manifest_path = _write_bundle_manifest(plan, bundle_dir, bundle_type, entry_script, warnings, generated_files)
    readme_path = _write_bundle_readme(plan, bundle_dir, bundle_type, entry_script, warnings)
    generated_files.extend([str(manifest_path), str(readme_path)])

    return ExportResult(
        bundle_type=bundle_type,
        bundle_dir=str(bundle_dir),
        entry_script=entry_script,
        generated_files=generated_files,
        warnings=warnings,
    )


def _is_position_monitor_bundle(plan: MissionPlan) -> bool:
    task_ids = [task.task_id for task in plan.tasks]
    return len(task_ids) == 1 and task_ids[0] == POSITION_TASK_ID


def _is_qr_patrol_bundle(plan: MissionPlan) -> bool:
    task_set = {task.task_id for task in plan.tasks}
    return bool(task_set & {PATROL_TASK_ID, DETECT_QR_TASK_ID, CAPTURE_QR_TASK_ID, ESTIMATE_QR_TASK_ID})


def _is_inventory_bundle(plan: MissionPlan) -> bool:
    task_set = {task.task_id for task in plan.tasks}
    return bool(task_set & {INVENTORY_ROUTE_TASK_ID, INVENTORY_SCAN_TASK_ID, INVENTORY_QUERY_TASK_ID, INVENTORY_LASER_TASK_ID})


def _is_delivery_bundle(plan: MissionPlan) -> bool:
    task_set = {task.task_id for task in plan.tasks}
    return bool(task_set & {DELIVERY_COORD_TASK_ID, DELIVERY_SEARCH_TASK_ID, DELIVERY_RELEASE_TASK_ID})


def _is_wildlife_bundle(plan: MissionPlan) -> bool:
    task_set = {task.task_id for task in plan.tasks}
    return bool(task_set & {WILDLIFE_GRID_TASK_ID, WILDLIFE_DETECT_TASK_ID})


def _is_utility_bundle(plan: MissionPlan) -> bool:
    task_set = {task.task_id for task in plan.tasks}
    return bool(task_set & UTILITY_TASK_IDS)


def _validate_qr_patrol_bundle(task_set: set, errors: List[str], warnings: List[str]) -> None:
    if PATROL_TASK_ID not in task_set:
        errors.append("二维码巡航任务必须包含“区域巡航”。")
    if DETECT_QR_TASK_ID not in task_set:
        errors.append("二维码巡航任务必须包含“识别二维码”。")
    if CAPTURE_QR_TASK_ID not in task_set:
        errors.append("二维码巡航任务必须包含“抓拍二维码”。")
    if WAIT_MAPPING_TASK_ID not in task_set:
        warnings.append("未显式加入“等待定位稳定”，将使用默认稳定性检查。")


def _validate_inventory_bundle(task_set: set, errors: List[str], warnings: List[str]) -> None:
    if INVENTORY_ROUTE_TASK_ID not in task_set:
        errors.append("货架盘点任务必须包含“货架观察路线”。")
    if INVENTORY_SCAN_TASK_ID not in task_set:
        errors.append("货架盘点任务必须包含“货架二维码盘点”。")
    if TAKEOFF_TASK_ID in task_set:
        warnings.append("货架盘点导出脚本内部会完成起飞，“起飞”任务主要用于表达方案。")


def _validate_delivery_bundle(task_set: set, errors: List[str], warnings: List[str]) -> None:
    if DELIVERY_RELEASE_TASK_ID not in task_set:
        errors.append("送货任务必须包含“送货释放货物”。")
    if DELIVERY_COORD_TASK_ID not in task_set and DELIVERY_SEARCH_TASK_ID not in task_set:
        errors.append("送货任务至少包含“按坐标送货”或“搜索颜色形状目标”之一。")
    if DELIVERY_COORD_TASK_ID in task_set and DELIVERY_SEARCH_TASK_ID in task_set:
        warnings.append("同时选择了坐标送货和目标搜索，导出时优先执行坐标送货模式。")


def _validate_wildlife_bundle(task_set: set, errors: List[str], warnings: List[str]) -> None:
    if WILDLIFE_GRID_TASK_ID not in task_set:
        errors.append("野生动物巡查任务必须包含“野生动物网格巡航”。")
    if WILDLIFE_DETECT_TASK_ID not in task_set:
        errors.append("野生动物巡查任务必须包含“野生动物识别统计”。")


def _validate_utility_bundle(task_set: set, errors: List[str], warnings: List[str]) -> None:
    if "estimate_visual_marker_coord" in task_set and "detect_visual_marker" not in task_set:
        errors.append("“计算目标标识坐标”依赖“识别视觉目标标识”。")
    if "land_on_marker" in task_set and "detect_visual_marker" not in task_set:
        errors.append("“降落到目标标识”依赖“识别视觉目标标识”。")
    if TAKEOFF_TASK_ID in task_set:
        warnings.append("通用工具任务包内部会根据动作需要决定是否起飞。")


def _write_plan_json(plan: MissionPlan, bundle_dir: Path) -> Path:
    payload = {
        "mission_name": plan.mission_name,
        "tasks": [{"task_id": task.task_id, "name": task.name, "params": task.params} for task in plan.tasks],
    }
    target = bundle_dir / f"{plan.mission_name}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _task_params(plan: MissionPlan) -> Dict[str, Dict]:
    return {task.task_id: dict(task.params) for task in plan.tasks}


def _bool_param(params: Dict, key: str, default: bool) -> bool:
    value = params.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_json_param(value, default):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        return json.loads(text)
    if value is None:
        return default
    return value


def _export_position_monitor_bundle(plan: MissionPlan, bundle_dir: Path) -> List[str]:
    params = plan.tasks[0].params
    generated: List[str] = []
    for source_name in ("position_monitor.py", "position_monitor.launch", "run_monitor.sh"):
        source = POSITION_REFERENCE_DIR / source_name
        target = bundle_dir / source_name
        shutil.copy2(source, target)
        generated.append(str(target))
    launch_path = bundle_dir / "position_monitor.launch"
    launch_content = launch_path.read_text(encoding="utf-8")
    launch_content = launch_content.replace('value="/mavros/local_position/odom"', f'value="{params.get("odom_topic", "/mavros/local_position/odom")}"')
    launch_content = launch_content.replace('value="5.0"', f'value="{params.get("rate_hz", 5.0)}"')
    launch_content = launch_content.replace('value="/uav_position/status"', f'value="{params.get("output_topic", "/uav_position/status")}"')
    launch_path.write_text(launch_content, encoding="utf-8")
    return generated


def _qr_patrol_support_files() -> List[str]:
    return [
        "node_manage_qr_patrol_slow.py",
        "node_manage_qr_patrol_with_coord.py",
        "node_manage_qr_patrol_with_coord_and_h.py",
        "qr_patrol_mission_slow.py",
        "qr_patrol_mission_with_coord.py",
        "qr_patrol_mission_with_coord_and_h.py",
        "qr_coordinate_utils.py",
        "h_landing_utils.py",
        "uav_ctrl_tools_slow.py",
    ]


def _build_qr_runtime_config(plan: MissionPlan) -> Dict:
    params = _task_params(plan)
    patrol = params.get(PATROL_TASK_ID, {})
    qr_capture = params.get(CAPTURE_QR_TASK_ID, {})
    coord_params = params.get(ESTIMATE_QR_TASK_ID, {})
    wait_mapping = params.get(WAIT_MAPPING_TASK_ID, {})
    return_home = params.get(RETURN_HOME_TASK_ID, {})
    return {
        "mission_name": plan.mission_name,
        "node_script": "node_manage_qr_patrol_with_coord.py" if ESTIMATE_QR_TASK_ID in params else "node_manage_qr_patrol_slow.py",
        "length": patrol.get("length", 4.0),
        "width": patrol.get("width", 3.0),
        "altitude": patrol.get("altitude", 1.2),
        "lane_spacing": patrol.get("lane_spacing", 1.0),
        "margin": patrol.get("margin", 0.4),
        "cruise_speed": patrol.get("cruise_speed", 0.35),
        "save_dir": qr_capture.get("save_dir", "/home/orangepi/Desktop/qr_captures"),
        "reference_altitude": coord_params.get("reference_altitude", 0.5),
        "reference_half_vertical": coord_params.get("reference_half_vertical", 0.3),
        "camera_forward_offset": coord_params.get("camera_forward_offset", 0.0),
        "camera_left_offset": coord_params.get("camera_left_offset", 0.0),
        "height_bias": coord_params.get("height_bias", 0.0),
        "check_count": wait_mapping.get("check_count", 5),
        "position_error": wait_mapping.get("position_error", 0.1),
        "yaw_error": wait_mapping.get("yaw_error", 2.0),
        "has_qr_coord": ESTIMATE_QR_TASK_ID in params,
        "has_h": False,
        "return_home": _bool_param(return_home, "return_home", True),
    }


def _export_qr_patrol_bundle(plan: MissionPlan, bundle_dir: Path) -> List[str]:
    generated: List[str] = []
    for name in _qr_patrol_support_files():
        source = QR_REFERENCE_DIR / name
        if source.exists():
            target = bundle_dir / name
            shutil.copy2(source, target)
            generated.append(str(target))
    runtime = _build_qr_runtime_config(plan)
    config_path = bundle_dir / "generated_runtime_config.json"
    config_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(str(config_path))
    main_script = bundle_dir / "generated_mission_entry.py"
    main_script.write_text(_render_qr_mission_entry(runtime), encoding="utf-8")
    generated.append(str(main_script))
    shell_script = bundle_dir / "run_generated_mission.sh"
    shell_script.write_text(_render_qr_startup_shell(runtime), encoding="utf-8")
    generated.append(str(shell_script))
    return generated


def _build_inventory_runtime_config(plan: MissionPlan) -> Dict:
    params = _task_params(plan)
    env = params.get(ENV_START_TASK_ID, {})
    wait_mapping = params.get(WAIT_MAPPING_TASK_ID, {})
    route = params.get(INVENTORY_ROUTE_TASK_ID, {})
    scan = params.get(INVENTORY_SCAN_TASK_ID, {})
    query = params.get(INVENTORY_QUERY_TASK_ID, {})
    laser = params.get(INVENTORY_LASER_TASK_ID, {})
    return_home = params.get(RETURN_HOME_TASK_ID, {})
    land = params.get(LAND_TASK_ID, {})
    return {
        "competition_pkg_script_dir": str(COMPETITION_SCRIPT_DIR).replace("\\", "/"),
        "use_fast_lio": _bool_param(env, "use_fast_lio", False),
        "use_camera": _bool_param(env, "use_camera", True),
        "use_mavros": _bool_param(env, "use_mavros", True),
        "wait_rc": True,
        "takeoff_altitude": route.get("takeoff_altitude", 1.5),
        "face_points": _parse_json_param(route.get("face_points_json"), []),
        "scan_seconds": route.get("scan_seconds", 3.0),
        "arrive_precision": route.get("arrive_precision", 0.2),
        "result_dir": scan.get("result_dir", "/home/orangepi/Desktop/inventory_results"),
        "pause_after_detect": scan.get("pause_after_detect", 0.5),
        "slot_margin_ratio": scan.get("slot_margin_ratio", 0.1),
        "target_qr_text": query.get("target_qr_text", ""),
        "stop_after_found": _bool_param(query, "stop_after_found", True),
        "laser_on_detect": _bool_param(laser, "laser_on_detect", False),
        "laser_seconds": laser.get("laser_seconds", 0.5),
        "return_home": _bool_param(return_home, "return_home", True),
        "auto_land": _bool_param(land, "auto_land", True),
        "check_count": wait_mapping.get("check_count", 5),
        "position_error": wait_mapping.get("position_error", 0.1),
        "yaw_error": wait_mapping.get("yaw_error", 2.0),
    }


def _export_inventory_bundle(plan: MissionPlan, bundle_dir: Path) -> List[str]:
    generated: List[str] = []
    for name in ("uav_ctrl_tools.py",):
        source = COMPETITION_SCRIPT_DIR / name
        target = bundle_dir / name
        shutil.copy2(source, target)
        generated.append(str(target))
    runtime = _build_inventory_runtime_config(plan)
    config_path = bundle_dir / "generated_runtime_config.json"
    config_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(str(config_path))
    mission_script = bundle_dir / "generated_mission.py"
    mission_script.write_text(render_inventory_mission(), encoding="utf-8")
    generated.append(str(mission_script))
    shell_script = bundle_dir / "run_inventory_mission.sh"
    shell_script.write_text(render_generic_startup_shell(runtime), encoding="utf-8")
    generated.append(str(shell_script))
    return generated


def _build_delivery_runtime_config(plan: MissionPlan) -> Dict:
    params = _task_params(plan)
    env = params.get(ENV_START_TASK_ID, {})
    wait_mapping = params.get(WAIT_MAPPING_TASK_ID, {})
    delivery = params.get(DELIVERY_COORD_TASK_ID, {})
    search = params.get(DELIVERY_SEARCH_TASK_ID, {})
    release = params.get(DELIVERY_RELEASE_TASK_ID, {})
    return_home = params.get(RETURN_HOME_TASK_ID, {})
    land = params.get(LAND_TASK_ID, {})
    has_coord = DELIVERY_COORD_TASK_ID in params
    return {
        "competition_pkg_script_dir": str(COMPETITION_SCRIPT_DIR).replace("\\", "/"),
        "use_fast_lio": _bool_param(env, "use_fast_lio", False),
        "use_camera": _bool_param(env, "use_camera", True),
        "use_mavros": _bool_param(env, "use_mavros", True),
        "wait_rc": True,
        "mode": "coordinates" if has_coord else "search",
        "targets": _parse_json_param(delivery.get("targets_json"), []),
        "target_features": _parse_json_param(search.get("target_features_json"), []),
        "search_origin_x": search.get("search_origin_x", 0.0),
        "search_origin_y": search.get("search_origin_y", 0.0),
        "search_length": search.get("search_length", 5.0),
        "search_width": search.get("search_width", 4.0),
        "lane_spacing": search.get("lane_spacing", 0.8),
        "cruise_altitude": delivery.get("cruise_altitude", 1.5),
        "drop_altitude": delivery.get("drop_altitude", 0.8),
        "hover_seconds": delivery.get("hover_seconds", 5.0),
        "servo_id": delivery.get("servo_id", 1),
        "servo_open_seconds": delivery.get("servo_open_seconds", 1.0),
        "arrive_precision": delivery.get("arrive_precision", 0.2),
        "result_dir": delivery.get("result_dir", "/home/orangepi/Desktop/delivery_results"),
        "reference_altitude": search.get("reference_altitude", 0.5),
        "reference_half_vertical": search.get("reference_half_vertical", 0.3),
        "camera_forward_offset": search.get("camera_forward_offset", 0.0),
        "camera_left_offset": search.get("camera_left_offset", 0.0),
        "height_bias": search.get("height_bias", 0.0),
        "laser_during_delivery": _bool_param(release, "laser_during_delivery", False),
        "return_home": _bool_param(return_home, "return_home", True),
        "auto_land": _bool_param(land, "auto_land", True),
        "check_count": wait_mapping.get("check_count", 5),
        "position_error": wait_mapping.get("position_error", 0.1),
        "yaw_error": wait_mapping.get("yaw_error", 2.0),
    }


def _export_delivery_bundle(plan: MissionPlan, bundle_dir: Path) -> List[str]:
    generated: List[str] = []
    for name in ("uav_ctrl_tools.py",):
        source = COMPETITION_SCRIPT_DIR / name
        target = bundle_dir / name
        shutil.copy2(source, target)
        generated.append(str(target))
    runtime = _build_delivery_runtime_config(plan)
    config_path = bundle_dir / "generated_runtime_config.json"
    config_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(str(config_path))
    mission_script = bundle_dir / "generated_mission.py"
    mission_script.write_text(render_delivery_mission(), encoding="utf-8")
    generated.append(str(mission_script))
    shell_script = bundle_dir / "run_delivery_mission.sh"
    shell_script.write_text(render_generic_startup_shell(runtime), encoding="utf-8")
    generated.append(str(shell_script))
    return generated


def _build_wildlife_runtime_config(plan: MissionPlan, bundle_dir: Path) -> Dict:
    params = _task_params(plan)
    env = params.get(ENV_START_TASK_ID, {})
    wait_mapping = params.get(WAIT_MAPPING_TASK_ID, {})
    grid = params.get(WILDLIFE_GRID_TASK_ID, {})
    detect = params.get(WILDLIFE_DETECT_TASK_ID, {})
    return_home = params.get(RETURN_HOME_TASK_ID, {})
    land = params.get(LAND_TASK_ID, {})
    return {
        "competition_pkg_script_dir": str(COMPETITION_SCRIPT_DIR).replace("\\", "/"),
        "use_fast_lio": _bool_param(env, "use_fast_lio", False),
        "use_camera": _bool_param(env, "use_camera", True),
        "use_mavros": _bool_param(env, "use_mavros", True),
        "wait_rc": True,
        "origin_x": grid.get("origin_x", 0.0),
        "origin_y": grid.get("origin_y", 0.0),
        "grid_cols": grid.get("grid_cols", 9),
        "grid_rows": grid.get("grid_rows", 7),
        "cell_size": grid.get("cell_size", 0.6),
        "patrol_altitude": grid.get("patrol_altitude", 1.2),
        "forbidden_cells": _parse_json_param(grid.get("forbidden_cells_json"), []),
        "hover_seconds": grid.get("hover_seconds", 1.2),
        "arrive_precision": grid.get("arrive_precision", 0.2),
        "result_dir": grid.get("result_dir", "/home/orangepi/Desktop/wildlife_results"),
        "model_path": str((bundle_dir / "animal82.onnx").as_posix()),
        "confidence": detect.get("confidence", 0.6),
        "return_home": _bool_param(return_home, "return_home", True),
        "auto_land": _bool_param(land, "auto_land", True),
        "check_count": wait_mapping.get("check_count", 5),
        "position_error": wait_mapping.get("position_error", 0.1),
        "yaw_error": wait_mapping.get("yaw_error", 2.0),
    }


def _export_wildlife_bundle(plan: MissionPlan, bundle_dir: Path) -> List[str]:
    generated: List[str] = []
    for name in ("uav_ctrl_tools.py", "animal82.onnx"):
        source = COMPETITION_SCRIPT_DIR / name
        target = bundle_dir / name
        shutil.copy2(source, target)
        generated.append(str(target))
    runtime = _build_wildlife_runtime_config(plan, bundle_dir)
    config_path = bundle_dir / "generated_runtime_config.json"
    config_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(str(config_path))
    mission_script = bundle_dir / "generated_mission.py"
    mission_script.write_text(render_wildlife_mission(), encoding="utf-8")
    generated.append(str(mission_script))
    shell_script = bundle_dir / "run_wildlife_mission.sh"
    shell_script.write_text(render_generic_startup_shell(runtime), encoding="utf-8")
    generated.append(str(shell_script))
    return generated


def _build_utility_runtime_config(plan: MissionPlan) -> Dict:
    params = _task_params(plan)
    env = params.get(ENV_START_TASK_ID, {})
    wait_mapping = params.get(WAIT_MAPPING_TASK_ID, {})
    return_home = params.get(RETURN_HOME_TASK_ID, {})
    land = params.get(LAND_TASK_ID, {})
    actions = []
    takeoff_needed = TAKEOFF_TASK_ID in params

    if "goto_point" in params:
        p = params["goto_point"]
        actions.append({"type": "goto_point", "x": p.get("x", 1.0), "y": p.get("y", 1.0), "z": p.get("z", 1.2)})
    if "set_yaw_task" in params:
        p = params["set_yaw_task"]
        actions.append({"type": "set_yaw", "yaw_deg": p.get("yaw_deg", 90.0), "step_deg": p.get("step_deg", 3.0)})
    if "capture_current_image" in params:
        p = params["capture_current_image"]
        actions.append({"type": "capture_image", "save_dir": p.get("save_dir", "/home/orangepi/Desktop/manual_captures"), "prefix": p.get("prefix", "capture")})
    if "laser_control_task" in params:
        p = params["laser_control_task"]
        actions.append({"type": "laser", "laser_on": _bool_param(p, "laser_on", True), "duration_sec": p.get("duration_sec", 0.5)})
    if "buzzer_control_task" in params:
        p = params["buzzer_control_task"]
        actions.append({"type": "buzzer", "audio_id": p.get("audio_id", 1), "audio_text": p.get("audio_text", "")})
    if "servo_control_task" in params:
        p = params["servo_control_task"]
        actions.append({"type": "servo", "servo_id": p.get("servo_id", 1), "open_servo": _bool_param(p, "open_servo", True), "hold_sec": p.get("hold_sec", 0.8)})
    if "detect_circle_target" in params:
        p = params["detect_circle_target"]
        actions.append({"type": "detect_circle", "save_dir": p.get("save_dir", "/home/orangepi/Desktop/circle_results")})
    if "detect_digit_target" in params:
        p = params["detect_digit_target"]
        actions.append({"type": "detect_digit", "save_dir": p.get("save_dir", "/home/orangepi/Desktop/digit_results")})
    if "detect_visual_marker" in params:
        actions.append({"type": "detect_marker"})
    if "land_on_marker" in params:
        p = params["land_on_marker"]
        actions.append({"type": "land_on_marker", "land_enabled": _bool_param(p, "land_enabled", True)})

    marker_params = params.get("detect_visual_marker", {})
    coord_params = params.get("estimate_visual_marker_coord", {})
    goto_params = params.get("goto_point", {})
    return {
        "competition_pkg_script_dir": str(COMPETITION_SCRIPT_DIR).replace("\\", "/"),
        "use_fast_lio": _bool_param(env, "use_fast_lio", False),
        "use_camera": _bool_param(env, "use_camera", True),
        "use_mavros": _bool_param(env, "use_mavros", True),
        "wait_rc": True,
        "takeoff_needed": takeoff_needed,
        "takeoff_altitude": params.get(TAKEOFF_TASK_ID, {}).get("altitude", goto_params.get("z", 1.2)),
        "return_home": _bool_param(return_home, "return_home", False),
        "auto_land": _bool_param(land, "auto_land", False),
        "arrive_precision": goto_params.get("arrive_precision", 0.2),
        "check_count": wait_mapping.get("check_count", 5),
        "position_error": wait_mapping.get("position_error", 0.1),
        "yaw_error": wait_mapping.get("yaw_error", 2.0),
        "reference_altitude": coord_params.get("reference_altitude", 0.5),
        "reference_half_vertical": coord_params.get("reference_half_vertical", 0.3),
        "camera_forward_offset": coord_params.get("camera_forward_offset", 0.0),
        "camera_left_offset": coord_params.get("camera_left_offset", 0.0),
        "height_bias": coord_params.get("height_bias", 0.0),
        "marker_type": marker_params.get("marker_type", "letter_h"),
        "marker_label": marker_params.get("marker_label", "H"),
        "marker_qr_text": marker_params.get("marker_qr_text", ""),
        "marker_save_dir": "/home/orangepi/Desktop/marker_results",
        "actions": actions,
    }


def _export_utility_bundle(plan: MissionPlan, bundle_dir: Path) -> List[str]:
    generated: List[str] = []
    for name in ("uav_ctrl_tools.py", "uav_img_tools.py", "model.pt"):
        source = COMPETITION_SCRIPT_DIR / name
        if source.exists():
            target = bundle_dir / name
            shutil.copy2(source, target)
            generated.append(str(target))
    runtime = _build_utility_runtime_config(plan)
    config_path = bundle_dir / "generated_runtime_config.json"
    config_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(str(config_path))
    mission_script = bundle_dir / "generated_mission.py"
    mission_script.write_text(render_utility_mission(), encoding="utf-8")
    generated.append(str(mission_script))
    shell_script = bundle_dir / "run_utility_mission.sh"
    shell_script.write_text(render_generic_startup_shell(runtime), encoding="utf-8")
    generated.append(str(shell_script))
    return generated


def _render_qr_mission_entry(runtime: Dict) -> str:
    args = [
        "--length", str(runtime["length"]),
        "--width", str(runtime["width"]),
        "--altitude", str(runtime["altitude"]),
        "--lane-spacing", str(runtime["lane_spacing"]),
        "--margin", str(runtime["margin"]),
        "--cruise-speed", str(runtime["cruise_speed"]),
        "--save-dir", runtime["save_dir"],
        "--check-count", str(runtime["check_count"]),
        "--position-error", str(runtime["position_error"]),
        "--yaw-error", str(runtime["yaw_error"]),
    ]
    if runtime["has_qr_coord"]:
        args.extend([
            "--reference-altitude", str(runtime["reference_altitude"]),
            "--reference-half-vertical", str(runtime["reference_half_vertical"]),
            "--camera-forward-offset", str(runtime["camera_forward_offset"]),
            "--camera-left-offset", str(runtime["camera_left_offset"]),
            "--height-bias", str(runtime["height_bias"]),
        ])
    if not runtime["return_home"]:
        args.append("--no-return-home")
    lines = ['"python3"', f'str(script_dir / "{runtime["node_script"]}")']
    lines.extend(repr(item) for item in args)
    literal_args = ",\n        ".join(lines)
    return f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path


def main():
    script_dir = Path(__file__).resolve().parent
    command = [
        {literal_args}
    ]
    result = subprocess.run(command, check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
"""


def _render_qr_startup_shell(runtime: Dict) -> str:
    extra_lines = []
    if runtime["has_qr_coord"]:
        extra_lines.extend(
            [
                f'    --reference-altitude "{runtime["reference_altitude"]}" \\',
                f'    --reference-half-vertical "{runtime["reference_half_vertical"]}" \\',
                f'    --camera-forward-offset "{runtime["camera_forward_offset"]}" \\',
                f'    --camera-left-offset "{runtime["camera_left_offset"]}" \\',
                f'    --height-bias "{runtime["height_bias"]}" \\',
            ]
        )
    if not runtime["return_home"]:
        extra_lines.append('    --no-return-home \\')
    extra_block = "\n".join(extra_lines)
    if extra_block:
        extra_block += "\n"
    return f"""#!/bin/bash

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

export LD_PRELOAD="${{LD_PRELOAD:-/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1}}"
export COMPETITION_PKG_SCRIPT_DIR="${{COMPETITION_PKG_SCRIPT_DIR:-/home/orangepi/ctrl_ws/src/competition_pkg/scripts}}"

roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 &
sleep 25

if [ -f /home/orangepi/livox_ws/devel/setup.bash ]; then
    roslaunch livox_ros_driver2 msg_MID360s.launch &
    sleep 8
fi

roslaunch cam_pkg cam_pub.launch &
sleep 5

python3 "$SCRIPT_DIR/{runtime["node_script"]}" \\
    --length "{runtime["length"]}" \\
    --width "{runtime["width"]}" \\
    --altitude "{runtime["altitude"]}" \\
    --lane-spacing "{runtime["lane_spacing"]}" \\
    --margin "{runtime["margin"]}" \\
    --cruise-speed "{runtime["cruise_speed"]}" \\
    --save-dir "{runtime["save_dir"]}" \\
    --check-count "{runtime["check_count"]}" \\
    --position-error "{runtime["position_error"]}" \\
    --yaw-error "{runtime["yaw_error"]}" \\
{extra_block}    "$@"
"""


def _write_bundle_manifest(plan: MissionPlan, bundle_dir: Path, bundle_type: str, entry_script: str, warnings: List[str], generated_files: List[str]) -> Path:
    manifest = {
        "mission_name": plan.mission_name,
        "bundle_type": bundle_type,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "entry_script": entry_script,
        "tasks": [{"task_id": task.task_id, "name": task.name, "params": task.params} for task in plan.tasks],
        "reference_sources": {
            "position_monitor_dir": str(POSITION_REFERENCE_DIR),
            "qr_patrol_dir": str(QR_REFERENCE_DIR),
            "competition_script_dir": str(COMPETITION_SCRIPT_DIR),
        },
        "generated_files": generated_files,
        "warnings": warnings,
    }
    target = bundle_dir / "bundle_manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _write_bundle_readme(plan: MissionPlan, bundle_dir: Path, bundle_type: str, entry_script: str, warnings: List[str]) -> Path:
    entry_name = Path(entry_script).name
    warning_lines = "\n".join(f"- {item}" for item in warnings) if warnings else "- 无额外提示。"
    task_lines = "\n".join(f"- {task.name} (`{task.task_id}`)" for task in plan.tasks)
    notes = {
        "position_monitor": "这个任务包用于持续输出无人机当前位置。",
        "patrol_mission": "这个任务包用于二维码巡航、抓拍和坐标估算。",
        "inventory_mission": "这个任务包用于货架二维码盘点、货位映射和结果导出。",
        "delivery_mission": "这个任务包用于坐标送货或颜色形状目标搜索后送货。",
        "wildlife_mission": "这个任务包用于网格巡航、动物识别和统计。",
        "utility_mission": "这个任务包用于通用小任务组合，比如单点飞行、转向、拍照、目标识别、激光和舵机动作。",
    }
    bundle_note = notes.get(bundle_type, "这是一个导出的无人机任务包。")
    content = f"""# {plan.mission_name}

{bundle_note}

## 当前任务流
{task_lines}

## 上机部署步骤

1. 把整个文件夹复制到机载电脑。
2. 在机载电脑中进入这个目录。
3. 给入口脚本增加执行权限：
   `chmod +x {entry_name}`
4. 运行入口脚本：
   `./{entry_name}`

## 当前入口文件

- `{entry_name}`

## 提示

{warning_lines}
"""
    target = bundle_dir / "README_上机部署.md"
    target.write_text(content, encoding="utf-8")
    return target
