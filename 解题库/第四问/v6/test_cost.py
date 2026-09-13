import json
import math
import random
from pathlib import Path
import subprocess
import sys
import pytest
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from mock_simulator_p4 import P4MockSimulator
from strategy_cost import CostAwareP4, optical_cover, OPTICAL_R
from strategy_fast import FastP4
from strategy_p4 import Track
from strategy import State
from robot_iter import run_with_sim_strategy
from cost_experiment import specs, run_case


def state(pos=(0.,0.),ch=1):return State(pos=pos,ch=ch)

@pytest.mark.parametrize('r',[1000,1500])
def test_reception_range(r):
    sim=P4MockSimulator(seed=5,n_sources=16,reception_range=(r,r))
    assert {s['re'] for s in sim.sources.values()}=={r}

@pytest.mark.parametrize('bounds',[(999,1500),(1000,1501),(1500,1000)])
def test_invalid_radius(bounds):
    with pytest.raises(ValueError):P4MockSimulator(reception_range=bounds)

@pytest.mark.parametrize('mode',['fixed','edge'])
def test_error_is_position_keyed(mode):
    sim=P4MockSimulator(seed=18,n_sources=10,dir_frac=0,error_mode=mode)
    ch=next(iter(sim.sources));x,y=sim.sources[ch]['pos'];p=(x+100,y)
    a=sim.measure(*p,ch)
    sim.measure(x+200,y+100,ch)
    b=sim.measure(*p,ch)
    assert a['svd_deg']==b['svd_deg']


def test_cardinality_15_16_and_clear():
    s=CostAwareP4();st=state()
    for ch in range(1,16):s.on_measure(st,ch,'near',None)
    assert s._needs_sample(20) and 20 not in s.absent
    s.on_clear(st,1,True)
    assert len(s.ever_observed_channels)==15
    s.on_measure(st,16,'direction',0.)
    assert len(s.ever_observed_channels)==16 and not s._needs_sample(20)
    assert not s.done and 16 in s.tracks
    s.on_measure(st,19,'no_signal',None)
    assert 19 not in s.ever_observed_channels


def test_near_preserves_scan_queue():
    s=CostAwareP4();st=state()
    first=s.step(st);st.pos=first.pos;st.ch=first.ch
    s.on_measure(st,first.ch,'near',None)
    before=(s.discovery_station_index,s.discovery_channel_index,s._station_channels[:],s.work_index)
    a=s.step(st)
    assert a.kind=='clear' and a.pos==st.pos
    s.on_clear(st,a.ch,True)
    assert before==(s.discovery_station_index,s.discovery_channel_index,s._station_channels,s.work_index)
    nxt=s.step(st)
    assert nxt.kind=='measure' and nxt.ch!=a.ch and nxt.pos==first.pos and not s.done


def test_center_alone_not_clear():
    s=CostAwareP4();s.tracks[1]=Track(poly=[(-30,-1),(30,-1),(30,1),(-30,1)],center=(0,0),radius=30)
    assert s._instant(state()) is None


def test_no_signal_never_clips():
    s=CostAwareP4(enable_c=True);s.phase='localization'
    s.tracks[1]=Track(records=[((0,0),0.),((0,100),315.)],poly=[(50,0),(150,0),(100,50)])
    before=s.region(1).wkt
    s.on_measure(state((1000,1000)),1,'no_signal',None)
    assert s.region(1).wkt==before


def test_duplicate_fixed_measure_not_information():
    s=CostAwareP4();st=state()
    s.on_measure(st,1,'direction',1.)
    s.on_measure(st,1,'direction',1.)
    assert len(s.tracks[1].records)==1


def test_failed_clear_advances_and_exclusion_persists():
    s=CostAwareP4(enable_c=True);s.phase='localization';s._ordered=True
    s.tracks[1]=Track(poly=[(-50,-50),(50,-50),(50,50),(-50,50)])
    s.optical_plans[1]=[(0,0),(30,0)]
    s.on_clear(state(),1,False)
    assert s.optical_plans[1]==[(30,0)]
    assert not s.region(1).covers(Point(0,0))
    # Geometry is recomputed later; exclusions still survive.
    s.tracks[1].poly=[(-60,-60),(60,-60),(60,60),(-60,60)]
    assert not s.region(1).covers(Point(0,0))
    assert s._next_local_action(1,state()).pos==(30,0)
    with pytest.raises(RuntimeError,match='exhausted'):s.on_clear(state((30,0)),1,False)
    assert 1 not in s.cleared and not s.done


def test_no_progress_bounded():
    s=CostAwareP4(enable_c=True);s.phase='localization';s._ordered=True
    s.work_channels=[1];s.tracks[1]=Track(records=[((0.,0.),0.)])
    st=state()
    for _ in range(2):
        a=s.step(st);s.on_measure(st,1,'direction',0.)
    with pytest.raises(RuntimeError,match='no_progress'):s.step(st)


