"""One-click acceptance uses fixtures and -Check only; never connects to a live simulator."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

REPO=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('one_click',REPO/'tools/practice_launch.py')
launch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)

def make_journal(root,event='practice_authorized',ready=True,entered=False,name='run-test'):
    path=root/'behavior-runs'/name/'behavior.journal.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    rows=[{'event':event,'seq':1}]
    if ready:rows.append({'event':'api_opened','entered':entered})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
    return path

def clock_with_tick(callback):
    now=[0.]
    def sleep(seconds):now[0]+=seconds;callback(now[0])
    return lambda:now[0],sleep

def test_wait_for_countdown_without_network(tmp_path):
    path=make_journal(tmp_path,ready=False)
    clock,sleep=clock_with_tick(lambda _:make_journal(tmp_path))
    result=launch.wait_for_practice(tmp_path,timeout=1,clock=clock,sleep=sleep)
    assert result.ready and result.journal==path

def test_wait_for_initial_preparation(tmp_path):
    clock,sleep=clock_with_tick(lambda _:make_journal(tmp_path))
    assert launch.wait_for_practice(tmp_path,timeout=1,clock=clock,sleep=sleep).ready

@pytest.mark.parametrize('event',['formal_authorized','unknown','case_generated'])
def test_never_accept_nonpractice(tmp_path,event):
    make_journal(tmp_path,event=event)
    with pytest.raises(RuntimeError,match='NOT A VERIFIED PRACTICE'):
        launch.wait_for_practice(tmp_path)

def test_refuse_existing_robot(tmp_path):
    make_journal(tmp_path,entered=True)
    with pytest.raises(RuntimeError,match='already entered'):launch.wait_for_practice(tmp_path)

def test_refuse_ended_session(tmp_path):
    path=make_journal(tmp_path)
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps({'event':'ended','end_reason':'user_exit'})+'\n')
    with pytest.raises(RuntimeError,match='already ended'):launch.wait_for_practice(tmp_path)

def test_timeout_does_not_enter(tmp_path):
    clock,sleep=clock_with_tick(lambda _:None)
    with pytest.raises(RuntimeError,match='未发现开放的演练'):
        launch.wait_for_practice(tmp_path,timeout=.5,clock=clock,sleep=sleep)

def test_session_switch_while_waiting_stops(tmp_path):
    old=make_journal(tmp_path,ready=False)
    def switch(_):
        old.unlink()  # Removes only this test's temporary fixture.
        make_journal(tmp_path,name='run-new')
    clock,sleep=clock_with_tick(switch)
    with pytest.raises(RuntimeError,match='会话已切换'):
        launch.wait_for_practice(tmp_path,timeout=1,clock=clock,sleep=sleep)

@pytest.mark.skipif(os.name!='nt',reason='Windows one-click lock')
def test_double_click_lock_released_on_exit(tmp_path):
    path=tmp_path/'test.lock'
    with launch.one_robot(path):
        with pytest.raises(RuntimeError,match='已有一个接入程序'):
            with launch.one_robot(path):pass
    with launch.one_robot(path):pass

@pytest.mark.parametrize('problem',[3,4])
@pytest.mark.skipif(os.name!='nt',reason='Windows one-click entry')
def test_dispatch_and_execution_record(tmp_path,monkeypatch,problem):
    monkeypatch.delenv('JAMMERS_ROBOT_ID',raising=False)
    config=tmp_path/'config.json';config.write_text('{"robot_id":"000000000000"}',encoding='utf-8')
    make_journal(tmp_path)
    calls=[]
    def fake_runner(args):
        calls.append(args)
        print('fixture team 000000000000')
        return tmp_path/'fixture-result',dict(cleared=1,virtual_time_s=5.)
    out=tmp_path/'out'
    assert launch.execute(problem,config,tmp_path,out,runner=fake_runner)==0
    assert calls[0][:4]==['--problem',str(problem),'--strategy','candidate']
    assert '--journal' in calls[0]
    record=json.loads(next(out.glob('*/execution.json')).read_text(encoding='utf-8'))
    assert record['exit_code']==0 and record['mode']=='practice'
    assert '000000000000' not in next(out.glob('*/console.log')).read_text(encoding='utf-8')

@pytest.mark.skipif(os.name!='nt',reason='Windows one-click entry')
def test_formal_session_never_dispatches_robot(tmp_path,monkeypatch):
    monkeypatch.delenv('JAMMERS_ROBOT_ID',raising=False)
    config=tmp_path/'config.json';config.write_text('{"robot_id":"000000000000"}',encoding='utf-8')
    make_journal(tmp_path,event='formal_authorized')
    def forbidden(args):pytest.fail('Robot must never dispatch in a formal session')
    assert launch.execute(3,config,tmp_path,tmp_path/'out',runner=forbidden)==1

@pytest.mark.parametrize('problem,label',[(3,'第三问'),(4,'第四问')])
@pytest.mark.skipif(os.name!='nt',reason='Windows CMD bootstrap')
def test_real_double_click_files_check_only(tmp_path,problem,label):
    entry=REPO/f'{label}_一键接入演练.cmd'
    response=subprocess.run(['cmd.exe','/d','/c',str(entry),'-Check'],cwd=tmp_path,
        capture_output=True,encoding='utf-8',timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
    assert response.returncode==0,response.stdout+response.stderr
    assert f'问题{problem}启动器可用' in response.stdout
    assert '没有发送任何模拟器请求' in response.stdout
