"""演练候选：先完成有证明的49站发现网格，仅为已知难定位源补扫。"""
import math
from strategy import Action
from strategy_p4 import AdaptiveP4, CHANNELS, DISCOVERY_STATIONS, _localize, distance

def nearest_path(points,start=(0.0,0.0)):
    remaining=set(points);out=[]
    while remaining:
        nxt=min(remaining,key=lambda p:(distance(start,p),p[1],p[0]))
        out.append(nxt);remaining.remove(nxt);start=nxt
    return out

CORE_STATIONS=tuple(nearest_path([(float(x),float(y)) for x in range(-2100,2101,700)
                                for y in range(-2100,2101,700)]))

class FastP4(AdaptiveP4):
    name='FastP4_grid49'
    def __init__(self):
        extras=set(DISCOVERY_STATIONS)-set(CORE_STATIONS)
        super().__init__(list(CORE_STATIONS)+nearest_path(extras,CORE_STATIONS[-1]))
        self.core_complete=False
        self._geometry_counts={}
        self._ordered=False

    def _update_geometry(self,ch):
        track=self.tracks[ch]
        if len(track.records)<2 or self._geometry_counts.get(ch)==len(track.records):return
        self._geometry_counts[ch]=len(track.records)
        geom=_localize(track.records)
        if geom is not None:
            track.poly=geom['poly'];track.center=geom['mec_center']
            track.radius=geom['mec_radius'];track.estimate=geom['mec_center']

    def _needs_sample(self,ch):
        if ch in self.cleared or ch in self.absent:return False
        track=self.tracks.get(ch)
        if track is None:return not self.core_complete
        return (track.near is None and track.radius>19.99999
                and len(track.records)<self.min_positive_records)

    def _next_discovery_action(self):
        if self._station_channels and self.discovery_channel_index>=len(self._station_channels):
            self.discovery_station_index+=1;self.discovery_channel_index=0;self._station_channels=[]
        while self.discovery_station_index<len(self.discovery_stations):
            if self.discovery_station_index>=len(CORE_STATIONS) and not self.core_complete:
                # Every target lies in a 700m square whose four corners are <=700sqrt(2)<1000m.
                # Any closed half-plane through the target contains at least one corner.
                # Thus only AFTER these 49 stations can an unseen channel be declared absent.
                self.core_complete=True;self.absent=set(CHANNELS)-set(self.tracks)
            if not self._station_channels:
                self._station_channels=[ch for ch in CHANNELS if self._needs_sample(ch)]
                self.discovery_channel_index=0
            if not self._station_channels:
                self.discovery_station_index+=1;continue
            ch=self._station_channels[self.discovery_channel_index]
            self.discovery_channel_index+=1
            if not self._needs_sample(ch):continue
            return Action('measure',self.discovery_stations[self.discovery_station_index],ch)
        self._finish_discovery()
        return None

    def on_measure(self,state,channel,result,svd):
        # Repeated readings at one point must not be treated as independent spatial information.
        track=self.tracks.get(channel)
        if result=='direction' and track and any(distance(state.pos,p)<1e-6 for p,_ in track.records):
            track.recovery_required=False;return
        super().on_measure(state,channel,result,svd)
        if result=='direction':self._update_geometry(channel)

    def _target(self,ch):
        track=self.tracks[ch]
        if track.near is not None:return track.near
        if math.isfinite(track.radius):return track.center
        return track.records[-1][0]

    def step(self,state):
        if self.phase=='localization' and self.work_index<len(self.work_channels):
            # Reorder only between completed channels, never interrupt a localization recovery.
            if not self._ordered:
                remaining=[ch for ch in self.work_channels if ch not in self.cleared]
                order=[];pos=state.pos
                while remaining:
                    ch=min(remaining,key=lambda c:(distance(pos,self._target(c)),c))
                    order.append(ch);remaining.remove(ch);pos=self._target(ch)
                self.work_channels=order;self.work_index=0;self._ordered=True
        return super().step(state)

    def on_clear(self,state,channel,success):
        super().on_clear(state,channel,success)
        if success:self._ordered=False

    def _next_local_action(self,channel,state):
        action=super()._next_local_action(channel,state)
        track=self.tracks[channel]
        if action.kind=='clear' and track.near is None and track.radius<19.99999:
            d=distance(state.pos,track.center)
            shift=min(d,19.99999-track.radius)
            if d>1e-9:
                point=tuple(track.center[i]+(state.pos[i]-track.center[i])*shift/d for i in (0,1))
                return Action('clear',point,channel)
        return action
