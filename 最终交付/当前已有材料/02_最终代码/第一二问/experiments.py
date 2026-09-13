"""Regenerate final data. Synthetic experiments supplement, not replace, proofs."""
from __future__ import annotations
import sys,csv,json,time,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from q12.geometry import *
from q12.policy import *
from q12.posterior import *
from q12.proof import verify_all
RES=ROOT/'results';RES.mkdir(exist_ok=True)

COVERAGE_STATUSES=frozenset({'point','segment','bounded'})

def coverage_rate(rows):
    """Compute coverage only for localization states with a defined metric.

    Empty and unbounded states are excluded from the denominator.  A missing
    value on a point/segment/bounded row is an interface error, not a False
    observation, so it is rejected explicitly.
    """
    values=[]
    for row in rows:
        if row.get('status') not in COVERAGE_STATUSES:
            continue
        covered=row.get('covered')
        if covered is None:
            raise ValueError('diameter_circle_covers is undefined for a defined region')
        values.append(bool(covered))
    return None if not values else float(sum(values)/len(values))

def dump(name,x):
    (RES/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda o:float(o)),encoding='utf-8')
def csvout(name,rows):
    with (RES/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def q1():
    cases=json.loads((ROOT/'examples/q1_cases.json').read_text(encoding='utf-8'))
    examples={}
    for name,x in cases.items():
        obs=[Observation(**o) for o in x['observations']];m=pure_bearing_region(obs).metrics()
        examples[name]=dict(x,metrics=m)
    rng=np.random.default_rng(2026091301);rows=[];n_values=[2,3,5,8,12];nscene=200
    for case in range(nscene):
        th=rng.uniform(-np.pi,np.pi);r=1800*math.sqrt(rng.uniform());G=r*np.array([math.cos(th),math.sin(th)])
        receive=rng.uniform(1000,1500);obs=[]
        for n in range(1,13):
            theta=rng.uniform(-np.pi,np.pi);d=rng.uniform(20,receive)
            S=G+d*np.array([math.cos(theta),math.sin(theta)])
            true=math.degrees(math.atan2(*(G-S)[::-1]));read=true+rng.uniform(-1,1)
            obs.append(Observation(*S,read))
            if n not in n_values:continue
            p=pure_bearing_region(obs);m=p.metrics()
            out=relaxed_region(obs,n=512);inside=contains(out.vertices,G)
            assert inside and p.status!='empty'
            if p.status!='unbounded':assert contains(p.vertices,G)
            rows.append(dict(case=case,n=n,status=p.status,D_m=m['D'],q=m['q'],covered=m['diameter_circle_covers'],true_source_contained=inside))
    summ=[]
    for n in n_values:
        group=[x for x in rows if x['n']==n];values=np.array([x['D_m'] for x in group if x['D_m'] is not None])
        summ.append(dict(n=n,total=len(group),bounded=len(values),unbounded=sum(x['status']=='unbounded' for x in group),
                         median_D=float(np.median(values)),p25_D=float(np.percentile(values,25)),p75_D=float(np.percentile(values,75)),
                         mean_D=float(np.mean(values)),covered_among_bounded=coverage_rate(group)))
    sensitivity=[]
    obs=[Observation(-500,0,0),Observation(200,-600,math.degrees(math.atan2(600,-200))),Observation(650,350,math.degrees(math.atan2(-350,-650)))]
    for e in [0.2,0.4,0.6,0.8,1.,1.5,2.,3.]:
        m=pure_bearing_region(obs,eps_deg=e).metrics();sensitivity.append(dict(eps_deg=e,D_m=m['D']))
    disks=[]
    for n in [32,64,128,256,512,1024,2048]:
        a=relaxed_region([Observation(0,0,0)],n=n,outer=False).metrics()['D'];b=relaxed_region([Observation(0,0,0)],n=n).metrics()['D']
        disks.append(dict(n=n,lower_D=a,upper_D=b,radial_outer_error=1500*(1/math.cos(math.pi/n)-1)))
    csvout('q1_samples.csv',rows);dump('q1_summary.json',dict(seed=2026091301,N_scenes=nscene,N_regions=len(rows),examples=examples,summary=summ,
                                                          eps_sensitivity=sensitivity,disk_brackets=disks))
    print('Q1',len(rows),'regions',flush=True)

def sample_scene(rng,s1):
    for _ in range(100000):
        a=rng.uniform(-np.pi,np.pi);r=1800*math.sqrt(rng.uniform());g=r*np.array([math.cos(a),math.sin(a)])
        R=rng.uniform(1000,1500);d=np.linalg.norm(g-s1)
        if 5<d<=R:
            e1,e2=rng.uniform(-1,1,2);b=math.degrees(math.atan2(*(g-s1)[::-1]))+e1
            return g,R,e1,e2,b
    raise RuntimeError('Cannot sample a source consistent with first observation')

def evaluate(s1,th,s2,g,R,e2):
    d=float(np.linalg.norm(g-s2))
    if d<=5:return dict(status='near_then_optical',D_upper=0.,D_lower=0.,optical_guaranteed=True,bracket_width=0.)
    if d>R:return dict(status='no_signal',D_upper=None,D_lower=None,optical_guaranteed=False,bracket_width=None)
    theta2=math.degrees(math.atan2(*(g-s2)[::-1]))+e2
    obs=[Observation(*s1,th),Observation(*s2,theta2)]
    b,shape=posterior_bracket(obs,n=512)
    if b['upper_m'] is None:raise ArithmeticError('A valid physical observation produced an empty upper posterior')
    assert shape.distance(Point(g))<1e-5
    return dict(status='direction',D_upper=b['upper_m'],D_lower=b['lower_m'],
                optical_guaranteed=b['outer_metrics']['radius']<=20,bracket_width=b['upper_m']-(b['lower_m'] or 0.))

def q2():
    rng=np.random.default_rng(2026091302);rows=[];k=policy_constants()
    poses=[('center',(0.,0.),1000),('offset',(900.,0.),100),('edge',(1750.,0.),100),
           ('external',(2100.,400.),100),('north',(0.,1700.),100),('oblique',(-1000.,800.),100)]
    for name,xy,N in poses:
        s1=np.array(xy)
        for i in range(N):
            g,R,e1,e2,b=sample_scene(rng,s1)
            ours=choose_second_point(s1,b)['S2'];a=math.radians(b)
            rand_angle=rng.uniform(-np.pi,np.pi);rand_r=1800*math.sqrt(rng.uniform())
            policies={'minimax':np.array(ours),'along_750':s1+750*np.array([math.cos(a),math.sin(a)]),
                      'perpendicular_1000':s1+1000*np.array([-math.sin(a),math.cos(a)]),
                      'random_omega':rand_r*np.array([math.cos(rand_angle),math.sin(rand_angle)])}
            # Same source, R, e1 and e2 for every strategy. No discarded failures.
            for label,s2 in policies.items():
                out=evaluate(s1,b,s2,g,R,e2)
                if label=='minimax':
                    assert out['status']!='no_signal'
                    assert out['D_upper']<=k.diameter_star+0.12 # polygon outward approximation, not the exact theorem bound
                rows.append(dict(pose=name,case=i,strategy=label,S1_x=s1[0],S1_y=s1[1],G_x=g[0],G_y=g[1],
                                 R_true=R,e1=e1,e2=e2,bearing1=b,S2_x=s2[0],S2_y=s2[1],**out))
        print('Q2 pose',name,N,flush=True)
    summaries=[]
    for pose in ['all']+[x[0] for x in poses]:
        for label in ['minimax','along_750','perpendicular_1000','random_omega']:
            group=[r for r in rows if r['strategy']==label and (pose=='all' or r['pose']==pose)]
            valid=[r['D_upper'] for r in group if r['D_upper'] is not None];vals=np.array(valid)
            summaries.append(dict(pose=pose,strategy=label,N=len(group),no_signal=sum(r['status']=='no_signal' for r in group),
                                  near=sum(r['status']=='near_then_optical' for r in group),n_valid=len(valid),
                                  mean_D_among_valid=float(np.mean(vals)),median_D_among_valid=float(np.median(vals)),
                                  p95_D_among_valid=float(np.percentile(vals,95)),max_D_among_valid=float(np.max(vals)),
                                  optical_guarantee_rate=sum(r['optical_guaranteed'] for r in group)/len(group)))
    # A deterministic adversarial case ATTAINING the theoretical lower/upper value.
    e=math.pi/180;s=np.array([k.local_x,k.local_y]);g=1500*np.array([math.cos(e),-math.sin(e)])
    theta2=math.degrees(math.atan2(*(g-s)[::-1]))-1
    obs=[Observation(0,0,0),Observation(*s,theta2)]
    bracket,_=posterior_bracket(obs,n=8192)
    worst=dict(S1=[0,0],bearing1=0,S2=s.tolist(),G=g.tolist(),q=[k.t_star*math.cos(e),k.t_star*math.sin(e)],
               e1=1,e2=-1,bearing2=theta2,R_true=1500,posterior=bracket)
    csvout('q2_paired_samples.csv',rows);dump('q2_summary.json',dict(seed=2026091302,N_scenarios=sum(p[2] for p in poses),
         N_evaluations=len(rows),sampling='G uniform in Omega and R uniform [1000,1500], conditioned on first direction; distinct-site errors independently uniform for this experiment only',
         constants=vars(k),summary=summaries,worst_case=worst))
    t=time.perf_counter()
    for _ in range(10000):choose_second_point((0,0),123.)
    dump('benchmark.json',dict(policy_calls=10000,seconds=time.perf_counter()-t,method='closed-form O(1), includes input checks and guard'))

if __name__=='__main__':
    from evidence import require_fresh
    require_fresh('prove',('proofs/',))
    started=time.perf_counter();q1();q2()
    print('Completed seconds',time.perf_counter()-started)
