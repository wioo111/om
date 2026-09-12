# -*- coding: utf-8 -*-
"""问题三 v8：就近定位、沿途测向、按频道证明搜索覆盖。

策略仅接收 State 和动作响应，不读取模拟器的源位置、数量或随机种子。
全向信号的 no_signal 排除半径 1000 m 的圆盘；网格按整格覆盖判断，
不是将未覆盖格点简单当成没有目标。虚拟时间限制由 /enter 的驱动器处理。
"""

import math
from dataclasses import dataclass, field

import numpy as np

from strategy import Action, State, p1

Vec = tuple[float, float]
CHANNELS = tuple(range(1, 21))
ARENA_R = 1800.0
RECEIVE_MIN = 1000.0
RECEIVE_MAX = 1500.0
# 官方 svd_deg 保留两位小数；量化最多再引入 0.005 度。
EPS_DEG = 1.0050001
CLEAR_R = 20.0


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def centroid(poly):
    area = cx = cy = 0.0
    for a, b in zip(poly, poly[1:] + poly[:1]):
        cross = a[0] * b[1] - b[0] * a[1]
        area += cross
        cx += (a[0] + b[0]) * cross
        cy += (a[1] + b[1]) * cross
    if abs(area) < 1e-9:
        return tuple(sum(p[i] for p in poly) / len(poly) for i in (0, 1))
    return cx / (3 * area), cy / (3 * area)


def convex_hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        return points
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-9:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-9:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def exclude_disk(poly, pos, radius=RECEIVE_MIN):
    """从凸定位区减去无信号圆盘的内接多边形，再取保守凸包。

    只删除能确认不可能的位置；凸包可能保留额外区域，不会删除真目标。
    """
    center, bound = enclosing_circle(poly)
    if distance(center, pos) - bound >= radius:
        return poly
    pieces = []
    rest = poly
    n = 64
    support = radius * math.cos(math.pi / n) - 1e-6
    for k in range(n):
        angle = 2 * math.pi * k / n
        normal = (math.cos(angle), math.sin(angle))
        d = support + normal[0] * pos[0] + normal[1] * pos[1]
        outer = p1.hpi_intersect(rest, [p1.HalfPlane((-normal[0], -normal[1]), -d)])
        if outer:
            pieces.extend(outer)
        rest = p1.hpi_intersect(rest, [p1.HalfPlane(normal, d)])
        if not rest:
            break
    return convex_hull(pieces)


def reception_halfplanes(positive, negative):
    """同一源的接收半径不变：d(X,S) <= R < d(X,N) 给出线性约束。"""
    return [p1.HalfPlane((2 * (n[0] - s[0]), 2 * (n[1] - s[1])),
                        n[0]**2 + n[1]**2 - s[0]**2 - s[1]**2)
            for s in positive for n in negative]


def enclosing_circle(poly):
    """小凸多边形的确定性包围圆；优先检验直径圆，余下枚举三点。

    最后重新取最大顶点距离，避免浮点误差低估清除半径。
    """
    if len(poly) == 1:
        return poly[0], 0.0
    diameter, a, b = p1.polygon_diameter(poly)
    center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    radius = max(distance(center, v) for v in poly)
    if radius <= diameter / 2 + 1e-7:
        return center, radius + 1e-7
    best = (center, radius)
    for i, a in enumerate(poly):
        for j in range(i):
            b = poly[j]
            for k in range(j):
                candidate = p1._circle_from_3(a, b, poly[k])
                if candidate is None:
                    continue
                c, r2 = candidate
                if r2 >= best[1] ** 2:
                    continue
                r = max(distance(c, v) for v in poly)
                if r * r <= r2 + 1e-5:
                    best = c, r + 1e-7
    return best


@dataclass
class Track:
    records: list = field(default_factory=list)
    poly: list = field(default_factory=list)
    center: Vec = (0.0, 0.0)
    radius: float = math.inf
    near: Vec | None = None
    failures: int = 0
    estimate: Vec = (0.0, 0.0)
    probe_after_fail: bool = False


