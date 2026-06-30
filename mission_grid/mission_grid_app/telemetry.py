"""
MAVLink 遥测模块
================

通过 MAVLink UDP 协议接收无人机遥测数据的后台线程。

本模块包含：
- TelemetryWorker: QThread 子类，后台接收 MAVLink 消息并发射 Qt 信号

依赖关系：
    pymavlink（外部库）← 本模块（MAVLink 协议处理）
    PySide6.QtCore ← 本模块（QThread, Signal）
    本模块 → main_window（被 MainWindow 持有，信号连接到遥测处理槽函数）

接收的 MAVLink 消息类型：
    - LOCAL_POSITION_NED (#32): 本地位置 (x, y, z)，发射 position_updated 信号
    - HEARTBEAT (#0): 心跳包，解析解锁状态和飞行模式，发射 status_updated 信号

发送的 MAVLink 消息：
    - HEARTBEAT: 地面站心跳（由 MainWindow 定时调用 send_heartbeat）

通信参数：
    - 协议: UDP
    - 默认端口: 14550
    - 源: 机载电脑桥接节点 (manage_bridge_node)
"""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal


class TelemetryWorker(QThread):
    """
    MAVLink 遥测后台线程。

    在独立线程中持续接收 MAVLink UDP 消息，
    通过 Qt 信号将数据传递到主线程的 UI 组件。

    信号：
        position_updated(x, y, z):  本地位置更新 (NED 坐标, 单位: 米)
        status_updated(dict):       飞行状态更新 {armed: bool, mode: int}
        node_status_updated(int):   节点状态位掩码更新
    """

    # Qt 信号定义（跨线程安全）
    position_updated = Signal(float, float, float)
    status_updated = Signal(dict)
    node_status_updated = Signal(int)

    def __init__(self, bind_port: int = 14550, parent=None):
        """
        初始化遥测线程。

        参数:
            bind_port: UDP 监听端口（默认 14550，与机载桥接节点匹配）
        """
        super().__init__(parent)
        self.bind_port = bind_port
        self._running = False
        self._mavlink_conn = None

    def run(self):
        """
        线程主循环。

        1. 尝试建立 MAVLink UDP 连接
        2. 等待心跳包（5秒超时）
        3. 循环接收消息并分发处理
        4. 线程退出时关闭连接
        """
        self._running = True
        try:
            from pymavlink import mavutil
            self._mavlink_conn = mavutil.mavlink_connection(f'udp:0.0.0.0:{self.bind_port}')
            self._mavlink_conn.wait_heartbeat(timeout=5)
        except Exception:
            pass  # 连接失败静默处理（可能未连接飞控）
        while self._running:
            try:
                if self._mavlink_conn:
                    msg = self._mavlink_conn.recv_match(blocking=True, timeout=1.0)
                    if msg:
                        self._handle_msg(msg)
            except Exception:
                pass
        if self._mavlink_conn:
            self._mavlink_conn.close()

    def _handle_msg(self, msg):
        """
        消息分发处理。

        LOCAL_POSITION_NED → position_updated 信号
        HEARTBEAT → status_updated 信号（解析解锁状态和飞行模式）
        CM_STATUS → node_status_updated 信号（节点状态位掩码）
        """
        msg_type = msg.get_type()
        if msg_type == 'LOCAL_POSITION_NED':
            self.position_updated.emit(msg.x, msg.y, msg.z)
        elif msg_type == 'HEARTBEAT':
            armed = bool(msg.base_mode & 128)  # bit7 = ARMED
            mode = msg.custom_mode
            self.status_updated.emit({"armed": armed, "mode": mode})
        elif msg_type == 'CM_STATUS':
            # 节点状态位掩码（自定义消息）
            bitmask = getattr(msg, 'bitmask', 0)
            self.node_status_updated.emit(bitmask)

    def send_heartbeat(self):
        """
        发送地面站心跳包。

        由 MainWindow 的 QTimer 每秒调用一次，
        保持 MAVLink 连接活跃并让飞控知道地面站在线。
        心跳参数: type=6(GCS), autopilot=8(通用), base_mode=0, custom_mode=0
        """
        if self._mavlink_conn:
            try:
                self._mavlink_conn.mav.heartbeat_send(6, 8, 0, 0, 0)
            except Exception:
                pass

    def stop(self):
        """
        停止遥测线程。

        设置退出标志并等待线程结束（最多 3 秒）。
        """
        self._running = False
        self.wait(3000)
