"""Read-only import/geometry smoke and hash check of Q3/Q4; writes only Q12 audit."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]

def snapshot():
    return {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ('第三问','第四问') for p in (REPO/'解题库'/name).rglob('*') if p.is_file()}

before=snapshot()
records=[]
for name,version,entry in [('第三问','v10','strategy_v10'),('第四问','v6','strategy_p4')]:
    directory=REPO/'解题库'/name/version
    code=(f"import sys;sys.path.insert(0,{str(directory)!r});import {entry};import strategy;"
          "assert strategy._SOURCE=='inline';"
          "assert callable(strategy.p1.solve_problem_1);"
          "print('DEPENDENCY_IMPORT_OK',strategy._FIRST_FILE)")
    cmd=[sys.executable,'-B','-c',code]
    proc=subprocess.run(cmd,cwd=REPO,capture_output=True,text=True,encoding='utf-8',
                        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'))
    records.append(dict(command=cmd,exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
after=snapshot()
diff=subprocess.run(['git','diff','--exit-code','HEAD','--','解题库/第三问','解题库/第四问'],cwd=REPO,capture_output=True)
result=dict(time=datetime.now(timezone.utc).isoformat(),unchanged=before==after,
            tracked_diff_exit=diff.returncode,files_before=before,files_after=after,commands=records)
(ROOT/'audit/protected_questions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert before==after and diff.returncode==0 and all(r['exit_code']==0 for r in records),result
print(f'Q3/Q4: {len(before)} files unchanged; both actual dependency entries imported successfully')
