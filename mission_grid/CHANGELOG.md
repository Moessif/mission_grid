# 更新日志 (CHANGELOG)

本文件记录 MissionGrid 项目的所有重要更新。每次发布新版本时自动更新。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) (主版本.次版本.修订号)。

---

## [1.2.0] - 2026-06-30

### 修复
- 降落逻辑优化
  - 无降落动作时自动返回起飞点降落（而非原地降落）
  - 有降落动作时直接执行，避免重复降落
  - 代码生成器智能检测是否需要返回起飞点

---

## [1.1.0] - 2026-06-29

### 新增
- 任务包导出可靠性修复（3 个严重 Bug）
  - `set_yaw` 单位修复：度数→弧度（`math.radians()`）
  - `CtrlTools()` 构造函数兼容：注入虚拟 `~point_0` ROS 参数防止崩溃
  - Shell 启动脚本加入 SLAM 节点（`node_manage.py`）和正确的等待时间
- 全项目中文文档系统
  - 所有 12 个 Python 文件添加完整的模块级/类级/方法级 docstring
  - `mission_grid/README.md` 项目概览、目录结构、文件关系图
  - `mission_grid_app/README.md` 模块层级架构、数据流图、依赖表
- 遥测网格实时显示
  - 无人机位置红点+坐标标签在网格上实时渲染
  - MAVROS→网格坐标旋转变换（支持 init_yaw 偏移）
  - 连接状态指示灯（绿/灰）
  - 节点状态着色（运行中=绿色，已停止=灰色）
- UI 细节优化
  - 格子悬停 Tooltip（显示名称、动作、禁飞/主线状态）
  - 禁飞区切换操作反馈
  - MChip 支持动态状态色（success/warning/error）
  - 分割器位置记忆（QSettings）
  - 心跳发送优化

### 修复
- `set_yaw` 传入度数导致无人机原地打转
- `CtrlTools()` 无 ROS 参数时 ValueError 崩溃
- Shell 脚本缺少 SLAM 启动导致导航盲飞
- MAVROS 等待时间从 25s 恢复到 30s
- grid_widget 双层 QPen 渲染错误
- `self.scene` 遮蔽 `QGraphicsView.scene()` 方法

---

## [1.0.0] - 2026-06-29

### 新增
- Material You 3 全面 UI 重设计
  - MD3Colors 紫色主题配色系统（39 个语义化颜色变量）
  - 全局 QSS 样式表（覆盖所有 Qt 组件）
  - 自定义组件：MCard、MChip、MRippleButton（涟漪动画）、AnimatedStackedWidget（滑动切换）
  - Fusion 样式支持（Windows 上 QSS border-radius 生效）
- 网格编辑器（7×9 可视化，QGraphicsView）
  - 动作编辑模式：左键设置动作，右键标记禁飞区
  - 手动航线模式：左键添加航点，右键移除
  - 主线任务编辑模式
  - 模拟飞行可视化
- 动作系统（10 种动作类型）
  - 起飞、拍照保存、识别二维码、YOLO 动物识别
  - H 点识别降落、直接降落、调整航向
  - 蜂鸣器、舵机、激光
- 触发条件系统（4 种条件，AND 逻辑）
  - 每次经过、首次经过、最后经过、主线完成后
- 主线任务系统
  - 格子选择 + 5 种全局完成条件
- 路径规划引擎
  - A* 搜索（8 方向，octile 启发函数）
  - ARA* 渐进优化搜索
  - TSP 求解：DP 精确（≤12 点）+ SA+LS 启发式（>12 点）
  - 局部搜索优化：2-opt + or-opt
  - 蛇形遍历（遍历所有格子）
  - 斜飞支持（禁飞区边缘安全检查）
- 任务代码生成器
  - Python 任务脚本（含触发条件、坐标旋转、动作执行）
  - Shell 启动脚本（source ROS + 启动驱动）
  - JSON 配置文件
- MAVLink UDP 遥测
  - 位置接收（LOCAL_POSITION_NED）
  - 飞行状态（HEARTBEAT 解锁/模式）
  - 节点状态（CM_STATUS 位掩码）
- 方案管理
  - JSON 格式保存/加载完整方案
  - 快捷键 Ctrl+1~4 切换标签页
