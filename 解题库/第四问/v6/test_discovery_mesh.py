"""Focused geometry tests; continuous coverage is the construction's proof."""

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import discovery_mesh as mesh


class DiscoveryMeshTests(unittest.TestCase):
    def test_all_intersecting_triangles_keep_all_vertices(self):
        # Independently enlarge the proven finite bound, then check each whole
        # triangle using its analytic minimum norm.  This is not circle sampling.
        route_ids = set(mesh.MESH_ROUTE_INDICES)
        touched = set()
        triangles = 0
        for i in range(-12, 13):
            for j in range(-12, 13):
                for ids in (((i, j), (i + 1, j), (i, j + 1)),
                            ((i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    vertices = tuple(mesh.lattice_point(p) for p in ids)
                    if mesh.triangle_distance_from_origin(vertices) <= mesh.ARENA_RADIUS + mesh.INTERSECTION_PADDING:
                        self.assertTrue(set(ids) <= route_ids)
                        touched.update(ids)
                        triangles += 1
        self.assertEqual(touched, route_ids)
        self.assertEqual(triangles, 33)
        self.assertEqual(len(route_ids), 25)

    def test_diameter_and_complete_triangle_structure(self):
        for triangle in mesh.MESH_TRIANGLES:
            for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
                self.assertAlmostEqual(math.dist(a, b), mesh.EDGE, places=8)
                self.assertLess(math.dist(a, b), mesh.RECEPTION_LOWER_BOUND)
            a, b, c = triangle
            area = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
            self.assertAlmostEqual(area, math.sqrt(3) * mesh.EDGE ** 2 / 4, places=6)

    def test_route_attains_fixed_station_set_lower_bound(self):
        self.assertEqual(len(mesh.MESH_STATIONS), len(set(mesh.MESH_STATIONS)))
        for a, b in zip(mesh.MESH_STATIONS, mesh.MESH_STATIONS[1:]):
            self.assertAlmostEqual(math.dist(a, b), mesh.EDGE, places=8)
        self.assertAlmostEqual(mesh.route_length(), mesh.MESH_CERTIFICATE["fixed_point_set_route_lower_bound_m"], places=7)
        self.assertAlmostEqual(mesh.route_length(), 24 * mesh.EDGE + math.sqrt(3) * mesh.EDGE / 12, places=6)
        self.assertEqual(math.hypot(*mesh.MESH_STATIONS[0]), min(math.hypot(*p) for p in mesh.MESH_STATIONS))

    def test_triangle_distance_analytic_cases(self):
        self.assertEqual(mesh.triangle_distance_from_origin(((0, 0), (2, 0), (0, 2))), 0)
        self.assertEqual(mesh.triangle_distance_from_origin(((-1, -1), (1, -1), (0, 2))), 0)
        self.assertAlmostEqual(mesh.triangle_distance_from_origin(((3, -2), (3, 2), (5, 0))), 3)
        self.assertAlmostEqual(mesh.triangle_distance_from_origin(((3, 4), (4, 4), (3, 5))), 5)
        self.assertAlmostEqual(mesh.triangle_distance_from_origin(((1800, -1), (1800, 1), (1801, 0))), 1800)

    def test_module_is_working_directory_independent(self):
        script = str(Path(mesh.__file__).resolve())
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            outputs = [subprocess.check_output([sys.executable, script], cwd=p, text=True) for p in (a, b)]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(json.loads(outputs[0])["station_count"], 25)

    def test_scan_list_is_owned_by_caller(self):
        first = mesh.discovery_stations()
        first.pop()
        self.assertEqual(len(mesh.discovery_stations()), 25)


if __name__ == "__main__":
    unittest.main()
