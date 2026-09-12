"""Task-derived correctness: cardinality deduction and continuous optical covers."""
import math
from pathlib import Path
import sys

import pytest
from shapely.geometry import Point,Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parent
_names=('strategy','strategy_fast','strategy_v8','strategy_night','strategy_transit','strategy_joint','strategy_task')
_saved={name:sys.modules.pop(name) for name in _names if name in sys.modules}
_path=str(ROOT.parent/'第三问/v10');sys.path.insert(0,_path)
try:
    from strategy import State,Action
    from strategy_v8 import Track,centroid,enclosing_circle,distance
    from strategy_task import CardinalityP3,OpticalTaskP3,SharedBearingP3,optical_strip
finally:
    sys.path.remove(_path)
    for _name in _names:sys.modules.pop(_name,None)
    sys.modules.update(_saved)


@pytest.mark.parametrize('count',[10,14,15,16])
def test_only_sixteen_positive_channels_retire_unknown(count):
    policy=CardinalityP3();state=State(pos=(0.,0.),ch=1)
    for ch in range(1,count+1):policy.on_measure(state,ch,'near',None)
    assert policy.cleared==set() and not policy.done
    if count==16:
        assert policy.absent==set(range(17,21))
        assert len(policy.cardinality_certificates)==1
    else:
        assert policy.absent==set() and policy.cardinality_certificates==[]


def test_repeated_channel_is_not_counted_twice():
    policy=CardinalityP3();state=State()
    for _ in range(20):policy.on_measure(state,1,'near',None)
    assert policy.absent==set()


def rectangle(length,width,angle):
    u,v=math.cos(angle),math.sin(angle)
    return [(500+x*u-y*v,-300+x*v+y*u)
            for x,y in [(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)]]


@pytest.mark.parametrize('length,width',[(30,2),(60,8),(100,15),(120,25),(60,35)])
@pytest.mark.parametrize('angle',[0.,.5,1.4])
def test_optical_disks_cover_the_whole_polygon_not_only_vertices(length,width,angle):
    poly=rectangle(length,width,angle);samples=OpticalTaskP3._belief_samples(poly)
    plan=optical_strip(poly,(0.,0.),samples)
    assert plan is not None
    # Inner polygon approximations to the physical 20m disks. Covering the whole
    # feasible polygon is stronger than checking a few sampled hypothetical targets.
    disks=unary_union([Point(p).buffer(20,quad_segs=512) for p in plan['points']])
    assert disks.covers(Polygon(poly))
    assert len(plan['points'])<=6
    assert plan['radius_guard']<20


def test_wide_or_long_uncertainty_falls_back_to_radio():
    for poly in [rectangle(100,80,0),rectangle(1000,10,0)]:
        assert optical_strip(poly,(0.,0.),OpticalTaskP3._belief_samples(poly)) is None


@pytest.mark.parametrize('target_fraction',[0.,.25,.5,.75,1.])
def test_every_optical_failure_advances_and_boundary_target_is_cleared(target_fraction):
    poly=rectangle(160,8,0);policy=OpticalTaskP3();state=State(pos=(0.,0.),ch=1)
    plan=optical_strip(poly,state.pos,policy._belief_samples(poly));assert plan is not None
    target=(420+160*target_fraction,-296)
    center,radius=enclosing_circle(poly)
    policy.tracks[1]=Track(records=[((0.,0.),0.),((50.,50.),0.)],poly=poly,center=center,radius=radius,estimate=centroid(poly))
    policy.active_ch=1;policy.optical_pending={'ch':1,'points':list(plan['points'])}
    for _ in range(len(plan['points'])):
        action=policy.step(state);assert action.kind=='clear'
        before=len(policy.optical_pending['points']);state.pos=action.pos
        success=distance(target,action.pos)<=20
        policy.on_clear(state,1,success)
        if success:break
        assert len(policy.optical_pending['points'])==before-1
        assert Polygon(policy.tracks[1].poly).buffer(1e-6).covers(Point(target))
    assert 1 in policy.cleared and 1 in state.cleared
    assert policy.optical_pending is None


def test_missing_cover_cannot_report_completion():
    policy=OpticalTaskP3();policy.optical_pending={'ch':1,'points':[]}
    with pytest.raises(RuntimeError,match='exhausted'):policy.step(State())


def test_regular_failure_keeps_original_recovery_not_optical_plan():
    policy=OpticalTaskP3();policy.tracks[1]=Track()
    policy.on_clear(State(),1,False)
    assert policy.tracks[1].probe_after_fail
    assert policy.optical_pending is None


def test_shared_measure_never_adds_travel_or_overwrites_active_channel():
    policy=SharedBearingP3();state=State(pos=(50.,70.),ch=1)
    policy.active_ch=1;policy.shared_queue=[2]
    a=policy.step(state)
    assert a.kind=='measure' and a.pos==state.pos and a.ch==2
    assert policy.active_ch==1 and policy.shared_trigger is None
