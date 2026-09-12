"""Fresh per-command evidence, including failures and exact artifact hashes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent

def hashes(paths):
    return {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths)) if p.is_file()}

def sources():
    return hashes([*ROOT.glob('*.py'), *ROOT.glob('src/**/*.py'),
                   *ROOT.glob('tests/*.py'), *ROOT.glob('examples/*.json'),
                   ROOT/'paper/正文模板.md', ROOT/'pyproject.toml'])

def products():
    return hashes([*ROOT.glob('results/*'), *ROOT.glob('figures/*'),
                   ROOT/'proofs/global_certificate.json', *ROOT.glob('paper/*'),
                   ROOT/'logs/pytest.xml'])

def recorded_command():
    """Outer process streams the child output and saves exit status even on failure."""
    command = sys.argv[1] if len(sys.argv) > 1 else 'help'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    folder = ROOT/'logs'/'runs'/run_id
    folder.mkdir(parents=True)
    before = sources()
    args = [sys.executable, '-X', 'utf8', str(ROOT/'run.py'), *sys.argv[1:]]
    env = dict(os.environ, Q12_RECORDED_CHILD='1', PYTHONIOENCODING='utf-8')
    env.setdefault('MPLBACKEND', 'Agg')
    started = datetime.now(timezone.utc).isoformat()
    with (folder/'output.txt').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen(args, cwd=Path.cwd(), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        for line in proc.stdout:
            log.write(line); log.flush()
            print(line, end='', flush=True)
        code = proc.wait()
    record = dict(run_id=run_id, command=command, argv=args, cwd=str(Path.cwd()),
                  started=started, finished=datetime.now(timezone.utc).isoformat(),
                  exit_code=code, sources=before, sources_unchanged=before == sources(),
                  artifacts=products(), log=str((folder/'output.txt').relative_to(ROOT)))
    (folder/'record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'audit').mkdir(exist_ok=True)
    (ROOT/'audit'/f'latest_{command}.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return code

def require_fresh(command, artifact_prefixes=()):
    record = json.loads((ROOT/'audit'/f'latest_{command}.json').read_text(encoding='utf-8'))
    if record['exit_code'] != 0 or not record['sources_unchanged']:
        raise RuntimeError(f'{command}: unsuccessful or concurrent source change')
    # A typesetting-only fix does not invalidate a mathematical proof or a CSV.
    # Validate the actual source dependencies of each stage, not unrelated builders.
    stage_files={'prove':{'run.py','evidence.py'},
                 'test':{'run.py','evidence.py','pyproject.toml'},
                 'experiments':{'run.py','evidence.py','experiments.py'},
                 'figures':{'run.py','evidence.py','plot_figures.py'},
                 'paper':{'run.py','evidence.py','build_paper.py','manuscript.py','paper/正文模板.md'}}
    def relevant(path):
        return (path.startswith('src/') or path in stage_files.get(command,set()) or
                command=='test' and path.startswith('tests/') or
                command in ('test','experiments') and path.startswith('examples/'))
    current_sources=sources()
    if {p:h for p,h in record['sources'].items() if relevant(p)} != {p:h for p,h in current_sources.items() if relevant(p)}:
        raise RuntimeError(f'{command}: source changed since execution; rerun required')
    current = products()
    for path, digest in record['artifacts'].items():
        if any(path.startswith(prefix) for prefix in artifact_prefixes) and current.get(path) != digest:
            raise RuntimeError(f'{command}: stale artifact {path}')
    return record
