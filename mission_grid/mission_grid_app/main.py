"""
应用启动模块
============

MissionGrid 地面站的 QApplication 初始化和启动入口。

本模块包含：
- run(): 应用启动函数（初始化 QApplication、设置主题、显示主窗口）

依赖关系：
    material_theme ← 本模块（global_stylesheet, COLORS）
    main_window ← 本模块（MainWindow）
    PySide6 ← 本模块（QApplication, QStyleFactory, QFont）

启动流程：
    1. 初始化日志系统
    2. 创建 QApplication 实例
    3. 设置 Fusion 样式（Windows 上必须，否则 QSS border-radius 无效）
    4. 应用 Material You 全局样式表
    5. 设置全局字体（Segoe UI 13pt，开启全提示）
    6. 创建并显示主窗口
    7. 进入事件循环
"""

import os
import logging
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QFont

from .material_theme import global_stylesheet, COLORS
from .main_window import MainWindow
from .logger import setup_logging


def run():
    """
    启动 MissionGrid 地面站应用。

    注意：必须在 setStyleSheet 之前调用 setStyle("Fusion")，
    否则 Windows 原生样式会覆盖 QSS 的 border-radius 等属性。
    """
    # 初始化日志系统
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    setup_logging(app_dir)
    logger = logging.getLogger(__name__)

    logger.info("MissionGrid 地面站启动中...")

    app = QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))  # Fusion 样式支持 QSS 圆角
    app.setStyleSheet(global_stylesheet())
    font = QFont("Segoe UI", 13)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    logger.info("创建主窗口...")
    window = MainWindow()
    window.show()

    logger.info("进入事件循环")
    app.exec()
    logger.info("MissionGrid 地面站退出")
