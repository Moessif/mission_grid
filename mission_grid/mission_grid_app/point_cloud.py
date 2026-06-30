"""
3D 点云可视化模块
================

从机载 rosbridge_server 获取点云数据并在 Qt 界面中显示。

本模块包含：
- PointCloudThread: 点云数据获取线程
- PointCloudWidget: 3D 点云显示组件

依赖关系：
    PyOpenGL ← 本模块（3D 渲染）
    websocket-client ← 本模块（WebSocket 连接）
    PySide6 ← 本模块（界面显示）

使用方法：
    1. 在 OrangePi 上启动 rosbridge_server
    2. 在地面站中创建 PointCloudWidget
    3. 连接到 rosbridge WebSocket（默认 ws://<ip>:9090）
"""

from __future__ import annotations

import json
import struct
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QCheckBox
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *


class PointCloudThread(QThread):
    """
    点云数据获取线程。
    
    从 rosbridge_server 获取点云帧并转换为 numpy 数组。
    使用 QThread 避免阻塞主线程。
    """
    pointcloud_ready = Signal(np.ndarray)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)
    
    def __init__(self, url: str, topic: str = "/livox/lidar", parent=None):
        """
        初始化点云端线程。
        
        参数:
            url: rosbridge WebSocket URL（如 ws://10.209.49.217:9090）
            topic: 点云话题名称
            parent: 父对象
        """
        super().__init__(parent)
        self.url = url
        self.topic = topic
        self.running = False
        self.ws = None
        
    def run(self):
        """线程主循环。"""
        import websocket
        
        self.running = True
        
        try:
            # 连接到 rosbridge
            self.ws = websocket.WebSocket()
            self.ws.connect(self.url)
            self.connection_changed.emit(True)
            
            # 订阅点云话题
            subscribe_msg = {
                "op": "subscribe",
                "topic": self.topic,
                "type": "sensor_msgs/PointCloud2"
            }
            self.ws.send(json.dumps(subscribe_msg))
            
            # 接收数据
            while self.running:
                try:
                    data = self.ws.recv()
                    if data:
                        self._process_message(data)
                except Exception as e:
                    if self.running:
                        self.error_occurred.emit(f"数据接收错误: {e}")
                    break
                    
        except Exception as e:
            self.error_occurred.emit(f"连接失败: {e}")
            self.connection_changed.emit(False)
        finally:
            if self.ws:
                self.ws.close()
            self.connection_changed.emit(False)
            
    def _process_message(self, data: str):
        """处理 rosbridge 消息。"""
        try:
            msg = json.loads(data)
            if msg.get("op") == "publish" and msg.get("topic") == self.topic:
                pointcloud = self._parse_pointcloud2(msg.get("msg", {}))
                if pointcloud is not None and len(pointcloud) > 0:
                    self.pointcloud_ready.emit(pointcloud)
        except Exception as e:
            pass  # 忽略解析错误
            
    def _parse_pointcloud2(self, msg: dict) -> np.ndarray:
        """解析 PointCloud2 消息。"""
        try:
            # 获取点云字段
            fields = msg.get("fields", [])
            point_step = msg.get("point_step", 0)
            data = msg.get("data", "")
            
            if not fields or not point_step or not data:
                return None
            
            # 解码 base64 数据
            import base64
            raw_data = base64.b64decode(data)
            
            # 计算点数
            num_points = len(raw_data) // point_step
            
            # 提取 x, y, z 坐标
            points = []
            for i in range(num_points):
                offset = i * point_step
                x = struct.unpack('f', raw_data[offset:offset+4])[0]
                y = struct.unpack('f', raw_data[offset+4:offset+8])[0]
                z = struct.unpack('f', raw_data[offset+8:offset+12])[0]
                points.append([x, y, z])
            
            return np.array(points, dtype=np.float32)
            
        except Exception as e:
            return None
            
    def stop(self):
        """停止点云端线程。"""
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.wait()
        
    def is_connected(self) -> bool:
        """检查是否已连接。"""
        return self.ws is not None and self.ws.connected


