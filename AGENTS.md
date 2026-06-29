# AGENTS.md — 无人机项目指南

## 项目概述

可编程无人机，配备 Livox MID360 激光雷达、RealSense 下视摄像头、OrangePi CM5 机载电脑。
用于竞赛任务：二维码巡航、货架盘点、送货、野生动物巡查等。

## 关键约束

- **所有机载脚本路径必须以 `/home/orangepi/` 开头** — 这是 OrangePi 的 home 目录
- **不要修改驱动和原始接口** — `uav_ctrl_tools.py`、`uav_img_tools.py`、ROS launch 文件等是厂家提供的，只读使用
- 新功能应创建新脚本，复用现有接口，不要改动原始代码

## 目录结构

```
TIdown/                    # 机载电脑文件镜像（只读参考）
├── ctrl_ws/               # 竞赛控制工作空间
│   └── src/competition_pkg/scripts/
│       ├── uav_ctrl_tools.py   # 核心控制接口（只读）
│       ├── uav_img_tools.py    # 图像处理接口（只读）
│       ├── competition_main.py # 竞赛主程序模板
│       └── node_manage.py      # SLAM 启动管理
├── tools_ws/              # 工具工作空间
│   └── src/
│       ├── FAST_LIO/      # 激光雷达 SLAM
│       ├── realsense-ros/  # RealSense 驱动
│       ├── ego2/          # 路径规划器
│       └── manage_bridge_node/ # 状态桥接节点
├── livox_ws/              # Livox 激光雷达驱动
├── self_start*.sh         # 各种启动脚本模板
├── qr_patrol_mission_*.py # 二维码巡航任务脚本
└── node_manage_*.py       # 节点管理脚本

drone_task_builder/        # Windows 端地面站/航路编排 GUI（队友开发）
├── app.py                 # 入口：python app.py
├── task_builder_app/      # 应用代码
└── test_exports/          # 导出的任务包示例

mission_grid/              # Windows 端网格任务编排地面站（自主开发，见下方详细说明）
├── app.py                 # 入口：python app.py
├── requirements.txt       # PySide6, pymavlink, python-tsp, numpy
└── mission_grid_app/      # 应用代码
    ├── main.py            # QApplication 启动
    ├── main_window.py     # 主窗口（标签页布局）
    ├── models.py          # GridConfig, CellAction, TRIGGER_CONDITIONS
    ├── grid_widget.py     # 网格可视化（QGraphicsView）
    ├── action_editor.py   # 动作配置对话框
    ├── path_planner.py    # 路径规划（python-tsp + BFS + 蛇形遍历）
    ├── code_generator.py  # 生成任务脚本
    └── telemetry.py       # MAVLink UDP 遥测

infomation/                # 厂家参考文档（只读）
```

## 核心接口（只读，不要修改）

### uav_ctrl_tools.CtrlTools
- `set_point(x, y, z)` — 飞到目标坐标
- `get_local()` — 获取当前位置
- `set_yaw(deg)` — 设置航向角
- `get_img()` — 获取下视摄像头图像
- `uav_takeoff()` / `uav_land()` — 起飞/降落
- `ctrl_buzzer(id)` — 控制蜂鸣器
- `ctrl_servo(ch, state)` — 控制舵机
- `set_rc_to_start()` — 等待遥控器解锁

### uav_img_tools.ImgTools
- `num(frame)` — CNN 手写数字识别
- `qr_code(frame)` — 二维码检测
- `circle_detect(frame)` — 圆形目标检测

## 启动顺序（机载电脑）

```bash
# 1. Source ROS 和工作空间
source /opt/ros/noetic/setup.bash --extend
source /home/orangepi/tools_ws/devel/setup.bash --extend
source /home/orangepi/livox_ws/devel/setup.bash --extend
source /home/orangepi/ctrl_ws/devel/setup.bash --extend

# 2. 设置 LD_PRELOAD（PyTorch 需要）
export LD_PRELOAD=/home/orangepi/.local/lib/python3.8/site-packages/torch/lib/libgomp-d22c30c5.so.1

# 3. 启动各节点（按顺序，每个需要 sleep 等待）
roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550 & sleep 30
roslaunch livox_ros_driver2 msg_MID360s.launch & sleep 10
roslaunch cam_pkg cam_pub.launch & sleep 5
rosrun competition_pkg node_manage.py & sleep 10
```

## ROS Topic 关键路径

- 控制指令: `/mavros/setpoint_raw/local`
- 本地定位: `/mavros/local_position/odom`
- SLAM 定位: `/Odometry` (FAST_LIO)
- 遥控器: `/mavros/rc/in`
- 摄像头图像: `/camera/color/image_raw`
- 蜂鸣器: `/mavros/play_tune`

## 开发新任务脚本

1. 复制 `competition_main.py` 作为模板
2. 保持 `uav_ctrl` 和 `uav_img` 的初始化方式
3. 在 `task_N()` 函数中实现具体任务逻辑
4. 航点模式：通过 `set_point()` 飞行，`get_state()` 判断到达
5. 保存路径使用 `/home/orangepi/` 下的目录

## drone_task_builder（Windows 端）

任务编排 GUI，用于生成可部署的任务包。

```bash
# 运行
python app.py

# 生成的任务包在 test_exports/ 下
# 部署到机载电脑后：chmod +x run_*.sh && ./run_*.sh
```

## EKF 原点设置

