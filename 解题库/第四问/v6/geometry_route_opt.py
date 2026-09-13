"""Bounded MILP optimization of two fixed P4 station sets, without scenarios.

Natural point indices are origin 0, inner ring 1..8, then the outer ring.
A zero-cost dummy node has its edge to the origin fixed on. Hamilton cycles
through the dummy are therefore origin-starting, free-ending open paths.
Degree constraints plus successive exact subtour cuts certify connectivity.
Only route order is optimized; this script makes no new coverage claim.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack


HERE=Path(__file__).resolve().parent


def ring_points(outer_count):
    points=[(0.,0.)]
    for radius,count in ((999.999,8),(1800.0001/math.cos(math.pi/outer_count),outer_count)):
        points.extend((radius*math.cos(math.tau*k/count),radius*math.sin(math.tau*k/count))
                      for k in range(count))
    return points


def route_length(points,route):
    return sum(math.dist(points[a],points[b]) for a,b in zip(route,route[1:]))


def _components(size,edges,solution):
    graph=[[] for _ in range(size)]
    for (a,b),selected in zip(edges,solution):
        if selected>.5:
            graph[a].append(b)
            graph[b].append(a)
    if any(len(neighbors)!=2 for neighbors in graph):
        raise ValueError('MILP incumbent does not satisfy the integral degree constraints')
    remaining=set(range(size))
    components=[]
    while remaining:
        todo=[min(remaining)]
        component=set()
        while todo:
            node=todo.pop()
            if node in component:continue
            component.add(node)
            todo.extend(graph[node])
        remaining-=component
        components.append(component)
    return graph,components


def _path(graph,dummy):
    path=[0]
    previous=dummy
    while True:
        nxt=next(node for node in graph[path[-1]] if node!=previous)
        if nxt==dummy:break
        previous=path[-1]
        path.append(nxt)
    if len(path)!=dummy or len(set(path))!=dummy:
        raise ValueError('Decoded path is not a Hamilton path')
    return path


def optimize(outer_count,seconds):
    points=ring_points(outer_count)
    size=len(points)+1
    dummy=size-1
    edges=[(a,b) for a in range(size) for b in range(a+1,size)]
    objective=np.array([0. if b==dummy else math.dist(points[a],points[b]) for a,b in edges])
    lower=np.zeros(len(edges));upper=np.ones(len(edges))
    fixed=edges.index((0,dummy));lower[fixed]=upper[fixed]=1.
    degree_rows=[];degree_columns=[]
    for index,(a,b) in enumerate(edges):
        degree_rows.extend((a,b));degree_columns.extend((index,index))
    degree=coo_matrix((np.ones(2*len(edges)),(degree_rows,degree_columns)),shape=(size,len(edges))).tocsr()
    initial=[0]+list(range(8,0,-1))+list(range(9,len(points)))
    best_route=initial[:]
    initial_length=route_length(points,initial)
    best_length=initial_length
    cuts=[];cut_sets=set();history=[]
    bound=0.;optimal=False;started=time.perf_counter();iteration=0
    while time.perf_counter()-started<seconds:
        iteration+=1
        remaining=seconds-(time.perf_counter()-started)
        if remaining<=0:break
        matrices=[degree,coo_matrix(objective.reshape(1,-1)).tocsr()]
        lows=[np.full(size,2.),np.array([-np.inf])]
        highs=[np.full(size,2.),np.array([best_length+1e-6])]
        if cuts:
            row_ids=[];columns=[]
            for row,component in enumerate(cuts):
                for column,(a,b) in enumerate(edges):
                    if a in component and b in component:
                        row_ids.append(row);columns.append(column)
            matrices.append(coo_matrix((np.ones(len(columns)),(row_ids,columns)),shape=(len(cuts),len(edges))).tocsr())
            lows.append(np.full(len(cuts),-np.inf))
            highs.append(np.array([len(component)-1 for component in cuts],dtype=float))
        result=milp(objective,integrality=np.ones(len(edges)),bounds=Bounds(lower,upper),
                    constraints=LinearConstraint(vstack(matrices),np.concatenate(lows),np.concatenate(highs)),
                    options=dict(time_limit=max(.01,remaining),mip_rel_gap=1e-8,disp=False))
        dual=getattr(result,'mip_dual_bound',None)
        if dual is not None and math.isfinite(dual):bound=max(bound,float(dual))
        item=dict(iteration=iteration,status=int(result.status),message=str(result.message),
                  elapsed_s=time.perf_counter()-started,subtour_cuts=len(cuts))
        if result.x is None:
            item['incumbent']='unavailable'
            history.append(item)
            break
        graph,components=_components(size,edges,result.x)
        item['component_sizes']=[len(component) for component in components]
        item['relaxation_incumbent_m']=float(result.fun)
        if len(components)==1:
            path=_path(graph,dummy)
            length=route_length(points,path)
            if length<best_length:best_route=path;best_length=length
            optimal=result.status==0
            item['connected_open_route_m']=length
            history.append(item)
            break
        history.append(item)
        for component in components:
            key=frozenset(component)
            if key not in cut_sets:
                cuts.append(component);cut_sets.add(key)
        if result.status not in (0,1):break
    elapsed=time.perf_counter()-started
    # Keep the known feasible route if time expired before a connected incumbent.
    gap=max(0.,(best_length-bound)/best_length)
    return dict(point_set='ring25' if outer_count==16 else 'compact21',station_count=len(points),
                origin_index=0,endpoint_free=True,points_m=points,initial_route_indices=initial,
                initial_route_m=initial_length,route_indices=best_route,
                route_points_m=[points[index] for index in best_route],open_route_m=best_length,
                saved_distance_m=initial_length-best_length,saved_move_time_s=(initial_length-best_length)/5,
                lower_bound_m=bound,solver_gap=gap,optimality_proved=optimal,
                elapsed_s=elapsed,iterations=iteration,history=history,
                connected_route_validated=(best_route[0]==0 and len(best_route)==len(points)
                                           and set(best_route)==set(range(len(points)))))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=20.,help='Maximum solve seconds for each fixed point set')
    parser.add_argument('--output',type=Path,default=HERE/'geometry_route_opt_results.json')
    args=parser.parse_args(argv)
    if args.seconds<=0:parser.error('--seconds must be positive')
    results=[]
    for outer_count in (16,12):
        row=optimize(outer_count,args.seconds)
        results.append(row)
        print(json.dumps({key:row[key] for key in ('point_set','initial_route_m','open_route_m','saved_distance_m',
                                                 'solver_gap','optimality_proved','elapsed_s')},ensure_ascii=False),flush=True)
    report=dict(kind='fixed_point_set_open_route_milp',simulator_scenarios_used=False,
                coverage_unchanged='Only order of the supplied fixed points is optimized',
                seconds_per_set=args.seconds,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                results=results)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
