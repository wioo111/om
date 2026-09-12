"""仅用于开发对照：预测覆盖时折减不确定定位点的覆盖半径。

只改变规划预测，正式排除区域仍仅由 v8 的实际 no_signal 更新。
"""
import numpy as np
from strategy_v8 import distance
from strategy_v10 import RouteV10


class CautiousRouteV10(RouteV10):
    name = 'CautiousRouteV10'

    def _planned_mask(self, ch, pos):
        if ch < 0:
            return self.coverage.covered_at(pos)
        track = self.tracks[ch]
        uncertainty = track.radius + distance(track.center, pos)
        radius = max(0.0, self.coverage.cover_radius - 0.5 * uncertainty)
        return np.sum((self.coverage.points - pos)**2, axis=1) <= radius**2

    def _build_cover_route(self, state, known, remaining, n_unknown, power):
        """在已知目标路径中插入补充扫描点，以新增覆盖量/额外耗时选点。"""
        route = self._route(state.pos, known)
        uncovered = remaining.copy()
        for ch, pos in known:
            uncovered &= ~self._planned_mask(ch, pos)
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
                other_masks = [self._planned_mask(n[0], n[1]) for n in route if n != node]
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

