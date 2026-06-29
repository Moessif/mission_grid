from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QStyledItemDelegate,
)

from .catalog import template_map, templates_by_category
from .contest_specs import format_contest_overview
from .exporter import export_mission_bundle, validate_mission_plan
from .models import MissionPlan, MissionTask


QUICK_PLANS = {
    "空白任务流": [],
    "坐标监控": ["monitor_position"],
    "二维码巡航": ["env_start", "wait_mapping", "patrol_area", "detect_qr", "capture_qr", "estimate_qr_coord", "return_home", "land"],
    "货架盘点": ["env_start", "wait_mapping", "inventory_route", "inventory_scan_qr", "inventory_laser_hint", "return_home", "land"],
    "按坐标送货": ["env_start", "wait_mapping", "delivery_coordinates", "delivery_release_cargo", "return_home", "land"],
    "野生动物巡查": ["env_start", "wait_mapping", "wildlife_grid_patrol", "wildlife_detect_animals", "return_home", "land"],
    "识别并降落到目标": ["env_start", "wait_mapping", "takeoff", "detect_visual_marker", "estimate_visual_marker_coord", "land_on_marker"],
}


class WrappingTreeDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)
        text = index.data(Qt.DisplayRole) or ""
        if not text:
            return base

        parent = self.parent()
        column_width = parent.columnWidth(index.column()) if parent else option.rect.width()
        text_width = max(80, column_width - 24)

        metrics = option.fontMetrics
        rect = metrics.boundingRect(0, 0, text_width, 2000, Qt.TextWordWrap, str(text))
        height = max(base.height(), rect.height() + 18)
        return QSize(base.width(), height)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("无人机任务编辑器")
        self.resize(1560, 950)
        self._templates = template_map()
        self.param_editor = {}
        self._build_ui()
        self._apply_style()
        self._refresh_catalog()
        self._set_default_output_dir()
        self._refresh_preview()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        main_layout.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_catalog_panel())
        splitter.addWidget(self._build_mission_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([400, 500, 900])
        main_layout.addWidget(splitter, 1)

        main_layout.addWidget(self._build_footer_card())

    def _build_header(self):
        card = self._create_card("heroCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        badge = QLabel("无人机任务工作台")
        badge.setObjectName("heroBadge")
        top_row.addWidget(badge, 0, Qt.AlignLeft)
        top_row.addStretch(1)
        hint = QLabel("支持组合导出，不覆盖原机载脚本")
        hint.setObjectName("heroHint")
        top_row.addWidget(hint, 0, Qt.AlignRight)
        layout.addLayout(top_row)

        title = QLabel("更容易拼装的小任务流程")
        title.setObjectName("heroTitle")
        layout.addWidget(title)

        subtitle = QLabel("左侧挑任务，中间排流程，右侧改参数。也可以直接用快速模板起步，再微调。")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("heroSubtitle")
        layout.addWidget(subtitle)
        return card

    def _build_catalog_panel(self):
        card = self._create_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(self._build_section_header("基础任务库", "双击或选中后点“加入任务流”。"))

        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setObjectName("catalogTree")
        self.catalog_tree.setHeaderLabels(["任务", "说明"])
        self.catalog_tree.setWordWrap(True)
        self.catalog_tree.setTextElideMode(Qt.ElideNone)
        self.catalog_tree.setUniformRowHeights(False)
        self.catalog_tree.setItemDelegate(WrappingTreeDelegate(self.catalog_tree))
        header = self.catalog_tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.catalog_tree.setColumnWidth(0, 150)
        header.sectionResized.connect(lambda *_: self.catalog_tree.doItemsLayout())
        self.catalog_tree.itemDoubleClicked.connect(self._add_task_from_catalog)
        layout.addWidget(self.catalog_tree, 1)
        return card

    def _build_mission_panel(self):
        card = self._create_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(self._build_section_header("工作流编辑", "先选一个快速模板，或者自己从左侧一点点加。"))

        quick_row = QHBoxLayout()
        quick_label = QLabel("快速模板")
        quick_label.setObjectName("fieldLabel")
        quick_row.addWidget(quick_label)

        self.quick_plan_combo = QComboBox()
        self.quick_plan_combo.addItems(list(QUICK_PLANS.keys()))
        self.quick_plan_combo.setObjectName("quickCombo")
        quick_row.addWidget(self.quick_plan_combo, 1)

        apply_quick_btn = self._make_action_button("套用模板", "primary")
        apply_quick_btn.clicked.connect(self._apply_quick_plan)
        quick_row.addWidget(apply_quick_btn)
        layout.addLayout(quick_row)

        helper_row = QHBoxLayout()
        helper_row.setSpacing(10)
        helper_row.addWidget(self._make_helper_button("加入起飞", "takeoff"))
        helper_row.addWidget(self._make_helper_button("加入返航", "return_home"))
        helper_row.addWidget(self._make_helper_button("加入降落", "land"))
        helper_row.addWidget(self._make_helper_button("加入目标识别", "detect_visual_marker"))
        helper_row.addStretch(1)
        layout.addLayout(helper_row)

        self.mission_list = QListWidget()
        self.mission_list.setObjectName("missionList")
        self.mission_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mission_list.currentItemChanged.connect(self._on_task_selected)
        layout.addWidget(self.mission_list, 1)

        actions = QGridLayout()
        actions.setHorizontalSpacing(10)
        actions.setVerticalSpacing(10)

        self.add_btn = self._make_action_button("加入任务流", "primary")
        self.remove_btn = self._make_action_button("删除", "secondary")
        self.up_btn = self._make_action_button("上移", "secondary")
        self.down_btn = self._make_action_button("下移", "secondary")
        self.save_plan_btn = self._make_action_button("保存方案", "ghost")
        self.load_plan_btn = self._make_action_button("加载方案", "ghost")

        self.add_btn.clicked.connect(self._add_selected_catalog_task)
        self.remove_btn.clicked.connect(self._remove_task)
        self.up_btn.clicked.connect(self._move_task_up)
        self.down_btn.clicked.connect(self._move_task_down)
        self.save_plan_btn.clicked.connect(self._save_plan)
        self.load_plan_btn.clicked.connect(self._load_plan)

        actions.addWidget(self.add_btn, 0, 0)
        actions.addWidget(self.remove_btn, 0, 1)
        actions.addWidget(self.up_btn, 0, 2)
        actions.addWidget(self.down_btn, 0, 3)
        actions.addWidget(self.save_plan_btn, 1, 0, 1, 2)
        actions.addWidget(self.load_plan_btn, 1, 2, 1, 2)
        layout.addLayout(actions)
        return card

    def _build_detail_panel(self):
        card = self._create_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(self._build_section_header("参数与说明", "先选中中间任务，再在这里改参数。"))

        self.task_title = QLabel("任务参数")
        self.task_title.setObjectName("sectionTitle")
        layout.addWidget(self.task_title)

        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.setChildrenCollapsible(False)

        self.param_scroll = QScrollArea()
        self.param_scroll.setMinimumHeight(320)
        self.param_scroll.setWidgetResizable(True)
        self.param_form_widget = QWidget()
        self.param_form_widget.setObjectName("paramInner")
        self.param_form = QFormLayout(self.param_form_widget)
        self.param_form.setContentsMargins(8, 8, 8, 8)
        self.param_form.setHorizontalSpacing(18)
        self.param_form.setVerticalSpacing(10)
        self.param_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.param_scroll.setWidget(self.param_form_widget)
        detail_splitter.addWidget(self.param_scroll)

        self.detail_tabs = QTabWidget()
        detail_splitter.addWidget(self.detail_tabs)
        detail_splitter.setSizes([460, 360])
        layout.addWidget(detail_splitter, 1)

        preview_tab = self._build_editor_tab("当前导出 JSON 预览")
        self.preview_box = preview_tab["editor"]
        self.detail_tabs.addTab(preview_tab["widget"], "方案预览")

        validation_tab = self._build_editor_tab("当前任务流导出校验")
        self.validation_box = validation_tab["editor"]
        self.detail_tabs.addTab(validation_tab["widget"], "导出校验")

        contest_tab = self._build_editor_tab("比赛题目拆解说明")
        self.contest_box = contest_tab["editor"]
        self.contest_box.setPlainText(format_contest_overview())
        self.detail_tabs.addTab(contest_tab["widget"], "题目拆解")
        return card

    def _build_footer_card(self):
        card = self._create_card()
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        layout.addWidget(self._field_label("任务名称"), 0, 0)
        self.mission_name_edit = QLineEdit("mission_001")
        self.mission_name_edit.setObjectName("mainLineEdit")
        self.mission_name_edit.textChanged.connect(self._refresh_preview)
        layout.addWidget(self.mission_name_edit, 0, 1)

        layout.addWidget(self._field_label("导出目录"), 0, 2)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setObjectName("mainLineEdit")
        self.output_dir_edit.textChanged.connect(self._refresh_preview)
        layout.addWidget(self.output_dir_edit, 0, 3)

        pick_btn = self._make_action_button("选择目录", "secondary")
        pick_btn.clicked.connect(self._pick_output_dir)
        layout.addWidget(pick_btn, 0, 4)

        self.export_btn = self._make_action_button("导出任务包", "primary")
        self.export_btn.clicked.connect(self._export_plan)
        layout.addWidget(self.export_btn, 0, 5)

        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(3, 3)
        return card

    def _build_editor_tab(self, title: str):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setObjectName("tabHeader")
        layout.addWidget(label)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setObjectName("contentEditor")
        mono = QFont("Consolas")
        mono.setPointSize(11)
        editor.setFont(mono)
        layout.addWidget(editor, 1)
        return {"widget": widget, "editor": editor}

    def _build_section_header(self, title: str, subtitle: str):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle_label)
        return box

    def _field_label(self, text: str):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _make_helper_button(self, text: str, task_id: str):
        btn = self._make_action_button(text, "ghost")
        btn.clicked.connect(lambda: self._add_task(task_id))
        return btn

    def _create_card(self, object_name: str = "panelCard"):
        card = QFrame()
        card.setObjectName(object_name)
        return card

    def _make_action_button(self, text: str, kind: str):
        btn = QPushButton(text)
        btn.setProperty("kind", kind)
        btn.setMinimumHeight(40)
        return btn

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6f8;
                color: #16202a;
                font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC";
                font-size: 14px;
            }
            QFrame#heroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fdfefe, stop:0.55 #eef5fb, stop:1 #e9f0f8);
                border: 1px solid #d7e0ea;
                border-radius: 24px;
            }
            QFrame#panelCard {
                background: #fbfcfd;
                border: 1px solid #dce4ec;
                border-radius: 22px;
            }
            QLabel#heroBadge {
                background: #dbeafe;
                color: #1d4ed8;
                border-radius: 12px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QLabel#heroHint {
                color: #5a6b7d;
                font-size: 13px;
            }
            QLabel#heroTitle {
                font-size: 34px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#heroSubtitle {
                font-size: 15px;
                color: #506173;
            }
            QLabel#sectionTitle {
                font-size: 24px;
                font-weight: 650;
                color: #111827;
            }
            QLabel#sectionSubtitle {
                color: #617385;
                font-size: 13px;
            }
            QLabel#tabHeader {
                color: #516172;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#fieldLabel {
                color: #4f6171;
                font-weight: 600;
            }
            QPushButton {
                border-radius: 14px;
                padding: 10px 16px;
                border: 1px solid transparent;
                font-weight: 600;
            }
            QPushButton[kind="primary"] {
                background: #1677ff;
                color: white;
                border-color: #1677ff;
            }
            QPushButton[kind="primary"]:hover {
                background: #0f67de;
            }
            QPushButton[kind="secondary"] {
                background: #eff4f8;
                color: #1f2d3d;
                border-color: #d8e1ea;
            }
            QPushButton[kind="secondary"]:hover {
                background: #e5edf5;
            }
            QPushButton[kind="ghost"] {
                background: #ffffff;
                color: #334155;
                border-color: #d6e0e8;
            }
            QPushButton[kind="ghost"]:hover {
                background: #f6f9fb;
            }
            QTreeWidget, QListWidget, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QScrollArea {
                background: #ffffff;
                border: 1px solid #d7e1ea;
                border-radius: 16px;
            }
            QSplitter::handle {
                background: #e6edf5;
                border-radius: 3px;
            }
            QSplitter::handle:horizontal {
                width: 8px;
                margin: 0 6px;
            }
            QSplitter::handle:vertical {
                height: 8px;
                margin: 6px 0;
            }
            QTreeWidget::item, QListWidget::item {
                padding: 8px 6px;
                border-radius: 10px;
                margin: 2px 4px;
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QTreeWidget::item:hover, QListWidget::item:hover {
                background: #eff6ff;
            }
            QHeaderView::section {
                background: #f6f8fb;
                color: #516172;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #d7e1ea;
                font-weight: 600;
            }
            QTabWidget::pane {
                border: 1px solid #d7e1ea;
                border-radius: 18px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #eef3f8;
                color: #4f6274;
                border: 1px solid #d6e0e8;
                border-bottom: none;
                padding: 10px 16px;
                margin-right: 8px;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #111827;
            }
            QPlainTextEdit#contentEditor {
                padding: 12px;
                color: #16202a;
                background: #fcfdff;
            }
            QLineEdit#mainLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                padding: 10px 12px;
                min-height: 22px;
                background: #fdfefe;
            }
            QScrollArea#paramScrollArea {
                background: #fdfefe;
            }
            """
        )

    def _set_default_output_dir(self):
        self.output_dir_edit.setText(str(Path.home() / "Documents" / "无人机任务导出"))

    def _refresh_catalog(self):
        self.catalog_tree.clear()
        for category, templates in templates_by_category().items():
            group_item = QTreeWidgetItem([category, ""])
            self.catalog_tree.addTopLevelItem(group_item)
            for template in templates:
                item = QTreeWidgetItem([template.name, template.description])
                item.setData(0, Qt.UserRole, template.task_id)
                group_item.addChild(item)
            group_item.setExpanded(True)
        self.catalog_tree.doItemsLayout()

    def _pick_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if path:
            self.output_dir_edit.setText(path)

    def _selected_template_id(self):
        item = self.catalog_tree.currentItem()
        if item is None:
            return None
        return item.data(0, Qt.UserRole)

    def _add_selected_catalog_task(self):
        task_id = self._selected_template_id()
        if task_id:
            self._add_task(task_id)

    def _apply_quick_plan(self):
        name = self.quick_plan_combo.currentText()
        task_ids = QUICK_PLANS.get(name, [])
        self.mission_list.clear()
        self._clear_params()
        for task_id in task_ids:
            self._add_task(task_id, refresh=False)
        if self.mission_list.count() > 0:
            self.mission_list.setCurrentRow(0)
        self._refresh_preview()

    def _add_task_from_catalog(self, item, _column):
        task_id = item.data(0, Qt.UserRole)
        if task_id:
            self._add_task(task_id)

    def _add_task(self, task_id, refresh: bool = True):
        template = self._templates[task_id]
        task = MissionTask(task_id=template.task_id, name=template.name, params=dict(template.default_params))
        item = QListWidgetItem(task.name)
        item.setData(Qt.UserRole, task)
        self.mission_list.addItem(item)
        self.mission_list.setCurrentItem(item)
        if refresh:
            self._refresh_preview()

    def _remove_task(self):
        row = self.mission_list.currentRow()
        if row >= 0:
            self.mission_list.takeItem(row)
            self._clear_params()
            self._refresh_preview()

    def _move_task_up(self):
        row = self.mission_list.currentRow()
        if row > 0:
            item = self.mission_list.takeItem(row)
            self.mission_list.insertItem(row - 1, item)
            self.mission_list.setCurrentRow(row - 1)
            self._refresh_preview()

    def _move_task_down(self):
        row = self.mission_list.currentRow()
        if 0 <= row < self.mission_list.count() - 1:
            item = self.mission_list.takeItem(row)
            self.mission_list.insertItem(row + 1, item)
            self.mission_list.setCurrentRow(row + 1)
            self._refresh_preview()

    def _clear_params(self):
        while self.param_form.rowCount():
            self.param_form.removeRow(0)
        self.param_editor = {}

    def _on_task_selected(self, current, _previous):
        self._clear_params()
        if current is None:
            self.task_title.setText("任务参数")
            return
        task = current.data(Qt.UserRole)
        self.task_title.setText(f"任务参数 · {task.name}")
        for key, value in task.params.items():
            widget = self._make_editor(value)
            self._set_widget_value(widget, value)
            self._connect_editor_signal(widget)
            self.param_form.addRow(key, widget)
            self.param_editor[key] = widget

    def _make_editor(self, value):
        if isinstance(value, bool):
            return QCheckBox()
        if isinstance(value, int) and not isinstance(value, bool):
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            return widget
        if isinstance(value, float):
            widget = QDoubleSpinBox()
            widget.setRange(-999999.0, 999999.0)
            widget.setDecimals(4)
            return widget
        return QLineEdit()

    def _set_widget_value(self, widget, value):
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))

    def _connect_editor_signal(self, widget):
        if isinstance(widget, QCheckBox):
            widget.stateChanged.connect(self._save_current_task_params)
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(self._save_current_task_params)
        elif isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(self._save_current_task_params)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._save_current_task_params)

    def _read_editor_value(self, widget):
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return int(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, QLineEdit):
            text = widget.text().strip()
            if text.lower() in {"true", "false"}:
                return text.lower() == "true"
            try:
                if "." in text:
                    return float(text)
                return int(text)
            except ValueError:
                return text
        return None

    def _save_current_task_params(self):
        item = self.mission_list.currentItem()
        if item is None:
            return
        task = item.data(Qt.UserRole)
        for key, widget in self.param_editor.items():
            task.params[key] = self._read_editor_value(widget)
        item.setData(Qt.UserRole, task)
        self._refresh_preview()

    def _gather_plan(self, sync_current: bool = True):
        if sync_current:
            item = self.mission_list.currentItem()
            if item is not None:
                task = item.data(Qt.UserRole)
                for key, widget in self.param_editor.items():
                    task.params[key] = self._read_editor_value(widget)
                item.setData(Qt.UserRole, task)
        tasks = []
        for index in range(self.mission_list.count()):
            item = self.mission_list.item(index)
            task = item.data(Qt.UserRole)
            tasks.append(MissionTask(task_id=task.task_id, name=task.name, params=dict(task.params)))
        return MissionPlan(mission_name=self.mission_name_edit.text().strip() or "mission_001", tasks=tasks)

    def _preview_payload(self):
        plan = self._gather_plan(sync_current=False)
        payload = {
            "mission_name": plan.mission_name,
            "output_dir": self.output_dir_edit.text().strip(),
            "tasks": [{"task_id": task.task_id, "name": task.name, "params": task.params} for task in plan.tasks],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _validation_text(self, plan: MissionPlan):
        errors, warnings = validate_mission_plan(plan)
        lines = ["错误："] + ([f"- {item}" for item in errors] if errors else ["- 无"])
        lines.append("")
        lines.append("提示：")
        lines.extend([f"- {item}" for item in warnings] if warnings else ["- 无"])
        return "\n".join(lines)

    def _refresh_preview(self):
        plan = self._gather_plan(sync_current=False)
        self.preview_box.setPlainText(self._preview_payload())
        self.validation_box.setPlainText(self._validation_text(plan))

    def _save_plan(self):
        plan = self._gather_plan()
        path, _ = QFileDialog.getSaveFileName(self, "保存任务方案", f"{plan.mission_name}.json", "JSON Files (*.json)")
        if not path:
            return
        payload = {
            "mission_name": plan.mission_name,
            "tasks": [{"task_id": task.task_id, "name": task.name, "params": task.params} for task in plan.tasks],
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "保存完成", f"任务方案已保存到\n{path}")

    def _load_plan(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载任务方案", "", "JSON Files (*.json)")
        if not path:
            return
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.mission_name_edit.setText(payload.get("mission_name", "mission_001"))
        self.mission_list.clear()
        for entry in payload.get("tasks", []):
            task = MissionTask(task_id=entry["task_id"], name=entry.get("name", entry["task_id"]), params=dict(entry.get("params", {})))
            item = QListWidgetItem(task.name)
            item.setData(Qt.UserRole, task)
            self.mission_list.addItem(item)
        if self.mission_list.count() > 0:
            self.mission_list.setCurrentRow(0)
        self._refresh_preview()

    def _export_plan(self):
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请先选择导出目录。")
            return
        plan = self._gather_plan()
        errors, _warnings = validate_mission_plan(plan)
        if errors:
            QMessageBox.warning(self, "当前任务流不能导出", "\n".join(errors))
            return
        try:
            result = export_mission_bundle(plan, output_dir)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        message_lines = [
            f"导出目录：{result.bundle_dir}",
            f"入口脚本：{result.entry_script}",
            "",
            "生成文件：",
            *result.generated_files,
        ]
        if result.warnings:
            message_lines.extend(["", "提示：", *result.warnings])
        QMessageBox.information(self, "导出成功", "\n".join(message_lines))
