"""Bounded P4 local-bearing planner; imports only the bundled P4 modules.

The caller owns measurement results, Tracks, clear plans and the global survey
cursor. This component only proposes at most eight measurements per channel.
One-bearing moves are explicitly speculative, never coverage certificates.
With two positive positions, every proposed point is a convex combination of
positive positions, hence remains in the convex reception disk/half-plane.
No ``no_signal`` result is accepted here and no spatial exclusions are inferred.
"""
import math
from collections import Counter

from strategy import Action, p1
from strategy_p4 import ARENA_R, EPS_DEG, R_EFF, distance


def _unique(points, tolerance=0.5):
    result = []
    for point in points:
        point = tuple(point)
        if not any(distance(point, old) <= tolerance for old in result):
            result.append(point)
    return result


def _ray_interval(origin, direction):
    """Central-bearing interval in the public arena/range; ranking only."""
    dot = origin[0] * direction[0] + origin[1] * direction[1]
    delta = dot * dot + ARENA_R * ARENA_R - sum(v * v for v in origin)
    if delta < 0:
        return 0.0, R_EFF
    root = math.sqrt(delta)
    lo, hi = max(0.0, -dot - root), min(R_EFF, -dot + root)
    return (lo, hi) if hi > lo else (0.0, R_EFF)


def _centroid(poly):
    # Vertex average stays in a convex polygon. It is only a cost hypothesis.
    return tuple(sum(p[k] for p in poly) / len(poly) for k in (0, 1))


def _finish_estimate(poly, position):
    """Ranking estimate includes travel and success/miss clear costs.

    This is deliberately NOT an optical coverage guarantee. The caller must
    still obtain a full continuous coverage certificate before using a plan.
    """
    center = _centroid(poly)
    radius = max(distance(center, q) for q in poly)
    diameter, _, _ = p1.polygon_diameter(poly)
    count = max(1, math.ceil(diameter / 32.0))
    move = max(0.0, distance(position, center) - max(0.0, 20.0 - radius)) / 5.0
    # A lower-dimensional strip estimate is enough for ranking candidate
    # measurements; cost/correctness claims never use this hypothetical count.
    return move + 5.0 + 3.0 * (count - 1) + max(0, count - 1) * 24.0 / 5.0


