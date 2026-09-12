import json
from pathlib import Path
import sys
import pytest
from run_practice import PracticeGuard

def journal(tmp_path,event='practice_authorized',entered=False):
    f=tmp_path/'behavior-runs/run-test/behavior.journal.jsonl';f.parent.mkdir(parents=True)
    f.write_text(json.dumps({'event':event})+'\n'+json.dumps({'event':'api_opened','entered':entered})+'\n',encoding='utf-8')
    return f

@pytest.mark.parametrize('event',['formal_authorized','case_generated','unknown',''])
def test_reject_nonpractice(tmp_path,event):
    journal(tmp_path,event)
    with pytest.raises(RuntimeError):PracticeGuard(tmp_path)

def test_accept_practice_and_reject_switch(tmp_path):
    f=journal(tmp_path);g=PracticeGuard(tmp_path);g.check()
    f.write_text(json.dumps({'event':'formal_authorized'})+'\n',encoding='utf-8')
    with pytest.raises(RuntimeError):g.check()

def test_reject_entered(tmp_path):
    journal(tmp_path,entered=True)
    with pytest.raises(RuntimeError):PracticeGuard(tmp_path)

def test_reject_missing(tmp_path):
    with pytest.raises(RuntimeError):PracticeGuard(tmp_path)

def test_reject_countdown(tmp_path):
    f=journal(tmp_path)
    f.write_text(json.dumps({'event':'practice_authorized'})+'\n',encoding='utf-8')
    with pytest.raises(RuntimeError,match='not ready'):PracticeGuard(tmp_path)

def test_core_geometry_and_direction():
    root=Path(__file__).resolve().parents[1]/'第四问/v6'
    sys.path.insert(0,str(root))
    from strategy_fast import CORE_STATIONS
    from mock_simulator_p4 import P4MockSimulator
    assert len(CORE_STATIONS)==49
    assert 2*700**2<1000**2
    assert min(x for x,y in CORE_STATIONS)==-2100 and max(x for x,y in CORE_STATIONS)==2100
    sim=P4MockSimulator(seed=1,error_mode='fixed')
    src={'pos':(0.,0.),'is_dir':True,'direction':0}
    assert sim._covered(src,(100.,0.))
    assert not sim._covered(src,(-100.,0.))
    assert sim._covered(src,(0.,100.))

def test_skipped_queue_tail_advances_station():
    from strategy_fast import FastP4
    policy=FastP4()
    policy._station_channels=[1,2]
    policy.discovery_channel_index=1
    policy.absent.add(2)
    action=policy._next_discovery_action()
    assert policy.discovery_station_index==1
    assert action.ch==1

def test_first_localization_action_uses_nearest_channel():
    from strategy import State
    from strategy_p4 import Track
    from strategy_fast import FastP4
    policy=FastP4()
    policy.discovery_station_index=len(policy.discovery_stations)
    policy.tracks={1:Track(),2:Track()}
    policy.tracks[1].near=(1500.,0.)
    policy.tracks[2].near=(5.,0.)
    action=policy.step(State(pos=(0.,0.),ch=1))
    assert action.kind=='clear' and action.ch==2
