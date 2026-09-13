"""Focused component tests; clear locations never become actual scan evidence."""

import unittest
from unittest.mock import patch

from discovery_compact import COMPACT_POINTS, COMPACT_STATIONS, build_coverage_certifier
from discovery_prune import MAX_CANDIDATES, choose_replacement


class DiscoveryPruneTests(unittest.TestCase):
    def test_fully_measured_core_can_retire_multiple_future_stations(self):
        actual = list(COMPACT_STATIONS)
        pending = list(COMPACT_STATIONS)
        result = choose_replacement(actual, pending, (0.0, 0.0), (0.0, 0.0))
        self.assertEqual(len(result["removed"]), MAX_CANDIDATES)
        self.assertEqual(len(result["remaining"]), len(pending) - MAX_CANDIDATES)
        self.assertEqual(actual, list(COMPACT_STATIONS))
        self.assertEqual(pending, list(COMPACT_STATIONS))
        self.assertLessEqual(len(result["diagnostics"]["attempts"]), MAX_CANDIDATES)
        self.assertGreater(result["diagnostics"]["route_saving_m"], 0.0)

    def test_few_actual_points_never_claim_actual_completion(self):
        for actual in ([], [(0.0, 0.0)]):
            result = choose_replacement(actual, [], (10.0, 0.0), (0.0, 0.0))
            self.assertEqual(result["removed"], [])
            self.assertFalse(result["diagnostics"]["future_plan_proved"])
            self.assertTrue(result["diagnostics"]["future_plan_only"])
            self.assertEqual(result["diagnostics"]["actual_completion"], "not_assessed")

    def test_duplicate_extra_point_cannot_remove_critical_boundary_station(self):
        critical = COMPACT_POINTS[12]
        actual = [p for p in COMPACT_STATIONS if p != critical]
        for extra in ((0.0, 0.0), (1e-8, 0.0)):
            result = choose_replacement(actual, [critical], extra, (0.0, 0.0))
            self.assertEqual(result["removed"], [])
            self.assertEqual(result["remaining"], [critical])
            self.assertFalse(result["diagnostics"]["extra_is_new_location"])
            self.assertEqual(result["diagnostics"]["actual_completion"], "not_assessed")

    def test_extra_point_is_future_obligation_not_actual_measurement(self):
        critical = COMPACT_POINTS[12]
        actual = [p for p in COMPACT_STATIONS if p != critical]
        result = choose_replacement(actual, [critical], critical, critical)
        self.assertEqual(result["removed"], [critical])
        self.assertEqual(result["remaining"], [])
        self.assertTrue(result["diagnostics"]["extra_requires_actual_unknown_channel_measurements"])
        self.assertEqual(result["diagnostics"]["actual_completion"], "not_assessed")
        checker = build_coverage_certifier()
        self.assertFalse(checker.certified_complete(actual))
        self.assertTrue(checker.certified_complete(actual + [critical]))

    def test_certificate_failure_keeps_original_pending_queue(self):
        class BrokenChecker:
            last_diagnostics = {}

            def certified_complete(self, points, **kwargs):
                raise ArithmeticError("intentional finite certificate failure")

        pending = list(COMPACT_STATIONS)
        result = choose_replacement([], pending, (0.0, 0.0), (0.0, 0.0), checker=BrokenChecker())
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["remaining"], pending)
        self.assertEqual(result["diagnostics"]["initial_future_certificate"]["reason"], "certificate_error")

    def test_certificate_construction_failure_keeps_pending_queue(self):
        pending = list(COMPACT_STATIONS)
        with patch("discovery_prune.build_coverage_certifier", side_effect=ArithmeticError("construction failure")):
            result = choose_replacement([], pending, (0.0, 0.0), (0.0, 0.0))
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["remaining"], pending)
        self.assertEqual(result["diagnostics"]["initial_future_certificate"]["reason"], "certificate_construction_error")


if __name__ == "__main__":
    unittest.main()
