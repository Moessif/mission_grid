# 更新日志 (CHANGELOG)

本文件记录 MissionGrid 项目的所有重要更新。每次发布新版本时自动更新。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) (主版本.次版本.修订号)。

---

## [1.5.0] - 2026-07-01

### 新增
- 3D 点云预览模块 (lidar_view.py)
  - 使用 pyqtgraph.opengl 进行 GPU 渲染
  - 支持订阅 FAST-LIO 的 /cloud_registered_body 话题
  - 后台线程解析与降采样，UI 线程只负责渲染
  - 支持 rosbridge_server 连接
- 摄像头测试工具
  - check_camera.py：摄像头状态检查
  - diagnose_camera.sh：摄像头诊断脚本
  - quick_camera.sh：快速摄像头测试
  - start_camera_server.sh：摄像头服务器启动
  - start_camera_v2.sh：摄像头 V2 启动
- 任务测试系统
  - test_mission.py：不起飞测试脚本
  - 测试指南.md：详细测试说明
- ROS 编译工具
  - compile_ros.sh：ROS 编译脚本
  - ssh_compile.py：SSH 远程编译
  - fix_permissions.sh：权限修复脚本
- 其他工具
  - push_all.bat：一键推送所有更改
  - start_all_services.sh：一键启动所有服务

### 变更
- 依赖更新
  - 新增 pyqtgraph：3D 点云渲染
  - 新增 websocket-client：rosbridge 连接
- 文档更新
  - README.md：添加新功能说明
  - 测试指南.md：任务包测试流程

---

## [1.3.1] - 2026-06-30

### 新增
- 配置系统
  - 配置文件保存在应用目录下 (`mission_grid/config.json`)
  - 可配置 OrangePi IP、SSH 凭据、ROS 话题、端口等
  - 连接 SSH 时自动保存 IP 到配置文件
- 网络扫描功能
  - 使用 nmap 快速扫描局域网中的 OrangePi
  - 远程管理标签页添加「🔍 扫描」按钮

### 修复
- 移除所有硬编码 IP 地址
- 默认 OrangePi IP 改为空（需要手动输入或扫描）
- ROS 节点和数据监控表格改为只读
- 添加 QGroupBox 导入缺失

---

## [1.3.0] - 2026-06-30

### 新增
- 仪表盘监控系统
  - 系统信息（主机名、运行时间、操作系统）
  - 性能监控（CPU/内存/磁盘使用率进度条）
  - 连接状态（SSH/遥测/摄像头/点云）
  - 性能指标（摄像头 FPS、点云 FPS、点云点数、遥测位置）
  - 最近日志显示
  - 每秒自动更新

- 远程服务管理
  - SSH 连接 OrangePi
  - 选择性启动/停止 ROS 服务（MAVROS/Livox/SLAM/摄像头/web_video_server/rosbridge）
  - 自动获取本机 IP 地址，配置 MAVROS gcs_url
  - 串行启动服务，避免 SSH 通道泄漏
  - 实时命令输出日志

- 摄像头监控
  - HTTP MJPEG 视频流实时显示
  - 自动获取最新帧，避免延迟堆积
  - 连接/断开操作
  - 帧率显示

- 3D 点云可视化
  - 双模式相机：轨道模式 + 第一人称漫游模式
  - 轨道模式：左键旋转、右键平移、滚轮缩放
  - 第一人称模式（按 F 切换）：WASD 移动、鼠标转向、Space/Shift 升降
  - VBO 加速渲染 + 显示列表缓存
  - 支持 Livox CustomMsg 和 PointCloud2 两种消息格式
  - 自动下采样大点云（可配置显示上限，最大 10 万点）
  - 话题选择器和调试日志面板
  - 雾化深度效果、地面网格

- 日志系统
  - 每次运行生成日志文件到 log/ 目录
  - 文件名格式：mission_grid_YYYYMMDD_HHMMSS.log
  - 支持 DEBUG/INFO/WARNING/ERROR 级别

- OrangePi 启动脚本
  - start_all_services.sh：一键启动所有服务
  - start_rosbridge.sh：点云 WebSocket 服务

### 修复
- 摄像头延迟堆积问题
  - 使用 grab() 跳过缓冲区旧帧
  - 添加帧流控机制
- 摄像头默认话题修正为 /image
- 摄像头启动超时保护
- 标签页构建方法修复
  - 恢复误删的 _build_data_tab 方法
  - 删除重复的 _build_lidar_tab 占位代码
- 远程管理 SSH 通道泄漏问题
  - 重构为串行启动服务
  - 添加线程安全锁和异常处理
  - 简化命令执行逻辑

### 变更
- 移除摄像头自动连接（避免启动时卡死）
- 标签页从 5 个增加到 6 个（新增仪表盘）
- 快捷键从 Ctrl+1~5 改为 Ctrl+1~6

---

## [1.2.4] - 2026-06-30

### 修复
- 摄像头延迟堆积问题
  - 使用 grab()+retrieve() 跳过缓冲区旧帧，始终显示最新画面
  - 添加帧流控机制，避免帧堆积导致延迟越来越大
  - 新增 FPS 显示

### 新增
- 3D 点云全面重写
  - 双模式相机：轨道模式 + 第一人称漫游模式
  - 轨道模式：左键旋转、右键平移、滚轮缩放
  - 第一人称模式（按 F 切换）：WASD 移动、鼠标转向、Space/Shift 升降
  - 接收端丢帧机制：只保留最新帧，避免堆积延迟
  - VBO 加速渲染 + 显示列表缓存网格/坐标轴
  - 支持 Livox CustomMsg 和 PointCloud2 两种消息格式
  - 自动下采样大点云（可配置显示上限，最大 50 万点）
  - 新增话题选择器和调试日志面板
  - 雾化深度效果、60° 广角视野

### 修复
- 标签页构建方法修复
  - 恢复误删的 _build_data_tab 方法
  - 删除重复的 _build_lidar_tab 占位代码

### 新增
- OrangePi 服务启动脚本
  - start_camera_pointcloud.sh：摄像头服务启动脚本
  - start_rosbridge.sh：点云 WebSocket 服务启动脚本

---

## [1.2.3] - 2026-06-30

### 修复
- GUI 模拟飞行显示降落动作
  - 模拟完成时显示降落动作弹窗
  - 区分有降落动作和无降落动作的情况
  - 无降落动作时显示"返回起飞点降落"提示

---

## [1.2.2] - 2026-06-30

### 修复
- 降落逻辑完善
  - 确保返回起飞点后执行降落
  - 优化日志消息，更清晰地显示降落过程
  - 代码生成器在路径末尾添加返回起飞点逻辑

---

## [1.2.1] - 2026-06-30

### 修复
- 路径规划修复
  - 修复 TSP 求解器：当只有 2 个点时正确返回起飞点
  - 优化代码生成器：移除重复的返回起飞点逻辑
  - 路径规划已包含返回起飞点，代码生成器直接执行降落

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
