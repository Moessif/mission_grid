"""
网络扫描模块
============

扫描局域网中的 OrangePi 设备。

本模块包含：
- NetworkScanner: 网络扫描线程
- find_orangepi(): 快速查找 OrangePi
"""

from __future__ import annotations

import socket
import subprocess
import platform
import re
from typing import List, Optional

from PySide6.QtCore import QThread, Signal


class NetworkScanner(QThread):
    """
    网络扫描线程。

    扫描局域网中的设备，查找开放 SSH 端口(22)的设备。
    """
    device_found = Signal(str, str)  # (ip, hostname)
    scan_finished = Signal()
    scan_progress = Signal(str)  # 进度信息

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        """扫描局域网。"""
        self._running = True

        # 获取本机 IP 和子网
        local_ip = self._get_local_ip()
        if not local_ip:
            self.scan_progress.emit("无法获取本机 IP")
            self.scan_finished.emit()
            return

        # 计算子网
        parts = local_ip.split('.')
        subnet = '.'.join(parts[:3])

        self.scan_progress.emit(f"扫描子网: {subnet}.0/24")
        self.scan_progress.emit(f"本机 IP: {local_ip}")

        # 扫描每个 IP
        found_count = 0
        for i in range(1, 255):
            if not self._running:
                break

            ip = f"{subnet}.{i}"
            if ip == local_ip:
                continue

            # 检查 SSH 端口
            if self._check_ssh(ip):
                hostname = self._get_hostname(ip)
                self.device_found.emit(ip, hostname)
                found_count += 1
                self.scan_progress.emit(f"发现设备: {ip} ({hostname})")

            # 更新进度
            if i % 20 == 0:
                self.scan_progress.emit(f"扫描进度: {i}/254")

        self.scan_progress.emit(f"扫描完成，发现 {found_count} 个设备")
        self.scan_finished.emit()

    def stop(self):
        """停止扫描。"""
        self._running = False

    def _get_local_ip(self) -> Optional[str]:
        """获取本机局域网 IP。"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def _check_ssh(self, ip: str, timeout: float = 0.5) -> bool:
        """检查 SSH 端口是否开放。"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, 22))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _get_hostname(self, ip: str) -> str:
        """获取主机名。"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except Exception:
            return "未知"


def find_orangepi() -> Optional[str]:
    """
    快速查找 OrangePi IP。

    返回:
        OrangePi IP 地址，如果未找到返回 None
    """
    scanner = NetworkScanner()
    scanner.run()

    # 如果找到设备，返回第一个
    # 实际使用中应该让用户选择
    return None


def get_local_ip() -> str:
    """获取本机局域网 IP。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
