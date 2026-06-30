"""
3D 点云可视化模块
================

从机载 rosbridge_server 获取点云数据并在 Qt 界面中显示。

关键优化：
- 接收端丢帧：只保留最新一帧，避免堆积
- 渲染限速：最高 30fps，超时自动跳过
- VBO 加速渲染
"""

from __future__ import annotations

import base64
import json
import struct
import time
import threading
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QCheckBox, QSpinBox, QTextEdit,
    QComboBox
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *


class PointCloudThread(QThread):
    """点云数据获取线程。"""
    pointcloud_ready = Signal(np.ndarray)
    error_occurred = Signal(str)
    connection_changed = Signal(bool)
    debug_message = Signal(str)

    def __init__(self, url: str, topic: str = "/livox/lidar", parent=None):
        super().__init__(parent)
        self.url = url
        self.topic = topic
        self.running = False
        self.ws = None
        self._latest_points = None
        self._lock = threading.Lock()

    def run(self):
        import websocket

        self.running = True
        self._log(f"正在连接 {self.url} ...")

        try:
            self.ws = websocket.WebSocket()
            self.ws.settimeout(1.0)
            self.ws.connect(self.url)
            self.connection_changed.emit(True)
            self._log("WebSocket 连接成功")

            subscribe_msg = {"op": "subscribe", "topic": self.topic}
            self.ws.send(json.dumps(subscribe_msg))
            self._log(f"已订阅话题: {self.topic}")

            # 启动定时发送线程（30fps 限制）
            sender = threading.Thread(target=self._sender_loop, daemon=True)
            sender.start()

            while self.running:
                try:
                    data = self.ws.recv()
                    if data:
                        self._process_message(data)
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception as e:
                    if self.running:
                        self.error_occurred.emit(f"接收错误: {e}")
                    break

        except Exception as e:
            self.error_occurred.emit(f"连接失败: {e}")
            self._log(f"连接失败: {e}")
            self.connection_changed.emit(False)
        finally:
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
            self.connection_changed.emit(False)

    def _sender_loop(self):
        """定时发送最新帧（30fps 限制，丢弃中间帧）。"""
        while self.running:
            time.sleep(1.0 / 30)  # 30fps
            with self._lock:
                if self._latest_points is not None:
                    points = self._latest_points
                    self._latest_points = None
                    self.pointcloud_ready.emit(points)

    def _log(self, msg: str):
        self.debug_message.emit(f"[Thread] {msg}")

    def _process_message(self, data: str):
        try:
            msg = json.loads(data)
            if msg.get("op") == "publish" and msg.get("topic") == self.topic:
                payload = msg.get("msg", {})
                points = self._parse_any_pointcloud(payload)
                if points is not None and len(points) > 0:
                    # 只保存最新帧，丢弃旧帧
                    with self._lock:
                        self._latest_points = points
        except:
            pass

    def _parse_any_pointcloud(self, msg: dict) -> np.ndarray:
        if "point_step" in msg:
            return self._parse_pointcloud2(msg)
        elif "points" in msg:
            return self._parse_livox_custom(msg)
        return None

    def _parse_livox_custom(self, msg: dict) -> np.ndarray:
        try:
            points_data = msg.get("points", [])
            if not points_data:
                return None
            num = len(points_data)
            points = np.zeros((num, 3), dtype=np.float32)
            for i, p in enumerate(points_data):
                points[i, 0] = p.get("x", 0.0)
                points[i, 1] = p.get("y", 0.0)
                points[i, 2] = p.get("z", 0.0)
            valid = np.isfinite(points).all(axis=1) & (np.abs(points) < 1000).all(axis=1)
            return points[valid] if valid.any() else None
        except:
            return None

    def _parse_pointcloud2(self, msg: dict) -> np.ndarray:
        try:
            fields = msg.get("fields", [])
            point_step = msg.get("point_step", 0)
            data = msg.get("data", "")
            if not data:
                return None

            raw_data = base64.b64decode(data)
            if not point_step:
                point_step = 12

            num_points = len(raw_data) // point_step
            if num_points == 0:
                return None

            x_off, y_off, z_off = 0, 4, 8
            for f in fields:
                name = f.get("name", "")
                if name == "x": x_off = f.get("offset", 0)
                elif name == "y": y_off = f.get("offset", 0)
                elif name == "z": z_off = f.get("offset", 0)

            raw = np.frombuffer(raw_data, dtype=np.uint8).reshape(num_points, point_step)
            x = raw[:, x_off:x_off+4].view('<f4').flatten()
            y = raw[:, y_off:y_off+4].view('<f4').flatten()
            z = raw[:, z_off:z_off+4].view('<f4').flatten()
            points = np.column_stack([x, y, z])

            valid = np.isfinite(points).all(axis=1) & (np.abs(points) < 1000).all(axis=1)
            return points[valid] if valid.any() else None
        except:
            return None

    def stop(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.wait()

    def is_connected(self) -> bool:
        return self.ws is not None and self.ws.connected


class PointCloudOpenGLWidget(QOpenGLWidget):
    """OpenGL 点云渲染组件（VBO 加速 + 帧率限制）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = None
        self.colors = None
        self.rotation_x = 30.0
        self.rotation_y = -45.0
        self.zoom = -10.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.last_mouse_pos = None
        self.show_axis = True
        self.point_size = 2.0
        self.max_points = 50000
        self._vbo_pos = None
        self._vbo_col = None
        self._vbo_count = 0
        self._need_vbo_update = False
        self._pending_update = False

        # 帧率限制定时器（60fps）
        self._render_timer = QTimer()
        self._render_timer.setInterval(16)  # ~60fps
        self._render_timer.timeout.connect(self._do_render)
        self._render_timer.start()

    def set_points(self, points: np.ndarray):
        if len(points) > self.max_points:
            indices = np.random.choice(len(points), self.max_points, replace=False)
            self.points = points[indices].copy()
        else:
            self.points = points.copy()
        self._compute_colors()
        self._need_vbo_update = True
        self._pending_update = True

    def _do_render(self):
        """定时器触发的渲染（限制 60fps）。"""
        if self._pending_update:
            self._pending_update = False
            self.update()

    def _compute_colors(self):
        if self.points is None or len(self.points) == 0:
            self.colors = None
            return
        z = self.points[:, 2]
        z_min, z_max = z.min(), z.max()
        z_range = z_max - z_min if z_max > z_min else 1.0
        z_norm = (z - z_min) / z_range
        colors = np.zeros((len(self.points), 3), dtype=np.float32)
        colors[:, 0] = np.clip(z_norm * 2, 0, 1)
        colors[:, 1] = np.clip(1.0 - np.abs(z_norm - 0.5) * 2, 0, 1)
        colors[:, 2] = np.clip((1 - z_norm) * 2, 0, 1)
        self.colors = colors

    def initializeGL(self):
        glClearColor(0.12, 0.12, 0.15, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._vbo_pos = glGenBuffers(1)
        self._vbo_col = glGenBuffers(1)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / max(h, 1), 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self.pan_x, self.pan_y, self.zoom)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)

        if self.show_axis:
            self._draw_axis()
        self._draw_grid()

        if self.points is not None and len(self.points) > 0:
            self._draw_points_vbo()

    def _update_vbo(self):
        if not self._need_vbo_update:
            return
        n = len(self.points)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
        glBufferData(GL_ARRAY_BUFFER, self.points.nbytes, self.points, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
        glBufferData(GL_ARRAY_BUFFER, self.colors.nbytes, self.colors, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self._vbo_count = n
        self._need_vbo_update = False

    def _draw_points_vbo(self):
        self._update_vbo()
        if self._vbo_count == 0:
            return

        glPointSize(self.point_size)
        glEnableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
        glVertexPointer(3, GL_FLOAT, 0, None)
        glEnableClientState(GL_COLOR_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
        glColorPointer(3, GL_FLOAT, 0, None)
        glDrawArrays(GL_POINTS, 0, self._vbo_count)
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _draw_grid(self):
        glColor4f(0.3, 0.3, 0.3, 0.5)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in range(-10, 11):
            glVertex3f(i, -10, 0)
            glVertex3f(i, 10, 0)
            glVertex3f(-10, i, 0)
            glVertex3f(10, i, 0)
        glEnd()

    def _draw_axis(self):
        glLineWidth(3.0)
        glBegin(GL_LINES)
        glColor3f(1, 0, 0); glVertex3f(0, 0, 0); glVertex3f(2, 0, 0)
        glColor3f(0, 1, 0); glVertex3f(0, 0, 0); glVertex3f(0, 2, 0)
        glColor3f(0, 0, 1); glVertex3f(0, 0, 0); glVertex3f(0, 0, 2)
        glEnd()
        glLineWidth(1.0)

    def mousePressEvent(self, event):
        self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos is None:
            return
        dx = event.position().x() - self.last_mouse_pos.x()
        dy = event.position().y() - self.last_mouse_pos.y()
        if event.buttons() & Qt.LeftButton:
            self.rotation_x += dy * 0.5
            self.rotation_y += dx * 0.5
        elif event.buttons() & Qt.RightButton:
            self.pan_x += dx * 0.01
            self.pan_y -= dy * 0.01
        self.last_mouse_pos = event.position()
        self._pending_update = True  # 标记需要重绘，不立即调用 update()

    def wheelEvent(self, event):
        self.zoom += event.angleDelta().y() * 0.01
        self._pending_update = True

    def reset_view(self):
        self.rotation_x = 30.0
        self.rotation_y = -45.0
        self.zoom = -10.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._pending_update = True

    def cleanup(self):
        if self._vbo_pos:
            glDeleteBuffers(1, [self._vbo_pos])
            self._vbo_pos = None
        if self._vbo_col:
            glDeleteBuffers(1, [self._vbo_col])
            self._vbo_col = None


class PointCloudWidget(QWidget):
    """3D 点云显示组件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pointcloud_thread = None
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        conn_group = QGroupBox("连接设置")
        conn_layout = QHBoxLayout(conn_group)
        conn_layout.addWidget(QLabel("rosbridge:"))
        self.url_input = QLineEdit("ws://10.209.49.217:9090")
        conn_layout.addWidget(self.url_input)
        conn_layout.addWidget(QLabel("话题:"))
        self.topic_input = QComboBox()
        self.topic_input.setEditable(True)
        self.topic_input.addItems(["/livox/lidar", "/livox/pointcloud", "/cloud_registered", "/velodyne_points", "/points_raw"])
        self.topic_input.setCurrentText("/livox/lidar")
        self.topic_input.setFixedWidth(180)
        conn_layout.addWidget(self.topic_input)
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        layout.addWidget(conn_group)

        ctrl = QHBoxLayout()
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        ctrl.addWidget(self.status_label)
        ctrl.addStretch()
        self.fps_label = QLabel("FPS: 0")
        ctrl.addWidget(self.fps_label)
        self.point_count_label = QLabel("点数: 0")
        ctrl.addWidget(self.point_count_label)
        ctrl.addWidget(QLabel("显示上限:"))
        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(1000, 500000)
        self.max_points_spin.setValue(50000)
        self.max_points_spin.setSingleStep(10000)
        self.max_points_spin.valueChanged.connect(lambda v: setattr(self.gl_widget, 'max_points', v))
        ctrl.addWidget(self.max_points_spin)
        self.axis_cb = QCheckBox("坐标轴")
        self.axis_cb.setChecked(True)
        self.axis_cb.toggled.connect(lambda v: setattr(self.gl_widget, 'show_axis', v) or self.gl_widget.update())
        ctrl.addWidget(self.axis_cb)
        reset_btn = QPushButton("重置视图")
        reset_btn.clicked.connect(lambda: self.gl_widget.reset_view())
        ctrl.addWidget(reset_btn)
        layout.addLayout(ctrl)

        self.gl_widget = PointCloudOpenGLWidget()
        self.gl_widget.setMinimumSize(400, 300)
        layout.addWidget(self.gl_widget, 1)

        self.debug_toggle = QPushButton("▼ 调试日志")
        self.debug_toggle.setCheckable(True)
        self.debug_toggle.toggled.connect(lambda v: (self.debug_text.setVisible(v), self.debug_toggle.setText("▲ 调试日志" if v else "▼ 调试日志")))
        layout.addWidget(self.debug_toggle)

        self.debug_text = QTextEdit()
        self.debug_text.setMaximumHeight(100)
        self.debug_text.setReadOnly(True)
        self.debug_text.setStyleSheet("font-family: Consolas; font-size: 11px;")
        self.debug_text.hide()
        layout.addWidget(self.debug_text)

        hint = QLabel("鼠标左键: 旋转 | 右键: 平移 | 滚轮: 缩放")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def toggle_connection(self):
        if self.pointcloud_thread and self.pointcloud_thread.is_connected():
            self.disconnect_stream()
        else:
            self.connect_stream()

    def connect_stream(self):
        url = self.url_input.text().strip()
        topic = self.topic_input.currentText().strip()
        if not url or not topic:
            return
        self.disconnect_stream()
        self._log(f"连接 {url}，话题 {topic}")

        self.pointcloud_thread = PointCloudThread(url, topic)
        self.pointcloud_thread.pointcloud_ready.connect(self.update_pointcloud)
        self.pointcloud_thread.error_occurred.connect(self.handle_error)
        self.pointcloud_thread.connection_changed.connect(self.update_connection_status)
        self.pointcloud_thread.debug_message.connect(self._log)
        self.pointcloud_thread.start()

        self.connect_btn.setText("断开")
        self.status_label.setText("● 连接中...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.frame_count = 0
        self.last_fps_time = time.time()

    def disconnect_stream(self):
        if self.pointcloud_thread:
            self.pointcloud_thread.stop()
            self.pointcloud_thread = None
        self.connect_btn.setText("连接")
        self.status_label.setText("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.point_count_label.setText("点数: 0")
        self.fps_label.setText("FPS: 0")

    def update_pointcloud(self, points: np.ndarray):
        self.gl_widget.set_points(points)
        self.point_count_label.setText(f"点数: {len(points)}")
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_fps_time
        if elapsed >= 1.0:
            self.fps_label.setText(f"FPS: {self.frame_count / elapsed:.1f}")
            self.frame_count = 0
            self.last_fps_time = now

    def handle_error(self, msg: str):
        self.status_label.setText(f"● 错误: {msg}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self._log(f"错误: {msg}")

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText("● 连接断开")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.debug_text.append(f"[{ts}] {msg}")

    def closeEvent(self, event):
        self.disconnect_stream()
        self.gl_widget.cleanup()
        super().closeEvent(event)
