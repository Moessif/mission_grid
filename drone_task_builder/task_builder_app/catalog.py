from .models import TaskTemplate


TASK_TEMPLATES = [
    TaskTemplate(
        task_id="monitor_position",
        name="位置监控",
        description="持续输出无人机当前坐标和航向。",
        category="基础",
        default_params={
            "odom_topic": "/mavros/local_position/odom",
            "rate_hz": 5.0,
            "output_topic": "/uav_position/status",
        },
    ),
    TaskTemplate(
        task_id="env_start",
        name="环境启动",
        description="控制是否启动 MAVROS、相机和激光雷达。",
        category="基础",
        default_params={
            "use_fast_lio": False,
            "use_camera": True,
            "use_mavros": True,
        },
    ),
    TaskTemplate(
        task_id="wait_mapping",
        name="等待定位稳定",
        description="等待位置和偏航稳定后再执行后续任务。",
        category="基础",
        default_params={
            "check_count": 5,
            "position_error": 0.1,
            "yaw_error": 2.0,
        },
    ),
    TaskTemplate(
        task_id="takeoff",
        name="起飞",
        description="起飞到指定高度。",
        category="飞行",
        default_params={"altitude": 1.2},
    ),
    TaskTemplate(
        task_id="goto_point",
        name="飞到单点",
        description="飞到指定单个坐标点，适合简单路线拼接。",
        category="飞行",
        default_params={
            "x": 1.0,
            "y": 1.0,
            "z": 1.2,
            "arrive_precision": 0.2,
        },
    ),
    TaskTemplate(
        task_id="set_yaw_task",
        name="调整航向",
        description="把无人机转到指定航向角。",
        category="飞行",
        default_params={
            "yaw_deg": 90.0,
            "step_deg": 3.0,
        },
    ),
    TaskTemplate(
        task_id="patrol_area",
        name="区域巡航",
        description="按蛇形方式覆盖矩形区域。",
        category="飞行",
        default_params={
            "length": 4.0,
            "width": 3.0,
            "altitude": 1.2,
            "lane_spacing": 1.0,
            "margin": 0.4,
            "cruise_speed": 0.35,
        },
    ),
    TaskTemplate(
        task_id="capture_current_image",
        name="拍摄当前图像",
        description="保存当前相机图像，用于人工检查或调试。",
        category="感知",
        default_params={
            "save_dir": "/home/orangepi/Desktop/manual_captures",
            "prefix": "capture",
        },
    ),
    TaskTemplate(
        task_id="detect_qr",
        name="识别二维码",
        description="持续识别图像中的二维码。",
        category="感知",
        default_params={"cooldown": 3.0},
    ),
    TaskTemplate(
        task_id="capture_qr",
        name="抓拍二维码",
        description="识别到二维码后保存原图、标注图和记录。",
        category="感知",
        default_params={"save_dir": "/home/orangepi/Desktop/qr_captures"},
    ),
    TaskTemplate(
        task_id="estimate_qr_coord",
        name="计算二维码坐标",
        description="根据高度和成像比例估算二维码坐标。",
        category="感知",
        default_params={
            "reference_altitude": 0.5,
            "reference_half_vertical": 0.3,
            "camera_forward_offset": 0.0,
            "camera_left_offset": 0.0,
            "height_bias": 0.0,
        },
    ),
    TaskTemplate(
        task_id="detect_circle_target",
        name="识别圆形目标",
        description="识别圆形标志并保存结果。",
        category="感知",
        default_params={
            "save_dir": "/home/orangepi/Desktop/circle_results",
            "cooldown": 2.0,
        },
    ),
    TaskTemplate(
        task_id="detect_digit_target",
        name="识别手写数字",
        description="识别画面中的手写数字或圆内数字。",
        category="感知",
        default_params={
            "save_dir": "/home/orangepi/Desktop/digit_results",
            "cooldown": 2.0,
        },
    ),
    TaskTemplate(
        task_id="detect_visual_marker",
        name="识别视觉目标标识",
        description="识别可配置目标，比如 H、A、圆形、指定二维码内容。",
        category="目标",
        default_params={
            "marker_type": "letter_h",
            "marker_label": "H",
            "marker_qr_text": "",
            "cooldown": 2.0,
        },
    ),
    TaskTemplate(
        task_id="estimate_visual_marker_coord",
        name="计算目标标识坐标",
        description="根据当前识别目标估算其坐标，可用于后续降落或飞抵。",
        category="目标",
        default_params={
            "reference_altitude": 0.5,
            "reference_half_vertical": 0.3,
            "camera_forward_offset": 0.0,
            "camera_left_offset": 0.0,
            "height_bias": 0.0,
        },
    ),
    TaskTemplate(
        task_id="land_on_marker",
        name="降落到目标标识",
        description="识别到目标后飞到其上方并降落，可配置成 H、A 或其他目标。",
        category="目标",
        default_params={
            "marker_label": "H",
            "land_enabled": True,
        },
    ),
    TaskTemplate(
        task_id="laser_control_task",
        name="激光开关",
        description="控制机载激光笔打开或关闭。",
        category="执行器",
        default_params={
            "laser_on": True,
            "duration_sec": 0.5,
        },
    ),
    TaskTemplate(
        task_id="buzzer_control_task",
        name="蜂鸣器提示",
        description="播放蜂鸣器提示音。",
        category="执行器",
        default_params={
            "audio_id": 1,
            "audio_text": "",
        },
    ),
    TaskTemplate(
        task_id="servo_control_task",
        name="舵机动作",
        description="控制舵机打开或关闭。",
        category="执行器",
        default_params={
            "servo_id": 1,
            "open_servo": True,
            "hold_sec": 0.8,
        },
    ),
    TaskTemplate(
        task_id="return_home",
        name="返航",
        description="任务结束后返回起飞点上方。",
        category="收尾",
        default_params={"return_home": True},
    ),
    TaskTemplate(
        task_id="land",
        name="直接降落",
        description="任务结束后在当前位置自动降落。",
        category="收尾",
        default_params={"auto_land": True},
    ),
    TaskTemplate(
        task_id="inventory_route",
        name="货架观察路线",
        description="按货架 A/B/C/D 面观察点依次飞行盘点。",
        category="货架盘点",
        default_params={
            "takeoff_altitude": 1.5,
            "face_points_json": '[{"face":"A","x":1.3,"y":1.2,"z":1.5,"yaw_deg":0},{"face":"B","x":1.7,"y":1.2,"z":1.5,"yaw_deg":180},{"face":"C","x":3.3,"y":1.2,"z":1.5,"yaw_deg":0},{"face":"D","x":3.7,"y":1.2,"z":1.5,"yaw_deg":180}]',
            "scan_seconds": 3.0,
            "arrive_precision": 0.2,
        },
    ),
    TaskTemplate(
        task_id="inventory_scan_qr",
        name="货架二维码盘点",
        description="扫描货架二维码并记录货位编号。",
        category="货架盘点",
        default_params={
            "result_dir": "/home/orangepi/Desktop/inventory_results",
            "pause_after_detect": 0.5,
            "slot_margin_ratio": 0.1,
        },
    ),
    TaskTemplate(
        task_id="inventory_target_query",
        name="指定货物定向盘点",
        description="输入目标二维码内容，识别到后可提前结束盘点。",
        category="货架盘点",
        default_params={
            "target_qr_text": "",
            "stop_after_found": True,
        },
    ),
    TaskTemplate(
        task_id="inventory_laser_hint",
        name="货架激光提示",
        description="识别到二维码时短时点亮激光。",
        category="货架盘点",
        default_params={
            "laser_on_detect": True,
            "laser_seconds": 0.5,
        },
    ),
    TaskTemplate(
        task_id="delivery_coordinates",
        name="按坐标送货",
        description="根据输入坐标依次送货并控制舵机释放。",
        category="送货",
        default_params={
            "targets_json": '[{"name":"target_1","x":2.0,"y":2.75},{"name":"target_2","x":3.2,"y":1.4}]',
            "cruise_altitude": 1.5,
            "drop_altitude": 0.8,
            "hover_seconds": 5.0,
            "servo_id": 1,
            "servo_open_seconds": 1.0,
            "arrive_precision": 0.2,
            "result_dir": "/home/orangepi/Desktop/delivery_results",
        },
    ),
    TaskTemplate(
        task_id="delivery_search_targets",
        name="搜索颜色形状目标",
        description="搜索指定颜色和形状目标并计算坐标。",
        category="送货",
        default_params={
            "target_features_json": '["red_triangle","blue_square"]',
            "search_origin_x": 0.0,
            "search_origin_y": 0.0,
            "search_length": 5.0,
            "search_width": 4.0,
            "lane_spacing": 0.8,
            "reference_altitude": 0.5,
            "reference_half_vertical": 0.3,
            "camera_forward_offset": 0.0,
            "camera_left_offset": 0.0,
            "height_bias": 0.0,
        },
    ),
    TaskTemplate(
        task_id="delivery_release_cargo",
        name="送货释放货物",
        description="在目标点上方下降、悬停并释放货物。",
        category="送货",
        default_params={
            "laser_during_delivery": False,
        },
    ),
    TaskTemplate(
        task_id="wildlife_grid_patrol",
        name="野生动物网格巡航",
        description="按网格自动巡航，并支持禁飞格过滤。",
        category="野生动物",
        default_params={
            "origin_x": 0.0,
            "origin_y": 0.0,
            "grid_cols": 9,
            "grid_rows": 7,
            "cell_size": 0.6,
            "patrol_altitude": 1.2,
            "forbidden_cells_json": '["B2","C5"]',
            "hover_seconds": 1.2,
            "arrive_precision": 0.2,
            "result_dir": "/home/orangepi/Desktop/wildlife_results",
        },
    ),
    TaskTemplate(
        task_id="wildlife_detect_animals",
        name="野生动物识别统计",
        description="调用动物识别模型完成分类、计数和记录。",
        category="野生动物",
        default_params={
            "model_path": "/home/orangepi/ctrl_ws/src/competition_pkg/scripts/animal82.onnx",
            "confidence": 0.6,
        },
    ),
]


def templates_by_category():
    groups = {}
    for template in TASK_TEMPLATES:
        groups.setdefault(template.category, []).append(template)
    return groups


def template_map():
    return {template.task_id: template for template in TASK_TEMPLATES}
