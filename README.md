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
| 主线任务 | 标记主线格子 + 全局完成条件 |
| 路径规划 | A* 寻路 + TSP 旅行商求解 + 蛇形遍历 |
| 斜飞支持 | 8 方向移动，禁飞区边缘安全检查 |
| 模拟飞行 | 可视化无人机沿路径飞行，动作弹窗提示 |
| 任务导出 | Python 脚本 + Shell 启动脚本 + JSON 配置 |
| 遥测监控 | MAVLink UDP 实时位置 / 状态 / 节点信息 |
| 摄像头监控 | HTTP MJPEG 视频流实时显示 |
| 3D 点云 | OpenGL 渲染，支持轨道 / 第一人称双模式 |
| 3D 点云预览 | pyqtgraph.opengl GPU 渲染 |
| 远程管理 | SSH 连接 OrangePi，一键启动 / 停止服务 |
| 任务测试 | 不起飞测试脚本，验证任务逻辑 |
| 仪表盘 | 系统实时监控（CPU / 内存 / 连接状态） |

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

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
ticup/
├── mission_grid/           # 地面站主项目
│   ├── app.py              # 入口：python app.py
│   ├── requirements.txt    # Python 依赖
│   └── mission_grid_app/   # 应用主包
├── TIdown/                 # 机载电脑文件镜像（只读参考）
├── infomation/             # 厂家参考文档
├── cominfo/                # 比赛信息
├── AGENTS.md               # 项目开发指南
├── COLLABORATION_GUIDE.md  # 协作开发指南
└── README.md               # 本文件
```

## 协作开发

详见 [COLLABORATION_GUIDE.md](COLLABORATION_GUIDE.md)

**分支策略**：
- `master`: 稳定版本
- `dev/moessif`: moessif 的开发分支
- `dev/mori`: mori 的开发分支

## 生成的任务包

导出后直接部署到 Orange Pi 机载电脑：

```bash
# SCP 传输到机载电脑
scp -r mission_grid_YYYYMMDD_HHMMSS/ orangepi@<IP>:/home/orangepi/

# SSH 登录并执行
ssh orangepi@<IP>
cd /home/orangepi/mission_grid_YYYYMMDD_HHMMSS/
chmod +x run_mission.sh
./run_mission.sh
```

## 技术栈

- **前端 UI**: PySide6 (Qt 6) + Material You 3 自定义主题
- **路径规划**: A* / ARA* + python-tsp + 蛇形遍历
- **通信协议**: MAVLink UDP (pymavlink)
- **3D 渲染**: OpenGL + pyqtgraph.opengl
- **机载接口**: uav_ctrl_tools.CtrlTools (ROS Noetic)
- **SLAM**: FAST_LIO (ikd-Tree) + Livox MID360

## 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|----------|
| v1.5.0 | 2026-07-01 | 3D 点云预览、任务测试系统、摄像头工具 |
| v1.3.1 | 2026-06-30 | 配置系统、网络扫描、Bug 修复 |
| v1.3.0 | 2026-06-30 | 仪表盘、远程管理、摄像头、3D 点云 |
| v1.0.0 | 2026-06-29 | 初始版本：网格编辑、路径规划、任务导出 |

## 开发团队

- **moessif**: 地面站 UI、路径规划、任务导出
- **mori**: 协作开发
