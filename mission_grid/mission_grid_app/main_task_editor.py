"""
主线任务编辑器模块
==================

用于配置主线任务的格子选择和全局完成条件的对话框。

本模块包含：
- MainTaskEditorDialog: 主线任务编辑弹窗（QDialog）

依赖关系：
    models ← 本模块（GridConfig, MAIN_TASK_GLOBAL_CONDITIONS）
    material_theme ← 本模块（COLORS 颜色常量）
    material_widgets ← 本模块（MChip 状态标签）
    action_editor ← 本模块（ACTION_TYPE_MAP 用于显示动作名称）
    本模块 → main_window（被 MainWindow._open_main_task_editor 调用）

主线任务机制：
    1. 用户选择哪些格子属于"主线任务"
    2. 用户选择全局完成条件（如：所有动物检测完成、所有二维码扫描完成）
    3. 当所有主线格子被访问且所有全局条件满足时，main_done 标志置 True
    4. 触发条件为 "main_task_done" 的动作在此时才会执行
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from .material_theme import COLORS as c
from .material_widgets import MChip
from .models import GridConfig, MAIN_TASK_GLOBAL_CONDITIONS
from .action_editor import ACTION_TYPE_MAP


class MainTaskEditorDialog(QDialog):
    """
    主线任务编辑对话框。

    布局结构：
    - 标题 "主线任务设置"
    - 滚动区域：
      - 主线任务格子复选框组（列出所有有动作的格子）
      - 全局完成条件复选框组
    - 摘要芯片（实时显示已选格子数和条件数）
    - 确定/取消按钮
    """

    def __init__(self, config: GridConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("编辑主线任务")
        self.setMinimumWidth(460)
        self.setMinimumHeight(450)
        self._build_ui()

    def _build_ui(self):
        """构建对话框布局。"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        header = QLabel("主线任务设置")
        header.setStyleSheet(f"font-size:18px; font-weight:700; color:{c.primary};")
        layout.addWidget(header)

        # 滚动区域（内容可能超出对话框高度）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        # 主线任务格子选择
        cells_group = QGroupBox("主线任务格子")
        cells_layout = QVBoxLayout(cells_group)
        self._cell_checks: dict[tuple[int, int], QCheckBox] = {}
        action_cells = self.config.action_cells()
        if not action_cells:
            hint = QLabel("暂无动作格子，请先在网格上设置动作")
            hint.setStyleSheet(f"color:{c.on_surface_variant}; font-size:12px;")
            cells_layout.addWidget(hint)
        else:
            for col, row in action_cells:
                label = self.config.cell_label(col, row)
                actions = self.config.actions.get((col, row), [])
                action_names = [ACTION_TYPE_MAP.get(a.action_type, (a.action_type, {}))[0] for a in actions]
                desc = ", ".join(action_names)
                cb = QCheckBox(f"{label}  —  {desc}")
                cb.setChecked((col, row) in self.config.main_task_cells)
                self._cell_checks[(col, row)] = cb
                cells_layout.addWidget(cb)
        scroll_layout.addWidget(cells_group)

        # 全局完成条件选择
        global_group = QGroupBox("全局完成条件")
        global_layout = QVBoxLayout(global_group)
        self._global_checks: dict[str, QCheckBox] = {}
        for cond_id, cond_name in MAIN_TASK_GLOBAL_CONDITIONS:
            cb = QCheckBox(cond_name)
            cb.setChecked(cond_id in self.config.main_task_conditions)
            self._global_checks[cond_id] = cb
            global_layout.addWidget(cb)
        hint = QLabel("满足所有勾选的全局条件时，触发\"主线完成后\"")
        hint.setStyleSheet(f"color:{c.on_surface_variant}; font-size:11px;")
        global_layout.addWidget(hint)
        scroll_layout.addWidget(global_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # 摘要芯片（实时更新）
        self._summary_chip = MChip("")
        self._update_summary()
        layout.addWidget(self._summary_chip)

        # 确定/取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 连接信号：复选框变化时更新摘要
        for cb in self._cell_checks.values():
            cb.toggled.connect(self._update_summary)
        for cb in self._global_checks.values():
            cb.toggled.connect(self._update_summary)

    def _update_summary(self):
        """更新摘要芯片文本（如 "已选 3 个格子  |  2 个全局条件"）。"""
        n_cells = sum(1 for cb in self._cell_checks.values() if cb.isChecked())
        n_conds = sum(1 for cb in self._global_checks.values() if cb.isChecked())
        parts = [f"已选 {n_cells} 个格子"]
        if n_conds:
            parts.append(f"{n_conds} 个全局条件")
        self._summary_chip.label.setText("  |  ".join(parts))

    def _on_accept(self):
        """确定按钮：将选择结果写回 GridConfig。"""
        self.config.main_task_cells = {
            (col, row) for (col, row), cb in self._cell_checks.items() if cb.isChecked()
        }
        self.config.main_task_conditions = [
            cond_id for cond_id, cb in self._global_checks.items() if cb.isChecked()
        ]
        self.accept()
