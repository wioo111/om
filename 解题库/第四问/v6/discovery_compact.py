"""Continuously certified P4 discovery with 21 fixed stations.

Construction: center + eight inner points at 999.999 m + twelve outer points
whose regular polygon apothem is 1800.0001 m.  Unlike the earlier ring25 proof,
this construction does not claim every triangulation edge is below 1000 m.
Its certificate is the stronger common-near-station convex-hull condition,
proved over every cell of an outer enclosure of the continuous target disk.

Production import uses only the standard library and does not rerun the proof.
build_coverage_certifier() reproduces its exact domain clipping without any
search script or result JSON.  Reproduction dependencies are the local
discovery_coverage.py, discovery_mesh.py and NumPy; no P3 module is needed.
"""

import hashlib
import json
import math


ARENA_RADIUS = 1800.0
RECEPTION_LOWER_BOUND = 1000.0
INNER_RADIUS = 999.999
INNER_COUNT = 8
OUTER_COUNT = 12
OUTER_APOTHEM = 1800.0001
OUTER_RADIUS = OUTER_APOTHEM / math.cos(math.pi / OUTER_COUNT)
CENTER = (0.0, 0.0)


def _ring(radius, count):
    return tuple((radius * math.cos(k * math.tau / count),
                  radius * math.sin(k * math.tau / count)) for k in range(count))


INNER_POINTS = _ring(INNER_RADIUS, INNER_COUNT)
OUTER_POINTS = _ring(OUTER_RADIUS, OUTER_COUNT)
COMPACT_POINTS = (CENTER,) + INNER_POINTS + OUTER_POINTS
COMPACT_ROUTE_INDICES = (0, 2, 1, 8, 7, 6, 5, 4, 3, 12, 13, 14, 15, 16, 17, 18, 19, 20, 9, 10, 11)
COMPACT_STATIONS = tuple(COMPACT_POINTS[index] for index in COMPACT_ROUTE_INDICES)


def route_length(stations=COMPACT_STATIONS, start=CENTER):
    total = 0.0
    for point in stations:
        total += math.dist(start, point)
        start = point
    return total


PROOF_PARAMETERS = {
    "kind": "continuous_common_range_convex_hull_cells",
    "arena_radius_m": ARENA_RADIUS,
    "reception_lower_bound_m": RECEPTION_LOWER_BOUND,
    "outer_polygon_sides": 96,
    "outer_polygon_apothem_reserve_m": 1e-5,
    "distance_inward_reserve_m": 1e-5,
    "domain": "exact intersection of outer 96-gon and strictly enclosing station hull",
    "max_cells": 10000,
    "max_depth": 56,
    "clipping": "exact rational closed half planes",
    "acceptance": "every continuous cell lies in hull of stations within 1000m of every cell vertex",
}


def _hash(value):
    data = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(data).hexdigest()


# Coordinate hex strings identify the exact binary floats used in the proof.
GEOMETRY_SHA256 = _hash({"points_hex": [[x.hex(), y.hex()] for x, y in COMPACT_POINTS],
                       "route_indices": COMPACT_ROUTE_INDICES})
CERTIFICATE_SHA256 = _hash({"geometry_sha256": GEOMETRY_SHA256, "proof_parameters": PROOF_PARAMETERS})
COMPACT_CERTIFICATE = {
    **PROOF_PARAMETERS,
    "inner_count": INNER_COUNT,
    "outer_count": OUTER_COUNT,
    "inner_radius_m": INNER_RADIUS,
    "outer_polygon_apothem_m": OUTER_APOTHEM,
    "outer_radius_m": OUTER_RADIUS,
    "station_count": len(COMPACT_STATIONS),
    "open_route_from_origin_m": route_length(),
    "geometry_sha256": GEOMETRY_SHA256,
    "certificate_sha256": CERTIFICATE_SHA256,
    "coverage_uses_sampling": False,
    "simulation_truth_used": False,
    "completion_condition": "each still-unseen channel actually measured at every required station",
}


def discovery_stations():
    return list(COMPACT_STATIONS)


def build_coverage_certifier(*, max_cells=10000, max_depth=56):
    """Create a reusable verifier, independently of search outputs.

    Both enclosures contain the entire radius-1800 disk; their exact convex
    intersection still contains it.  The candidate's hull reserve is checked
    before it is allowed to restrict the proof domain.  A caller can later test
    ANY actual point set against this fixed enclosing domain.
    """
    from discovery_coverage import (CoverageCertifier, DISTANCE_RESERVE,
                                    OUTER_RESERVE, OUTER_SIDES, _Cell, _clip,
                                    _exact_point, _hull, _initial_geometry, _positive_area)

    if (OUTER_SIDES != PROOF_PARAMETERS["outer_polygon_sides"]
            or OUTER_RESERVE != PROOF_PARAMETERS["outer_polygon_apothem_reserve_m"]
            or DISTANCE_RESERVE != PROOF_PARAMETERS["distance_inward_reserve_m"]):
        raise RuntimeError("coverage implementation changed; refresh the compact proof parameters")
    hull = _hull(COMPACT_POINTS)
    for a, b in zip(hull, hull[1:] + hull[:1]):
        support = (a[0] * b[1] - a[1] * b[0]) / math.dist(a, b)
        if support <= ARENA_RADIUS + 0.00005:
            raise ArithmeticError("compact station hull no longer strictly encloses the target disk")
    exact_hull = tuple(_exact_point(p) for p in hull)
    _, original_outer, original_cells = _initial_geometry()

    def intersect(poly):
        for a, b in zip(exact_hull, exact_hull[1:] + exact_hull[:1]):
            poly = _clip(poly, a, b)
        return poly

    checker = CoverageCertifier(max_cells=max_cells, max_depth=max_depth)
    checker.exact_outer = intersect(original_outer)
    checker.outer = tuple(tuple(map(float, p)) for p in checker.exact_outer)
    checker.cells = tuple(_Cell(poly) for cell in original_cells
                          if _positive_area(poly := intersect(cell)))
    return checker


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = dict(COMPACT_CERTIFICATE)
    if args.verify:
        certifier = build_coverage_certifier()
        output["reproved_complete"] = certifier.certified_complete(COMPACT_STATIONS)
        output["reproof_diagnostics"] = certifier.last_diagnostics
        if not output["reproved_complete"]:
            raise SystemExit(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
