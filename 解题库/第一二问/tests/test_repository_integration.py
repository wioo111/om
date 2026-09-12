"""Exercise actual repository entry points from a different working directory."""
from pathlib import Path
import json
import os
import subprocess
import sys
import pytest

MODULE=Path(__file__).resolve().parents[1]
REPO=MODULE.parents[1]

@pytest.mark.parametrize('entry,args',[
    ('run.py',['q1','--input',str(MODULE/'examples/q1_observations.json')]),
    ('run.py',['q2','--s1','0','0','--bearing','0']),
    ('run.py',['q2','--s1','2100','400','--bearing','190','--side','-1']),
    ('解题库/第一问/run.py',['--input',str(MODULE/'examples/q1_observations.json')]),
    ('解题库/第二问/run.py',['--s1','0','0','--bearing','0']),
])
def test_entry_from_unrelated_directory(entry,args,tmp_path):
    target=tmp_path/'result.json'
    env=dict(os.environ,Q12_RECORDED_CHILD='1',PYTHONIOENCODING='utf-8')
    completed=subprocess.run([sys.executable,str(REPO/entry),*args,'--out',str(target)],cwd=tmp_path,
                             env=env,capture_output=True,text=True,encoding='utf-8')
    assert completed.returncode==0,completed.stderr
    data=json.loads(target.read_text(encoding='utf-8'))
    if 'S2' in data:
        assert data['minimum_reception_disk_margin_m']>0
        assert abs(data['theoretical_worst_diameter_m']-110.969318572838)<1e-8
    else:assert data['status']=='bounded' and data['D']>0
