"""Computer-assisted, whole-plane minimax certificate for the universal policy.

No sampled location is used to establish the global lower bound. It follows
from a quadratic-over-disk maximization and the exact reception domain.
The upper proof covers ALL headings, with one analytic active interval.
All verifier arithmetic is directed rational arithmetic (interval.py).
"""
from __future__ import annotations
import json,time
from fractions import Fraction as F
from pathlib import Path
from itertools import combinations
from .interval import IV,SCALE,sincos_deg,sincos_range,pi,dot,cross,norm2,vecsub

R0=5;RM=1000;RU=1500

def constants():
    se,ce=sincos_deg(F(1));sd,cd=sincos_deg(F(2));s2,c2=sincos_deg(F(4))
    K=sd*(RM**2-R0*(RU-R0));H=s2*(RU-R0)
    qa=RM**2-H.sq()
    qb=2*RM**2*(sd*(RU-2*R0)*s2-RU*cd*c2)-2*K*H
    qc=RM**2*(sd.sq()*(RU-2*R0)**2+RU**2*cd.sq())-K.sq()
    discriminant=qb.sq()-4*qa*qc
    T=(-qb-discriminant.sqrt())/(2*qa)
    A=sd*(RU-2*R0)+T*s2;B=RU*cd-T*c2
    den=(A.sq()+B.sq()).sqrt()
    sx=R0+RM*A/den;sy=RM*B/den
    # Rotate from lower-ray coordinates (first lower ray has global angle -1deg).
    s=[sx*ce+sy*se,-sx*se+sy*ce]
    far=[RU*ce,-RU*se]
    d2=RU**2+T.sq()-2*RU*T*cd
    D=d2.sqrt()
    return dict(se=se,ce=ce,sd=sd,cd=cd,s2=s2,c2=c2,K=K,H=H,qa=qa,qb=qb,qc=qc,
                T=T,A=A,B=B,den=den,sx=sx,sy=sy,s=s,far=far,D2=d2,D=D)

def assert_interval(cond,msg):
    if not cond:raise AssertionError(msg)

def lower_checks(k):
    # Algebraic identity: the chosen root gives sup_disk(N-T H)=0.
    # Check branch, positive discriminant, stationary point outside the disk,
    # exact four-disk feasibility, and the physical lower witness.
    T=k['T'];sd=k['sd'];cd=k['cd'];sn=k['s2'];cs=k['c2'];sx=k['sx'];sy=k['sy']
    assert_interval(T.lo>1401*SCALE and T.hi<1402*SCALE,'Wrong quadratic root')
    assert_interval((k['K']+k['H']*T).lo>0,'Extraneous squared-equation root')
    # v-c = (A,B)/(2 sin delta); outside the radius-RM disk.
    assert_interval((k['den']/(2*sd)).lo>RM*SCALE,'Disk maximum not on boundary')
    assert_interval((k['A']).lo>0 and k['B'].lo>0,'Wrong normal quadrant')
    # Circle centred at (5,0) is active exactly by construction. Other three are strict.
    s=[sx,sy]
    centers=[[IV.of(RM),IV.of(0)],[R0*cd,R0*sd],[RM*cd,RM*sd]]
    distances=[]
    for c in centers:
        d=norm2(vecsub(s,c));assert_interval(d.hi<RM**2*SCALE,'Other reception disk violated');distances.append(d.sqrt().json())
    # Exterior-above-wedge regime and physically valid active pair.
    assert_interval((sy*cd-sx*sd).lo>0,'Station is not above the upper ray')
    q=[T*cd,T*sd];p=[IV.of(RU),IV.of(0)]
    assert_interval(norm2(vecsub(p,s)).lo>25*SCALE,'Far witness is near station')
    assert_interval(norm2(vecsub(q,s)).lo>25*SCALE,'Upper-ray witness is near station')
    assert_interval(T.lo>5*SCALE and T.hi<RU*SCALE,'Witness outside first annular sector')
    assert_interval(T.hi<(RU*cd).lo,'Wrong branch of distance monotonicity')
    assert_interval(k['D'].hi<111*SCALE,'Fallback lower-bound comparisons need D<111')
    return dict(other_disk_distances_m=distances,root_branch='smaller real root; unsquared sign positive',
                active_circle='center 5*u_minus, radius 1000; equality by construction',pass_=True)

