"""P4 online joint route for required survey stations and certified clear tasks.

Plans use only current positive observations and actual robot position. Every
unseen channel still receives a complete continuous discovery certificate.
HuntP4 remains unchanged as the deployed baseline.
"""
import math

from strategy import Action
from strategy_fast import FastP4
from strategy_hunt import HuntP4
from strategy_p4 import CHANNELS, distance
from discovery_prune import choose_replacement


def path_length(nodes, start):
    total = 0.0
    for node in nodes:
        total += distance(start, node[2])
        start = node[2]
    return total


def joint_path(stations, tasks, start):
    """Bounded deterministic open TSP heuristic; no scene information is used."""
    nodes = [('scan', i, p) for i, p in enumerate(stations)]
    nodes += [('clear', ch, p) for ch, p in tasks]
    remaining = list(nodes)
    nearest = []
    pos = start
    while remaining:
        nxt = min(remaining, key=lambda n: (distance(pos, n[2]), n[0], n[1]))
        nearest.append(nxt)
        remaining.remove(nxt)
        pos = nxt[2]
    # A scan backbone with cheapest task insertions provides a second initial
    # route. The backbone is itself merely a plan; visits are recorded separately.
    inserted = nodes[:len(stations)]
    for node in nodes[len(stations):]:
        def extra(i):
            a = start if i == 0 else inserted[i - 1][2]
            gain = distance(a, node[2])
            if i < len(inserted):
                gain += distance(node[2], inserted[i][2]) - distance(a, inserted[i][2])
            return gain
        index = min(range(len(inserted) + 1), key=lambda i: (extra(i), i))
        inserted.insert(index, node)

    def improve(route):
        route = route[:]
        for _ in range(64):
            best = None
            for i in range(len(route) - 1):
                before = start if i == 0 else route[i - 1][2]
                for j in range(i + 1, len(route)):
                    gain = distance(before, route[i][2]) - distance(before, route[j][2])
                    if j + 1 < len(route):
                        after = route[j + 1][2]
                        gain += distance(route[j][2], after) - distance(route[i][2], after)
                    if gain > 1e-7 and (best is None or gain > best[0]):
                        best = gain, i, j
            if best is None:
                break
            _, i, j = best
            route[i:j + 1] = reversed(route[i:j + 1])
        # One-node relocations address clusters that segment reversal cannot.
        for _ in range(8):
            best = None
            for i, node in enumerate(route):
                a = start if i == 0 else route[i - 1][2]
                saving = distance(a, node[2])
                if i + 1 < len(route):
                    b = route[i + 1][2]
                    saving += distance(node[2], b) - distance(a, b)
                reduced = route[:i] + route[i + 1:]
                for j in range(len(reduced) + 1):
                    before = start if j == 0 else reduced[j - 1][2]
                    cost = distance(before, node[2])
                    if j < len(reduced):
                        after = reduced[j][2]
                        cost += distance(node[2], after) - distance(before, after)
                    gain = saving - cost
                    if gain > 1e-7 and (best is None or gain > best[0]):
                        best = gain, i, j
            if best is None:
                break
            _, i, j = best
            node = route.pop(i)
            route.insert(j, node)
        return route

    alternatives = [improve(nearest), improve(inserted)]
    return min(alternatives, key=lambda route: path_length(route, start))


