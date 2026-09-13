"""One bounded P4 candidate; all switches off delegates exactly to frozen FastP4.

Geometry uses only positive bearings, the 1500m upper radius, arena, and
failed optical clears. No direction-dependent no_signal spatial exclusion.
"""
import itertools
import math
from collections import Counter
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from strategy import Action
from strategy_fast import FastP4
from strategy_p4 import CHANNELS, distance

OPTICAL_R = 19.99999


def optical_cover(region, start, limit=6):
    """Cover a continuous superset by <=6 inscribed optical disks.

    Tile an oriented bounding rectangle into rectangles of diagonal <40m.
    Exact polygon difference against inscribed disks certifies full coverage;
    no target samples, area tolerance, or missing slivers are accepted.
    """
    if region is None or region.is_empty or not region.is_valid:
        return None
    rect = list(region.minimum_rotated_rectangle.exterior.coords)
    axes = [(1., 0.)]
    if len(rect) >= 2:
        dx, dy = rect[1][0]-rect[0][0], rect[1][1]-rect[0][1]
        d = math.hypot(dx, dy)
        if d > 1e-9:
            axes.append((dx/d, dy/d))
    coords = list(region.convex_hull.exterior.coords)
    best = None
    for ux, uy in axes:
        vx, vy = -uy, ux
        xs = [x*ux+y*uy for x,y in coords]
        ys = [x*vx+y*vy for x,y in coords]
        x0,x1,y0,y1 = min(xs),max(xs),min(ys),max(ys)
        for nx in range(1,limit+1):
            for ny in range(1,limit//nx+1):
                if math.hypot((x1-x0)/nx,(y1-y0)/ny)/2 > 19.99:
                    continue
                centers = []
                for i in range(nx):
                    for j in range(ny):
                        a=x0+(i+.5)*(x1-x0)/nx; b=y0+(j+.5)*(y1-y0)/ny
                        centers.append((a*ux+b*vx,a*uy+b*vy))
                disks = unary_union([Point(p).buffer(OPTICAL_R,quad_segs=32) for p in centers])
                if not region.difference(disks).is_empty:
                    continue
                # k-1 failures, final success; clear never switches measurement channel.
                path = min(itertools.permutations(centers),key=lambda ps: sum(
                    distance(a,b) for a,b in zip((start,)+ps,ps)))
                movement = sum(distance(a,b)/5 for a,b in zip((start,)+path,path))
                cost = movement+3*(len(path)-1)+5
                if best is None or cost < best['total_s']:
                    best=dict(points=list(path),total_s=cost,move_s=movement,
                              measure_s=0.,switch_s=0.,clear_success_s=5.,
                              clear_failure_s=3.*(len(path)-1))
    return best


class CostAwareP4(FastP4):
    def __init__(self, enable_a=True, enable_b=True, enable_c=False):
        super().__init__()
        self.enable_a,self.enable_b,self.enable_c=enable_a,enable_b,enable_c
        self.name='CostAwareP4_'+(''.join(k for k,v in zip('ABC',(enable_a,enable_b,enable_c)) if v) or 'off')
        self.ever_observed_channels=set()
        self.failed_clear_positions={}
        self.optical_plans={}
        self.events=Counter()
        self.cost_comparisons=[]
        self._last_action=None
        self._same_action_count=0
        self._local_counts=Counter()
        self.action_stage='discovery'

    def diagnostics(self):
        return dict(switches=dict(A=self.enable_a,B=self.enable_b,C=self.enable_c),
                    triggers=dict(self.events),ever_observed_channels=sorted(self.ever_observed_channels),
                    failed_clear_positions=self.failed_clear_positions,cost_comparisons=self.cost_comparisons)

    def _needs_sample(self,ch):
        if self.enable_a and len(self.ever_observed_channels)==16 and ch not in self.ever_observed_channels:
            return False
        return super()._needs_sample(ch)

    def on_measure(self,state,channel,result,svd):
        if result in ('direction','near'):
            self.ever_observed_channels.add(channel)
            if self.enable_a and len(self.ever_observed_channels)==16 and not self.events['A_cardinality_proof']:
                self.events['A_cardinality_proof']=1
                self.absent.update(set(CHANNELS)-self.ever_observed_channels)
        super().on_measure(state,channel,result,svd)

    def region(self,ch):
        """Outer polygon: tangent disk halfplanes + bearing error incl rounding.

        P4 _localize uses eps=1.0050001 and circumscribed (not inscribed)
        1500m/1800m disks. Removing INSCRIBED failed-clear disks remains outer.
        This is recomputed with all stored exclusions after every localization.
        """
        t=self.tracks[ch]
        if len(t.poly)<3:
            return None
        g=Polygon(t.poly)
        if not g.is_valid:
            # Unusable numerical polygon is not an optical coverage certificate.
            # Fall back to the original action instead of repairing/shrinking it.
            self.events['invalid_geometry_fallback']+=1
            return None
        for p in self.failed_clear_positions.get(ch,[]):
            g=g.difference(Point(p).buffer(OPTICAL_R,quad_segs=32))
        if g.is_empty:
            raise RuntimeError('geometry_contradiction: empty feasible region after failed clears')
        return g

    def _instant(self,state):
        for ch,t in sorted(self.tracks.items()):
            if ch in self.cleared:
                continue
            near=t.near is not None and distance(state.pos,t.near)<1e-7
            g=None if near else self.region(ch)
            covered=g is not None and g.difference(Point(state.pos).buffer(OPTICAL_R,quad_segs=32)).is_empty
            if near or covered:
                self.events['B_near' if near else 'B_region']=self.events['B_near' if near else 'B_region']+1
                return Action('clear',state.pos,ch)
        return None

    def step(self,state):
        if not any((self.enable_a,self.enable_b,self.enable_c)):
            return super().step(state)
        action=None
        if self.enable_b and self.phase=='discovery':
            action=self._instant(state)
        if action is not None:
            self.action_stage='instant_clear'
        else:
            action=super().step(state)
            self.action_stage='optical' if action.ch in self.optical_plans else self.phase
        if action.kind!='done':
            signature=(action.kind,tuple(action.pos),action.ch)
            self._same_action_count=self._same_action_count+1 if signature==self._last_action else 1
            self._last_action=signature
            if self._same_action_count>2:
                self.events['no_progress_stop']+=1
                raise RuntimeError('no_progress: repeated identical action')
        return action

    def _next_local_action(self,channel,state):
        # FastP4 may reorder the active channel; respect its selected action.ch.
        if self.enable_c and self._ordered and channel in self.optical_plans:
            plan=self.optical_plans[channel]
            if not plan:
                self.events['geometry_contradiction']+=1
                raise RuntimeError('geometry_contradiction: optical cover exhausted without success')
            return Action('clear',plan[0],channel)
        action=super()._next_local_action(channel,state)
        channel=action.ch
        if not self.enable_c:
            return action
        self._local_counts[channel]+=1
        if self._local_counts[channel]>256:
            raise RuntimeError('no_progress: bounded localization budget exhausted')
        g=self.region(channel)
        if action.kind!='measure' or g is None:
            return action
        plan=optical_cover(g,state.pos)
        if plan is None:
            self.events['C_no_cover']+=1
            return action
        candidates=self._safe_probe_candidates(self.tracks[channel],state)+[action.pos]
        # Optimistic LOWER bound for safe-probe-and-clear: travel, detection,
        # channel switch, minimum subsequent travel, one successful clear.
        # Further measurements/failures cost >=0. Optical uses worst-case misses.
        # Only replace if even that lower bound is more expensive.
        def lower(p):
            return distance(state.pos,p)/5+5+float(state.ch!=channel)+max(0.,Point(p).distance(g)-20.)/5+5
        safe=min(lower(p) for p in candidates)
        self.cost_comparisons.append(dict(channel=channel,optical=plan,safe_lower_bound_s=safe,
                                          selected=plan['total_s']+1e-6<safe))
        if plan['total_s']+1e-6>=safe:
            self.events['C_no_advantage']+=1
            return action
        self.optical_plans[channel]=plan['points'][:]
        self.events['C_plan_started']+=1
        return Action('clear',self.optical_plans[channel][0],channel)

    def on_clear(self,state,channel,success):
        if not any((self.enable_a,self.enable_b,self.enable_c)):
            return super().on_clear(state,channel,success)
        before=self.work_index
        if not success:
            self.failed_clear_positions.setdefault(channel,[]).append(tuple(state.pos))
            self.events['failed_clear_exclusion']+=1
        super().on_clear(state,channel,success)
        # Parent advances local index even during discovery; undo only that increment.
        if self.phase=='discovery':
            self.work_index=before
        if channel in self.optical_plans:
            if success:
                del self.optical_plans[channel]
                self.events['C_plan_success']+=1
            else:
                self.optical_plans[channel].pop(0)
                self.tracks[channel].recovery_required=False
                self.events['C_plan_failure_advance']+=1
                if not self.optical_plans[channel]:
                    self.events['geometry_contradiction']+=1
                    raise RuntimeError('geometry_contradiction: optical cover exhausted without success')
        elif not success and self.action_stage=='instant_clear':
            raise RuntimeError('geometry_contradiction: certified instantaneous clear failed')
