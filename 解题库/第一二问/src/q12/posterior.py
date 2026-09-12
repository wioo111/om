"""Full physical posterior: target/reception disks AND exclusions of near disks.

Polygonal lower/upper sets are used only to bracket the SAME physical set.
They are not silently substituted as a different optimization objective.
"""
from __future__ import annotations
import math
import numpy as np
from shapely.geometry import Polygon,LineString,Point
from .geometry import Observation,relaxed_region,disk_polygon,convex_hull,Region

def _shape(vertices):
    if len(vertices)==0:return Polygon()
    if len(vertices)==1:return Point(vertices[0])
    if len(vertices)==2:return LineString(vertices)
    return Polygon(vertices)

def _coords(shape):
    if shape.is_empty:return []
    if shape.geom_type=='Polygon':return list(shape.exterior.coords)[:-1]
    if shape.geom_type in ('LineString','LinearRing','Point'):return list(shape.coords)
    return [p for g in shape.geoms for p in _coords(g)]

def physical_posterior(observations,n=512,outer=True):
    observations=list(observations)
    if not observations:raise ValueError('At least one observed direction is required')
    base=relaxed_region(observations,n=n,outer=outer)
    shape=_shape(base.vertices)
    for obs in observations:
        # Upper F removes INSCRIBED near polygons; lower F removes CIRCUMSCRIBED ones.
        near=_shape(disk_polygon(obs.position,5.,n=n,outer=not outer))
        shape=shape.difference(near)
    points=_coords(shape)
    hull=convex_hull(points) if points else np.empty((0,2))
    status='empty' if len(hull)==0 else 'point' if len(hull)==1 else 'segment' if len(hull)==2 else 'bounded'
    return shape,Region(status,hull,('outer' if outer else 'inner')+' physical posterior (diameter computed on its hull)')

def posterior_bracket(observations,n=512):
    _,a=physical_posterior(observations,n,False);shape,b=physical_posterior(observations,n,True)
    ma,mb=a.metrics(),b.metrics()
    return dict(lower_m=ma['D'],upper_m=mb['D'],outer_metrics=mb,inner_metrics=ma),shape
