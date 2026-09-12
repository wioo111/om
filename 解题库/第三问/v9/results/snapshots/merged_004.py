"""第三问合并迭代版：统一路线优化与测向动作，不依赖 A/B 候选文件。"""
import math
import numpy as np

from strategy import Action
from strategy_v8 import AdaptiveV8, distance


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

    def __init__(self, known_first=False, actual_scan_cost=False, transit_scan=False, **kwargs):
        kwargs.setdefault('first_hop', 200.0)
        kwargs.setdefault('lateral', 100.0)
        kwargs.setdefault('probe_radius', 50.0)
        super().__init__(**kwargs)
        self.known_first = known_first
        self.actual_scan_cost = actual_scan_cost
        self.transit_scan = transit_scan

    def step(self, state):
        action = super().step(state)
        if (not self.transit_scan or action.kind == 'done'
                or distance(state.pos, action.pos) < 650):
            return action
        unknown = self._unknown()
        if not unknown:
            return action
        endpoint = self.coverage.covered_at(action.pos)
        minimum = len(self.coverage.points) * 0.015
        best = None
        for fraction in (1/3, 1/2, 2/3):
            pos = tuple(a + (b-a)*fraction for a,b in zip(state.pos, action.pos))
            unique = self.coverage.covered_at(pos) & ~endpoint
            gains = {ch: self.coverage.gain(ch, unique) for ch in unknown}
            channels = [ch for ch in unknown if gains[ch] >= minimum]
            if channels:
                score = sum(gains[ch] for ch in channels) / (6 * len(channels))
                if best is None or score > best[0]:
                    best = score, pos, channels
        if best is not None:
            _, pos, channels = best
            self.scan_queue = channels[1:]
            self.scan_pending = False
            self.exploring = False
            return Action('measure', pos, channels[0])
        return action

    def _next_destination(self, state):
        if self.known_first:
            known = [(ch, track.estimate) for ch, track in self.tracks.items()
                     if ch not in self.cleared]
            if known:
                return self._route(state.pos, known)[0]
        return super()._next_destination(state)

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
        powers = (0.3, 0.6, 1.0, 1.6, 2.2) if self.actual_scan_cost else (1.0, 1.6)
        routes = [self._build_cover_route(state, known, remaining, n_unknown, power)
                  for power in powers]
        routes = [route for route in routes if route]
        if not routes:
            return None
        def cost(route):
            previous = state.pos
            value = 0.0
            future = {ch: self.coverage.remaining[ch].copy() for ch in self._unknown()}
            for ch, pos in route:
                value += distance(previous, pos) / 5
                if self.actual_scan_cost:
                    mask = self.coverage.covered_at(pos)
                    for channel, area in future.items():
                        gain = np.count_nonzero(area & mask)
                        threshold = 1 if ch < 0 else max(1, min(
                            len(area) * self.scan_fraction, np.count_nonzero(area) * 0.8))
                        if gain >= threshold:
                            value += 6
                            area &= ~mask
                elif ch < 0:
                    value += 4 * n_unknown
                previous = pos
            return value
        return min(routes, key=cost)[0]


def make_strategy():
    return AdaptiveV9()


def make_direct():
    return AdaptiveV9(first_hop=None, lateral=60.0)


def make_scan():
    return AdaptiveV9(scan_fraction=0.18)


def make_direct_scan():
    return AdaptiveV9(first_hop=None, lateral=60.0, scan_fraction=0.18)


def make_eager():
    return AdaptiveV9(first_hop=None, lateral=60.0, scan_fraction=0.03)


def make_mid():
    return AdaptiveV9(first_hop=None, lateral=60.0, scan_fraction=0.06)


def make_eager_short():
    return AdaptiveV9(scan_fraction=0.03)


def make_known_direct():
    return AdaptiveV9(known_first=True, first_hop=None, lateral=60.0, scan_fraction=0.06)


def make_known_short():
    return AdaptiveV9(known_first=True, scan_fraction=0.06)


def make_known_sparse():
    return AdaptiveV9(known_first=True, first_hop=None, lateral=60.0)


def make_cost():
    return AdaptiveV9(actual_scan_cost=True, first_hop=None, lateral=60.0, scan_fraction=0.06)


def make_transit():
    return AdaptiveV9(transit_scan=True, first_hop=None, lateral=60.0, scan_fraction=0.06)


def make_cost_transit():
    return AdaptiveV9(actual_scan_cost=True, transit_scan=True, first_hop=None,
                      lateral=60.0, scan_fraction=0.06)
