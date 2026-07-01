# mission_grid_app 模块文档

MissionGrid 地面站的核心应用包，包含所有 UI 组件、业务逻辑和数据模型。

## 模块层级架构

```
┌─────────────────────────────────────────────────────────┐
│                    应用启动层                             │
│  main.py (QApplication 初始化)                           │
│  app.py (顶层入口脚本)                                   │
├─────────────────────────────────────────────────────────┤
│                    主窗口层                               │
│  main_window.py (MainWindow - 集成所有模块)              │
├──────────────────────┬──────────────────────────────────┤
│     UI 组件层         │        业务逻辑层                 │
│  grid_widget.py      │  path_planner.py (路径规划)      │
│  action_editor.py    │  code_generator.py (代码生成)    │
│  main_task_editor.py │  telemetry.py (MAVLink 遥测)     │
│  video_stream.py     │  remote_service.py (远程管理)    │
│  point_cloud.py      │  logger.py (日志模块)            │
│  dashboard.py        │                                  │
├──────────────────────┴──────────────────────────────────┤
│                    基础设施层                             │
│  material_theme.py (Material You 3 主题)                │
│  material_widgets.py (自定义 Qt 组件)                    │
│  models.py (数据模型)                                    │
└─────────────────────────────────────────────────────────┘
```

## 文件详细说明

### models.py — 数据模型

**职责**: 定义应用的核心数据结构，是所有模块的共享数据层。

**主要类型**:
- `GridConfig`: 全局网格配置（尺寸、起飞点、动作、禁飞区、主线任务）
- `CellAction`: 单个格子的动作配置（类型、参数、触发条件）
- `TRIGGER_CONDITIONS`: 触发条件定义列表
- `MAIN_TASK_GLOBAL_CONDITIONS`: 主线任务全局完成条件列表

**被引用**: 所有其他模块

---

### material_theme.py — Material You 3 主题

**职责**: 提供 Material Design 3 配色系统和全局 QSS 样式表。

**主要导出**:
- `MD3Colors`: 色彩数据类（39 个语义化颜色变量）
- `COLORS`: 全局默认色彩实例（紫色主题 #6750A4）
- `global_stylesheet()`: 完整 QSS 样式表生成函数

**被引用**: 所有 UI 模块

---

### material_widgets.py — 自定义 Material 组件

**职责**: 基于 PySide6 实现 Material Design 3 风格的可复用组件。

**组件列表**:
| 组件 | 说明 |
|------|------|
| `add_shadow()` | 为任意 QWidget 添加阴影效果 |
| `MRippleButton` | 带涟漪动画的按钮 |
| `MCard` | 圆角卡片容器（带阴影） |
| `MChip` | 状态标签芯片（支持 success/warning/error） |
| `MFloatingActionButton` | 浮动操作按钮 (FAB) |
| `MDialogHeader` | 对话框标题头部 |
| `AnimatedStackedWidget` | 滑动动画堆叠页面切换器 |

**被引用**: main_window, action_editor, main_task_editor

---

### grid_widget.py — 网格可视化组件

**职责**: 基于 QGraphicsView 的 7×9 网格编辑器，支持动作编辑、禁飞区标记、路径渲染、无人机位置显示。

**主要类**:
- `CellItem`: 单个格子图形项（悬停高亮、Tooltip）
- `GridWidget`: 网格视图主组件

**信号**:
- `cell_action_changed(col, row)`: 左键点击格子
- `cell_nofly_changed(col, row)`: 右键切换禁飞区
- `waypoint_added(col, row)`: 手动模式添加航点

**渲染层级**: 格子(0) → 标签(2) → 航迹(4) → 路径(5) → 无人机(9-11)

**被引用**: main_window

---

### action_editor.py — 动作编辑器

**职责**: 格子动作编辑对话框，配置动作类型、触发条件和参数。

**主要类**:
- `ActionEditorDialog`: 动作编辑弹窗

