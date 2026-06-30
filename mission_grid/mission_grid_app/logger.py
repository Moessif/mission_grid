"""
日志模块
========

将应用运行日志保存到 log/ 目录，每次运行一个文件。
"""

import os
import sys
import time
import logging
from pathlib import Path


def setup_logging(app_dir: str = None) -> logging.Logger:
    """
    配置日志系统。

    参数:
        app_dir: 应用目录（默认为脚本所在目录）

    返回:
        根日志记录器
    """
    if app_dir is None:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_dir = os.path.join(app_dir, "log")
    os.makedirs(log_dir, exist_ok=True)

    # 日志文件名：日期_时间.log
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"mission_grid_{timestamp}.log")

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 文件处理器（详细日志）
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器（简洁日志）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)

    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 记录启动信息
    root_logger.info(f"MissionGrid 启动，日志文件: {log_file}")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器。"""
    return logging.getLogger(name)
