"""The route candidate must execute from its own dependency bundle and any cwd."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


RUNTIME_FILES = (
    'strategy.py', 'problem1_v4_inline.py', 'strategy_p4.py', 'strategy_fast.py',
    'strategy_cost.py', 'strategy_finish.py', 'strategy_hunt.py', 'local_hunt.py',
    'discovery_mesh.py', 'discovery_rings.py', 'discovery_compact.py',
    'discovery_coverage.py', 'discovery_prune.py', 'strategy_route.py',
    'strategy_route_probe.py', 'robot_iter.py', 'mock_simulator_p4.py',
    'run_route_local.py',
)


def test_two_separate_bundles_and_unrelated_working_directories(tmp_path):
    source = Path(__file__).resolve().parent
    frozen = {name: (source / name).read_bytes() for name in RUNTIME_FILES}
    outcomes = []
    for index in range(2):
        bundle, work = tmp_path / f'bundle_{index}', tmp_path / f'unrelated_{index}'
        bundle.mkdir()
        work.mkdir()
        for name, content in frozen.items():
            (bundle / name).write_bytes(content)
        output = work / 'result.json'
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        run = subprocess.run(
            [sys.executable, '-X', 'utf8', str(bundle / 'run_route_local.py'),
             '--strategy', 'RouteProbeP4', '--N', '10', '--seed', '993302',
             '--error-mode', 'fixed', '--output', str(output)],
            cwd=work, env=environment, capture_output=True, encoding='utf-8', timeout=120,
        )
        assert run.returncode == 0, run.stderr + run.stdout[-4000:]
        result = json.loads(output.read_text(encoding='utf-8'))
        summary = result['summary']
        assert summary['accepted_run'] and summary['normal_stop'] and summary['full_clear']
        assert summary['accounting_ok'] and summary['cleared'] == 10
        assert summary['loaded']['actual_class'] == 'RouteProbeP4'
        assert Path(summary['loaded']['source']) == bundle / 'strategy_route_probe.py'
        assert summary['loaded']['sha256'] == hashlib.sha256(frozen['strategy_route_probe.py']).hexdigest()
        outcomes.append((summary['virtual_time_s'], summary['time_breakdown'], result['result']['log']))
    assert outcomes[0] == outcomes[1]
