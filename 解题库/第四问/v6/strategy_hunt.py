"""P4 candidate: certified triangular discovery and bounded early local work.

No hidden source count/radius, P3 imports, or no-signal localization exclusions.
The old FastP4 and FinishP4 are left runnable unchanged.
"""
import math
from collections import Counter
from shapely.geometry import Polygon

from strategy import Action
from strategy_fast import FastP4, nearest_path
from strategy_finish import FinishP4
from strategy_p4 import CHANNELS, DISCOVERY_STATIONS, distance
from strategy_cost import optical_cover
from discovery_mesh import MESH_STATIONS, MESH_CERTIFICATE
from discovery_rings import RING_STATIONS, RING_CERTIFICATE
from discovery_compact import COMPACT_STATIONS, COMPACT_CERTIFICATE, build_coverage_certifier
from local_hunt import LocalHuntPlanner
from discovery_coverage import CoverageCertifier


class HuntP4(FinishP4):
    def __init__(self, hunt=True, early_hunt=False, grid='compact', adapt=True, insertion=True):
        super().__init__(enabled=True, trim_corners=False)
        self.hunt = bool(hunt)
        self.early_hunt = bool(early_hunt)
        self.adapt = bool(adapt and hunt)
        self.insertion = bool(insertion)
        self.coverage_certifier = build_coverage_certifier() if grid == 'compact' else CoverageCertifier()
        self.reanchored = False
        self._anchor_checks = set()
        if grid not in ('mesh', 'rings', 'compact'):
            raise ValueError('grid must be mesh, rings or compact')
        self.grid = grid
        self.core_stations, self.core_certificate = {
            'mesh': (MESH_STATIONS, MESH_CERTIFICATE),
            'rings': (RING_STATIONS, RING_CERTIFICATE),
            'compact': (COMPACT_STATIONS, COMPACT_CERTIFICATE),
        }[grid]
        self.name = ('HuntP4_' if hunt else 'MeshP4_') + grid + str(len(self.core_stations))
        self.discovery_stations = list(self.core_stations) + nearest_path(
            set(DISCOVERY_STATIONS), self.core_stations[-1])
        self.ever_observed_channels = set()
        self.actual_scan_points = {ch: set() for ch in CHANNELS}
        self.local_planner = LocalHuntPlanner(max_probes=8)
        self.active_hunt = None
        self.early_plan = None
        self.held_action = None
        self.hunt_versions = {}
        self.hunt_events = Counter()
        self._issued_local = set()

    def _needs_sample(self, ch):
        if len(self.ever_observed_channels) >= 16 and ch not in self.ever_observed_channels:
            return False
        if self.hunt and ch in self.tracks and ch not in self.cleared:
            certificate = self._certificate(ch)
            if certificate and len(certificate['points']) <= 3:
                return False
        return super()._needs_sample(ch)

    def _next_discovery_action(self):
        while self.discovery_station_index < len(self.discovery_stations):
            if self._station_channels and self.discovery_channel_index >= len(self._station_channels):
                self.discovery_station_index += 1
                self.discovery_channel_index = 0
                self._station_channels = []
                continue
            if self.discovery_station_index >= len(self.core_stations) and not self.core_complete:
                # Check actual per-channel evidence, never merely a cursor value.
                for ch in set(CHANNELS) - self.ever_observed_channels:
                    if len(self.ever_observed_channels) < 16 and not set(self.core_stations) <= self.actual_scan_points[ch]:
                        if not self.reanchored or not self.coverage_certifier.certified_complete(self.actual_scan_points[ch]):
                            raise RuntimeError('incomplete_directional_discovery_certificate')
                self.core_complete = True
                self.absent = set(CHANNELS) - self.ever_observed_channels
                self.hunt_events['mesh_coverage_completed'] += 1
                if self.hunt:
                    self._finish_discovery()
                    return None
            if not self._station_channels:
                self._station_channels = [ch for ch in CHANNELS if self._needs_sample(ch)]
                self.discovery_channel_index = 0
            if not self._station_channels:
                self.discovery_station_index += 1
                continue
            ch = self._station_channels[self.discovery_channel_index]
            self.discovery_channel_index += 1
            if self._needs_sample(ch):
                return Action('measure', self.discovery_stations[self.discovery_station_index], ch)
        self._finish_discovery()
        return None

    def _cover(self, ch, pos):
        track = self.tracks[ch]
        if track.near is not None:
            return dict(points=[tuple(track.near)], total_s=distance(pos, track.near) / 5.0 + 5.0)
        if len(track.poly) < 3:
            return None
        region = Polygon(track.poly)
        if not region.is_valid or region.is_empty:
            return None
        # All vertices in the convex clear disk proves the COMPLETE polygon.
        if max(distance(pos, v) for v in track.poly) < 19.99999:
            return dict(points=[tuple(pos)], total_s=5.0)
        if track.radius < 19.99999:
            d = distance(pos, track.center)
            shift = min(d, 19.99999 - track.radius)
            point = tuple(track.center[i] + (pos[i] - track.center[i]) * shift / d for i in (0, 1)) if d else tuple(pos)
            return dict(points=[point], total_s=distance(pos, point) / 5.0 + 5.0)
        return optical_cover(region, pos, limit=6)

    def _start_plan(self, ch, plan):
        if not plan or not plan['points']:
            raise RuntimeError('empty_early_optical_plan')
        self.early_plan = dict(channel=ch, points=list(plan['points']))
        self.hunt_events['early_plan_started'] += 1
        return Action('clear', self.early_plan['points'][0], ch)

    def _hunt_action(self, state):
        ch = self.active_hunt
        if ch in self.cleared:
            self.active_hunt = None
            return None
        plan = self._cover(ch, state.pos)
        if plan is not None:
            return self._start_plan(ch, plan)
        action = self.local_planner.next_probe(self.tracks[ch], state, ch)
        if action is None:
            self.hunt_events['bounded_hunt_fallback'] += 1
            self.hunt_versions[ch] = len(self.tracks[ch].records)
            self.active_hunt = None
        return action

    def _reanchor_scan(self, state):
        action = self.held_action
        index = self.discovery_station_index
        if (not self.adapt or action is None or action.kind != 'measure'
                or self.phase != 'discovery' or index >= len(self.core_stations)
                or self.discovery_channel_index > 1 or distance(state.pos, action.pos) < 1e-6):
            return
        key = (index, tuple(state.pos))
        if key in self._anchor_checks:
            return
        self._anchor_checks.add(key)
        # Source-clear detours change the starting position. Reorder only whole,
        # still-unvisited scan stations; every channel's required set is preserved.
        tail = self.discovery_stations[index:len(self.core_stations)]
        def path_length(points):
            return sum(distance(a, b) for a, b in zip([state.pos] + points, points))
        best = tail[:]
        trial = nearest_path(tail, state.pos)
        if path_length(trial) < path_length(best):
            best = trial
        for _ in range(24):
            improvement = None
            for i in range(len(best) - 1):
                a = state.pos if i == 0 else best[i - 1]
                for j in range(i + 1, len(best)):
                    gain = distance(a, best[i]) - distance(a, best[j])
                    if j + 1 < len(best):
                        gain += distance(best[j], best[j + 1]) - distance(best[i], best[j + 1])
                    if gain > 1e-7 and (improvement is None or gain > improvement[0]):
                        improvement = (gain, i, j)
            if improvement is None:
                break
            _, i, j = improvement
            best[i:j + 1] = reversed(best[i:j + 1])
        if path_length(best) + 1e-7 < path_length(tail):
            self.discovery_stations[index:len(self.core_stations)] = best
            action = Action('measure', best[0], action.ch)
            self.held_action = action
            self.hunt_events['remaining_scan_route_shortened'] += 1
        unknown = set(CHANNELS) - self.ever_observed_channels
        if not unknown or len(self.ever_observed_channels) >= 16:
            return
        actual = set.intersection(*(self.actual_scan_points[ch] for ch in unknown))
        future = set(self.discovery_stations[index + 1:len(self.core_stations)])
        # This certificate only changes a future plan. Absence later requires
        # a second certificate built solely from actual channel measurements.
        if self.coverage_certifier.certified_complete(actual | future | {tuple(state.pos)}):
            self.discovery_stations[index] = tuple(state.pos)
            self.held_action = Action('measure', tuple(state.pos), action.ch)
            self.reanchored = True
            self.hunt_events['clear_stop_replaces_scan_station'] += 1

    def step(self, state):
        if self.done:
            return Action('done')
        if self.early_plan:
            self.action_stage = 'early_clear'
            return Action('clear', self.early_plan['points'][0], self.early_plan['channel'])
        # A near reply always permits a zero-movement clear without touching scan cursors.
        for ch, track in self.tracks.items():
            if ch not in self.cleared and track.near is not None and distance(track.near, state.pos) < 1e-6:
                self.action_stage = 'near_clear'
                return self._start_plan(ch, self._cover(ch, state.pos))
        if self.active_hunt is not None:
            action = self._hunt_action(state)
            if action is not None:
                self.action_stage = 'early_clear' if action.kind == 'clear' else 'early_localization'
                return action
        self._reanchor_scan(state)
        action = self.held_action
        self.held_action = None
        if action is None or action.ch in self.cleared:
            action = super().step(state)
        # Interpose only between scan stations, after the full queued station was read.
        if self.hunt and self.phase == 'discovery' and action.kind == 'measure' and distance(state.pos, action.pos) > 1e-6:
            ready = []
            for ch, track in self.tracks.items():
                if ch in self.cleared:
                    continue
                plan = self._cover(ch, state.pos)
                if plan is not None:
                    last = plan['points'][-1]
                    extra = plan['total_s'] + (distance(last, action.pos) - distance(state.pos, action.pos)) / 5.0
                    future_best = math.inf
                    if self.insertion and not self.core_complete and len(self.ever_observed_channels) < 16:
                        target = self._target(ch)
                        remaining = self.discovery_stations[self.discovery_station_index:len(self.core_stations)]
                        for a, b in zip(remaining, remaining[1:]):
                            future_best = min(future_best, (distance(a, target) + distance(target, b) - distance(a, b)) / 5.0 + 5.0)
                    if extra <= 160.0 and extra <= future_best + 8.0:
                        ready.append((extra, ch, plan))
            if ready:
                _, ch, plan = min(ready, key=lambda row: (row[0], row[1]))
                self.held_action = action
                self.action_stage = 'early_clear'
                return self._start_plan(ch, plan)
            # A bounded local task starts close to a fresh positive observation.
            eligible = [ch for ch, t in self.tracks.items() if ch not in self.cleared
                        and t.records and self.hunt_versions.get(ch) != len(t.records)
                        and len(self.local_planner.history.get(ch, [])) < self.local_planner.max_probes
                        and min(distance(state.pos, p) for p, _ in t.records) <= 1050.0]
            if eligible and self.early_hunt:
                ch = min(eligible, key=lambda c: (distance(state.pos, self._target(c)), c))
                self.active_hunt = ch
                follow = self._hunt_action(state)
                if follow is not None:
                    self.held_action = action
                    self.action_stage = 'early_clear' if follow.kind == 'clear' else 'early_localization'
                    return follow
        self.action_stage = self.phase
        return action

    def _next_local_action(self, ch, state):
        action = super()._next_local_action(ch, state)
        ch = action.ch
        if self.hunt and ch not in self.plans:
            plan = self._cover(ch, state.pos)
            if plan is not None:
                return self._start_plan(ch, plan)
            if action.kind == 'measure':
                better = self.local_planner.next_probe(self.tracks[ch], state, ch)
                if better is not None:
                    action = better
        if action.kind == 'measure':
            key = (ch, tuple(action.pos), len(self.tracks[ch].records))
            if key in self._issued_local:
                raise RuntimeError('localization_no_progress: repeated fixed-position action')
            self._issued_local.add(key)
        return action

    def on_measure(self, state, ch, result, svd):
        self.actual_scan_points[ch].add(tuple(state.pos))
        if result in ('direction', 'near'):
            self.ever_observed_channels.add(ch)
        super().on_measure(state, ch, result, svd)

    def on_clear(self, state, ch, success):
        if self.early_plan is None or self.early_plan['channel'] != ch:
            return super().on_clear(state, ch, success)
        if success:
            old_index = self.work_index
            FastP4.on_clear(self, state, ch, True)
            if self.phase == 'discovery':
                self.work_index = old_index
            self.early_plan = None
            self.active_hunt = None
            self.plans.pop(ch, None)
            self.hunt_events['early_clear_success'] += 1
        else:
            self.failed_clears.setdefault(ch, []).append(tuple(state.pos))
            self.tracks[ch].clear_failures += 1
            self.tracks[ch].recovery_required = False
            self.early_plan['points'].pop(0)
            self.hunt_events['early_clear_miss_advance'] += 1
            if not self.early_plan['points']:
                raise RuntimeError('early_optical_cover_exhausted: inconsistent observations')

    def diagnostics(self):
        result = super().diagnostics()
        result.update(hunt=self.hunt, early_hunt=self.early_hunt, grid=self.grid, adapt=self.adapt, insertion=self.insertion,
                      mesh_certificate=self.core_certificate,
                      ever_observed_channels=sorted(self.ever_observed_channels),
                      local_planner=self.local_planner.diagnostics())
        result['triggers'].update(self.hunt_events)
        return result
