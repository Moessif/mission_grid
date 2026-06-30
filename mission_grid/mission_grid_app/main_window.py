"""
主窗口模块
==========

MissionGrid 地面站的主窗口，集成所有子模块并协调交互。

本模块包含：
- MainWindow: QMainWindow 子类，应用的顶层 UI 容器

依赖关系：
    models ← 本模块（GridConfig, CellAction, COL_LABELS, ROW_LABELS）
    material_theme ← 本模块（COLORS 颜色常量）
    material_widgets ← 本模块（MCard, MChip, AnimatedStackedWidget, add_shadow）
    grid_widget ← 本模块（GridWidget 网格视图）
    action_editor ← 本模块（ActionEditorDialog 动作编辑弹窗）
    main_task_editor ← 本模块（MainTaskEditorDialog 主线任务编辑弹窗）
    path_planner ← 本模块（plan_path, plan_path_all 路径规划）
    code_generator ← 本模块（export_mission 任务导出）
    telemetry ← 本模块（TelemetryWorker MAVLink 遥测线程）

UI 布局结构：
    MainWindow (QMainWindow)
    └── central QWidget (QVBoxLayout)
        ├── 顶部工具栏卡片 (MCard)
        │   ├── 飞行高度设置
        │   ├── 电子围栏设置
        │   ├── 模拟飞行 / 保存 / 加载 按钮
        │   └── 分隔线
        ├── 操作栏卡片 (MCard)
        │   ├── 自动规划路径（下拉菜单：有动作格子/所有格子）
        │   ├── 导出任务包
        │   ├── 手动编辑航线（切换按钮）
        │   ├── 编辑主线任务
        │   ├── 清除航点
        │   └── 状态芯片 MChip
        └── 主内容区 (QSplitter)
            ├── 左侧：网格视图 (GridWidget in MCard)
            └── 右侧：标签页面板 (MCard)
                ├── 标签栏 QTabBar (Ctrl+1~4 快捷键)
                ├── 堆叠页面 AnimatedStackedWidget
                │   ├── ROS 节点监控页 (QTableWidget)
                │   ├── 数据监控页 (QTableWidget)
                │   ├── 摄像头预览页 (占位符)
                │   └── 3D 点云页 (占位符)
                └── 状态栏（连接指示灯 + 状态文本）

功能模块：
    1. 网格编辑：左键编辑动作、右键标记禁飞区
    2. 路径规划：自动（TSP+A*）或手动航点编辑
    3. 模拟飞行：可视化无人机沿路径飞行
    4. 任务导出：生成可部署的 Python+Shell 任务包
    5. 方案管理：JSON 格式保存/加载完整方案
    6. 遥测监控：MAVLink 实时位置/状态/节点信息
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QFont, QColor, QAction, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .action_editor import ActionEditorDialog
from .grid_widget import GridWidget
from .main_task_editor import MainTaskEditorDialog
from .material_theme import COLORS as c
from .material_widgets import MCard, MChip, AnimatedStackedWidget, add_shadow
from .models import CellAction, GridConfig, COL_LABELS, ROW_LABELS
from .path_planner import plan_path, plan_path_all
from .code_generator import export_mission
from .telemetry import TelemetryWorker
from .video_stream import CameraWidget
from .point_cloud import PointCloudWidget
from .remote_service import RemoteServiceWidget
from .dashboard import DashboardWidget


class MainWindow(QMainWindow):
    """
    MissionGrid 地面站主窗口。

    持有 GridConfig 作为全局数据模型，协调所有子模块的交互。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MissionGrid - 网格任务编排地面站")
        self.resize(1400, 900)
        self.config = GridConfig()         # 全局网格配置
        self._current_path = []            # 当前规划路径
        self._sim_index = 0               # 模拟飞行当前步数
        self._sim_timer = QTimer()         # 模拟飞行定时器
        self._sim_timer.timeout.connect(self._sim_step)
        self._build_ui()

    # ==========================================================
    # UI 构建
    # ==========================================================

    def _build_ui(self):
        """构建完整的主窗口 UI 布局。"""
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ----------------------------------------------------------
        # 顶部工具栏卡片：飞行高度 + 围栏 + 模拟/保存/加载
        # ----------------------------------------------------------
        toolbar_card = MCard()
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        alt_label = QLabel("飞行高度")
        alt_label.setStyleSheet(f"font-weight:600; color:{c.on_surface_variant}; font-size:12px;")
        toolbar.addWidget(alt_label)
        self.alt_spin = QDoubleSpinBox()
        self.alt_spin.setRange(0.3, 5.0)
        self.alt_spin.setValue(self.config.flight_altitude)
        self.alt_spin.setSingleStep(0.1)
        self.alt_spin.setSuffix(" m")
        self.alt_spin.setFixedWidth(100)
        self.alt_spin.valueChanged.connect(lambda v: setattr(self.config, 'flight_altitude', v))
        toolbar.addWidget(self.alt_spin)
        toolbar.addWidget(self._make_separator())

        # 电子围栏设置
        fence_label = QLabel("围栏")
        fence_label.setStyleSheet(f"font-weight:600; color:{c.on_surface_variant}; font-size:12px;")
        toolbar.addWidget(fence_label)
        for attr, label_text in [("fence_min_x", "X"), ("fence_max_x", "~"), ("fence_min_y", "Y"), ("fence_max_y", "~")]:
            spin = QDoubleSpinBox()
            spin.setRange(0, 10)
            spin.setValue(getattr(self.config, attr))
            spin.setFixedWidth(70)
            spin.valueChanged.connect(lambda v, a=attr: setattr(self.config, a, v))
            setattr(self, f"_{attr}_spin", spin)
            if label_text == "~":
                sep = QLabel("~")
                sep.setStyleSheet(f"color:{c.outline}; font-weight:bold;")
                toolbar.addWidget(sep)
            else:
                lbl = QLabel(label_text)
                lbl.setStyleSheet(f"font-weight:600; color:{c.on_surface_variant}; font-size:12px; margin-left:8px;")
                toolbar.addWidget(lbl)
            toolbar.addWidget(spin)

        toolbar.addStretch()

        # 模拟飞行 / 保存 / 加载 按钮
        self.sim_btn = QPushButton("模拟飞行")
        self.sim_btn.setProperty("cssClass", "tonal")
        self.sim_btn.clicked.connect(self._start_simulation)
        toolbar.addWidget(self.sim_btn)

        save_btn = QPushButton("保存方案")
        save_btn.setProperty("cssClass", "outlined")
        save_btn.clicked.connect(self._save_plan)
        toolbar.addWidget(save_btn)

        load_btn = QPushButton("加载方案")
        load_btn.setProperty("cssClass", "outlined")
        load_btn.clicked.connect(self._load_plan)
        toolbar.addWidget(load_btn)

        toolbar_card.addLayout(toolbar)
        main_layout.addWidget(toolbar_card)

        # ----------------------------------------------------------
        # 操作栏卡片：路径规划 + 导出 + 手动模式 + 主线任务
        # ----------------------------------------------------------
        action_card = MCard()
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        # 自动规划路径（下拉菜单）
        plan_btn = QPushButton("自动规划路径 ▾")
        plan_menu = QMenu(self)
        a1 = QAction("遍历有动作的格子", self)
        a1.triggered.connect(lambda: self._plan_path(mode="action_cells"))
        plan_menu.addAction(a1)
        a2 = QAction("遍历所有格子", self)
        a2.triggered.connect(lambda: self._plan_path(mode="all_cells"))
        plan_menu.addAction(a2)
        plan_btn.setMenu(plan_menu)
        action_row.addWidget(plan_btn)

        export_btn = QPushButton("导出任务包")
        export_btn.clicked.connect(self._export)
        action_row.addWidget(export_btn)

        self.manual_btn = QPushButton("手动编辑航线")
        self.manual_btn.setCheckable(True)
        self.manual_btn.clicked.connect(self._toggle_manual_mode)
        action_row.addWidget(self.manual_btn)

        self.main_task_btn = QPushButton("编辑主线任务")
        self.main_task_btn.setProperty("cssClass", "tonal")
        self.main_task_btn.clicked.connect(self._open_main_task_editor)
        action_row.addWidget(self.main_task_btn)

        clear_btn = QPushButton("清除航点")
        clear_btn.setProperty("cssClass", "text")
        clear_btn.clicked.connect(self._clear_waypoints)
        action_row.addWidget(clear_btn)

        action_row.addStretch()

        # 状态芯片
        self._path_chip = MChip("就绪", filled=True)
        action_row.addWidget(self._path_chip)

        action_card.addLayout(action_row)
        main_layout.addWidget(action_card)

        # ----------------------------------------------------------
        # 主内容区：左侧网格 + 右侧标签页
        # ----------------------------------------------------------
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：网格视图
        grid_card = MCard()
        self.grid_widget = GridWidget(self.config)
        self.grid_widget.cell_action_changed.connect(self._on_cell_click)
        self.grid_widget.cell_nofly_changed.connect(self._on_nofly_changed)
        self.grid_widget.waypoint_added.connect(self._on_waypoint_added)
        grid_card.addWidget(self.grid_widget)
        splitter.addWidget(grid_card)

        # 右侧：标签页面板
        right_card = MCard()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.addTab("📊  仪表盘")
        self.tab_bar.addTab("📡  ROS 节点")
        self.tab_bar.addTab("📈  数据监控")
        self.tab_bar.addTab("📷  摄像头")
        self.tab_bar.addTab("🧊  3D 点云")
        self.tab_bar.addTab("🖥  远程管理")
        right_layout.addWidget(self.tab_bar)

        self.stack = AnimatedStackedWidget()
        self.stack.addWidget(self._build_dashboard_tab())
        self.stack.addWidget(self._build_node_tab())
        self.stack.addWidget(self._build_data_tab())
        self.stack.addWidget(self._build_camera_tab())
        self.stack.addWidget(self._build_lidar_tab())
        self.stack.addWidget(self._build_remote_tab())
        right_layout.addWidget(self.stack, 1)

        self.tab_bar.currentChanged.connect(self.stack.slideToIndex)
        self.tab_bar.setCurrentIndex(0)

        # Ctrl+1~6 快捷键切换标签页
        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self, lambda idx=i: self._switch_tab(idx))

        # 状态栏（连接指示灯 + 状态文本）
        status_bar = QWidget()
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(8, 4, 8, 4)
        status_bar_layout.setSpacing(8)
        self._conn_dot = QLabel("●")
        self._conn_dot.setFixedWidth(16)
        self._conn_dot.setAlignment(Qt.AlignCenter)
        self._conn_dot.setStyleSheet(f"color:{c.outline}; font-size:10px;")
        self._conn_dot.setToolTip("遥测未连接")
        status_bar_layout.addWidget(self._conn_dot)
        self.status_label = QLabel("就绪 — 左键设置动作，右键标记禁飞区")
        self.status_label.setStyleSheet(f"color:{c.on_surface_variant}; font-size:12px;")
        status_bar_layout.addWidget(self.status_label, 1)
        right_layout.addWidget(status_bar)

        right_card.addLayout(right_layout)
        splitter.addWidget(right_card)

        # 分割器比例和状态恢复
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self._splitter = splitter
        settings = QSettings("MissionGrid", "MissionGrid")
        saved_sizes = settings.value("splitter_sizes")
        if saved_sizes:
            splitter.restoreState(saved_sizes)
        main_layout.addWidget(splitter)

        # ----------------------------------------------------------
        # 遥测初始化
        # ----------------------------------------------------------
        self._telem_alive = False    # 遥测是否收到过数据
        self._init_yaw = 0.0         # 初始航向角（用于坐标旋转）
        self.telemetry = TelemetryWorker()
        self.telemetry.position_updated.connect(self._on_position)
        self.telemetry.status_updated.connect(self._on_status)
        self.telemetry.node_status_updated.connect(self._on_node_status)
        self.telemetry.start()
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._heartbeat_tick)
        self.heartbeat_timer.start(1000)

    # ==========================================================
    # 辅助 UI 构建
    # ==========================================================

    def _make_separator(self):
        """创建垂直分隔线。"""
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"background:{c.outline_variant};")
        return sep

    def _switch_tab(self, index: int):
        """切换标签页（快捷键触发）。"""
        self.tab_bar.setCurrentIndex(index)
        self.stack.slideToIndex(index)

    # ----------------------------------------------------------
    # 标签页内容构建
    # ----------------------------------------------------------

    def _build_dashboard_tab(self):
        """仪表盘标签页。"""
        self.dashboard_widget = DashboardWidget()
        return self.dashboard_widget

    def _build_node_tab(self):
        """ROS 节点监控标签页。6 个节点的状态表格，遥测更新时着色。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 提示信息
        hint = QLabel("等待 MAVLink 遥测数据... 确保 MAVROS 已启动")
        hint.setStyleSheet("color: gray; font-size: 12px; padding: 8px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # 节点信息表格
        self.node_table = QTableWidget(6, 5)
        self.node_table.setHorizontalHeaderLabels(["节点", "状态", "描述", "进程名", "权限"])
        self.node_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.node_table.verticalHeader().setVisible(False)
        nodes = [
            ("MAVROS节点", "已停止", "机载电脑与飞控通信", "mavros", "不可操作"),
            ("SLAM节点", "已停止", "提供室内定位信息", "manage_bridge_node", "可操作"),
            ("相机节点", "已停止", "RealSense 摄像头驱动", "cam_pub", "可操作"),
            ("路径规划节点", "已停止", "ego_planner 运动控制器", "ego_planner", "暂不支持"),
            ("定位融合节点", "已停止", "定位融合提高odom频率", "odom_fusion", "不可操作"),
            ("硬件驱动节点", "已停止", "读取原始数据的相关节点", "hardware_driver", "不可操作"),
        ]
        for i, (name, status, desc, proc, perm) in enumerate(nodes):
            self.node_table.setItem(i, 0, QTableWidgetItem(name))
            self.node_table.setItem(i, 1, QTableWidgetItem(status))
            self.node_table.setItem(i, 2, QTableWidgetItem(desc))
            self.node_table.setItem(i, 3, QTableWidgetItem(proc))
            self.node_table.setItem(i, 4, QTableWidgetItem(perm))
        layout.addWidget(self.node_table)

        # 节点说明
        info_group = QGroupBox("节点说明")
        info_layout = QVBoxLayout(info_group)
        info_text = QLabel(
            "• MAVROS: 飞控通信桥接，转发 MAVLink 消息\n"
            "• SLAM: FAST_LIO 室内定位，提供 /Odometry 话题\n"
            "• 相机: RealSense 下视摄像头，发布 /image 话题\n"
            "• 路径规划: ego_planner 运动控制器\n"
            "• 定位融合: 提高定位频率，融合多传感器\n"
            "• 硬件驱动: 读取传感器原始数据"
        )
        info_text.setStyleSheet("color: gray; font-size: 11px; padding: 8px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        return widget

    def _build_lidar_tab(self):
        """3D 点云标签页。"""
        self.pointcloud_widget = PointCloudWidget()
        return self.pointcloud_widget

    def _build_data_tab(self):
        """数据监控标签页。显示 MAVLink 消息数据（飞行状态、节点状态、位置）。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 提示信息
        hint = QLabel("等待 MAVLink 遥测数据... 确保 MAVROS 已启动")
        hint.setStyleSheet("color: gray; font-size: 12px; padding: 8px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.data_table = QTableWidget(3, 2)
        self.data_table.setHorizontalHeaderLabels(["消息", "数据"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.verticalHeader().setVisible(False)
        msgs = [("FLY_STATUS (#150)", "-"), ("CM_STATUS (#151)", "-"), ("POSITION_DATA (#152)", "-")]
        for i, (name, val) in enumerate(msgs):
            self.data_table.setItem(i, 0, QTableWidgetItem(name))
            self.data_table.setItem(i, 1, QTableWidgetItem(val))
        layout.addWidget(self.data_table)

        return widget

    def _build_camera_tab(self):
        """摄像头预览标签页。"""
        self.camera_widget = CameraWidget()
        return self.camera_widget

    def _build_lidar_tab(self):
        """3D 点云标签页。"""
        self.pointcloud_widget = PointCloudWidget()
        return self.pointcloud_widget

    def _build_remote_tab(self):
        """远程服务管理标签页。"""
        self.remote_widget = RemoteServiceWidget()
        return self.remote_widget

    # ==========================================================
    # 摄像头自动连接
    # ==========================================================

    def _auto_connect_camera(self):
        """启动时自动尝试连接摄像头。"""
        if hasattr(self, 'camera_widget'):
            self.camera_widget.connect_stream()

    # ==========================================================
    # 起飞点自动检测
    # ==========================================================

    def _update_takeoff_from_actions(self):
        """从动作配置中自动检测起飞点。如果无 "takeoff" 动作则默认 A9B1。"""
        for (col, row), actions in self.config.actions.items():
            for a in actions:
                if a.action_type == "takeoff":
                    self.config.takeoff_col = col
                    self.config.takeoff_row = row
                    return
        self.config.takeoff_col = 8
        self.config.takeoff_row = 0

    # ==========================================================
    # 网格交互回调
    # ==========================================================

    def _on_cell_click(self, col, row):
        """格子左键点击：打开动作编辑弹窗。"""
        if self.config.is_no_fly(col, row):
            return
        dialog = ActionEditorDialog(col, row, self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self._update_takeoff_from_actions()
        self.grid_widget.refresh()

    def _on_nofly_changed(self, col, row):
        """禁飞区状态变化：刷新网格并显示操作反馈。"""
        self.grid_widget.refresh()
        label = self.config.cell_label(col, row)
        if self.config.is_no_fly(col, row):
            self.status_label.setText(f"{label} 已标记为禁飞区")
        else:
            self.status_label.setText(f"{label} 已解除禁飞")

    def _toggle_manual_mode(self, checked):
        """切换手动航线编辑模式。"""
        self.grid_widget.set_manual_mode(checked)
        if checked:
            self.manual_btn.setText("退出手动模式")
            self.manual_btn.setProperty("cssClass", "checkable checked")
            self.status_label.setText("手动模式 — 左键按顺序添加航点，右键移除")
        else:
            self.manual_btn.setText("手动编辑航线")
            self.manual_btn.setProperty("cssClass", "")
            self.status_label.setText("就绪 — 左键设置动作，右键标记禁飞区")
        self.style().unpolish(self.manual_btn)
        self.style().polish(self.manual_btn)

    def _open_main_task_editor(self):
        """打开主线任务编辑弹窗。"""
        dialog = MainTaskEditorDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            n = len(self.config.main_task_cells)
            nc = len(self.config.main_task_conditions)
            self._path_chip.setText(f"主线: {n}格 {nc}条件")
            self.grid_widget.refresh()

    def _clear_waypoints(self):
        """清除手动航点和路径叠加层。"""
        self.config.custom_waypoints.clear()
        self._current_path = []
        self.grid_widget.clear_overlay()
        self._path_chip.setText("就绪")
        self.status_label.setText("航点已清除")

    def _on_waypoint_added(self, col, row):
        """手动模式下航点变化回调。"""
        label = self.config.cell_label(col, row)
        n = len(self.config.custom_waypoints)
        self.grid_widget.draw_waypoint_numbers()
        self._path_chip.setText(f"手动: {n}航点")
        self.status_label.setText(f"航点 {n}: {label}")

    # ==========================================================
    # 路径规划
    # ==========================================================

    def _plan_path(self, mode="action_cells"):
        """
        触发路径规划。

        参数:
            mode: "action_cells" 遍历有动作的格子 / "all_cells" 遍历所有格子
        """
        self._update_takeoff_from_actions()
        if self.config.custom_waypoints:
            # 手动航点模式
            path = list(self.config.custom_waypoints)
            self.grid_widget.draw_waypoint_numbers()
            self._path_chip.setText(f"手动: {len(path)}航点")
            self.status_label.setText(f"手动航线: {len(path)} 个航点")
        else:
            # 自动规划模式
            if mode == "all_cells":
                path = plan_path_all(self.config)
                mode_label = "遍历所有格子"
            else:
                path = plan_path(self.config)
                mode_label = "遍历有动作的格子"
            if not path:
                QMessageBox.warning(self, "路径规划", "无法找到有效路径。请检查禁飞区设置。")
                return
            self.grid_widget.draw_path(self.config, path)
            # 检查是否有降落格子
            land_cell = None
            for (c_, r), actions in self.config.actions.items():
                for a in actions:
                    if a.action_type == "land":
                        land_cell = (c_, r)
            if land_cell:
                endpoint_label = self.config.cell_label(*land_cell)
                self._path_chip.setText(f"{mode_label}: {len(path)}航点")
                self.status_label.setText(f"{mode_label}: {len(path)} 个航点 → 降落于 {endpoint_label}")
            else:
                self._path_chip.setText(f"{mode_label}: {len(path)}航点")
                self.status_label.setText(f"{mode_label}: {len(path)} 个航点 → 返回起飞点")
        self._current_path = path

    # ==========================================================
    # 任务导出
    # ==========================================================

    def _export(self):
        """导出任务包到用户选择的目录。"""
        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not output_dir:
            return
        try:
            entry = export_mission(self.config, output_dir)
            QMessageBox.information(self, "导出成功", f"任务包已导出:\n{entry}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    # ==========================================================
    # 模拟飞行
    # ==========================================================

    def _start_simulation(self):
        """启动/停止模拟飞行。300ms 一步，可视化无人机沿路径移动。"""
        if not self._current_path:
            QMessageBox.warning(self, "模拟飞行", "请先规划路径。")
            return
        if self._sim_timer.isActive():
            # 停止模拟
            self._sim_timer.stop()
            self.sim_btn.setText("模拟飞行")
            self.sim_btn.setProperty("cssClass", "tonal")
            self._path_chip.setText("就绪")
            self.status_label.setText("模拟已停止")
            self.style().unpolish(self.sim_btn)
            self.style().polish(self.sim_btn)
            return
        # 启动模拟
        self._sim_index = 0
        self._sim_trail = []
        self.sim_btn.setText("停止模拟")
        self.sim_btn.setProperty("cssClass", "danger")
        self.style().unpolish(self.sim_btn)
        self.style().polish(self.sim_btn)
        self._sim_timer.start(300)

    def _sim_step(self):
        """模拟飞行单步执行。"""
        if self._sim_index >= len(self._current_path):
            self._sim_timer.stop()
            # 检查是否有降落动作
            has_land = any(
                a.action_type == "land"
                for actions in self.config.actions.values()
                for a in actions
            )
            if has_land:
                self._path_chip.setText("模拟完成（已降落）")
                self.status_label.setText("模拟完成（已降落）")
            else:
                # 显示返回起飞点降落的提示
                self._path_chip.setText("模拟完成（返回起飞点降落）")
                self.status_label.setText("模拟完成（返回起飞点降落）")
                # 显示降落动作弹窗
                self._show_landing_popup()
            self.sim_btn.setText("模拟飞行")
            self.sim_btn.setProperty("cssClass", "tonal")
            self.style().unpolish(self.sim_btn)
            self.style().polish(self.sim_btn)
            return
        col, row = self._current_path[self._sim_index]
        self._sim_trail.append((col, row))
        self.grid_widget.set_drone_position(col, row, trail=self._sim_trail)
        label = self.config.cell_label(col, row)
        self._path_chip.setText(f"飞行: {self._sim_index + 1}/{len(self._current_path)}")
        self.status_label.setText(f"飞行中: {label}")
        actions = self.config.actions.get((col, row), [])
        if actions:
            self._show_action_popup(col, row, actions)
        self._sim_index += 1

    def _show_landing_popup(self):
        """模拟飞行完成时显示降落动作提示。"""
        popup = QDialog(self)
        popup.setWindowTitle("执行动作 - 降落")
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup.setStyleSheet(f"""
            QDialog {{
                background: {c.surface_container_lowest};
                border: 2px solid {c.primary};
                border-radius: 16px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(popup)
        layout.setSpacing(6)
        name_label = QLabel("📍 返回起飞点降落")
        name_label.setStyleSheet(f"font-size:16px; font-weight:700; color:{c.primary};")
        layout.addWidget(name_label)
        action_label = QLabel("✅ 降落")
        action_label.setStyleSheet(f"font-size:14px; color:{c.on_surface};")
        layout.addWidget(action_label)
        popup.setLayout(layout)
        popup.adjustSize()
        popup.show()
        QTimer.singleShot(1000, popup.close)

    def _show_action_popup(self, col, row, actions):
        """模拟飞行时弹出动作执行提示（500ms 后自动关闭）。"""
        from .action_editor import ACTION_TYPE_MAP, TRIGGER_LABEL_MAP
        popup = QDialog(self)
        popup.setWindowTitle(f"执行动作 - {self.config.cell_label(col, row)}")
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup.setStyleSheet(f"""
            QDialog {{
                background: {c.surface_container_lowest};
                border: 2px solid {c.primary};
                border-radius: 16px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(popup)
        layout.setSpacing(6)
        name_label = QLabel(f"📍 {self.config.cell_label(col, row)}")
        name_label.setStyleSheet(f"font-size:16px; font-weight:700; color:{c.primary};")
        layout.addWidget(name_label)
        for a in actions:
            display = ACTION_TYPE_MAP.get(a.action_type, (a.action_type, {}))[0]
            triggers = ", ".join(TRIGGER_LABEL_MAP.get(t, t) for t in a.triggers)
            action_label = QLabel(f"  [{triggers}] {display}")
            action_label.setStyleSheet(f"font-size:13px; color:{c.on_surface}; padding:2px 0;")
            layout.addWidget(action_label)
        popup.show()
        QTimer.singleShot(500, popup.close)

    # ==========================================================
    # 方案保存/加载
    # ==========================================================

    def _save_plan(self):
        """将完整方案保存为 JSON 文件。"""
        path, _ = QFileDialog.getSaveFileName(self, "保存方案", "", "JSON (*.json)")
        if not path:
            return
        data = {
            "takeoff_col": self.config.takeoff_col,
            "takeoff_row": self.config.takeoff_row,
            "flight_altitude": self.config.flight_altitude,
            "fence_min_x": self.config.fence_min_x,
            "fence_max_x": self.config.fence_max_x,
            "fence_min_y": self.config.fence_min_y,
            "fence_max_y": self.config.fence_max_y,
            "actions": {f"{k[0]},{k[1]}": [{"type": a.action_type, "params": a.params, "triggers": a.triggers} for a in v] for k, v in self.config.actions.items()},
            "no_fly": [f"{c_[0]},{c_[1]}" for c_ in self.config.no_fly],
            "custom_waypoints": [f"{c_[0]},{c_[1]}" for c_ in self.config.custom_waypoints],
            "main_task_cells": [f"{c_[0]},{c_[1]}" for c_ in self.config.main_task_cells],
            "main_task_conditions": list(self.config.main_task_conditions),
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_label.setText(f"方案已保存: {path}")

    def _load_plan(self):
        """从 JSON 文件加载完整方案。"""
        path, _ = QFileDialog.getOpenFileName(self, "加载方案", "", "JSON (*.json)")
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.config.takeoff_col = data.get("takeoff_col", 8)
        self.config.takeoff_row = data.get("takeoff_row", 0)
        self.config.flight_altitude = data.get("flight_altitude", 1.2)
        self.config.fence_min_x = data.get("fence_min_x", 0.0)
        self.config.fence_max_x = data.get("fence_max_x", 4.0)
        self.config.fence_min_y = data.get("fence_min_y", 0.0)
        self.config.fence_max_y = data.get("fence_max_y", 3.0)
        self.config.actions.clear()
        for key, actions in data.get("actions", {}).items():
            col, row = map(int, key.split(","))
            self.config.actions[(col, row)] = [CellAction(a["type"], a.get("params", {}), a.get("triggers", ["always"])) for a in actions]
        self.config.no_fly = set()
        for key in data.get("no_fly", []):
            col, row = map(int, key.split(","))
            self.config.no_fly.add((col, row))
        self.config.custom_waypoints = []
        for key in data.get("custom_waypoints", []):
            col, row = map(int, key.split(","))
            self.config.custom_waypoints.append((col, row))
        self.config.main_task_cells = set()
        for key in data.get("main_task_cells", []):
            col, row = map(int, key.split(","))
            self.config.main_task_cells.add((col, row))
        self.config.main_task_conditions = list(data.get("main_task_conditions", []))
        self._update_takeoff_from_actions()
        self.grid_widget.refresh()
        self._path_chip.setText("已加载")
        self.status_label.setText(f"方案已加载: {path}")

    # ==========================================================
    # 遥测回调
    # ==========================================================

    def _on_position(self, x, y, z):
        """
        遥测位置更新回调。

        将 MAVROS NED 坐标转换为网格坐标：
        1. 减去起飞点物理坐标得到偏移量
        2. 通过 -init_yaw 旋转到网格坐标系
        3. 转换为网格浮点坐标
        """
        origin_col = self.config.takeoff_col
        origin_row = self.config.takeoff_row
        cs = self.config.cell_size
        origin_gx = (self.config.cols - 1 - origin_col) * cs
        origin_gy = origin_row * cs
        yaw = getattr(self, '_init_yaw', 0.0)
        dx = x - origin_gx
        dy = y - origin_gy
        gx = dx * math.cos(-yaw) - dy * math.sin(-yaw)
        gy = dx * math.sin(-yaw) + dy * math.cos(-yaw)
        col_f = (self.config.cols - 1) - gx / cs
        row_f = gy / cs
        col_f = max(-0.5, min(self.config.cols - 0.5, col_f))
        row_f = max(-0.5, min(self.config.rows - 0.5, row_f))
        label = f"({x:.1f},{y:.1f},{z:.1f})"
        self.grid_widget.update_drone_telemetry(col_f, row_f, label)
        pos_text = f"X={x:.2f}  Y={y:.2f}  Z={z:.2f}"
        self.data_table.setItem(2, 1, QTableWidgetItem(pos_text))
        self._telem_alive = True
        self._conn_dot.setStyleSheet(f"color:#2E7D32; font-size:10px;")
        self._conn_dot.setToolTip("遥测已连接")

        # 更新仪表盘
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.update_telemetry_status(True)
            self.dashboard_widget.update_position(x, y, z)

    def _on_status(self, status):
        """遥测飞行状态回调。更新数据表和状态芯片。"""
        armed = "已解锁" if status.get("armed") else "未解锁"
        mode = status.get('mode', '?')
        self.data_table.setItem(0, 1, QTableWidgetItem(f"{armed}  mode={mode}"))
        if status.get("armed"):
            self._path_chip.setText("遥测: 已解锁")
            self._path_chip.setStatus("warning")
        self._telem_alive = True
        self._conn_dot.setStyleSheet(f"color:#2E7D32; font-size:10px;")
        self._conn_dot.setToolTip("遥测已连接")

        # 更新仪表盘
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.update_telemetry_status(True)

    def _on_node_status(self, bitmask):
        """
        遥测节点状态回调。

        bitmask 各位含义：
        bit0=MAVROS, bit1=SLAM, bit2=相机, bit3=规划器, bit4=定位融合, bit5=硬件驱动
        """
        for i in range(6):
            alive = bool(bitmask & (1 << i))
            status = "运行中" if alive else "已停止"
            item = self.node_table.item(i, 1)
            if item:
                item.setText(status)
                if alive:
                    item.setForeground(QColor("#2E7D32"))
                else:
                    item.setForeground(QColor(c.on_surface_variant))
        self._telem_alive = True

    def _heartbeat_tick(self):
        """定时发送 MAVLink 心跳（每秒一次）。"""
        self.telemetry.send_heartbeat()

    def closeEvent(self, event):
        """窗口关闭：保存分割器状态、停止遥测、清除无人机标记。"""
        settings = QSettings("MissionGrid", "MissionGrid")
        settings.setValue("splitter_sizes", self._splitter.saveState())
        self.telemetry.stop()
        self.grid_widget.clear_drone_display()
        event.accept()
