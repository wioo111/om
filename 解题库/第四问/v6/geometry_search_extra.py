"""Second explicitly bounded geometry-only search: exactly 16 new combinations."""

import hashlib
import json
from pathlib import Path
import time

from geometry_search import (_sample_points, candidate_certifier, open_route,
                             rejecting_counterexample, ring_points)


def run():
    output = Path(__file__).with_name("geometry_search_extra_results.json")
    if output.exists():
        raise SystemExit("output exists; retain the original search evidence")
    combinations = [(n, m, r, phase) for n in (6, 7) for m in (12, 13)
                    for r in (999.999, 950.0) for phase in (0.0, 0.5)]
    assert len(combinations) == 16
    rows = []
    samples = _sample_points()
    for index, (inner, outer, radius, phase) in enumerate(combinations, 1):
        points = ring_points(inner, outer, radius, phase)
        witness = rejecting_counterexample(points, samples)
        row = dict(inner_count=inner, outer_count=outer, inner_radius_m=radius,
                   outer_phase_fraction=phase, station_count=len(points),
                   rejection_counterexample=witness, continuous_certificate=False)
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
                row.update(open_route_m=length, route_indices=route,
                           route_points_m=[points[i] for i in route], points_m=points)
        rows.append(row)
        print(json.dumps(dict(index=index, total=16, **{k: row[k] for k in (
            "inner_count", "outer_count", "inner_radius_m", "outer_phase_fraction", "status")})), flush=True)
    accepted = [row for row in rows if row["continuous_certificate"]]
    result = dict(kind="second_bounded_fixed_geometry_only", simulator_scenarios_used=False,
                  samples_only_reject=True, accepted_only_by_continuous_certificate=True,
                  candidate_count=len(rows), continuously_certified_count=len(accepted),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), rows=rows)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(result_path=str(output), continuously_certified_count=len(accepted))))


if __name__ == "__main__":
    run()
