"""Offline-only P3 regression checks; isolate legacy P3/P4 module names."""
from pathlib import Path
import json
import math
import subprocess
import sys

import numpy as np
import pytest
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent
_module_names = ('strategy', 'strategy_fast', 'strategy_v8', 'strategy_night')
_saved = {name: sys.modules.pop(name) for name in _module_names if name in sys.modules}
_module_path = str(ROOT.parent / '第三问/v10')
sys.path.insert(0, _module_path)
try:
    from strategy import State
    from strategy_fast import FastScanP3
    from strategy_night import (CachedScanP3, CoverP3, HopP3, RouteP3,
                                OUTER_TARGET, polygon_coverage_certificate)
    from strategy_v8 import Track, distance
finally:
    sys.path.remove(_module_path)
    for _name in _module_names:
        sys.modules.pop(_name, None)
    sys.modules.update(_saved)


def ring(radius):
    return [(radius * math.cos(k * math.pi / 3),
             radius * math.sin(k * math.pi / 3)) for k in range(6)]


@pytest.mark.parametrize('positions', [[], [(0., 0.)], ring(1500.)])
def test_incomplete_coverage_never_certified(positions):
    # The ring covers the entire boundary but leaves a central hole.
    assert not polygon_coverage_certificate(positions)


def test_certificate_covers_interior_and_boundary():
    assert polygon_coverage_certificate([(0., 0.)] + ring(1200.))
    for k in range(1000):
        angle = 2 * math.pi * k / 1000
        assert OUTER_TARGET.covers(Point(1800 * math.cos(angle), 1800 * math.sin(angle)))


def test_unknown_channel_can_finish_without_whole_grid_overcoverage():
    policy = CoverP3()
    # 1150m leaves whole-cell remnants, although the continuous disk is covered.
    for pos in [(0., 0.)] + ring(1150.):
        policy.on_measure(State(pos=pos, ch=1), 1, 'no_signal', None)
    assert 1 in policy.absent
    assert 1 in policy.coverage_certificates
    assert 2 not in policy.absent
    assert policy.negative_positions[2] == []
    assert polygon_coverage_certificate(policy.coverage_certificates[1])


def test_known_channel_not_marked_absent_by_coverage():
    policy = CoverP3()
    policy.tracks[1] = Track()
    # A deliberately inconsistent observation sequence must not silently discard a known source.
    for pos in [(0., 0.)] + ring(1200.):
        policy.on_measure(State(pos=pos, ch=1), 1, 'no_signal', None)
    assert 1 not in policy.absent
    assert 1 not in policy.coverage_certificates
    assert 1 in policy.tracks


@pytest.mark.parametrize('witness', [(0., 0.), (1800., 0.), (150., -700.)])
def test_consistent_possible_source_prevents_certificate(witness):
    positions = [(x, y) for x in range(-2000, 2001, 500)
                 for y in range(-2000, 2001, 500)
                 if math.hypot(x - witness[0], y - witness[1]) > 1000.]
    assert not polygon_coverage_certificate(positions)


def test_cache_is_geometry_only_not_channel_state():
    base, cached = FastScanP3(), CachedScanP3()
    for pos in [(0., 0.), (1000., 50.), (-1800., 1800.), (0., 0.)]:
        first = cached.coverage.covered_at(pos).copy()
        np.testing.assert_array_equal(base.coverage.covered_at(pos), first)
        cached.coverage.exclude(1, pos)
        np.testing.assert_array_equal(first, cached.coverage.covered_at(pos))
    assert cached._cached_mask.cache_info().hits > 0
    assert cached.coverage.remaining[2].all()


def test_cache_has_bounded_memory():
    policy = CachedScanP3()
    for k in range(2060):
        policy.coverage.covered_at((float(k), 0.))
    assert policy._cached_mask.cache_info().currsize == 2048


def test_hop_keeps_search_and_failure_safety_parameters():
    base, policy = FastScanP3(), HopP3()
    assert policy.first_hop == 500.
    assert policy.lateral == 100.
    assert policy.probe_radius == base.probe_radius
    assert policy.coverage.cover_radius == base.coverage.cover_radius
    assert policy.cleared == policy.absent == set()


def test_route_relocation_keeps_all_targets_and_reduces_planned_length():
    nodes = [(i, (float((i * 197) % 1900), float((i * 521) % 2100))) for i in range(12)]
    start = (0., 0.)
    before, after = FastScanP3._route(start, nodes), RouteP3._route(start, nodes)
    def cost(route):
        points = [start] + [node[1] for node in route]
        return sum(distance(a, b) for a, b in zip(points, points[1:]))
    assert sorted(before) == sorted(after) == nodes
    assert cost(after) <= cost(before) + 1e-6


@pytest.mark.parametrize('seed', range(940001, 940015))
def test_frozen_cache_ablation_has_identical_actions(seed):
    folder = ROOT / 'results/p3_night_dev01/runs'
    base = json.loads((folder / f'{seed}_scan.json').read_text(encoding='utf-8'))
    cached = json.loads((folder / f'{seed}_cache.json').read_text(encoding='utf-8'))
    assert base['actions'] == cached['actions']
    assert base['summary']['full_clear'] and cached['summary']['full_clear']


@pytest.mark.parametrize('outside', [False, True])
def test_selected_candidate_entry_offline(tmp_path, outside):
    code = f'''
import sys
sys.path[:0] = {[_module_path, str(ROOT)]!r}
from candidates import make_candidate
from mock_simulator import MockSimulator
from robot_iter import run_with_sim_strategy
policy = make_candidate(3)
assert policy.name == 'OpticalTaskP3'
sim = MockSimulator(seed=980001, N=10, error_mode='edge')
result = run_with_sim_strategy(policy, sim, max_steps=8000)
assert result['cleared'] == 10
assert result['coverage_complete']
assert policy.diagnostics()['mask_cache_hits'] > 0
print('P3_ENTRY_OFFLINE_PASS', policy.name, result['virtual_time_s'])
'''
    result = subprocess.run([sys.executable, '-c', code],
                            cwd=tmp_path if outside else ROOT.parents[1],
                            capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'P3_ENTRY_OFFLINE_PASS OpticalTaskP3' in result.stdout
