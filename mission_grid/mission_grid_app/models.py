"""
数据模型模块
============

定义 MissionGrid 地面站的核心数据结构，是整个应用的数据层基础。

本模块包含：
- 网格常量（列数、行数、格子尺寸）
- 标签常量（A1-A9 列标签、B1-B7 行标签）
- 触发条件定义（TRIGGER_CONDITIONS、MAIN_TASK_GLOBAL_CONDITIONS）
- CellAction 数据类：单个格子的动作配置
- GridConfig 数据类：全局网格配置（含坐标转换、禁飞区、主线任务等）

依赖关系：
    本模块无内部依赖，被所有其他模块引用。

坐标系统：
    - 网格坐标: (col, row), col=0~8 (A1~A9), row=0~6 (B1~B7)
    - X 轴: A9→A1 方向, X = (8 - col) * 0.5
    - Y 轴: B1→B7 方向, Y = row * 0.5
    - 原点: A9B1 (col=8, row=0) 对应物理坐标 (0, 0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# 网格常量
# ============================================================

COLS = 9          # 网格列数 (A1~A9)
ROWS = 7          # 网格行数 (B1~B7)
CELL_SIZE = 0.5   # 格子物理尺寸 (米)

# 列标签: A1, A2, ..., A9
COL_LABELS = [f"A{i+1}" for i in range(COLS)]
# 行标签: B1, B2, ..., B7
ROW_LABELS = [f"B{i+1}" for i in range(ROWS)]


# ============================================================
# 触发条件定义
# ============================================================

# 单个动作的触发条件（可多选，AND 逻辑）
TRIGGER_CONDITIONS = [
    ("always", "每次经过"),           # 每次到达该格子都执行
    ("first_visit", "首次经过"),      # 仅第一次到达时执行
    ("last_visit", "最后经过"),       # 仅最后一次到达时执行
    ("main_task_done", "主线完成后"), # 主线任务全部完成后才执行
]

# 主线任务全局完成条件（可多选，AND 逻辑）
MAIN_TASK_GLOBAL_CONDITIONS = [
    ("all_visited", "所有格子已遍历"),
    ("all_actions_done", "所有非降落动作已执行"),
    ("all_detect_done", "所有动物检测已完成"),
    ("all_qr_done", "所有二维码已扫描"),
    ("all_photo_done", "所有拍照已完成"),
]


# ============================================================
# 数据类
# ============================================================

@dataclass
class CellAction:
    """
    单个格子的动作配置。

    属性:
        action_type: 动作类型标识符，如 "takeoff", "photo", "yolo_detect" 等
        params: 动作参数字典，不同动作类型有不同的参数
        triggers: 触发条件列表，默认 ["always"]，多条件为 AND 关系
    """
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    triggers: List[str] = field(default_factory=lambda: ["always"])


CellState = str

CELL_STATE_CLEAR = "clear"
CELL_STATE_KNOWN_NO_FLY = "known_no_fly"
CELL_STATE_UNKNOWN_NO_FLY = "unknown_no_fly"
CELL_STATE_OBSTACLE = "obstacle"


@dataclass
class GridConfig:
    """
    全局网格配置，包含网格尺寸、起飞点、动作、禁飞区、主线任务等全部状态。

    这是应用的核心数据对象，在 MainWindow、GridWidget、ActionEditor、
    PathPlanner、CodeGenerator 之间共享传递。

    属性:
        cols/rows: 网格尺寸（默认 9x7）
        cell_size: 格子物理尺寸（默认 0.5m）
        takeoff_col/row: 起飞点网格坐标（默认 A9B1）
        flight_altitude: 飞行高度（米）
        actions: 动作映射 {(col, row): [CellAction, ...]}
        known_no_fly: 起飞前已知禁飞区
        unknown_no_fly: 起飞前未知、飞行中可发现的禁飞区
        obstacles: 起飞后扫描发现的障碍物
        discovered_unknown_no_fly: 飞行中已发现的未知禁飞区
        discovered_obstacles: 飞行中已发现的障碍物
        fence_*: 电子围栏边界（米）
        custom_waypoints: 手动编辑的航点序列
        main_task_cells: 主线任务格子集合
        main_task_conditions: 主线任务全局完成条件列表
    """
    cols: int = COLS
    rows: int = ROWS
    cell_size: float = CELL_SIZE
    takeoff_col: int = 8              # 默认起飞: A9B1
    takeoff_row: int = 0
    flight_altitude: float = 1.2      # 默认飞行高度 1.2m
    actions: Dict[Tuple[int, int], List[CellAction]] = field(default_factory=dict)
    known_no_fly: set = field(default_factory=set)
    unknown_no_fly: set = field(default_factory=set)
    obstacles: set = field(default_factory=set)
    discovered_unknown_no_fly: set = field(default_factory=set)
    discovered_obstacles: set = field(default_factory=set)
    fence_min_x: float = 0.0
    fence_max_x: float = 4.0
    fence_min_y: float = 0.0
    fence_max_y: float = 3.0
    custom_waypoints: List[Tuple[int, int]] = field(default_factory=list)
    main_task_cells: set = field(default_factory=set)
    main_task_conditions: List[str] = field(default_factory=list)

    # ----------------------------------------------------------
    # 坐标转换
    # ----------------------------------------------------------

    def cell_label(self, col: int, row: int) -> str:
        """返回格子的人类可读标签，如 'A1B1', 'A9B7'"""
        return f"{COL_LABELS[col]}{ROW_LABELS[row]}"

    def grid_to_xy(self, col: int, row: int) -> Tuple[float, float]:
        """
        网格坐标 → 物理坐标（米）。
        X: A9→A1 方向递增, Y: B1→B7 方向递增。
        """
        x = (self.cols - 1 - col) * self.cell_size
        y = row * self.cell_size
        return x, y

    def xy_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """物理坐标（米）→ 最近的网格坐标。"""
        col = round((x / self.cell_size) - (self.cols - 1))
        col = max(0, min(self.cols - 1, -col))
        row = round(y / self.cell_size)
        row = max(0, min(self.rows - 1, row))
        return col, row

    # ----------------------------------------------------------
    # 动作查询与操作
    # ----------------------------------------------------------

    def has_action(self, col: int, row: int) -> bool:
        """指定格子是否有动作配置。"""
        return (col, row) in self.actions and len(self.actions[(col, row)]) > 0

    def in_bounds(self, col: int, row: int) -> bool:
        """指定格子是否在网格范围内。"""
        return 0 <= col < self.cols and 0 <= row < self.rows

    @property
    def no_fly(self) -> set:
        """兼容旧接口：等价于起飞前已知禁飞区。"""
        return self.known_no_fly

    @no_fly.setter
    def no_fly(self, value: set):
        self.known_no_fly = set(value)

    def is_known_no_fly(self, col: int, row: int) -> bool:
        return (col, row) in self.known_no_fly

    def is_unknown_no_fly(self, col: int, row: int) -> bool:
        return (col, row) in self.unknown_no_fly

    def is_obstacle(self, col: int, row: int) -> bool:
        return (col, row) in self.obstacles

    def is_discovered_unknown_no_fly(self, col: int, row: int) -> bool:
        return (col, row) in self.discovered_unknown_no_fly

    def is_discovered_obstacle(self, col: int, row: int) -> bool:
        return (col, row) in self.discovered_obstacles

    def is_no_fly(self, col: int, row: int) -> bool:
        """兼容旧接口：已知禁飞区或已发现的未知禁飞区。"""
        return self.is_known_no_fly(col, row) or self.is_discovered_unknown_no_fly(col, row)

    def is_blocked_preflight(self, col: int, row: int) -> bool:
        """起飞前规划视图：只避开已知禁飞区。"""
        return self.is_known_no_fly(col, row)

    def is_blocked_runtime(self, col: int, row: int) -> bool:
        """运行时规划视图：避开已知禁飞区和已发现风险。"""
        return (
            self.is_known_no_fly(col, row)
            or self.is_discovered_unknown_no_fly(col, row)
            or self.is_discovered_obstacle(col, row)
        )

    def _clear_static_cell_state(self, col: int, row: int):
        cell = (col, row)
        self.known_no_fly.discard(cell)
        self.unknown_no_fly.discard(cell)
        self.obstacles.discard(cell)
        self.discovered_unknown_no_fly.discard(cell)
        self.discovered_obstacles.discard(cell)

    def set_cell_state(self, col: int, row: int, state: CellState):
        """
        设置格子的静态状态。
        同一格只能属于一种风险类型；设为风险格时自动清除动作配置。
        """
        cell = (col, row)
        self._clear_static_cell_state(col, row)
        if state == CELL_STATE_CLEAR:
            return
        if state == CELL_STATE_KNOWN_NO_FLY:
            self.known_no_fly.add(cell)
        elif state == CELL_STATE_UNKNOWN_NO_FLY:
            self.unknown_no_fly.add(cell)
        elif state == CELL_STATE_OBSTACLE:
            self.obstacles.add(cell)
        else:
            raise ValueError(f"未知格子状态: {state}")
        self.actions.pop(cell, None)

    def clear_cell_state(self, col: int, row: int):
        """清除格子的所有风险状态。"""
        self.set_cell_state(col, row, CELL_STATE_CLEAR)

    def get_static_cell_state(self, col: int, row: int) -> CellState:
        """返回格子的静态编辑状态。"""
        if self.is_known_no_fly(col, row):
            return CELL_STATE_KNOWN_NO_FLY
        if self.is_unknown_no_fly(col, row):
            return CELL_STATE_UNKNOWN_NO_FLY
        if self.is_obstacle(col, row):
            return CELL_STATE_OBSTACLE
        return CELL_STATE_CLEAR

    def get_runtime_cell_state(self, col: int, row: int) -> CellState:
        """返回格子的运行时已知状态。"""
        if self.is_known_no_fly(col, row):
            return CELL_STATE_KNOWN_NO_FLY
        if self.is_discovered_unknown_no_fly(col, row):
            return CELL_STATE_UNKNOWN_NO_FLY
        if self.is_discovered_obstacle(col, row):
            return CELL_STATE_OBSTACLE
        return CELL_STATE_CLEAR

    def set_action(self, col: int, row: int, action_list: List[CellAction]):
        """
        设置格子的动作列表。传入空列表则删除该格子的动作配置。
        """
        if action_list:
            self.actions[(col, row)] = action_list
        elif (col, row) in self.actions:
            del self.actions[(col, row)]

    def toggle_no_fly(self, col: int, row: int):
        """
        兼容旧接口：切换“已知禁飞区”状态。
        """
        if self.is_known_no_fly(col, row):
            self.clear_cell_state(col, row)
        else:
            self.set_cell_state(col, row, CELL_STATE_KNOWN_NO_FLY)

    def reset_runtime_discovery(self):
        """清空飞行中发现状态。"""
        self.discovered_unknown_no_fly.clear()
        self.discovered_obstacles.clear()

    def discover_cell(self, col: int, row: int) -> Optional[CellState]:
        """发现单个格子的隐藏风险，返回发现到的状态。"""
        cell = (col, row)
        if cell in self.unknown_no_fly and cell not in self.discovered_unknown_no_fly:
            self.discovered_unknown_no_fly.add(cell)
            return CELL_STATE_UNKNOWN_NO_FLY
        if cell in self.obstacles and cell not in self.discovered_obstacles:
            self.discovered_obstacles.add(cell)
            return CELL_STATE_OBSTACLE
        return None

    def discover_cells_around(self, col: int, row: int, radius: int) -> List[Tuple[int, int, CellState]]:
        """扫描当前位置周围格子，返回本次新发现的风险。"""
        discovered: List[Tuple[int, int, CellState]] = []
        radius_sq = max(radius, 0) ** 2
        for dc in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                nc = col + dc
                nr = row + dr
                if not self.in_bounds(nc, nr):
                    continue
                if dc * dc + dr * dr > radius_sq:
                    continue
                state = self.discover_cell(nc, nr)
                if state:
                    discovered.append((nc, nr, state))
        return discovered

    def discover_cells_with_radii(
        self,
        col: int,
        row: int,
        unknown_no_fly_radius: int,
        obstacle_radius: int,
    ) -> List[Tuple[int, int, CellState]]:
        """按不同风险类型使用不同感知半径进行扫描。"""
        discovered: List[Tuple[int, int, CellState]] = []
        max_radius = max(unknown_no_fly_radius, obstacle_radius, 0)
        unknown_radius_sq = max(unknown_no_fly_radius, 0) ** 2
        obstacle_radius_sq = max(obstacle_radius, 0) ** 2
        for dc in range(-max_radius, max_radius + 1):
            for dr in range(-max_radius, max_radius + 1):
                nc = col + dc
                nr = row + dr
                if not self.in_bounds(nc, nr):
                    continue
                dist_sq = dc * dc + dr * dr
                cell = (nc, nr)
                if (
                    cell in self.unknown_no_fly
                    and cell not in self.discovered_unknown_no_fly
                    and dist_sq <= unknown_radius_sq
                ):
                    self.discovered_unknown_no_fly.add(cell)
                    discovered.append((nc, nr, CELL_STATE_UNKNOWN_NO_FLY))
                    continue
                if (
                    cell in self.obstacles
                    and cell not in self.discovered_obstacles
                    and dist_sq <= obstacle_radius_sq
                ):
                    self.discovered_obstacles.add(cell)
                    discovered.append((nc, nr, CELL_STATE_OBSTACLE))
        return discovered

    def runtime_blocked_cells(self) -> set:
        """返回运行时已知阻塞格集合。"""
        return set(self.known_no_fly) | set(self.discovered_unknown_no_fly) | set(self.discovered_obstacles)

    def action_cells(self) -> List[Tuple[int, int]]:
        """返回所有有动作的格子坐标列表（已排序）。"""
        return sorted(self.actions.keys())

    def toggle_main_task(self, col: int, row: int):
        """切换格子是否属于主线任务。"""
        if (col, row) in self.main_task_cells:
            self.main_task_cells.discard((col, row))
        else:
            self.main_task_cells.add((col, row))
