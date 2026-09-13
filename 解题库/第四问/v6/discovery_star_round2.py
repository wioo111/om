"""72 bounded three-layer star geometries; continuous proof alone accepts.

Outer n-gon strictly encloses the 1800m target disk.  A middle n-ring is rotated
by half an outer step.  Center and a small inner ring bridge its interior.
This script never reads simulator scenes or hidden source information.
"""

import hashlib
import json
import math
from pathlib import Path
import time

from geometry_search import (_sample_points, candidate_certifier, open_route,
                             rejecting_counterexample)


def ring(n, radius, phase=0.0):
    return [(radius * math.cos(i * math.tau / n + phase),
             radius * math.sin(i * math.tau / n + phase)) for i in range(n)]


def configurations():
    return [(n, middle, inner_count, inner_radius, phase)
            for n in (7, 8, 9) for middle in (1300.0, 1400.0, 1500.0)
            for inner_count in (3, 4) for inner_radius in (650.0, 800.0)
            for phase in (0.0, math.pi / n)]


def points_for(config):
    n, middle, inner_count, inner_radius, phase = config
    outer_radius = 1800.0001 / math.cos(math.pi / n)
    return ([(0.0, 0.0)] + ring(inner_count, inner_radius, phase)
            + ring(n, middle, math.pi / n) + ring(n, outer_radius))


def run():
    output = Path(__file__).with_name("discovery_star_round2_results.json")
    if output.exists():
        raise SystemExit("result exists; preserve bounded geometry evidence")
    configs = configurations()
    assert len(configs) == 72
    samples = _sample_points()
    baseline = dict(station_count=21, open_route_m=17831.848533569653)
    baseline["surrogate_s"] = baseline["open_route_m"] / 5 + 80 * baseline["station_count"]
    started = time.perf_counter()
    rows = []
    for index, config in enumerate(configs, 1):
        n, middle, inner_count, inner_radius, phase = config
        points = points_for(config)
        witness = rejecting_counterexample(points, samples)
        row = dict(index=index, outer_count=n, outer_radius_m=1800.0001 / math.cos(math.pi / n),
                   middle_count=n, middle_radius_m=middle, middle_phase_rad=math.pi / n,
                   inner_count=inner_count, inner_radius_m=inner_radius, inner_phase_rad=phase,
                   origin_is_actual_station=True, station_count=len(points), points_m=points,
                   strict_counterexample=witness, continuous_certificate=False)
        if witness is not None:
            row["status"] = "rejected_by_strict_counterexample"
        else:
            checker = candidate_certifier(points)
            before = time.perf_counter()
            passed = checker.certified_complete(points)
            row.update(continuous_certificate=passed, certificate_seconds=time.perf_counter() - before,
                       certificate_diagnostics=checker.last_diagnostics,
                       status="continuously_certified" if passed else "unproved_within_finite_budget")
            if passed:
                length, route = open_route(points)
                surrogate = length / 5 + 80 * len(points)
                row.update(open_route_m=length, route_indices=route, route_points_m=[points[i] for i in route],
                           surrogate_s=surrogate, surrogate_improvement_fraction=1 - surrogate / baseline["surrogate_s"])
        rows.append(row)
        summary = dict(index=index, total=len(configs), n=n, middle=middle, inner=inner_count,
                       inner_radius=inner_radius, phase=phase, status=row["status"])
        if row["continuous_certificate"]:
            summary.update(route_m=row["open_route_m"], surrogate_s=row["surrogate_s"],
                           improvement=row["surrogate_improvement_fraction"])
        print(json.dumps(summary), flush=True)
    accepted = [row for row in rows if row["continuous_certificate"]]
    best = min(accepted, key=lambda row: row["surrogate_s"]) if accepted else None
    result = dict(kind="bounded_three_layer_star_geometry_only", planned_geometry_count=72,
                  simulator_scenarios_used=False, samples_only_reject=True,
                  continuous_proof_required_for_acceptance=True, baseline=baseline,
                  continuously_certified_count=len(accepted), elapsed_seconds=time.perf_counter() - started,
                  best_by_surrogate=best, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), rows=rows)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(result_path=str(output), certified_count=len(accepted),
                          best_surrogate_s=best["surrogate_s"] if best else None,
                          best_improvement=best["surrogate_improvement_fraction"] if best else None)))


if __name__ == "__main__":
    run()
