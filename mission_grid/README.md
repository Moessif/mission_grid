# MissionGrid — 网格任务编排地面站

基于 PySide6 的 Windows 端地面站，在 7×9 网格地图上编排无人机任务、自动规划路径、实时监控遥测。

## 快速启动

```bash
cd mission_grid
pip install PySide6 pymavlink python-tsp numpy
python app.py
```

## 目录结构

```
mission_grid/
├── app.py                      # 入口脚本（python app.py）
├── requirements.txt            # Python 依赖列表
├── start.bat                   # Windows 双击启动脚本
├── README.md                   # 本文件
└── mission_grid_app/           # 应用主包
    ├── __init__.py             # 包初始化（空）
    ├── main.py                 # QApplication 启动入口
    ├── main_window.py          # 主窗口（集成所有模块）
    ├── models.py               # 数据模型（GridConfig, CellAction）
    ├── grid_widget.py          # 网格可视化组件（QGraphicsView）
    ├── action_editor.py        # 动作编辑弹窗
    ├── main_task_editor.py     # 主线任务编辑弹窗
    ├── path_planner.py         # 路径规划（A* + TSP + 蛇形遍历）
    ├── code_generator.py       # 任务脚本代码生成器
    ├── telemetry.py            # MAVLink UDP 遥测线程
    ├── material_theme.py       # Material You 3 颜色系统 + 全局 QSS
    ├── material_widgets.py     # Material 自定义组件（MCard, MChip 等）
    └── README.md               # 模块详细文档
```

## 文件关系图

```
app.py
 └── main.py (run)
      └── main_window.py (MainWindow)
           ├── models.py (GridConfig, CellAction)        ← 被所有模块引用
           ├── grid_widget.py (GridWidget)                ← 网格可视化
           │    ├── material_theme.py (COLORS)            ← 颜色常量
           │    └── models.py
           ├── action_editor.py (ActionEditorDialog)      ← 动作编辑弹窗
           │    ├── material_theme.py
           │    ├── material_widgets.py (MChip)
           │    └── models.py
           ├── main_task_editor.py (MainTaskEditorDialog) ← 主线任务编辑
           │    ├── material_theme.py
           │    ├── material_widgets.py (MChip)
           │    ├── action_editor.py (ACTION_TYPE_MAP)
           │    └── models.py
           ├── path_planner.py (plan_path, plan_path_all) ← 路径规划
           │    └── models.py
           ├── code_generator.py (export_mission)         ← 任务导出
           │    ├── path_planner.py (plan_path)
           │    └── models.py
           ├── telemetry.py (TelemetryWorker)             ← MAVLink 遥测
           ├── material_theme.py (global_stylesheet)      ← 全局样式
           └── material_widgets.py (MCard, MChip, ...)    ← 自定义组件
                └── material_theme.py
```

## 坐标系统

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

- **网格坐标**: (col, row), col=0~8 (A1~A9), row=0~6 (B1~B7)
- **X 轴**: A9→A1 方向 → `X = (8 - col) * 0.5`
- **Y 轴**: B1→B7 方向 → `Y = row * 0.5`
- **机头方向**: 始终朝 +Y (B1→B7)
- **起飞位置**: 由格子上的"起飞"动作决定（默认 A9B1）

## 功能概览

| 功能 | 说明 |
|------|------|
| 网格编辑器 | 7×9 可视化网格，左键设置动作，右键标记禁飞区 |
| 动作系统 | 10 种动作（起飞/拍照/二维码/YOLO/降落/航向/蜂鸣器/舵机/激光） |
| 触发条件 | 4 种条件（每次/首次/最后/主线完成后），多条件 AND 逻辑 |
| 主线任务 | 标记主线格子 + 全局完成条件 |
| 路径规划 | A* + TSP（DP≤12点，SA>12点）+ 蛇形遍历 |
| 斜飞支持 | 8 方向移动，禁飞区边缘安全检查 |
| 模拟飞行 | 可视化无人机沿路径飞行，动作弹窗提示 |
| 任务导出 | Python 脚本 + Shell 启动脚本 + JSON 配置 |
| 方案管理 | JSON 格式保存/加载完整方案 |
| 遥测监控 | MAVLink UDP 实时位置/状态/节点信息 |

## 生成的任务包

```
mission_grid_YYYYMMDD_HHMMSS/
├── generated_mission.py    # 任务脚本（使用 uav_ctrl_tools 接口）
├── run_mission.sh          # Shell 启动脚本（source ROS + 启动驱动）
└── mission_config.json     # 航点和动作配置
```

## 依赖

- Python 3.10+
- PySide6 >= 6.5
- pymavlink >= 1.4
- python-tsp >= 0.4（可选，用于精确 TSP 求解）
- numpy >= 1.24
