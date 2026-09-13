"""Strict whole-region checks for the 25-station ring discovery construction."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from shapely.geometry import Polygon
from shapely.ops import unary_union

import discovery_rings as rings


class DiscoveryRingsTests(unittest.TestCase):
    def test_triangles_cover_entire_outer_polygon_without_holes_or_overlap(self):
        outer=Polygon(rings.OUTER_POINTS)
        triangles=[Polygon(vertices) for vertices in rings.RING_TRIANGLES]
        self.assertEqual(len(triangles),32)
        self.assertTrue(all(tri.is_valid and tri.area>0 for tri in triangles))
        complete=unary_union(triangles)
        self.assertTrue(complete.is_valid)
        self.assertEqual(complete.geom_type,'Polygon')
        self.assertEqual(len(complete.interiors),0)
        # Exact topological differences, not sampled points or area tolerances.
        self.assertTrue(outer.difference(complete).is_empty)
        self.assertTrue(complete.difference(outer).is_empty)
        self.assertTrue(outer.equals(complete))
        for i,a in enumerate(triangles):
            for b in triangles[i+1:]:
                self.assertEqual(a.intersection(b).area,0)

    def test_whole_target_disk_lies_strictly_inside_all_outer_support_lines(self):
        points=rings.OUTER_POINTS
        for a,b,c in zip(points,points[1:]+points[:1],points[2:]+points[:2]):
            cross=a[0]*b[1]-a[1]*b[0]
            self.assertGreater(cross,0)  # origin is strictly inside every edge
            self.assertGreater(cross/math.dist(a,b),rings.ARENA_RADIUS)
            self.assertGreater((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]),0)
        self.assertGreater(rings.OUTER_RADIUS*math.cos(math.pi/16),rings.ARENA_RADIUS)

    def test_every_triangle_diameter_is_strictly_below_lower_reception_radius(self):
        stations=set(rings.RING_STATIONS)
        for triangle in rings.RING_TRIANGLES:
            self.assertTrue(set(triangle)<=stations)
            for i in range(3):
                self.assertLess(math.dist(triangle[i],triangle[(i+1)%3]),rings.RECEPTION_LOWER_BOUND)
        self.assertLess(rings.RING_CERTIFICATE['edge_m'],1000)
        for point in rings.INNER_POINTS:
            self.assertLess(math.dist(rings.CENTER,point),1000)

    def test_unique_stations_and_short_fixed_route(self):
        stations=rings.RING_STATIONS
        self.assertEqual(len(stations),25)
        self.assertEqual(len(set(stations)),25)
        self.assertEqual(stations[0],rings.CENTER)
        self.assertEqual(stations[1:9],rings.INNER_POINTS)
        self.assertEqual(stations[9],rings.OUTER_POINTS[14])
        self.assertLessEqual(rings.route_length(),17935)
        analytic=(rings.INNER_RADIUS+7*2*rings.INNER_RADIUS*math.sin(math.pi/8)
                  +(rings.OUTER_RADIUS-rings.INNER_RADIUS)+15*2*rings.OUTER_RADIUS*math.sin(math.pi/16))
        self.assertAlmostEqual(rings.route_length(),analytic,places=7)

    def test_module_runs_independently_without_any_strategy_or_p3_files(self):
        source=Path(rings.__file__).read_bytes()
        with tempfile.TemporaryDirectory() as first,tempfile.TemporaryDirectory() as second:
            outputs=[]
            for directory in (first,second):
                script=Path(directory)/'discovery_rings.py'
                script.write_bytes(source)
                outputs.append(subprocess.check_output([sys.executable,str(script)],cwd=directory,text=True))
        self.assertEqual(outputs[0],outputs[1])
        certificate=json.loads(outputs[0])
        self.assertEqual(certificate['station_count'],25)
        self.assertFalse(certificate['simulation_truth_used'])
        self.assertFalse(certificate['sampling_used_for_coverage'])

    def test_scan_list_mutation_does_not_change_certificate_or_future_lists(self):
        stations=rings.discovery_stations()
        stations.pop()
        self.assertEqual(len(rings.discovery_stations()),25)
        self.assertEqual(rings.RING_CERTIFICATE['station_count'],25)


if __name__=='__main__':
    unittest.main()
