"""开发对照：保留 v8 搜索站位，仅在最终计划有明确缩短时调整访问顺序。"""
from strategy_v8 import AdaptiveV8, CLEAR_R, distance
from route_search import route_order


class GuardedRouteV10(AdaptiveV8):
    name = 'GuardedRouteV10'

    def _cover_route(self, state, known, remaining, n_unknown):
        # 构造/插入/收缩搜索站位完全使用 v8，避免每次内部排序都改变站位。
        routes = [self._build_cover_route(state, known, remaining, n_unknown, power)
                  for power in (0.6, 1.0, 1.6)]
        def cost(route):
            positions = [state.pos] + [pos for _, pos in route]
            return (sum(distance(a, b) for a, b in zip(positions, positions[1:]))
                    + 30 * n_unknown * sum(ch < 0 for ch, _ in route))
        original = min(routes, key=cost)
        improved = []
        for route in routes:
            if not route:
                continue
            order = route_order(tuple(state.pos), tuple(tuple(pos) for _, pos in route))
            improved.append([route[i] for i in order])
        best = min(improved, key=cost) if improved else original
        # 小于两个清除半径的预测差异不触发换序；它只是规划容差，不是收益证明。
        selected = best if cost(best) + 2 * CLEAR_R < cost(original) else original
        return selected[0] if selected else None
