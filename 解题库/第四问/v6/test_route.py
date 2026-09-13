import copy

import pytest

from strategy import State
from strategy_p4 import CHANNELS, Track
from strategy_route import RouteAwareP4, joint_path, path_length


def test_joint_path_keeps_every_required_visit_once():
    stations = [(0., 0.), (100., 0.), (100., 100.), (0., 100.)]
    tasks = [(3, (50., 1.)), (7, (99., 50.))]
    route = joint_path(stations, tasks, (0., 0.))
    assert len(route) == 6
    assert {n[1] for n in route if n[0] == 'scan'} == set(range(4))
    assert {n[1] for n in route if n[0] == 'clear'} == {3, 7}
    assert route == joint_path(stations, tasks, (0., 0.))
    naive = [('scan', i, p) for i, p in enumerate(stations)] + [('clear', ch, p) for ch, p in tasks]
    assert path_length(route, (0., 0.)) <= path_length(naive, (0., 0.))


def test_near_clear_preserves_scan_queue_and_pending_points():
    strategy = RouteAwareP4()
    state = State((0., 0.), 1)
    action = strategy.step(state)
    state.pos = action.pos
    strategy.on_measure(state, action.ch, 'near', None)
    before = (strategy.current_station, strategy.discovery_channel_index,
              strategy._station_channels[:], strategy.pending_stations[:], strategy.work_index)
    clear = strategy.step(state)
    assert clear.kind == 'clear' and clear.pos == state.pos
    strategy.on_clear(state, clear.ch, True)
    assert before == (strategy.current_station, strategy.discovery_channel_index,
                      strategy._station_channels[:], strategy.pending_stations[:], strategy.work_index)
    follow = strategy.step(state)
    assert follow.kind == 'measure' and follow.ch != clear.ch and follow.pos == action.pos


def test_pending_plan_cannot_prove_completed_discovery():
    strategy = RouteAwareP4()
    strategy.pending_stations.clear()
    strategy.completed_stations = set(strategy.core_stations)
    with pytest.raises(RuntimeError, match='missing_actual'):
        strategy.step(State((0., 0.), 1))
    assert not strategy.done and not strategy.absent


def test_fifteen_is_not_sixteen_even_after_clear():
    strategy = RouteAwareP4()
    state = State((0., 0.), 1)
    for ch in range(1, 16):
        strategy.on_measure(state, ch, 'near', None)
        strategy.on_clear(state, ch, True)
    assert len(strategy.ever_observed_channels) == 15
    assert strategy._needs_sample(16)
    strategy.pending_stations.clear()
    with pytest.raises(RuntimeError, match='missing_actual'):
        strategy.step(state)


def test_sixteen_positive_sources_allow_no_unknown_station_visits():
    strategy = RouteAwareP4()
    state = State((0., 0.), 1)
    for ch in range(1, 17):
        strategy.on_measure(state, ch, 'near', None)
        strategy.on_clear(state, ch, True)
    assert strategy.step(state).kind == 'done'
    assert len(strategy.ever_observed_channels) == 16
    assert strategy.completion_reason == 'all_channels_cleared_or_covered'


def test_no_signal_does_not_crop_region():
    strategy = RouteAwareP4()
    strategy.tracks[3] = Track(records=[((0., 0.), 0.), ((100., 100.), 320.)],
                               poly=[(200., 0.), (210., 10.), (220., 0.)],
                               center=(210., 5.), radius=11.)
    before = copy.deepcopy(strategy.tracks[3])
    strategy.on_measure(State((500., 500.), 3), 3, 'no_signal', None)
    assert strategy.tracks[3] == before