def test_continuous_cover():
    g=Polygon([(-45,-8),(45,-8),(45,8),(-45,8)])
    plan=optical_cover(g,(100,0));assert plan and len(plan['points'])<=6
    assert g.difference(unary_union([Point(p).buffer(OPTICAL_R,quad_segs=32) for p in plan['points']])).is_empty
    assert plan['total_s']==pytest.approx(plan['move_s']+plan['clear_success_s']+plan['clear_failure_s'])


def test_outer_region_contains_actual_source():
    sim=P4MockSimulator(seed=75,n_sources=10,error_mode='edge',dir_frac=.5)
    s=CostAwareP4(enable_c=True)
    for ch,src in sim.sources.items():
        for dx,dy in [(100,0),(-100,0),(0,100),(0,-100),(80,80),(-80,-80)]:
            x,y=src['pos'][0]+dx,src['pos'][1]+dy
            r=sim.measure(x,y,ch);s.on_measure(state((x,y),ch),ch,r['measure_result'],r['svd_deg'])
        if ch in s.tracks and s.tracks[ch].poly:
            assert s.region(ch).buffer(1e-7).covers(Point(src['pos']))


def test_all_off_exact_baseline_actions():
    logs=[]
    for factory in (FastP4,lambda:CostAwareP4(False,False,False)):
        random.seed(999)
        r=run_with_sim_strategy(factory(),P4MockSimulator(seed=942000,n_sources=10,dir_frac=.25,error_mode='fixed'))
        assert r['stop_reason']=='all_channels_cleared_or_covered'
        logs.append(r['log'])
    assert logs[0]==logs[1]


def test_cartesian_and_disjoint():
    d,c,b=specs('development'),specs('confirmation'),specs('boundary')
    assert len(d)==14 and len(c)==56 and len(b)==112
    assert len({(s['N'],s['dir_frac'],s['error_mode']) for s in c})==56
    assert not {s['seed'] for s in d}&{s['seed'] for s in c}


def test_step_limit_not_accepted(monkeypatch,tmp_path):
    import cost_experiment
    class Stopped:
        name='stopped';phase='localization'
    monkeypatch.setattr(cost_experiment,'make',lambda _:Stopped())
    import mock_simulator_p4
    class AlreadyCleared(P4MockSimulator):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.cleared=set(self.sources)
    monkeypatch.setattr(mock_simulator_p4,'P4MockSimulator',AlreadyCleared)
    import robot_iter
    def stopped(strategy,sim,max_steps):
        # Test harness creates all-clear, while the strategy sees no truth.
        return dict(stop_reason='step_limit',cleared=10,virtual_time_s=0.)
    monkeypatch.setattr(robot_iter,'run_with_sim_strategy',stopped)
    r=run_case((specs('development')[0],'FastP4',tmp_path))
    assert r['full_clear'] and not r['normal_stop'] and not r['accepted_run']


def test_independent_cwd(tmp_path):
    runner=Path(__file__).with_name('cost_experiment.py').resolve()
    dirs=[tmp_path/'a',tmp_path/'b'];logs=[]
    for d in dirs:
        d.mkdir();out=d/'out'
        proc=subprocess.run([sys.executable,str(runner),'--single','941005','--output',str(out)],cwd=d,capture_output=True)
        assert proc.returncode==0,proc.stderr
        logs.append(json.loads(next(out.glob('*.json')).read_text(encoding='utf-8'))['actions'])
    assert logs[0]==logs[1]


def test_benchmark_forwards_radius(monkeypatch,tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'演练调试/benchmark_speed.py'
    if not path.exists():
        pytest.skip('shared benchmark is outside standalone package; tested in source workspace')
    spec=importlib.util.spec_from_file_location('benchmark_p4_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import mock_simulator_p4
    seen=[]
    class Checking(P4MockSimulator):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            seen.append(self.reception_range)
            assert {s['re'] for s in self.sources.values()}=={1000.}
    monkeypatch.setattr(mock_simulator_p4,'P4MockSimulator',Checking)
    module.run_case((4,'fast',941019,10,'fixed',.5,tmp_path,(1000,1000)))
    assert seen==[(1000.,1000.)]


def test_invalid_region_falls_back_without_repair():
    s=CostAwareP4(enable_c=True)
    s.tracks[1]=Track(poly=[(0,0),(10,10),(0,10),(10,0)])
    original=s.tracks[1].poly[:]
    assert s.region(1) is None
    assert s._instant(state()) is None
    assert s.tracks[1].poly==original and not s.done
    assert s.events['invalid_geometry_fallback']==2
