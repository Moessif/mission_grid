"""
视频流模块
==========

从机载 web_video_server 获取视频流并在 Qt 界面中显示。

本模块包含：
- VideoStreamThread: 视频流获取线程
- CameraWidget: 摄像头显示组件

依赖关系：
    opencv-python ← 本模块（视频流获取）
    PySide6 ← 本模块（图像显示）

使用方法：
    1. 在 OrangePi 上启动 web_video_server
    2. 在地面站中创建 CameraWidget
    3. 连接到视频流 URL（默认 http://<ip>:8080/stream?topic=/camera/color/image_raw）
"""

from __future__ import annotations

import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox
)


class VideoStreamThread(QThread):
    """
    视频流获取线程。

    从 web_video_server 获取视频帧并转换为 QPixmap。
    使用 QThread 避免阻塞主线程。

    关键优化：
    - 使用 grab() + retrieve() 跳过缓冲区旧帧
    - 限制待处理帧数，避免堆积
    """
    frame_ready = Signal(QPixmap)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.running = False
        self.cap = None
        self._frame_pending = False  # 是否有未处理的帧

    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(self.url)

        if not self.cap.isOpened():
            self.error_occurred.emit(f"无法连接: {self.url}")
            self.connection_changed.emit(False)
            return

        # 关键：最小缓冲区
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.connection_changed.emit(True)

        while self.running and self.cap.isOpened():
            # 如果上一帧还没处理完，跳过当前帧（丢帧防堆积）
            if self._frame_pending:
                self.cap.grab()  # 丢弃一帧
                continue

            ret, frame = self.cap.read()
            if not ret:
                self.error_occurred.emit("视频流读取失败")
                self.connection_changed.emit(False)
                break

            # 降低分辨率
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                frame = cv2.resize(frame, None, fx=scale, fy=scale)

            # 转换为 QPixmap
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            qt_image = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)

            self._frame_pending = True
            self.frame_ready.emit(pixmap)

            # 约 30fps
            self.msleep(33)

        if self.cap:
            self.cap.release()
        self.connection_changed.emit(False)

    def on_frame_displayed(self):
        """主线程调用，表示帧已显示完毕。"""
        self._frame_pending = False

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()

    def is_connected(self) -> bool:
        return self.cap is not None and self.cap.isOpened()


class CameraWidget(QWidget):
    """
    摄像头显示组件。

    功能：
    - 连接到 web_video_server 视频流
    - 实时显示视频帧
    - 支持连接/断开操作
    - 显示连接状态和帧率
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_thread = None
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 连接设置
        conn_group = QGroupBox("连接设置")
        conn_layout = QHBoxLayout(conn_group)

        conn_layout.addWidget(QLabel("视频流地址:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://<ip>:8080/stream?topic=/camera/color/image_raw")
        self.url_input.setText("http://10.209.49.217:8080/stream?topic=/camera/color/image_raw")
        conn_layout.addWidget(self.url_input)

        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)

        layout.addWidget(conn_group)

        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.fps_label)
        self.resolution_label = QLabel("")
        self.resolution_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.resolution_label)
        layout.addLayout(status_layout)

        # 视频显示
        self.video_label = QLabel("等待连接...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #333;
                border-radius: 8px;
                color: #888;
                font-size: 16px;
            }
        """)
        layout.addWidget(self.video_label)

    def toggle_connection(self):
        if self.video_thread and self.video_thread.is_connected():
            self.disconnect_stream()
        else:
            self.connect_stream()

    def connect_stream(self):
        url = self.url_input.text().strip()
        if not url:
            return

        self.disconnect_stream()

        self.video_thread = VideoStreamThread(url)
        self.video_thread.frame_ready.connect(self.update_frame)
        self.video_thread.error_occurred.connect(self.handle_error)
        self.video_thread.connection_changed.connect(self.update_connection_status)
        self.video_thread.start()

        self.connect_btn.setText("断开")
        self.status_label.setText("● 连接中...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.frame_count = 0
        self.last_fps_time = time.time()

    def disconnect_stream(self):
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread = None

        self.connect_btn.setText("连接")
        self.status_label.setText("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.resolution_label.setText("")
        self.fps_label.setText("FPS: 0")
        self.video_label.setText("等待连接...")
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #333;
                border-radius: 8px;
                color: #888;
                font-size: 16px;
            }
        """)

    def update_frame(self, pixmap: QPixmap):
        """更新视频帧。"""
        # 缩放显示
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled)
        self.resolution_label.setText(f"{pixmap.width()}x{pixmap.height()}")

        # 通知线程帧已显示（允许读下一帧）
        if self.video_thread:
            self.video_thread.on_frame_displayed()

        # FPS 统计
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_fps_time
        if elapsed >= 1.0:
            self.fps_label.setText(f"FPS: {self.frame_count / elapsed:.1f}")
            self.frame_count = 0
            self.last_fps_time = now

    def handle_error(self, error_msg: str):
        self.status_label.setText(f"● 错误: {error_msg}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.disconnect_stream()

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText("● 连接断开")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def closeEvent(self, event):
        self.disconnect_stream()
        super().closeEvent(event)
