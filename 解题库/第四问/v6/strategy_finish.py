"""P4 finish-cost transfer: stop extra survey only with a finite optical certificate.

Inherits FastP4 directly. No CostAware policy chain and no P3 imports.
The complete 49-station discovery proof and all simulator physics stay unchanged.
"""
import math
from collections import Counter
from shapely.geometry import Polygon,Point
from strategy import Action
from strategy_fast import FastP4, CORE_STATIONS, nearest_path
from strategy_p4 import CHANNELS, DISCOVERY_STATIONS, distance
from strategy_cost import optical_cover


def optimized_core():
    points=[p for p in CORE_STATIONS if not (abs(p[0])==2100 and abs(p[1])==2100)]
    route=nearest_path(points)
    # Fixed-start OPEN route: deterministic bounded 2-opt; no case observations.
    for _ in range(80):
        best=None
        for i in range(1,len(route)-1):
            for j in range(i+1,len(route)):
                before=distance(route[i-1],route[i])
                after=distance(route[i-1],route[j])
                if j+1<len(route):
                    before+=distance(route[j],route[j+1]);after+=distance(route[i],route[j+1])
                gain=before-after
                if gain>1e-7 and (best is None or gain>best[0]):best=(gain,i,j)
        if best is None:break
        _,i,j=best;route[i:j+1]=reversed(route[i:j+1])
    return tuple(route)

TRIMMED_CORE=optimized_core()


class FinishP4(FastP4):
    name='FinishP4_certified_tail'

    def __init__(self, enabled=True, trim_corners=False):
        super().__init__()
        self.enabled=enabled
        self.trim_corners=trim_corners
        self.name='FinishP4_'+('tail' if enabled else '')+('_grid45' if trim_corners else '')
        if trim_corners:
            extras=set(DISCOVERY_STATIONS)-set(CORE_STATIONS)
            self.discovery_stations=list(TRIMMED_CORE)+nearest_path(extras,TRIMMED_CORE[-1])
        self.certificates={}
        self.plans={}
        self.events=Counter()
        self._certificate_checks={}
        self.failed_clears={}
        self.action_stage='discovery'

    def _next_discovery_action(self):
        if not self.trim_corners:return super()._next_discovery_action()
        while self.discovery_station_index<len(self.discovery_stations):
            if self._station_channels and self.discovery_channel_index>=len(self._station_channels):
                self.discovery_station_index+=1;self.discovery_channel_index=0;self._station_channels=[]
                continue
            if self.discovery_station_index>=len(TRIMMED_CORE) and not self.core_complete:
                # Every 700m cell intersecting the 1800m disk retains all corners.
                # The four discarded corners touch only cells >=sqrt(2)*1400 away.
                self.core_complete=True;self.absent=set(CHANNELS)-set(self.tracks)
            if not self._station_channels:
                self._station_channels=[ch for ch in CHANNELS if self._needs_sample(ch)]
                self.discovery_channel_index=0
            if not self._station_channels:
                self.discovery_station_index+=1;continue
            ch=self._station_channels[self.discovery_channel_index];self.discovery_channel_index+=1
            if not self._needs_sample(ch):continue
            return Action('measure',self.discovery_stations[self.discovery_station_index],ch)
        self._finish_discovery()
        return None

    def _certificate(self,ch):
        track=self.tracks[ch]
        key=(len(track.records),tuple(track.poly))
        if self._certificate_checks.get(ch)==key:
            return self.certificates.get(ch)
        self._certificate_checks[ch]=key
        self.certificates.pop(ch,None)
        if len(track.records)<2 or len(track.poly)<3:return None
        region=Polygon(track.poly)
        # Never repair invalid polygons into smaller regions; keep original policy.
        if not region.is_valid or region.is_empty:
            self.events['invalid_polygon_fallback']+=1
            return None
        # Starting at the existing target estimate isolates the terminal extra cost;
        # actual routing is replanned from the real position when this channel runs.
        plan=optical_cover(region,track.center,limit=6)
        if plan is None:return None
        # Bounded terminal surcharge (including up to 5 misses) must be cheaper
        # than one 700m grid move + measurement. This is a selection heuristic,
        # not a guarantee of globally improved route cost; paired gate is required.
        if plan['total_s']>700./5+5:
            self.events['finish_cost_rejected']+=1
            return None
        proof=dict(polygon=list(track.poly),points=plan['points'],
                   worst_finish_from_center_s=plan['total_s'],records=len(track.records))
        self.certificates[ch]=proof
        return proof

    def _needs_sample(self,ch):
        needed=super()._needs_sample(ch)
        if not self.enabled or not needed or not self.core_complete:return needed
        # If any channel still needs the outer tour, keep cheap opportunistic
        # readings of every eligible channel along that same tour.
        remaining=[c for c in self.tracks if FastP4._needs_sample(self,c)]
        proofs={c:self._certificate(c) for c in remaining}
        if any(proof is None for proof in proofs.values()):return needed
        for c in remaining:
            if c not in self.plans:
                self.events['extra_scan_channel_retired']+=1
                self.plans[c]=None
        return False

    def step(self,state):
        action=super().step(state)
        self.action_stage='optical_finish' if action.ch in self.plans and action.kind=='clear' else self.phase
        return action

    def _next_local_action(self,ch,state):
        if self.enabled and self._ordered and self.plans.get(ch):
            return Action('clear',self.plans[ch][0],ch)
        # FastP4 can reorder channels in this hook, so first let it select action.ch.
        action=super()._next_local_action(ch,state)
        ch=action.ch
        if not self.enabled or ch not in self.plans:return action
        if self.plans[ch] is None:
            region=Polygon(self.certificates[ch]['polygon'])
            plan=optical_cover(region,state.pos,limit=6)
            if plan is None:raise RuntimeError('certificate_plan_unavailable')
            self.plans[ch]=plan['points'][:]
            self.events['optical_plan_started']+=1
        if not self.plans[ch]:raise RuntimeError('optical_cover_exhausted: inconsistent observations')
        return Action('clear',self.plans[ch][0],ch)

    def on_clear(self,state,ch,success):
        if ch not in self.plans:return super().on_clear(state,ch,success)
        track=self.tracks[ch]
        if success:
            super().on_clear(state,ch,True)
            del self.plans[ch]
            self.events['optical_success']+=1
            return
        # Immutable full-region cover stays valid for its shrinking subset.
        # Store negative evidence; no relocalization occurs mid-plan.
        self.failed_clears.setdefault(ch,[]).append(tuple(state.pos))
        self.plans[ch].pop(0)
        track.clear_failures+=1;track.recovery_required=False
        self.events['optical_miss_advance']+=1
        if not self.plans[ch]:raise RuntimeError('optical_cover_exhausted: inconsistent observations')

    def diagnostics(self):
        return dict(enabled=self.enabled,trim_corners=self.trim_corners,triggers=dict(self.events),certificates=self.certificates,
                    failed_clear_positions=self.failed_clears)
