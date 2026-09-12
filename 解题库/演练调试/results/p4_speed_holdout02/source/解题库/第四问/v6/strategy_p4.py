# -*- coding: utf-8 -*-
"""问题4 v6：对定向源安全的发现、定位与清除策略。

策略不读取模拟器真值。发现阶段使用 700m 基线网格和 350m 错位外围网格，
在每一个站位检测全部频道。只有整张发现网格完成后，仍然从未出现
``direction``/``near`` 的频道才会被标记为 absent。

这里的 ``no_signal`` 永远不是定位负约束：

* 发现阶段不把单次 no_signal 从覆盖区域中排除；
* 已经有正向测量的频道不修改既有定位多边形；
* 局部测量丢失时，只回到最近的正向测量点恢复。

一旦有正向测量，交会定位、MEC 和 20m 清除判据复用
``problem1_v4_inline.py``。额外的局部探测点只取已验证正向测量点的凸组合，
因此不会把一个猜测的 no_signal 当成几何事实。
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from strategy import Action, State, p1


Vec = Tuple[float, float]
CHANNELS = tuple(range(1, 21))
ARENA_R = 1800.0
R_EFF = 1500.0
EPS_DEG = 1.0050001
CLEAR_R = 20.0
GRID_STEP = 700.0
GRID_OFFSET = 350.0
MIN_DISCOVERY_RECORDS = 5


def _snake_grid(axis: Tuple[int, ...]) -> List[Vec]:
    """生成固定顺序的 700m 方格路线，不依赖源位置。"""
    points: List[Vec] = []
    for row, y in enumerate(axis):
        xs = axis if row % 2 == 0 else tuple(reversed(axis))
        points.extend((float(x), float(y)) for x in xs)
    return points


def _discovery_stations() -> List[Vec]:
    """700m 基线网格 + 错位外围网格。

    基线覆盖 [-2100, 2100]^2；外围错位网格覆盖
    [-2450, 2450]^2。两者都保留在目标圆外的必要站位，保证源在目标圆
    边缘且定向半平面朝外时仍有近距离正向检测机会。
    """
    base_axis = tuple(range(-2100, 2101, 700))
    offset_axis = tuple(range(-2450, 2451, 700))
    ordered = _snake_grid(base_axis) + _snake_grid(offset_axis)

    # 站点集合保持不变；完成全清验证后，只优化访问顺序以减少移动时间。
    origin = (0.0, 0.0)
    seen = {origin}
    points = []
    for point in ordered:
        if point not in seen:
            seen.add(point)
            points.append(point)

    # 确定性最近邻开放路径；它不使用任何源信息，也不改变发现覆盖集合。
    result = [origin]
    current = origin
    while points:
        next_point = min(points, key=lambda point: (
            math.hypot(current[0] - point[0], current[1] - point[1]),
            point[1], point[0]))
        result.append(next_point)
        points.remove(next_point)
        current = next_point
    return result


DISCOVERY_STATIONS = tuple(_discovery_stations())


def distance(a: Vec, b: Vec) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _same_point(a: Vec, b: Vec, tol: float = 1e-3) -> bool:
    return distance(a, b) <= tol


def _localize(records: List[Tuple[Vec, float]]) -> Optional[dict]:
    """只用 direction 记录交会定位并计算 MEC。"""
    if len(records) < 2:
        return None
    dets = [pos for pos, _ in records]
    thetas = [angle for _, angle in records]
    result = p1.solve_problem_1(
        dets,
        thetas,
        eps_deg=EPS_DEG,
        R_eff=R_EFF,
        R_target=ARENA_R,
        N_disk=64,
    )
    if (result['n_vertices'] < 3 or result['D'] <= 1e-6
            or not all(math.isfinite(v) for v in result['mec_center'])
            or not math.isfinite(result['mec_radius'])):
        return None
    return result


@dataclass
class Track:
    records: List[Tuple[Vec, float]] = field(default_factory=list)
    near: Optional[Vec] = None
    poly: List[Vec] = field(default_factory=list)
    center: Vec = (0.0, 0.0)
    radius: float = math.inf
    estimate: Vec = (0.0, 0.0)
    recovery_required: bool = False
    clear_failures: int = 0
    probe_round: int = 0
    probe_history: List[Vec] = field(default_factory=list)


class AdaptiveP4:
    """问题4独立策略：完整安全发现后，再逐频道定位和清除。"""

    name = 'AdaptiveP4'

    def __init__(self, discovery_stations: Optional[List[Vec]] = None,
                 min_positive_records: int = MIN_DISCOVERY_RECORDS):
        self.discovery_stations = list(discovery_stations or DISCOVERY_STATIONS)
        self.min_positive_records = max(2, int(min_positive_records))
        self.discovery_station_index = 0
        self.discovery_channel_index = 0
        self._station_channels: List[int] = []
        self.phase = 'discovery'
        self.discovery_complete = False

        self.tracks: Dict[int, Track] = {}
        self.absent: Set[int] = set()
        self.cleared: Set[int] = set()
        self.work_channels: List[int] = []
        self.work_index = 0

        self.done = False
        self.completion_reason: Optional[str] = None
        self._attempts = 0
        self.geometry_conflicts = 0

    # ------------------------------------------------------------
    # 发现阶段
    # ------------------------------------------------------------
    def _finish_discovery(self) -> None:
        if self.discovery_complete:
            return
        self.discovery_complete = True
        # 只有完整网格完成后才允许做这一次集合判定；no_signal 本身不参与。
        self.absent = set(CHANNELS) - set(self.tracks)
        self.work_channels = sorted(self.tracks)
        self.work_index = 0
        self.phase = 'localization'

    def _next_discovery_action(self) -> Optional[Action]:
        if (self._station_channels
                and self.discovery_channel_index >= len(self._station_channels)):
            self.discovery_station_index += 1
            self.discovery_channel_index = 0
            self._station_channels = []

        while self.discovery_station_index < len(self.discovery_stations):
            if self.discovery_channel_index >= len(self._station_channels):
                station = self.discovery_stations[self.discovery_station_index]
                self._station_channels = [
                    channel for channel in CHANNELS
                    if channel not in self.tracks
                    or (self.tracks[channel].near is None
                        and len(self.tracks[channel].records)
                        < self.min_positive_records)
                ]
                self.discovery_channel_index = 0
                if not self._station_channels:
                    self.discovery_station_index += 1
                    continue

            station = self.discovery_stations[self.discovery_station_index]
            channel = self._station_channels[self.discovery_channel_index]
            self.discovery_channel_index += 1
            return Action('measure', station, channel)

        self._finish_discovery()
        return None

    # ------------------------------------------------------------
    # 正向记录与安全探测
    # ------------------------------------------------------------
    @staticmethod
    def _nearest_record(track: Track, pos: Vec) -> Vec:
        if not track.records:
            return pos
        return min(track.records, key=lambda row: distance(row[0], pos))[0]

    def _safe_probe_candidates(self, track: Track, state: State) -> List[Vec]:
        """从正向测量点凸组合产生候选点。

        对同一源，正向可接收集合是有效接收圆盘与定向半平面的交集，
        是凸集；其内的凸组合仍然是正向候选。候选永远不由 no_signal 生成。
        """
        positions: List[Vec] = []
        for pos, _ in track.records:
            if not any(_same_point(pos, old) for old in positions):
                positions.append(pos)
        if len(positions) < 2:
            return positions[:]

        pairs = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                pair_distance = distance(positions[i], positions[j])
                if pair_distance > 1e-3:
                    pairs.append((pair_distance, positions[i], positions[j]))
        pairs.sort(reverse=True, key=lambda item: item[0])

        candidates: List[Vec] = []
        # 优先长基线，再在基线内部取多个新的安全点。
        for _, a, b in pairs[:80]:
            for fraction in (0.12, 0.25, 0.40, 0.60, 0.75, 0.88):
                point = (
                    a[0] * (1.0 - fraction) + b[0] * fraction,
                    a[1] * (1.0 - fraction) + b[1] * fraction,
                )
                if any(_same_point(point, old, 0.5)
                       for old in positions + track.probe_history):
                    continue
                candidates.append(point)

        # 加入三点平均值，避免所有候选都落在同一条长边上。
        for group in (positions[:3], positions[-3:], positions[::2][:3]):
            if len(group) == 3:
                point = tuple(sum(p[i] for p in group) / 3.0 for i in (0, 1))
                if not any(_same_point(point, old, 0.5)
                           for old in positions + track.probe_history):
                    candidates.append(point)

        if not candidates:
            return []

        center = track.center if math.isfinite(track.radius) else state.pos

        def angular_separation(point: Vec) -> float:
            if distance(point, center) < 1e-6:
                return math.pi
            new_angle = math.atan2(center[1] - point[1], center[0] - point[0])
            separations = []
            for old, _ in track.records:
                if distance(old, center) < 1e-6:
                    continue
                old_angle = math.atan2(center[1] - old[1], center[0] - old[0])
                separations.append(abs(math.sin(new_angle - old_angle)))
            return min(separations) if separations else 0.0

        def score(point: Vec) -> Tuple[float, float, float]:
            # 先取新方向最不同的点；再偏好靠近当前估计、且不重复的位置。
            return (
                angular_separation(point),
                -distance(point, center),
                -distance(point, state.pos),
            )

        return sorted(candidates, key=score, reverse=True)

    def _next_probe(self, track: Track, state: State) -> Action:
        candidates = self._safe_probe_candidates(track, state)
        if candidates:
            point = candidates[0]
            track.probe_history.append(point)
            track.probe_round += 1
            return Action('measure', point, self._active_channel)

        # 仅在没有第二个不同正向点时重复已验证正向位置；这仍然不会产生
        # 空间负约束，新的独立噪声测量有机会收紧同一测点的角度区间。
        point = self._nearest_record(track, state.pos)
        track.probe_round += 1
        return Action('measure', point, self._active_channel)

    # ------------------------------------------------------------
    # 局部定位与清除阶段
    # ------------------------------------------------------------
    def _next_local_action(self, channel: int, state: State) -> Action:
        track = self.tracks[channel]
        self._active_channel = channel

        if track.near is not None:
            return Action('clear', track.near, channel)

        if track.recovery_required:
            # 消费恢复请求；若该点再次 no_signal，on_measure 会重新置位。
            track.recovery_required = False
            return Action('measure', self._nearest_record(track, state.pos), channel)

        localized = _localize(track.records)
        if localized is not None:
            track.poly = localized['poly']
            track.center = localized['mec_center']
            track.radius = localized['mec_radius']
            track.estimate = localized['mec_center']

            if track.radius <= CLEAR_R:
                return Action('clear', track.center, channel)

        return self._next_probe(track, state)

    # ------------------------------------------------------------
    # 驱动器接口
    # ------------------------------------------------------------
    def step(self, state: State) -> Action:
        if self.done:
            return Action('done')
        self._attempts += 1
        if self._attempts > 30000:
            self.done = True
            self.completion_reason = 'step_limit'
            return Action('done')

        if self.phase == 'discovery':
            action = self._next_discovery_action()
            if action is not None:
                return action

        while self.work_index < len(self.work_channels):
            channel = self.work_channels[self.work_index]
            if channel in self.cleared:
                self.work_index += 1
                continue
            return self._next_local_action(channel, state)

        self.done = True
        self.completion_reason = 'all_channels_cleared_or_covered'
        return Action('done')

    def on_measure(self, state: State, channel: int, result: str,
                   svd: Optional[float]) -> None:
        if result in ('direction', 'near'):
            track = self.tracks.setdefault(channel, Track())
            if result == 'near':
                track.near = state.pos
                track.recovery_required = False
                return
            if svd is None or not math.isfinite(svd):
                return
            # discovery 阶段每个站位只测一次；局部恢复允许同一点重复测量，
            # 作为新的独立噪声样本，但从不把 no_signal 作为约束。
            track.records.append((state.pos, float(svd) % 360.0))
            track.recovery_required = False
            return

        if result == 'no_signal' and self.phase == 'localization':
            track = self.tracks.get(channel)
            if track is not None and track.records:
                # 保留 poly、center、radius 和全部正向 records 原样。
                track.recovery_required = True

    def on_clear(self, state: State, channel: int, success: bool) -> None:
        track = self.tracks[channel]
        if success:
            self.cleared.add(channel)
            state.cleared.add(channel)
            track.recovery_required = False
            self.work_index += 1
            return

        # 清除失败也不能将频道标 absent 或 skip；回到正向点继续收集几何信息。
        track.clear_failures += 1
        track.recovery_required = True


def make_strategy() -> AdaptiveP4:
    return AdaptiveP4()


if __name__ == '__main__':
    strategy = AdaptiveP4()
    state = State(pos=(0.0, 0.0), ch=1)
    print(strategy.name, len(strategy.discovery_stations), strategy.step(state))
