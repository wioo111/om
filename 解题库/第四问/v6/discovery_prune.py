"""Finite, continuous-certified replacement of future P4 discovery stations.

This component proves a FUTURE plan only.  A clear at extra_point is not a
measurement of any unknown channel.  Before deleting a pending station, the
caller must arrange real measurements at extra_point for EVERY unknown channel
whose plan relies on it.  Discovery completion still requires separate evidence
from each channel's actual completed measurements.

There is no simulator/source-count input, no source truth and no individual
no_signal localization exclusion.  Geometry uncertainty or finite-budget failure
keeps the original future plan.  At most eight deletion candidates are tested.
"""

import math

from discovery_compact import build_coverage_certifier


MAX_CANDIDATES = 8
MAX_CELLS_PER_CERTIFICATE = 2400
MAX_CERTIFICATE_DEPTH = 48
SAME_POINT_TOLERANCE = 1e-6


def _point(value):
    result = tuple(map(float, value))
    if len(result) != 2 or not all(math.isfinite(x) for x in result):
        raise ValueError("points must be finite (x, y) pairs")
    return result


def _unique_points(points):
    # Tiny coordinate serialization differences do not constitute new evidence.
    unique = []
    for point in points:
        if not any(math.dist(point, existing) <= SAME_POINT_TOLERANCE for existing in unique):
            unique.append(point)
    return unique


def route_length(points, start):
    length = 0.0
    for point in points:
        length += math.dist(start, point)
        start = point
    return length


def _saving(entries, index, start):
    previous = entries[index - 1][1] if index else start
    point = entries[index][1]
    saving = math.dist(previous, point)
    if index + 1 < len(entries):
        following = entries[index + 1][1]
        saving += math.dist(point, following) - math.dist(previous, following)
    return max(0.0, saving)


def choose_replacement(actual_points, pending, extra_point, start, checker=None):
    """Return {removed, remaining, diagnostics}; no actual evidence is mutated.

    actual_points must contain ONLY locations at which ALL currently unknown
    channels have already really been measured.  extra_point is a hypothetical
    common measurement location, even if the robot has already cleared there.
    pending order is preserved.  Accepted deletions are tested cumulatively.
    """
    actual = _unique_points([_point(point) for point in actual_points])
    original = [_point(point) for point in pending]
    extra = _point(extra_point)
    start = _point(start)
    equivalent = next((point for point in actual if math.dist(point, extra) <= SAME_POINT_TOLERANCE), None)
    proof_extra = equivalent if equivalent is not None else extra
    hypothetical_common = actual + ([] if equivalent is not None else [proof_extra])
    entries = list(enumerate(original))
    removed = []
    stats = {
        "kind": "continuous_future_plan_replacement",
        "future_plan_only": True,
        "actual_completion": "not_assessed",
        "actual_common_unique_points": len(actual),
        "extra_point": extra,
        "extra_is_new_location": equivalent is None,
        "extra_requires_actual_unknown_channel_measurements": equivalent is None,
        "pending_before": len(original),
        "pending_after": len(original),
        "max_candidate_attempts": MAX_CANDIDATES,
        "max_cells_per_certificate": MAX_CELLS_PER_CERTIFICATE,
        "attempts": [],
        "future_plan_proved": False,
        "route_before_m": route_length(original, start),
        "route_after_m": route_length(original, start),
        "route_saving_m": 0.0,
        "coverage_uses_sampling": False,
    }
    if checker is None:
        try:
            checker = build_coverage_certifier(max_cells=MAX_CELLS_PER_CERTIFICATE,
                                              max_depth=MAX_CERTIFICATE_DEPTH)
        except (ArithmeticError, ValueError, RuntimeError) as exc:
            stats["initial_future_certificate"] = {"reason": "certificate_construction_error", "error": str(exc)}
            stats["reason"] = "initial_future_plan_not_proved"
            return dict(removed=[], remaining=list(original), diagnostics=stats)

    def prove(points):
        try:
            passed = checker.certified_complete(points, max_cells=MAX_CELLS_PER_CERTIFICATE)
            diagnostic = dict(checker.last_diagnostics)
            return bool(passed), diagnostic
        except (ArithmeticError, ValueError, RuntimeError) as exc:
            # A certificate construction/calculation failure supplies no license
            # to remove a station.  The caller gets the reason rather than a crash.
            return False, {"reason": "certificate_error", "error": str(exc)}

    initial_passed, initial_diagnostic = prove(hypothetical_common + original)
    stats["initial_future_certificate"] = initial_diagnostic
    if not initial_passed:
        stats["reason"] = "initial_future_plan_not_proved"
        return dict(removed=[], remaining=list(original), diagnostics=stats)
    stats["future_plan_proved"] = True
    attempted_ids = set()
    while entries and len(attempted_ids) < MAX_CANDIDATES:
        candidates = [i for i, (identity, _) in enumerate(entries) if identity not in attempted_ids]
        if not candidates:
            break
        # Nearby interior points can be replaced by a clear stop. Outer support
        # vertices often have a large route saving but cannot be replaced by an
        # interior point; do not spend the entire finite budget on those first.
        index = min(candidates, key=lambda i: (math.dist(extra, entries[i][1]),
                                               -_saving(entries, i, start), entries[i][0]))
        identity, point = entries[index]
        attempted_ids.add(identity)
        estimated_saving = _saving(entries, index, start)
        tentative = [p for j, (_, p) in enumerate(entries) if j != index]
        passed, diagnostic = prove(hypothetical_common + tentative)
        stats["attempts"].append({
            "original_pending_index": identity,
            "point": point,
            "prospective_route_saving_m": estimated_saving,
            "distance_to_extra_m": math.dist(extra, point),
            "accepted": passed,
            "certificate": diagnostic,
        })
        if passed:
            removed.append(point)
            entries.pop(index)
    remaining = [point for _, point in entries]
    stats["pending_after"] = len(remaining)
    stats["route_after_m"] = route_length(remaining, start)
    stats["route_saving_m"] = stats["route_before_m"] - stats["route_after_m"]
    stats["reason"] = "certified_future_replacement" if removed else "no_deletion_proved"
    return dict(removed=removed, remaining=remaining, diagnostics=stats)