class Coverage:
    """覆盖证明：每格外接圆全部落入一次无信号检测的 1000 m 圆内。

    保留所有与目标圆相交的方格，包含边缘格；已排除的格子不会遗漏
    目标圆边缘。此条件比圆盘并集覆盖更保守，但不会虚报完整覆盖。
    """

    def __init__(self, cell_size=60.0):
        n = math.ceil(2 * ARENA_R / cell_size)
        step = 2 * ARENA_R / n
        a = -ARENA_R + step * (np.arange(n) + 0.5)
        x, y = np.meshgrid(a, a)
        nearest_x = np.maximum(np.abs(x) - step / 2, 0)
        nearest_y = np.maximum(np.abs(y) - step / 2, 0)
        inside = nearest_x**2 + nearest_y**2 <= ARENA_R**2
        self.points = np.column_stack((x[inside], y[inside]))
        self.cover_radius = RECEIVE_MIN - step / math.sqrt(2) - 1e-6
        self.remaining = {ch: np.ones(len(self.points), dtype=bool)
                          for ch in CHANNELS}

    def covered_at(self, pos):
        delta = self.points - pos
        return np.sum(delta * delta, axis=1) <= self.cover_radius**2

    def gain(self, ch, mask):
        return int(np.count_nonzero(self.remaining[ch] & mask))

    def exclude(self, ch, pos):
        self.remaining[ch] &= ~self.covered_at(pos)

    def absent(self, ch):
        return not np.any(self.remaining[ch])


