"""Offline tests for packaging; these are NOT new strategy experiments."""
import importlib.util
import json
import subprocess
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('deliver',Path(__file__).with_name('prepare_submission.py'))
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture(root):
    for name in m.REQUIRED:
        p=root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('VALUE = 1\n',encoding='utf-8')
    a=root/m.P3/'strategy_task.py'
    a.write_text('from helper import VALUE\n',encoding='utf-8')
    (a.parent/'helper.py').write_text('VALUE = 1\n',encoding='utf-8')
    (root/'tools/formal_launch.py').write_text('raise RuntimeError("MUST NOT EXECUTE")\n',encoding='utf-8')
    return root


def test_prepare_keeps_code_and_never_runs(tmp_path):
    r=fixture(tmp_path/'repo');o=tmp_path/'out';m.prepare(r,o,{})
    assert (o/'支撑材料工作区/程序与复现'/m.P3/'helper.py').is_file()
    assert 'MUST NOT EXECUTE' in (o/'附录B_完整代码.md').read_text(encoding='utf-8')
    assert not (o/'正式提交').exists()


def test_no_overwrite(tmp_path):
    r=fixture(tmp_path/'repo');o=tmp_path/'out';m.prepare(r,o,{})
    with pytest.raises(FileExistsError):m.prepare(r,o,{})


def test_missing_sources_fail(tmp_path):
    with pytest.raises(ValueError):m.prepare(tmp_path/'empty',tmp_path/'out',{})


def test_traversal_rejected():
    for p in ['../secrets','/absolute','C:/bad','x/../../bad']:
        with pytest.raises(ValueError):m.safe_relative(p)


def test_undisclosed_finalization_is_blocked(tmp_path):
    r=fixture(tmp_path/'repo');o=tmp_path/'out';m.prepare(r,o,{})
    with pytest.raises(RuntimeError):m.final_check_and_pack(r,o)
    assert (o/'阻塞项.json').exists()
    assert not (o/'正式提交').exists()


def test_extra_files_join_inventory_and_appendix(tmp_path):
    r=fixture(tmp_path/'repo');ext=tmp_path/'extra.py';ext.write_text('x = 3\n',encoding='utf-8')
    o=tmp_path/'out';m.prepare(r,o,{'extra_files':[{'source':str(ext),'destination':'其他/extra.py'}]})
    assert '其他/extra.py' in (o/'附录B_完整代码.md').read_text(encoding='utf-8')


def test_identity_flagged_not_redacted(tmp_path):
    p=tmp_path/'source.py';p.write_text('SOME_PRIVATE_VALUE\n',encoding='utf-8')
    assert m.scan_text(p,['SOME_PRIVATE_VALUE'])==['private_term']
    assert 'SOME_PRIVATE_VALUE' in p.read_text(encoding='utf-8')


def test_archive_only_tracked_allowlist(tmp_path):
    r=fixture(tmp_path/'repo')
    subprocess.run(['git','init',str(r)],check=True,capture_output=True)
    (r/'CUMCM_Q1Q2_COMPLETE.zip').write_bytes(b'old bytes')
    (r/'private.txt').write_text('leave me',encoding='utf-8')
    (r/'.claude').mkdir();(r/'.claude/untracked').write_text('keep untracked',encoding='utf-8')
    subprocess.run(['git','-C',str(r),'add','CUMCM_Q1Q2_COMPLETE.zip'],check=True)
    subprocess.run(['git','-C',str(r),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture'],check=True,capture_output=True)
    out=tmp_path/'archive';m.archive(r,out)
    assert not (r/'CUMCM_Q1Q2_COMPLETE.zip').exists()
    assert (out/'CUMCM_Q1Q2_COMPLETE.zip').read_bytes()==b'old bytes'
    assert (r/'private.txt').exists() and (r/'.claude/untracked').exists()
    assert (r/m.P3/'strategy_task.py').exists()


def test_archive_must_be_external(tmp_path):
    with pytest.raises(ValueError):m.archive(tmp_path,tmp_path/'inner')


def test_hash_change_detected(tmp_path):
    r=fixture(tmp_path/'repo');o=tmp_path/'out';m.prepare(r,o,{})
    (o/'支撑材料工作区/程序与复现'/m.P3/'strategy_task.py').write_text('MODIFIED = True\n',encoding='utf-8')
    with pytest.raises(RuntimeError):m.final_check_and_pack(r,o)
    assert any('支撑文件缺失或变化' in i for i in json.loads((o/'阻塞项.json').read_text(encoding='utf-8')))
