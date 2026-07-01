"""
网格可视化组件模块
==================

基于 QGraphicsView 实现的 7×9 网格可视化编辑器。

本模块包含：
- CellItem: 单个格子的图形项（支持悬停高亮、Tooltip）
- GridWidget: 网格视图主组件（支持四种编辑模式、路径/无人机渲染）

依赖关系：
    models ← 本模块（GridConfig, CellAction, COL_LABELS, ROW_LABELS）
    material_theme ← 本模块（COLORS 颜色常量）
    本模块 → main_window（被 MainWindow 持有和操作）

编辑模式（由 MainWindow 控制切换）：
    1. 动作编辑模式（默认）：左键打开动作编辑弹窗，右键切换禁飞区
    2. 手动航线模式：左键按顺序添加航点，右键移除航点
    3. 主线任务编辑：在 MainTaskEditorDialog 中操作
    4. 模拟飞行模式：可视化无人机沿路径飞行

渲染层级 (zValue)：
    0: 格子底色
    2: 格子动作标签文字
    4: 航迹/路径连线
    5: 路径航点编号
    9: 无人机光晕
    10: 无人机红点 / 航点编号
    11: 无人机坐标标签

坐标映射：
    网格 (col, row) → 场景像素 (x, y):
        x = MARGIN + col * CELL_PX + CELL_PX / 2
        y = MARGIN + (rows - 1 - row) * CELL_PX + CELL_PX / 2
    注意 Y 轴翻转：row=0 (B1) 在底部，row=6 (B7) 在顶部。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from .material_theme import COLORS as c
from .models import (
    CELL_STATE_CLEAR,
    CELL_STATE_KNOWN_NO_FLY,
    CELL_STATE_OBSTACLE,
    CELL_STATE_UNKNOWN_NO_FLY,
    CellAction,
    GridConfig,
    COL_LABELS,
    ROW_LABELS,
)


# ============================================================
# 布局常量
# ============================================================

CELL_PX = 64   # 每个格子的像素尺寸
MARGIN = 48     # 网格边缘留白（用于放置行列标签）
CORNER_R = 10   # 格子圆角半径（预留）


# ============================================================
# CellItem - 单个格子图形项
# ============================================================

class CellItem(QGraphicsRectItem):
    """
    网格中的单个格子图形项。

    功能：
    - 根据格子状态显示不同底色（起飞/禁飞/主线/动作/空）
    - 悬停时高亮边框 + 加深底色
    - 悬停时显示 Tooltip（格子名、动作、禁飞/主线状态）
    """

    def __init__(self, col: int, row: int, rect: QRectF, config: GridConfig = None, parent=None):
        super().__init__(rect, parent)
        self.col = col
        self.row = row
        self._config = config     # 用于 Tooltip 构建
        self.setAcceptHoverEvents(True)
        self.setZValue(0)
        self._hover = False
        self._base_color = QColor(c.surface_container_lowest)

    def setBaseColor(self, color: QColor):
        """设置格子底色（由 GridWidget._update_cell_color 调用）。"""
        self._base_color = color
        self._updateBrush()

    def _updateBrush(self):
        """根据悬停状态更新画刷颜色。悬停时增加 30 点透明度。"""
        if self._hover:
            hover_color = QColor(self._base_color)
            hover_color.setAlpha(min(255, hover_color.alpha() + 30))
            self.setBrush(QBrush(hover_color))
        else:
            self.setBrush(QBrush(self._base_color))

    def hoverEnterEvent(self, event):
        """鼠标进入：高亮边框 + 显示 Tooltip。"""
        self._hover = True
        self._updateBrush()
        self.setPen(QPen(QColor(c.primary), 2))
        self.setToolTip(self._build_tooltip())
        super().hoverEnterEvent(event)

    def _build_tooltip(self) -> str:
        """构建 Tooltip 文本：格子名 | 状态 | 动作列表。"""
        config = self._config
        if not config:
            return ""
        label = config.cell_label(self.col, self.row)
        parts = [label]
        if config.is_known_no_fly(self.col, self.row):
            parts.append("已知禁飞区")
        elif config.is_discovered_unknown_no_fly(self.col, self.row):
            parts.append("未知禁飞区（已发现）")
        elif config.is_unknown_no_fly(self.col, self.row):
            parts.append("未知禁飞区（未发现）")
        elif config.is_discovered_obstacle(self.col, self.row):
            parts.append("障碍物（已发现）")
        elif config.is_obstacle(self.col, self.row):
            parts.append("障碍物（未发现）")
        actions = config.actions.get((self.col, self.row), [])
        for a in actions:
            parts.append(a.action_type)
        if (self.col, self.row) in config.main_task_cells:
            parts.append("[主线]")
        return " | ".join(parts)

    def hoverLeaveEvent(self, event):
        """鼠标离开：恢复默认边框和底色。"""
        self._hover = False
        self._updateBrush()
        self.setPen(QPen(QColor(c.outline_variant), 1))
        super().hoverLeaveEvent(event)


# ============================================================
# GridWidget - 网格视图主组件
# ============================================================

class GridWidget(QGraphicsView):
    """
    7×9 网格可视化编辑器。

    信号：
        cell_action_changed(col, row): 左键点击格子（动作编辑模式）
        cell_state_changed(col, row, state):  右键按当前标记模式修改格子状态
        waypoint_added(col, row):      手动模式下添加/移除航点

    内部数据：
        _cells: {(col, row): CellItem} — 格子图形项映射
        _labels: {(col, row): QGraphicsSimpleTextItem} — 格子动作标签
        _draw_path_items: [QGraphicsItem] — 规划路径叠加层（可清除）
        _drone_items: [QGraphicsItem] — 无人机标记叠加层（可清除）
    """

    # 信号定义
    cell_action_changed = Signal(int, int)
    cell_state_changed = Signal(int, int, str)
    waypoint_added = Signal(int, int)

    def __init__(self, config: GridConfig, parent=None):
        super().__init__(parent)
        self.config = config

        # 场景初始化
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        # 内部状态
        self._cells: dict[tuple[int, int], CellItem] = {}
        self._labels: dict[tuple[int, int], QGraphicsSimpleTextItem] = {}
        self._manual_mode = False     # 手动航线编辑模式
        self._cell_mark_mode = CELL_STATE_KNOWN_NO_FLY
        self._path_items: list = []   # 路径叠加层
        self._drone_items: list = []  # 无人机标记叠加层

        # 构建网格并设置最小尺寸
        self._build_grid()
        self._update_all_colors()
        self.setMinimumSize(
            (config.cols + 1) * CELL_PX + MARGIN * 2,
            (config.rows + 1) * CELL_PX + MARGIN * 2,
        )
        self.setStyleSheet(f"background-color: {c.surface}; border: none;")

    # ----------------------------------------------------------
    # 网格构建
    # ----------------------------------------------------------

    def _build_grid(self):
        """构建完整的网格场景：行列标签 + 格子 + 动作标签。"""
        self.scene.clear()
        self._cells.clear()
        self._labels.clear()
        header_font = QFont("Segoe UI", 9, QFont.DemiBold)
        cell_font = QFont("Segoe UI", 7)

        # 列标签 (A1~A9)
        for col in range(self.config.cols):
            x = MARGIN + col * CELL_PX
            label = self.scene.addSimpleText(COL_LABELS[col], header_font)
            label.setBrush(QBrush(QColor(c.on_surface_variant)))
            label.setPos(x + CELL_PX / 2 - 10, 8)

        # 行标签 (B1~B7)
        for row in range(self.config.rows):
            y = MARGIN + (self.config.rows - 1 - row) * CELL_PX
            label = self.scene.addSimpleText(ROW_LABELS[row], header_font)
            label.setBrush(QBrush(QColor(c.on_surface_variant)))
            label.setPos(8, y + CELL_PX / 2 - 10)

        # 格子 + 动作标签
        for col in range(self.config.cols):
            for row in range(self.config.rows):
                x = MARGIN + col * CELL_PX
                y = MARGIN + (self.config.rows - 1 - row) * CELL_PX
                rect = QRectF(x + 1, y + 1, CELL_PX - 2, CELL_PX - 2)
                item = CellItem(col, row, rect, config=self.config)
                item.setPen(QPen(QColor(c.outline_variant), 1))
                item.setBrush(QBrush(QColor(c.surface_container_lowest)))
                self.scene.addItem(item)
                self._cells[(col, row)] = item

                label = self.scene.addSimpleText("", cell_font)
                label.setBrush(QBrush(QColor(c.on_surface_variant)))
                label.setPos(x + 6, y + CELL_PX - 20)
                label.setZValue(2)
                self._labels[(col, row)] = label

        self._draw_path_items = []

    # ----------------------------------------------------------
    # 颜色更新
    # ----------------------------------------------------------

    def _update_all_colors(self):
        """刷新所有格子的颜色和标签。"""
        for (col, row) in self._cells:
            self._update_cell_color(col, row)

    def _update_cell_color(self, col: int, row: int):
        """
        根据格子状态设置颜色优先级：
        1. 起飞点 → 绿色
        2. 已知禁飞区 → 深红
        3. 已发现未知禁飞区 → 深橙
        4. 未发现未知禁飞区 → 橙黄
        5. 已发现障碍物 → 深青色
        6. 未发现障碍物 → 淡蓝色
        7. 主线任务 → 橙色半透明
        8. 有动作 → 紫色半透明
        9. 空白 → 默认表面色
        """
        item = self._cells.get((col, row))
        if not item:
            return
        if col == self.config.takeoff_col and row == self.config.takeoff_row:
            color = QColor("#2E7D32")
            color.setAlpha(200)
        elif self.config.is_known_no_fly(col, row):
            color = QColor(c.error)
            color.setAlpha(130)
        elif self.config.is_discovered_unknown_no_fly(col, row):
            color = QColor("#F4511E")
            color.setAlpha(170)
        elif self.config.is_unknown_no_fly(col, row):
            color = QColor("#FFB300")
            color.setAlpha(125)
        elif self.config.is_discovered_obstacle(col, row):
            color = QColor("#00796B")
            color.setAlpha(170)
        elif self.config.is_obstacle(col, row):
            color = QColor("#29B6F6")
            color.setAlpha(125)
        elif (col, row) in self.config.main_task_cells:
            color = QColor("#E65100")
            color.setAlpha(160)
        elif self.config.has_action(col, row):
            color = QColor(c.primary)
            color.setAlpha(140)
        else:
            color = QColor(c.surface_container_lowest)
        item.setBaseColor(color)

        # 更新动作标签文字
        label = self._labels.get((col, row))
        if label:
            actions = self.config.actions.get((col, row), [])
            if actions:
                parts = []
                for a in actions:
                    if a.triggers != ["always"]:
                        t_short = "/".join(t[:2] for t in a.triggers)
                        parts.append(f"[{t_short}]{a.action_type}")
                    else:
                        parts.append(a.action_type)
                label.setText(", ".join(parts))
            else:
                label.setText("")

    # ----------------------------------------------------------
    # 鼠标事件
    # ----------------------------------------------------------

    def mousePressEvent(self, event):
        """
        鼠标点击处理。

        动作编辑模式：
            左键 → 发射 cell_action_changed 信号（打开编辑弹窗）
            右键 → 切换禁飞区
        手动航线模式：
            左键 → 添加航点
            右键 → 移除最近的同位置航点
        """
        pos = self.mapToScene(event.pos())
        col = int((pos.x() - MARGIN) / CELL_PX)
        row = self.config.rows - 1 - int((pos.y() - MARGIN) / CELL_PX)
        if not (0 <= col < self.config.cols and 0 <= row < self.config.rows):
            return super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            if self._manual_mode:
                if not self.config.is_blocked_preflight(col, row):
                    self.config.custom_waypoints.append((col, row))
                    self.waypoint_added.emit(col, row)
                    self.refresh()
            else:
                self.cell_action_changed.emit(col, row)
        elif event.button() == Qt.RightButton:
            if self._manual_mode:
                self.config.custom_waypoints = [
                    w for w in self.config.custom_waypoints if w != (col, row)
                ]
                self.refresh()
                self.waypoint_added.emit(col, row)
            else:
                current = self.config.get_static_cell_state(col, row)
                next_state = CELL_STATE_CLEAR if current == self._cell_mark_mode else self._cell_mark_mode
                self.config.set_cell_state(col, row, next_state)
                self._update_cell_color(col, row)
                self.cell_state_changed.emit(col, row, next_state)
        super().mousePressEvent(event)

    # ----------------------------------------------------------
    # 公共接口
    # ----------------------------------------------------------

    def refresh(self):
        """刷新所有格子的颜色和标签显示。"""
        self._update_all_colors()

    def clear_overlay(self):
        """清除规划路径叠加层。"""
        for item in self._draw_path_items:
            self.scene.removeItem(item)
        self._draw_path_items.clear()
        self._update_all_colors()

    def set_manual_mode(self, enabled: bool):
        """切换手动航线编辑模式。"""
        self._manual_mode = enabled

    def set_cell_mark_mode(self, mode: str):
        """设置右键标记模式。"""
        self._cell_mark_mode = mode

    # ----------------------------------------------------------
    # 无人机标记渲染（遥测 + 模拟飞行）
    # ----------------------------------------------------------

    def _cell_to_scene(self, col: float, row: float) -> QPointF:
        """网格坐标 → 场景像素坐标（中心点）。"""
        x = MARGIN + col * CELL_PX + CELL_PX / 2
        y = MARGIN + (self.config.rows - 1 - row) * CELL_PX + CELL_PX / 2
        return QPointF(x, y)

    def set_drone_position(self, col: float, row: float, trail: list = None):
        """
        设置无人机位置（模拟飞行用）。

        清除旧的无人机标记，绘制新的红点 + 可选航迹线。
        航迹线使用 primary 色实线。
        """
        for item in self._drone_items:
            self.scene.removeItem(item)
        self._drone_items.clear()
        if trail and len(trail) >= 2:
            pen = QPen(QColor(c.primary), 2)
            pen.setCapStyle(Qt.RoundCap)
            for i in range(len(trail) - 1):
                p1 = self._cell_to_scene(*trail[i])
                p2 = self._cell_to_scene(*trail[i + 1])
                line = self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
                line.setZValue(4)
                self._drone_items.append(line)
        self._draw_drone_marker(col, row)

    def _draw_drone_marker(self, col: float, row: float, label: str = ""):
        """
        绘制无人机标记：红色光晕 + 红色实心圆 + 可选坐标标签。

        参数:
            col, row: 网格坐标（支持浮点数，用于遥测连续位置）
            label: 可选的文字标签（如坐标信息）
        """
        pos = self._cell_to_scene(col, row)
        # 光晕（较大、半透明）
        glow = self.scene.addEllipse(
            pos.x() - 14, pos.y() - 14, 28, 28,
            QPen(Qt.NoPen), QBrush(QColor(c.error_container)),
        )
        glow.setZValue(9)
        self._drone_items.append(glow)
        # 实心圆点
        dot = self.scene.addEllipse(
            pos.x() - 8, pos.y() - 8, 16, 16,
            QPen(QColor(c.error), 2), QBrush(QColor(c.error)),
        )
        dot.setZValue(10)
        self._drone_items.append(dot)
        # 坐标标签
        if label:
            lbl = self.scene.addSimpleText(label, QFont("Segoe UI", 8, QFont.Bold))
            lbl.setBrush(QBrush(QColor(c.error)))
            lbl.setZValue(11)
            lbl.setPos(pos.x() + 14, pos.y() - 18)
            self._drone_items.append(lbl)

    def update_drone_telemetry(self, col: float, row: float, label: str = ""):
        """
        更新遥测无人机位置（实时模式）。

        与 set_drone_position 不同，此方法不绘制航迹线，
        仅更新红点标记和坐标标签，不影响路径叠加层。
        """
        for item in self._drone_items:
            self.scene.removeItem(item)
        self._drone_items.clear()
        self._draw_drone_marker(col, row, label)

    def clear_drone_display(self):
        """清除所有无人机标记。"""
        for item in self._drone_items:
            self.scene.removeItem(item)
        self._drone_items.clear()

    # ----------------------------------------------------------
    # 路径渲染
    # ----------------------------------------------------------

    def draw_path(self, config: GridConfig, path: list[tuple[int, int]]):
        """
        绘制自动规划的飞行路径。

        路径用虚线连接，中间航点显示序号。
        首尾航点不显示序号（分别是起飞点和终点）。
        """
        for item in self._draw_path_items:
            self.scene.removeItem(item)
        self._draw_path_items.clear()
        if len(path) < 2:
            return
        pen = QPen(QColor(c.tertiary), 3, Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        pen.setDashPattern([8, 4])
        for i in range(len(path) - 1):
            c1, r1 = path[i]
            c2, r2 = path[i + 1]
            x1 = MARGIN + c1 * CELL_PX + CELL_PX / 2
            y1 = MARGIN + (config.rows - 1 - r1) * CELL_PX + CELL_PX / 2
            x2 = MARGIN + c2 * CELL_PX + CELL_PX / 2
            y2 = MARGIN + (config.rows - 1 - r2) * CELL_PX + CELL_PX / 2
            line = self.scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(5)
            self._draw_path_items.append(line)
        num_font = QFont("Segoe UI", 9, QFont.Bold)
        for i, (col, row) in enumerate(path):
            if i == 0 or i == len(path) - 1:
                continue
            x = MARGIN + col * CELL_PX + CELL_PX / 2 - 5
            y = MARGIN + (config.rows - 1 - row) * CELL_PX + 2
            num_label = self.scene.addSimpleText(str(i), num_font)
            num_label.setBrush(QBrush(QColor(c.tertiary)))
            num_label.setPos(x, y)
            num_label.setZValue(10)
            self._draw_path_items.append(num_label)

    def draw_waypoint_numbers(self):
        """
        绘制手动航点序号和连线。

        航点用 primary 色实线连接，每个航点显示从 1 开始的序号。
        """
        for item in self._draw_path_items:
            self.scene.removeItem(item)
        self._draw_path_items.clear()
        if not self.config.custom_waypoints:
            return
        pen = QPen(QColor(c.primary), 3, Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        for i in range(len(self.config.custom_waypoints) - 1):
            c1, r1 = self.config.custom_waypoints[i]
            c2, r2 = self.config.custom_waypoints[i + 1]
            x1 = MARGIN + c1 * CELL_PX + CELL_PX / 2
            y1 = MARGIN + (self.config.rows - 1 - r1) * CELL_PX + CELL_PX / 2
            x2 = MARGIN + c2 * CELL_PX + CELL_PX / 2
            y2 = MARGIN + (self.config.rows - 1 - r2) * CELL_PX + CELL_PX / 2
            line = self.scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(5)
            self._draw_path_items.append(line)
        num_font = QFont("Segoe UI", 10, QFont.Bold)
        for i, (col, row) in enumerate(self.config.custom_waypoints):
            x = MARGIN + col * CELL_PX + CELL_PX / 2 - 6
            y = MARGIN + (self.config.rows - 1 - row) * CELL_PX + 4
            num_label = self.scene.addSimpleText(str(i + 1), num_font)
            num_label.setBrush(QBrush(QColor(c.primary)))
            num_label.setPos(x, y)
            num_label.setZValue(10)
            self._draw_path_items.append(num_label)
