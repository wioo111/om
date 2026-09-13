"""Focused zero-detour probe tests; no confirmation or scenario batch run."""
import copy
import math

import pytest

from strategy import Action, State
from strategy_p4 import Track
from strategy_route import RouteAwareP4
from strategy_route_probe import RouteProbeP4


def setup_segment():
    strategy = RouteProbeP4(adaptive_scan=False, scan_investments=0)
    strategy.tracks[7] = Track(records=[((0.0, 0.0), 0.0)])
    strategy.ever_observed_channels.add(7)
    strategy.current_station = (0.0, 700.0)
    strategy._station_channels = [1, 2, 3]
    strategy.discovery_channel_index = 0
    return strategy, State((0.0, 0.0), 1)


def scan_state(strategy):
    return copy.deepcopy((strategy.current_station, strategy.discovery_station_index,
                          strategy.discovery_channel_index, strategy._station_channels,
                          strategy.pending_stations, strategy.completed_stations, strategy.work_index))


def test_probe_has_zero_added_distance_and_resumes_exact_held_action():
    strategy, state = setup_segment()
    probe = strategy.step(state)
    assert probe.kind == 'measure' and probe.ch == 7
    held = copy.deepcopy(strategy._probe_held_action)
    queues = scan_state(strategy)
    assert held == Action('measure', (0.0, 700.0), 1)
    assert math.dist(state.pos, probe.pos) + math.dist(probe.pos, held.pos) == pytest.approx(math.dist(state.pos, held.pos), abs=1e-9)
    state.pos, state.ch = probe.pos, probe.ch
    strategy.on_measure(state, probe.ch, 'no_signal', None)
    assert strategy.step(state) == held
    assert scan_state(strategy) == queues
    assert strategy._probe_held_action is None
    assert strategy.probe_events['held_scan_resumed'] == 1


def test_near_clear_and_then_resume_preserves_parent_queue():
    strategy, state = setup_segment()
    probe = strategy.step(state)
    held, queues = copy.deepcopy(strategy._probe_held_action), scan_state(strategy)
    start = state.pos
    state.pos, state.ch = probe.pos, probe.ch
    strategy.on_measure(state, probe.ch, 'near', None)
    clear = strategy.step(state)
    assert clear == Action('clear', probe.pos, probe.ch)
    assert scan_state(strategy) == queues
    strategy.on_clear(state, clear.ch, True)
    assert scan_state(strategy) == queues
    assert strategy.step(state) == held
    assert scan_state(strategy) == queues
    assert math.dist(start, clear.pos) + math.dist(clear.pos, held.pos) == pytest.approx(math.dist(start, held.pos), abs=1e-9)
    assert probe.ch in strategy.cleared
    assert not strategy._consider_scan_stop


def test_no_signal_does_not_modify_track_or_known_channel_count():
    strategy, state = setup_segment()
    strategy.tracks[7].poly = [(1.0, 1.0), (2.0, 1.0), (1.0, 2.0)]
    before = copy.deepcopy(strategy.tracks[7])
    known = strategy.ever_observed_channels.copy()
    probe = strategy.step(state)
    state.pos, state.ch = probe.pos, probe.ch
    strategy.on_measure(state, probe.ch, 'no_signal', None)
    assert strategy.tracks[7] == before
    assert strategy.ever_observed_channels == known


def test_identical_fixed_point_is_not_independent_information():
    strategy, state = setup_segment()
    before = len(strategy.tracks[7].records)
    strategy.on_measure(state, 7, 'direction', 0.3)
    assert len(strategy.tracks[7].records) == before
    assert strategy._single_positive(strategy.tracks[7]) == ((0.0, 0.0), 0.0)


def test_at_most_two_probes_per_channel_and_distinct_positions():
    strategy, state = setup_segment()
    first = strategy.step(state)
    state.pos, state.ch = first.pos, first.ch
    strategy.on_measure(state, first.ch, 'no_signal', None)
    strategy.step(state)  # restore held scan
    state.pos, state.ch = (0.0, 0.0), 1
    strategy.current_station = (0.0, 800.0)
    strategy._station_channels = [1, 2]
    strategy.discovery_channel_index = 0
    second = strategy.step(state)
    assert second.ch == 7 and second.pos != first.pos
    state.pos, state.ch = second.pos, second.ch
    strategy.on_measure(state, second.ch, 'no_signal', None)
    strategy.step(state)
    state.pos, state.ch = (0.0, 0.0), 1
    strategy.current_station = (0.0, 900.0)
    strategy._station_channels = [1, 2]
    strategy.discovery_channel_index = 0
    assert strategy.step(state) == Action('measure', (0.0, 900.0), 1)
    assert len(strategy.probe_positions[7]) == 2


def test_collinear_or_short_travel_does_not_insert_without_value():
    strategy, state = setup_segment()
    strategy.current_station = (700.0, 0.0)
    assert strategy.step(state) == Action('measure', (700.0, 0.0), 1)
    assert not strategy.probe_history
    strategy.current_station = (0.0, 20.0)
    strategy.discovery_channel_index = 0
    assert strategy.step(state) == Action('measure', (0.0, 20.0), 1)
    assert not strategy.probe_history


def test_probe_cost_includes_detection_and_outbound_return_channel_switches():
    strategy, state = setup_segment()
    probe = strategy.step(state)
    state.pos, state.ch = probe.pos, probe.ch
    strategy.on_measure(state, probe.ch, 'direction', 315.0)
    assert strategy.probe_added_cost == dict(measure_time_s=5.0, switch_time_s=2.0, move_time_s=0.0)
    assert strategy.step(state) == Action('measure', (0.0, 700.0), 1)
    assert len(strategy.tracks[7].records) == 2


def test_switch_off_matches_parent_actions():
    candidate, state = setup_segment()
    candidate.probe_enabled = False
    baseline = RouteAwareP4(adaptive_scan=False, scan_investments=0)
    baseline.tracks = copy.deepcopy(candidate.tracks)
    baseline.ever_observed_channels = candidate.ever_observed_channels.copy()
    baseline.current_station = candidate.current_station
    baseline._station_channels = candidate._station_channels[:]
    for _ in range(3):
        assert candidate.step(state) == baseline.step(copy.deepcopy(state))
        state.pos = candidate.current_station
    assert not candidate.probe_history


def test_different_positive_positions_are_not_single_bearing_candidate():
    strategy, state = setup_segment()
    strategy.tracks[7].records.append(((200.0, 100.0), 0.0))
    assert strategy.step(state) == Action('measure', (0.0, 700.0), 1)
    assert not strategy.probe_history


def test_missing_callback_cannot_consume_parent_action():
    strategy, state = setup_segment()
    strategy.step(state)
    held = strategy._probe_held_action
    with pytest.raises(RuntimeError, match='measurement_result_missing'):
        strategy.step(state)
    assert strategy._probe_held_action is held


def test_off_segment_resume_is_rejected():
    strategy, state = setup_segment()
    probe = strategy.step(state)
    state.pos, state.ch = probe.pos, probe.ch
    strategy.on_measure(state, probe.ch, 'no_signal', None)
    state.pos = (100.0, state.pos[1])
    with pytest.raises(RuntimeError, match='resume_would_add_movement'):
        strategy.step(state)
