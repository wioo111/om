"""Conservative continuous directional-discovery certificates for P4.

For observations at S, a target p is guaranteed detectable for every transmitting
half-plane iff p is in conv({s in S: |s-p| <= 1000}).  This verifier covers a
polygon strictly OUTSIDE the target disk with finite convex cells.  On each cell
Q it uses only stations within 1000 m of EVERY vertex of Q, then verifies
Q <= conv(those stations).  Convexity proves the whole cell, not a point sample.

Cell clipping and ambiguous orientation predicates use exact rational arithmetic
on the supplied floating-point coordinates.  Distance filtering keeps a 10 um
inward reserve.  Cells partition the outer polygon; failure to prove any cell,
including finite-budget exhaustion, returns False.  No simulator truth and no
single-no_signal localization exclusion are involved.

A certifier caches continuous cell witnesses, so additional observations cannot
invalidate a previously established certificate.  Instances own their caches;
use one per stream of observations (or identical unknown-channel point sets).
"""

from dataclasses import dataclass, field
from fractions import Fraction
from functools import lru_cache
import math

import numpy as np

from discovery_mesh import ARENA_RADIUS, lattice_point, triangle_distance_from_origin


RADIUS = 1000.0
DISTANCE_RESERVE = 1e-5
OUTER_RESERVE = 1e-5
OUTER_SIDES = 96


@lru_cache(maxsize=8192)
def _exact_point(point):
    return (Fraction.from_float(point[0]), Fraction.from_float(point[1]))