**支持的 10 种动作类型**:
`takeoff`, `photo`, `qr_scan`, `yolo_detect`, `h_land`, `land`, `set_yaw`, `buzzer`, `servo`, `laser`

**被引用**: main_window, main_task_editor (仅 ACTION_TYPE_MAP)

---

### main_task_editor.py — 主线任务编辑器

**职责**: 配置主线任务的格子选择和全局完成条件。

**主要类**:
- `MainTaskEditorDialog`: 主线任务编辑弹窗

**被引用**: main_window

---

### path_planner.py — 路径规划器

**职责**: 在网格地图上自动规划最优飞行路径。

**算法**:
| 算法 | 用途 |
|------|------|
| A* | 网格最短路径搜索（8 方向，octile 启发） |
| ARA* | 渐进优化的 A*（Anytime Repairing A*） |
| 贪心最近邻 | TSP 初始解构造 |
| 最近/最远插入 | TSP 初始解构造 |
| 2-opt | TSP 局部搜索优化 |
| or-opt | TSP 局部搜索优化 |
| python-tsp DP | ≤12 节点精确 TSP 求解 |
| python-tsp SA+LS | >12 节点启发式 TSP 求解 |
| 蛇形遍历 | 遍历所有格子的最优方案 |

**公共接口**:
- `plan_path(config)`: 规划遍历有动作格子的路径
- `plan_path_all(config)`: 规划遍历所有格子的路径

**被引用**: main_window, code_generator

---

### code_generator.py — 任务代码生成器

**职责**: 将网格配置导出为可部署到机载电脑的 Python 任务脚本。

**生成内容**:
- `generated_mission.py`: Python 任务脚本（含触发条件逻辑）
- `run_mission.sh`: Shell 启动脚本（source ROS + 启动驱动）
- `mission_config.json`: 航点和动作配置

**公共接口**:
- `export_mission(config, output_dir)`: 导出完整任务包

**被引用**: main_window

---

### telemetry.py — MAVLink 遥测

**职责**: 通过 MAVLink UDP 协议接收无人机遥测数据的后台线程。

**接收消息**:
- `LOCAL_POSITION_NED`: 本地位置 (x, y, z)
- `HEARTBEAT`: 解锁状态和飞行模式
- `CM_STATUS`: 节点状态位掩码

**信号**:
- `position_updated(x, y, z)`: 位置更新
- `status_updated(dict)`: 状态更新
- `node_status_updated(int)`: 节点状态位掩码

**被引用**: main_window

---

### video_stream.py — 摄像头视频流

**职责**: 从 web_video_server 获取 HTTP MJPEG 视频流并显示。

**主要类**:
- `VideoStreamThread`: 视频流获取线程
- `CameraWidget`: 摄像头显示组件

**特性**:
- 自动获取最新帧，避免延迟堆积
- 连接/断开操作
- 帧率显示
- 默认话题：/image

**被引用**: main_window

---

### point_cloud.py — 3D 点云可视化

**职责**: 从 rosbridge_server 获取点云数据并使用 OpenGL 渲染。

**主要类**:
- `PointCloudThread`: 点云数据获取线程
- `PointCloudGLWidget`: OpenGL 渲染组件
- `PointCloudWidget`: 点云显示组件

**特性**:
- 双模式相机：轨道模式 + 第一人称漫游模式
- VBO 加速渲染 + 显示列表缓存
- 支持 Livox CustomMsg 和 PointCloud2 两种消息格式
- 自动下采样大点云
- 话题选择器和调试日志面板

**操控**:
- 轨道模式：左键旋转、右键平移、滚轮缩放
- 第一人称模式（按 F）：WASD 移动、鼠标转向、Space/Shift 升降

**被引用**: main_window

---

### remote_service.py — 远程服务管理

**职责**: 通过 SSH 连接 OrangePi，远程启动/停止 ROS 服务。

**主要类**:
- `SSHWorker`: SSH 连接和命令执行线程
- `RemoteServiceWidget`: 远程管理界面

