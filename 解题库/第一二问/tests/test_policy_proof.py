from fractions import Fraction as F
import math
import numpy as np
import pytest
from q12.interval import IV,pi,sincos_deg
from q12.geometry import contains
from q12.proof import verify_all,constants
from q12.policy import *
from q12.posterior import *

@pytest.mark.parametrize('a',range(-720,721,45))
def test_trig_interval(a):
    # Compare to an independent high precision implementation; proof does not need it.
    import mpmath as mp
    mp.mp.dps=80;s,c=sincos_deg(F(a))
    for iv,v in [(s,mp.sin(mp.pi*a/180)),(c,mp.cos(mp.pi*a/180))]:
        lo,hi=iv.json();assert mp.mpf(lo)-mp.mpf('1e-75')<=v<=mp.mpf(hi)+mp.mpf('1e-75')

def test_interval_outward():
    a=IV.of(F(1,3));b=IV.of(F(-7,11))
    for iv,v in [(a+b,F(1,3)-F(7,11)),(a*b,-F(7,33)),(a/b,-F(11,21))]:
        lo,hi=iv.endpoints();assert lo<=v<=hi
    x=IV.of(2).sqrt();l,h=x.endpoints();assert l*l<=2<=h*h

def test_complete_global_proof():
    r=verify_all();assert r['pass']
    assert r['all_other_headings']['leaf_count']>1
    assert r['candidate_region']['pass_']

def test_constants_agree_with_proof():
    c=constants();n=policy_constants()
    assert abs(float(c['D'].midpoint())-n.diameter_star)<1e-9
    assert abs(float(c['s'][0].midpoint())-n.local_x)<1e-8
    assert abs(float(c['s'][1].midpoint())-n.local_y)<1e-8

@pytest.mark.parametrize('angle',[0,1,45,179.999,180,270,359.999,-720])
@pytest.mark.parametrize('s1',[(0,0),(1750,0),(2100,400)])
def test_universal_safe_rotation(s1,angle):
    if not first_direction_possible(s1,angle):
        with pytest.raises(ValueError):choose_second_point(s1,angle)
        return
    d=choose_second_point(s1,angle)
    assert reception_safe_local(d['operational_local'])[0]
    assert d['minimum_reception_disk_margin_m']>0
    rng=np.random.default_rng(42)
    r=rng.uniform(5.0001,1500,1000);ph=np.deg2rad(rng.uniform(-1,1,1000))
    g=np.c_[r*np.cos(ph),r*np.sin(ph)]
    dist=np.linalg.norm(g-np.array(d['operational_local']),axis=1)
    assert np.all(dist<=np.maximum(1000,r)+1e-8)

def test_active_case_matches_global_value():
    k=policy_constants();s=np.array([k.local_x,k.local_y]);e=math.pi/180
    g=1500*np.array([math.cos(e),-math.sin(e)])
    theta2=math.degrees(math.atan2(*(g-s)[::-1]))-1
    obs=[Observation(0,0,0),Observation(*s,theta2)]
    d,shape=posterior_bracket(obs,n=2048)
    assert abs(d['upper_m']-k.diameter_star)<1e-5
    assert d['lower_m']<=k.diameter_star+1e-6

def test_candidate_box_reception_filter():
    k=policy_constants();pts=np.array([[k.local_x-1,k.local_y-1],[k.local_x+50,k.local_y]])
    assert good_candidate_mask(pts).tolist()==[True,False]

def test_no_truth_argument():
    import inspect
    assert set(inspect.signature(choose_second_point).parameters)=={'s1','bearing_deg','side','operational_margin'}


def test_coverage_rate_excludes_empty_and_never_coerces_none():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from experiments import coverage_rate
    rows=[
        {'status':'empty','covered':None},
        {'status':'unbounded','covered':False},
        {'status':'bounded','covered':True},
        {'status':'segment','covered':False},
    ]
    assert coverage_rate(rows)==pytest.approx(0.5)
    with pytest.raises(ValueError):
        coverage_rate([{'status':'point','covered':None}])


def test_standard_f0_four_circle_boundary_semantics():
    k=policy_constants();opt=np.array([k.local_x,k.local_y])
    assert reception_safe_local(opt)[0]
    inside=np.array([[100.,0.],[750.,0.],opt,[k.local_x,-k.local_y]])
    assert np.all(reception_safe_local(inside))
    centers=safe_centers_local()
    active=int(np.argmax(np.sum((opt-centers)**2,axis=1)))
    outward=(opt-centers[active])/np.linalg.norm(opt-centers[active])
    assert not reception_safe_local(opt+1e-4*outward)[0]


def test_target_truncated_first_observation_keeps_universal_policy_guarantee():
    obs=Observation(1700.,0.,0.)
    truncated=relaxed_region([obs],target_radius=1800.)
    assert truncated.status=='bounded'
    assert contains(truncated.vertices,[1750.,0.])
    assert first_direction_possible(obs.position,obs.bearing_deg)
    result=choose_second_point(obs.position,obs.bearing_deg)
    assert reception_safe_local(result['operational_local'])[0]
    assert result['minimum_reception_disk_margin_m']>0


def test_formal_policy_signature_has_no_truth_inputs():
    import inspect
    forbidden={'G','G_true','d_true','R_eff_true','source','true_source','true_distance'}
    names=set(inspect.signature(choose_second_point).parameters)
    assert names.isdisjoint(forbidden)
