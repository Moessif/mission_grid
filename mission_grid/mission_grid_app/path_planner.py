"""
路径规划模块
============

实现网格地图上的自动路径规划，包括 A* 寻路和 TSP 旅行商问题求解。

本模块包含：
- A* 搜索算法（支持 8 方向移动，octile 启发函数）
- ARA* 搜索算法（Anytime Repairing A*，渐进优化）
- TSP 求解器（多起点贪心 + 2-opt + or-opt + python-tsp SA/LS）
- 蛇形遍历路径生成（遍历所有格子时的最优方案）

依赖关系：
    models ← 本模块（GridConfig）
    numpy（外部库）← 本模块（距离矩阵）
    python_tsp（外部库，可选）← 本模块（TSP 精确/启发式求解）
    本模块 → code_generator（plan_path 被 export_mission 调用）
    本模块 → main_window（plan_path/plan_path_all 被路径规划按钮调用）

路径规划策略：
    1. 遍历有动作的格子（plan_path）：
       - 构建起降点 + 动作格子的距离矩阵
       - TSP 求解最优访问顺序
       - A* 拼接相邻航点间的实际路径
    2. 遍历所有格子（plan_path_all）：
       - 蛇形遍历（serpentine）作为基础路径
       - 从起飞点开始，选择较短的正/反两个方向

移动模型：
    - 4 方向（上下左右）：代价 1.0
    - 4 对角线：代价 √2 ≈ 1.414（需两侧无障碍）
    - 禁飞区不可通行
    - 斜飞安全检查：对角线移动时两侧正交格子必须可通行
"""

from __future__ import annotations

import heapq
import math
import random
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .models import GridConfig


# ============================================================
# 常量
# ============================================================

GridCell = Tuple[int, int]    # 网格坐标类型别名
DIAG_DIST = math.sqrt(2)      # 对角线距离 ≈ 1.414
INF = 999999.0                # 无穷大替代值
BlockChecker = Callable[[int, int], bool]


# ============================================================
# 网格合法性与邻居查询
# ============================================================

def _make_block_checker(config: GridConfig, runtime: bool = False) -> BlockChecker:
    """根据规划阶段生成阻塞判断函数。"""
    if runtime:
        return lambda col, row: config.is_blocked_runtime(col, row)
    return lambda col, row: config.is_blocked_preflight(col, row)


def _is_valid(col: int, row: int, config: GridConfig, is_blocked: Optional[BlockChecker] = None) -> bool:
    """检查网格坐标是否合法（在范围内且非禁飞区）。"""
    checker = is_blocked or _make_block_checker(config, runtime=False)
    return 0 <= col < config.cols and 0 <= row < config.rows and not checker(col, row)


def _neighbors(
    col: int,
    row: int,
    config: GridConfig,
    is_blocked: Optional[BlockChecker] = None,
) -> List[Tuple[GridCell, float]]:
    """
    获取可达邻居格子及移动代价。

    4 方向（上下左右）：代价 1.0
    4 对角线：代价 √2（需检查两侧正交格子是否可通行，防止斜穿禁飞区角落）
    """
    result = []
    # 正交方向
    for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nc, nr = col + dc, row + dr
        if _is_valid(nc, nr, config, is_blocked):
            result.append(((nc, nr), 1.0))
    # 对角线方向（需检查两侧正交格子）
    for dc, dr in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        nc, nr = col + dc, row + dr
        if _is_valid(nc, nr, config, is_blocked):
            if _is_valid(col + dc, row, config, is_blocked) and _is_valid(col, row + dr, config, is_blocked):
                result.append(((nc, nr), DIAG_DIST))
    return result


# ============================================================
# 启发函数
# ============================================================

def _heuristic(a: GridCell, b: GridCell) -> float:
    """
    Octile 距离启发函数（适用于 8 方向网格移动）。

    h = max(Δc, Δr) + (√2 - 1) * min(Δc, Δr)
    这是 8 方向网格上的精确最短距离（无障碍时）。
    """
    dc = abs(a[0] - b[0])
    dr = abs(a[1] - b[1])
    return max(dc, dr) + (DIAG_DIST - 1) * min(dc, dr)


