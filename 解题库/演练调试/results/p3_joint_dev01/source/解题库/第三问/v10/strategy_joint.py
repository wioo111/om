"""P3 observation-only joint localization/routing experiments."""
import math

from strategy import State
from strategy_transit import ResidualP3
from strategy_v8 import distance


class ActionRouteP3(ResidualP3):
    name = 'ActionRouteP3'

    def _visit_cost(self, previous, node):
        ch, finish = node
        if ch <= 0:
            return distance(previous, finish)
        # The first localization measurement may not lie on the route to the estimate.
        action = self._local_action(ch, State(pos=previous, ch=ch))
        return distance(previous, action.pos) + distance(action.pos, finish)

    def _route(self, start, nodes):
        if len(nodes) < 2:
            return list(nodes)
        n = len(nodes)
        positions = [node[1] for node in nodes] + [start]
        costs = [[self._visit_cost(pos, node) if i != j else 0.
                  for j, node in enumerate(nodes)] for i, pos in enumerate(positions)]
        remaining = set(range(n))
        order, previous = [], n
        while remaining:
            chosen = min(remaining, key=lambda j: (costs[previous][j], j))
            order.append(chosen)
            remaining.remove(chosen)
            previous = chosen
        # Directed 2-opt: account for every reversed internal arc, not only endpoint edges.
        for _ in range(12):
            best = (-1e-6, None)
            prefix = [0.]
            for a, b in zip(order, order[1:]):
                prefix.append(prefix[-1] + costs[b][a] - costs[a][b])
            for i in range(n-1):
                prev = n if i == 0 else order[i-1]
                for j in range(i+1, n):
                    delta = costs[prev][order[j]] - costs[prev][order[i]] + prefix[j]-prefix[i]
                    if j+1 < n:
                        nxt = order[j+1]
                        delta += costs[order[i]][nxt] - costs[order[j]][nxt]
                    if delta < best[0]:
                        best = delta, (i, j)
            if best[1] is None:
                break
            i, j = best[1]
            order[i:j+1] = reversed(order[i:j+1])
        return [nodes[i] for i in order]

    def _cover_route(self, state, known, remaining, n_unknown):
        routes = [self._build_cover_route(state, known, remaining, n_unknown, power)
                  for power in (0.6, 1.0, 1.6)]
        def cost(route):
            previous, total = state.pos, 0.
            for node in route:
                total += self._visit_cost(previous, node)/5 + (6*n_unknown if node[0] < 0 else 0.)
                previous = node[1]
            return total
        route = min(routes, key=cost)
        return route[0] if route else None


class SurveyP3(ResidualP3):
    name = 'SurveyP3'

    def __init__(self):
        super().__init__()
        self._survey_measure = None
        self.local_survey_stops = 0

    def step(self, state):
        action = super().step(state)
        self._survey_measure = None
        if (action.kind == 'measure' and action.ch == self.active_ch
                and not self.scan_queue and distance(state.pos, action.pos) > 100.):
            self._survey_measure = action.ch
        return action

    def on_measure(self, state, ch, result, svd):
        super().on_measure(state, ch, result, svd)
        if self._survey_measure == ch:
            self.scan_pending = True
            self.local_survey_stops += 1
        self._survey_measure = None

    def diagnostics(self):
        result = super().diagnostics()
        result['local_survey_stops'] = self.local_survey_stops
        return result


class JointP3(SurveyP3, ActionRouteP3):
    name = 'JointP3'
