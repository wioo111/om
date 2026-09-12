"""Save one offline-only acceptance invocation and real subprocess exit codes."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    folder = ROOT / 'results' / ('p3_night_acceptance_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(exist_ok=False)
    command = [sys.executable, '-m', 'pytest',
               str(ROOT / 'test_p3_night.py'), str(ROOT / 'test_practice_safety.py'),
               str(ROOT / 'test_protocol.py'), str(ROOT / 'test_one_click.py'),
               '-q', '--junitxml=' + str(folder / 'tests.xml')]
    started = datetime.now(timezone.utc).isoformat()
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    with (folder / 'console.txt').open('w', encoding='utf-8') as log:
        completed = subprocess.run(command, cwd=REPO, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=90)
    files = [ROOT / 'candidates.py', ROOT / 'run_practice.py', ROOT / 'test_p3_night.py',
             ROOT.parent / '第三问/v10/strategy_night.py']
    record = dict(command=command, cwd=str(REPO), exit_code=completed.returncode,
                  started=started, finished=datetime.now(timezone.utc).isoformat(),
                  scope='offline pytest, synthetic inputs and launcher Check; no simulator requests',
                  code_sha256={str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
    (folder / 'execution.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print((folder / 'console.txt').read_text(encoding='utf-8'), flush=True)
    print('ACCEPTANCE_FOLDER', folder, flush=True)
    return completed.returncode


if __name__ == '__main__':
    sys.exit(main())