class AdaptiveV8:
    name = 'AdaptiveV8'

    def __init__(self, lateral=150.0, scan_fraction=0.10,
                 cell_size=30.0, opportunistic=True, first_hop=300.0,
                 probe_radius=80.0):
        self.lateral = lateral
        self.scan_fraction = scan_fraction
        self.opportunistic = opportunistic
        self.coverage = Coverage(cell_size)
        self.tracks = {}
        self.negative_positions = {ch: [] for ch in CHANNELS}
        self.cleared = set()
        self.absent = set()
        self.done = False
        self.completion_reason = None
        self.scan_queue = []
        self.active_ch = None
        self.scan_pending = True
        self.exploring = False
        self.geometry_conflicts = 0
        self.first_hop = first_hop
        self.probe_radius = probe_radius
        self.station_positions = []
        for radius in (800., 1150., 1350., 1550.):
            for k in range(24):
                a = k * math.pi / 12
                self.station_positions.append((radius * math.cos(a), radius * math.sin(a)))
        self.station_positions.extend((float(x), float(y))
                                      for x in range(-1600, 1601, 200)
                                      for y in range(-1600, 1601, 200)
                                      if x * x + y * y <= 1800**2)
        self.station_masks = np.asarray([self.coverage.covered_at(p)
                                        for p in self.station_positions])

    def _unknown(self):
        return [ch for ch in CHANNELS if ch not in self.tracks
                and ch not in self.cleared and ch not in self.absent]

    def _start_scan(self, state, force=False):
        mask = self.coverage.covered_at(state.pos)
        unknown = [ch for ch in self._unknown()
                   if self.coverage.gain(ch, mask) >= (1 if force else max(1, int(
                       min(len(self.coverage.points) * self.scan_fraction,
                           np.count_nonzero(self.coverage.remaining[ch]) * 0.8))))]
        useful = []
        if self.opportunistic:
            for ch, track in self.tracks.items():
                if ch in self.cleared or track.radius <= max(CLEAR_R, self.probe_radius):
                    continue
                if not track.records:
                    continue
                nearest = min(distance(state.pos, p) for p, _ in track.records)
                if nearest < 100 or distance(state.pos, track.center) > 1250:
                    continue
                # 只有新视点能提供足够夹角时才补测，避免原地重复检测。
                old = min(track.records, key=lambda r: distance(state.pos, r[0]))[0]
                a = math.atan2(track.center[1] - old[1], track.center[0] - old[0])
                b = math.atan2(track.center[1] - state.pos[1],
                               track.center[0] - state.pos[0])
                if abs(math.sin(a - b)) > 0.15:
                    useful.append(ch)
        self.scan_queue = sorted(set(unknown + useful),
                                 key=lambda ch: (ch != state.ch, ch))
        self.scan_pending = False

    def _local_action(self, ch, state):
        track = self.tracks[ch]
        if track.probe_after_fail:
            if any(distance(state.pos, p) < 1 for p, _ in track.records):
                return Action('measure', (state.pos[0] + 25, state.pos[1] + 25), ch)
            return Action('measure', state.pos, ch)
        if track.near is not None:
            return Action('clear', track.near, ch)
        if track.radius <= CLEAR_R - 1e-5:
            # 利用 20 m 清除半径，向当前位置平移仍能覆盖整个定位区域。
            d = distance(state.pos, track.center)
            shift = min(d, CLEAR_R - track.radius - 1e-5)
            if d > 1e-9:
                pos = (track.center[0] + (state.pos[0] - track.center[0]) * shift / d,
                       track.center[1] + (state.pos[1] - track.center[1]) * shift / d)
            else:
                pos = track.center
            return Action('clear', pos, ch)

        if (track.radius <= self.probe_radius and len(track.records) >= 2
                and track.failures == 0):
            return Action('clear', track.estimate, ch)

        pos = track.estimate
        # 单条方向只约束一条长带：增加横向基线，避免沿射线走造成退化。
        if len(track.records) == 1:
            old, angle = track.records[-1]
            theta = math.radians(angle)
            if self.first_hop is not None:
                if (distance(state.pos, old) > 150 and distance(state.pos, pos) < 1250
                        and not any(distance(state.pos, p) < 1 for p in self.negative_positions[ch])):
                    return Action('measure', state.pos, ch)
                length = min(distance(old, pos), self.first_hop)
                pos = (old[0] + length * math.cos(theta),
                       old[1] + length * math.sin(theta))
            options = [(pos[0] + sign * self.lateral * -math.sin(theta),
                        pos[1] + sign * self.lateral * math.cos(theta))
                       for sign in (-1, 1)]
            pos = min(options, key=lambda p: distance(state.pos, p))
        elif any(distance(pos, p) < 10 for p, _ in track.records):
            _, a, b = p1.polygon_diameter(track.poly)
            theta = math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2
            length = max(25.0, min(self.lateral, track.radius * 0.5))
            options = [(pos[0] + sign * length * math.cos(theta),
                        pos[1] + sign * length * math.sin(theta))
                       for sign in (-1, 1)]
            pos = min(options, key=lambda p: distance(state.pos, p))
        return Action('measure', pos, ch)

    def _explore_action(self, state):
        unknown = self._unknown()
        if not unknown:
            return None
        weights = np.sum([self.coverage.remaining[ch] for ch in unknown], axis=0)
        indices = np.flatnonzero(weights)
        if len(indices) == 0:
            return None
        points = self.coverage.points
        # 候选仅由未覆盖区域生成，不读取源位置。稀疏取点并加入最近未覆盖点。
        stride = max(1, len(indices) // 100)
        choices = points[indices[::stride]]
        closest = points[indices[np.argmin(np.sum((points[indices] - state.pos)**2,
                                                axis=1))]]
        choices = np.vstack((choices, closest))
        best = None
        for candidate in choices:
            # 朝未覆盖区域走到足以覆盖其附近的站位，可比走到格心少走一段。
            d = distance(state.pos, candidate)
            if d > 600:
                candidate = np.asarray(state.pos) + (
                    candidate - state.pos) * max(0.4, (d - 500) / d)
            mask = self.coverage.covered_at(candidate)
            gain = int(np.sum(weights[mask]))
            if not gain:
                continue
            nscan = sum(self.coverage.gain(ch, mask) > 0 for ch in unknown)
            cost = distance(state.pos, candidate) / 5 + 6 * nscan + 25
            score = gain / cost
            if best is None or score > best[0]:
                best = (score, tuple(candidate), mask)
        if best is None:
            raise RuntimeError('搜索区域非空但无法生成覆盖站位')
        _, pos, mask = best
        channels = [ch for ch in unknown if self.coverage.gain(ch, mask)]
        self.exploring = True
        self.scan_pending = True
        return Action('measure', pos, channels[0])

    @staticmethod
    def _route(start, nodes):
        """最近邻起点 + 开放路径 2-opt，只规划剩余目标，不要求返回原点。"""
        remaining = list(nodes)
        route = []
        pos = start
        while remaining:
            node = min(remaining, key=lambda node: distance(pos, node[1]))
            remaining.remove(node)
            route.append(node)
            pos = node[1]
        for _ in range(12):
            changed = False
            for i in range(len(route) - 1):
                prev = start if i == 0 else route[i - 1][1]
                for j in range(i + 1, len(route)):
                    old = distance(prev, route[i][1])
                    new = distance(prev, route[j][1])
                    if j + 1 < len(route):
                        old += distance(route[j][1], route[j + 1][1])
                        new += distance(route[i][1], route[j + 1][1])
                    if new + 1e-6 < old:
                        route[i:j + 1] = reversed(route[i:j + 1])
                        changed = True
            if not changed:
                break
        return route

    def _next_destination(self, state):
        known = [(ch, track.estimate) for ch, track in self.tracks.items()
                 if ch not in self.cleared]
        unknown = self._unknown()
        if not unknown:
            route = self._route(state.pos, known)
            return route[0] if route else None
        remaining = np.any([self.coverage.remaining[ch] for ch in unknown], axis=0)
        return self._cover_route(state, known, remaining, len(unknown))

    def _cover_route(self, state, known, remaining, n_unknown):
        routes = [self._build_cover_route(state, known, remaining, n_unknown, power)
                  for power in (0.6, 1.0, 1.6)]
        def cost(route):
            previous = state.pos
            value = 0.0
            for ch, pos in route:
                value += distance(previous, pos) / 5
                if ch < 0:
                    value += 6 * n_unknown
                previous = pos
            return value
        route = min(routes, key=cost)
        return route[0] if route else None

    def _build_cover_route(self, state, known, remaining, n_unknown, power):
        """在已知目标路径中插入补充扫描点，以新增覆盖量/额外耗时选点。"""
        route = self._route(state.pos, known)
        uncovered = remaining.copy()
        for _, pos in known:
            uncovered &= ~self.coverage.covered_at(pos)
        candidates = self.station_positions
        masks = self.station_masks
        for _ in range(12):
            if not np.any(uncovered):
                break
            best = None
            for i, (pos, mask) in enumerate(zip(candidates, masks)):
                gain = int(np.count_nonzero(uncovered & mask))
                if not gain:
                    continue
                costs = []
                previous = state.pos
                for _, nxt in route:
                    costs.append(distance(previous, pos) + distance(pos, nxt)
                                 - distance(previous, nxt))
                    previous = nxt
                costs.append(distance(previous, pos))
                insertion = min(range(len(costs)), key=costs.__getitem__)
                score = gain**power / (costs[insertion] / 5 + 6 * n_unknown + 1)
                if best is None or score > best[0]:
                    best = (score, i, insertion)
            if best is None:
                break
            _, i, insertion = best
            route.insert(insertion, (-(i + 1), candidates[i]))
            uncovered &= ~masks[i]
        if np.any(uncovered):
            # 极小边缘格由通用探索补足；不能据此宣告完成。
            for index in np.flatnonzero(uncovered)[::max(1, np.count_nonzero(uncovered) // 10)]:
                pos = tuple(self.coverage.points[index])
                route.append((-10000 - int(index), pos))
                uncovered &= ~self.coverage.covered_at(pos)
                if not np.any(uncovered):
                    break
        route = self._route(state.pos, route)
        for _ in range(3):
            changed = False
            for node in list(route):
                if node[0] > 0:
                    continue
                i = route.index(node)
                other_masks = [self.coverage.covered_at(n[1]) for n in route if n != node]
                covered = np.any(other_masks, axis=0) if other_masks else np.zeros_like(remaining)
                critical = remaining & ~covered
                if not np.any(critical):
                    route.remove(node)
                    changed = True
                    continue
                valid = np.flatnonzero(np.all(masks[:, critical], axis=1))
                previous = state.pos if i == 0 else route[i - 1][1]
                nxt = route[i + 1][1] if i + 1 < len(route) else None
                def added(pos):
                    return distance(previous, pos) + (distance(pos, nxt) if nxt else 0)
                best = min(valid, key=lambda j: added(candidates[j]), default=None)
                if best is not None and added(candidates[best]) + 1e-5 < added(node[1]):
                    route[i] = (-(int(best) + 1), candidates[best])
                    changed = True
                refined = self._refine_station(previous, nxt, route[i][1],
                                               self.coverage.points[critical])
                if added(refined) + 1e-5 < added(route[i][1]):
                    route[i] = (route[i][0], refined)
                    changed = True
            if not changed:
                break
            route = self._route(state.pos, route)
        return route

    def _refine_station(self, previous, nxt, current, critical):
        """在保持所有独占覆盖格的前提下，将站位向行进路线移动。

        允许站位是以独占格心为圆心的圆盘交集；每个候选都重新检查全部
        约束，仅接受缩短路径的可行点。这里只优化站位，不改变排除证据。
        """
        points = np.asarray(convex_hull([tuple(p) for p in critical]))
        radius = self.coverage.cover_radius - 1e-5
        radius2 = radius * radius
        start = np.asarray(previous)
        finish = np.asarray(nxt) if nxt is not None else start
        best = np.asarray(current)
        def cost(pos):
            return distance(previous, pos) + (distance(pos, nxt) if nxt else 0)
        def project(pos):
            pos = np.asarray(pos).copy()
            for _ in range(40):
                delta = pos - points
                norm2 = np.sum(delta * delta, axis=1)
                i = int(np.argmax(norm2))
                if norm2[i] <= radius2 + 1e-7:
                    return pos
                pos = points[i] + delta[i] * radius / math.sqrt(norm2[i])
            return None
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            pos = project(start + fraction * (finish - start))
            if pos is not None and cost(pos) < cost(best):
                best = pos
        for step in (100., 25., 5.):
            for _ in range(4):
                delta = best - start
                grad = delta / max(1e-6, float(np.linalg.norm(delta)))
                if nxt:
                    delta = best - finish
                    grad += delta / max(1e-6, float(np.linalg.norm(delta)))
                pos = project(best - step * grad)
                if pos is None or cost(pos) >= cost(best) - 1e-5:
                    break
                best = pos
        # 当前离散站位始终作为保底，不用尚未验证可行的连续解替换它。
        if np.all(np.sum((points - best)**2, axis=1) <= self.coverage.cover_radius**2):
            return tuple(float(v) for v in best)
        return current

    def step(self, state: State):
        if self.done:
            return Action('done')
        if len(self.cleared | state.cleared) == 16:
            self.done = True
            self.completion_reason = 'cleared_maximum_16'
            return Action('done')
        if self.scan_pending:
            self._start_scan(state, force=self.exploring or not self.tracks)
            self.exploring = False
        while self.scan_queue:
            ch = self.scan_queue.pop(0)
            if ch not in self.cleared and ch not in self.absent:
                return Action('measure', state.pos, ch)

        if self.active_ch in self.tracks and self.active_ch not in self.cleared:
            return self._local_action(self.active_ch, state)
        destination = self._next_destination(state)
        if destination is not None:
            ch, pos = destination
            if ch > 0:
                self.active_ch = ch
                return self._local_action(ch, state)
            mask = self.coverage.covered_at(pos)
            channels = [ch for ch in self._unknown() if self.coverage.gain(ch, mask)]
            self.exploring = True
            self.scan_pending = True
            return Action('measure', pos, channels[0])
        action = self._explore_action(state)
        if action is not None:
            return action
        self.done = True
        self.completion_reason = 'all_channels_cleared_or_covered'
        return Action('done')

    def on_measure(self, state, ch, result, svd):
        if result == 'no_signal':
            self.negative_positions[ch].append(state.pos)
            self.coverage.exclude(ch, state.pos)
            if ch not in self.tracks and self.coverage.absent(ch):
                self.absent.add(ch)
            # 已发现的源不因失去信号而被永久丢弃。保留之前的有效测向。
            if ch == self.active_ch and ch in self.tracks:
                track = self.tracks[ch]
                poly = exclude_disk(track.poly, state.pos)
                if poly:
                    poly = p1.hpi_intersect(poly, reception_halfplanes(
                        [p for p, _ in track.records], [state.pos]))
                if not poly:
                    raise RuntimeError(f'频道 {ch} 的无信号响应与先前测向矛盾')
                track.poly = poly
                track.center, track.radius = enclosing_circle(poly)
                track.estimate = centroid(poly)
            return
        if result == 'near':
            track = self.tracks.setdefault(ch, Track())
            track.near = state.pos
            track.center, track.radius = state.pos, 5.0
            track.estimate = state.pos
            track.probe_after_fail = False
            return
        if result != 'direction' or svd is None or not math.isfinite(svd):
            raise ValueError(f'非法测向响应: {result}, {svd}')
        track = self.tracks.setdefault(ch, Track())
        if any(distance(state.pos, p) < 1e-5 for p, _ in track.records):
            return
        track.records.append((state.pos, svd))
        if track.poly:
            poly = track.poly
        else:
            poly = p1.clip_polygon_by_disk(
                [(-1800., -1800.), (1800., -1800.),
                 (1800., 1800.), (-1800., 1800.)], (0., 0.), ARENA_R, 64)
        poly = p1.hpi_intersect(poly, p1.make_sector_halfplanes(state.pos, svd, EPS_DEG))
        if poly:
            poly = p1.clip_polygon_by_disk(poly, state.pos, RECEIVE_MAX, 32)
        if poly and self.negative_positions[ch]:
            poly = p1.hpi_intersect(poly, reception_halfplanes(
                [p for p, _ in track.records], self.negative_positions[ch]))
        if poly:
            for pos in self.negative_positions[ch]:
                poly = exclude_disk(poly, pos)
                if not poly:
                    break
        if not poly:
            self.geometry_conflicts += 1
            raise RuntimeError(f'频道 {ch} 的有效测向约束无交集，需检查接口或误差模型')
        track.poly = poly
        track.center, track.radius = enclosing_circle(poly)
        track.estimate = centroid(poly)
        track.probe_after_fail = False

    def on_clear(self, state, ch, success):
        if success:
            self.cleared.add(ch)
            state.cleared.add(ch)
            self.active_ch = None
            self.scan_pending = True
        else:
            track = self.tracks[ch]
            track.failures += 1
            track.near = None
            # 不重试同一个清除点，也不把未清除源标记为完成。
            if track.failures > 3:
                raise RuntimeError(f'频道 {ch} 清除连续失败，检查真实设备规则')
            self.active_ch = ch
            track.probe_after_fail = True


def make_strategy(name='AdaptiveV8'):
    if name not in ('AdaptiveV8', 'v8'):
        raise ValueError(f'未知 v8 策略: {name}')
    return AdaptiveV8()
