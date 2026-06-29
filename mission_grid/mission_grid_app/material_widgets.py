"""
Material You 3 自定义组件模块
=============================

基于 PySide6 实现的 Material Design 3 风格自定义 Qt 组件。

本模块包含：
- add_shadow(): 为任意 QWidget 添加阴影效果的工具函数
- MRippleButton: 带 Material 涟漪点击动画的按钮
- MCard: 圆角卡片容器（带阴影和内边距）
- MChip: 状态标签芯片（支持 success/warning/error 状态色）
- MFloatingActionButton: 浮动操作按钮（FAB）
- MDialogHeader: 对话框标题头部（大标题+副标题）
- AnimatedStackedWidget: 带左右滑动动画的堆叠页面切换器

依赖关系：
    material_theme → 本模块（使用 COLORS 颜色常量）
    本模块 → main_window, action_editor, main_task_editor（被引用）
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QTimer, QSize, QPoint
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QPainterPath
from PySide6.QtWidgets import (
    QPushButton,
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QStackedWidget,
    QTabBar,
)

from .material_theme import COLORS as c


# ============================================================
# 工具函数
# ============================================================

def add_shadow(widget: QWidget, radius: int = 8, offset_y: int = 2, opacity: int = 40):
    """
    为 QWidget 添加 Material 风格的阴影效果。

    参数:
        widget: 目标组件
        radius: 模糊半径（越大阴影越扩散）
        offset_y: 垂直偏移（模拟光源角度）
        opacity: 阴影不透明度 (0-255)

    返回:
        QGraphicsDropShadowEffect 对象（防止被 GC 回收）
    """
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(radius)
    shadow.setOffset(0, offset_y)
    shadow.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(shadow)
    return shadow


# ============================================================
# MRippleButton - 涟漪按钮
# ============================================================

class MRippleButton(QPushButton):
    """
    带 Material Design 涟漪（Ripple）点击动画的按钮。

    点击时从鼠标位置向外扩散一个半透明圆形，
    使用 QPropertyAnimation 实现平滑过渡。

    动画属性:
        rippleRadius (float): 涟漪当前半径，通过 Property 暴露给动画系统
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._ripple_radius = 0.0
        self._ripple_center = None
        self._ripple_anim = None
        self._ripple_color = QColor(c.on_primary)
        self._ripple_color.setAlpha(60)

    def paintEvent(self, event):
        """在按钮文字之上绘制涟漪圆形。"""
        super().paintEvent(event)
        if self._ripple_center and self._ripple_radius > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QBrush(self._ripple_color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(self._ripple_center, int(self._ripple_radius), int(self._ripple_radius))
            p.end()

    def mousePressEvent(self, event):
        """点击时启动涟漪动画。"""
        self._ripple_center = event.pos()
        self._ripple_radius = 0
        max_r = max(self.width(), self.height()) * 1.5
        self._ripple_anim = QPropertyAnimation(self, b"rippleRadius")
        self._ripple_anim.setDuration(400)
        self._ripple_anim.setStartValue(0.0)
        self._ripple_anim.setEndValue(float(max_r))
        self._ripple_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._ripple_anim.start()
        super().mousePressEvent(event)

    # Property getter/setter —— QPropertyAnimation 通过这些方法驱动动画
    def _get_ripple_radius(self) -> float:
        return self._ripple_radius

    def _set_ripple_radius(self, val: float):
        self._ripple_radius = val
        self.update()  # 触发重绘

    rippleRadius = Property(float, _get_ripple_radius, _set_ripple_radius)


# ============================================================
# MCard - 卡片容器
# ============================================================

class MCard(QWidget):
    """
    Material Design 3 风格的卡片容器。

    特点：
    - 圆角边框 (12px)
    - 可选阴影效果（elevated=True）
    - 内置 QVBoxLayout，边距 16px

    使用方式:
        card = MCard()
        card.addWidget(some_widget)
        card.addLayout(some_layout)
    """

    def __init__(self, parent=None, elevated: bool = True):
        super().__init__(parent)
        self._elevated = elevated
        self.setStyleSheet(f"""
            MCard {{
                background-color: {c.surface_container_lowest};
                border: 1px solid {c.outline_variant};
                border-radius: 12px;
            }}
        """)
        if elevated:
            add_shadow(self, radius=6, offset_y=1, opacity=30)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(8)

    def addWidget(self, w: QWidget):
        """添加子组件到卡片内部布局。"""
        self._layout.addWidget(w)

    def addLayout(self, l):
        """添加子布局到卡片内部布局。"""
        self._layout.addLayout(l)


# ============================================================
# MChip - 状态标签芯片
# ============================================================

class MChip(QWidget):
    """
    Material Design 3 风格的状态标签芯片。

    支持动态切换状态颜色：
    - default: 使用构造时指定的颜色（默认次要色容器）
    - success: 绿色 (#2E7D32)
    - warning: 橙色 (#E65100)
    - error: 使用主题 error 色
    - info: 使用主题 info 色

    使用方式:
        chip = MChip("就绪", filled=True)
        chip.setText("运行中")
        chip.setStatus("success")
    """

    # 状态 → (背景色, 前景色) 映射
    STATUS_COLORS = {
        "default": None,
        "success": ("#2E7D32", "#FFFFFF"),
        "warning": ("#E65100", "#FFFFFF"),
        "error": (None, None),   # 回退到主题 error 色
        "info": (None, None),    # 回退到主题 info 色
    }

    def __init__(self, text: str, parent=None, color: str = None, filled: bool = False):
        super().__init__(parent)
        self._base_color = color
        self._filled = filled
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignCenter)
        self._apply_style()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def _apply_style(self, status: str = "default"):
        """根据状态应用对应的 QSS 样式。"""
        colors = self.STATUS_COLORS.get(status)
        if colors and colors[0]:
            bg, fg = colors
        elif self._filled:
            bg = self._base_color or c.primary
            fg = c.on_primary
        else:
            bg = self._base_color or c.secondary_container
            fg = c.on_secondary_container
        self.label.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {fg};
                padding: 4px 12px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 500;
            }}
        """)

    def text(self) -> str:
        """获取当前显示文本。"""
        return self.label.text()

    def setText(self, t: str):
        """设置显示文本。"""
        self.label.setText(t)

    def setStatus(self, status: str):
        """
        动态切换状态颜色。

        参数:
            status: "default" | "success" | "warning" | "error" | "info"
        """
        self._apply_style(status)


# ============================================================
# MFloatingActionButton - 浮动操作按钮
# ============================================================

class MFloatingActionButton(QPushButton):
    """
    Material Design 3 浮动操作按钮 (FAB)。

    固定尺寸 56x56，带较重阴影，通常浮动在界面右下角。
    """

    def __init__(self, text: str = "", icon_char: str = "+", parent=None):
        super().__init__(text, parent)
        self.setProperty("cssClass", "fab")
        self.setFixedSize(56, 56)
        add_shadow(self, radius=12, offset_y=4, opacity=50)


# ============================================================
# MDialogHeader - 对话框标题头部
# ============================================================

class MDialogHeader(QWidget):
    """
    Material Design 3 对话框标题区域。

    包含大标题（20px 粗体）和可选副标题（13px 常规）。
    """

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        t = QLabel(title)
        t.setStyleSheet(f"""
            font-size: 20px; font-weight: 700; color: {c.on_surface};
        """)
        layout.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"font-size: 13px; color: {c.on_surface_variant};")
            layout.addWidget(s)


# ============================================================
# AnimatedStackedWidget - 滑动动画堆叠页面
# ============================================================

class AnimatedStackedWidget(QStackedWidget):
    """
    带左右滑动动画的 QStackedWidget。

    切换页面时，当前页面向左/右滑出，新页面从对应方向滑入。
    动画时长 250ms，使用 InOutCubic 缓动曲线。

    使用方式:
        stack = AnimatedStackedWidget()
        stack.addWidget(page1)
        stack.addWidget(page2)
        stack.slideToIndex(1)  # 滑动切换到第2页
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = None
        self._duration = 250       # 动画时长 (ms)
        self._animating = False    # 防止动画期间重复触发

    def slideToIndex(self, index: int):
        """
        滑动切换到指定页面索引。

        如果已在目标页面或动画进行中，则忽略。
        滑动方向：目标在右侧则向左滑，反之向右滑。
        """
        if index == self.currentIndex() or self._animating:
            return
        self._animating = True
        direction = 1 if index > self.currentIndex() else -1
        current_widget = self.currentWidget()
        next_widget = self.widget(index)
        if not current_widget or not next_widget:
            self.setCurrentIndex(index)
            self._animating = False
            return

        # 预设新页面位置（在屏幕外）
        w = self.width()
        next_widget.setGeometry(0, 0, w, self.height())
        next_widget.show()
        next_widget.move(direction * w, 0)

        # 退出动画：当前页面滑出
        anim_out = QPropertyAnimation(current_widget, b"pos")
        anim_out.setDuration(self._duration)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(-direction * w, 0))
        anim_out.setEasingCurve(QEasingCurve.InOutCubic)

        # 进入动画：新页面滑入
        anim_in = QPropertyAnimation(next_widget, b"pos")
        anim_in.setDuration(self._duration)
        anim_in.setStartValue(QPoint(direction * w, 0))
        anim_in.setEndValue(QPoint(0, 0))
        anim_in.setEasingCurve(QEasingCurve.InOutCubic)

        def on_finished():
            self.setCurrentIndex(index)
            current_widget.move(0, 0)
            self._animating = False

        anim_out.finished.connect(on_finished)
        # 保持引用防止 GC 回收
        self._anim_out = anim_out
        self._anim_in = anim_in
        anim_out.start()
        anim_in.start()
