"""Reprove compact coverage continuously; production import stays lightweight."""

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import discovery_compact as compact


class DiscoveryCompactTests(unittest.TestCase):
    def test_continuous_certificate_reproduces_without_search_results(self):
        checker = compact.build_coverage_certifier()
        self.assertTrue(checker.certified_complete(compact.COMPACT_STATIONS))
        self.assertEqual(checker.last_diagnostics["reason"], "all_continuous_cells_proved")
        self.assertFalse(checker.last_diagnostics["coverage_uses_sampling"])
        self.assertEqual(len(compact.COMPACT_STATIONS), 21)

    def test_critical_outer_station_loss_is_not_accepted(self):
        checker = compact.build_coverage_certifier()
        top = compact.COMPACT_POINTS[12]
        self.assertFalse(checker.certified_complete([p for p in compact.COMPACT_STATIONS if p != top]))
        self.assertFalse(checker.certified_complete([]))

    def test_route_visits_all_stations_once(self):
        self.assertEqual(set(compact.COMPACT_STATIONS), set(compact.COMPACT_POINTS))
        self.assertEqual(len(set(compact.COMPACT_STATIONS)), len(compact.COMPACT_STATIONS))
        self.assertEqual(compact.COMPACT_STATIONS[0], (0.0, 0.0))
        self.assertAlmostEqual(compact.route_length(), 17831.848533569653, places=6)
        owned = compact.discovery_stations()
        owned.pop()
        self.assertEqual(len(compact.discovery_stations()), 21)

    def test_outer_hull_strictly_encloses_disk(self):
        points = compact.OUTER_POINTS
        for a, b in zip(points, points[1:] + points[:1]):
            support = (a[0] * b[1] - a[1] * b[0]) / math.dist(a, b)
            self.assertGreater(support, 1800.00005)

    def test_production_import_needs_no_coverage_or_search_modules(self):
        path = str(Path(compact.__file__).resolve())
        code = ("import importlib.util,sys;"
                f"spec=importlib.util.spec_from_file_location('compact_under_test',{path!r});"
                "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);"
                "assert 'discovery_coverage' not in sys.modules;"
                "assert 'geometry_search' not in sys.modules;"
                "assert 'numpy' not in sys.modules;"
                "print(module.CERTIFICATE_SHA256)")
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            values = [subprocess.check_output([sys.executable, "-I", "-c", code], cwd=p, text=True).strip()
                      for p in (a, b)]
        self.assertEqual(values, [compact.CERTIFICATE_SHA256] * 2)
        self.assertEqual(len(compact.CERTIFICATE_SHA256), 64)


if __name__ == "__main__":
    unittest.main()
