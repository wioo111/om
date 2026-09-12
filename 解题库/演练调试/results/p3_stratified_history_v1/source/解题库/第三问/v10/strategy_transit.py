"""P3 practice: ResidualP3 is selected; transit/tail variants remain offline experiments."""
from functools import lru_cache
import numpy as np
from shapely import box, intersects
from shapely.geometry import Polygon
from shapely.ops import unary_union

from strategy import Action
from strategy_night import HopP3, OUTER_TARGET, UNIT, MARGIN_M
from strategy_v8 import RECEIVE_MIN, distance


class ResidualP3(HopP3):
    name = 'ResidualP3'
    residual_fraction = 0.35

    def __init__(self):
        super().__init__()
        # Coverage was constructed with exactly 60m cells by FastScanP3.
        points = self.coverage.points
        self._cells = box(points[:, 0] - 30., points[:, 1] - 30.,
                          points[:, 0] + 30., points[:, 1] + 30.)
        self._residual_mask = lru_cache(maxsize=128)(self._compute_residual_mask)
        self.residual_updates = 0
        self.residual_channels = set()
        self.residual_certificates = {}

    def _compute_residual_mask(self, positions):
        radius = RECEIVE_MIN - MARGIN_M
        exclusions = [Polygon([(cx + radius*x, cy + radius*y) for x, y in UNIT])
                      for cx, cy in positions]
        residual = OUTER_TARGET.difference(unary_union(exclusions))
        # Closed cell intersection also retains touching cells and a small outward guard.
        return np.asarray(intersects(residual.buffer(0.0001), self._cells), dtype=bool)

    def on_measure(self, state, ch, result, svd):
        super().on_measure(state, ch, result, svd)
        if result == 'no_signal' and ch in self.absent and ch in self.residual_channels:
            self.residual_certificates[ch] = list(self.negative_positions[ch])
        if result != 'no_signal' or ch in self.tracks or ch in self.absent:
            return
        remaining = self.coverage.remaining[ch]
        if np.count_nonzero(remaining) > len(remaining) * self.residual_fraction:
            return
        positions = tuple(tuple(p) for p in self.negative_positions[ch])
        residual_mask = self._residual_mask(positions)
        before = np.count_nonzero(remaining)
        remaining &= residual_mask
        changed = np.count_nonzero(remaining) < before
        self.residual_updates += int(changed)
        if changed:
            self.residual_channels.add(ch)
        if not np.any(remaining):
            self.absent.add(ch)
            self.coverage_certificates[ch] = list(positions)
            self.residual_certificates[ch] = list(positions)

    def diagnostics(self):
        result = super().diagnostics()
        result.update(residual_updates=self.residual_updates,
                      residual_method='whole 60m cells disjoint from outward-guarded polygon difference',
                      residual_cache_hits=self._residual_mask.cache_info().hits,
                      residual_certificates=self.residual_certificates)
        return result


class TransitP3(HopP3):
    name = 'TransitP3'
    transit_fraction = 0.12
    minimum_leg = 700.

    def __init__(self):
        super().__init__()
        self._transit_pending = None
        self._transit_channels = []
        self.transit_stops = []

    def step(self, state):
        if self._transit_pending is not None:
            while self._transit_channels:
                ch = self._transit_channels.pop(0)
                if ch not in self.cleared and ch not in self.absent and ch not in self.tracks:
                    return Action('measure', state.pos, ch)
            action = self._transit_pending
            self._transit_pending = None
            return action
        action = super().step(state)
        unknown = self._unknown()
        if (action.kind not in ('measure', 'clear') or not unknown
                or distance(state.pos, action.pos) < self.minimum_leg):
            return action
        endpoint = self.coverage.covered_at(action.pos)
        start = np.asarray(state.pos)
        finish = np.asarray(action.pos)
        best = None
        for fraction in (0.25, 0.5, 0.75):
            pos = tuple(float(v) for v in start + fraction * (finish-start))
            mask = self.coverage.covered_at(pos) & ~endpoint
            channels, gain = [], 0
            for ch in unknown:
                extra = self.coverage.gain(ch, mask)
                threshold = max(1, int(min(len(mask)*self.transit_fraction,
                                          np.count_nonzero(self.coverage.remaining[ch])*0.8)))
                if extra >= threshold:
                    channels.append(ch)
                    gain += extra
            if not channels:
                continue
            score = gain/(6*len(channels)+1)
            if best is None or score > best[0]:
                best = score, pos, channels
        if best is None:
            return action
        _, pos, channels = best
        self._transit_pending = action
        self._transit_channels = sorted(channels, key=lambda ch: (ch != state.ch, ch))
        self.transit_stops.append(dict(start=state.pos, finish=action.pos, pos=pos,
                                       channels=list(self._transit_channels)))
        return Action('measure', pos, self._transit_channels.pop(0))

    def diagnostics(self):
        result = super().diagnostics()
        result['transit_stops'] = self.transit_stops
        return result


class TransitResidualP3(TransitP3, ResidualP3):
    name = 'TransitResidualP3'


class TransitSparseP3(TransitP3):
    name = 'TransitSparseP3'
    transit_fraction = 0.20
    minimum_leg = 900.


class TailResidualP3(ResidualP3):
    name = 'TailResidualP3'
    residual_fraction = 0.12


class TransitEagerP3(TransitP3):
    name = 'TransitEagerP3'
    transit_fraction = 0.025
    minimum_leg = 500.


class TailTransitP3(TransitEagerP3, TailResidualP3):
    name = 'TailTransitP3'