**支持的服务**:
- MAVROS（飞控通信）
- Livox 激光雷达
- SLAM（FAST_LIO）
- 摄像头
- web_video_server（HTTP 视频流）
- rosbridge（WebSocket 点云流）

**特性**:
- 自动获取本机 IP 地址
- 串行启动服务，避免 SSH 通道泄漏
- 实时命令输出日志

**被引用**: main_window

---

### dashboard.py — 仪表盘监控

**职责**: 系统实时监控仪表盘。

**显示内容**:
- 系统信息（主机名、运行时间、操作系统）
- 性能监控（CPU/内存/磁盘使用率进度条）
- 连接状态（SSH/遥测/摄像头/点云）
- 性能指标（摄像头 FPS、点云 FPS、点云点数、遥测位置）
- 最近日志

**特性**:
- 每秒自动更新
- 需要 psutil 库（可选）

**被引用**: main_window

---

### logger.py — 日志模块

**职责**: 将应用运行日志保存到 log/ 目录。

**主要函数**:
- `setup_logging(app_dir)`: 配置日志系统
- `get_logger(name)`: 获取日志记录器

**日志文件**:
- 位置：`mission_grid/log/mission_grid_YYYYMMDD_HHMMSS.log`
- 格式：`YYYY-MM-DD HH:MM:SS [LEVEL] module: message`

**被引用**: main.py

---

### main_window.py — 主窗口

**职责**: 应用的顶层 UI 容器，集成所有子模块并协调交互。

**持有**: GridConfig (全局数据模型), GridWidget, TelemetryWorker, CameraWidget, PointCloudWidget, RemoteServiceWidget, DashboardWidget

**标签页**:
1. 仪表盘（系统监控）
2. ROS 节点（节点状态）
3. 数据监控（飞行状态）
4. 摄像头（视频流）
5. 3D 点云（点云渲染）
6. 远程管理（SSH 服务管理）

**功能模块**:
1. 网格编辑（左键动作、右键禁飞）
2. 路径规划（自动/手动）
3. 模拟飞行
4. 任务导出
5. 方案保存/加载
6. 遥测监控
7. 摄像头监控
8. 点云可视化
9. 远程服务管理
10. 系统监控

**被引用**: main.py

---

### main.py — 应用启动

**职责**: QApplication 初始化、主题设置、主窗口创建、日志系统初始化。

**被引用**: app.py

## 数据流

```
用户操作 → main_window.py
            ├── 格子点击 → ActionEditorDialog → GridConfig.set_action()
            ├── 禁飞切换 → GridConfig.toggle_no_fly()
            ├── 路径规划 → path_planner.plan_path() → GridWidget.draw_path()
            ├── 模拟飞行 → QTimer → GridWidget.set_drone_position()
            ├── 任务导出 → code_generator.export_mission() → 文件系统
            ├── 方案保存 → GridConfig → JSON 文件
            ├── 遥测接收 → TelemetryWorker → _on_position/_on_status
            │                    ↓
            │              GridWidget.update_drone_telemetry()
            ├── 摄像头连接 → VideoStreamThread → CameraWidget.update_frame()
            ├── 点云连接 → PointCloudThread → PointCloudGLWidget.set_points()
            ├── 远程管理 → SSHWorker → RemoteServiceWidget
            └── 系统监控 → DashboardWidget._update_stats()
```

## 外部依赖

| 库 | 用途 | 必需 |
|----|------|------|
| PySide6 | Qt UI 框架 | 是 |
| pymavlink | MAVLink 通信 | 是 |
| numpy | 距离矩阵计算 | 是 |
| python-tsp | TSP 精确/启发式求解 | 否（有回退方案） |
| opencv-python | 摄像头视频流 | 是 |
| PyOpenGL | 3D 点云渲染 | 是 |
| websocket-client | 点云 WebSocket 连接 | 是 |
| psutil | 系统性能监控 | 否（仪表盘降级显示 N/A） |
