"""Offline-only coverage and in-transit action safety regression tests."""
from pathlib import Path
import math
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent
_names = ('strategy', 'strategy_fast', 'strategy_v8', 'strategy_night', 'strategy_transit')
_saved = {name: sys.modules.pop(name) for name in _names if name in sys.modules}
_path = str(ROOT.parent / '第三问/v10')
sys.path.insert(0, _path)
try:
    from strategy import Action, State
    from strategy_night import HopP3
    from strategy_transit import ResidualP3, TransitP3, TransitResidualP3
finally:
    sys.path.remove(_path)
    for _name in _names:
        sys.modules.pop(_name, None)
    sys.modules.update(_saved)


@pytest.mark.parametrize('witness', [(0., 0.), (1800., 0.), (-1800., 0.),
                                    (0., 1800.), (0., -1800.), (1200., 1200.),
                                    (150., -700.), (30., 30.), (-30., -30.)])
def test_consistent_source_is_never_excluded(witness):
    policy = ResidualP3()
    positions = [(float(x), float(y)) for x in range(-2000, 2001, 500)
                 for y in range(-2000, 2001, 500)
                 if math.dist((x, y), witness) > 1000.]
    for pos in positions:
        policy.on_measure(State(pos=pos, ch=1), 1, 'no_signal', None)
    assert 1 not in policy.absent
    witness_cells = np.all(np.abs(policy.coverage.points - witness) <= 30.000001, axis=1)
    assert witness_cells.any()
    assert np.any(policy.coverage.remaining[1] & witness_cells)
    assert policy.coverage.remaining[2].all()


def test_union_exclusion_removes_more_than_individual_cell_disks():
    policy = ResidualP3()
    old = HopP3()
    positions = [(0., 0.)] + [(1150*math.cos(k*math.pi/3), 1150*math.sin(k*math.pi/3))
                              for k in range(5)]
    for pos in positions:
        state = State(pos=pos, ch=1)
        old.on_measure(state, 1, 'no_signal', None)
        policy.on_measure(state, 1, 'no_signal', None)
    assert 1 not in old.absent and 1 not in policy.absent
    assert np.count_nonzero(policy.coverage.remaining[1]) < np.count_nonzero(old.coverage.remaining[1])
    assert np.all(~policy.coverage.remaining[1] | old.coverage.remaining[1])


def test_residual_mask_cache_is_not_modified_by_channel_updates():
    policy = ResidualP3()
    positions = ((0., 0.), (1200., 0.), (0., 1200.))
    mask = policy._residual_mask(positions).copy()
    for pos in positions:
        policy.on_measure(State(pos=pos, ch=1), 1, 'no_signal', None)
    np.testing.assert_array_equal(mask, policy._residual_mask(positions))


def test_grid_geometry_matches_parent_coverage():
    policy = ResidualP3()
    assert abs(policy.coverage.cover_radius - (1000 - 60/math.sqrt(2) - 1e-6)) < 1e-9


def test_in_transit_scan_resumes_original_action(monkeypatch):
    action = Action('clear', (1600., 0.), 20)
    monkeypatch.setattr(HopP3, 'step', lambda self, state: action)
    policy = TransitP3()
    first = policy.step(State(pos=(-1600., 0.), ch=1))
    assert first.kind == 'measure'
    assert first.pos[1] == 0.
    assert -1600. < first.pos[0] < 1600.
    assert math.dist((-1600., 0.), first.pos) + math.dist(first.pos, action.pos) == 3200.
    state = State(pos=first.pos, ch=first.ch)
    for _ in range(21):
        next_action = policy.step(state)
        if next_action is action:
            break
        assert next_action.kind == 'measure' and next_action.pos == first.pos
        state.ch = next_action.ch
    else:
        pytest.fail('transit scan did not resume its pending action')
    assert policy._transit_pending is None
    assert len(policy.transit_stops) == 1


def test_pending_scan_skips_discovered_channels():
    policy = TransitP3()
    action = Action('clear', (1600., 0.), 20)
    policy._transit_pending = action
    policy._transit_channels = [1, 2, 3]
    policy.tracks[1] = object()
    policy.absent.add(2)
    policy.cleared.add(3)
    assert policy.step(State(pos=(0., 0.), ch=1)) is action


def test_combined_candidate_initializes_both_observation_layers():
    policy = TransitResidualP3()
    assert policy._transit_pending is None
    assert policy._residual_mask is not None
    assert policy.diagnostics()['residual_updates'] == 0