class LocalHuntPlanner:
    """Simple interface: ``next_probe(track, state, channel) -> Action | None``.

    The issued action itself consumes budget. No callback is required: the next
    call reads the caller's current positive records. Calling again after a
    no-signal reply therefore advances to a distinct point without modifying
    the feasible region. ``None`` means hand the channel back to the existing
    global survey/localization fallback, never clear/skip/mark it done.
    """

    def __init__(self, max_probes=8):
        if not 1 <= int(max_probes) <= 8:
            raise ValueError('max_probes must be within 1..8')
        self.max_probes = int(max_probes)
        self.history = {}
        self.events = Counter()
        self.last_reason = {}
        self.cost_comparisons = []

    def _first_candidates(self, track):
        origin, bearing = track.records[0]
        angle = math.radians(bearing)
        u = (math.cos(angle), math.sin(angle))
        v = (-u[1], u[0])
        lo, hi = _ray_interval(origin, u)
        hop = lo + 0.4 * (hi - lo)
        hop = max(100.0, min(1100.0, hop))
        lateral = min(180.0, max(60.0, hop * 0.3))
        # Opposite lateral side first after a miss; then retreat along the
        # original ray. None of these no-signal attempts shortens that ray.
        offsets = ((hop, lateral), (hop, -lateral),
                   (hop * 0.5, -lateral * 0.75),
                   (hop * 0.5, lateral * 0.75),
                   (hop / 6.0, lateral * 0.5),
                   (hop / 6.0, -lateral * 0.5))
        return [(origin[0] + forward * u[0] + side * v[0],
                 origin[1] + forward * u[1] + side * v[1])
                for forward, side in offsets]

    def _safe_candidates(self, track, used):
        positions = _unique(pos for pos, _ in track.records)
        pairs = sorted(((distance(a, b), a, b)
                        for i, a in enumerate(positions)
                        for b in positions[i + 1:]), reverse=True)
        candidates = []
        for _, a, b in pairs[:12]:
            for fraction in (0.2, 0.4, 0.6, 0.8):
                candidates.append(tuple(a[k] * (1.0 - fraction) + b[k] * fraction
                                        for k in (0, 1)))
        if len(positions) >= 3:
            for group in (positions[:3], positions[-3:], positions[::2][:3]):
                if len(group) == 3:
                    candidates.append(_centroid(group))
        return [p for p in _unique(candidates)
                if all(distance(p, old) > 0.5 for old in positions + used)]

    def _score(self, point, track, state, channel):
        immediate = distance(state.pos, point) / 5.0 + 5.0 + float(state.ch != channel)
        poly = track.poly
        if len(poly) < 3:
            # No available polygon: ranking by measured travel remains valid.
            return immediate + distance(point, track.records[-1][0]) / 5.0 + 5.0
        center = _centroid(poly)
        # Spatial sample hypotheses select a cheap action only. All safety and
        # any later optical coverage use the unchanged complete input polygon.
        _, a, b = p1.polygon_diameter(poly)
        hypotheses = (center, tuple(0.75 * center[k] + 0.25 * a[k] for k in (0, 1)),
                      tuple(0.75 * center[k] + 0.25 * b[k] for k in (0, 1)))
        finishes = []
        for target in hypotheses:
            if distance(point, target) < 1e-6:
                finishes.append(5.0)
                continue
            theta = math.degrees(math.atan2(target[1] - point[1], target[0] - point[0]))
            hypothetical = p1.hpi_intersect(poly[:], p1.make_sector_halfplanes(point, theta, EPS_DEG))
            finishes.append(_finish_estimate(hypothetical or poly, point))
        return immediate + sum(finishes) / len(finishes)

    def next_probe(self, track, state, channel):
        used = self.history.setdefault(channel, [])
        if not track.records or track.near is not None:
            self.last_reason[channel] = 'no_bearing_or_near'
            return None
        if len(used) >= self.max_probes:
            self.last_reason[channel] = 'probe_budget_exhausted'
            self.events['budget_fallback'] += 1
            return None
        positions = _unique(pos for pos, _ in track.records)
        excluded = used + list(getattr(track, 'probe_history', [])) + positions
        if len(positions) == 1:
            candidates = [p for p in self._first_candidates(track)
                          if all(distance(p, old) > 0.5 for old in excluded)]
            # Keep bounded planned side/retreat order after a miss. Initial
            # reflection is selected by travel from the actual current point.
            if not used and len(candidates) >= 2:
                candidates[:2] = sorted(candidates[:2], key=lambda p: (distance(state.pos, p), p))
            kind = 'speculative_first_pair'
        else:
            candidates = self._safe_candidates(track, excluded)
            candidates.sort(key=lambda p: (self._score(p, track, state, channel), p))
            kind = 'safe_convex_probe'
        if not candidates:
            self.last_reason[channel] = 'distinct_candidates_exhausted'
            self.events['candidate_fallback'] += 1
            return None
        point = candidates[0]
        used.append(point)
        self.last_reason[channel] = kind
        self.events[kind] += 1
        self.cost_comparisons.append(dict(channel=channel, kind=kind, point=point,
                                         estimated_total_s=self._score(point, track, state, channel),
                                         issued_index=len(used)))
        return Action('measure', point, channel)

    def diagnostics(self):
        return dict(max_probes=self.max_probes, triggers=dict(self.events),
                    history={ch: list(points) for ch, points in self.history.items()},
                    last_reason=dict(self.last_reason),
                    cost_comparisons=list(self.cost_comparisons))