def _inconsistent_heuristic(
    a: GridCell, b: GridCell, g_old: Dict[GridCell, float]
) -> float:
    """不一致启发函数（用于 ARA* 的渐进优化）。"""
    h = _heuristic(a, b)
    if a in g_old:
        return max(h, g_old[a] - g_old.get(b, 0))
    return h


# ============================================================
# A* 搜索算法
# ============================================================

def _astar_path(
    start: GridCell,
    goal: GridCell,
    config: GridConfig,
    is_blocked: Optional[BlockChecker] = None,
) -> List[GridCell]:
    """
    A* 最短路径搜索。

    使用 octile 启发函数和优先队列，在网格图上找到从 start 到 goal 的最短路径。

    返回:
        路径坐标列表（含首尾），无路径时返回空列表
    """
    if start == goal:
        return [start]
    open_set: list = []
    heapq.heappush(open_set, (0.0, start))
    came_from: Dict[GridCell, GridCell] = {}
    g_score: Dict[GridCell, float] = {start: 0.0}
    closed: set = set()
    while open_set:
        _, current = heapq.heappop(open_set)
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]
        for (nc, nr), step in _neighbors(current[0], current[1], config, is_blocked):
            if (nc, nr) in closed:
                continue
            tentative = g_score[current] + step
            if tentative < g_score.get((nc, nr), INF):
                came_from[(nc, nr)] = current
                g_score[(nc, nr)] = tentative
                f = tentative + _heuristic((nc, nr), goal)
                heapq.heappush(open_set, (f, (nc, nr)))
    return []


# ============================================================
# ARA* 搜索算法（Anytime Repairing A*）
# ============================================================

def arastar_path(
    start: GridCell,
    goal: GridCell,
    config: GridConfig,
    runtime: bool = False,
    initial_epsilon: float = 3.0,
    final_epsilon: float = 1.0,
    epsilon_step: float = 0.5,
) -> Tuple[List[GridCell], float]:
    """
    ARA* 算法：渐进优化的 A* 搜索。

    从宽松的启发权重 (epsilon=3.0) 开始，逐步收紧到 1.0（即标准 A*）。
    每轮找到一条次优路径，后续轮次尝试改进。
    如果 ARA* 失败，回退到标准 A*。

    返回:
        (路径, 代价) 元组
    """
    if start == goal:
        return [start], 0.0
    is_blocked = _make_block_checker(config, runtime)

    best_path: List[GridCell] = []
    best_cost: float = INF
    epsilon = initial_epsilon

    g_score: Dict[GridCell, float] = {start: 0.0}
    came_from: Dict[GridCell, GridCell] = {}
    closed: set = set()
    open_set: list = []
    heapq.heappush(open_set, (0.0, start))
    improved = True

    while epsilon >= final_epsilon and improved:
        improved = False

        while open_set:
            f_key, current = heapq.heappop(open_set)
            if current in closed:
                continue

            if current == goal:
                path = [current]
                c = current
                while c in came_from:
                    c = came_from[c]
                    path.append(c)
                path = path[::-1]
                cost = g_score[goal]
                if cost < best_cost:
                    best_path = path
                    best_cost = cost
                break

            closed.add(current)

            for (nc, nr), step in _neighbors(current[0], current[1], config, is_blocked):
                if (nc, nr) in closed:
                    continue
                tentative = g_score[current] + step
                if tentative < g_score.get((nc, nr), INF):
                    g_score[(nc, nr)] = tentative
                    came_from[(nc, nr)] = current
                    h = _heuristic((nc, nr), goal)
                    f = tentative + epsilon * h
                    heapq.heappush(open_set, (f, (nc, nr)))
                    improved = True

        if best_path:
            break

        epsilon -= epsilon_step
        open_set = []
        for node, g in g_score.items():
            if node not in closed:
                h = _heuristic(node, goal)
                heapq.heappush(open_set, (g + epsilon * h, node))

    # 回退到标准 A*
    if not best_path:
        best_path = _astar_path(start, goal, config, is_blocked)
        if best_path:
            best_cost = sum(
                _step_cost(best_path[i], best_path[i + 1])
                for i in range(len(best_path) - 1)
            )

    return best_path, best_cost


