"""
仪表盘模块
==========

系统实时监控仪表盘，显示：
- CPU/内存使用率
- ROS 节点状态
- 遥测数据
- 连接状态
- 帧率统计
"""

from __future__ import annotations

import time
import platform
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QProgressBar
)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class DashboardWidget(QWidget):
    """
    系统监控仪表盘。

    显示实时系统状态、连接状态、性能指标。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = time.time()
        self.setup_ui()

        # 定时更新
        self._timer = QTimer()
        self._timer.setInterval(1000)  # 每秒更新
        self._timer.timeout.connect(self._update_stats)
        self._timer.start()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 系统信息卡片
        sys_group = QGroupBox("系统信息")
        sys_layout = QGridLayout(sys_group)

        # 主机名
        sys_layout.addWidget(QLabel("主机名:"), 0, 0)
        self.hostname_label = QLabel(platform.node())
        self.hostname_label.setStyleSheet("font-weight: bold;")
        sys_layout.addWidget(self.hostname_label, 0, 1)

        # 运行时间
        sys_layout.addWidget(QLabel("运行时间:"), 0, 2)
        self.uptime_label = QLabel("0:00:00")
        self.uptime_label.setStyleSheet("font-weight: bold;")
        sys_layout.addWidget(self.uptime_label, 0, 3)

        # 操作系统
        sys_layout.addWidget(QLabel("系统:"), 1, 0)
        self.os_label = QLabel(f"{platform.system()} {platform.release()}")
        sys_layout.addWidget(self.os_label, 1, 1)

        # Python 版本
        sys_layout.addWidget(QLabel("Python:"), 1, 2)
        self.python_label = QLabel(platform.python_version())
        sys_layout.addWidget(self.python_label, 1, 3)

        layout.addWidget(sys_group)

        # 性能监控卡片
        perf_group = QGroupBox("性能监控")
        perf_layout = QGridLayout(perf_group)

        # CPU 使用率
        perf_layout.addWidget(QLabel("CPU:"), 0, 0)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFormat("%v%")
        perf_layout.addWidget(self.cpu_bar, 0, 1)
        self.cpu_label = QLabel("0%")
        self.cpu_label.setFixedWidth(50)
        self.cpu_label.setAlignment(Qt.AlignRight)
        perf_layout.addWidget(self.cpu_label, 0, 2)

        # 内存使用率
        perf_layout.addWidget(QLabel("内存:"), 1, 0)
        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        self.mem_bar.setFormat("%v%")
        perf_layout.addWidget(self.mem_bar, 1, 1)
        self.mem_label = QLabel("0%")
        self.mem_label.setFixedWidth(50)
        self.mem_label.setAlignment(Qt.AlignRight)
        perf_layout.addWidget(self.mem_label, 1, 2)

        # 磁盘使用率
        perf_layout.addWidget(QLabel("磁盘:"), 2, 0)
        self.disk_bar = QProgressBar()
        self.disk_bar.setRange(0, 100)
        self.disk_bar.setFormat("%v%")
        perf_layout.addWidget(self.disk_bar, 2, 1)
        self.disk_label = QLabel("0%")
        self.disk_label.setFixedWidth(50)
        self.disk_label.setAlignment(Qt.AlignRight)
        perf_layout.addWidget(self.disk_label, 2, 2)

        layout.addWidget(perf_group)

        # 连接状态卡片
        conn_group = QGroupBox("连接状态")
        conn_layout = QGridLayout(conn_group)

        # SSH 连接
        conn_layout.addWidget(QLabel("SSH:"), 0, 0)
        self.ssh_status = QLabel("● 未连接")
        self.ssh_status.setStyleSheet("color: gray;")
        conn_layout.addWidget(self.ssh_status, 0, 1)

        # 遥测连接
        conn_layout.addWidget(QLabel("遥测:"), 0, 2)
        self.telem_status = QLabel("● 未连接")
        self.telem_status.setStyleSheet("color: gray;")
        conn_layout.addWidget(self.telem_status, 0, 3)

        # 摄像头连接
        conn_layout.addWidget(QLabel("摄像头:"), 1, 0)
        self.camera_status = QLabel("● 未连接")
        self.camera_status.setStyleSheet("color: gray;")
        conn_layout.addWidget(self.camera_status, 1, 1)

        # 点云连接
        conn_layout.addWidget(QLabel("点云:"), 1, 2)
        self.pointcloud_status = QLabel("● 未连接")
        self.pointcloud_status.setStyleSheet("color: gray;")
        conn_layout.addWidget(self.pointcloud_status, 1, 3)

        layout.addWidget(conn_group)

        # 性能指标卡片
        metrics_group = QGroupBox("性能指标")
        metrics_layout = QGridLayout(metrics_group)

        # 摄像头帧率
        metrics_layout.addWidget(QLabel("摄像头 FPS:"), 0, 0)
        self.camera_fps = QLabel("0")
        self.camera_fps.setStyleSheet("font-weight: bold; color: #7c4dff;")
        metrics_layout.addWidget(self.camera_fps, 0, 1)

        # 点云帧率
        metrics_layout.addWidget(QLabel("点云 FPS:"), 0, 2)
        self.pointcloud_fps = QLabel("0")
        self.pointcloud_fps.setStyleSheet("font-weight: bold; color: #7c4dff;")
        metrics_layout.addWidget(self.pointcloud_fps, 0, 3)

        # 点云点数
        metrics_layout.addWidget(QLabel("点云点数:"), 1, 0)
        self.pointcloud_count = QLabel("0")
        self.pointcloud_count.setStyleSheet("font-weight: bold;")
        metrics_layout.addWidget(self.pointcloud_count, 1, 1)

        # 遥测位置
        metrics_layout.addWidget(QLabel("位置 X:"), 1, 2)
        self.pos_x = QLabel("0.00")
        metrics_layout.addWidget(self.pos_x, 1, 3)

        metrics_layout.addWidget(QLabel("位置 Y:"), 2, 0)
        self.pos_y = QLabel("0.00")
        metrics_layout.addWidget(self.pos_y, 2, 1)

        metrics_layout.addWidget(QLabel("位置 Z:"), 2, 2)
        self.pos_z = QLabel("0.00")
        metrics_layout.addWidget(self.pos_z, 2, 3)

        layout.addWidget(metrics_group)

        # 日志卡片
        log_group = QGroupBox("最近日志")
        log_layout = QVBoxLayout(log_group)
        self.log_label = QLabel("等待日志...")
        self.log_label.setStyleSheet("font-family: Consolas; font-size: 11px; color: gray;")
        self.log_label.setWordWrap(True)
        log_layout.addWidget(self.log_label)
        layout.addWidget(log_group)

        layout.addStretch()

    def _update_stats(self):
        """更新统计数据。"""
        # 运行时间
        elapsed = int(time.time() - self._start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self.uptime_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}")

        # 系统性能
        if HAS_PSUTIL:
            cpu_percent = psutil.cpu_percent(interval=0)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            self.cpu_bar.setValue(int(cpu_percent))
            self.cpu_label.setText(f"{cpu_percent:.1f}%")

            self.mem_bar.setValue(int(mem.percent))
            self.mem_label.setText(f"{mem.percent:.1f}%")

            self.disk_bar.setValue(int(disk.percent))
            self.disk_label.setText(f"{disk.percent:.1f}%")
        else:
            self.cpu_label.setText("N/A")
            self.mem_label.setText("N/A")
            self.disk_label.setText("N/A")

    def update_ssh_status(self, connected: bool):
        """更新 SSH 连接状态。"""
        if connected:
            self.ssh_status.setText("● 已连接")
            self.ssh_status.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self.ssh_status.setText("● 未连接")
            self.ssh_status.setStyleSheet("color: gray;")

    def update_telemetry_status(self, connected: bool):
        """更新遥测连接状态。"""
        if connected:
            self.telem_status.setText("● 已连接")
            self.telem_status.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self.telem_status.setText("● 未连接")
            self.telem_status.setStyleSheet("color: gray;")

    def update_camera_status(self, connected: bool):
        """更新摄像头连接状态。"""
        if connected:
            self.camera_status.setText("● 已连接")
            self.camera_status.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self.camera_status.setText("● 未连接")
            self.camera_status.setStyleSheet("color: gray;")

    def update_pointcloud_status(self, connected: bool):
        """更新点云连接状态。"""
        if connected:
            self.pointcloud_status.setText("● 已连接")
            self.pointcloud_status.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self.pointcloud_status.setText("● 未连接")
            self.pointcloud_status.setStyleSheet("color: gray;")

    def update_camera_fps(self, fps: float):
        """更新摄像头帧率。"""
        self.camera_fps.setText(f"{fps:.1f}")

    def update_pointcloud_fps(self, fps: float):
        """更新点云帧率。"""
        self.pointcloud_fps.setText(f"{fps:.1f}")

    def update_pointcloud_count(self, count: int):
        """更新点云点数。"""
        self.pointcloud_count.setText(f"{count:,}")

    def update_position(self, x: float, y: float, z: float):
        """更新遥测位置。"""
        self.pos_x.setText(f"{x:.2f}")
        self.pos_y.setText(f"{y:.2f}")
        self.pos_z.setText(f"{z:.2f}")

    def update_log(self, message: str):
        """更新最近日志。"""
        ts = time.strftime("%H:%M:%S")
        self.log_label.setText(f"[{ts}] {message}")