def line_intersection(k,gamma,lo,hi):
    """Range of G on first ray gamma intersecting second ray beta in [lo,hi]."""
    sn,cs=sincos_range(lo,hi);sg,cg=sincos_deg(F(gamma));u=[cg,sg];v=[cs,sn]
    den=cg*sn-sg*cs
    r=cross(k['s'],v)/den
    rp=(k['s'][1]*cg-k['s'][0]*sg)/(den.sq())
    return [r*cg,r*sg],r,rp

def active_checks(k):
    a,b=F('-42.1'),F('-42.0')
    A,ra,da=line_intersection(k,1,a-1,b-1)
    B,rb,db=line_intersection(k,-1,a-1,b-1)
    C,rc,dc=line_intersection(k,1,a+1,b+1)
    V,rv,dv=line_intersection(k,-1,a+1,b+1)
    p=k['far'];sh,ch=sincos_deg(F('0.5'));tangent=[IV.of(RU),-RU*sh/ch]
    # Event occurs strictly within active interval: far-lower intersection crosses R.
    _,rleft,_=line_intersection(k,-1,a+1,a+1)
    _,rright,_=line_intersection(k,-1,b+1,b+1)
    assert_interval(rleft.hi<RU*SCALE<rright.lo,'Active event not bracketed')
    for name,r in [('A',ra),('B',rb),('C',rc)]:
        assert_interval(r.lo>5*SCALE and r.hi<RU*SCALE,f'{name} crosses radial cap')
    assert_interval(ra.hi<rc.lo and rb.hi<rv.lo,'Active quadrilateral radial ordering failed')
    assert_interval(all(z.lo>0 for z in (da,db,dc,dv)),'Ray intersection not increasing')
    forward={}
    for name,gamma,l,h in [('A',1,a-1,b-1),('B',-1,a-1,b-1),('C',1,a+1,b+1),('V',-1,a+1,b+1)]:
        sn,cs=sincos_range(l,h);sg,cg=sincos_deg(F(gamma))
        coefficient=cross(k['s'],[cg,sg])/(cg*sn-sg*cs)
        assert_interval(coefficient.lo>0,f'{name} lies on a backward second ray')
        forward[name]=coefficient.json()
    # 1/2 derivative of |A-V|^2 in radians, valid across the WHOLE active interval.
    deriv=da*(ra-rv*k['cd'])+dv*(rv-ra*k['cd'])
    assert_interval(deriv.lo>0,'Left active diameter is not increasing')
    assert_interval((ra-RU*k['cd']).hi<0,'Right active diameter is not decreasing')
    # The upper second ray hits the first outer tangent BEFORE its x=RU corner.
    sn,cs=sincos_range(a+1,b+1);v=[cs,sn]
    outside=cross(v,vecsub(tangent,k['s']))
    assert_interval(outside.lo>0,'Right clipping may pass beyond first tangent edge')
    # Every other possible vertex pair is uniformly separated from D*.
    other=[]
    for label,pts,skip in [('left',[A,B,C,V],(0,3)),('right',[A,B,C,p,tangent],(0,3))]:
        for i,j in combinations(range(len(pts)),2):
            if (i,j)==skip:continue
            d=norm2(vecsub(pts[i],pts[j]))
            assert_interval(d.hi<k['D2'].lo,f'Nonactive pair {label,i,j} is not excluded')
            other.append(dict(side=label,pair=[i,j],upper_m=d.sqrt().json()[1]))
    return dict(interval_degrees=[str(a),str(b)],left_squared_distance_derivative_half=deriv.json(),
                other_pairs=other,forward_ray_coefficients=forward,pass_=True)