def _step_cost(a: GridCell, b: GridCell) -> float:
    """计算两相邻格子间的移动代价（正交=1，对角=√2）。"""
    dc = abs(a[0] - b[0])
    dr = abs(a[1] - b[1])
    if dc == 1 and dr == 1:
        return DIAG_DIST
    return float(dc + dr)


def arastar_distance(a: GridCell, b: GridCell, config: GridConfig, runtime: bool = False) -> float:
    """计算两格子间的 ARA* 最短距离（仅返回代价，不返回路径）。"""
    if a == b:
        return 0.0
    path, cost = arastar_path(a, b, config, runtime=runtime)
    return cost if path else INF


# ============================================================
# 辅助函数
# ============================================================

def _find_land_cell(config: GridConfig) -> Optional[GridCell]:
    """查找配置中的降落格子（如果存在 "land" 动作）。"""
    for (col, row), actions in config.actions.items():
        for a in actions:
            if a.action_type == "land":
                return (col, row)
    return None


def _build_distance_matrix(points: List[GridCell], config: GridConfig, runtime: bool = False) -> np.ndarray:
    """
    构建航点间的距离矩阵。

    使用 ARA* 计算每对航点间的最短距离，存入 n×n 对称矩阵。
    """
    n = len(points)
    dm = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            d = arastar_distance(points[i], points[j], config, runtime=runtime)
            dm[i][j] = d
            dm[j][i] = d
    return dm


# ============================================================
# TSP 局部搜索优化
# ============================================================

def _total_dist(order: List[int], dm: np.ndarray) -> float:
    """计算访问顺序的总距离。"""
    return sum(dm[order[i]][order[i + 1]] for i in range(len(order) - 1))


def _two_opt(order: List[int], dm: np.ndarray) -> List[int]:
    """
    2-opt 局部搜索优化。

    反转路径中的一段子序列，如果能缩短总距离则接受。
    重复直到无法改进。
    """
    n = len(order)
    if n <= 3:
        return order
    best = list(order)
    best_d = _total_dist(best, dm)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                new_o = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                new_d = _total_dist(new_o, dm)
                if new_d < best_d - 0.001:
                    best = new_o
                    best_d = new_d
                    improved = True
    return best


def _or_opt(order: List[int], dm: np.ndarray, seg_len: int = 2) -> List[int]:
    """
    or-opt 局部搜索优化。

    将路径中的一段子序列移动到另一个位置，如果能缩短总距离则接受。
    seg_len: 要移动的子序列长度（2 或 3）。
    """
    n = len(order)
    if n <= seg_len + 2:
        return order
    best = list(order)
    best_d = _total_dist(best, dm)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - seg_len):
            segment = best[i:i + seg_len]
            remaining = best[:i] + best[i + seg_len:]
            for j in range(1, len(remaining)):
                new_o = remaining[:j] + segment + remaining[j:]
                new_d = _total_dist(new_o, dm)
                if new_d < best_d - 0.001:
                    best = new_o
                    best_d = new_d
                    improved = True
                    break
            if improved:
                break
    return best


def _improve(order: List[int], dm: np.ndarray) -> List[int]:
    """组合优化：2-opt → or-opt(2) → or-opt(3)。"""
    o = _two_opt(order, dm)
    o = _or_opt(o, dm, 2)
    o = _or_opt(o, dm, 3)
    return o


# ============================================================
# TSP 构造启发式
# ============================================================

def _greedy_nn_from(dm: np.ndarray, start: int) -> List[int]:
    """贪心最近邻构造：从 start 开始，每次选择最近的未访问节点。"""
    n = dm.shape[0]
    visited = {start}
    order = [start]
    current = start
    while len(visited) < n:
        best_j = -1
        best_d = INF
        for j in range(n):
            if j not in visited and dm[current][j] < best_d:
                best_d = dm[current][j]
                best_j = j
        if best_j == -1:
            break
        order.append(best_j)
        visited.add(best_j)
        current = best_j
    return order


