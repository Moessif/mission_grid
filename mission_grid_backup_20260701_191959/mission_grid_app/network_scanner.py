"""
网络扫描模块
============

使用 nmap 快速扫描局域网中的 OrangePi 设备。

本模块包含：
- NetworkScanner: 网络扫描线程
"""

from __future__ import annotations

import re
import subprocess
import socket
from typing import List, Tuple

from PySide6.QtCore import QThread, Signal


class NetworkScanner(QThread):
    """
    网络扫描线程。

    使用 nmap 快速扫描局域网中开放 SSH 端口(22)的设备。
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
        subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"

        self.scan_progress.emit(f"扫描子网: {subnet}")
        self.scan_progress.emit(f"本机 IP: {local_ip}")

        # 使用 nmap 扫描
        devices = self._nmap_scan(subnet, local_ip)

        for ip, hostname in devices:
            if not self._running:
                break
            self.device_found.emit(ip, hostname)
            self.scan_progress.emit(f"发现设备: {ip} ({hostname})")

        self.scan_progress.emit(f"扫描完成，发现 {len(devices)} 个设备")
        self.scan_finished.emit()

    def stop(self):
        """停止扫描。"""
        self._running = False

    def _nmap_scan(self, subnet: str, local_ip: str) -> List[Tuple[str, str]]:
        """
        使用 nmap 扫描开放 SSH 端口的设备。

        参数:
            subnet: 子网地址 (如 192.168.1.0/24)
            local_ip: 本机 IP（排除）

        返回:
            [(ip, hostname), ...] 设备列表
        """
        devices = []

        try:
            # nmap 扫描 SSH 端口（快速扫描）
            cmd = [
                "nmap",
                "-p", "22",           # 只扫描 SSH 端口
                "--open",              # 只显示开放的端口
                "-T4",                 # 快速扫描
                "--max-retries", "1",  # 最多重试 1 次
                "-Pn",                 # 跳过 ping 探测（更可靠）
                "-n",                  # 不进行 DNS 解析
                subnet
            ]

            self.scan_progress.emit("执行 nmap 扫描...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 秒超时（-Pn 扫描较慢）
            )

            if result.returncode != 0:
                self.scan_progress.emit(f"nmap 错误: {result.stderr}")
                return devices

            # 解析 nmap 输出
            output = result.stdout
            current_ip = None

            for line in output.split('\n'):
                line = line.strip()

                # 匹配 IP 地址
                ip_match = re.match(r'Nmap scan report for (\d+\.\d+\.\d+\.\d+)', line)
                if ip_match:
                    current_ip = ip_match.group(1)
                    continue

                # 匹配开放端口
                if current_ip and '22/tcp' in line and 'open' in line:
                    if current_ip != local_ip:  # 排除本机
                        hostname = self._get_hostname(current_ip)
                        devices.append((current_ip, hostname))
                    current_ip = None

        except subprocess.TimeoutExpired:
            self.scan_progress.emit("扫描超时")
        except FileNotFoundError:
            self.scan_progress.emit("nmap 未安装，请先安装 nmap")
        except Exception as e:
            self.scan_progress.emit(f"扫描错误: {e}")

        return devices

    def _get_local_ip(self) -> str:
        """获取本机局域网 IP。"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return ""

    def _get_hostname(self, ip: str) -> str:
        """获取主机名。"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except Exception:
            return "未知"


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
