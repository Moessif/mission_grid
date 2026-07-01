"""
3D 点云预览模块
================

通过 rosbridge_server 订阅 ROS 点云话题，并使用 OpenGL 进行高效渲染。

优化策略：
- 默认订阅 FAST-LIO 的 /cloud_registered_body，而不是原始 /livox/lidar
- 使用 rosbridge 的 throttle_rate + queue_length，避免消息堆积
- 后台线程中完成点云解析与降采样，UI 线程只负责渲染
- 使用 GLScatterPlotItem 进行 GPU 点绘制
"""

from __future__ import annotations

import base64
import json
import math
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .material_theme import COLORS as c

try:
    from pyqtgraph import Vector
    import pyqtgraph.opengl as gl
except Exception as exc:  # pragma: no cover - optional runtime dependency
    Vector = None
    gl = None
    _GL_IMPORT_ERROR = exc
else:
    _GL_IMPORT_ERROR = None

try:
    import websocket
except Exception as exc:  # pragma: no cover - optional runtime dependency
    websocket = None
    _WS_IMPORT_ERROR = exc
else:
    _WS_IMPORT_ERROR = None


POINT_FIELD_DTYPES = {
    1: "i1",  # INT8
    2: "u1",  # UINT8
    3: "i2",  # INT16
    4: "u2",  # UINT16
    5: "i4",  # INT32
    6: "u4",  # UINT32
    7: "f4",  # FLOAT32
    8: "f8",  # FLOAT64
}


@dataclass
class CloudStats:
    topic: str
    points: int
    rendered_points: int
    fps: float


def _make_structured_dtype(fields: Iterable[dict], point_step: int, bigendian: bool) -> Optional[np.dtype]:
    names = []
    formats = []
    offsets = []
    endian = ">" if bigendian else "<"
    wanted = {"x", "y", "z", "intensity", "rgb", "rgba"}
    for field in fields:
        name = field.get("name")
        if name not in wanted:
            continue
        dtype_code = POINT_FIELD_DTYPES.get(field.get("datatype"))
        if not dtype_code:
            continue
        names.append(name)
        formats.append(endian + dtype_code)
        offsets.append(int(field.get("offset", 0)))
    if not {"x", "y", "z"} <= set(names):
        return None
    return np.dtype(
        {
            "names": names,
            "formats": formats,
            "offsets": offsets,
            "itemsize": int(point_step),
        }
    )


def _decode_rosbridge_data(raw_data) -> bytes:
    if isinstance(raw_data, str):
        try:
            return base64.b64decode(raw_data)
        except Exception:
            return raw_data.encode("latin1", errors="ignore")
    if isinstance(raw_data, list):
        return bytes(raw_data)
    if isinstance(raw_data, (bytes, bytearray)):
        return bytes(raw_data)
    return b""


def _extract_colors_from_struct(arr: np.ndarray) -> np.ndarray:
    if "rgba" in arr.dtype.names:
        rgb_field = arr["rgba"].view(np.uint32)
    elif "rgb" in arr.dtype.names:
        rgb_field = arr["rgb"].view(np.uint32)
    else:
        rgb_field = None

    if rgb_field is not None:
        rgb = np.empty((len(arr), 4), dtype=np.float32)
        rgb[:, 0] = ((rgb_field >> 16) & 0xFF) / 255.0
        rgb[:, 1] = ((rgb_field >> 8) & 0xFF) / 255.0
        rgb[:, 2] = (rgb_field & 0xFF) / 255.0
        rgb[:, 3] = 0.95
        return rgb

    if "intensity" in arr.dtype.names:
        intensity = np.asarray(arr["intensity"], dtype=np.float32)
        finite = np.isfinite(intensity)
        if finite.any():
            lo = float(np.min(intensity[finite]))
            hi = float(np.max(intensity[finite]))
            if hi - lo < 1e-6:
                norm = np.full_like(intensity, 0.8, dtype=np.float32)
            else:
                norm = np.clip((intensity - lo) / (hi - lo), 0.0, 1.0)
        else:
            norm = np.full_like(intensity, 0.8, dtype=np.float32)
        colors = np.empty((len(arr), 4), dtype=np.float32)
        colors[:, 0] = 0.15 + 0.85 * norm
        colors[:, 1] = 0.45 + 0.45 * norm
        colors[:, 2] = 1.0 - 0.55 * norm
        colors[:, 3] = 0.92
        return colors

    colors = np.empty((len(arr), 4), dtype=np.float32)
    colors[:] = (0.12, 0.69, 0.97, 0.92)
    return colors