def _nearest_insertion(dm: np.ndarray, start: int) -> List[int]:
    """最近插入构造：每次选择距当前路径最近的节点，插入最优位置。"""
    n = dm.shape[0]
    remaining = set(range(n)) - {start}
    tour = [start]
    if not remaining:
        return tour
    nearest = min(remaining, key=lambda j: dm[start][j])
    tour.append(nearest)
    remaining.discard(nearest)
    while remaining:
        best_cost = INF
        best_node = -1
        best_pos = -1
        for node in remaining:
            for pos in range(len(tour)):
                a = tour[pos]
                b = tour[(pos + 1) % len(tour)]
                cost = dm[a][node] + dm[node][b] - dm[a][b]
                if cost < best_cost:
                    best_cost = cost
                    best_node = node
                    best_pos = pos
        tour.insert(best_pos + 1, best_node)
        remaining.discard(best_node)
    return tour


def _farthest_insertion(dm: np.ndarray, start: int) -> List[int]:
    """最远插入构造：每次选择距当前路径最远的节点，插入最优位置。"""
    n = dm.shape[0]
    remaining = set(range(n)) - {start}
    tour = [start]
    if not remaining:
        return tour
    farthest = max(remaining, key=lambda j: dm[start][j])
    tour.append(farthest)
    remaining.discard(farthest)
    while remaining:
        best_cost = INF
        best_node = -1
        best_pos = -1
        for node in remaining:
            for pos in range(len(tour)):
                a = tour[pos]
                b = tour[(pos + 1) % len(tour)]
                cost = dm[a][node] + dm[node][b] - dm[a][b]
                if cost < best_cost:
                    best_cost = cost
                    best_node = node
                    best_pos = pos
        tour.insert(best_pos + 1, best_node)
        remaining.discard(best_node)
    return tour


# ============================================================
# TSP 多起点求解器
# ============================================================

def _solve_tsp_multistart(dm: np.ndarray, open_path: bool = False, attempts: int = 200) -> List[int]:
    """
    多起点 TSP 求解器。

    策略组合：
    1. ≤12 节点：使用 python-tsp 精确 DP 求解
    2. 多起点贪心最近邻 + 2-opt + or-opt
    3. 多起点最近插入 + 2-opt + or-opt
    4. 多起点最远插入 + 2-opt + or-opt
    5. 随机打乱 + 局部搜索（剩余次数）
    6. python-tsp SA + LS PS3（启发式，可选）

    open_path=True 时设置 dm[:, 0] = 0 实现开放路径（不返回起点）。
    """
    n = dm.shape[0]
    if n <= 1:
        return [0]
    if n == 2:
        if open_path:
            return [0, 1]
        else:
            return [0, 1, 0]

    # 小规模精确求解
    if n <= 12:
        try:
            from python_tsp.exact import solve_tsp_dynamic_programming
            if open_path:
                dm_copy = dm.copy()
                dm_copy[:, 0] = 0
                perm, _ = solve_tsp_dynamic_programming(dm_copy)
            else:
                perm, _ = solve_tsp_dynamic_programming(dm)
            return list(perm)
        except Exception:
            pass

    best_order = None
    best_dist = INF

    # 多起点贪心最近邻
    for start_node in range(n):
        order = _greedy_nn_from(dm, start_node)
        order = _improve(order, dm)
        d = _total_dist(order, dm)
        if d < best_dist:
            best_dist = d
            best_order = list(order)

    # 多起点最近插入
    for start_node in range(n):
        order = _nearest_insertion(dm, start_node)
        order = _improve(order, dm)
        d = _total_dist(order, dm)
        if d < best_dist:
            best_dist = d
            best_order = list(order)

    # 多起点最远插入
    for start_node in range(n):
        order = _farthest_insertion(dm, start_node)
        order = _improve(order, dm)
        d = _total_dist(order, dm)
        if d < best_dist:
            best_dist = d
            best_order = list(order)

    # 随机打乱 + 局部搜索
    remaining = attempts - 3 * n
    for _ in range(max(remaining, 20)):
        p = list(range(n))
        random.shuffle(p)
        p = _improve(p, dm)
        d = _total_dist(p, dm)
        if d < best_dist:
            best_dist = d
            best_order = list(p)

    # python-tsp 启发式（SA + LS PS3）
    try:
        from python_tsp.heuristics import solve_tsp_simulated_annealing, solve_tsp_local_search
        if open_path:
            dm_work = dm.copy()
            dm_work[:, 0] = 0
        else:
            dm_work = dm
        for _ in range(5):
            perm_sa, _ = solve_tsp_simulated_annealing(dm_work)
            try:
                perm_ls, _ = solve_tsp_local_search(dm_work, x0=perm_sa, perturbation_scheme="ps3")
                perm = list(perm_ls)
            except Exception:
                perm = list(perm_sa)
            d = _total_dist(perm, dm_work)
            if d < best_dist:
                if open_path:
                    idx0 = perm.index(0)
                    perm = perm[idx0:] + perm[:idx0]
                best_dist = d
                best_order = perm
    except Exception:
        pass

    if best_order is None:
        best_order = _greedy_nn_from(dm, 0)

    # 确保闭合路径
    if not open_path and best_order[-1] != best_order[0]:
        best_order.append(best_order[0])

    return best_order


