"""
远程服务管理模块
================

通过 SSH 连接 OrangePi，远程启动/停止各种 ROS 服务。

本模块包含：
- SSHWorker: SSH 连接和命令执行线程
- RemoteServiceWidget: 远程服务管理界面
"""

from __future__ import annotations

import time
import threading
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QCheckBox,
    QTextEdit, QFrame
)


class SSHWorker(QThread):
    """SSH 命令执行线程。"""
    output_received = Signal(str)
    command_finished = Signal(int)  # return code
    connection_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self, host: str, username: str, password: str, parent=None):
        super().__init__(parent)
        self.host = host
        self.username = username
        self.password = password
        self.client = None
        self._running = False
        self._commands = []
        self._lock = threading.Lock()

    def run(self):
        import paramiko

        self._running = True
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.host,
                username=self.username,
                password=self.password,
                timeout=10
            )
            self.connection_changed.emit(True)
            self.output_received.emit(f"已连接到 {self.host}")

            # 保持连接，等待命令
            while self._running:
                with self._lock:
                    if self._commands:
                        cmd = self._commands.pop(0)
                    else:
                        cmd = None

                if cmd:
                    self._execute_command(cmd)
                else:
                    time.sleep(0.1)

        except Exception as e:
            self.error_occurred.emit(f"SSH 连接失败: {e}")
            self.connection_changed.emit(False)
        finally:
            if self.client:
                self.client.close()
            self.connection_changed.emit(False)

    def _execute_command(self, cmd: str):
        """执行远程命令并输出结果。"""
        try:
            self.output_received.emit(f">>> {cmd[:80]}...")
            # 执行命令，超时设为 10 秒
            stdin, stdout, stderr = self.client.exec_command(cmd, timeout=10)

            # 对于后台命令，立即返回
            if '&' in cmd:
                time.sleep(0.5)
                self.output_received.emit("[后台命令] 已发送")
                return

            exit_code = stdout.channel.recv_exit_status()

            # 读取输出
            out = stdout.read().decode('utf-8', errors='replace').strip()
            err = stderr.read().decode('utf-8', errors='replace').strip()

            if out:
                self.output_received.emit(out)
            if err:
                self.output_received.emit(f"[stderr] {err}")

            self.command_finished.emit(exit_code)
            self.output_received.emit(f"[完成] 退出码: {exit_code}")

        except Exception as e:
            self.error_occurred.emit(f"命令执行失败: {e}")

    def run_command(self, cmd: str):
        """添加命令到队列。"""
        with self._lock:
            self._commands.append(cmd)

    def stop(self):
        self._running = False
        if self.client:
            try:
                self.client.close()
            except:
                pass
        self.wait(3000)