def _downsample(points: np.ndarray, colors: np.ndarray, max_points: int) -> Tuple[np.ndarray, np.ndarray]:
    if len(points) <= max_points:
        return points, colors
    step = max(1, math.ceil(len(points) / max_points))
    return points[::step][:max_points], colors[::step][:max_points]


def _parse_pointcloud2(msg: dict, max_points: int) -> Optional[Tuple[np.ndarray, np.ndarray, int]]:
    dtype = _make_structured_dtype(
        msg.get("fields", []),
        int(msg.get("point_step", 0)),
        bool(msg.get("is_bigendian", False)),
    )
    if dtype is None:
        return None
    width = int(msg.get("width", 0))
    height = int(msg.get("height", 1))
    total_points = max(0, width * height)
    payload = _decode_rosbridge_data(msg.get("data"))
    if not payload or total_points <= 0:
        return None
    arr = np.frombuffer(payload, dtype=dtype, count=total_points)
    points = np.column_stack((arr["x"], arr["y"], arr["z"])).astype(np.float32, copy=False)
    mask = np.isfinite(points).all(axis=1)
    points = points[mask]
    arr = arr[mask]
    if len(points) == 0:
        return None
    colors = _extract_colors_from_struct(arr)
    points, colors = _downsample(points, colors, max_points)
    return points, colors, total_points


def _parse_livox_custom(msg: dict, max_points: int) -> Optional[Tuple[np.ndarray, np.ndarray, int]]:
    points = msg.get("points") or []
    total_points = len(points)
    if total_points == 0:
        return None
    step = max(1, math.ceil(total_points / max_points))
    sampled = points[::step][:max_points]
    pos = np.asarray(
        [[p.get("x", 0.0), p.get("y", 0.0), p.get("z", 0.0)] for p in sampled],
        dtype=np.float32,
    )
    refl = np.asarray([p.get("reflectivity", 0.0) for p in sampled], dtype=np.float32)
    if len(pos) == 0:
        return None
    finite = np.isfinite(refl)
    if finite.any():
        lo = float(np.min(refl[finite]))
        hi = float(np.max(refl[finite]))
        if hi - lo < 1e-6:
            norm = np.full_like(refl, 0.8)
        else:
            norm = np.clip((refl - lo) / (hi - lo), 0.0, 1.0)
    else:
        norm = np.full_like(refl, 0.8)
    colors = np.empty((len(pos), 4), dtype=np.float32)
    colors[:, 0] = 0.20 + 0.80 * norm
    colors[:, 1] = 0.35 + 0.60 * norm
    colors[:, 2] = 1.0 - 0.55 * norm
    colors[:, 3] = 0.92
    return pos, colors, total_points


