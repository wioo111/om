"""Offline deployment checks; never contact or start a simulator.

Run with the configured Python: python test_p4_route_deployment.py
Each import check uses an isolated process so P3/P4 module names cannot collide.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
P4 = REPO / '解题库/第四问/v6'
SELECTION = P4 / 'route_round2/selection.json'
MARKER = 'FORMAL_DEPLOYMENT_TEST_JSON='

CHILD = r'''
from contextlib import nullcontext, redirect_stdout
import hashlib
import inspect
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

repo, operation, problem, variant = sys.argv[1:]
repo = Path(repo)
problem = int(problem)

def forbid_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'urllib.Request',
                 'http.client.connect'):
        raise AssertionError('Offline deployment test attempted network: ' + event)

sys.addaudithook(forbid_network)
sys.path.insert(0, str(repo / 'tools'))
import formal_launch as launch

args = (problem,) if variant == 'default' else (problem, variant)
module, strategy, client_type, post, run = launch.load_strategy(*args)
source = Path(inspect.getfile(type(strategy))).resolve()
result = {
    'class': type(strategy).__name__,
    'name': strategy.name,
    'source': str(source),
    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'module': str(module.resolve()),
    'driver': str(Path(inspect.getfile(run)).resolve()),
}

if operation == 'check':
    argv = ['--problem', str(problem), '--check']
    if variant != 'default':
        argv += ['--p4-strategy', variant]
    captured = io.StringIO()
    with patch.object(launch, 'execute', side_effect=AssertionError('--check called execute')), \
            redirect_stdout(captured):
        result['exit_code'] = launch.main(argv)
    result['console'] = captured.getvalue()

elif operation == 'stop_reasons':
    class DummyClient:
        def __init__(self, base_url, secret):
            self.base_url, self.secret = base_url, secret

    def no_post(*args, **kwargs):
        raise AssertionError('Mock execution attempted simulator request')

    checks = []
    for reason in ('step_limit', 'all_channels_cleared_or_covered', 'cleared_maximum_16'):
        with tempfile.TemporaryDirectory(prefix='p4_formal_stop_') as folder:
            root = Path(folder)
            fixture = root / 'fixture'
            fixture.mkdir()
            (root / 'tools').mkdir()
            def fake_run(*args, **kwargs):
                # Even a coincidental clear of all 16 cannot validate step_limit.
                return dict(cleared=16, virtual_time_s=1.0, stop_reason=reason, log=[])
            with patch.object(launch, 'REPO', root), \
                    patch.object(launch, 'ROOT', root / 'tools'), \
                    patch.object(launch, 'load_strategy', return_value=(
                        fixture, strategy, DummyClient, no_post, fake_run)), \
                    patch.object(launch, 'one_robot', return_value=nullcontext()), \
                    patch.object(launch, 'robot_id', return_value='000000000000'), \
                    redirect_stdout(io.StringIO()):
                code = launch.execute(4)
            records = list(root.glob('解题库/正式运行/results/*/execution.json'))
            assert len(records) == 1
            record = json.loads(records[0].read_text(encoding='utf-8'))
            version = json.loads(records[0].with_name('version.json').read_text(encoding='utf-8'))
            outcome = json.loads(records[0].with_name('result.json').read_text(encoding='utf-8'))
            checks.append(dict(reason=reason, code=code, record=record,
                               version=version, result=outcome))
    result['stop_checks'] = checks

print('FORMAL_DEPLOYMENT_TEST_JSON=' + json.dumps(result, ensure_ascii=False))
'''


class FormalRouteDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = json.loads(SELECTION.read_text(encoding='utf-8'))

    def isolated(self, operation='factory', problem=4, variant='default', cwd=None):
        proc = subprocess.run(
            [sys.executable, '-I', '-X', 'utf8', '-c', CHILD,
             str(REPO), operation, str(problem), variant],
            cwd=cwd or REPO, capture_output=True, encoding='utf-8', timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + '\n' + proc.stderr)
        rows = [line[len(MARKER):] for line in proc.stdout.splitlines()
                if line.startswith(MARKER)]
        self.assertEqual(len(rows), 1, proc.stdout)
        return json.loads(rows[0])

    def test_default_factory_matches_frozen_selection_from_independent_cwds(self):
        actual = self.isolated()
        with tempfile.TemporaryDirectory(prefix='p4_formal_cwd_') as folder:
            independent = self.isolated(cwd=folder)
        self.assertEqual(actual, independent)
        self.assertEqual(actual['class'], 'RouteProbeP4')
        self.assertEqual(actual['class'], self.selection['selected_class'])
        self.assertEqual(Path(actual['source']), P4 / 'strategy_route_probe.py')
        self.assertEqual(actual['sha256'], self.selection['selected_sha256'])
        self.assertEqual(Path(actual['driver']), P4 / 'robot_iter.py')
        for name, expected in self.selection['selected_dependency_sha256'].items():
            with self.subTest(dependency=name):
                self.assertEqual(hashlib.sha256((P4 / name).read_bytes()).hexdigest(), expected)

    def test_check_is_offline_and_prints_actual_class_source_and_hash(self):
        actual = self.isolated('check')
        self.assertEqual(actual['exit_code'], 0)
        for field in ('class', 'sha256'):
            self.assertIn(actual[field], actual['console'])
        source_line = next(line.removeprefix('来源：') for line in actual['console'].splitlines()
                           if line.startswith('来源：'))
        self.assertEqual((REPO / source_line).resolve(), Path(actual['source']))
        self.assertIn('未发送模拟器请求', actual['console'])

    def test_preserved_fast_factory_and_cli_rollback(self):
        actual = self.isolated('check', variant='FastP4')
        self.assertEqual(actual['exit_code'], 0)
        self.assertEqual(actual['class'], 'FastP4')
        self.assertEqual(Path(actual['source']), P4 / 'strategy_fast.py')
        self.assertEqual(actual['sha256'], self.selection['selected_dependency_sha256']['strategy_fast.py'])
        self.assertIn('class=FastP4', actual['console'])

    def test_p3_factory_and_driver_remain_in_p3(self):
        actual = self.isolated('check', problem=3)
        p3 = REPO / '解题库/第三问/v10'
        self.assertEqual(actual['class'], 'OpticalTaskP3')
        self.assertEqual(Path(actual['source']), p3 / 'strategy_task.py')
        self.assertEqual(Path(actual['driver']), p3 / 'robot_iter.py')
        self.assertEqual(actual['exit_code'], 0)

    def test_step_limit_is_nonzero_even_with_16_clears(self):
        actual = self.isolated('stop_reasons')
        for check in actual['stop_checks']:
            with self.subTest(reason=check['reason']):
                normal = check['reason'] != 'step_limit'
                self.assertEqual(check['code'], 0 if normal else 1)
                self.assertEqual(check['record']['exit_code'], check['code'])
                self.assertEqual(check['record']['normal_stop'], normal)
                for artifact in ('record', 'version', 'result'):
                    self.assertEqual(check[artifact]['actual_class'], 'RouteProbeP4')
                    self.assertEqual(check[artifact]['strategy_sha256'], self.selection['selected_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
