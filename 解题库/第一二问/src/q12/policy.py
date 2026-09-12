"""Constant-time universal minimax second-station policy.

For an untruncated first sector the two ideal stations are the EXACT global
minimizers over the entire reception-safe plane. For any valid first observation,
including outside the target disk, their worst residual diameter is <=D_star.
The policy is therefore minimax-optimal over all first-observation states.
Target-boundary truncation may permit an even better state-specific policy;
that different claim is not made by this module.
"""
from __future__ import annotations
from functools import lru_cache
from dataclasses import dataclass
import math
import numpy as np
from .geometry import Observation,relaxed_region,minimum_enclosing_circle

@dataclass(frozen=True)
class PolicyConstants:
    t_star:float
    diameter_star:float
    lower_x:float
    lower_y:float
    local_x:float
    local_y:float

@lru_cache(maxsize=1)
def policy_constants()->PolicyConstants:
    # These constants implement the analytic quadratic, not a stored grid result.
    a=5.;R=1000.;b=1500.;eps=math.pi/180;d=2*eps
    sd,cd,s2,c2=math.sin(d),math.cos(d),math.sin(2*d),math.cos(2*d)
    K=sd*(R*R-a*(b-a));H=(b-a)*s2
    qa=R*R-H*H
    qb=2*R*R*(sd*(b-2*a)*s2-b*cd*c2)-2*K*H
    qc=R*R*((sd*(b-2*a))**2+(b*cd)**2)-K*K
    disc=qb*qb-4*qa*qc
    if disc<=0:raise ArithmeticError('Unexpected quadratic discriminant')
    t=(-qb-math.sqrt(disc))/(2*qa)
    A=sd*(b-2*a)+t*s2;B=b*cd-t*c2;den=math.hypot(A,B)
    x=a+R*A/den;y=R*B/den
    lx=x*math.cos(eps)+y*math.sin(eps);ly=-x*math.sin(eps)+y*math.cos(eps)
    D=math.hypot(t-b*cd,b*sd)
    return PolicyConstants(t,D,x,y,lx,ly)

def safe_centers_local()->np.ndarray:
    e=math.pi/180
    return np.array([[r*math.cos(a),r*math.sin(a)] for r in (5.,1000.) for a in (-e,e)])

def reception_safe_local(points,tol=0.):
    pts=np.atleast_2d(np.asarray(points,dtype=float))
    if pts.shape[1]!=2 or not np.isfinite(pts).all():raise ValueError('Need finite 2D points')
    return np.all(np.sum((pts[:,None,:]-safe_centers_local()[None,:,:])**2,axis=2)<=(1000.+tol)**2,axis=1)

def transform(points,s1,bearing_deg):
    a=math.radians(float(bearing_deg));c,s=math.cos(a),math.sin(a)
    return np.asarray(points)@np.array([[c,s],[-s,c]])+np.asarray(s1)

def first_direction_possible(s1,bearing_deg):
    """Exact ray/disk feasibility criterion; only three possible angular extrema."""
    p=np.asarray(s1,float);angles=[bearing_deg-1.,bearing_deg+1.]
    if np.linalg.norm(p)>0:
        inward=math.degrees(math.atan2(-p[1],-p[0]));difference=(inward-bearing_deg+180)%360-180
        if abs(difference)<=1:angles.append(inward)
    for a in angles:
        u=np.array([math.cos(math.radians(a)),math.sin(math.radians(a))]);z=float(p@u)
        disc=z*z-float(p@p)+1800.**2
        if disc<0:continue
        root=math.sqrt(max(0.,disc));lo=max(0.,-z-root);hi=min(1500.,-z+root)
        if hi>5. and hi>=lo:return True
    return False

def choose_second_point(s1,bearing_deg,side=1,operational_margin=True)->dict:
    """Only observable inputs. side chooses one of the reflection-equivalent optima.

    operational_margin adds a 0.000056 m-scale inward displacement to prevent
    floating rounding of an active reception circle from causing a boundary miss.
    The ideal point and executed point are both returned and never conflated.
    """
    obs=Observation(float(s1[0]),float(s1[1]),float(bearing_deg))
    if side not in (-1,1):raise ValueError('side must be +1 or -1')
    # A direction cannot originate beyond the 1500m reception limit from Omega.
    if not first_direction_possible(obs.position,obs.bearing_deg):raise ValueError('No source can produce the stated first direction')
    k=policy_constants();ideal=np.array([k.local_x,side*k.local_y])
    shrink=1e-7 if operational_margin else 0.
    local=(1-shrink)*ideal+shrink*np.array([750.,0.])
    actual=transform(local,obs.position,obs.bearing_deg)
    return dict(S1=obs.position.tolist(),bearing_deg=obs.bearing_deg,side=side,
                theoretical_local=ideal.tolist(),operational_local=local.tolist(),S2=actual.tolist(),
                theoretical_S2=transform(ideal,obs.position,obs.bearing_deg).tolist(),
                theoretical_worst_diameter_m=k.diameter_star,travel_m=float(np.linalg.norm(local)),
                guard_displacement_m=float(np.linalg.norm(local-ideal)),
                minimum_reception_disk_margin_m=float(1000-np.max(np.linalg.norm(local-safe_centers_local(),axis=1))),
                guarantee='universal minimax; exact theorem for ideal coordinates; inward floating-point guard')

def good_candidate_mask(points):
    pts=np.atleast_2d(np.asarray(points,float));k=policy_constants()
    in_box=((np.abs(pts[:,0]-k.local_x)<=4)&(np.abs(np.abs(pts[:,1])-k.local_y)<=4))
    return reception_safe_local(pts)&in_box