class RosPointCloudThread(QThread):
    cloud_ready = Signal(object, object, object)
    status_changed = Signal(str, bool)
    error_occurred = Signal(str)

    def __init__(self, url: str, topic: str, throttle_ms: int, max_points: int, parent=None):
        super().__init__(parent)
        self.url = url
        self.topic = topic
        self.throttle_ms = throttle_ms
        self.max_points = max_points
        self._running = False
        self._ws = None
        self._frame_times: list[float] = []

    def run(self):
        if websocket is None:
            self.error_occurred.emit(f"缺少 websocket-client 依赖: {_WS_IMPORT_ERROR}")
            return
        self._running = True
        try:
            self._ws = websocket.create_connection(self.url, timeout=3)
            self._ws.settimeout(1.0)
            self._ws.send(
                json.dumps(
                    {
                        "op": "subscribe",
                        "topic": self.topic,
                        "queue_length": 1,
                        "throttle_rate": self.throttle_ms,
                    }
                )
            )
            self.status_changed.emit(f"已连接 {self.topic}", True)
            while self._running:
                try:
                    raw = self._ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception as exc:
                    if self._running:
                        self.error_occurred.emit(f"点云连接中断: {exc}")
                    break
                if not raw:
                    continue
                now = time.perf_counter()
                self._frame_times.append(now)
                if len(self._frame_times) > 20:
                    self._frame_times = self._frame_times[-20:]
                if len(self._frame_times) >= 2:
                    dt = self._frame_times[-1] - self._frame_times[0]
                    fps = (len(self._frame_times) - 1) / dt if dt > 1e-6 else 0.0
                else:
                    fps = 0.0
                self._handle_message(raw, fps)
        except Exception as exc:
            self.error_occurred.emit(f"无法连接 rosbridge: {exc}")
        finally:
            self._cleanup()
            self.status_changed.emit("未连接", False)

    def _handle_message(self, raw, fps: float) -> Optional[CloudStats]:
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except Exception:
                return None
        try:
            envelope = json.loads(raw)
        except Exception:
            return None
        if envelope.get("op") != "publish":
            return None
        msg = envelope.get("msg") or {}
        parsed = None
        if "fields" in msg and "data" in msg:
            parsed = _parse_pointcloud2(msg, self.max_points)
        elif "points" in msg:
            parsed = _parse_livox_custom(msg, self.max_points)
        if parsed is None:
            return None
        points, colors, total_points = parsed
        stats = CloudStats(
            topic=self.topic,
            points=total_points,
            rendered_points=len(points),
            fps=fps,
        )
        self.cloud_ready.emit(points, colors, stats)
        return stats

    def stop(self):
        self._running = False
        self._cleanup()
        self.wait(3000)

    def _cleanup(self):
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None


class PointCloudViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if gl is None:
            self._view = None
            hint = QLabel(f"缺少点云渲染依赖: {_GL_IMPORT_ERROR}")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet(f"color:{c.on_surface_variant}; font-size:13px;")
            layout.addWidget(hint, 1)
            return

        self._view = gl.GLViewWidget()
        self._view.setMinimumHeight(520)
        self._view.setBackgroundColor((15, 18, 24))
        self._view.opts["distance"] = 8
        self._view.opts["elevation"] = 18
        self._view.opts["azimuth"] = 42
        layout.addWidget(self._view, 1)

        grid = gl.GLGridItem(color=(70, 78, 92, 130))
        grid.scale(0.5, 0.5, 0.5)
        grid.setSize(8, 8)
        self._view.addItem(grid)
        self._grid = grid

        axis = gl.GLAxisItem()
        axis.setSize(1.0, 1.0, 1.0)
        self._view.addItem(axis)
        self._axis = axis

        self._scatter = gl.GLScatterPlotItem(pos=np.zeros((1, 3), dtype=np.float32), size=0.05, pxMode=False)
        self._view.addItem(self._scatter)
        self._point_size = 0.04

    def set_point_size(self, size_m: float):
        self._point_size = size_m

    def reset_view(self):
        if self._view is None:
            return
        self._view.opts["distance"] = 8
        self._view.opts["elevation"] = 18
        self._view.opts["azimuth"] = 42
        self._view.opts["center"] = Vector(0.0, 0.0, 0.0)
        self._view.update()

    def update_cloud(self, points: np.ndarray, colors: np.ndarray):
        if self._view is None:
            return
        if len(points) == 0:
            return
        self._scatter.setData(pos=points, color=colors, size=self._point_size, pxMode=False)
        center = np.mean(points, axis=0)
        span = np.max(points, axis=0) - np.min(points, axis=0)
        radius = max(1.2, float(np.linalg.norm(span)))
        self._view.opts["center"] = Vector(float(center[0]), float(center[1]), float(center[2]))
        self._view.opts["distance"] = min(max(radius * 1.25, 3.0), 30.0)
        self._view.update()