class RemoteServiceWidget(QWidget):
    """
    远程服务管理界面。

    功能：
    - SSH 连接 OrangePi
    - 选择性启动/停止 ROS 服务
    - 实时显示命令输出
    """

    # 服务定义
    SERVICES = [
        {
            "name": "MAVROS",
            "desc": "飞控通信（遥测）",
            "cmd_start": "nohup bash -c 'source /opt/ros/noetic/setup.bash --extend; roslaunch mavros apm.launch fcu_url:=udp://:14555@192.168.144.15:14550' > /dev/null 2>&1 &",
            "cmd_stop": "pkill -f mavros",
            "check": "pgrep -f mavros",
        },
        {
            "name": "Livox 激光雷达",
            "desc": "MID360 点云数据源",
            "cmd_start": "nohup bash -c 'source /opt/ros/noetic/setup.bash --extend; source /home/orangepi/livox_ws/devel/setup.bash --extend; roslaunch livox_ros_driver2 msg_MID360s.launch' > /dev/null 2>&1 &",
            "cmd_stop": "pkill -f livox_ros_driver2",
            "check": "pgrep -f livox_ros_driver2",
        },
        {
            "name": "SLAM",
            "desc": "室内定位（FAST_LIO）",
            "cmd_start": "nohup bash -c 'source /opt/ros/noetic/setup.bash --extend; source /home/orangepi/tools_ws/devel/setup.bash --extend; rosrun manage_bridge_node manage_bridge_node' > /dev/null 2>&1 &",
            "cmd_stop": "pkill -f manage_bridge_node",
            "check": "pgrep -f manage_bridge_node",
        },
        {
            "name": "摄像头",
            "desc": "RealSense 下视摄像头",
            "cmd_start": "nohup bash -c 'source /opt/ros/noetic/setup.bash --extend; source /home/orangepi/ctrl_ws/devel/setup.bash --extend; roslaunch cam_pkg cam_pub.launch' > /dev/null 2>&1 &",
            "cmd_stop": "pkill -f cam_pub",
            "check": "pgrep -f cam_pub",
        },
        {
            "name": "web_video_server",
            "desc": "摄像头 HTTP 视频流",
            "cmd_start": "nohup bash -c 'source /opt/ros/noetic/setup.bash --extend; rosrun web_video_server web_video_server' > /dev/null 2>&1 &",
            "cmd_stop": "pkill -f web_video_server",
            "check": "pgrep -f web_video_server",
        },
        {
            "name": "rosbridge",
            "desc": "点云 WebSocket 流",
            "cmd_start": "nohup bash -c 'source /opt/ros/noetic/setup.bash --extend; roslaunch rosbridge_server rosbridge_websocket.launch' > /dev/null 2>&1 &",
            "cmd_stop": "pkill -f rosbridge",
            "check": "pgrep -f rosbridge",
        },
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ssh_worker = None
        self.service_checks = {}
        self.service_status = {}
        self._starting = False  # 防止重复启动
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # SSH 连接设置
        conn_group = QGroupBox("SSH 连接")
        conn_layout = QHBoxLayout(conn_group)
        conn_layout.addWidget(QLabel("主机:"))
        self.host_input = QLineEdit("10.209.49.217")
        self.host_input.setFixedWidth(150)
        conn_layout.addWidget(self.host_input)
        conn_layout.addWidget(QLabel("用户:"))
        self.user_input = QLineEdit("orangepi")
        self.user_input.setFixedWidth(100)
        conn_layout.addWidget(self.user_input)
        conn_layout.addWidget(QLabel("密码:"))
        self.pass_input = QLineEdit("orangepi")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setFixedWidth(100)
        conn_layout.addWidget(self.pass_input)
        self.conn_btn = QPushButton("连接")
        self.conn_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.conn_btn)
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        conn_layout.addWidget(self.status_label)
        conn_layout.addStretch()
        layout.addWidget(conn_group)

        # 服务管理
        services_group = QGroupBox("服务管理")
        services_layout = QVBoxLayout(services_group)

        # 全选/全不选
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(lambda: self._select_all(True))
        select_layout.addWidget(select_all_btn)
        select_none_btn = QPushButton("全不选")
        select_none_btn.clicked.connect(lambda: self._select_all(False))
        select_layout.addWidget(select_none_btn)
        select_layout.addStretch()

        # 状态刷新
        refresh_btn = QPushButton("刷新状态")
        refresh_btn.clicked.connect(self.check_all_status)
        select_layout.addWidget(refresh_btn)
        services_layout.addLayout(select_layout)

        # 服务列表
        for svc in self.SERVICES:
            row = QHBoxLayout()

            cb = QCheckBox(svc["name"])
            cb.setChecked(True)
            cb.setFixedWidth(150)
            self.service_checks[svc["name"]] = cb
            row.addWidget(cb)

            desc = QLabel(svc["desc"])
            desc.setStyleSheet("color: gray;")
            row.addWidget(desc)

            # 状态指示
            status = QLabel("●")
            status.setFixedWidth(20)
            status.setStyleSheet("color: gray;")
            self.service_status[svc["name"]] = status
            row.addWidget(status)

            row.addStretch()
            services_layout.addLayout(row)

        # 操作按钮
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("启动选中服务")
        start_btn.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 8px 16px;")
        start_btn.clicked.connect(self.start_selected)
        btn_layout.addWidget(start_btn)

        stop_btn = QPushButton("停止选中服务")
        stop_btn.setStyleSheet("background-color: #C62828; color: white; font-weight: bold; padding: 8px 16px;")
        stop_btn.clicked.connect(self.stop_selected)
        btn_layout.addWidget(stop_btn)

        start_all_btn = QPushButton("一键启动全部")
        start_all_btn.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; padding: 8px 16px;")
        start_all_btn.clicked.connect(self.start_all)
        btn_layout.addWidget(start_all_btn)

        services_layout.addLayout(btn_layout)
        layout.addWidget(services_group)

        # 输出日志
        log_group = QGroupBox("命令输出")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 11px; background-color: #1e1e1e; color: #d4d4d4;")
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_btn)

        layout.addWidget(log_group)

    def _select_all(self, checked: bool):
        for cb in self.service_checks.values():
            cb.setChecked(checked)

    def toggle_connection(self):
        if self.ssh_worker and self.ssh_worker.isRunning():
            self.disconnect_ssh()
        else:
            self.connect_ssh()

    def connect_ssh(self):
        host = self.host_input.text().strip()
        user = self.user_input.text().strip()
        password = self.pass_input.text().strip()

        if not host or not user:
            return

        self.disconnect_ssh()

        self.ssh_worker = SSHWorker(host, user, password)
        self.ssh_worker.output_received.connect(self.log)
        self.ssh_worker.error_occurred.connect(self.log_error)
        self.ssh_worker.connection_changed.connect(self.on_connection_changed)
        self.ssh_worker.start()

        self.conn_btn.setText("断开")
        self.status_label.setText("● 连接中...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")

    def disconnect_ssh(self):
        if self.ssh_worker:
            self.ssh_worker.stop()
            self.ssh_worker = None
        self.conn_btn.setText("连接")
        self.status_label.setText("● 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")

    def on_connection_changed(self, connected: bool):
        if connected:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.check_all_status()
        else:
            self.status_label.setText("● 连接断开")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def start_selected(self):
        if self._starting:
            return
        if not self.ssh_worker or not self.ssh_worker.isRunning():
            self.log("[错误] 请先连接 SSH")
            return

        self._starting = True
        try:
            for svc in self.SERVICES:
                if self.service_checks[svc["name"]].isChecked():
                    self.log(f"启动 {svc['name']}...")
                    cmd = svc['cmd_start']
                    self.ssh_worker.run_command(cmd)
                    time.sleep(1.0)  # 增加间隔，避免 SSH 过载

            # 延迟检查状态
            threading.Timer(5.0, self.check_all_status).start()
        finally:
            self._starting = False

    def stop_selected(self):
        if not self.ssh_worker or not self.ssh_worker.isRunning():
            self.log("[错误] 请先连接 SSH")
            return

        for svc in self.SERVICES:
            if self.service_checks[svc["name"]].isChecked():
                self.log(f"停止 {svc['name']}...")
                self.ssh_worker.run_command(svc["cmd_stop"])
                time.sleep(0.2)

        threading.Timer(1.0, self.check_all_status).start()

    def start_all(self):
        """一键启动全部服务。"""
        if self._starting:
            return
        self._select_all(True)
        self.start_selected()

    def check_all_status(self):
        """检查所有服务状态。"""
        if not self.ssh_worker or not self.ssh_worker.isRunning():
            return

        for svc in self.SERVICES:
            # 异步检查每个服务
            threading.Thread(
                target=self._check_service,
                args=(svc,),
                daemon=True
            ).start()

    def _check_service(self, svc: dict):
        """检查单个服务状态。"""
        try:
            stdin, stdout, stderr = self.ssh_worker.client.exec_command(svc["check"], timeout=5)
            exit_code = stdout.channel.recv_exit_status()
            alive = exit_code == 0

            status_widget = self.service_status[svc["name"]]
            if alive:
                status_widget.setText("●")
                status_widget.setStyleSheet("color: #2E7D32; font-weight: bold;")
                status_widget.setToolTip("运行中")
            else:
                status_widget.setText("●")
                status_widget.setStyleSheet("color: gray;")
                status_widget.setToolTip("已停止")
        except:
            pass

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")

    def log_error(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.append(f"<span style='color: red;'>[{ts}] {msg}</span>")

    def closeEvent(self, event):
        self.disconnect_ssh()
        super().closeEvent(event)
