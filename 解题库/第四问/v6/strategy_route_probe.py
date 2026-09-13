"""At most two valuable, zero-detour one-bearing probes per known P4 channel.

Parent RouteAwareP4 owns every scan queue and discovery proof. A probe is an
interior point of an already-issued travel segment; its parent action resumes
before any route replanning. Hypothetical target samples only rank information
value. They never prove reception, localization, absence or successful clear.
"""
import math
from collections import Counter

from strategy import Action
from strategy_p4 import distance
from strategy_route import RouteAwareP4


class RouteProbeP4(RouteAwareP4):
    name = 'RouteProbeP4_zero_detour'

    def __init__(self, probe_enabled=True, max_probes_per_channel=2, **kwargs):
        super().__init__(**kwargs)
        if not 0 <= int(max_probes_per_channel) <= 2:
            raise ValueError('max_probes_per_channel must lie within 0..2')
        self.probe_enabled = bool(probe_enabled)
        self.max_probes_per_channel = int(max_probes_per_channel)
        self.probe_positions = {}
        self.probe_events = Counter()
        self.probe_history = []
        self.probe_added_cost = dict(measure_time_s=0.0, switch_time_s=0.0, move_time_s=0.0)
        self._probe_held_action = None
        self._probe_context = None
        self._probe_inflight = False
        self._probe_near_channel = None

    @staticmethod
    def _single_positive(track):
        positions = []
        for position, angle in track.records:
            if not any(distance(position, old[0]) <= 1e-6 for old in positions):
                positions.append((tuple(position), float(angle)))
        return positions[0] if len(positions) == 1 else None

    def _rank_probe(self, ch, track, start, destination, old_channel, scan_channel):
        observation = self._single_positive(track)
        if observation is None:
            return None
        origin, angle = observation
        theta = math.radians(angle)
        bearing = (math.cos(theta), math.sin(theta))
        targets = [(origin[0] + r * bearing[0], origin[1] + r * bearing[1])
                   for r in (500.0, 1000.0, 1400.0)]
        # The public arena only rejects implausible ranking hypotheses.
        targets = [p for p in targets if math.hypot(*p) <= 1800.0001]
        if len(targets) < 2:
            return None
        dx, dy = destination[0] - start[0], destination[1] - start[1]
        segment2 = dx * dx + dy * dy
        if segment2 < 40.0 ** 2:
            return None
        fractions = {0.15, 0.3, 0.5, 0.7, 0.85}
        for point in targets:
            fraction = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / segment2
            if 0.08 <= fraction <= 0.92:
                fractions.add(fraction)
        forbidden = [p for p, _ in track.records] + self.probe_positions.get(ch, [])
        added_switch = float(old_channel != ch) + float(ch != scan_channel) - float(old_channel != scan_channel)
        added_cost = 5.0 + added_switch
        best = None
        for fraction in sorted(fractions):
            point = (start[0] + fraction * dx, start[1] + fraction * dy)
            if any(distance(point, old) <= 1.0 for old in forbidden):
                continue
            estimates = []
            useful = 0
            for target in targets:
                old_range, new_range = distance(origin, target), distance(point, target)
                if not 5.0 < new_range <= 1500.0:
                    estimates.append(0.0)
                    continue
                cross = abs(bearing[0] * (target[1] - point[1]) - bearing[1] * (target[0] - point[0])) / new_range
                if cross < 0.2:
                    estimates.append(0.0)
                    continue
                # Small-angle width is an estimate for value ranking, not the
                # actual region or a clear-radius certificate.
                predicted_radius = math.tan(math.radians(1.0050001)) * (old_range + new_range) / cross
                information = max(0.0, min(1.0, (250.0 - predicted_radius) / 230.0))
                # Saving a future distinct-position visit is worth at most this
                # bounded travel estimate. Reception remains explicitly unknown.
                estimated_saved_s = min(80.0, distance(origin, point) / 5.0) * information * 0.5
                estimates.append(estimated_saved_s)
                useful += predicted_radius <= 120.0
            expected_gain = sum(estimates) / len(targets)
            if useful < 2 or expected_gain <= max(10.0, 2.0 * added_cost):
                continue
            candidate = dict(channel=ch, point=point, segment_fraction=fraction,
                             estimated_gain_s=expected_gain, added_measure_s=5.0,
                             added_switch_s=added_switch, estimated_net_gain_s=expected_gain - added_cost,
                             useful_hypotheses=useful, hypothesis_count=len(targets),
                             reception_guaranteed=False, geometry_certificate=False)
            if best is None or (candidate['estimated_net_gain_s'], -fraction) > (best['estimated_net_gain_s'], -best['segment_fraction']):
                best = candidate
        return best

    def _candidate(self, state, action):
        if (not self.probe_enabled or self.max_probes_per_channel == 0 or self.phase != 'discovery'
                or action.kind != 'measure' or distance(state.pos, action.pos) <= 40.0):
            return None
        candidates = []
        for ch, track in sorted(self.tracks.items()):
            # The held scan channel already has an imminent paid observation;
            # avoid adding another observation to that channel on this trip.
            if (ch in self.cleared or ch == action.ch or track.near is not None
                    or len(self.probe_positions.get(ch, [])) >= self.max_probes_per_channel):
                continue
            candidate = self._rank_probe(ch, track, tuple(state.pos), tuple(action.pos), state.ch, action.ch)
            if candidate is not None:
                candidates.append(candidate)
        return max(candidates, key=lambda row: (row['estimated_net_gain_s'], -row['channel'])) if candidates else None

    def step(self, state):
        self._state = state
        if self._probe_held_action is not None:
            if self._probe_inflight:
                raise RuntimeError('route_probe_measurement_result_missing')
            ch = self._probe_context['channel']
            track = self.tracks.get(ch)
            if (ch not in self.cleared and track is not None and track.near is not None
                    and distance(track.near, state.pos) < 1e-6):
                self._probe_near_channel = ch
                self.action_stage = 'route_probe_near_clear'
                self.probe_events['near_immediate_clear'] += 1
                return self._start_plan(ch, self._cover(ch, state.pos))
            action = self._probe_held_action
            context = self._probe_context
            detour = distance(context['start'], tuple(state.pos)) + distance(tuple(state.pos), action.pos) - context['segment_distance_m']
            if abs(detour) > 1e-6:
                raise RuntimeError('route_probe_resume_would_add_movement')
            self._probe_held_action = None
            self._probe_context = None
            self.action_stage = context['held_stage']
            self.probe_events['held_scan_resumed'] += 1
            return action
        action = super().step(state)
        candidate = self._candidate(state, action)
        if candidate is None:
            return action
        point, ch = candidate['point'], candidate['channel']
        direct = distance(state.pos, action.pos)
        detour = distance(state.pos, point) + distance(point, action.pos) - direct
        assert abs(detour) <= 1e-6, 'probe point must lie on the existing movement segment'
        self._probe_held_action = action
        self._probe_context = dict(candidate, start=tuple(state.pos), destination=tuple(action.pos),
                                   segment_distance_m=direct, added_distance_m=detour,
                                   held_stage=self.action_stage,
                                   prior_consider_scan_stop=self._consider_scan_stop)
        self.probe_history.append(self._probe_context.copy())
        self.probe_positions.setdefault(ch, []).append(point)
        self._probe_inflight = True
        self.probe_events['zero_detour_probe_issued'] += 1
        self.action_stage = 'route_probe'
        return Action('measure', point, ch)

    def on_measure(self, state, ch, result, svd):
        inserted = (self._probe_inflight and self._probe_context is not None
                    and ch == self._probe_context['channel']
                    and distance(state.pos, self._probe_context['point']) < 1e-6)
        super().on_measure(state, ch, result, svd)
        if inserted:
            self._probe_inflight = False
            self.probe_events['probe_' + result] += 1
            self.probe_added_cost['measure_time_s'] += 5.0
            self.probe_added_cost['switch_time_s'] += self._probe_context['added_switch_s']
            self.probe_history[-1]['result'] = result

    def on_clear(self, state, ch, success):
        inserted_near = self._probe_near_channel == ch
        super().on_clear(state, ch, success)
        if inserted_near and success:
            # Resume the already-issued station before the parent can reinterpret
            # this intermediate clear point as a new survey stop.
            self._consider_scan_stop = self._probe_context['prior_consider_scan_stop']
            self._probe_near_channel = None
            self.probe_events['probe_near_clear_success'] += 1

    def diagnostics(self):
        result = super().diagnostics()
        result['route_probe'] = dict(enabled=self.probe_enabled,
                                     max_probes_per_channel=self.max_probes_per_channel,
                                     triggers=dict(self.probe_events), history=self.probe_history,
                                     added_cost=self.probe_added_cost,
                                     added_cost_scope='detection and total round-trip channel-switch increment versus the held scan action; optical success is counted by the driver',
                                     target_samples_are_only_ranking=True)
        result['triggers'].update({'route_probe_' + key: value for key, value in self.probe_events.items()})
        return result