class LidarWidget(QWidget):
    DEFAULT_URL = "ws://10.209.49.217:9090"
    TOPIC_CHOICES = [
        "/cloud_registered_body",
        "/cloud_registered",
        "/Laser_map",
        "/livox/lidar",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stream_thread: Optional[RosPointCloudThread] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        controls = QGroupBox("点云连接设置")
        form = QFormLayout(controls)

        self.url_input = QLineEdit(self.DEFAULT_URL)
        self.url_input.setPlaceholderText("ws://<机载IP>:9090")
        form.addRow("rosbridge", self.url_input)

        self.topic_combo = QComboBox()
        self.topic_combo.setEditable(True)
        self.topic_combo.addItems(self.TOPIC_CHOICES)
        self.topic_combo.setCurrentText("/cloud_registered_body")
        form.addRow("点云话题", self.topic_combo)

        self.throttle_spin = QSpinBox()
        self.throttle_spin.setRange(50, 2000)
        self.throttle_spin.setSingleStep(50)
        self.throttle_spin.setSuffix(" ms")
        self.throttle_spin.setValue(150)
        form.addRow("节流周期", self.throttle_spin)

        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(1000, 100000)
        self.max_points_spin.setSingleStep(1000)
        self.max_points_spin.setValue(12000)
        form.addRow("最大渲染点数", self.max_points_spin)

        self.point_size_spin = QSpinBox()
        self.point_size_spin.setRange(1, 20)
        self.point_size_spin.setValue(4)
        form.addRow("点尺寸", self.point_size_spin)

        layout.addWidget(controls)

        action_row = QHBoxLayout()
        self.connect_btn = QPushButton("连接点云")
        self.connect_btn.clicked.connect(self.toggle_connection)
        action_row.addWidget(self.connect_btn)

        self.reset_btn = QPushButton("重置视角")
        self.reset_btn.setProperty("cssClass", "outlined")
        self.reset_btn.clicked.connect(self._reset_view)
        action_row.addWidget(self.reset_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        stats_row = QHBoxLayout()
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        stats_row.addWidget(self.status_label)

        self.info_label = QLabel("推荐话题: /cloud_registered_body")
        self.info_label.setStyleSheet(f"color:{c.on_surface_variant};")
        stats_row.addWidget(self.info_label, 1)
        layout.addLayout(stats_row)

        self.view = PointCloudViewWidget()
        layout.addWidget(self.view, 1)

        hint = QLabel("推荐使用 FAST-LIO 的 /cloud_registered_body。原始 /livox/lidar 点数更大，帧率会明显更低。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{c.on_surface_variant}; font-size:12px;")
        layout.addWidget(hint)

        if gl is not None:
            self._apply_point_size()
        self.point_size_spin.valueChanged.connect(self._apply_point_size)

    def _apply_point_size(self):
        if gl is None:
            return
        self.view.set_point_size(self.point_size_spin.value() / 100.0)

    def _reset_view(self):
        self.view.reset_view()

    def toggle_connection(self):
        if self.stream_thread is not None:
            self.disconnect_stream()
        else:
            self.connect_stream()

    def connect_stream(self):
        if websocket is None:
            self._set_status(f"● 缺少依赖: {_WS_IMPORT_ERROR}", "red")
            return
        url = self.url_input.text().strip()
        topic = self.topic_combo.currentText().strip()
        if not url or not topic:
            return
        self.disconnect_stream()
        self.stream_thread = RosPointCloudThread(
            url=url,
            topic=topic,
            throttle_ms=self.throttle_spin.value(),
            max_points=self.max_points_spin.value(),
        )
        self.stream_thread.cloud_ready.connect(self._on_cloud_ready)
        self.stream_thread.status_changed.connect(self._on_status_changed)
        self.stream_thread.error_occurred.connect(self._on_error)
        self.stream_thread.start()
        self.connect_btn.setText("断开点云")
        self._set_status("● 连接中...", "orange")

    def disconnect_stream(self):
        if self.stream_thread is not None:
            self.stream_thread.stop()
            self.stream_thread = None
        self.connect_btn.setText("连接点云")
        self._set_status("● 未连接", "gray")

    def _on_cloud_ready(self, points: np.ndarray, colors: np.ndarray, stats: CloudStats):
        self.view.update_cloud(points, colors)
        self.info_label.setText(
            f"{stats.topic}  |  原始 {stats.points} 点  |  渲染 {stats.rendered_points} 点  |  {stats.fps:.1f} FPS"
        )

    def _on_status_changed(self, text: str, connected: bool):
        if connected:
            self._set_status("● 已连接", "#2E7D32")
            self.info_label.setText(text)
        elif self.stream_thread is not None:
            self.connect_btn.setText("连接点云")
            self._set_status("● 连接断开", "red")

    def _on_error(self, message: str):
        self.info_label.setText(message)
        self._set_status("● 错误", "red")
        self.connect_btn.setText("连接点云")

    def _set_status(self, text: str, color: str):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def closeEvent(self, event):
        self.disconnect_stream()
        super().closeEvent(event)
