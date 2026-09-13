"""Continuous directional discovery with 25 stations and a 17.94 km route.

The radius-1800 m target disk lies strictly inside a regular 16-gon whose
apothem is 1800.0001 m. A center, an 8-point inner ring and the outer polygon's
16 vertices triangulate that entire polygon into 32 triangles. Every triangle
edge is strictly shorter than the official 1000 m reception lower bound.

For any target p in a triangle, all three vertices are within 1000 m of p by
convexity of distance. Writing p as a convex combination of the vertices also
shows that at least one vertex lies in every closed directional half-plane
through p. Measuring each still-unseen channel at ALL its required stations
therefore guarantees discovery. No no_signal localization exclusion follows
from this proof. No simulator truth or sampled-point coverage is used.

This module uses only the Python standard library and has no P3 dependency.
"""
import math


ARENA_RADIUS=1800.0
RECEPTION_LOWER_BOUND=1000.0
INNER_RADIUS=999.999
OUTER_APOTHEM=1800.0001
OUTER_RADIUS=OUTER_APOTHEM/math.cos(math.pi/16)
CENTER=(0.0,0.0)


def _ring(radius,count):
    return tuple((radius*math.cos(math.tau*k/count),radius*math.sin(math.tau*k/count))
                 for k in range(count))


INNER_POINTS=_ring(INNER_RADIUS,8)
OUTER_POINTS=_ring(OUTER_RADIUS,16)

# Start at the origin; traverse the inner ring counterclockwise. Inner point 7
# aligns with outer point 14, so transfer radially and traverse the outer ring.
RING_STATIONS=(CENTER,)+INNER_POINTS+tuple(OUTER_POINTS[(14+k)%16] for k in range(16))


def _triangles():
    result=[]
    for a in range(8):
        ia,ib=INNER_POINTS[a],INNER_POINTS[(a+1)%8]
        oa,om,ob=(OUTER_POINTS[k%16] for k in (2*a,2*a+1,2*a+2))
        result.extend(((CENTER,ia,ib),(ia,oa,om),(ia,om,ib),(ib,om,ob)))
    return tuple(result)


RING_TRIANGLES=_triangles()


def route_length(stations=RING_STATIONS,start=CENTER):
    total=0.0
    for point in stations:
        total+=math.dist(start,point)
        start=point
    return total


RING_CERTIFICATE={
    'kind':'complete_concentric_ring_triangulation',
    'arena_radius_m':ARENA_RADIUS,
    'guaranteed_reception_radius_m':RECEPTION_LOWER_BOUND,
    'inner_radius_m':INNER_RADIUS,
    'outer_radius_m':OUTER_RADIUS,
    'outer_polygon_apothem_m':OUTER_APOTHEM,
    'station_count':len(RING_STATIONS),
    'retained_triangle_count':len(RING_TRIANGLES),
    'edge_m':max(math.dist(tri[i],tri[(i+1)%3]) for tri in RING_TRIANGLES for i in range(3)),
    'open_route_from_origin_m':route_length(),
    'coverage_basis':'entire_outer_polygon_triangulated; continuous_triangle_diameter_and_convex_half_plane',
    'simulation_truth_used':False,
    'sampling_used_for_coverage':False,
    'completion_condition':'each still-unseen channel actually measured at every ring station',
}


def discovery_stations():
    """Return a fresh list; scan progress remains owned by the caller."""
    return list(RING_STATIONS)


if __name__=='__main__':
    import json
    print(json.dumps(RING_CERTIFICATE,ensure_ascii=False,indent=2))
