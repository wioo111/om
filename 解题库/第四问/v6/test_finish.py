import random
import pytest
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from strategy import State
from strategy_fast import FastP4
from strategy_finish import FinishP4
from strategy_p4 import Track
from mock_simulator_p4 import P4MockSimulator
from robot_iter import run_with_sim_strategy


def thin():return Track(records=[((0.,0.),0.),((0.,100.),315.)],poly=[(-24.,-2.),(24.,-2.),(24.,2.),(-24.,2.)],center=(0.,0.),radius=24.1)

def test_core_completion_required():
    s=FinishP4();s.tracks[1]=thin()
    assert s._needs_sample(1)
    assert not s.plans
    s.core_complete=True
    assert not s._needs_sample(1)
    assert 1 in s.plans and s.plans[1] is None

def test_uncoverable_channel_keeps_shared_readings():
    s=FinishP4();s.core_complete=True;s.tracks[1]=thin();s.tracks[2]=Track()
    assert s._needs_sample(1) and not s.plans

def test_cover_whole_region():
    s=FinishP4();s.core_complete=True;s.tracks[1]=thin();assert not s._needs_sample(1)
    proof=s.certificates[1]
    assert len(proof['points'])<=6
    assert Polygon(proof['polygon']).difference(unary_union([Point(p).buffer(19.99999,quad_segs=32) for p in proof['points']])).is_empty

def test_invalid_polygon_falls_back():
    s=FinishP4();s.core_complete=True;s.tracks[1]=thin();s.tracks[1].poly=[(0,0),(10,10),(0,10),(10,0)]
    assert s._needs_sample(1) and not s.plans

def test_failure_advances_not_recovery():
    s=FinishP4();s.tracks[1]=thin();s.plans[1]=[(0,0),(25,0)];s.phase='localization';s._ordered=True
    st=State(pos=(0.,0.),ch=2)
    s.on_clear(st,1,False)
    assert s.plans[1]==[(25,0)] and not s.tracks[1].recovery_required
    assert s._next_local_action(1,st).pos==(25,0) and 1 not in s.cleared
    with pytest.raises(RuntimeError,match='exhausted'):s.on_clear(st,1,False)

def test_success_completes_actual_channel():
    s=FinishP4();s.tracks[1]=thin();s.plans[1]=[(0,0)];st=State(pos=(0,0),ch=2)
    s.on_clear(st,1,True)
    assert 1 in st.cleared and 1 not in s.plans and st.ch==2

def test_no_signal_does_not_clip():
    s=FinishP4();s.tracks[1]=thin();s.phase='localization';poly=s.tracks[1].poly[:]
    s.on_measure(State(pos=(1000,1000),ch=1),1,'no_signal',None)
    assert s.tracks[1].poly==poly

def test_switch_off_exact():
    outputs=[]
    for s in [FastP4(),FinishP4(enabled=False)]:
        random.seed(17);r=run_with_sim_strategy(s,P4MockSimulator(seed=946000,n_sources=10,dir_frac=.25,error_mode='fixed'))
        outputs.append(r['log'])
    assert outputs[0]==outputs[1]


def test_trimmed_core_cell_coverage_proof():
    from strategy_finish import TRIMMED_CORE
    import math
    grid=set(TRIMMED_CORE)
    assert len(grid)==45 and (0.,0.) in grid
    for x in range(-2100,2100,700):
        for y in range(-2100,2100,700):
            closest=(max(x,min(0,x+700)),max(y,min(0,y+700)))
            if math.hypot(*closest)<=1800:
                assert {(x,y),(x+700,y),(x,y+700),(x+700,y+700)}<=grid
    assert math.sqrt(2)*700<1000


def test_core45_not_declared_after44():
    from strategy_finish import TRIMMED_CORE
    s=FinishP4(trim_corners=True)
    s.discovery_station_index=44
    a=s._next_discovery_action()
    assert a.kind=='measure' and not s.core_complete
    s.discovery_channel_index=len(s._station_channels)
    s._next_discovery_action()
    assert s.core_complete
