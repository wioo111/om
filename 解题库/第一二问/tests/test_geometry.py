import math
import itertools
import numpy as np
import pytest
from scipy.spatial.distance import pdist
from q12.geometry import *


def brute_mec(p):
    candidates=[(x,0.) for x in p]
    for a,b in itertools.combinations(p,2):
        c=(a+b)/2;candidates.append((c,np.linalg.norm(c-a)))
    for a,b,c in itertools.combinations(p,3):
        mat=2*np.vstack((b-a,c-a))
        if abs(np.linalg.det(mat))<1e-12:continue
        x=np.linalg.solve(mat,np.array([np.dot(b-a,b-a),np.dot(c-a,c-a)]))+a
        candidates.append((x,np.linalg.norm(x-a)))
    valid=[(c,r) for c,r in candidates if np.max(np.linalg.norm(p-c,axis=1))<=r+1e-8]
    return min(valid,key=lambda c:c[1])

@pytest.mark.parametrize('seed',range(30))
def test_mec_against_exhaustive_support(seed):
    rng=np.random.default_rng(seed);p=rng.normal(size=(9,2))*100
    c,r=minimum_enclosing_circle(p);_,rr=brute_mec(p)
    assert r==pytest.approx(rr,abs=1e-7)
    assert np.max(np.linalg.norm(p-c,axis=1))<=r+1e-9

@pytest.mark.parametrize('seed',range(30))
def test_calipers_against_all_pairs(seed):
    rng=np.random.default_rng(seed)
    n=80
    a=np.sort(rng.uniform(0,2*np.pi,n))
    p=np.column_stack((np.cos(a),np.sin(a)))*1000
    d,i,j=diameter(p)
    assert d==pytest.approx(pdist(p).max(),abs=1e-8)
    assert np.linalg.norm(p[i]-p[j])==pytest.approx(d,abs=1e-8)

@pytest.mark.parametrize('p',[
    [[0,0]],[[0,0],[10,0]],[[2,0],[-10,0],[30,0],[2,0]],
    [[0,0],[1,0],[0.5,math.sqrt(3)/2]],[[0,0],[1,0],[1,1],[0,1]]])
def test_degeneracies_and_jung(p):
    p=np.asarray(p,float);c,r=minimum_enclosing_circle(p);d,_,_=diameter(p)
    assert np.max(np.linalg.norm(p-c,axis=1))<=r+1e-8
    assert r>=d/2-1e-8
    assert r<=d/math.sqrt(3)+1e-8


def test_empty_is_not_zero():
    r=Region('empty',np.empty((0,2)),'test').metrics()
    assert r['D'] is None and r['radius'] is None
    with pytest.raises(ValueError):diameter([])


def test_empty_intersection_uses_none_for_coverage_metric():
    region=pure_bearing_region([Observation(0,0,180),Observation(10,0,0)])
    metrics=region.metrics()
    assert region.status=='empty'
    assert metrics['D'] is None
    assert metrics['radius'] is None
    assert metrics['q'] is None
    assert metrics['diameter_circle_covers'] is None


def test_point_and_segment_are_defined_nonempty_states():
    point=Region('point',np.array([[2.,3.]]),'test').metrics()
    segment=Region('segment',np.array([[0.,0.],[10.,0.]]),'test').metrics()
    assert point['status']=='point' and point['D']==pytest.approx(0.)
    assert segment['status']=='segment' and segment['D']==pytest.approx(10.)
    assert point['diameter_circle_covers'] is True
    assert segment['diameter_circle_covers'] is True


def test_unbounded_and_inconsistent():
    assert pure_bearing_region([Observation(0,0,0)]).status=='unbounded'
    assert pure_bearing_region([Observation(0,0,180),Observation(10,0,0)]).status=='empty'


def test_two_observation_counterexample():
    p=pure_bearing_region([Observation(0,0,0),Observation(10,-400,91)])
    q=p.metrics()
    assert len(p.vertices)==3 and q['q']>1.0001
    assert not q['diameter_circle_covers']
    assert q['q']==pytest.approx(1/math.cos(math.radians(1)),abs=1e-9)


def test_wrapping_and_outside_omega():
    for a in [0.,359.9,-.1,720.]:
        o=Observation(2000.,0.,a+180)
        r=relaxed_region([o])
        assert r.status=='bounded'
    with pytest.raises(ValueError):Observation(float('nan'),0,0)
    with pytest.raises(ValueError):pure_bearing_region([])
    with pytest.raises(ValueError):relaxed_region([Observation(0,0,0)],eps_deg=0)

@pytest.mark.parametrize('seed',range(20))
def test_true_source_containment_and_nested_intervals(seed):
    rng=np.random.default_rng(seed)
    g=rng.uniform(-800,800,2);obs=[];last=1e10
    for k in range(6):
        a=rng.uniform(-np.pi,np.pi);r=rng.uniform(20,1500)
        s=g+r*np.array([np.cos(a),np.sin(a)])
        th=np.degrees(np.arctan2(*(g-s)[::-1]))+rng.uniform(-1,1)
        obs.append(Observation(*s,th))
        out=relaxed_region(obs,n=512);ins=relaxed_region(obs,n=512,outer=False)
        assert contains(out.vertices,g)
        d=diameter(out.vertices)[0]
        assert d<=last+1e-5;last=d
        if len(ins.vertices):assert diameter(ins.vertices)[0]<=d+1e-6


def test_disk_bracket_active_arc():
    obs=[Observation(0,0,0)]
    widths=[]
    for n in [32,64,128,256,512,1024]:
        lo=diameter(relaxed_region(obs,n=n,outer=False).vertices)[0]
        hi=diameter(relaxed_region(obs,n=n).vertices)[0]
        assert lo<=1500+1e-6<=hi+1e-6
        widths.append(hi-lo)
    assert widths[-1]<widths[0]/100
