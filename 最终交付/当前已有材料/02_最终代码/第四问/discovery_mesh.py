"""A continuous, directional-discovery certificate using 25 fixed stations.

This module is independent of simulator state and of every P3 module.  The
certificate uses the official lower reception radius (1000 m), not a source's
hidden radius.  It says nothing about no_signal localization exclusions.

Construction/proof
------------------
Tile the whole plane with equilateral triangles of side 999.999 m.  Keep all
triangles whose CLOSED area intersects the CLOSED 1800 m target disk, and keep
all their vertices.  Triangle/disk intersection is decided by exact geometric
formulas (with conservative floating-point padding), never a point sample.

For every possible source p, at least one retained triangle contains p.  Each
vertex is at distance <= the triangle's diameter < 1000 m from p.  For every
unit direction n, p=sum(w_i*v_i), w_i>=0, sum(w_i)=1 gives
sum(w_i * n.dot(v_i-p))=0, so at least one vertex is in the closed transmitting
half-plane n.dot(v_i-p)>=0.  Measuring that source's channel at all retained
vertices therefore discovers it regardless of its direction/radius.

The 25-point route below is an open Hamilton path made of lattice edges, from
the closest station to the origin.  Distinct lattice vertices are >= one edge
apart, so its length is the EXACT optimum for this particular fixed station
set and origin start.  This is not a lower bound for all possible P4 policies.
"""

import math


ARENA_RADIUS = 1800.0
RECEPTION_LOWER_BOUND = 1000.0
EDGE = 999.999
HEIGHT = math.sqrt(3.0) * EDGE / 2.0
OFFSET = (1.0 / 12.0, 1.0 / 12.0)
INTERSECTION_PADDING = 1e-7


def lattice_point(index):
    """Map the integer triangular-lattice index to a fixed physical point."""
    i, j = index
    u, v = OFFSET
    return (EDGE * (i - u + (j - v) / 2.0), HEIGHT * (j - v))


def _segment_distance_from_origin(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = -(a[0] * dx + a[1] * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(a[0] + t * dx, a[1] + t * dy)


def triangle_distance_from_origin(vertices):
    """Minimum Euclidean norm over the complete closed triangle."""
    a, b, c = vertices
    edges = ((a, b), (b, c), (c, a))
    crosses = [x[0] * y[1] - x[1] * y[0] for x, y in edges]
    if min(crosses) >= 0.0 or max(crosses) <= 0.0:
        return 0.0
    return min(_segment_distance_from_origin(x, y) for x, y in edges)


def _retained_triangle_indices():
    # If a triangle meets the radius-R disk, every vertex is within R+EDGE.
    # For q=a*e1+b*e2, |a| and |b| <= |q|/HEIGHT.  This gives a finite
    # enumeration bound for ALL such vertices; the extra unit includes either
    # choice of a cell's lower index.  No omitted cell can meet the target disk.
    bound = math.ceil((ARENA_RADIUS + EDGE) / HEIGHT + max(map(abs, OFFSET))) + 1
    retained = []
    for i in range(-bound, bound + 1):
        for j in range(-bound, bound + 1):
            for ids in (
                ((i, j), (i + 1, j), (i, j + 1)),
                ((i + 1, j), (i + 1, j + 1), (i, j + 1)),
            ):
                vertices = tuple(lattice_point(k) for k in ids)
                if triangle_distance_from_origin(vertices) <= ARENA_RADIUS + INTERSECTION_PADDING:
                    retained.append(ids)
    return tuple(retained)


MESH_TRIANGLE_INDICES = _retained_triangle_indices()
MESH_TRIANGLES = tuple(tuple(lattice_point(i) for i in tri) for tri in MESH_TRIANGLE_INDICES)

# This route visits each retained vertex once.  Every consecutive pair differs
# by one of (+/-1,0), (0,+/-1), (+/-1,-/+1), hence is exactly one lattice edge.
MESH_ROUTE_INDICES = (
    (0, 0), (-1, 0), (-2, 0), (-2, 1), (-2, 2), (-2, 3),
    (-1, 3), (-1, 2), (-1, 1), (0, 1), (0, 2), (1, 2),
    (2, 1), (1, 1), (1, 0), (2, 0), (3, -1), (3, -2),
    (2, -1), (2, -2), (1, -1), (1, -2), (0, -2), (-1, -1), (0, -1),
)
MESH_STATIONS = tuple(lattice_point(i) for i in MESH_ROUTE_INDICES)


def route_length(stations=MESH_STATIONS, start=(0.0, 0.0)):
    total = 0.0
    for station in stations:
        total += math.dist(start, station)
        start = station
    return total


MESH_CERTIFICATE = {
    "kind": "complete_equilateral_triangle_intersection",
    "arena_radius_m": ARENA_RADIUS,
    "guaranteed_reception_radius_m": RECEPTION_LOWER_BOUND,
    "edge_m": EDGE,
    "lattice_offset": OFFSET,
    "station_count": len(MESH_STATIONS),
    "retained_triangle_count": len(MESH_TRIANGLES),
    "open_route_from_origin_m": route_length(),
    "fixed_point_set_route_lower_bound_m": (
        (len(MESH_STATIONS) - 1) * EDGE + min(math.hypot(*p) for p in MESH_STATIONS)
    ),
    "coverage_basis": "continuous_triangle_diameter_and_convex_half_plane",
    "simulation_truth_used": False,
    "sampling_used_for_coverage": False,
    "completion_condition": "each still-unseen channel actually measured at every retained vertex",
}


def discovery_stations():
    """A fresh list, so a caller may own its scan progress without mutation here."""
    return list(MESH_STATIONS)


if __name__ == "__main__":
    import json
    print(json.dumps(MESH_CERTIFICATE, indent=2, ensure_ascii=False))
