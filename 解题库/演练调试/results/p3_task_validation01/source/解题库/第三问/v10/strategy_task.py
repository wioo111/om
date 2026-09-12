"""P3 task-cost candidates: certify all sources, then minimize actual action time.

Uses only observations. Optical strips cover a continuous feasible polygon with
20m disks, not sampled targets. Belief quadrature ranks plans; it never certifies them.
"""
import math

from strategy import Action, State
from strategy_joint import ProbePlanP3
from strategy_v8 import (CLEAR_R, EPS_DEG, centroid, distance, enclosing_circle,
                         exclude_disk, p1)


def optical_strip(poly, current, samples, maximum_shots=6):
    """A bounded continuous cover of a polygon's oriented bounding rectangle.

    At normal half-width w, each radius-r disk covers a rectangle of axial
    half-length sqrt(r*r-w*w). Adjacent rectangles tile the bounding rectangle.
    A 0.01m inward guard separates execution from the mathematical 20m boundary.
    """
    if len(poly)<3:
        return None
    _,a,b=p1.polygon_diameter(poly)
    length=distance(a,b)
    if length<1e-9:
        return None
    ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    vx,vy=-uy,ux
    along=[x*ux+y*uy for x,y in poly]
    across=[x*vx+y*vy for x,y in poly]
    low,high=min(along),max(along);middle=(min(across)+max(across))/2
    half_width=(max(across)-min(across))/2
    r=CLEAR_R-.01
    if half_width>=r:
        return None
    half_length=math.sqrt(r*r-half_width*half_width)
    n=max(1,math.ceil((high-low)/(2*half_length)))
    if n>maximum_shots:
        return None
    centers=[(low+high)/2] if n==1 else [low+half_length+i*(high-low-2*half_length)/(n-1) for i in range(n)]
    points=[(s*ux+middle*vx,s*uy+middle*vy) for s in centers]
    def expected(order):
        result=0.
        for target,weight in samples:
            prev=current;cost=0.;found=False
            for point in order:
                cost+=distance(prev,point)/5
                if distance(target,point)<=CLEAR_R:
                    cost+=5;found=True;break
                cost+=3;prev=point
            if not found:
                return math.inf
            result+=weight*cost
        return result
    reverse=list(reversed(points))
    forward_cost,reverse_cost=expected(points),expected(reverse)
    if reverse_cost<forward_cost:
        points=reverse;forward_cost=reverse_cost
    return dict(points=points, expected_s=forward_cost, half_width=half_width,
                half_length=half_length, axial_bounds=[low,high], radius_guard=r)


class CardinalityP3(ProbePlanP3):
    name='CardinalityP3'

    def __init__(self):
        super().__init__()
        self.cardinality_certificates=[]

    def _retire_unknown_at_maximum(self):
        # The count is inferred from distinct positively observed channels, not the
        # simulator's hidden N. Finding 16 is enough; clearing all 16 is not needed.
        known=set(self.tracks)|self.cleared
        if len(known)>16:
            raise RuntimeError('More observed source channels than the problem permits')
        if len(known)==16:
            unknown=[ch for ch in range(1,21) if ch not in known and ch not in self.absent]
            if unknown:
                self.absent.update(unknown)
                self.cardinality_certificates.append(dict(observed_channels=sorted(known),absent_channels=unknown))

    def on_measure(self,state,ch,result,svd):
        super().on_measure(state,ch,result,svd)
        self._retire_unknown_at_maximum()

    def diagnostics(self):
        result=super().diagnostics()
        result['cardinality_certificates']=self.cardinality_certificates
        return result


