"""Hunt integration invariants and two complete isolated-directory runs."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from strategy import Action, State
from strategy_hunt import HuntP4
from strategy_p4 import CHANNELS, Track


@pytest.mark.parametrize('grid', ('mesh', 'rings', 'compact'))
def test_cursor_alone_cannot_certify_unobserved_channels(grid):
    strategy = HuntP4(grid=grid)
    strategy.discovery_station_index = len(strategy.core_stations)
    with pytest.raises(RuntimeError, match='incomplete_directional_discovery_certificate'):
        strategy._next_discovery_action()
    assert not strategy.core_complete
    assert not strategy.absent


@pytest.mark.parametrize('grid', ('mesh', 'rings', 'compact'))
def test_last_unmeasured_core_point_prevents_completion(grid):
    strategy = HuntP4(grid=grid)
    for channel in CHANNELS:
        strategy.actual_scan_points[channel] = set(strategy.core_stations)
    strategy.actual_scan_points[20].remove(strategy.core_stations[-1])
    strategy.discovery_station_index = len(strategy.core_stations)
    with pytest.raises(RuntimeError, match='incomplete_directional_discovery_certificate'):
        strategy._next_discovery_action()
    assert not strategy.core_complete and 20 not in strategy.absent


@pytest.mark.parametrize('grid', ('mesh', 'rings', 'compact'))
def test_actual_full_core_allows_absence_and_normal_completion(grid):
    strategy = HuntP4(grid=grid)
    for channel in CHANNELS:
        strategy.actual_scan_points[channel] = set(strategy.core_stations)
    strategy.discovery_station_index = len(strategy.core_stations)
    assert strategy._next_discovery_action() is None
    assert strategy.core_complete
    assert strategy.absent == set(CHANNELS)
    assert strategy.step(State((0.0, 0.0), 1)).kind == 'done'
    assert strategy.completion_reason == 'all_channels_cleared_or_covered'


def test_fifteen_positive_channels_do_not_drain_unknown_channels():
    strategy = HuntP4()
    state = State((0.0, 0.0), 1)
    for channel in range(1, 16):
        strategy.on_measure(state, channel, 'direction', 0.0)
    assert len(strategy.ever_observed_channels) == 15
    assert strategy._needs_sample(16)
    assert strategy._needs_sample(20)
    assert not strategy.core_complete and not strategy.absent


def test_sixteen_positive_channels_allow_drain_after_clears():
    strategy = HuntP4()
    state = State((0.0, 0.0), 1)
    for channel in range(1, 17):
        strategy.on_measure(state, channel, 'near', None)
        action = strategy.step(state)
        assert action.kind == 'clear' and action.ch == channel
        strategy.on_clear(state, channel, True)
    assert strategy.ever_observed_channels == set(range(1, 17))
    assert strategy.cleared == set(range(1, 17))
    assert all(not strategy._needs_sample(ch) for ch in range(17, 21))
    assert strategy.step(state).kind == 'done'
    assert strategy.core_complete and strategy.absent == set(range(17, 21))
    assert strategy.completion_reason == 'all_channels_cleared_or_covered'


def test_no_signal_never_counts_as_positive_channel():
    strategy = HuntP4()
    strategy.on_measure(State((0.0, 0.0), 1), 1, 'no_signal', None)
    assert not strategy.ever_observed_channels
    assert strategy._needs_sample(1)


@pytest.mark.parametrize('half_length,expected_count,skip',
                         ((40.0, 3, True), (70.0, 4, False)))
def test_readiness_requires_at_most_three_full_cover_points(half_length, expected_count, skip):
    strategy = HuntP4()
    strategy.tracks[1] = Track(
        records=[((0.0, 100.0), 270.0), ((0.0, -100.0), 90.0)],
        poly=[(-half_length, -2.0), (half_length, -2.0),
              (half_length, 2.0), (-half_length, 2.0)],
        center=(0.0, 0.0), radius=half_length + 0.1)
    certificate = strategy._certificate(1)
    assert certificate is not None
    assert len(certificate['points']) == expected_count
    disks = unary_union([Point(p).buffer(19.99999, quad_segs=32)
                         for p in certificate['points']])
    assert Polygon(certificate['polygon']).difference(disks).is_empty
    assert strategy._needs_sample(1) is not skip
    assert strategy._needs_sample(20)
    assert 1 not in strategy.absent and 1 not in strategy.cleared


def test_invalid_readiness_polygon_does_not_retire_known_channel():
    strategy = HuntP4()
    strategy.tracks[1] = Track(
        records=[((0.0, 100.0), 270.0), ((0.0, -100.0), 90.0)],
        poly=[(0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)],
        radius=100.0)
    assert strategy._certificate(1) is None
    assert strategy._needs_sample(1)


def test_ready_channel_skips_readings_but_remains_in_final_clear_work():
    strategy = HuntP4(adapt=False)
    target = (900.0, 300.0)
    for pos in ((0.0, 0.0), (500.0, 500.0)):
        bearing = math.degrees(math.atan2(target[1] - pos[1], target[0] - pos[0])) % 360
        strategy.on_measure(State(pos, 1), 1, 'direction', bearing)
    certificate = strategy._certificate(1)
    assert certificate and len(certificate['points']) <= 3
    assert not strategy._needs_sample(1)
    first = strategy._next_discovery_action()
    assert first.kind == 'measure' and first.ch == 2
    assert 1 not in strategy._station_channels
    # All unknown-channel actual observations are now present; the known
    # channel only has its two useful positive observations and must remain.
    for channel in set(CHANNELS) - {1}:
        strategy.actual_scan_points[channel] = set(strategy.core_stations)
    strategy.discovery_station_index = len(strategy.core_stations)
    strategy.discovery_channel_index = 0
    strategy._station_channels = []
    assert strategy._next_discovery_action() is None
    assert strategy.work_channels == [1] and 1 not in strategy.absent
    state = State((0.0, 0.0), 2)
    for _ in range(3):
        action = strategy.step(state)
        assert action.kind == 'clear' and action.ch == 1
        state.pos = action.pos
        success = math.dist(action.pos, target) <= 20.0
        strategy.on_clear(state, 1, success)
        if success:
            break
    assert 1 in strategy.cleared and 1 in state.cleared
    assert strategy.step(state).kind == 'done'
    assert strategy.completion_reason == 'all_channels_cleared_or_covered'


def test_near_clear_keeps_station_queue_and_all_cursors():
    strategy = HuntP4()
    state = State((0.0, 0.0), 1)
    first = strategy.step(state)
    assert first.kind == 'measure'
    state.pos = first.pos
    strategy.on_measure(state, first.ch, 'near', None)
    before = (strategy.discovery_station_index, strategy.discovery_channel_index,
              strategy._station_channels[:], strategy.work_index)
    clear = strategy.step(state)
    assert clear.kind == 'clear' and clear.pos == state.pos and clear.ch == first.ch
    strategy.on_clear(state, clear.ch, True)
    after = (strategy.discovery_station_index, strategy.discovery_channel_index,
             strategy._station_channels[:], strategy.work_index)
    assert after == before
    second = strategy.step(state)
    assert second.kind == 'measure' and second.ch == before[2][before[1]]
    assert second.ch != first.ch and second.pos == first.pos
    assert first.ch in strategy.ever_observed_channels


def test_failed_clear_advances_and_exhaustion_reports_contradiction():
    strategy = HuntP4()
    strategy.tracks[3] = Track(records=[((0.0, 0.0), 0.0)])
    strategy._start_plan(3, dict(points=[(20.0, 0.0), (40.0, 0.0)]))
    strategy.on_clear(State((20.0, 0.0), 3), 3, False)
    assert strategy.failed_clears[3] == [(20.0, 0.0)]
    assert strategy.early_plan['points'] == [(40.0, 0.0)]
    assert not strategy.tracks[3].recovery_required
    action = strategy.step(State((20.0, 0.0), 3))
    assert action.kind == 'clear' and action.pos == (40.0, 0.0)
    with pytest.raises(RuntimeError, match='early_optical_cover_exhausted'):
        strategy.on_clear(State((40.0, 0.0), 3), 3, False)
    assert strategy.failed_clears[3] == [(20.0, 0.0), (40.0, 0.0)]
    assert 3 not in strategy.cleared and not strategy.done


def test_no_signal_preserves_feasible_polygon_and_positive_records():
    strategy = HuntP4()
    strategy.phase = 'localization'
    strategy.tracks[4] = Track(records=[((0.0, 0.0), 0.0), ((100.0, 100.0), 300.0)],
                               poly=[(200.0, 0.0), (210.0, 10.0), (220.0, 0.0)],
                               center=(210.0, 5.0), radius=11.2)
    before = copy.deepcopy(strategy.tracks[4])
    strategy.on_measure(State((1000.0, 1000.0), 4), 4, 'no_signal', None)
    track = strategy.tracks[4]
    assert track.records == before.records and track.poly == before.poly
    assert track.center == before.center and track.radius == before.radius
    assert not strategy.ever_observed_channels


def test_exhausted_hunt_returns_held_scan_without_losing_cursor():
    strategy = HuntP4(early_hunt=True)
    strategy.tracks[1] = Track(records=[((0.0, 0.0), 0.0)])
    strategy.active_hunt = 1
    strategy.local_planner.history[1] = [(float(i), 0.0) for i in range(8)]
    held = Action('measure', (700.0, 0.0), 8)
    strategy.held_action = held
    strategy.discovery_station_index = 1
    strategy.discovery_channel_index = 8
    strategy._station_channels = list(CHANNELS)
    before = (strategy.discovery_station_index, strategy.discovery_channel_index,
              strategy._station_channels[:])
    action = strategy.step(State((0.0, 0.0), 1))
    assert action == held
    assert strategy.held_action is None and strategy.active_hunt is None
    assert strategy.hunt_versions[1] == 1
    assert (strategy.discovery_station_index, strategy.discovery_channel_index,
            strategy._station_channels[:]) == before
    assert 1 not in strategy.cleared and 1 not in strategy.absent


def test_first_hunt_action_does_not_consume_held_scan_twice():
    strategy = HuntP4(early_hunt=True)
    strategy.tracks[1] = Track(records=[((0.0, 0.0), 0.0)])
    strategy.discovery_station_index = 1
    strategy._station_channels = [8, 9]
    state = State((0.0, 0.0), 1)
    action = strategy.step(state)
    assert action.kind == 'measure' and action.ch == 1
    assert strategy.held_action is not None and strategy.held_action.ch == 8
    before = strategy.discovery_channel_index
    state.pos = action.pos
    strategy.on_measure(state, 1, 'no_signal', None)
    next_action = strategy.step(state)
    assert next_action.ch == 1 and next_action.pos != action.pos
    assert strategy.discovery_channel_index == before
    assert strategy.held_action.ch == 8


def _reanchored_plan_with_only_first_station_measured():
    strategy = HuntP4(adapt=True)
    strategy.discovery_station_index = 1
    strategy.discovery_channel_index = 1
    strategy._station_channels = list(CHANNELS)
    for channel in CHANNELS:
        strategy.actual_scan_points[channel] = {strategy.core_stations[0]}
    original = strategy.discovery_stations[1]
    replacement = (original[0] + 0.000001, original[1] + 0.000001)
    strategy.held_action = Action('measure', original, 1)
    strategy._reanchor_scan(State(replacement, 1))
    assert strategy.reanchored
    assert strategy.discovery_stations[1] == replacement
    assert strategy.held_action.pos == replacement
    return strategy


def test_future_reanchor_certificate_does_not_prove_actual_completion():
    strategy = _reanchored_plan_with_only_first_station_measured()
    assert strategy.coverage_certifier.last_diagnostics['complete']
    assert not strategy.core_complete and not strategy.absent
    assert all(strategy._needs_sample(channel) for channel in CHANNELS)
    # The cached certificate contains future stations; it cannot certify the
    # actual first-station-only point set when the cursor is artificially moved.
    strategy.discovery_station_index = len(strategy.core_stations)
    strategy.discovery_channel_index = 0
    strategy._station_channels = []
    with pytest.raises(RuntimeError, match='incomplete_directional_discovery_certificate'):
        strategy._next_discovery_action()
    assert not strategy.core_complete and not strategy.absent


def test_reanchor_requires_sufficient_actual_points_for_each_unknown_channel():
    strategy = _reanchored_plan_with_only_first_station_measured()
    actual_route = set(strategy.discovery_stations[:len(strategy.core_stations)])
    for channel in CHANNELS:
        strategy.actual_scan_points[channel] = actual_route.copy()
    # Nineteen channels have the full amended route. Their evidence must never
    # compensate for the last unknown channel's missing measurements.
    strategy.actual_scan_points[20] = {strategy.core_stations[0]}
    strategy.discovery_station_index = len(strategy.core_stations)
    strategy.discovery_channel_index = 0
    strategy._station_channels = []
    with pytest.raises(RuntimeError, match='incomplete_directional_discovery_certificate'):
        strategy._next_discovery_action()
    assert not strategy.core_complete and 20 not in strategy.absent
    strategy.actual_scan_points[20] = actual_route.copy()
    assert strategy._next_discovery_action() is None
    assert strategy.core_complete and strategy.absent == set(CHANNELS)


def test_same_scene_two_independent_directories(tmp_path):
    """Identical full actions, all ten sources and normal stop are required."""
    source = Path(__file__).resolve().parent
    modules = ('strategy.py', 'problem1_v4_inline.py', 'strategy_p4.py',
               'strategy_fast.py', 'strategy_cost.py', 'strategy_finish.py',
               'strategy_hunt.py', 'discovery_mesh.py', 'discovery_rings.py', 'discovery_compact.py',
               'discovery_coverage.py', 'local_hunt.py',
               'robot_iter.py', 'mock_simulator_p4.py')
    # Freeze bytes once: concurrent development must not silently put different
    # strategy revisions into the two comparison directories.
    frozen_modules = {module: (source / module).read_bytes() for module in modules}
    code = '''import hashlib,json,random
from strategy_hunt import HuntP4
from mock_simulator_p4 import P4MockSimulator
from robot_iter import run_with_sim_strategy
random.seed(17)
result=run_with_sim_strategy(HuntP4(),P4MockSimulator(seed=993201,n_sources=10,dir_frac=.5,error_mode='fixed'))
print(json.dumps(dict(actions=len(result['log']),stop=result['stop_reason'],cleared=result['cleared'],coverage_complete=result['coverage_complete'],virtual_time_s=result['virtual_time_s'],digest=hashlib.sha256(json.dumps(result['log'],sort_keys=True).encode()).hexdigest()),sort_keys=True))
'''
    outputs = []
    for name in ('independent_a', 'independent_b'):
        directory = tmp_path / name
        directory.mkdir()
        for module, content in frozen_modules.items():
            (directory / module).write_bytes(content)
        environment = os.environ.copy()
        environment['PYTHONUTF8'] = '1'
        environment.pop('PYTHONPATH', None)
        run = subprocess.run([sys.executable, '-c', code], cwd=directory,
                             env=environment, capture_output=True, text=True,
                             encoding='utf-8', timeout=60)
        assert run.returncode == 0, run.stderr
        outputs.append(json.loads(run.stdout.splitlines()[-1]))
    assert outputs[0] == outputs[1]
    assert outputs[0]['cleared'] == 10 and outputs[0]['coverage_complete']
    assert outputs[0]['stop'] == 'all_channels_cleared_or_covered'
    assert outputs[0]['actions'] > 60