# ============================================================
# 路径拼接
# ============================================================

def _build_path_from_order(order: List[GridCell], config: GridConfig, runtime: bool = False) -> List[GridCell]:
    """
    将 TSP 访问顺序拼接为完整的网格路径。

    对每对相邻航点使用 ARA* 计算实际网格路径，
    然后将各段路径拼接（去除重复的连接点）。
    """
    full_path: List[GridCell] = []
    for i in range(len(order) - 1):
        segment, _ = arastar_path(order[i], order[i + 1], config, runtime=runtime)
        if not segment:
            return []
        if full_path:
            segment = segment[1:]  # 去除与上一段重叠的起点
        full_path.extend(segment)
    return full_path


# ============================================================
# 公共接口：路径规划
# ============================================================

def plan_path(
    config: GridConfig,
    start: Optional[GridCell] = None,
    runtime: bool = False,
    targets: Optional[List[GridCell]] = None,
) -> List[GridCell]:
    """
    规划遍历有动作格子的最优路径。

    流程：
    1. 收集起降点 + 所有动作格子
    2. 构建距离矩阵
    3. TSP 求解最优访问顺序
    4. A* 拼接实际网格路径

    特殊处理：
    - 如果存在 "land" 降落格子，路径终点固定为该格子
    - 起飞点固定为路径起点（节点 0）
    """
    start = start if start is not None else (config.takeoff_col, config.takeoff_row)
    action_cells = list(dict.fromkeys(targets if targets is not None else config.action_cells()))
    land_cell = _find_land_cell(config)
    default_end = (config.takeoff_col, config.takeoff_row)
    end = land_cell if land_cell else default_end

    if not _is_valid(start[0], start[1], config, _make_block_checker(config, runtime)):
        return []
    if not action_cells:
        if start == end:
            return [start]
        segment, _ = arastar_path(start, end, config, runtime=runtime)
        return segment

    # 去重并确保起降点在列表中
    all_points = list(dict.fromkeys([start] + action_cells))
    if end not in all_points:
        all_points.append(end)

    n = len(all_points)
    dm = _build_distance_matrix(all_points, config, runtime=runtime)

    # 确保 start 是节点 0（TSP 求解器从 0 开始）
    start_idx = 0
    for i, p in enumerate(all_points):
        if p == start:
            start_idx = i
            break
    if start_idx != 0:
        all_points[0], all_points[start_idx] = all_points[start_idx], all_points[0]
        dm[:, [0, start_idx]] = dm[:, [start_idx, 0]]
        dm[[0, start_idx], :] = dm[[start_idx, 0], :]

    # 固定终点的 TSP 求解
    if land_cell:
        end_node = -1
        for i, p in enumerate(all_points):
            if p == land_cell:
                end_node = i
                break
        if end_node > 0:
            others = [i for i in range(n) if i != 0 and i != end_node]
            best_perm = None
            best_dist = INF
            for _ in range(200):
                random.shuffle(others)
                perm = [0] + others + [end_node]
                perm = _improve(perm, dm)
                d = _total_dist(perm, dm)
                if d < best_dist:
                    best_dist = d
                    best_perm = list(perm)
            perm = best_perm
        else:
            perm = _solve_tsp_multistart(dm, open_path=False)
    else:
        perm = _solve_tsp_multistart(dm, open_path=False)

    order = [all_points[i] for i in perm]
    return _build_path_from_order(order, config, runtime=runtime)


