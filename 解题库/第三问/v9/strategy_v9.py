"""第三问 v9：合并后的单一策略入口。

保留完整搜索证明；不读取源位置、源数量、接收半径或测试种子。
"""
from strategy import p1
from strategy_v8 import (AdaptiveV8, distance, exclude_disk, reception_halfplanes,
                         enclosing_circle, centroid)


def polish_route(start, nodes, max_rounds=30):
    """开放路径的 2-opt 与单节点重插入；每次只接受真实净缩短。"""
    nodes = list(nodes)
    if len(nodes) < 2:
        return nodes
    points = [start] + [node[1] for node in nodes]
    distances = [[distance(a, b) for b in points] for a in points]
    n = len(nodes)
    order = list(range(1, n + 1))
    for _ in range(max_rounds):
        best_gain = 1e-7
        operation = None
        for i in range(n - 1):
            previous = order[i - 1] if i else 0
            for j in range(i + 1, n):
                gain = distances[previous][order[i]] - distances[previous][order[j]]
                if j + 1 < n:
                    nxt = order[j + 1]
                    gain += distances[order[j]][nxt] - distances[order[i]][nxt]
                if gain > best_gain:
                    best_gain, operation = gain, ('reverse', i, j)
        for i, node in enumerate(order):
            previous = order[i - 1] if i else 0
            nxt = order[i + 1] if i + 1 < n else None
            saving = distances[previous][node]
            if nxt is not None:
                saving += distances[node][nxt] - distances[previous][nxt]
            reduced = order[:i] + order[i + 1:]
            for gap in range(n):
                if gap == i:
                    continue
                a = reduced[gap - 1] if gap else 0
                b = reduced[gap] if gap < n - 1 else None
                added = distances[a][node]
                if b is not None:
                    added += distances[node][b] - distances[a][b]
                gain = saving - added
                if gain > best_gain:
                    best_gain, operation = gain, ('relocate', i, gap)
        if operation is None:
            break
        kind, i, j = operation
        if kind == 'reverse':
            order[i:j + 1] = reversed(order[i:j + 1])
        else:
            node = order.pop(i)
            order.insert(j, node)
    return [nodes[i - 1] for i in order]


class AdaptiveV9(AdaptiveV8):
    name = 'AdaptiveV9'

    def __init__(self, opportunistic_radius=300.0, **kwargs):
        kwargs.setdefault('first_hop', None)
        kwargs.setdefault('lateral', 40.0)
        kwargs.setdefault('probe_radius', 80.0)
        kwargs.setdefault('scan_fraction', 0.10)
        super().__init__(**kwargs)
        self.opportunistic_radius = opportunistic_radius


    def _start_scan(self, state, force=False):
        super()._start_scan(state, force)
        self.scan_queue = [ch for ch in self.scan_queue if ch not in self.tracks
                           or self.tracks[ch].radius > self.opportunistic_radius]

    def on_measure(self, state, ch, result, svd):
        super().on_measure(state, ch, result, svd)
        if (result == 'no_signal' and ch != self.active_ch and ch in self.tracks
                and self.tracks[ch].poly):
            track = self.tracks[ch]
            poly = exclude_disk(track.poly, state.pos)
            if poly:
                poly = p1.hpi_intersect(poly, reception_halfplanes(
                    [pos for pos, _ in track.records], [state.pos]))
            if not poly:
                raise RuntimeError(f'频道 {ch} 的沿途无信号响应与测向矛盾')
            track.poly = poly
            track.center, track.radius = enclosing_circle(poly)
            track.estimate = centroid(poly)

    @staticmethod
    def _route(start, nodes):
        nodes = list(nodes)
        if len(nodes) < 2:
            return nodes
        starts = sorted(range(len(nodes)), key=lambda i: distance(start, nodes[i][1]))[:3]
        candidates = []
        for first in starts:
            remaining = nodes[:]
            route = [remaining.pop(first)]
            while remaining:
                nxt = min(range(len(remaining)),
                          key=lambda i: distance(route[-1][1], remaining[i][1]))
                route.append(remaining.pop(nxt))
            candidates.append(polish_route(start, route))
        def cost(route):
            return distance(start, route[0][1]) + sum(
                distance(a[1], b[1]) for a, b in zip(route, route[1:]))
        return min(candidates, key=cost)

    def _cover_route(self, state, known, remaining, n_unknown):
        routes = [self._build_cover_route(state, known, remaining, n_unknown, power)
                  for power in (1.0, 1.6)]
        routes = [route for route in routes if route]
        if not routes:
            return None
        def cost(route):
            previous = state.pos
            value = 0.0
            for ch, pos in route:
                value += distance(previous, pos) / 5
                if ch < 0:
                    value += 4 * n_unknown
                previous = pos
            return value
        return min(routes, key=cost)[0]


def make_strategy():
    return AdaptiveV9()
