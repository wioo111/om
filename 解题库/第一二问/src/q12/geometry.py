"""Validated planar set-membership geometry for CUMCM 2026 B, Q1/Q2.

P is the pure bearing intersection (possibly unbounded). K is a separately
labelled convex relaxation using the target disk and reception upper bound.
An ordinary direction excludes a 5 m disk; that nonconvex exclusion is NOT
silently claimed to be part of K. Empty, point, segment, bounded and unbounded
states are represented separately. All public angles are in degrees.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Sequence
import numpy as np
from scipy.optimize import linprog

try:
    from numba import njit
except ImportError:  # Correct, slower fallback; no network or runtime installation.
    def njit(*args, **kwargs):
        return lambda f: f

ABS_TOL = 2e-9

@dataclass(frozen=True)
class Observation:
    x: float
    y: float
    bearing_deg: float
    def __post_init__(self):
        if not np.isfinite([self.x, self.y, self.bearing_deg]).all():
            raise ValueError('Observation values must be finite.')
        if max(abs(self.x), abs(self.y)) > 2_000_000:
            raise ValueError('Position exceeds the interface coordinate limit.')
    @property
    def position(self):
        return np.array([self.x, self.y], dtype=float)

@dataclass
class Region:
    status: str
    vertices: np.ndarray
    description: str
    def metrics(self) -> dict:
        if self.status == 'empty':
            return dict(status='empty', D=None, radius=None, q=None,
                        diameter_circle_covers=None, vertices=[])
        if self.status == 'unbounded':
            return dict(status='unbounded', D=None, radius=None, q=None,
                        diameter_circle_covers=False, vertices=self.vertices.tolist())
        p = self.vertices
        d, ia, ib = diameter(p)
        c, r = minimum_enclosing_circle(p)
        mid = (p[ia] + p[ib]) / 2
        off = float(np.max(np.linalg.norm(p-mid, axis=1)) - d/2)
        return dict(status=self.status, D=d, radius=r, q=(2*r/d if d > 0 else None),
                    mec_center=c.tolist(), A=p[ia].tolist(), B=p[ib].tolist(),
                    diameter_circle_center=mid.tolist(), off=off,
                    diameter_circle_covers=off <= 1e-7 * max(1., d/1000),
                    area=polygon_area(p), vertices=p.tolist())


def wrap_deg(a):
    return (np.asarray(a) + 180.) % 360. - 180.


def validate_eps(eps):
    if not np.isfinite(eps) or not 0 < eps < 90:
        raise ValueError('eps must lie strictly between 0 and 90 degrees.')


def bearing_halfplanes(obs: Observation, eps_deg=1.):
    validate_eps(eps_deg)
    lo, hi = np.deg2rad([obs.bearing_deg-eps_deg, obs.bearing_deg+eps_deg])
    a = np.array([[np.sin(lo), -np.cos(lo)], [-np.sin(hi), np.cos(hi)]])
    return a, a @ obs.position


@njit(cache=True)
def clip_raw(poly, nx, ny, b):
    """Clip a convex point sequence, retaining point/segment degeneracies.

    The half-plane has a tiny outward floating-point safety displacement;
    there is no geometric vertex simplification that could cut off a source.
    """
    m = len(poly)
    if m == 0:
        return np.empty((0, 2), dtype=np.float64)
    bound = b + ABS_TOL
    out = np.empty((m+2, 2), dtype=np.float64)
    count = 0
    for i in range(m):
        j = (i-1) % m
        va = nx*poly[j,0]+ny*poly[j,1]-bound
        vb = nx*poly[i,0]+ny*poly[i,1]-bound
        ai, bi = va <= 0., vb <= 0.
        if ai != bi:
            t = va/(va-vb)
            out[count,0] = poly[j,0]+t*(poly[i,0]-poly[j,0])
            out[count,1] = poly[j,1]+t*(poly[i,1]-poly[j,1])
            count += 1
        if bi:
            out[count] = poly[i]
            count += 1
    return out[:count].copy()


def clip(poly, a, b):
    p = np.asarray(poly, dtype=float).reshape(-1,2)
    for n, d in zip(a,b):
        p = clip_raw(p, float(n[0]), float(n[1]), float(d))
        if len(p)==0: break
    return p


def convex_hull(points):
    p = np.asarray(points, dtype=float).reshape(-1,2)
    if len(p) == 0: return p
    pts = sorted(set(map(tuple, p)))
    if len(pts) <= 2: return np.asarray(pts)
    def cross(o,a,b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[]
    for x in pts:
        while len(lower)>=2 and cross(lower[-2], lower[-1], x)<=0: lower.pop()
        lower.append(x)
    upper=[]
    for x in reversed(pts):
        while len(upper)>=2 and cross(upper[-2], upper[-1], x)<=0: upper.pop()
        upper.append(x)
    return np.asarray(lower[:-1]+upper[:-1], dtype=float)


def pure_bearing_region(observations: Sequence[Observation], eps_deg=1.) -> Region:
    """Exact half-plane model; vectorized O(h^3) vertex feasibility, h=2n.

    No bounding box is used to turn an unbounded wedge into a finite polygon.
    A feasibility LP handles empty/degenerate inputs; a recession-cone test
    based on normal-angle gaps distinguishes bounded from unbounded sets.
    """
    validate_eps(eps_deg)
    if not observations: raise ValueError('At least one direction observation is required.')
    aa,bb=zip(*(bearing_halfplanes(o,eps_deg) for o in observations))
    a,b=np.vstack(aa),np.concatenate(bb)
    # Translation improves conditioning for off-origin coordinates.
    origin=np.mean([o.position for o in observations],axis=0)
    bs=b-a@origin
    feas=linprog([0.,0.],A_ub=a,b_ub=bs,bounds=[(None,None)]*2,method='highs')
    if feas.status==2:
        return Region('empty',np.empty((0,2)),'pure bearing intersection')
    if not feas.success:
        raise ArithmeticError(f'Feasibility LP failed: {feas.message}')
    ang=np.sort(np.mod(np.arctan2(a[:,1],a[:,0]),2*np.pi))
    gap=np.max(np.diff(np.r_[ang,ang[0]+2*np.pi]))
    if gap >= np.pi-1e-12:
        return Region('unbounded',np.empty((0,2)),'pure bearing intersection')
    i,j=np.triu_indices(len(b),k=1)
    det=a[i,0]*a[j,1]-a[i,1]*a[j,0]
    ok=np.abs(det)>1e-13
    i,j,det=i[ok],j[ok],det[ok]
    pts=np.column_stack(((bs[i]*a[j,1]-a[i,1]*bs[j])/det,
                         (a[i,0]*bs[j]-bs[i]*a[j,0])/det))
    pts=pts[np.all(pts@a.T <= bs+2e-7,axis=1)]
    if len(pts)==0:
        # Bounded feasible set without reliable vertices signals conditioning,
        # not perfect localization. Do not fabricate a zero diameter.
        raise ArithmeticError('Numerically unresolved bounded intersection.')
    p=convex_hull(pts+origin)
    return Region('point' if len(p)==1 else 'segment' if len(p)==2 else 'bounded',p,
                  'pure bearing intersection')


@lru_cache(maxsize=64)
def normals(n: int, phase: float=0.):
    if n<8: raise ValueError('Use at least 8 polygon sides.')
    a=phase+2*np.pi*np.arange(n)/n
    v=np.column_stack((np.cos(a),np.sin(a)))
    v.setflags(write=False)
    return v


def disk_polygon(center, radius, n=512, outer=True, phase=0.):
    if radius<=0 or not np.isfinite(radius): raise ValueError('radius must be positive.')
    r=radius/np.cos(np.pi/n) if outer else radius
    # Both inner and outer polygons use the same outward normal grid.
    return np.asarray(center)+r*normals(n,phase+np.pi/n)


def clip_disk(poly, center, radius, n=512, outer=True, phase=0.):
    p=np.asarray(poly,dtype=float).reshape(-1,2)
    if len(p)==0: return p
    ns=normals(n,phase)
    rr=radius if outer else radius*np.cos(np.pi/n)
    b=ns@np.asarray(center)+rr
    active=np.max(p@ns.T-b,axis=0)>0.
    # Omitting already satisfied planes is exact for a shrinking convex set.
    return clip(p,ns[active],b[active])


def relaxed_region(observations: Sequence[Observation], eps_deg=1., n=512,
                   outer=True, target_radius=1800., reception_upper=1500.) -> Region:
    """K: convex relaxation of direction data + known radius upper bounds.

    K does not enforce distance>5. For inner=True (outer=False), floating point
    slack is offset inward so the intended inner geometry remains conservative.
    """
    validate_eps(eps_deg)
    if not observations: raise ValueError('Need direction observations.')
    if n<8: raise ValueError('n must be >=8.')
    # Align polygon orientation with the first observation for equivariance.
    phase=math.radians(observations[0].bearing_deg)
    safety=1e-7 if not outer else 0.
    p=disk_polygon((0.,0.),target_radius-safety,n,outer,phase)
    for o in observations:
        a,b=bearing_halfplanes(o,eps_deg)
        p=clip(p,a,b-(1e-7 if not outer else 0.))
        if len(p)==0: return Region('empty',p,'convex relaxation K')
    for o in observations:
        p=clip_disk(p,o.position,reception_upper-safety,n,outer,phase)
        if len(p)==0: return Region('empty',p,'convex relaxation K')
    # Remove only exact duplicate/collinear interior points by convex hull.
    p=convex_hull(p)
    return Region('point' if len(p)==1 else 'segment' if len(p)==2 else 'bounded',p,
                  ('outer' if outer else 'inner')+' polygon of convex relaxation K')


@njit(cache=True)
def diameter_raw(poly):
    # Quadratic reference, also faster than calipers for tiny posteriors.
    best=0.; bi=0; bj=0
    for i in range(len(poly)):
        for j in range(i+1,len(poly)):
            dx=poly[i,0]-poly[j,0]; dy=poly[i,1]-poly[j,1]
            ds=dx*dx+dy*dy
            if ds>best: best=ds; bi=i; bj=j
    return math.sqrt(best),bi,bj


def diameter(points):
    p=convex_hull(points)
    m=len(p)
    if m==0: raise ValueError('The empty set is not a zero-diameter localization.')
    if m<24:
        # Return indices into the original input, not the sorted hull.
        d,i,j=diameter_raw(p)
        original=np.asarray(points)
        return float(d),int(np.argmin(np.sum((original-p[i])**2,axis=1))),int(np.argmin(np.sum((original-p[j])**2,axis=1)))
    j=1; best=-1.; pair=(0,1)
    def area(i,ni,k):
        a=p[ni]-p[i];b=p[k]-p[i]
        return abs(a[0]*b[1]-a[1]*b[0])
    for i in range(m):
        ni=(i+1)%m
        for _ in range(m):
            nj=(j+1)%m
            if area(i,ni,nj)>area(i,ni,j)+1e-12: j=nj
            else: break
        for a in (i,ni):
            for b in (j,(j+1)%m):  # Include ties at parallel supporting edges.
                ds=float(np.sum((p[a]-p[b])**2))
                if ds>best: best=ds; pair=(a,b)
    original=np.asarray(points)
    return math.sqrt(best),*(int(np.argmin(np.sum((original-p[k])**2,axis=1))) for k in pair)


def polygon_area(p):
    if len(p)<3:return 0.
    q=np.asarray(p)-p[0]
    return abs(float(np.sum(q[:,0]*np.roll(q[:,1],-1)-q[:,1]*np.roll(q[:,0],-1))))/2


def minimum_enclosing_circle(points,seed=17):
    p=np.asarray(points,dtype=float).reshape(-1,2)
    if len(p)==0:raise ValueError('No enclosing circle requested for empty input.')
    offset=p.mean(axis=0); scale=max(1.,float(np.ptp(p,axis=0).max()))
    p=(p-offset)/scale
    p=p[np.random.default_rng(seed).permutation(len(p))]
    def pair(a,b):
        c=(a+b)/2;return c,float(np.linalg.norm(a-c))
    def inside(x,c):return np.linalg.norm(x-c[0])<=c[1]+2e-12
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    def circum(a,b,c):
        u=b-a;v=c-a;det=2*cross(u,v)
        if abs(det)<1e-15:return None
        ux=(np.dot(u,u)*v[1]-np.dot(v,v)*u[1])/det
        uy=(u[0]*np.dot(v,v)-v[0]*np.dot(u,u))/det
        center=a+np.array([ux,uy]);return center,float(np.linalg.norm(center-a))
    def two_boundary(prefix,a,b):
        base=pair(a,b);left=None;right=None
        for x in prefix:
            if inside(x,base):continue
            side=cross(b-a,x-a);c=circum(a,b,x)
            if c is None:continue
            cc=cross(b-a,c[0]-a)
            if side>0 and (left is None or cc>cross(b-a,left[0]-a)):left=c
            if side<0 and (right is None or cc<cross(b-a,right[0]-a)):right=c
        if left is None:return right or base
        if right is None:return left
        return left if left[1]<=right[1] else right
    circle=None
    for i,a in enumerate(p):
        if circle is not None and inside(a,circle):continue
        circle=(a.copy(),0.)
        for j,b in enumerate(p[:i]):
            if inside(b,circle):continue
            circle=pair(a,b) if circle[1]==0 else two_boundary(p[:j+1],a,b)
    center=circle[0]*scale+offset
    # Repair only floating-point last bits; this enforces containment explicitly.
    radius=float(np.max(np.linalg.norm(np.asarray(points)-center,axis=1)))
    return center,radius


def contains(poly,point,tol=1e-6):
    p=np.asarray(poly);x=np.asarray(point)
    if len(p)==0:return False
    if len(p)==1:return np.linalg.norm(p[0]-x)<=tol
    if len(p)==2:
        d=p[1]-p[0];t=np.clip(np.dot(x-p[0],d)/max(np.dot(d,d),1e-30),0,1)
        return np.linalg.norm(p[0]+t*d-x)<=tol
    edges=np.roll(p,-1,axis=0)-p
    v=x-p
    return bool(np.all(edges[:,0]*v[:,1]-edges[:,1]*v[:,0]>=-tol*np.maximum(1.,np.linalg.norm(edges,axis=1))))