代码中硬编码了初始坐标（用于 SLAM 定位）：
```python
ekf_origin_msg.position.latitude = 34.8069498
ekf_origin_msg.position.longitude = 113.5129698
ekf_origin_msg.position.altitude = 110.0
```
如果换场地，需要更新 `uav_ctrl_tools.py` 中的这些值。

## 模型文件

- YOLO 动物检测: `/home/orangepi/ctrl_ws/src/competition_pkg/scripts/animal82.onnx`
- CNN 手写数字: `/home/orangepi/ctrl_ws/src/competition_pkg/scripts/model.pt`

## 常见坑

- MAVROS 启动后需要 30 秒才能连接飞控
- FAST_LIO 启动后需要多次重启直到定位稳定（见 `node_manage.py` 的检查逻辑）
- PyTorch 需要 `LD_PRELOAD` 环境变量，否则会报 OpenMP 错误
- 所有 Python 脚本使用 Python 3.8（系统自带）
- ROS 版本是 Noetic（Ubuntu 20.04）

## MissionGrid 网格任务编排地面站（自主开发）

### 概述
基于 PySide6 的 Windows 端地面站，在 7×9 网格地图上编排无人机任务、自动规划路径、实时监控遥测。
不修改机载电脑代码，复用 `uav_ctrl_tools` 接口。

### 启动
```bash
cd mission_grid
pip install PySide6 pymavlink python-tsp numpy
python app.py
```

### 坐标系统
```
    A1  A2  A3  A4  A5  A6  A7  A8  A9
B7  ·   ·   ·   ·   ·   ·   ·   ·   ·     row=6
B6  ·   ·   ·   ·   ·   ·   ·   ·   ·     row=5
B5  ·   ·   ·   ·   ·   ·   ·   ·   ·     row=4
B4  ·   ·   ·   ·   ·   ·   ·   ·   ·     row=3
B3  ·   ·   ·   ·   ·   ·   ·   ·   ·     row=2
B2  ·   ·   ·   ·   ·   ·   ·   ·   ·     row=1
B1  ·   ·   ·   ·   ·   ·   ·   ·   ★     row=0
    col=0                           col=8
```
- 网格坐标: (col, row), col=0~8 (A1~A9), row=0~6 (B1~B7)
- X 轴: A9→A1 方向 → `X = (8 - col) * 0.5`
- Y 轴: B1→B7 方向 → `Y = row * 0.5`
- 机头方向: 始终朝 +Y (B1→B7)
- 起飞位置: 由格子上的"起飞"动作决定（默认 A9B1）

### 已实现功能
1. **网格编辑器** — 7×9 可视化网格，左键设置动作，右键标记禁飞区
2. **动作系统** — 10 种动作（起飞/拍照/二维码/YOLO/H降落/降落/航向/蜂鸣器/舵机/激光）
3. **触发条件** — 每个动作可设触发条件：每次经过/首次经过/最后经过/主线完成后
4. **主线任务** — 可标记哪些格子属于主线任务，"主线完成后"触发条件基于此
5. **路径规划** — python-tsp TSP 求解 + BFS 路径 + 斜飞支持（禁飞区边缘 0.5m 内禁止斜飞）
6. **模拟飞行** — 可视化模拟无人机沿路径飞行，经过有动作的格子弹窗显示
7. **任务导出** — 生成 Python 脚本 + Shell 启动脚本 + JSON 配置
8. **遥测** — MAVLink UDP 接收位置和状态，网格实时显示无人机位置（红点+坐标标签），连接状态指示灯
9. **标签页** — ROS 节点监控（状态着色）、数据监控、摄像头（预留）、3D 点云（预留）

### 文件说明
| 文件 | 作用 |
|------|------|
| `app.py` | 入口脚本：`python app.py` |
| `main.py` | QApplication 初始化、Fusion 样式、全局字体 |
| `models.py` | GridConfig, CellAction, TRIGGER_CONDITIONS 数据模型 |
| `grid_widget.py` | QGraphicsView 网格可视化，支持动作/禁飞/手动航线/主线任务四种编辑模式 |
| `action_editor.py` | 动作编辑弹窗，10 种动作类型，触发条件复选框 + 动作参数编辑 |
| `main_task_editor.py` | 主线任务编辑弹窗，格子选择 + 全局完成条件 |
| `path_planner.py` | 路径规划：A* + ARA* + python-tsp TSP 求解 + 蛇形遍历 |
| `code_generator.py` | 导出任务脚本，含触发条件判断和坐标旋转 |
| `telemetry.py` | MAVLink UDP 遥测线程（QThread），接收位置/状态/节点信息 |
| `material_theme.py` | Material You 3 颜色系统 (MD3Colors) + 全局 QSS 样式表 |
| `material_widgets.py` | Material 组件：MCard, MChip, MRippleButton, AnimatedStackedWidget |
| `main_window.py` | 主窗口集成所有模块，含遥测坐标转换和连接状态指示 |

每个目录下均有 README.md 详细文档，所有 Python 文件包含完整的中文模块注释和函数文档。

### 生成的任务包结构
```
mission_grid_YYYYMMDD_HHMMSS/
├── generated_mission.py    # 任务脚本（使用 uav_ctrl_tools 接口）
├── run_mission.sh          # Shell 启动脚本（source ROS + 启动驱动）
└── mission_config.json     # 航点和动作配置
```

### 未完成/待开发
- 摄像头实时预览标签页（需要机载 web_video_server）
- 3D 点云可视化标签页（需要机载 rosbridge_server）
- 更多动作类型扩展