# Exact rational convex polygon tools: the proof does not depend on scipy/NumPy.
def cross_q(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def hull(points):
    points=sorted(set(points))
    if len(points)<=2:return points
    l=[];u=[]
    for p in points:
        while len(l)>1 and cross_q(l[-2],l[-1],p)<=0:l.pop()
        l.append(p)
    for p in reversed(points):
        while len(u)>1 and cross_q(u[-2],u[-1],p)<=0:u.pop()
        u.append(p)
    return l[:-1]+u[:-1]

def rational_outer(k):
    sh,ch=sincos_deg(F('0.5'))
    vertices=[[IV.of(0),IV.of(0)],k['far'],[IV.of(RU),-RU*sh/ch],
              [IV.of(RU),RU*sh/ch],[RU*k['ce'],RU*k['se']]]
    pts=[]
    for v in vertices:
        for x in v[0].endpoints():
            for y in v[1].endpoints():pts.append((x,y))
    return hull(pts)

def clip(poly,nx,ny,b):
    if not poly:return []
    out=[]
    for i,cur in enumerate(poly):
        prev=poly[i-1];va=nx*prev[0]+ny*prev[1]-b;vb=nx*cur[0]+ny*cur[1]-b
        if (va<=0)!=(vb<=0):
            t=va/(va-vb);out.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
        if vb<=0:out.append(cur)
    return out

def plane_relax(n,k):
    # Select rational coefficient midpoints and bound the residual on P,
    # where |x|<=1501, |y|<=27. This makes the rational plane an OUTER plane.
    mids=[q.midpoint() for q in n]
    dev=[max(abs(q.endpoints()[0]-m),abs(q.endpoints()[1]-m)) for q,m in zip(n,mids)]
    rhs=dot(n,k['s']).endpoints()[1]+1501*dev[0]+27*dev[1]
    return mids[0],mids[1],rhs

def angle_box_upper(k,poly,a,b,halfwidth=F(1)):
    # Union of all W(phi,eps), phi in [a,b], is contained in W([a-eps,b+eps]).
    if b-a+2*halfwidth>=180:return None
    sn,cs=sincos_deg(a-halfwidth);p=clip(poly,*plane_relax([sn,-cs],k))
    sn,cs=sincos_deg(b+halfwidth);p=clip(p,*plane_relax([-sn,cs],k))
    d=F(0)
    for x,y in combinations(p,2):d=max(d,(x[0]-y[0])**2+(x[1]-y[1])**2)
    return d

def heading_certificate(k,max_nodes=30000):
    poly=rational_outer(k);Dlo=k['D2'].endpoints()[0]
    stack=[(F(-180),F('-42.1')),(F('-42.0'),F(180))];leaves=[];n=0;max_other=F(0)
    while stack:
        a,b=stack.pop();n+=1
        if n>max_nodes:raise RuntimeError('Certificate node limit reached; no proof exported')
        ub=angle_box_upper(k,poly,a,b)
        if ub is not None and ub<Dlo:
            max_other=max(max_other,ub)
            leaves.append(dict(lo_deg=str(a),hi_deg=str(b),upper_squared_m=str(ub)))
        else:
            m=(a+b)/2
            if b-a<F(1,10**9):raise RuntimeError('Unresolved angle interval')
            stack.extend([(a,m),(m,b)])
    leaves.sort(key=lambda z:F(z['lo_deg']))
    # Independently check the partition, not just that the loop ended.
    intervals=[(F(x['lo_deg']),F(x['hi_deg'])) for x in leaves]+[(F('-42.1'),F('-42.0'))]
    intervals.sort();assert_interval(intervals[0][0]==-180 and intervals[-1][1]==180,'Missing ends')
    assert_interval(all(x[1]==y[0] for x,y in zip(intervals,intervals[1:])),'Coverage gap or overlap')
    return dict(nodes=n,leaf_count=len(leaves),outside_active_upper_m=IV.of(max_other).sqrt().json(),
                partition=leaves,pass_=True)


def candidate_certificate(k):
    """All reception-safe points within a +/-4 m square of either exact optimum.
    Position uncertainty increases the angular half-width by at most 0.625deg.
    """
    dmin=k['s'][1]-RU*k['se'];sb,cb=sincos_deg(F('0.625'))
    assert_interval((dmin*sb).sq().lo>32*SCALE,'Position-to-angle perturbation bound failed')
    poly=rational_outer(k);limit=F(36,25)*k['D2'].endpoints()[0]
    stack=[(F(-180),F(180))];parts=[];nodes=0;ubmax=F(0)
    while stack:
        a,b=stack.pop();nodes+=1
        if nodes>30000:raise RuntimeError('Candidate proof failed to terminate')
        u=angle_box_upper(k,poly,a,b,F('1.625'))
        if u is not None and u<limit:
            ubmax=max(ubmax,u);parts.append([str(a),str(b),str(u)])
        else:
            m=(a+b)/2;stack.extend([(a,m),(m,b)])
    parts.sort(key=lambda x:F(x[0]));assert F(parts[0][0])==-180 and F(parts[-1][1])==180
    assert all(F(a[1])==F(b[0]) for a,b in zip(parts,parts[1:]))
    return dict(half_side_m=4,extra_angle_degrees='0.625',position_to_angle_proved=True,
                bound_m=IV.of(ubmax).sqrt().json(),threshold_m=(k['D']*F(6,5)).json(),
                partition=parts,leaf_count=len(parts),pass_=True)

def operational_certificate(k):
    from .policy import choose_second_point
    proposed=choose_second_point((0.,0.),0.)['operational_local']
    # Each proposed finite decimal is treated exactly; the extra 1e-9m box
    # also covers ordinary coordinate conversion roundoff in this bounded task.
    point=[IV.of(str(x))+IV.of('0') for x in proposed]
    box=[IV(q.lo-10**31,q.hi+10**31) for q in point]
    se,ce=k['se'],k['ce'];lower=[box[0]*ce-box[1]*se,box[0]*se+box[1]*ce]
    for r in [5,1000]:
        for sign in [-1,1]:
            cc=[r*ce,sign*r*se]
            assert_interval(norm2(vecsub(box,cc)).hi<1000000*SCALE,'Operational guard is not strictly reception safe')
    A,B=lower;N=(RU*A-A.sq()-B.sq())*k['sd']+RU*B*k['cd']
    H=(RU-A)*k['s2']+B*k['c2'];T=N/H
    v=dict(k);v['s']=box;v['T']=T;v['D2']=RU**2+T.sq()-2*RU*T*k['cd'];v['D']=v['D2'].sqrt()
    active_checks(v);rest=heading_certificate(v)
    gap=v['D']-k['D']
    assert_interval(gap.hi<IV.of('0.0001').lo,'Operational deviation exceeds 0.1 mm objective budget')
    return dict(local_decimal_coordinates=[str(x) for x in proposed],
                coordinate_uncertainty_m='0.000000001',bound_m=v['D'].json(),
                optimality_loss_upper_m=gap.json()[1],nonactive_heading_leaves=rest['leaf_count'],pass_=True)

def verify_all(out:Path|None=None):
    t=time.perf_counter();k=constants()
    res=dict(arithmetic='integer fixed-point intervals, scale 10^40; exact rational clipping',
             pi=pi().json(),t_star_m=k['T'].json(),diameter_star_m=k['D'].json(),
             station_lower_coordinates_m=[k['sx'].json(),k['sy'].json()],
             station_original_coordinates_m=[x.json() for x in k['s']],
             lower_proof=lower_checks(k),active_upper_proof=active_checks(k))
    res['all_other_headings']=heading_certificate(k)
    res['candidate_region']=candidate_certificate(k)
    res['operational_guard']=operational_certificate(k)
    res['elapsed_s']=time.perf_counter()-t;res['pass']=True
    if out:
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    return res