def plan_path_all(
    config: GridConfig,
    start: Optional[GridCell] = None,
    runtime: bool = False,
    visited: Optional[set[GridCell]] = None,
) -> List[GridCell]:
    """
    规划遍历所有非禁飞格子的路径。

    使用蛇形遍历（serpentine）作为基础路径：
    - 偶数行从左到右，奇数行从右到左
    - 从起飞点开始，选择正/反两个方向中较短的

    如果存在 "land" 降落格子，路径终点延伸到该格子。
    """
    start = start if start is not None else (config.takeoff_col, config.takeoff_row)
    land_cell = _find_land_cell(config)
    default_end = (config.takeoff_col, config.takeoff_row)
    end = land_cell if land_cell else default_end
    is_blocked = _make_block_checker(config, runtime)
    visited_cells = set(visited or set())
    all_cells = set()
    for col in range(config.cols):
        for row in range(config.rows):
            if not is_blocked(col, row):
                all_cells.add((col, row))
    if not all_cells or start not in all_cells:
        return []
    remaining_cells = {cell for cell in all_cells if cell not in visited_cells}
    remaining_cells.add(start)
    if end in all_cells:
        remaining_cells.add(end)
    if not remaining_cells:
        if start == end:
            return [start]
        segment, _ = arastar_path(start, end, config, runtime=runtime)
        return segment

    snake = _build_snake_order(config)
    reachable = [c for c in snake if c in remaining_cells]
    if start not in reachable:
        return []

    idx = reachable.index(start)
    # 尝试正向和反向蛇形遍历
    path_a = _build_full_snake_path(reachable, idx, config, reverse=False, runtime=runtime)
    path_b = _build_full_snake_path(reachable, idx, config, reverse=True, runtime=runtime)
    candidates = []
    for p in [path_a, path_b]:
        if p:
            if p[-1] != end:
                extra, _ = arastar_path(p[-1], end, config, runtime=runtime)
                if extra:
                    p = p + extra[1:]
            candidates.append(p)
    if not candidates:
        return []
    return min(candidates, key=len)


def _build_full_snake_path(
    reachable: List[GridCell],
    idx: int,
    config: GridConfig,
    reverse: bool,
    runtime: bool = False,
) -> List[GridCell]:
    """构建从指定索引开始的完整蛇形路径。"""
    if reverse:
        order = reachable[idx:] + reachable[:idx]
    else:
        order = [reachable[idx]] + reachable[idx - 1::-1] + reachable[idx + 1:]
    return _build_path_from_order(order, config, runtime=runtime)


def _build_snake_order(config: GridConfig) -> List[GridCell]:
    """
    构建蛇形遍历顺序。

    偶数行 (0, 2, 4, ...): 从左到右 (col 0→8)
    奇数行 (1, 3, 5, ...): 从右到左 (col 8→0)
    """
    order = []
    for row in range(config.rows):
        if row % 2 == 0:
            cols = range(config.cols)
        else:
            cols = range(config.cols - 1, -1, -1)
        for col in cols:
            order.append((col, row))
    return order
