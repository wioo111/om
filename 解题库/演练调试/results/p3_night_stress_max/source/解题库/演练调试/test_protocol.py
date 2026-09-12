"""Attachment 2 contract checks with fake responses only; never open a socket."""
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
import pytest

REPO=Path(__file__).resolve().parents[2]

@pytest.fixture(params=['第三问/v10','第四问/v6'])
def modules(request):
    root=REPO/'解题库'/request.param
    sys.path.insert(0,str(root))
    def read_module(name):
        spec=importlib.util.spec_from_file_location('contract_'+name,root/(name+'.py'))
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    try:
        yield read_module('robot'),read_module('robot_iter')
    finally:
        sys.path.remove(str(root))

class Reply:
    status=200
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps(self.data).encode('utf-8')

def test_network_retry_reuses_identical_request(modules,monkeypatch):
    client,_=modules
    seen=[];pauses=[]
    def send(req,timeout):
        seen.append(req)
        if len(seen)==1:raise URLError('simulated disconnect')
        return Reply({'accepted':True,'virtual_time_s':106})
    monkeypatch.setattr(client.urlrequest,'urlopen',send)
    monkeypatch.setattr(client,'time',SimpleNamespace(monotonic=lambda:100.,sleep=pauses.append))
    payload={'arena_id':'default','robot_id':'test-only','request_id':'same-id',
             'position':{'x':300.,'y':400.},'channel':2}
    assert client._post('http://127.0.0.1:2026','/measure',payload)['accepted']
    assert len(seen)==2 and seen[0] is seen[1]
    assert json.loads(seen[0].data)==payload
    assert seen[0].get_header('Content-type')=='application/json'
    assert not seen[0].data.startswith(b'\xef\xbb\xbf')
    assert pauses==[.2]  # Backoff only after a connection failure, never a 5s detection sleep.

def test_rejected_response_is_not_success(modules,monkeypatch):
    client,driver=modules
    monkeypatch.setattr(client.urlrequest,'urlopen',lambda *a,**k:Reply({'accepted':False,'virtual_time_s':0}))
    with pytest.raises(client.HTTPError_):client._post('http://127.0.0.1:2026','/measure',{})
    with pytest.raises(RuntimeError):driver.accepted_response({'accepted':False,'virtual_time_s':0})

def test_practice_guard_rechecked_before_network_retry(modules,monkeypatch):
    client,_=modules
    checks=[];requests=[]
    def guard():
        checks.append(1)
        if len(checks)==2:raise RuntimeError('session switched')
    def send(*args,**kwargs):
        requests.append(1);raise URLError('simulated disconnect')
    monkeypatch.setattr(client.urlrequest,'urlopen',send)
    monkeypatch.setattr(client,'time',SimpleNamespace(monotonic=lambda:100.,sleep=lambda _:None))
    with pytest.raises(RuntimeError,match='session switched'):
        client._post('http://127.0.0.1:2026','/measure',{},before_attempt=guard)
    assert len(checks)==2 and len(requests)==1

def test_http_conflict_not_retried_as_new_action(modules,monkeypatch):
    client,_=modules
    attempts=[]
    def send(*args,**kwargs):
        attempts.append(1)
        raise HTTPError('http://127.0.0.1:2026/measure',409,'Conflict',{},io.BytesIO(b'{}'))
    monkeypatch.setattr(client.urlrequest,'urlopen',send)
    with pytest.raises(client.HTTPError_,match='409'):client._post('http://127.0.0.1:2026','/measure',{})
    assert len(attempts)==1

def test_clear_preserves_receiver_and_uses_returned_clock(modules,monkeypatch):
    _,driver=modules
    from strategy import Action
    seen=[]
    class Policy:
        def __init__(self):
            self.actions=iter([Action('measure',(300.,400.),2),Action('clear',(0.,0.),3),
                               Action('measure',(0.,0.),2),Action('done')])
        def step(self,state):seen.append((state.ch,state.virtual_time));return next(self.actions)
        def on_measure(self,*args):pass
        def on_clear(self,*args):pass
    class Sim:
        def __init__(self):self.readings=iter([106.,214.]);self.deadlines=[]
        def set_deadline(self,value):self.deadlines.append(value)
        def enter(self):return dict(accepted=True,virtual_time_s=0.,remaining_real_duration_s=3.,max_virtual_duration_s=360000.)
        def measure(self,*args):return dict(accepted=True,virtual_time_s=next(self.readings),measure_result='no_signal')
        def clear(self,*args):return dict(accepted=True,virtual_time_s=209.,clear_result='no_target_in_range')
        def exit(self):return dict(accepted=True,virtual_time_s=214.)
    monkeypatch.setattr(driver,'time',SimpleNamespace(monotonic=lambda:100.))
    sim=Sim();result=driver.run_with_sim_strategy(Policy(),sim)
    assert sim.deadlines==[102.7,103.]
    assert seen==[(1,0.),(2,106.),(2,209.),(2,214.)]
    assert result['time_breakdown']==dict(move_time_s=200.,switch_time_s=1.,measure_time_s=10.,clear_time_s=3.)
    assert result['virtual_time_s']==214. and result['clear_fail_count']==1
