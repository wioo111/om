"""仅验证新增路线变换的净缩短、边界与节点完整性。"""
import unittest

from collab.merged_candidate import polish_route, AdaptiveV9
from strategy_v8 import distance, Track, enclosing_circle
from strategy import State


def length(start, route):
    points = [start] + [n[1] for n in route]
    return sum(distance(a, b) for a, b in zip(points, points[1:]))


class RouteTests(unittest.TestCase):
    def test_selected_parameters_and_passive_negative_evidence(self):
        strategy = AdaptiveV9()
        self.assertEqual((strategy.first_hop, strategy.lateral, strategy.probe_radius,
                          strategy.scan_fraction, strategy.opportunistic_radius),
                         (None, 40., 80., .10, 300.))
        poly = [(600.,-20.), (1400.,-20.), (1400.,20.), (600.,20.)]
        center, radius = enclosing_circle(poly)
        strategy.tracks[1] = Track(records=[((0.,0.),0.)], poly=poly,
                                   center=center, radius=radius, estimate=center)
        strategy.active_ch = 2
        strategy.on_measure(State(pos=(-100.,0.), ch=1), 1, 'no_signal', None)
        self.assertEqual(strategy.active_ch, 2)
        self.assertLess(strategy.tracks[1].radius, radius)
        self.assertGreater(min(p[0] for p in strategy.tracks[1].poly), 850.)
        self.assertLessEqual(distance((1200.,0.), strategy.tracks[1].center),
                             strategy.tracks[1].radius)

    def test_relocation_actually_shortens_and_preserves_nodes(self):
        start = (0., 0.)
        nodes = [(1, (10., 0.)), (2, (1., 0.)), (3, (11., 0.))]
        result = polish_route(start, nodes)
        self.assertEqual(length(start, result), 11.)
        self.assertCountEqual(result, nodes)
        self.assertEqual(nodes[0][0], 1)

    def test_open_path_endpoints_and_duplicate_positions(self):
        for nodes in ([], [(1, (1., 1.))],
                      [(1, (2., 0.)), (-1, (2., 0.)), (3, (1., 0.))]):
            result = AdaptiveV9._route((0., 0.), nodes)
            self.assertCountEqual(result, nodes)
            self.assertLessEqual(length((0., 0.), result), length((0., 0.), nodes) + 1e-7)


if __name__ == '__main__':
    unittest.main()
