"""
动作编辑器模块
==============

格子动作编辑对话框，用于配置单个格子上的一组动作及其触发条件。

本模块包含：
- ACTION_TYPES: 支持的 10 种动作类型定义（类型ID、显示名、默认参数）
- ACTION_TYPE_MAP / TRIGGER_LABEL_MAP: 快速查找字典
- ActionEditorDialog: 动作编辑弹窗（QDialog）

依赖关系：
    models ← 本模块（CellAction, GridConfig, TRIGGER_CONDITIONS）
    material_theme ← 本模块（COLORS 颜色常量）
    material_widgets ← 本模块（MChip 状态标签）
    本模块 → main_window（被 MainWindow._on_cell_click 调用）
    本模块 → main_task_editor（ACTION_TYPE_MAP 被引用）

支持的动作类型：
    takeoff     起飞          params: {altitude}
    photo       拍照保存      params: {save_dir, prefix}
    qr_scan     识别二维码    params: {save_dir}
    yolo_detect YOLO动物识别  params: {model_path, save_dir, confidence}
    h_land      识别H点降落   params: {}
    land        直接降落      params: {}
    set_yaw     调整航向      params: {yaw_deg}
    buzzer      蜂鸣器        params: {audio_id}
    servo       舵机          params: {servo_id, open_servo}
    laser       激光          params: {laser_on, duration_sec}
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .material_theme import COLORS as c
from .material_widgets import MChip
from .models import CellAction, GridConfig, TRIGGER_CONDITIONS


# ============================================================
# 动作类型注册表
# ============================================================

# 格式: (类型ID, 显示名称, 默认参数字典)
ACTION_TYPES = [
    ("takeoff", "起飞", {"altitude": 1.2}),
    ("photo", "拍照保存", {"save_dir": "/home/orangepi/Desktop/captures", "prefix": "photo"}),
    ("qr_scan", "识别二维码", {"save_dir": "/home/orangepi/Desktop/qr_results"}),
    ("yolo_detect", "YOLO动物识别", {
        "model_path": "/home/orangepi/ctrl_ws/src/competition_pkg/scripts/animal82.onnx",
        "save_dir": "/home/orangepi/Desktop/yolo_results",
        "confidence": 0.6,
    }),
    ("h_land", "识别H点降落", {}),
    ("land", "直接降落", {}),
    ("set_yaw", "调整航向", {"yaw_deg": 90.0}),
    ("buzzer", "蜂鸣器", {"audio_id": 1}),
    ("servo", "舵机", {"servo_id": 1, "open_servo": True}),
    ("laser", "激光", {"laser_on": True, "duration_sec": 0.5}),
]

# 类型ID → (显示名, 默认参数) 快速查找
ACTION_TYPE_MAP = {t[0]: (t[1], t[2]) for t in ACTION_TYPES}
# 触发条件ID → 显示名 快速查找
TRIGGER_LABEL_MAP = {t[0]: t[1] for t in TRIGGER_CONDITIONS}


# ============================================================
# ActionEditorDialog - 动作编辑弹窗
# ============================================================

class ActionEditorDialog(QDialog):
    """
    格子动作编辑对话框。

    布局结构：
    - 标题标签（显示格子名称如 "A3B5"）
    - 动作列表（QListWidget，可多选）
    - 添加/删除按钮行
    - 触发条件复选框组（每次经过/首次/最后/主线完成后）
    - 动作参数编辑区（根据参数类型自动选择控件）
    - 确定/取消按钮

    编辑流程：
    1. 构造时复制当前格子的动作列表（不直接修改原数据）
    2. 用户在弹窗中编辑动作、触发条件、参数
    3. 点击确定时调用 config.set_action() 写回数据
    """

    def __init__(self, col: int, row: int, config: GridConfig, parent=None):
        super().__init__(parent)
        self.col = col
        self.row = row
        self.config = config
        # 深拷贝当前格子的动作列表（避免直接修改原数据）
        self.result_actions: List[CellAction] = [
            CellAction(action_type=a.action_type, params=dict(a.params), triggers=list(a.triggers))
            for a in config.actions.get((col, row), [])
        ]
        self.setWindowTitle(f"编辑动作 — {config.cell_label(col, row)}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(500)
        self._build_ui()
        self._refresh_list()

    # ----------------------------------------------------------
    # UI 构建
    # ----------------------------------------------------------

    def _build_ui(self):
        """构建完整的对话框布局。"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        header = QLabel(f"格子: {self.config.cell_label(self.col, self.row)}")
        header.setStyleSheet(f"font-size:18px; font-weight:700; color:{c.primary};")
        layout.addWidget(header)

        # 动作列表
        list_label = QLabel("动作列表")
        list_label.setStyleSheet(f"font-size:12px; font-weight:600; color:{c.on_surface_variant};")
        layout.addWidget(list_label)
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.list_widget)

        # 添加/删除按钮行
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.add_combo = QComboBox()
        for type_id, name, _ in ACTION_TYPES:
            self.add_combo.addItem(name, type_id)
        add_row.addWidget(self.add_combo, 1)
        add_btn = QPushButton("添加动作")
        add_btn.clicked.connect(self._add_action)
        add_row.addWidget(add_btn)
        del_btn = QPushButton("删除")
        del_btn.setProperty("cssClass", "danger")
        del_btn.clicked.connect(self._del_action)
        add_row.addWidget(del_btn)
        layout.addLayout(add_row)

        # 触发条件复选框组
        self.trigger_group = QGroupBox("触发条件")
        trigger_layout = QVBoxLayout(self.trigger_group)
        trigger_layout.setSpacing(4)
        self.trigger_checks: Dict[str, QCheckBox] = {}
        for cond_id, cond_name in TRIGGER_CONDITIONS:
            cb = QCheckBox(cond_name)
            self.trigger_checks[cond_id] = cb
            trigger_layout.addWidget(cb)
        layout.addWidget(self.trigger_group)

        # 动作参数编辑区（动态生成）
        self.param_group = QGroupBox("动作参数")
        self.param_layout = QFormLayout(self.param_group)
        layout.addWidget(self.param_group)

        # 确定/取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ----------------------------------------------------------
    # 列表操作
    # ----------------------------------------------------------

    def _refresh_list(self):
        """刷新动作列表显示（格式: "[触发条件] 动作名"）。"""
        self.list_widget.clear()
        for action in self.result_actions:
            name = ACTION_TYPE_MAP.get(action.action_type, (action.action_type, {}))[0]
            triggers = ", ".join(TRIGGER_LABEL_MAP.get(t, t) for t in action.triggers)
            self.list_widget.addItem(f"[{triggers}] {name}")
        if self.result_actions:
            self.list_widget.setCurrentRow(0)

    def _on_select(self, row: int):
        """
        列表选中项变化时：
        1. 保存当前项的触发条件和参数
        2. 清空参数编辑区
        3. 加载新选中项的触发条件和参数
        """
        self._save_current_triggers()
        self._save_current_params()
        while self.param_layout.rowCount():
            self.param_layout.removeRow(0)
        for cb in self.trigger_checks.values():
            cb.setChecked(False)
        if row < 0 or row >= len(self.result_actions):
            return
        action = self.result_actions[row]
        # 恢复触发条件复选框
        for t in action.triggers:
            if t in self.trigger_checks:
                self.trigger_checks[t].setChecked(True)
        # 动态生成参数编辑控件
        self._current_param_widgets = {}
        for key, value in action.params.items():
            if isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
            elif isinstance(value, int):
                widget = QSpinBox()
                widget.setRange(-999999, 999999)
                widget.setValue(value)
            elif isinstance(value, float):
                widget = QDoubleSpinBox()
                widget.setRange(-999999, 999999)
                widget.setDecimals(4)
                widget.setValue(value)
            else:
                widget = QLineEdit(str(value))
            self.param_layout.addRow(key, widget)
            self._current_param_widgets[key] = (widget, type(value))

    def _add_action(self):
        """从下拉框添加新动作到列表。"""
        type_id = self.add_combo.currentData()
        name, default_params = ACTION_TYPE_MAP[type_id]
        self.result_actions.append(CellAction(action_type=type_id, params=dict(default_params), triggers=["always"]))
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self.result_actions) - 1)

    def _del_action(self):
        """删除当前选中的动作。"""
        row = self.list_widget.currentRow()
        if row >= 0:
            self.result_actions.pop(row)
            self._refresh_list()

    # ----------------------------------------------------------
    # 数据保存
    # ----------------------------------------------------------

    def _save_current_triggers(self):
        """保存当前选中动作的触发条件。"""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.result_actions):
            return
        triggers = [cid for cid, cb in self.trigger_checks.items() if cb.isChecked()]
        if not triggers:
            triggers = ["always"]
        self.result_actions[row].triggers = triggers

    def _save_current_params(self):
        """保存当前选中动作的参数（从动态控件中读取值）。"""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.result_actions):
            return
        action = self.result_actions[row]
        if not hasattr(self, '_current_param_widgets'):
            return
        for key, (widget, orig_type) in self._current_param_widgets.items():
            if isinstance(widget, QCheckBox):
                action.params[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                action.params[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                action.params[key] = widget.value()
            else:
                text = widget.text()
                if orig_type == int:
                    action.params[key] = int(text) if text else 0
                elif orig_type == float:
                    action.params[key] = float(text) if text else 0.0
                else:
                    action.params[key] = text

    def _on_accept(self):
        """确定按钮：保存所有数据并写回 GridConfig。"""
        self._save_current_triggers()
        self._save_current_params()
        self.config.set_action(self.col, self.row, self.result_actions)
        self.accept()
