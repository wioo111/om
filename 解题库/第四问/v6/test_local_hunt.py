"""Focused component tests; no confirmation-set or official simulator calls."""
import copy
import math

import pytest
from shapely.geometry import MultiPoint, Point

from local_hunt import LocalHuntPlanner
from strategy import State
from strategy_p4 import Track, _localize


def _track(points, target=(900.0, 200.0)):
    records = [(p, math.degrees(math.atan2(target[1]-p[1], target[0]-p[0])) % 360)
               for p in points]
    track = Track(records=records)
    geometry = _localize(records)
    if geometry:
        track.poly = geometry['poly']
        track.center = geometry['mec_center']
        track.radius = geometry['mec_radius']
    return track


def test_no_signal_does_not_mutate_positive_information():
    planner = LocalHuntPlanner()
    track = _track([(0.0, 0.0)])
    before = copy.deepcopy(track)
    state = State((0.0, 0.0), 1)
    positions = []
    while (action := planner.next_probe(track, state, 1)) is not None:
        positions.append(action.pos)
        state.pos = action.pos  # simulate a miss, leaving records untouched
    assert track == before
    assert len(positions) == len(set(positions)) == 6
    assert planner.last_reason[1] == 'distinct_candidates_exhausted'


def test_fixed_repeated_point_is_not_a_second_positive_position():
    planner = LocalHuntPlanner()
    track = Track(records=[((0.0, 0.0), 0.0)] * 10)
    planner.next_probe(track, State((0.0, 0.0), 1), 1)
    assert planner.events['speculative_first_pair'] == 1
    assert not planner.events['safe_convex_probe']


def test_two_positive_positions_only_use_safe_convex_combinations():
    track = _track([(0.0, 0.0), (600.0, 180.0), (300.0, -100.0)])
    polygon = MultiPoint([p for p, _ in track.records]).convex_hull
    before = copy.deepcopy(track)
    planner = LocalHuntPlanner(max_probes=8)
    state = State((600.0, 180.0), 1)
    issued = []
    for _ in range(8):
        action = planner.next_probe(track, state, 1)
        assert action is not None
        assert polygon.buffer(1e-8).covers(Point(action.pos))
        assert all(math.dist(action.pos, pos) > 0.5 for pos, _ in track.records)
        state.pos = action.pos
        issued.append(action.pos)
    assert len(set(issued)) == 8
    assert planner.next_probe(track, state, 1) is None
    assert planner.last_reason[1] == 'probe_budget_exhausted'
    assert track == before


def test_single_positive_misses_then_positive_changes_to_safe_mode():
    track = _track([(0.0, 0.0)])
    planner = LocalHuntPlanner()
    state = State((0.0, 0.0), 2)
    first = planner.next_probe(track, state, 7)
    state.pos = first.pos
    track = _track([(0.0, 0.0), first.pos])
    second = planner.next_probe(track, state, 7)
    line = MultiPoint([p for p, _ in track.records]).convex_hull
    assert second.ch == 7 and second.kind == 'measure'
    assert line.buffer(1e-7).covers(Point(second.pos))
    assert planner.last_reason[7] == 'safe_convex_probe'


def test_channel_budgets_are_independent_and_track_history_is_respected():
    track = _track([(0.0, 0.0)])
    planner = LocalHuntPlanner(max_probes=1)
    state = State((0.0, 0.0), 1)
    action = planner.next_probe(track, state, 1)
    assert planner.next_probe(track, state, 1) is None
    assert planner.next_probe(track, state, 2) is not None
    other = LocalHuntPlanner()
    track.probe_history.append(action.pos)
    assert other.next_probe(track, state, 1).pos != action.pos


def test_cost_accounts_for_measure_switch_and_clear():
    track = _track([(0.0, 0.0), (600.0, 180.0)])
    planner = LocalHuntPlanner()
    point = (300.0, 90.0)
    same = planner._score(point, track, State(point, 1), 1)
    different = planner._score(point, track, State(point, 2), 1)
    assert same >= 10.0
    assert different == pytest.approx(same + 1.0)


def test_bad_budgets_are_rejected_and_near_defers_to_caller():
    for count in (0, 9):
        with pytest.raises(ValueError):
            LocalHuntPlanner(count)
    planner = LocalHuntPlanner()
    assert planner.next_probe(Track(), State((0.0, 0.0), 1), 1) is None
    track = Track(records=[((0.0, 0.0), 0.0)], near=(0.0, 0.0))
    assert planner.next_probe(track, State((0.0, 0.0), 1), 1) is None
