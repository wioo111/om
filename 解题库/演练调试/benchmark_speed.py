"""CLI-only paired offline practice; no network, GUI, formal testing or source-truth policy input."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]

def run_case(spec):
    problem,variant,seed,n,mode,frac,folder,reception_range=spec[:8]
    reference_profile=spec[8] if len(spec)>8 else None
    module=REPO/'解题库'/('第三问/v10' if problem==3 else '第四问/v6')
    sys.path.insert(0,str(module))
    from robot_iter import run_with_sim_strategy
    if problem==3:
        from mock_simulator import MockSimulator
        from strategy_v8 import AdaptiveV8
        from strategy_fast import FastScanP3,CautiousP3,CompactP3
        from strategy_night import CachedScanP3,CoverP3,HopP3,MidpointP3,RouteP3
        from strategy_transit import ResidualP3,TransitP3,TransitResidualP3,TransitSparseP3
        from strategy_transit import TailResidualP3,TransitEagerP3,TailTransitP3
        from strategy_joint import ActionRouteP3,SurveyP3,JointP3
        from strategy_joint import ProbePlanP3,PlanJointP3
        from strategy_task import CardinalityP3,OpticalTaskP3,OpticalProbeP3
        from strategy_task import SharedBearingP3,SharedOpticalP3
        from strategy_task import BoundedOpticalP3
        factory={'baseline':AdaptiveV8,'scan':FastScanP3,'cautious':CautiousP3,'compact':CompactP3,
                 'cache':CachedScanP3,'cover':CoverP3,'hop':HopP3,'midpoint':MidpointP3,'route':RouteP3,
                 'residual':ResidualP3,'transit':TransitP3,'combined':TransitResidualP3,
                 'sparse':TransitSparseP3,'tail':TailResidualP3,'eager':TransitEagerP3,
                 'tail_transit':TailTransitP3,'action_route':ActionRouteP3,'survey':SurveyP3,
                 'joint':JointP3,'probe_plan':ProbePlanP3,'plan_joint':PlanJointP3,
                 'cardinality':CardinalityP3,'optical_task':OpticalTaskP3,'optical_probe':OpticalProbeP3,
                 'shared_bearing':SharedBearingP3,'shared_optical':SharedOpticalP3,
                 'bounded_optical':BoundedOpticalP3}[variant]
        if reference_profile is None:
            sim=MockSimulator(seed=seed,N=n,error_mode=mode,R_eff_range=reception_range)
        else:
            from p3_reference import reference_simulator
            sim=reference_simulator(seed,n,mode,reference_profile)
    else:
        from mock_simulator_p4 import P4MockSimulator
        from strategy_p4 import AdaptiveP4
        from strategy_fast import FastP4
        from strategy_cost import CostAwareP4
        factory={'baseline':AdaptiveP4,'fast':FastP4,'ab':lambda:CostAwareP4(True,True,False),'abc':lambda:CostAwareP4(True,True,True)}[variant]
        sim=P4MockSimulator(seed=seed,n_sources=n,dir_frac=frac,error_mode=mode,reception_range=reception_range)
    start=time.perf_counter();error=None;trace=[]
    try:
        strategy=factory()
        result=run_with_sim_strategy(strategy,sim,max_steps=8000)
        if hasattr(strategy,'diagnostics'):result['policy_diagnostics']=strategy.diagnostics()
        trace=result.pop('log',[])
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        result=sim.stats()
        result['virtual_time_s']=getattr(sim,'virtual_time_s',getattr(sim,'virtual_time',0.0))
        result['stop_reason']='error'
    result.pop('sources_truth',None)
    result.update(problem=problem,variant=variant,seed=seed,N=n,error_mode=mode,dir_frac=frac,
                  error=error,wall_s=time.perf_counter()-start,evaluation='offline_practice_not_official_simulator')
    result['full_clear']=error is None and result['cleared']==n
    if problem==4:
        result['normal_stop']=error is None and result.get('stop_reason') in ('all_channels_cleared_or_covered','cleared_maximum_16')
        result['accepted_run']=result['full_clear'] and result['normal_stop']
        result['actual_class']=type(strategy).__name__
        result['strategy_source']=str(Path(sys.modules[type(strategy).__module__].__file__).resolve())
    result['avg_time_per_cleared']=result['virtual_time_s']/result['cleared'] if result['cleared'] else None
    if problem==3:
        last_clear=next((r['virtual_time_s'] for r in reversed(trace)
                         if r['action']=='clear' and r['result']=='success'),None)
        result['post_last_clear_s']=result['virtual_time_s']-last_clear if last_clear is not None else None
        result['evaluation_model']='reference' if reference_profile is not None else 'uniform'
    path=Path(folder)/f'{seed}_{variant}.json'
    path.write_text(json.dumps(dict(summary=result,actions=trace),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--problem',type=int,choices=(3,4),required=True)
    p.add_argument('--variants',default='baseline,fast')
    p.add_argument('--cases',type=int,default=12)
    p.add_argument('--seed-start',type=int,required=True)
    p.add_argument('--label',required=True)
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--reference',default=None)
    p.add_argument('--error-modes',default='fixed,fixed,fixed,edge')
    p.add_argument('--reception-min',type=float,default=1000.)
    p.add_argument('--reception-max',type=float,default=1500.)
    args=p.parse_args()
    if Path(args.label).name!=args.label:p.error('label must be a directory name')
    if args.reference is None:args.reference='fast' if args.problem==4 else 'baseline'
    variants=args.variants.split(',')
    if args.reference not in variants:p.error('reference must be included in variants')
    if args.cases<1:p.error('cases must be positive')
    modes=args.error_modes.split(',')
    folder=ROOT/'results'/args.label;folder.mkdir(parents=True,exist_ok=False)
    traces=folder/'runs';traces.mkdir()
    module=REPO/'解题库'/('第三问/v10' if args.problem==3 else '第四问/v6')
    files=list(module.glob('*.py'))+list(ROOT.glob('*.py'))
    hashes={str(f.relative_to(REPO)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    for f in files:
        target=folder/'source'/f.relative_to(REPO);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    meta=dict(started=datetime.now(timezone.utc).isoformat(),command=sys.argv,code_sha256=hashes,
              evaluation='offline_practice_not_official_simulator',problem=args.problem)
    (folder/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    specs=[(args.problem,v,args.seed_start+i,10+i%7,modes[i%len(modes)],
            (.25,.5,.75,1.)[i%4],str(traces),(args.reception_min,args.reception_max)) for i in range(args.cases) for v in variants]
    if args.problem==4:
        from itertools import product
        modes=list(dict.fromkeys(modes))
        if any(m not in ('random','fixed','edge') for m in modes):p.error('P4 modes: random/fixed/edge')
        grid=list(product(range(10,17),(.25,.5,.75,1.),modes))
        if args.cases != len(grid):p.error(f'P4 Cartesian set requires --cases {len(grid)}')
        specs=[(4,v,args.seed_start+i,n,m,f,str(traces),(args.reception_min,args.reception_max)) for i,(n,f,m) in enumerate(grid) for v in variants]
    rows=[]
    with (folder/'progress.jsonl').open('w',encoding='utf-8') as progress:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(run_case,spec) for spec in specs]
            for future in as_completed(futures):
                row=future.result();rows.append(row)
                line=json.dumps({k:row.get(k) for k in ('variant','seed','N','cleared','full_clear','virtual_time_s','measure_count','wall_s','error')},ensure_ascii=False)
                progress.write(line+'\n');progress.flush();print(line,flush=True)
    summary={}
    baseline={r['seed']:r for r in rows if r['variant']==args.reference}
    for v in variants:
        group=[r for r in rows if r['variant']==v]
        good=group if args.problem==4 else [r for r in group if r['full_clear']]
        deltas=[r['virtual_time_s']-baseline[r['seed']]['virtual_time_s'] for r in good if args.problem==4 or baseline[r['seed']]['full_clear']]
        summary[v]=dict(rounds=len(group),full_clear=sum(r['full_clear'] for r in group),
            mean_virtual_s=statistics.mean(r['virtual_time_s'] for r in group),
            mean_wall_s=statistics.mean(r['wall_s'] for r in group),
            mean_measure=statistics.mean(r.get('measure_count',0) for r in group),
            clear_failures=sum(r.get('clear_fail_count',0) for r in group),
            paired_completed=len(deltas),mean_paired_delta_s=statistics.mean(deltas) if deltas else None,
            improved=sum(d<-.001 for d in deltas),worse=sum(d>.001 for d in deltas))
        if args.problem==4:
            import math
            regression=[(r['virtual_time_s']/baseline[r['seed']]['virtual_time_s']-1,r['seed']) for r in group]
            summary[v].update(normal_stop=sum(r['normal_stop'] for r in group),accepted=sum(r['accepted_run'] for r in group),
                mean_T_per_N=statistics.mean(r['virtual_time_s']/r['N'] for r in group),
                by_N={str(n):statistics.mean(r['virtual_time_s']/n for r in group if r['N']==n) for n in sorted({r['N'] for r in group})},
                mean_distance_m=statistics.mean(r.get('time_breakdown',{}).get('move_time_s',0)*5 for r in group),
                p95_T=sorted(r['virtual_time_s'] for r in group)[math.ceil(.95*len(group))-1],
                worst_regression_fraction=max(regression)[0],worst_seed=max(regression)[1])
    unchanged=hashes=={str(f.relative_to(REPO)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    exit_code=0 if unchanged and all(r.get('accepted_run',r['full_clear']) for r in rows) else 1
    report=dict(**meta,finished=datetime.now(timezone.utc).isoformat(),exit_code=exit_code,
                sources_unchanged=unchanged,summary=summary,records=rows)
    if args.problem==3:
        from p3_metrics import stratified
        report['stratified']=stratified(rows,args.reference)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    sys.exit(exit_code)

if __name__=='__main__':main()