class OpticalTaskP3(CardinalityP3):
    name='OpticalTaskP3'
    optical_gain_margin_s=1.

    def __init__(self):
        super().__init__()
        self.optical_pending=None
        self.optical_plans=[]

    @staticmethod
    def _old_action_cost(action,poly,samples,current):
        if action.kind=='measure':
            return ProbePlanP3._probe_cost(current,action.pos,poly,samples)
        if action.kind!='clear':
            return math.inf
        missed=[(point,w) for point,w in samples if distance(point,action.pos)>CLEAR_R]
        probability=sum(w for _,w in missed)
        cost=distance(current,action.pos)/5+(1-probability)*5
        if probability:
            conditional=[(point,w/probability) for point,w in missed]
            cost+=probability*(3+ProbePlanP3._probe_cost(action.pos,action.pos,poly,conditional))
        return cost

    def step(self,state):
        if self.optical_pending is not None:
            plan=self.optical_pending
            if not plan['points']:
                raise RuntimeError('Continuous optical cover exhausted without clearing: inconsistent observations')
            return Action('clear',plan['points'][0],plan['ch'])
        action=super().step(state)
        if action.kind not in ('clear','measure') or action.ch!=self.active_ch:
            return action
        track=self.tracks.get(action.ch)
        if (track is None or track.near is not None or len(track.records)<2
                or track.probe_after_fail or track.radius<=CLEAR_R or not track.poly):
            return action
        samples=self._belief_samples(track.poly)
        plan=optical_strip(track.poly,state.pos,samples)
        if plan is None:
            return action
        old_cost=self._old_action_cost(action,track.poly,samples,state.pos)
        if plan['expected_s']+self.optical_gain_margin_s>=old_cost:
            return action
        self.optical_pending=dict(ch=action.ch,points=list(plan['points']))
        self.optical_plans.append(dict(ch=action.ch,**plan,previous_expected_s=old_cost,
                                       feasible_polygon=list(track.poly)))
        return Action('clear',plan['points'][0],action.ch)

    def on_clear(self,state,ch,success):
        if self.optical_pending is None:
            return super().on_clear(state,ch,success)
        if ch!=self.optical_pending['ch']:
            raise RuntimeError('Optical plan channel mismatch')
        if success:
            self.optical_pending=None
            return super().on_clear(state,ch,True)
        self.optical_pending['points'].pop(0)
        track=self.tracks[ch]
        track.failures+=1
        track.near=None
        # A failed optical action is useful information. Preserve a conservative
        # hull; the precomputed continuous cover stays valid for any subset.
        poly=exclude_disk(track.poly,state.pos,CLEAR_R)
        if not poly:
            raise RuntimeError('Optical failure contradicts the feasible source region')
        track.poly=poly;track.center,track.radius=enclosing_circle(poly)
        track.estimate=centroid(poly);track.probe_after_fail=False

    def diagnostics(self):
        result=super().diagnostics()
        result['optical_plans']=self.optical_plans
        return result


class OpticalProbeP3(OpticalTaskP3):
    """Also price the terminal optical plan when choosing the second bearing point."""
    name='OpticalProbeP3'

    @staticmethod
    def _probe_cost(current,point,poly,samples):
        value=distance(current,point)/5+5.
        for hypothesis,weight in samples:
            d=distance(point,hypothesis)
            if d<=5:
                value+=weight*5;continue
            if d>1000:
                value+=weight*(d/5+30);continue
            angle=math.degrees(math.atan2(hypothesis[1]-point[1],hypothesis[0]-point[0]))%360
            for error,ew in ((-1.,.25),(0.,.5),(1.,.25)):
                observed=round((angle+error)%360,2)%360
                posterior=p1.hpi_intersect(poly,p1.make_sector_halfplanes(point,observed,EPS_DEG))
                if not posterior:return math.inf
                center,radius=enclosing_circle(posterior)
                if radius<=20-1e-5:
                    continuation=max(0.,distance(point,center)-(20-radius-1e-5))/5+5
                else:
                    estimate=centroid(posterior);miss=distance(estimate,hypothesis)
                    continuation=distance(point,estimate)/5
                    if radius<=80 and miss<=20:
                        continuation+=5
                    else:
                        continuation+=10+max(0.,miss-20)/5+(3 if radius<=80 else 0)
                    plan=optical_strip(posterior,point,ProbePlanP3._belief_samples(posterior))
                    if plan is not None:
                        continuation=min(continuation,plan['expected_s'])
                value+=weight*ew*continuation
        return value


