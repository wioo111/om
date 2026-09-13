"""Continuous-coverage regressions; no sampling is used to claim coverage."""

import math
import unittest

from discovery_coverage import CoverageCertifier, OUTER_RESERVE, _initial_geometry
from discovery_mesh import MESH_STATIONS, MESH_ROUTE_INDICES


class DiscoveryCoverageTests(unittest.TestCase):
    def test_25_station_mesh_has_continuous_certificate(self):
        checker = CoverageCertifier()
        self.assertTrue(checker.certified_complete(MESH_STATIONS))
        self.assertEqual(checker.last_diagnostics["reason"], "all_continuous_cells_proved")
        self.assertFalse(checker.last_diagnostics["coverage_uses_sampling"])
        self.assertLess(checker.last_diagnostics["cells_checked"], 100)

    def test_missing_critical_boundary_station_is_rejected(self):
        checker = CoverageCertifier()
        station = MESH_STATIONS[MESH_ROUTE_INDICES.index((-2, 3))]
        self.assertFalse(checker.certified_complete([p for p in MESH_STATIONS if p != station]))

    def test_different_ring_triangulation_has_continuous_certificate(self):
        inner = 999.999
        outer = 1800.0001 / math.cos(math.pi / 16)
        points = [(0.0, 0.0)]
        points += [(inner * math.cos(i * math.pi / 4), inner * math.sin(i * math.pi / 4)) for i in range(8)]
        points += [(outer * math.cos(i * math.pi / 8), outer * math.sin(i * math.pi / 8)) for i in range(16)]
        checker = CoverageCertifier()
        self.assertTrue(checker.certified_complete(points))
        self.assertGreater(checker.last_diagnostics["cells_split"], 0)
        self.assertLess(checker.last_diagnostics["cells_checked"], 2400)

    def test_few_points_cannot_claim_discovery_completion(self):
        checker = CoverageCertifier()
        self.assertFalse(checker.certified_complete([]))
        self.assertFalse(checker.certified_complete([(0, 0)]))
        self.assertFalse(checker.certified_complete([(0, 0), (100, 0), (0, 100)]))

    def test_added_points_preserve_completed_proof(self):
        checker = CoverageCertifier()
        self.assertTrue(checker.certified_complete(MESH_STATIONS))
        for i in range(30):
            points = list(MESH_STATIONS) + [(23.0 * j, 17.0 * j) for j in range(i + 1)]
            self.assertTrue(checker.certified_complete(points))
            self.assertEqual(checker.last_diagnostics["reason"], "complete_witness_cache")
            self.assertEqual(checker.last_diagnostics["cells_checked"], 0)

    def test_finite_budget_returns_unproved(self):
        checker = CoverageCertifier(max_cells=0)
        self.assertFalse(checker.certified_complete(MESH_STATIONS))
        self.assertEqual(checker.last_diagnostics["reason"], "finite_cell_budget_exhausted")

    def test_future_omission_requires_sufficient_combined_points(self):
        checker = CoverageCertifier()
        omitted = MESH_STATIONS[MESH_ROUTE_INDICES.index((-2, 3))]
        self.assertFalse(checker.certified_omit([], MESH_STATIONS, omitted))
        self.assertTrue(checker.certified_omit([omitted], MESH_STATIONS, omitted))
        with self.assertRaises(ValueError):
            checker.certified_omit([], MESH_STATIONS, (123.0, 456.0))

    def test_outer_polygon_strictly_encloses_target_disk(self):
        outer, _, cells = _initial_geometry()
        for a, b in zip(outer, outer[1:] + outer[:1]):
            support = (a[0] * b[1] - a[1] * b[0]) / math.dist(a, b)
            self.assertGreater(support, 1800.0 + OUTER_RESERVE / 2)
        self.assertGreater(len(cells), 0)

    def test_nonfinite_input_is_rejected(self):
        with self.assertRaises(ValueError):
            CoverageCertifier().certified_complete([(float("nan"), 0)])


if __name__ == "__main__":
    unittest.main()
