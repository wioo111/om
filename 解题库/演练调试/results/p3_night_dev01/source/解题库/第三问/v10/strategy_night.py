"""P3 nightly candidates; observations only, no simulator internals or known source count."""
from functools import lru_cache
import math
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from strategy_fast import FastScanP3
from strategy_v8 import ARENA_R, RECEIVE_MIN

POLYGON_SIDES=128
MARGIN_M=0.01
UNIT=tuple((math.cos(2*math.pi*i/POLYGON_SIDES),math.sin(2*math.pi*i/POLYGON_SIDES))
           for i in range(POLYGON_SIDES))
# The target circle is inside this polygon; exclusion polygons are inside 1000m disks.
OUTER_TARGET=Polygon([(x*(ARENA_R+MARGIN_M)/math.cos(math.pi/POLYGON_SIDES),
                       y*(ARENA_R+MARGIN_M)/math.cos(math.pi/POLYGON_SIDES)) for x,y in UNIT])

def polygon_coverage_certificate(negative_positions):
    if not negative_positions:return False
    radius=RECEIVE_MIN-MARGIN_M
    disks=[Polygon([(cx+radius*x,cy+radius*y) for x,y in UNIT]) for cx,cy in negative_positions]
    return bool(unary_union(disks).covers(OUTER_TARGET))

class CachedScanP3(FastScanP3):
    name='CachedScanP3'
    def __init__(self):
        super().__init__()
        original=self.coverage.covered_at
        self._cached_mask=lru_cache(maxsize=2048)(original)
        self.coverage.covered_at=lambda pos:self._cached_mask((float(pos[0]),float(pos[1])))

class CoverP3(CachedScanP3):
    name='CoverP3'
    def __init__(self):
        super().__init__()
        self.coverage_certificates={}

    def on_measure(self,state,ch,result,svd):
        super().on_measure(state,ch,result,svd)
        if result!='no_signal' or ch in self.tracks or ch in self.absent:return
        # Ordinary whole-cell coverage remains the primary test. Only certify the small tail.
        if np.count_nonzero(self.coverage.remaining[ch])>len(self.coverage.points)*0.12:return
        positions=self.negative_positions[ch]
        if polygon_coverage_certificate(positions):
            self.absent.add(ch)
            self.coverage.remaining[ch][:]=False
            self.coverage_certificates[ch]=list(positions)

    def diagnostics(self):
        info=self._cached_mask.cache_info()
        return dict(mask_cache_hits=info.hits,mask_cache_misses=info.misses,
            coverage_certificate_method='outer-target128 covered by union of inner-exclusion128, 0.01m margins',
            coverage_certificates=self.coverage_certificates)

class HopP3(CoverP3):
    name='HopP3'
    def __init__(self):
        super().__init__()
        self.first_hop=500.0
        self.lateral=100.0
