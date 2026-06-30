"""
3D 点云可视化模块（moderngl 加速版）
====================================

使用 moderngl 实现高性能点云渲染，目标 60 FPS。

关键优化：
- moderngl 替代 PyOpenGL（更高效的 Python OpenGL 绑定）
- GLSL 着色器实现 GPU 端颜色计算
- 接收端丢帧，只渲染最新帧
- VBO 只在数据变化时更新
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
from PySide6.QtGui import QCursor, QSurfaceFormat
import moderngl


# 顶点着色器
VERTEX_SHADER = """
#version 330
in vec3 in_position;
in vec3 in_color;
uniform mat4 mvp;
out vec3 frag_color;
void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
    frag_color = in_color;
    gl_PointSize = 2.0;
}
"""

# 片段着色器
FRAGMENT_SHADER = """
#version 330
in vec3 frag_color;
out vec4 out_color;
void main() {
    out_color = vec4(frag_color, 1.0);
}
"""

# 网格着色器
GRID_VERTEX = """
#version 330
in vec3 in_position;
uniform mat4 mvp;
void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
}
"""

GRID_FRAGMENT = """
#version 330
uniform vec4 grid_color;
out vec4 out_color;
void main() {
    out_color = grid_color;
}
"""


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
                try: self.ws.close()
                except: pass
            self.connection_changed.emit(False)

    def _sender_loop(self):
        while self.running:
            time.sleep(1.0 / 30)
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
                points = self._parse_any_pointcloud(msg.get("msg", {}))
                if points is not None and len(points) > 0:
                    with self._lock:
                        self._latest_points = points
        except: pass

    def _parse_any_pointcloud(self, msg: dict) -> np.ndarray:
        if "point_step" in msg: return self._parse_pointcloud2(msg)
        elif "points" in msg: return self._parse_livox_custom(msg)
        return None

    def _parse_livox_custom(self, msg: dict) -> np.ndarray:
        try:
            points_data = msg.get("points", [])
            if not points_data: return None
            num = len(points_data)
            points = np.zeros((num, 3), dtype=np.float32)
            for i, p in enumerate(points_data):
                points[i, 0] = p.get("x", 0.0)
                points[i, 1] = p.get("y", 0.0)
                points[i, 2] = p.get("z", 0.0)
            valid = np.isfinite(points).all(axis=1) & (np.abs(points) < 1000).all(axis=1)
            return points[valid] if valid.any() else None
        except: return None

    def _parse_pointcloud2(self, msg: dict) -> np.ndarray:
        try:
            fields = msg.get("fields", [])
            point_step = msg.get("point_step", 0)
            data = msg.get("data", "")
            if not data: return None
            raw_data = base64.b64decode(data)
            if not point_step: point_step = 12
            num_points = len(raw_data) // point_step
            if num_points == 0: return None
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
        except: return None

    def stop(self):
        self.running = False
        if self.ws:
            try: self.ws.close()
            except: pass
        self.wait()

    def is_connected(self) -> bool:
        return self.ws is not None and self.ws.connected


class PointCloudGLWidget(QOpenGLWidget):
    """
    moderngl 点云渲染组件。

    操控：
    - 左键拖动：旋转视角
    - 右键拖动：平移
    - 滚轮：缩放
    - F 键：切换第一人称模式
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = None
        self.colors = None

        # 轨道模式参数
        self.orbit_yaw = -45.0
        self.orbit_pitch = 30.0
        self.orbit_dist = 10.0
        self.orbit_target = [0.0, 0.0, 0.0]

        # 第一人称参数
        self.fp_pos = [5.0, 5.0, 3.0]
        self.fp_yaw = -135.0
        self.fp_pitch = 0.0
        self.fp_speed = 5.0

        self.show_axis = True
        self.point_size = 2.0
        self.max_points = 100000  # 提升到 10 万点

        # moderngl 资源
        self.ctx = None
        self.point_prog = None
        self.point_vao = None
        self.grid_prog = None
        self.grid_vao = None
        self.axis_vao = None
        self._need_vbo_update = False

        # 模式
        self.fps_mode = False
        self.last_mouse_pos = None
        self._keys_pressed = set()

        # 移动定时器
        self._move_timer = QTimer()
        self._move_timer.setInterval(16)
        self._move_timer.timeout.connect(self._update_movement)
        self._move_timer.start()

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # 设置 OpenGL 版本
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setDepthBufferSize(24)
        self.setFormat(fmt)

    def set_points(self, points: np.ndarray):
        if len(points) > self.max_points:
            indices = np.random.choice(len(points), self.max_points, replace=False)
            self.points = points[indices].copy()
        else:
            self.points = points.copy()
        self._compute_colors()
        self._need_vbo_update = True
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

    def toggle_fps_mode(self):
        self.fps_mode = not self.fps_mode
        if self.fps_mode:
            yaw_rad = np.radians(self.orbit_yaw)
            pitch_rad = np.radians(self.orbit_pitch)
            self.fp_pos = [
                self.orbit_target[0] + self.orbit_dist * np.cos(pitch_rad) * np.cos(yaw_rad),
                self.orbit_target[1] + self.orbit_dist * np.cos(pitch_rad) * np.sin(yaw_rad),
                self.orbit_target[2] + self.orbit_dist * np.sin(pitch_rad)
            ]
            self.fp_yaw = self.orbit_yaw + 180
            self.fp_pitch = -self.orbit_pitch
            self.setCursor(Qt.BlankCursor)
            self.grabMouse()
        else:
            self.setCursor(Qt.ArrowCursor)
            self.releaseMouse()
        self.update()

    def _update_movement(self):
        if not self.fps_mode or not self._keys_pressed:
            return
        dt = 0.016
        speed = self.fp_speed * dt
        yaw_rad = np.radians(self.fp_yaw)
        forward = [np.cos(yaw_rad), np.sin(yaw_rad), 0]
        right = [-np.sin(yaw_rad), np.cos(yaw_rad), 0]
        moved = False
        if Qt.Key_W in self._keys_pressed:
            self.fp_pos[0] += forward[0] * speed
            self.fp_pos[1] += forward[1] * speed
            moved = True
        if Qt.Key_S in self._keys_pressed:
            self.fp_pos[0] -= forward[0] * speed
            self.fp_pos[1] -= forward[1] * speed
            moved = True
        if Qt.Key_A in self._keys_pressed:
            self.fp_pos[0] -= right[0] * speed
            self.fp_pos[1] -= right[1] * speed
            moved = True
        if Qt.Key_D in self._keys_pressed:
            self.fp_pos[0] += right[0] * speed
            self.fp_pos[1] += right[1] * speed
            moved = True
        if Qt.Key_Space in self._keys_pressed:
            self.fp_pos[2] += speed
            moved = True
        if Qt.Key_Shift in self._keys_pressed:
            self.fp_pos[2] -= speed
            moved = True
        if moved:
            self.update()

    def initializeGL(self):
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)

        # 点云着色器
        self.point_prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER
        )

        # 网格着色器
        self.grid_prog = self.ctx.program(
            vertex_shader=GRID_VERTEX,
            fragment_shader=GRID_FRAGMENT
        )
        self.grid_prog['grid_color'].value = (0.2, 0.2, 0.25, 0.6)

        # 创建网格 VAO
        self._create_grid_vao()

        # 创建坐标轴 VAO
        self._create_axis_vao()

    def _create_grid_vao(self):
        """创建网格顶点数据。"""
        vertices = []
        for i in range(-20, 21):
            vertices.extend([i, -20, 0, i, 20, 0])
            vertices.extend([-20, i, 0, 20, i, 0])
        vertices = np.array(vertices, dtype='f4')
        vbo = self.ctx.buffer(vertices.tobytes())
        self.grid_vao = self.ctx.vertex_array(
            self.grid_prog,
            [(vbo, '3f', 'in_position')]
        )

    def _create_axis_vao(self):
        """创建坐标轴顶点数据。"""
        vertices = np.array([
            0, 0, 0, 2, 0, 0,  # X
            0, 0, 0, 0, 2, 0,  # Y
            0, 0, 0, 0, 0, 2,  # Z
        ], dtype='f4')
        colors = np.array([
            1, 0, 0, 1, 0, 0,  # X 红
            0, 1, 0, 0, 1, 0,  # Y 绿
            0, 0, 1, 0, 0, 1,  # Z 蓝
        ], dtype='f4')
        vbo_pos = self.ctx.buffer(vertices.tobytes())
        vbo_col = self.ctx.buffer(colors.tobytes())
        self.axis_vao = self.ctx.vertex_array(
            self.point_prog,
            [(vbo_pos, '3f', 'in_position'),
             (vbo_col, '3f', 'in_color')]
        )

    def _update_point_vbo(self):
        """更新点云 VBO。"""
        if not self._need_vbo_update or self.points is None:
            return

        # 合并位置和颜色到一个交错 VBO（更快）
        n = len(self.points)
        interleaved = np.zeros((n, 6), dtype='f4')
        interleaved[:, 0:3] = self.points
        interleaved[:, 3:6] = self.colors

        if self.point_vao:
            self.point_vao.release()

        vbo = self.ctx.buffer(interleaved.tobytes())
        self.point_vao = self.ctx.vertex_array(
            self.point_prog,
            [(vbo, '3f 3f', 'in_position', 'in_color')]
        )
        self._need_vbo_update = False

    def paintGL(self):
        if self.ctx is None:
            return

        self.ctx.clear(0.05, 0.05, 0.08, 1.0)

        # 计算 MVP 矩阵
        mvp = self._compute_mvp()
        mvp_bytes = np.array(mvp, dtype='f4').tobytes()

        # 绘制网格
        if self.grid_vao:
            self.grid_prog['mvp'].write(mvp_bytes)
            self.grid_vao.render(moderngl.LINES)

        # 绘制坐标轴
        if self.show_axis and self.axis_vao:
            self.ctx.line_width = 3.0
            self.point_prog['mvp'].write(mvp_bytes)
            self.axis_vao.render(moderngl.LINES)
            self.ctx.line_width = 1.0

        # 绘制点云
        self._update_point_vbo()
        if self.point_vao and self.points is not None and len(self.points) > 0:
            self.point_prog['mvp'].write(mvp_bytes)
            self.point_vao.render(moderngl.POINTS)

    def _compute_mvp(self) -> list:
        """计算 Model-View-Projection 矩阵。"""
        w, h = self.width(), self.height()

        # 投影矩阵
        fov = 70 if self.fps_mode else 60
        aspect = w / max(h, 1)
        near, far = 0.05, 200.0
        f = 1.0 / np.tan(np.radians(fov) / 2)
        proj = np.array([
            [f/aspect, 0, 0, 0],
            [0, f, 0, 0],
            [0, 0, (far+near)/(near-far), -1],
            [0, 0, 2*far*near/(near-far), 0]
        ], dtype='f4')

        # 视图矩阵
        if self.fps_mode:
            yaw_rad = np.radians(self.fp_yaw)
            pitch_rad = np.radians(self.fp_pitch)
            eye = self.fp_pos
            look = [
                eye[0] + np.cos(pitch_rad) * np.cos(yaw_rad),
                eye[1] + np.cos(pitch_rad) * np.sin(yaw_rad),
                eye[2] + np.sin(pitch_rad)
            ]
        else:
            yaw_rad = np.radians(self.orbit_yaw)
            pitch_rad = np.radians(self.orbit_pitch)
            eye = [
                self.orbit_target[0] + self.orbit_dist * np.cos(pitch_rad) * np.cos(yaw_rad),
                self.orbit_target[1] + self.orbit_dist * np.cos(pitch_rad) * np.sin(yaw_rad),
                self.orbit_target[2] + self.orbit_dist * np.sin(pitch_rad)
            ]
            look = self.orbit_target

        view = self._look_at(eye, look, [0, 0, 1])

        # MVP = proj * view
        mvp = proj @ view
        return mvp.flatten().tolist()

    def _look_at(self, eye, target, up) -> np.ndarray:
        """计算 look-at 视图矩阵。"""
        eye = np.array(eye, dtype='f4')
        target = np.array(target, dtype='f4')
        up = np.array(up, dtype='f4')

        f = target - eye
        f = f / np.linalg.norm(f)
        s = np.cross(f, up)
        s = s / np.linalg.norm(s)
        u = np.cross(s, f)

        m = np.eye(4, dtype='f4')
        m[0, 0:3] = s
        m[1, 0:3] = u
        m[2, 0:3] = -f
        m[0, 3] = -np.dot(s, eye)
        m[1, 3] = -np.dot(u, eye)
        m[2, 3] = np.dot(f, eye)
        return m

    def resizeGL(self, w, h):
        if self.ctx:
            self.ctx.viewport = (0, 0, w, h)

    def keyPressEvent(self, event):
        if event.isAutoRepeat(): return
        if event.key() == Qt.Key_F:
            self.toggle_fps_mode()
            return
        self._keys_pressed.add(event.key())

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat(): return
        self._keys_pressed.discard(event.key())

    def mousePressEvent(self, event):
        if not self.fps_mode:
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        if self.fps_mode:
            center = self.rect().center()
            dx = event.position().x() - center.x()
            dy = event.position().y() - center.y()
            if abs(dx) > 2 or abs(dy) > 2:
                self.fp_yaw += dx * 0.15
                self.fp_pitch -= dy * 0.15
                self.fp_pitch = max(-89, min(89, self.fp_pitch))
                QCursor.setPos(self.mapToGlobal(center))
            self.update()
        else:
            if self.last_mouse_pos is None: return
            dx = event.position().x() - self.last_mouse_pos.x()
            dy = event.position().y() - self.last_mouse_pos.y()
            if event.buttons() & Qt.LeftButton:
                self.orbit_yaw -= dx * 0.3
                self.orbit_pitch += dy * 0.3
                self.orbit_pitch = max(-89, min(89, self.orbit_pitch))
            elif event.buttons() & Qt.RightButton:
                yaw_rad = np.radians(self.orbit_yaw)
                scale = self.orbit_dist * 0.002
                self.orbit_target[0] += (-np.sin(yaw_rad) * dx + np.cos(yaw_rad) * dy) * scale
                self.orbit_target[1] += (np.cos(yaw_rad) * dx + np.sin(yaw_rad) * dy) * scale
                self.orbit_target[2] += dy * scale * 0.5
            self.last_mouse_pos = event.position()
            self.update()

    def wheelEvent(self, event):
        if not self.fps_mode:
            delta = event.angleDelta().y()
            self.orbit_dist *= 0.9 if delta > 0 else 1.1
            self.orbit_dist = max(0.5, min(100, self.orbit_dist))
            self.update()

    def reset_view(self):
        self.orbit_yaw = -45.0
        self.orbit_pitch = 30.0
        self.orbit_dist = 10.0
        self.orbit_target = [0.0, 0.0, 0.0]
        self.fp_pos = [5.0, 5.0, 3.0]
        self.fp_yaw = -135.0
        self.fp_pitch = 0.0
        if self.fps_mode:
            self.toggle_fps_mode()
        self.update()


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
        self.mode_label = QLabel("[轨道模式]")
        self.mode_label.setStyleSheet("color: #7c4dff; font-weight: bold;")
        ctrl.addWidget(self.mode_label)
        self.fps_label = QLabel("FPS: 0")
        ctrl.addWidget(self.fps_label)
        self.point_count_label = QLabel("点数: 0")
        ctrl.addWidget(self.point_count_label)
        ctrl.addWidget(QLabel("显示上限:"))
        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(1000, 500000)
        self.max_points_spin.setValue(100000)
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

        self.gl_widget = PointCloudGLWidget()
        self.gl_widget.setMinimumSize(400, 300)
        layout.addWidget(self.gl_widget, 1)

        self.debug_toggle = QPushButton("▼ 调试日志")
        self.debug_toggle.setCheckable(True)
        self.debug_toggle.toggled.connect(lambda v: (self.debug_text.setVisible(v), self.debug_toggle.setText("▲ 调试日志" if v else "▼ 调试日志")))
        layout.addWidget(self.debug_toggle)

        self.debug_text = QTextEdit()
        self.debug_text.setMaximumHeight(80)
        self.debug_text.setReadOnly(True)
        self.debug_text.setStyleSheet("font-family: Consolas; font-size: 11px;")
        self.debug_text.hide()
        layout.addWidget(self.debug_text)

        self.hint_label = QLabel("轨道: 左键旋转 | 右键平移 | 滚轮缩放  |  按 F 切换第一人称")
        self.hint_label.setStyleSheet("color: gray; font-size: 11px;")
        self.hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.hint_label)

        self.gl_widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.gl_widget and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key_F:
                self._update_mode_label()
        return super().eventFilter(obj, event)

    def _update_mode_label(self):
        if self.gl_widget.fps_mode:
            self.mode_label.setText("[第一人称]")
            self.hint_label.setText("WASD 移动 | 鼠标转向 | Space 上升 | Shift 下降 | F 切换")
        else:
            self.mode_label.setText("[轨道模式]")
            self.hint_label.setText("轨道: 左键旋转 | 右键平移 | 滚轮缩放  |  按 F 切换第一人称")

    def toggle_connection(self):
        if self.pointcloud_thread and self.pointcloud_thread.is_connected():
            self.disconnect_stream()
        else:
            self.connect_stream()

    def connect_stream(self):
        url = self.url_input.text().strip()
        topic = self.topic_input.currentText().strip()
        if not url or not topic: return
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
        super().closeEvent(event)