def _cross_exact(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _orientation(a, b, p, exact_p=None):
    x = (b[0] - a[0]) * (p[1] - a[1])
    y = (b[1] - a[1]) * (p[0] - a[0])
    cross = x - y
    uncertainty = 1e-12 * (abs(x) + abs(y) + 1.0)
    if cross > uncertainty:
        return 1
    if cross < -uncertainty:
        return -1
    value = _cross_exact(_exact_point(a), _exact_point(b), exact_p or _exact_point(p))
    return (value > 0) - (value < 0)


def _hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        return points
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and _orientation(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and _orientation(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _inside_hull(hull, vertices, exact_vertices):
    if len(hull) < 3:
        return False
    for a, b in zip(hull, hull[1:] + hull[:1]):
        for p, exact_p in zip(vertices, exact_vertices):
            if _orientation(a, b, tuple(p), exact_p) < 0:
                return False
    return True


def _clip(poly, a, b):
    """Exact closed left-half-plane clipping of a convex rational polygon."""
    if not poly:
        return ()
    result = []
    previous = poly[-1]
    previous_d = _cross_exact(a, b, previous)
    for current in poly:
        current_d = _cross_exact(a, b, current)
        if (current_d >= 0) != (previous_d >= 0):
            t = previous_d / (previous_d - current_d)
            result.append(tuple(previous[k] + t * (current[k] - previous[k]) for k in (0, 1)))
        if current_d >= 0:
            result.append(current)
        previous, previous_d = current, current_d
    dedup = []
    for p in result:
        if not dedup or p != dedup[-1]:
            dedup.append(p)
    if len(dedup) > 1 and dedup[0] == dedup[-1]:
        dedup.pop()
    return tuple(dedup)


def _positive_area(poly):
    if len(poly) < 3:
        return False
    return sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(poly, poly[1:] + poly[:1])) > 0


@lru_cache(maxsize=1)
def _initial_geometry():
    radius = (ARENA_RADIUS + OUTER_RESERVE) / math.cos(math.pi / OUTER_SIDES)
    outer = tuple((radius * math.cos((2 * i + 1) * math.pi / OUTER_SIDES),
                   radius * math.sin((2 * i + 1) * math.pi / OUTER_SIDES))
                  for i in range(OUTER_SIDES))
    # The regular polygon has all edge supports > ARENA_RADIUS by 0.01 mm,
    # much more than the floating-point construction error.
    for a, b in zip(outer, outer[1:] + outer[:1]):
        support = (a[0] * b[1] - a[1] * b[0]) / math.dist(a, b)
        if support <= ARENA_RADIUS + OUTER_RESERVE / 2:
            raise ArithmeticError("outer polygon failed its strict enclosure bound")
    exact_outer = tuple(_exact_point(p) for p in outer)
    cells = []
    # At radius <1802 m, intersecting lattice triangles have every vertex
    # within 2802 m.  Their inverse lattice coordinates are <4 in magnitude.
    # This larger finite box contains all cells that could intersect the polygon.
    for i in range(-6, 7):
        for j in range(-6, 7):
            for ids in (((i, j), (i + 1, j), (i, j + 1)),
                        ((i + 1, j), (i + 1, j + 1), (i, j + 1))):
                triangle = tuple(lattice_point(index) for index in ids)
                if triangle_distance_from_origin(triangle) > radius + 1e-7:
                    continue
                exact_triangle = tuple(_exact_point(p) for p in triangle)
                poly = exact_outer
                for a, b in zip(exact_triangle, exact_triangle[1:] + exact_triangle[:1]):
                    poly = _clip(poly, a, b)
                if _positive_area(poly):
                    cells.append(poly)
    return outer, exact_outer, tuple(cells)


@dataclass
class _Cell:
    exact: tuple
    depth: int = 0
    witnesses: list = field(default_factory=list)
    children: tuple = ()

    def __post_init__(self):
        self.vertices = np.array([[float(x), float(y)] for x, y in self.exact])

    def split(self):
        if self.children:
            return self.children
        bounds = [(min(p[k] for p in self.exact), max(p[k] for p in self.exact)) for k in (0, 1)]
        axis = max((0, 1), key=lambda k: bounds[k][1] - bounds[k][0])
        midpoint = sum(bounds[axis], Fraction()) / 2
        if axis == 0:
            a, b = (midpoint, Fraction(0)), (midpoint, Fraction(1))
        else:
            a, b = (Fraction(1), midpoint), (Fraction(0), midpoint)
        halves = (_clip(self.exact, a, b), _clip(self.exact, b, a))
        self.children = tuple(_Cell(p, self.depth + 1) for p in halves if _positive_area(p))
        return self.children


class CoverageCertifier:
    """Finite sufficient certificate; False means unproved, never safe to stop."""

    def __init__(self, max_cells=2400, max_depth=48):
        self.max_cells = int(max_cells)
        self.max_depth = int(max_depth)
        self.outer, self.exact_outer, cells = _initial_geometry()
        self.cells = tuple(_Cell(poly) for poly in cells)
        self.completed_witnesses = []
        self.last_diagnostics = {}

    def certified_complete(self, points, *, max_cells=None):
        points = tuple(sorted(set(tuple(map(float, p)) for p in points)))
        if any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in points):
            raise ValueError("observation points must be finite (x, y) pairs")
        point_set = frozenset(points)
        stats = dict(complete=False, point_count=len(points), cells_checked=0,
                     witness_cache_hits=0, cells_split=0, max_depth=0,
                     reason="not_started", coverage_uses_sampling=False)
        self.last_diagnostics = stats
        if any(witness <= point_set for witness in self.completed_witnesses):
            stats.update(complete=True, reason="complete_witness_cache", witness_cache_hits=1)
            return True
        if len(points) < 3 or not _inside_hull(_hull(points), self.outer, self.exact_outer):
            stats["reason"] = "outer_polygon_not_in_global_hull"
            return False
        budget = self.max_cells if max_cells is None else int(max_cells)
        array = np.asarray(points)
        stack = list(reversed(self.cells))
        while stack:
            if stats["cells_checked"] >= budget:
                stats["reason"] = "finite_cell_budget_exhausted"
                return False
            cell = stack.pop()
            stats["cells_checked"] += 1
            stats["max_depth"] = max(stats["max_depth"], cell.depth)
            if any(witness <= point_set for witness in cell.witnesses):
                stats["witness_cache_hits"] += 1
                continue
            delta = array[:, None, :] - cell.vertices[None, :, :]
            maximum_squared = np.max(np.sum(delta * delta, axis=2), axis=1)
            common = [p for p, eligible in zip(points, maximum_squared <= (RADIUS - DISTANCE_RESERVE) ** 2) if eligible]
            hull = _hull(common)
            if _inside_hull(hull, cell.vertices, cell.exact):
                # Only the hull stations are needed as a replayable whole-cell
                # witness.  Their range was bounded over every cell vertex.
                witness = frozenset(hull)
                cell.witnesses = [witness] + cell.witnesses[:1]
                continue
            if cell.depth >= self.max_depth:
                stats["reason"] = "finite_depth_budget_exhausted"
                return False
            children = cell.split()
            if not children:
                stats["reason"] = "non_subdividable_unproved_cell"
                return False
            stats["cells_split"] += 1
            stack.extend(reversed(children))
        self.completed_witnesses = [point_set] + self.completed_witnesses[:7]
        stats.update(complete=True, reason="all_continuous_cells_proved")
        return True

    def certified_omit(self, points, remaining_stations, station_to_omit, *, max_cells=None):
        """Certify the combined actual+future set after omitting one station.

        A True result proves a planned route sufficient.  It does NOT prove that
        future measurements have already happened, or mark any channel absent.
        """
        omitted = tuple(map(float, station_to_omit))
        remaining = [tuple(map(float, p)) for p in remaining_stations]
        if omitted not in remaining:
            raise ValueError("station_to_omit is not in remaining_stations")
        return self.certified_complete(list(points) + [p for p in remaining if p != omitted], max_cells=max_cells)


@lru_cache(maxsize=1)
def _default_certifier():
    return CoverageCertifier()


def certified_complete(points, *, max_cells=None):
    return _default_certifier().certified_complete(points, max_cells=max_cells)


def certified_omit(points, remaining_stations, station_to_omit, *, max_cells=None):
    return _default_certifier().certified_omit(points, remaining_stations, station_to_omit, max_cells=max_cells)
