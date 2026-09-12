"""No network: directed route accounting, observation-only planning, queue safety."""
import copy
import math
from pathlib import Path
import random
import sys

import pytest

ROOT = Path(__file__).resolve().parent
_names = ('strategy', 'strategy_fast', 'strategy_v8', 'strategy_night', 'strategy_transit', 'strategy_joint')
_saved = {name: sys.modules.pop(name) for name in _names if name in sys.modules}
_path = str(ROOT.parent / '第三问/v10')
sys.path.insert(0, _path)
try:
    from strategy import Action, State
    from strategy_transit import ResidualP3
    from strategy_joint import ActionRouteP3, SurveyP3, ProbePlanP3, PlanJointP3
finally:
    sys.path.remove(_path)
    for _name in _names:
        sys.modules.pop(_name, None)
    sys.modules.update(_saved)


@pytest.mark.parametrize('n', [2, 3, 8, 14])
def test_directed_two_opt_never_increases_its_own_route_cost(n):
    policy = ActionRouteP3()
    rng = random.Random(1900+n)
    costs = [[rng.uniform(1., 1000.) for _ in range(n)] for _ in range(n+1)]
    policy._visit_cost = lambda previous, node: costs[int(previous[0])][node[0]-1]
    nodes = [(i+1, (float(i), 0.)) for i in range(n)]
    start = (float(n), 0.)
    available, greedy, previous = set(range(n)), [], n
    while available:
        index = min(available, key=lambda j: (costs[previous][j], j))
        greedy.append(index)
        available.remove(index)
        previous = index
    route = policy._route(start, nodes)
    order = [node[0]-1 for node in route]
    def cost(indices):
        return sum(costs[a][b] for a, b in zip([n]+indices, indices))
    assert sorted(order) == list(range(n))
    assert cost(order) <= cost(greedy)+1e-6
    # Every possible reversal must be evaluated including internal directed arcs.
    if n <= 8:
        for i in range(n-1):
            for j in range(i+1, n):
                candidate = order[:i]+list(reversed(order[i:j+1]))+order[j+1:]
                assert cost(candidate) >= cost(order)-1e-6


def test_visit_cost_includes_the_actual_measurement_detour():
    policy = ActionRouteP3()
    policy._local_action = lambda ch, state: Action('measure', (0., 300.), ch)
    assert policy._visit_cost((0., 0.), (1, (400., 0.))) == 800.
    assert policy._visit_cost((0., 0.), (-1, (400., 0.))) == 400.


def test_survey_does_not_overwrite_a_pending_channel_queue(monkeypatch):
    policy = SurveyP3()
    policy.active_ch = 1
    policy.scan_pending = False
    policy.scan_queue = [2, 3]
    monkeypatch.setattr(ResidualP3, 'step', lambda self, state: Action('measure', (500., 0.), 1))
    policy.step(State(pos=(0., 0.), ch=1))
    policy.on_measure(State(pos=(500., 0.), ch=1), 1, 'near', None)
    assert policy.scan_queue == [2, 3]
    assert not policy.scan_pending


def test_survey_adds_scan_only_after_executed_local_measurement(monkeypatch):
    policy = SurveyP3()
    policy.active_ch = 1
    policy.scan_pending = False
    monkeypatch.setattr(ResidualP3, 'step', lambda self, state: Action('measure', (500., 0.), 1))
    policy.step(State(pos=(0., 0.), ch=1))
    policy.on_measure(State(pos=(500., 0.), ch=1), 1, 'near', None)
    assert policy.scan_pending
    assert policy.local_survey_stops == 1


def test_hypothetical_probe_does_not_mutate_real_observations():
    policy = ProbePlanP3()
    state = State(pos=(0., 0.), ch=1)
    policy.on_measure(state, 1, 'direction', 0.)
    policy.active_ch = 1
    policy.scan_pending = False
    before = copy.deepcopy(policy.tracks[1])
    action = policy.step(state)
    assert policy.tracks[1] == before
    assert action.kind == 'measure' and action.ch == 1
    assert all(math.isfinite(x) for x in action.pos)
    if policy.probe_plans:
        assert max(math.dist(action.pos, vertex) for vertex in before.poly) <= 999.99
        plan = policy.probe_plans[-1]
        assert plan['predicted_new_s'] < plan['predicted_old_s']


def test_belief_quadrature_uses_geometry_not_simulator_state():
    samples = ProbePlanP3._belief_samples([(0., 0.), (10., 0.), (10., 10.), (0., 10.)])
    assert sum(weight for _, weight in samples) == pytest.approx(1.)
    assert sum(point[0]*weight for point, weight in samples) == pytest.approx(5.)
    assert sum(point[1]*weight for point, weight in samples) == pytest.approx(5.)


def test_failed_clear_recovery_is_preserved():
    policy = ProbePlanP3()
    state = State(pos=(0., 0.), ch=1)
    policy.on_measure(state, 1, 'direction', 0.)
    policy.active_ch = 1
    policy.scan_pending = False
    policy.tracks[1].probe_after_fail = True
    expected = policy._local_action(1, state)
    assert policy.step(state) == expected
    assert not policy.probe_plans


def test_combined_policy_has_both_diagnostics():
    result = PlanJointP3().diagnostics()
    assert result['local_survey_stops'] == 0
    assert result['probe_plans'] == []
