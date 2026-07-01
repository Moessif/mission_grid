"""
配置模块
========

MissionGrid 的可配置参数。

本模块包含：
- AppConfig: 应用配置数据类
- load_config(): 加载配置
- save_config(): 保存配置
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    """
    应用配置。

    属性:
        orangepi_ip: OrangePi IP 地址
        orangepi_user: SSH 用户名
        orangepi_pass: SSH 密码
        flight_controller_ip: 飞控 IP 地址
        camera_topic: 摄像头 ROS 话题
        pointcloud_topic: 点云 ROS 话题
        rosbridge_port: rosbridge WebSocket 端口
        web_video_port: web_video_server HTTP 端口
        mavlink_port: MAVLink UDP 端口
    """
    # OrangePi 连接
    orangepi_ip: str = ""  # 空表示未配置，需要扫描或手动输入
    orangepi_user: str = "orangepi"
    orangepi_pass: str = "orangepi"

    # 飞控连接
    flight_controller_ip: str = "192.168.144.15"

    # ROS 话题
    camera_topic: str = "/image"
    pointcloud_topic: str = "/livox/lidar"

    # 端口
    rosbridge_port: int = 9090
    web_video_port: int = 8080
    mavlink_port: int = 14550

    # 飞行参数
    default_altitude: float = 1.2
    default_speed: float = 1.0

    @property
    def camera_url(self) -> str:
        """摄像头视频流 URL。"""
        return f"http://{self.orangepi_ip}:{self.web_video_port}/stream?topic={self.camera_topic}"

    @property
    def rosbridge_url(self) -> str:
        """rosbridge WebSocket URL。"""
        return f"ws://{self.orangepi_ip}:{self.rosbridge_port}"

    @property
    def fcu_url(self) -> str:
        """飞控连接 URL。"""
        return f"udp://:14555@{self.flight_controller_ip}:14550"

    @property
    def gcs_url(self) -> str:
        """地面站连接 URL（需要 @ 符号）。"""
        return f"udp://@{{local_ip}}:{self.mavlink_port}"


# 默认配置文件路径（应用目录下）
_APP_DIR = Path(__file__).parent.parent  # mission_grid/
CONFIG_FILE = _APP_DIR / "config.json"


def load_config() -> AppConfig:
    """
    加载配置文件。

    如果配置文件不存在，返回默认配置。
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return AppConfig(**data)
        except (json.JSONDecodeError, TypeError):
            pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """
    保存配置文件。

    参数:
        config: 配置对象
    """
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(config), f, ensure_ascii=False, indent=2)


def get_config_path() -> Path:
    """获取配置文件路径。"""
    return CONFIG_FILE