class PointCloudOpenGLWidget(QOpenGLWidget):
    """
    OpenGL 点云渲染组件。
    
    功能：
    - 3D 点云渲染
    - 鼠标旋转/缩放/平移
    - 坐标轴显示
    """
    
    def __init__(self, parent=None):
        """初始化 OpenGL 组件。"""
        super().__init__(parent)
        self.points = None
        self.rotation_x = 0.0
        self.rotation_y = 0.0
        self.zoom = -5.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.last_mouse_pos = None
        self.show_axis = True
        self.point_size = 2.0
        
    def set_points(self, points: np.ndarray):
        """设置点云数据。"""
        self.points = points
        self.update()
        
    def initializeGL(self):
        """初始化 OpenGL 设置。"""
        glClearColor(0.1, 0.1, 0.1, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_POINT_SMOOTH)
        glHint(GL_POINT_SMOOTH_HINT, GL_NICEST)
        
    def resizeGL(self, width: int, height: int):
        """调整视口大小。"""
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, width / height, 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)
        
    def paintGL(self):
        """绘制点云。"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # 应用变换
        glTranslatef(self.pan_x, self.pan_y, self.zoom)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # 绘制坐标轴
        if self.show_axis:
            self._draw_axis()
        
        # 绘制点云
        if self.points is not None and len(self.points) > 0:
            glPointSize(self.point_size)
            glBegin(GL_POINTS)
            for point in self.points:
                # 根据高度设置颜色
                z = point[2]
                r = min(1.0, max(0.0, (z + 2) / 4))
                g = min(1.0, max(0.0, 1.0 - abs(z) / 2))
                b = min(1.0, max(0.0, (2 - z) / 4))
                glColor3f(r, g, b)
                glVertex3f(point[0], point[1], point[2])
            glEnd()
            
    def _draw_axis(self):
        """绘制坐标轴。"""
        glLineWidth(2.0)
        glBegin(GL_LINES)
        
        # X 轴（红色）
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(1, 0, 0)
        
        # Y 轴（绿色）
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 1, 0)
        
        # Z 轴（蓝色）
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 1)
        
        glEnd()
        glLineWidth(1.0)
        
    def mousePressEvent(self, event):
        """鼠标按下事件。"""
        self.last_mouse_pos = event.position()
        
    def mouseMoveEvent(self, event):
        """鼠标移动事件。"""
        if self.last_mouse_pos is None:
            return
            
        dx = event.position().x() - self.last_mouse_pos.x()
        dy = event.position().y() - self.last_mouse_pos.y()
        
        if event.buttons() & Qt.LeftButton:
            # 旋转
            self.rotation_x += dy * 0.5
            self.rotation_y += dx * 0.5
        elif event.buttons() & Qt.RightButton:
            # 平移
            self.pan_x += dx * 0.01
            self.pan_y -= dy * 0.01
            
        self.last_mouse_pos = event.position()
        self.update()
        
    def wheelEvent(self, event):
        """鼠标滚轮事件。"""
        delta = event.angleDelta().y()
        self.zoom += delta * 0.001
        self.update()
        
    def reset_view(self):
        """重置视图。"""
        self.rotation_x = 0.0
        self.rotation_y = 0.0
        self.zoom = -5.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()


class PointCloudWidget(QWidget):
    """
    3D 点云显示组件。
    
    功能：
    - 连接到 rosbridge_server
    - 实时显示点云数据
    - 支持鼠标交互（旋转/缩放/平移）
    - 显示连接状态
    """
    
    def __init__(self, parent=None):
        """初始化点云组件。"""
        super().__init__(parent)
        self.pointcloud_thread = None
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
        conn_layout.addWidget(QLabel("rosbridge 地址:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("ws://<ip>:9090")
        self.url_input.setText("ws://10.209.49.217:9090")
        conn_layout.addWidget(self.url_input)
        
        # 话题输入
        conn_layout.addWidget(QLabel("话题:"))
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("/livox/lidar")
        self.topic_input.setText("/livox/lidar")
        self.topic_input.setFixedWidth(150)
        conn_layout.addWidget(self.topic_input)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        
        layout.addWidget(conn_group)
        
        # 状态指示器和控制
        control_layout = QHBoxLayout()
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()
        
        # 显示选项
        self.axis_checkbox = QCheckBox("显示坐标轴")
        self.axis_checkbox.setChecked(True)
        self.axis_checkbox.toggled.connect(self._toggle_axis)
        control_layout.addWidget(self.axis_checkbox)
        
        # 重置视图按钮
        reset_btn = QPushButton("重置视图")
        reset_btn.clicked.connect(self._reset_view)
        control_layout.addWidget(reset_btn)
        
        # 点数显示
        self.point_count_label = QLabel("点数: 0")
        self.point_count_label.setStyleSheet("color: gray;")
        control_layout.addWidget(self.point_count_label)
        
        layout.addLayout(control_layout)
        
        # OpenGL 点云显示区域
        self.gl_widget = PointCloudOpenGLWidget()
        self.gl_widget.setMinimumSize(640, 480)
        layout.addWidget(self.gl_widget)
        
        # 状态栏
        status_bar = QLabel("鼠标左键: 旋转 | 右键: 平移 | 滚轮: 缩放")
        status_bar.setStyleSheet("color: gray; font-size: 11px;")
        status_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_bar)
        
    def toggle_connection(self):
        """切换连接状态。"""
        if self.pointcloud_thread and self.pointcloud_thread.is_connected():
            self.disconnect_stream()
        else:
            self.connect_stream()
            
    def connect_stream(self):
        """连接到点云端。"""
        url = self.url_input.text().strip()
        topic = self.topic_input.text().strip()
        if not url or not topic:
            return
            
        # 断开现有连接
        self.disconnect_stream()
        
        # 创建新连接
        self.pointcloud_thread = PointCloudThread(url, topic)
        self.pointcloud_thread.pointcloud_ready.connect(self.update_pointcloud)
        self.pointcloud_thread.error_occurred.connect(self.handle_error)
        self.pointcloud_thread.connection_changed.connect(self.update_connection_status)
        self.pointcloud_thread.start()
        
        self.connect_btn.setText("断开")
        self.status_label.setText("● 连接中...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
    def disconnect_stream(self):
        """断开点云端。"""
        if self.pointcloud_thread:
            self.pointcloud_thread.stop()
            self.pointcloud_thread = None
            
        self.connect_btn.setText("连接")
        self.status_label.setText("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.point_count_label.setText("点数: 0")
        
    def update_pointcloud(self, points: np.ndarray):
        """更新点云数据。"""
        self.gl_widget.set_points(points)
        self.point_count_label.setText(f"点数: {len(points)}")
        
    def handle_error(self, error_msg: str):
        """处理错误。"""
        self.status_label.setText(f"● 错误: {error_msg}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
    def update_connection_status(self, connected: bool):
        """更新连接状态。"""
        if connected:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText("● 连接断开")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
    def _toggle_axis(self, checked: bool):
        """切换坐标轴显示。"""
        self.gl_widget.show_axis = checked
        self.gl_widget.update()
        
    def _reset_view(self):
        """重置视图。"""
        self.gl_widget.reset_view()
        
    def closeEvent(self, event):
        """关闭事件。"""
        self.disconnect_stream()
        super().closeEvent(event)
