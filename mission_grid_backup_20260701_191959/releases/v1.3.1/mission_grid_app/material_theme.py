"""
Material You 3 主题模块
======================

实现 Google Material Design 3 (Material You) 配色系统和全局 QSS 样式表。

本模块包含：
- MD3Colors: Material You 3 色彩系统数据类（39 个语义化颜色变量）
- COLORS: 全局默认色彩实例（紫色主题 #6750A4）
- global_stylesheet(): 生成完整的 QSS 样式表字符串

依赖关系：
    本模块无内部依赖，被所有 UI 模块引用（material_widgets, grid_widget,
    action_editor, main_task_editor, main_window）。

使用方式：
    from material_theme import COLORS as c
    from material_theme import global_stylesheet

    # 在 QApplication 上设置全局样式
    app.setStyleSheet(global_stylesheet())

    # 在组件中使用颜色
    label.setStyleSheet(f"color: {c.on_surface_variant};")

色彩系统说明：
    Material You 使用 "角色-表面" 命名法：
    - primary/on_primary: 主色调及其上前景色
    - secondary/on_secondary: 次要色
    - tertiary/on_tertiary: 第三色（强调色）
    - error/on_error: 错误色
    - surface/on_surface: 表面色（背景/文字）
    - surface_container_*: 表面容器层级（从低到高）
    - outline/outline_variant: 边框色
    - inverse_*: 反色（用于深色元素上的浅色内容）
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MD3Colors:
    """
    Material Design 3 色彩系统。

    每个颜色角色都有对应的 "on_" 反色，用于该色表面上的前景内容。
    例如 primary 背景上用 on_primary 前景色。
    """
    # 主色调
    primary: str = "#6750A4"
    on_primary: str = "#FFFFFF"
    primary_container: str = "#EADDFF"
    on_primary_container: str = "#21005D"

    # 次要色
    secondary: str = "#625B71"
    on_secondary: str = "#FFFFFF"
    secondary_container: str = "#E8DEF8"
    on_secondary_container: str = "#1D192B"

    # 第三色（强调色）
    tertiary: str = "#7D5260"
    on_tertiary: str = "#FFFFFF"
    tertiary_container: str = "#FFD8E4"
    on_tertiary_container: str = "#31111D"

    # 错误色
    error: str = "#B3261E"
    on_error: str = "#FFFFFF"
    error_container: str = "#F9DEDC"
    on_error_container: str = "#410E0B"

    # 表面色（背景层级从低到高）
    surface: str = "#FEF7FF"
    on_surface: str = "#1D1B20"
    surface_variant: str = "#E7E0EC"
    on_surface_variant: str = "#49454F"
    surface_container_lowest: str = "#FFFFFF"
    surface_container_low: str = "#F7F2FA"
    surface_container: str = "#F3EDF7"
    surface_container_high: str = "#ECE6F0"
    surface_container_highest: str = "#E6E0E9"

    # 反色（用于深色元素上的浅色内容）
    inverse_surface: str = "#322F35"
    inverse_on_surface: str = "#F5EFF7"
    inverse_primary: str = "#D0BCFF"

    # 边框与阴影
    outline: str = "#79747E"
    outline_variant: str = "#CAC4D0"
    shadow: str = "#000000"
    scrim: str = "#000000"


# 全局默认色彩实例（紫色 Material You 主题）
COLORS = MD3Colors()


def global_stylesheet(c: MD3Colors = COLORS) -> str:
    """
    生成完整的 Qt QSS 全局样式表。

    覆盖的组件类型：
    - QPushButton (含 tonal/outlined/text/danger 变体)
    - QToolButton
    - QLineEdit / QSpinBox / QDoubleSpinBox
    - QComboBox
    - QCheckBox
    - QGroupBox
    - QTableWidget / QHeaderView
    - QTabBar / QTabWidget
    - QDialogButtonBox
    - QListWidget
    - QScrollArea / QSplitter
    - QMenuBar / QMenu
    - QStatusBar / QDialog / QLabel
    - QToolTip

    按钮变体通过 cssClass 属性区分：
    - 默认: 填充紫色
    - "tonal": 次要色容器背景
    - "outlined": 透明背景 + 边框
    - "text": 透明背景无边框
    - "danger": 红色警告
    """
    return f"""
    /* ========== 全局字体 ========== */
    * {{
        font-family: "Segoe UI", "Noto Sans SC", "Microsoft YaHei", sans-serif;
        font-size: 13px;
    }}

    /* ========== 主窗口背景 ========== */
    QMainWindow, QWidget#central {{
        background-color: {c.surface};
    }}

    /* ========== 按钮 - 默认（填充紫色） ========== */
    QPushButton {{
        background-color: {c.primary};
        color: {c.on_primary};
        border: none;
        padding: 8px 20px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 13px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: #7965AF;
    }}
    QPushButton:pressed {{
        background-color: #5b4296;
    }}
    QPushButton:disabled {{
        background-color: {c.surface_variant};
        color: {c.outline};
    }}

    /* 按钮变体 - tonal（次要色容器背景） */
    QPushButton[cssClass="tonal"] {{
        background-color: {c.secondary_container};
        color: {c.on_secondary_container};
    }}
    QPushButton[cssClass="tonal"]:hover {{
        background-color: #d5cce8;
    }}

    /* 按钮变体 - outlined（透明+边框） */
    QPushButton[cssClass="outlined"] {{
        background-color: transparent;
        color: {c.primary};
        border: 1px solid {c.outline};
    }}
    QPushButton[cssClass="outlined"]:hover {{
        background-color: rgba(103, 80, 164, 0.08);
    }}

    /* 按钮变体 - text（透明无边框） */
    QPushButton[cssClass="text"] {{
        background-color: transparent;
        color: {c.primary};
        border: none;
        padding: 8px 12px;
    }}
    QPushButton[cssClass="text"]:hover {{
        background-color: rgba(103, 80, 164, 0.08);
    }}

    /* 按钮变体 - danger（红色警告） */
    QPushButton[cssClass="danger"] {{
        background-color: {c.error};
        color: {c.on_error};
    }}
    QPushButton[cssClass="danger"]:hover {{
        background-color: #a31f18;
    }}

    /* ========== 工具按钮（含菜单下拉） ========== */
    QToolButton {{
        background-color: {c.primary};
        color: {c.on_primary};
        border: none;
        padding: 8px 20px;
        border-radius: 20px;
        font-weight: 600;
    }}
    QToolButton::menu-indicator {{
        image: none;
        width: 0;
    }}

    /* ========== 输入框（文本/数字） - Material 底部边框样式 ========== */
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {c.surface_container_highest};
        color: {c.on_surface};
        border: none;
        border-bottom: 2px solid {c.on_surface_variant};
        padding: 8px 12px;
        border-radius: 4px 4px 0 0;
        font-size: 13px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-bottom: 2px solid {c.primary};
    }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: transparent;
        border: none;
        width: 20px;
    }}

    /* ========== 下拉框 - Material 底部边框样式 ========== */
    QComboBox {{
        background-color: {c.surface_container_highest};
        color: {c.on_surface};
        border: none;
        border-bottom: 2px solid {c.on_surface_variant};
        padding: 8px 12px;
        border-radius: 4px 4px 0 0;
    }}
    QComboBox:focus {{
        border-bottom: 2px solid {c.primary};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c.surface_container_lowest};
        color: {c.on_surface};
        border: 1px solid {c.outline_variant};
        border-radius: 4px;
        selection-background-color: {c.secondary_container};
        selection-color: {c.on_secondary_container};
    }}

    /* ========== 复选框 ========== */
    QCheckBox {{
        spacing: 8px;
        color: {c.on_surface};
    }}
    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border: 2px solid {c.on_surface_variant};
        border-radius: 4px;
        background-color: transparent;
    }}
    QCheckBox::indicator:checked {{
        background-color: {c.primary};
        border-color: {c.primary};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c.on_surface};
    }}

    /* ========== 分组框 ========== */
    QGroupBox {{
        background-color: {c.surface_container_low};
        border: 1px solid {c.outline_variant};
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        color: {c.on_surface};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 16px;
        padding: 0 8px;
        color: {c.on_surface_variant};
    }}

    /* ========== 表格 ========== */
    QTableWidget {{
        background-color: {c.surface_container_lowest};
        color: {c.on_surface};
        border: 1px solid {c.outline_variant};
        border-radius: 12px;
        gridline-color: {c.outline_variant};
        selection-background-color: {c.secondary_container};
        selection-color: {c.on_secondary_container};
    }}
    QTableWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {c.surface_variant};
    }}
    QTableWidget::item:selected {{
        background-color: {c.secondary_container};
    }}
    QHeaderView::section {{
        background-color: {c.surface_container};
        color: {c.on_surface_variant};
        border: none;
        border-bottom: 2px solid {c.outline_variant};
        padding: 10px 8px;
        font-weight: 600;
        font-size: 12px;
    }}

    /* ========== 标签页（药丸样式） ========== */
    QTabWidget::pane {{
        background-color: {c.surface_container_lowest};
        border: 1px solid {c.outline_variant};
        border-radius: 12px;
        padding: 4px;
    }}
    QTabBar {{
        background-color: transparent;
        border-bottom: 1px solid {c.outline_variant};
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {c.on_surface_variant};
        padding: 10px 20px;
        margin-right: 2px;
        border: none;
        border-bottom: 3px solid transparent;
        font-weight: 500;
        font-size: 13px;
    }}
    QTabBar::tab:selected {{
        color: {c.primary};
        border-bottom: 3px solid {c.primary};
        font-weight: 700;
    }}
    QTabBar::tab:hover:!selected {{
        color: {c.on_surface};
        background-color: rgba(103, 80, 164, 0.06);
        border-radius: 8px 8px 0 0;
    }}

    /* ========== 对话框按钮 ========== */
    QDialogButtonBox QPushButton {{
        background-color: {c.primary};
        color: {c.on_primary};
        border: none;
        padding: 8px 24px;
        border-radius: 20px;
        font-weight: 600;
        min-width: 80px;
    }}
    QDialogButtonBox QPushButton:hover {{
        background-color: #7965AF;
    }}
    QDialogButtonBox QPushButton:pressed {{
        background-color: #5b4296;
    }}

    /* ========== 列表 ========== */
    QListWidget {{
        background-color: {c.surface_container_lowest};
        color: {c.on_surface};
        border: 1px solid {c.outline_variant};
        border-radius: 12px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 10px 12px;
        border-radius: 8px;
        margin: 2px 4px;
    }}
    QListWidget::item:selected {{
        background-color: {c.secondary_container};
        color: {c.on_secondary_container};
    }}
    QListWidget::item:hover {{
        background-color: {c.surface_variant};
    }}

    /* ========== 滚动区域 / 分割器 ========== */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QSplitter::handle {{
        background-color: {c.outline_variant};
        width: 1px;
    }}

    /* ========== 菜单栏 / 右键菜单 ========== */
    QMenuBar {{
        background-color: {c.surface};
        color: {c.on_surface};
        border-bottom: 1px solid {c.outline_variant};
    }}
    QMenuBar::item:selected {{
        background-color: {c.secondary_container};
    }}
    QMenu {{
        background-color: {c.surface_container_lowest};
        color: {c.on_surface};
        border: 1px solid {c.outline_variant};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {c.secondary_container};
    }}

    /* ========== 状态栏 / 对话框 / 标签 ========== */
    QStatusBar {{
        background-color: {c.surface_container};
        color: {c.on_surface_variant};
        border-top: 1px solid {c.outline_variant};
        padding: 4px 12px;
    }}
    QDialog {{
        background-color: {c.surface_container_lowest};
    }}
    QLabel {{
        color: {c.on_surface};
        background-color: transparent;
    }}

    /* ========== 工具提示 ========== */
    QToolTip {{
        background-color: {c.inverse_surface};
        color: {c.inverse_on_surface};
        border: none;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
    }}
    """
