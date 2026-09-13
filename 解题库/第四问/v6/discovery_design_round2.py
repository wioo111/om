"""80 bounded geometry-only designs; no simulator scenarios or source truth.

Strict directional counterexamples can reject a design.  Only a successful
continuous CoverageCertifier can accept it.  An origin used solely as the route
start is NEVER silently promoted into an actual discovery measurement station.
"""

import hashlib
import json
import math
from pathlib import Path
import time

from discovery_compact import OUTER_POINTS, build_coverage_certifier
from geometry_search import _sample_points, open_route, rejecting_counterexample


def ring(count, radius, phase=0.0):
    return [(radius * math.cos(phase + i * math.tau / count),
             radius * math.sin(phase + i * math.tau / count)) for i in range(count)]


def descriptors():
    cases = []

    def add(family, params, internal):
        cases.append(dict(family=family, parameters=params, internal_points=internal))

    # 8: nonuniform cardinal/diagonal ring, with and without a center station.
    for a in (950.0, 980.0):
        for b in (950.0, 980.0):
            for center in (True, False):
                points = ring(4, a) + ring(4, b, math.pi / 4)
                add("cardinal_diagonal", dict(axis_radius=a, diagonal_radius=b, center=center),
                    ([(0.0, 0.0)] if center else []) + points)

    # 8: delete the center and use a genuine reception overlap around the origin.
    for radius in (960.0, 970.0, 980.0, 990.0):
        for phase in (0.0, math.pi / 24):
            add("eight_without_center", dict(radius=radius, phase=phase), ring(8, radius, phase))

    # 8: nine interior points without a center station, allowed a smaller radius.
    for radius in (940.0, 960.0, 980.0, 999.999):
        for phase in (0.0, math.pi / 24):
            add("nine_without_center", dict(radius=radius, phase=phase), ring(9, radius, phase))

    # 8: seven nonuniform points plus center, some allowed beyond 1000m.
    for low in (950.0, 999.999):
        for high in (1050.0, 1150.0):
            for phase in (0.0, math.pi / 24):
                points = [(0.0, 0.0)]
                points += [((low if i % 2 == 0 else high) * math.cos(phase + i * math.tau / 7),
                            (low if i % 2 == 0 else high) * math.sin(phase + i * math.tau / 7)) for i in range(7)]
                add("alternating_seven", dict(low=low, high=high, phase=phase), points)

    # 8: six nonuniform points plus center (19 total stations).
    for low in (850.0, 950.0):
        for high in (1050.0, 1150.0):
            for phase in (0.0, math.pi / 12):
                points = [(0.0, 0.0)]
                points += [((low if i % 2 == 0 else high) * math.cos(phase + i * math.tau / 6),
                            (low if i % 2 == 0 else high) * math.sin(phase + i * math.tau / 6)) for i in range(6)]
                add("alternating_six", dict(low=low, high=high, phase=phase), points)

    # 8: tiny inner triangle and a larger hexagon.
    for inner in (150.0, 300.0):
        for outer in (1050.0, 1100.0):
            for phase in (0.0, math.pi / 6):
                add("triangle_hexagon", dict(inner=inner, outer=outer, phase=phase),
                    ring(3, inner, phase) + ring(6, outer))

    # 8: inner triangle and four farther bridge points.
    for inner in (350.0, 500.0):
        for outer in (1000.0, 1200.0):
            for phase in (0.0, math.pi / 4):
                add("triangle_square", dict(inner=inner, outer=outer, phase=phase),
                    ring(3, inner, phase) + ring(4, outer))

    # 8: inner triangle and five farther bridge points.
    for inner in (350.0, 500.0):
        for outer in (1000.0, 1100.0):
            for phase in (0.0, math.pi / 5):
                add("triangle_pentagon", dict(inner=inner, outer=outer, phase=phase),
                    ring(3, inner, phase) + ring(5, outer))

    # 8: seven regular bridge points plus a displaced central point.
    for offset in (150.0, 300.0):
        for offset_angle in (0.0, math.pi / 12):
            for phase in (0.0, math.pi / 24):
                central = [(offset * math.cos(offset_angle), offset * math.sin(offset_angle))]
                add("displaced_center_seven", dict(offset=offset, offset_angle=offset_angle, phase=phase),
                    central + ring(7, 999.999, phase))

    # 8: ellipse with or without a center, rotated relative to the fixed boundary.
    for axis in (850.0, 950.0):
        for rotation in (0.0, math.pi / 12):
            for center in (True, False):
                cs, sn = math.cos(rotation), math.sin(rotation)
                ellipse = []
                for i in range(8):
                    x, y = axis * math.cos(i * math.pi / 4), 1050.0 * math.sin(i * math.pi / 4)
                    ellipse.append((cs * x - sn * y, sn * x + cs * y))
                add("ellipse", dict(short_axis=axis, long_axis=1050.0, rotation=rotation, center=center),
                    ([(0.0, 0.0)] if center else []) + ellipse)
    assert len(cases) == 80
    return cases