class RouteAwareP4(HuntP4):
    name = 'RouteAwareP4_joint21'

    def __init__(self, adaptive_scan=True, scan_investments=0):
        super().__init__(hunt=True, early_hunt=False, grid='compact', adapt=False, insertion=False)
        self.name = type(self).name
        self.pending_stations = list(self.core_stations)
        self.current_station = None
        self.completed_stations = set()
        self.route_history = []
        self._state = None
        self.adaptive_scan = bool(adaptive_scan)
        self.survey_changed = False
        self._consider_scan_stop = False
        self.replacement_history = []
        self.scan_investments = max(0, min(6, int(scan_investments)))
        self.invested_scan_points = []

    def _queued_channels(self):
        channels = [ch for ch in CHANNELS if self._needs_sample(ch)]
        # A measure at the currently selected channel avoids one paid switch.
        # Every other queued channel remains present exactly once.
        if self._state.ch in channels:
            channels.remove(self._state.ch)
            channels.insert(0, self._state.ch)
        return channels

    def _finish_with_evidence(self):
        unseen = set(CHANNELS) - self.ever_observed_channels
        if len(self.ever_observed_channels) < 16:
            actual = set.intersection(*(self.actual_scan_points[ch] for ch in unseen))
            if not set(self.core_stations) <= actual:
                if not self.survey_changed or not self.coverage_certifier.certified_complete(actual):
                    raise RuntimeError('joint_route_missing_actual_discovery_evidence')
        self.core_complete = True
        self.hunt_events['joint_discovery_completed'] += 1
        self._finish_discovery()

    def _route_next(self):
        state = self._state
        if self._consider_scan_stop and self.adaptive_scan and self.pending_stations and len(self.ever_observed_channels) < 16:
            self._consider_scan_stop = False
            unseen = set(CHANNELS) - self.ever_observed_channels
            actual = set.intersection(*(self.actual_scan_points[ch] for ch in unseen))
            replacement = choose_replacement(actual, self.pending_stations, state.pos, state.pos,
                                              checker=self.coverage_certifier)
            self.replacement_history.append(replacement)
            if replacement['removed']:
                self.pending_stations = replacement['remaining']
                self.current_station = tuple(state.pos)
                self._station_channels = self._queued_channels()
                self.discovery_channel_index = 0
                self.survey_changed = True
                self.hunt_events['clear_stop_used_for_discovery'] += 1
                self.hunt_events['proved_scan_station_removed'] += len(replacement['removed'])
                return None
            radius = math.hypot(*state.pos)
            if (len(self.invested_scan_points) < self.scan_investments
                    and 800.0 <= radius <= 1500.0
                    and all(distance(state.pos, p) >= 400.0 for p in actual)):
                # A bounded cost investment at a position already reached for
                # clear. No pending station is removed by this heuristic.
                # Later deletions still require the full continuous certificate.
                self.current_station = tuple(state.pos)
                self._station_channels = self._queued_channels()
                self.discovery_channel_index = 0
                self.invested_scan_points.append(tuple(state.pos))
                self.hunt_events['bounded_additional_scan_at_clear_stop'] += 1
                return None
        ready = {}
        for ch, track in self.tracks.items():
            if ch in self.cleared:
                continue
            if track.near is not None or self._certificate(ch) is not None:
                plan = self._cover(ch, state.pos)
                if plan is not None:
                    ready[ch] = plan
        if len(self.ever_observed_channels) >= 16 and all(ch in self.cleared or ch in ready for ch in self.ever_observed_channels):
            # This derives the public maximum solely from positive observations.
            self.pending_stations.clear()
            self.hunt_events['sixteen_sources_retire_remaining_stations'] += 1
        if not self.pending_stations:
            self._finish_with_evidence()
            return None
        route = joint_path(self.pending_stations, [(ch, self._target(ch)) for ch in ready], state.pos)
        if not route:
            raise RuntimeError('empty_joint_plan_with_pending_stations')
        self.route_history.append(dict(position=state.pos, scan_points=len(self.pending_stations),
                                       ready_channels=sorted(ready), planned_distance_m=path_length(route, state.pos),
                                       next_kind=route[0][0], next_key=route[0][1]))
        kind, key, point = route[0]
        self.hunt_events['joint_route_planned'] += 1
        if kind == 'clear':
            self.hunt_events['joint_clear_before_scan'] += 1
            return self._start_plan(key, ready[key])
        # Reordering happens between complete stations, never mid-channel queue.
        self.pending_stations = [node[2] for node in route if node[0] == 'scan']
        self.current_station = self.pending_stations.pop(0)
        self._station_channels = self._queued_channels()
        self.discovery_channel_index = 0
        return None

    def _next_discovery_action(self):
        while True:
            if self.current_station is not None:
                while self.discovery_channel_index < len(self._station_channels):
                    ch = self._station_channels[self.discovery_channel_index]
                    self.discovery_channel_index += 1
                    if self._needs_sample(ch):
                        return Action('measure', self.current_station, ch)
                self.completed_stations.add(self.current_station)
                self.current_station = None
                self.discovery_station_index += 1
                self._station_channels = []
            action = self._route_next()
            if action is not None:
                return action
            if self.discovery_complete:
                return None

    def step(self, state):
        self._state = state
        if self.done:
            return Action('done')
        if self.early_plan:
            self.action_stage = 'joint_optical_clear'
            return Action('clear', self.early_plan['points'][0], self.early_plan['channel'])
        for ch, track in self.tracks.items():
            if ch not in self.cleared and track.near is not None and distance(state.pos, track.near) < 1e-6:
                self.action_stage = 'near_clear'
                return self._start_plan(ch, self._cover(ch, state.pos))
        # The stable driver contract dispatches our scan and local hooks. Avoid
        # ancestor Hunt's independent greedy clear insertion running a second time.
        action = FastP4.step(self, state)
        self.action_stage = 'joint_optical_clear' if action.kind == 'clear' and self.early_plan else self.phase
        return action

    def diagnostics(self):
        result = super().diagnostics()
        result.update(joint_route=True, route_history=self.route_history,
                      actual_completed_station_count=len(self.completed_stations),
                      adaptive_scan=self.adaptive_scan, replacement_history=self.replacement_history,
                      scan_investments=self.scan_investments, invested_scan_points=self.invested_scan_points)
        return result

    def on_clear(self, state, ch, success):
        super().on_clear(state, ch, success)
        if success and self.phase == 'discovery':
            self._consider_scan_stop = True
