"""Bounded, simulator-independent ring discovery geometry experiment.

Samples may produce a rejecting counterexample.  A candidate is accepted ONLY
when CoverageCertifier proves every continuous cell.  No simulator scenes,
channels, true source positions or strategy tuning results are read.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from discovery_coverage import (CoverageCertifier, _Cell, _clip, _exact_point,
                                _hull, _initial_geometry, _positive_area)


def ring_points(inner_count, outer_count, inner_radius, phase_fraction=0.0):
    outer_radius = 1800.0001 / math.cos(math.pi / outer_count)
    phase = phase_fraction * math.tau / outer_count
    inner = [(inner_radius * math.cos(i * math.tau / inner_count),
              inner_radius * math.sin(i * math.tau / inner_count)) for i in range(inner_count)]
    outer = [(outer_radius * math.cos(i * math.tau / outer_count + phase),
              outer_radius * math.sin(i * math.tau / outer_count + phase)) for i in range(outer_count)]
    return [(0.0, 0.0)] + inner + outer


def candidate_certifier(points):
    """Intersect two independently verified outer enclosures before proving.

    The original 96-gon and candidate station hull both contain the entire disk.
    Their exact intersection therefore also contains it.  This avoids rejecting
    outer rings solely because their edge normals differ from the 96-gon's.
    """
    checker = CoverageCertifier(max_cells=10000, max_depth=56)
    hull = _hull(points)
    for a, b in zip(hull, hull[1:] + hull[:1]):
        support = (a[0] * b[1] - a[1] * b[0]) / math.dist(a, b)
        if support <= 1800.00005:
            raise ValueError("candidate hull lacks the required outer-disk reserve")
    exact_hull = tuple(_exact_point(p) for p in hull)
    _, original_outer, original_cells = _initial_geometry()

    def intersect(poly):
        for a, b in zip(exact_hull, exact_hull[1:] + exact_hull[:1]):
            poly = _clip(poly, a, b)
        return poly

    checker.exact_outer = intersect(original_outer)
    checker.outer = tuple(tuple(map(float, p)) for p in checker.exact_outer)
    checker.cells = tuple(_Cell(p) for cell in original_cells
                          if _positive_area(p := intersect(cell)))
    return checker


def _sample_points():
    samples = [(r * math.cos(k * math.tau / 360), r * math.sin(k * math.tau / 360))
               for r in range(0, 1801, 50) for k in range(360)]
    return np.array([p for p in samples if math.hypot(*p) <= 1800.0])


def rejecting_counterexample(points, samples):
    """A strict empty transmitting half-plane witnesses rejection, never acceptance."""
    station_array = np.array(points)
    delta = station_array[None, :, :] - samples[:, None, :]
    squared = np.sum(delta * delta, axis=2)
    eligible = squared <= (1000.0 + 1e-8) ** 2
    counts = np.sum(eligible, axis=1)
    angles = np.mod(np.arctan2(delta[:, :, 1], delta[:, :, 0]), math.tau)
    ordered = np.sort(np.where(eligible, angles, math.tau * 2), axis=1)
    ordinary_gaps = np.where(np.arange(len(points) - 1)[None, :] < counts[:, None] - 1,
                             np.diff(ordered, axis=1), 0.0)
    largest = np.max(ordinary_gaps, axis=1)
    last = ordered[np.arange(len(samples)), np.maximum(counts - 1, 0)]
    wrap = ordered[:, 0] + math.tau - last
    largest = np.maximum(largest, wrap)
    possible = np.flatnonzero(((largest > math.pi + 1e-7) | (counts == 0))
                              & (np.min(squared, axis=1) > 1e-12))
    for row in possible:
        local_angles = ordered[row, :counts[row]]
        if len(local_angles):
            gaps = np.diff(np.r_[local_angles, local_angles[0] + math.tau])
            index = int(np.argmax(gaps))
            direction = (local_angles[index] + gaps[index] / 2) % math.tau
        else:
            direction = 0.0
        unit = np.array([math.cos(direction), math.sin(direction)])
        projected = delta[row, eligible[row], :] @ unit
        # Recheck the proposed counterexample directly, including all stations
        # within a conservatively inflated reception radius.
        if len(projected) == 0 or np.max(projected) < -1e-6:
            return dict(position_m=samples[row].tolist(), direction_deg=math.degrees(direction),
                        reception_radius_m=1000.0, eligible_station_count=int(counts[row]),
                        maximum_in_range_half_plane_projection_m=float(np.max(projected)) if len(projected) else None)
    return None


def open_route(points):
    """Deterministic multistart nearest-neighbor plus bounded fixed-start 2-opt."""
    size = len(points)
    distances = np.linalg.norm(np.array(points)[:, None, :] - np.array(points)[None, :, :], axis=2)
    best = None
    for first in range(1, size):
        route = [0, first]
        remaining = set(range(1, size)) - {first}
        while remaining:
            nxt = min(remaining, key=lambda k: (distances[route[-1], k], k))
            route.append(nxt)
            remaining.remove(nxt)
        for _ in range(80):
            improvement = None
            for i in range(1, size - 1):
                for j in range(i + 1, size):
                    gain = distances[route[i - 1], route[i]] - distances[route[i - 1], route[j]]
                    if j + 1 < size:
                        gain += distances[route[j], route[j + 1]] - distances[route[i], route[j + 1]]
                    if gain > 1e-7 and (improvement is None or gain > improvement[0]):
                        improvement = (gain, i, j)
            if improvement is None:
                break
            _, i, j = improvement
            route[i:j + 1] = reversed(route[i:j + 1])
        length = sum(float(distances[a, b]) for a, b in zip(route, route[1:]))
        candidate = (length, route)
        if best is None or candidate < best:
            best = candidate
    return best


def run(output_path):
    # Exactly 48 prespecified candidate geometries and one ring25 reference.
    configurations = [(n, m, radius, phase) for n in (7, 8, 9)
                      for m in (12, 13, 14, 15)
                      for radius in (950.0, 999.999) for phase in (0.0, 0.25)]
    configurations.append((8, 16, 999.999, 0.0))
    if len(configurations) > 60:
        raise AssertionError("bounded geometry search exceeded 60 combinations")
    samples = _sample_points()
    rows = []
    started = time.perf_counter()
    for index, (inner, outer, radius, phase) in enumerate(configurations, 1):
        points = ring_points(inner, outer, radius, phase)
        row = dict(inner_count=inner, outer_count=outer, inner_radius_m=radius,
                   outer_phase_fraction=phase, station_count=len(points))
        witness = rejecting_counterexample(points, samples)
        row["rejection_counterexample"] = witness
        row["continuous_certificate"] = False
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
                row.update(open_route_m=length, move_time_s=length / 5,
                           route_indices=route, route_points_m=[points[i] for i in route],
                           points_m=points)
        rows.append(row)
        print(json.dumps(dict(index=index, total=len(configurations), **{k: row[k] for k in (
            "inner_count", "outer_count", "inner_radius_m", "outer_phase_fraction", "status")},
                              open_route_m=row.get("open_route_m")), ensure_ascii=False), flush=True)
    accepted = [row for row in rows if row["continuous_certificate"]]
    best = min(accepted, key=lambda row: (row["open_route_m"], row["station_count"])) if accepted else None
    result = dict(kind="bounded_fixed_geometry_only", simulator_scenarios_used=False,
                  samples_only_reject=True, accepted_only_by_continuous_certificate=True,
                  candidate_count=len(rows), continuously_certified_count=len(accepted),
                  elapsed_seconds=time.perf_counter() - started, best_by_route=best,
                  smallest_station_count=min((r["station_count"] for r in accepted), default=None),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), rows=rows)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dict(result_path=str(output_path), best_station_count=best["station_count"] if best else None,
                          best_route_m=best["open_route_m"] if best else None,
                          continuously_certified_count=len(accepted)), ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("geometry_search_results.json"))
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; choose a new output path to retain all search evidence")
    run(args.output.resolve())
