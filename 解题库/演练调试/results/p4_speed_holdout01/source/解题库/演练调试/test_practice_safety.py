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
