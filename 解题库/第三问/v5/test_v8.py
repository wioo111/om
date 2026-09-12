# -*- coding: utf-8 -*-
"""仅覆盖物理计时、边界几何、退出条件及 HTTP 驱动的必要回归。"""
import math
import unittest
from unittest.mock import patch
from urllib.error import URLError

from mock_simulator import MockSimulator, Source
from robot_iter import run_with_sim_strategy, response_dict
from strategy import Action, State
from strategy_v8 import AdaptiveV8, Coverage, enclosing_circle, distance
from robot import _post


class Actions:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.clear_channel = None
        self.measure_events = 0

    def step(self, state):
        return next(self.actions, Action('done'))

    def on_measure(self, *args):
        self.measure_events += 1

    def on_clear(self, state, ch, success):
        self.clear_channel = state.ch
        if success:
            state.cleared.add(ch)


class DictionaryAPI:
    """模拟官方返回 JSON dict，且不暴露 stats/source 属性给驱动。"""
    def __init__(self, sim):
        self.sim = sim

    def enter(self):
        return response_dict(self.sim.enter())

    def measure(self, *args):
        return response_dict(self.sim.measure(*args))

    def clear(self, *args):
        return response_dict(self.sim.clear(*args))

    def exit(self):
        return response_dict(self.sim.exit())


class ContractTests(unittest.TestCase):
    def test_official_199_second_example_and_clear_channel(self):
        sim = MockSimulator()
        sim.sources[3] = Source(3, (1700, 0), 1000)
        actions = Actions([Action('measure', (300, 400), 1),
                           Action('measure', (300, 400), 2),
                           Action('clear', (300, 0), 3),
                           Action('measure', (300, 0), 2)])
        result = run_with_sim_strategy(actions, DictionaryAPI(sim))
        self.assertEqual(result['virtual_time_s'], 199)
        self.assertEqual(result['time_breakdown']['switch_time_s'], 1)
        self.assertEqual(actions.clear_channel, 2)

    def test_rejected_action_has_no_callback(self):
        class Reject(DictionaryAPI):
            def measure(self, *args):
                return {'accepted': False, 'virtual_time_s': 0}
        strategy = Actions([Action('measure', (100, 0), 2)])
        with self.assertRaisesRegex(RuntimeError, '未更新状态'):
            run_with_sim_strategy(strategy, Reject(MockSimulator()))
        self.assertEqual(strategy.measure_events, 0)

    def test_budget_checked_before_move_not_1200_virtual_seconds(self):
        class Limited(DictionaryAPI):
            def enter(self):
                return {**super().enter(), 'max_virtual_duration_s': 10}
        result = run_with_sim_strategy(Actions([Action('measure', (100, 0), 1)]),
                                       Limited(MockSimulator()))
        self.assertEqual(result['stop_reason'], 'virtual_deadline')
        self.assertEqual(result['measure_count'], 0)
        result = run_with_sim_strategy(Actions([Action('measure', (7000, 0), 1)]),
                                       DictionaryAPI(MockSimulator()))
        self.assertEqual(result['measure_count'], 1)
        self.assertEqual(result['virtual_time_s'], 1405)

    def test_zero_remaining_real_time_prevents_actions(self):
        class Expired(DictionaryAPI):
            def enter(self):
                return {**super().enter(), 'remaining_real_duration_s': 0}
        result = run_with_sim_strategy(Actions([Action('measure', (0, 0), 1)]),
                                       Expired(MockSimulator()))
        self.assertEqual(result['stop_reason'], 'real_deadline')
        self.assertEqual(result['measure_count'], 0)

    def test_same_location_error_fixed_and_two_decimal_places(self):
        sim = MockSimulator()
        sim.sources[1] = Source(1, (800, 20), 1000)
        sim.enter()
        a = sim.measure(0, 0, 1).svd_deg
        sim.measure(80, 80, 1)
        b = sim.measure(-0.0, 0, 1).svd_deg
        self.assertEqual(a, b)
        self.assertAlmostEqual(a * 100, round(a * 100))

    def test_retry_reuses_exact_request(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"accepted":true,"virtual_time_s":5}'
        with patch('robot.urlrequest.urlopen', side_effect=[URLError('timeout'), Response()]) as send:
            with patch('robot.time.sleep'):
                result = _post('http://example.invalid', '/measure', {'request_id': 'same-id'})
        self.assertTrue(result['accepted'])
        self.assertIs(send.call_args_list[0].args[0], send.call_args_list[1].args[0])


class GeometryTests(unittest.TestCase):
    def test_coverage_is_whole_cell_and_channel_specific(self):
        coverage = Coverage(60)
        mask = coverage.covered_at((0, 0))
        for x, y in coverage.points[mask]:
            for dx, dy in ((30, 30), (30, -30), (-30, 30), (-30, -30)):
                self.assertLessEqual(math.hypot(x + dx, y + dy), 1000)
        coverage.exclude(1, (0, 0))
        self.assertTrue(coverage.remaining[2].all())
        self.assertFalse(coverage.absent(1))
        for k in range(6):
            coverage.exclude(1, (1350 * math.cos(k * math.pi / 3),
                                 1350 * math.sin(k * math.pi / 3)))
        self.assertTrue(coverage.absent(1))

    def test_near_clears_without_fake_bearings(self):
        strategy = AdaptiveV8()
        state = State((0, 0), 1)
        strategy.on_measure(state, 1, 'near', None)
        self.assertEqual(strategy._local_action(1, state).kind, 'clear')
        self.assertEqual(strategy.tracks[1].records, [])
        strategy.on_clear(state, 1, False)
        strategy.on_measure(state, 1, 'near', None)
        self.assertEqual(strategy._local_action(1, state).kind, 'clear')

    def test_rounding_wrap_and_collinear_circle(self):
        center, radius = enclosing_circle([(0, 0), (1, 0), (3, 0), (3, 0)])
        self.assertAlmostEqual(radius, 1.5, places=6)
        for source in ((1000., -.01), (1800., 0.), (-1000., .01)):
            strategy = AdaptiveV8()
            sign = 1 if source[0] > 0 else -1
            for pos, error in (((400. * sign, 0.), 1.), ((800. * sign, 150.), -1.)):
                angle = (math.degrees(math.atan2(source[1] - pos[1], source[0] - pos[0])) + error) % 360
                strategy.on_measure(State(pos, 1), 1, 'direction', round(angle, 2) % 360)
            track = strategy.tracks[1]
            self.assertLessEqual(distance(track.center, source), track.radius + 1e-5)


if __name__ == '__main__':
    unittest.main()
