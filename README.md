# 无人机网格任务编排系统

2025 年全国大学生电子设计竞赛 **H 题 — 野生动物巡查系统** 地面站与机载控制方案。

## 项目简介

基于 PySide6 的 Windows 端地面站，在 7×9 网格地图上可视化编排无人机任务，自动规划飞行路径，一键导出可部署到机载电脑的任务脚本。

硬件平台：Orange Pi CM5 + Livox MID360 激光雷达 + RealSense 下视摄像头 + ArduPilot 飞控。

## 功能特性

| 功能 | 说明 |
|------|------|
| 网格编辑器 | 7×9 可视化网格，左键设置动作，右键标记禁飞区 |
| 动作系统 | 10 种动作：起飞 / 拍照 / 二维码 / YOLO 识别 / H 降落 / 降落 / 航向 / 蜂鸣器 / 舵机 / 激光 |
| 触发条件 | 每次经过 / 首次经过 / 最后经过 / 主线完成后，多条件 AND 逻辑 |
| 主线任务 | 标记主线格子 + 全局完成条件（所有检测完成 / 所有二维码扫描完成等） |
| 路径规划 | A* 寻路 + TSP 旅行商求解（≤12 点精确 DP，>12 点 SA 启发式）+ 蛇形遍历 |
| 斜飞支持 | 8 方向移动，禁飞区边缘安全检查 |
| 模拟飞行 | 可视化无人机沿路径飞行，经过动作格子弹窗提示 |
| 任务导出 | 生成 Python 任务脚本 + Shell 启动脚本 + JSON 配置，直接部署到机载电脑 |
| 遥测监控 | MAVLink UDP 实时接收位置 / 飞行状态 / ROS 节点状态 |
| 方案管理 | JSON 格式保存 / 加载完整任务方案 |
| Material You | Google Material Design 3 风格 UI，紫色主题 |

## 快速启动

```bash
# 安装依赖
pip install PySide6 pymavlink python-tsp numpy

# 启动地面站
cd mission_grid
python app.py
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

- 每格 50×50cm，总区域 450×350cm
- 起飞点默认 A9B1（右下角）
- 机头始终朝 +Y 方向（B1→B7）

## 项目结构

```
mission_grid/
├── app.py                      # 入口：python app.py
├── requirements.txt            # Python 依赖
├── mission_grid_app/           # 应用主包
│   ├── main.py                 # QApplication 启动
│   ├── main_window.py          # 主窗口（集成所有模块）
│   ├── models.py               # 数据模型（GridConfig, CellAction）
│   ├── grid_widget.py          # 网格可视化（QGraphicsView）
│   ├── action_editor.py        # 动作编辑弹窗
│   ├── main_task_editor.py     # 主线任务编辑弹窗
│   ├── path_planner.py         # 路径规划（A* + TSP + 蛇形遍历）
│   ├── code_generator.py       # 任务脚本代码生成器
│   ├── telemetry.py            # MAVLink UDP 遥测
│   ├── material_theme.py       # Material You 3 主题
│   └── material_widgets.py     # Material 自定义组件
│   └── README.md               # 模块详细文档
└── README.md                   # 项目说明
```

## 生成的任务包

导出后直接部署到 Orange Pi 机载电脑：

```bash
# SCP 传输到机载电脑
scp -r mission_grid_YYYYMMDD_HHMMSS/ orangepi@10.118.249.217:/home/orangepi/

# SSH 登录并执行
ssh orangepi@10.118.249.217
cd /home/orangepi/mission_grid_YYYYMMDD_HHMMSS/
chmod +x run_mission.sh
./run_mission.sh
```

## 技术栈

- **前端 UI**: PySide6 (Qt 6) + Material You 3 自定义主题
- **路径规划**: A* / ARA* + python-tsp (DP/SA/LS) + 蛇形遍历
- **通信协议**: MAVLink UDP (pymavlink)
- **机载接口**: uav_ctrl_tools.CtrlTools (ROS Noetic)
- **SLAM**: FAST_LIO (ikd-Tree) + Livox MID360

## 依赖

| 库 | 版本 | 用途 |
|----|------|------|
| PySide6 | ≥ 6.5 | Qt UI 框架 |
| pymavlink | ≥ 1.4 | MAVLink 通信 |
| numpy | ≥ 1.24 | 距离矩阵计算 |
| python-tsp | ≥ 0.4 | TSP 精确/启发式求解（可选） |

## 开发团队

- 地面站 UI 与路径规划
- 机载控制与竞赛任务