class SharedBearingP3(CardinalityP3):
    """Buy a second channel's bearing at an already paid-for localization stop.

    Expected avoided future localization cost must exceed 5s detection + up to
    1s switching, plus a 2s planning margin. No extra movement is inserted.
    """
    name='SharedBearingP3'

    def __init__(self):
        super().__init__()
        self.shared_queue=[]
        self.shared_trigger=None
        self.shared_measurements=[]

    @staticmethod
    def _future_finish_cost(previous,poly,hypothesis):
        center,radius=enclosing_circle(poly)
        if radius<=20-1e-5:
            return max(0.,distance(previous,center)-(20-radius-1e-5))/5+5
        estimate=centroid(poly);error=distance(estimate,hypothesis)
        cost=distance(previous,estimate)/5
        if radius<=80 and error<=20:return cost+5
        return cost+10+max(0.,error-20)/5+(3 if radius<=80 else 0)

    def _sharing_candidates(self,state):
        current_track=self.tracks.get(self.active_ch)
        previous=current_track.estimate if current_track else state.pos
        nodes=[(ch,t.estimate) for ch,t in self.tracks.items() if ch not in self.cleared and ch!=self.active_ch]
        candidates=[]
        for ch,estimate in self._route(previous,nodes):
            track=self.tracks[ch]
            origin=previous;previous=estimate
            if (track.near is not None or track.probe_after_fail or track.radius<=20
                    or not track.records or not track.poly):continue
            if min(distance(state.pos,p) for p,_ in track.records)<100:continue
            if max(distance(state.pos,v) for v in track.poly)>999.99:continue
            samples=self._belief_samples(track.poly)
            old=self._local_action(ch,State(pos=origin,ch=ch))
            before=OpticalTaskP3._old_action_cost(old,track.poly,samples,origin)
            after=0.
            for hypothesis,weight in samples:
                if distance(state.pos,hypothesis)<=5:
                    after+=weight*(distance(origin,state.pos)/5+5);continue
                angle=math.degrees(math.atan2(hypothesis[1]-state.pos[1],hypothesis[0]-state.pos[0]))%360
                for error,ew in ((-1.,.25),(0.,.5),(1.,.25)):
                    observed=round((angle+error)%360,2)%360
                    posterior=p1.hpi_intersect(track.poly,p1.make_sector_halfplanes(state.pos,observed,EPS_DEG))
                    if not posterior:after=math.inf;break
                    after+=weight*ew*self._future_finish_cost(origin,posterior,hypothesis)
            saved=before-after-6.
            if saved>2.:
                candidates.append((saved,ch))
        return sorted(candidates,reverse=True)

    def step(self,state):
        self.shared_trigger=None
        while self.shared_queue:
            ch=self.shared_queue.pop(0)
            if ch in self.cleared or ch in self.absent:continue
            return Action('measure',state.pos,ch)
        action=super().step(state)
        if (action.kind=='measure' and action.ch==self.active_ch
                and distance(state.pos,action.pos)>100):
            self.shared_trigger=action.ch
        return action

    def on_measure(self,state,ch,result,svd):
        super().on_measure(state,ch,result,svd)
        if self.shared_trigger==ch:
            candidates=self._sharing_candidates(state)
            self.shared_queue=[other for _,other in candidates]
            if candidates:
                self.shared_measurements.append(dict(pos=state.pos,channels=list(self.shared_queue),
                                                      predicted_net_savings=[s for s,_ in candidates]))
        self.shared_trigger=None

    def diagnostics(self):
        result=super().diagnostics()
        result['shared_bearing_stops']=self.shared_measurements
        return result


class SharedOpticalP3(SharedBearingP3,OpticalTaskP3):
    name='SharedOpticalP3'
