"""P3 observation-only joint localization/routing experiments."""
import math

from strategy import Action, State, p1
from strategy_transit import ResidualP3
from strategy_v8 import EPS_DEG, distance, centroid, enclosing_circle


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


class ProbePlanP3(ResidualP3):
    """One-step expected-cost probe selection; sampled beliefs are not source truth."""
    name = 'ProbePlanP3'

    def __init__(self):
        super().__init__()
        self.probe_plans = []

    @staticmethod
    def _belief_samples(poly):
        center = centroid(poly)
        samples = []
        for a, b in zip(poly, poly[1:]+poly[:1]):
            weight = abs((a[0]-center[0])*(b[1]-center[1]) - (a[1]-center[1])*(b[0]-center[0]))
            if weight > 1e-9:
                samples.append((((center[0]+a[0]+b[0])/3,
                                 (center[1]+a[1]+b[1])/3), weight))
        total = sum(w for _, w in samples)
        return [(point, w/total) for point, w in samples]

    @staticmethod
    def _probe_cost(current, point, poly, samples):
        value = distance(current, point)/5 + 5.
        for truth, weight in samples:
            d = distance(point, truth)
            if d < 5.:
                value += weight*5.
                continue
            # Conservative planning penalty for a possible no-signal response at the old probe.
            if d > 1000.:
                value += weight*(d/5 + 30.)
                continue
            angle = math.degrees(math.atan2(truth[1]-point[1], truth[0]-point[0])) % 360
            for error, ew in ((-1., .25), (0., .5), (1., .25)):
                observed = round((angle+error) % 360, 2) % 360
                posterior = p1.hpi_intersect(poly, p1.make_sector_halfplanes(point, observed, EPS_DEG))
                if not posterior:
                    return math.inf
                center, radius = enclosing_circle(posterior)
                if radius <= 20. - 1e-5:
                    continuation = max(0., distance(point, center)-(20-radius-1e-5))/5+5.
                else:
                    estimate = centroid(posterior)
                    miss = distance(estimate, truth)
                    continuation = distance(point, estimate)/5
                    if radius <= 80. and miss <= 20.:
                        continuation += 5.
                    else:
                        continuation += 10. + max(0., miss-20.)/5
                        if radius <= 80.:
                            continuation += 3.
                value += weight*ew*continuation
        return value

    def step(self, state):
        action = super().step(state)
        if action.kind != 'measure' or action.ch != self.active_ch:
            return action
        track = self.tracks.get(action.ch)
        if (track is None or len(track.records) != 1 or track.probe_after_fail
                or distance(state.pos, action.pos) < 1. or not track.poly):
            return action
        old, angle = track.records[0]
        theta = math.radians(angle)
        ux, uy = math.cos(theta), math.sin(theta)
        length = distance(old, track.estimate)
        samples = self._belief_samples(track.poly)
        best_point = action.pos
        baseline = self._probe_cost(state.pos, action.pos, track.poly, samples)
        best_cost = baseline
        for fraction in (.45, .65, .85, 1.):
            for lateral in (50., 100., 200.):
                options = [(old[0]+fraction*length*ux-sign*lateral*uy,
                            old[1]+fraction*length*uy+sign*lateral*ux) for sign in (-1, 1)]
                point = min(options, key=lambda p: distance(state.pos, p))
                if max(distance(point, vertex) for vertex in track.poly) > 999.99:
                    continue
                if any(distance(point, p) < 10. for p, _ in track.records):
                    continue
                score = self._probe_cost(state.pos, point, track.poly, samples)
                if score < best_cost-1e-6:
                    best_point, best_cost = point, score
        if best_point != action.pos:
            self.probe_plans.append(dict(ch=action.ch, old=action.pos, chosen=best_point,
                                         predicted_old_s=baseline, predicted_new_s=best_cost))
            return Action('measure', best_point, action.ch)
        return action

    def diagnostics(self):
        result = super().diagnostics()
        result['probe_plans'] = self.probe_plans
        return result


class PlanJointP3(ProbePlanP3, JointP3):
    name = 'PlanJointP3'