def route_from_real_origin(stations):
    required = list(dict.fromkeys(stations))
    zero = (0.0, 0.0)
    # open_route optimizes a fixed origin.  It is virtual unless it really occurs
    # in required; remove it from the returned station list in that case.
    planning_points = [zero] + [p for p in required if p != zero]
    length, order = open_route(planning_points)
    route = [planning_points[i] for i in order if i != 0 or zero in required]
    assert len(route) == len(required) and set(route) == set(required)
    return length, route


def run():
    output = Path(__file__).with_name("discovery_design_round2_results.json")
    if output.exists():
        raise SystemExit("result exists; preserve this bounded geometry experiment")
    started = time.perf_counter()
    samples = _sample_points()
    baseline = dict(station_count=21, open_route_m=17831.848533569653)
    baseline["surrogate_s"] = baseline["open_route_m"] / 5 + 80 * baseline["station_count"]
    rows = []
    for index, case in enumerate(descriptors(), 1):
        if time.perf_counter() - started > 590:
            rows.append(dict(index=index, **case, status="not_run_wall_clock_budget"))
            continue
        points = case["internal_points"] + list(OUTER_POINTS)
        witness = rejecting_counterexample(points, samples)
        row = dict(index=index, family=case["family"], parameters=case["parameters"],
                   station_count=len(points), points_m=points, strict_counterexample=witness,
                   continuous_certificate=False)
        if witness is not None:
            row["status"] = "rejected_by_strict_counterexample"
        else:
            checker = build_coverage_certifier(max_cells=12000, max_depth=60)
            before = time.perf_counter()
            passed = checker.certified_complete(points)
            row.update(continuous_certificate=passed, certificate_seconds=time.perf_counter() - before,
                       certificate_diagnostics=checker.last_diagnostics,
                       status="continuously_certified" if passed else "unproved_within_finite_budget")
            if passed:
                length, route = route_from_real_origin(points)
                surrogate = length / 5 + 80 * len(points)
                row.update(open_route_m=length, route_points_m=route, surrogate_s=surrogate,
                           surrogate_improvement_fraction=1 - surrogate / baseline["surrogate_s"],
                           origin_is_actual_station=(0.0, 0.0) in points)
        rows.append(row)
        print(json.dumps(dict(index=index, family=row["family"], status=row["status"],
                              stations=len(points), surrogate_s=row.get("surrogate_s"))), flush=True)
    accepted = [r for r in rows if r.get("continuous_certificate")]
    best = min(accepted, key=lambda r: r["surrogate_s"]) if accepted else None
    result = dict(kind="bounded_nonuniform_geometry_only", simulator_scenarios_used=False,
                  samples_only_reject=True, continuous_proof_required_for_acceptance=True,
                  planned_geometry_count=80, max_wall_clock_seconds=600, baseline=baseline,
                  continuously_certified_count=len(accepted), elapsed_seconds=time.perf_counter() - started,
                  best_by_surrogate=best,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), rows=rows)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(result_path=str(output), certified_count=len(accepted),
                          best_surrogate_s=best["surrogate_s"] if best else None,
                          best_improvement=best["surrogate_improvement_fraction"] if best else None)))


if __name__ == "__main__":
    run()
