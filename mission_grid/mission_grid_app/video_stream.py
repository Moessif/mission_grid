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

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QGroupBox
)


class VideoStreamThread(QThread):
    """
    视频流获取线程。
    
    从 web_video_server 获取视频帧并转换为 QPixmap。
    使用 QThread 避免阻塞主线程。
    """
    frame_ready = Signal(QPixmap)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)
    
    def __init__(self, url: str, parent=None):
        """
        初始化视频流线程。
        
        参数:
            url: 视频流 URL（如 http://10.209.49.217:8080/stream?topic=/camera/color/image_raw）
            parent: 父对象
        """
        super().__init__(parent)
        self.url = url
        self.running = False
        self.cap = None
        
    def run(self):
        """线程主循环。"""
        self.running = True
        self.cap = cv2.VideoCapture(self.url)
        
        if not self.cap.isOpened():
            self.error_occurred.emit(f"无法连接到视频流: {self.url}")
            self.connection_changed.emit(False)
            return
            
        self.connection_changed.emit(True)
        
        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                self.error_occurred.emit("视频流读取失败")
                self.connection_changed.emit(False)
                break
                
            # 转换 OpenCV 图像为 QPixmap
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # 发送帧到主线程
            self.frame_ready.emit(pixmap)
            
            # 控制帧率（约 30fps）
            self.msleep(33)
            
        if self.cap:
            self.cap.release()
        self.connection_changed.emit(False)
        
    def stop(self):
        """停止视频流。"""
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()
        
    def is_connected(self) -> bool:
        """检查是否已连接。"""
        return self.cap is not None and self.cap.isOpened()


class CameraWidget(QWidget):
    """
    摄像头显示组件。
    
    功能：
    - 连接到 web_video_server 视频流
    - 实时显示视频帧
    - 支持连接/断开操作
    - 显示连接状态
    """
    
    def __init__(self, parent=None):
        """初始化摄像头组件。"""
        super().__init__(parent)
        self.video_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        """设置界面布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 连接控制组
        conn_group = QGroupBox("连接设置")
        conn_layout = QHBoxLayout(conn_group)
        
        # URL 输入
        conn_layout.addWidget(QLabel("视频流地址:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://<ip>:8080/stream?topic=/camera/color/image_raw")
        self.url_input.setText("http://10.209.49.217:8080/stream?topic=/camera/color/image_raw")
        conn_layout.addWidget(self.url_input)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        
        layout.addWidget(conn_group)
        
        # 状态指示器
        status_layout = QHBoxLayout()
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        # 分辨率显示
        self.resolution_label = QLabel("")
        self.resolution_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.resolution_label)
        
        layout.addLayout(status_layout)
        
        # 视频显示区域
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #333;
                border-radius: 8px;
            }
        """)
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
        layout.addWidget(self.video_label)
        
    def toggle_connection(self):
        """切换连接状态。"""
        if self.video_thread and self.video_thread.is_connected():
            self.disconnect_stream()
        else:
            self.connect_stream()
            
    def connect_stream(self):
        """连接到视频流。"""
        url = self.url_input.text().strip()
        if not url:
            return
            
        # 断开现有连接
        self.disconnect_stream()
        
        # 创建新连接
        self.video_thread = VideoStreamThread(url)
        self.video_thread.frame_ready.connect(self.update_frame)
        self.video_thread.error_occurred.connect(self.handle_error)
        self.video_thread.connection_changed.connect(self.update_connection_status)
        self.video_thread.start()
        
        self.connect_btn.setText("断开")
        self.status_label.setText("● 连接中...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
    def disconnect_stream(self):
        """断开视频流。"""
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread = None
            
        self.connect_btn.setText("连接")
        self.status_label.setText("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.resolution_label.setText("")
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
        # 缩放图像以适应标签大小
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)
        
        # 更新分辨率显示
        self.resolution_label.setText(f"{pixmap.width()}x{pixmap.height()}")
        
    def handle_error(self, error_msg: str):
        """处理错误。"""
        self.status_label.setText(f"● 错误: {error_msg}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.disconnect_stream()
        
    def update_connection_status(self, connected: bool):
        """更新连接状态。"""
        if connected:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText("● 连接断开")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
    def closeEvent(self, event):
        """关闭事件。"""
        self.disconnect_stream()
        super().closeEvent(event)
