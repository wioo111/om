"""P4 console checks use recorded response shapes and never open a socket."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p4_console_runner',ROOT/'run_practice.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize('path,response,result',[
    ('/enter',dict(accepted=True,virtual_time_s=0),'entered'),
    ('/measure',dict(accepted=True,virtual_time_s=5,measure_result='direction',svd_deg=190.62),'direction'),
    ('/measure',dict(accepted=True,virtual_time_s=11,measure_result='no_signal'),'no_signal'),
    ('/measure',dict(accepted=True,virtual_time_s=17,measure_result='near',svd_deg=None),'near'),
    ('/clear',dict(accepted=True,virtual_time_s=22,clear_result='success'),'success'),
    ('/clear',dict(accepted=True,virtual_time_s=25,clear_result='no_target_in_range'),'no_target_in_range'),
    ('/exit',dict(accepted=True,virtual_time_s=25,exit_reason='user_exit'),'exited'),
])
def test_real_endpoint_result_without_false_nulls(path,response,result):
    before=copy.deepcopy(response)
    request=dict(channel=7,position=dict(x=1.,y=2.)) if path in ('/measure','/clear') else {}
    summary=runner.p4_action_summary(100,path,request,response)
    assert summary['result']==result
    assert summary['accepted'] is True
    assert 'null' not in json.dumps(summary)
    assert response==before
    if result=='direction':assert summary['svd_deg']==190.62
    else:assert 'svd_deg' not in summary
    if request:assert summary['channel']==7 and summary['position']==request['position']
    if path=='/exit':assert summary['exit_reason']=='user_exit'


@pytest.mark.parametrize('response,missing',[
    (dict(accepted=True,virtual_time_s=5),['measure_result']),
    (dict(accepted=True,virtual_time_s=5,measure_result='direction'),['svd_deg']),
    (dict(accepted=True,measure_result='no_signal'),['virtual_time_s']),
    (dict(virtual_time_s=5,measure_result='near'),['accepted']),
])
def test_missing_required_data_is_reported(response,missing):
    summary=runner.p4_action_summary(2,'/measure',{},response)
    assert summary['protocol_warning']=='missing_required_fields'
    assert summary['missing_fields']==missing
    assert 'null' not in json.dumps(summary)


class FutureCandidate:
    name='FutureP4_new_config'
    def diagnostics(self):
        return dict(local_limit=6,scan_spacing=720.,switches=dict(new_feature=True),triggers={})


class FinishShapedCandidate:
    name='FinishShape'
    def diagnostics(self):
        return dict(enabled=True,trim_corners=True,triggers={})


@pytest.mark.parametrize('candidate',[FutureCandidate(),FinishShapedCandidate()])
def test_metadata_follows_loaded_class_and_existing_diagnostics(candidate,capsys):
    metadata=runner.p4_strategy_metadata(candidate)
    assert metadata['actual_class']==type(candidate).__name__
    assert metadata['strategy']==candidate.name
    assert metadata['strategy_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    assert metadata['feature_config']
    runner.print_p4_strategy(metadata)
    output=capsys.readouterr().out
    assert type(candidate).__name__ in output and candidate.name in output
    assert metadata['strategy_sha256'] in output
    assert 'triggers' not in output
    for key in metadata['feature_config']:assert key in output


def test_check_supports_candidate_without_finish_attributes(monkeypatch,capsys):
    launch_spec=importlib.util.spec_from_file_location('p4_console_launch',ROOT.parents[1]/'tools/practice_launch.py')
    launch=importlib.util.module_from_spec(launch_spec)
    monkeypatch.setattr(sys,'path',sys.path[:])
    launch_spec.loader.exec_module(launch)
    monkeypatch.setitem(sys.modules,'candidates',SimpleNamespace(make_candidate=lambda problem:FutureCandidate()))
    monkeypatch.setattr(launch,'execute',lambda *a,**k:pytest.fail('Check must never execute a robot'))
    assert launch.main(['--problem','4','--check'])==0
    output=capsys.readouterr().out
    assert 'FutureCandidate' in output and 'new_feature' in output
    assert '没有发送任何模拟器请求' in output
