"""Bounded, standalone P4 experiment. Never connects to the real simulator."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import inspect
import itertools
import json
from pathlib import Path
import random
import statistics
import time

HERE=Path(__file__).resolve().parent
NORMAL={'all_channels_cleared_or_covered','cleared_maximum_16'}

def make(variant):
    from strategy_fast import FastP4
    from strategy_cost import CostAwareP4
    if variant=='FastP4':return FastP4()
    return CostAwareP4(enable_a='A' in variant,enable_b='B' in variant,enable_c='C' in variant)

def specs(stage):
    if stage=='development':
        return [dict(seed=942000+i,N=10+i%7,dir_frac=(.25,.5,.75,1.)[i%4],
                     error_mode=('random','fixed','edge')[i%3],reception_range=[1000,1500]) for i in range(14)]
    grid=list(itertools.product(range(10,17),(.25,.5,.75,1.),('fixed','edge')))
    if stage=='confirmation':
        return [dict(seed=943000+i,N=n,dir_frac=f,error_mode=m,reception_range=[1000,1500]) for i,(n,f,m) in enumerate(grid)]
    return [dict(seed=944000+i+100*j,N=n,dir_frac=f,error_mode=m,reception_range=[r,r])
            for j,r in enumerate((1000,1500)) for i,(n,f,m) in enumerate(grid)]

def run_case(job):
    spec,variant,out=job
    from mock_simulator_p4 import P4MockSimulator
    from robot_iter import run_with_sim_strategy
    random.seed(spec['seed']) # deterministic legacy MEC shuffle, isolated per run
    strategy=make(variant)
    actual=dict(actual_class=type(strategy).__name__,source=Path(inspect.getfile(type(strategy))).name,
                name=strategy.name)
    sim=P4MockSimulator(seed=spec['seed'],n_sources=spec['N'],dir_frac=spec['dir_frac'],
                        error_mode=spec['error_mode'],reception_range=spec['reception_range'])
    assert all(spec['reception_range'][0]<=s['re']<=spec['reception_range'][1] for s in sim.sources.values())
    trace=[]
    class Recorder:
        def enter(self):return sim.enter()
        def exit(self):return sim.exit()
        def stats(self):return sim.stats()
        def action(self,kind,x,y,ch):
            before=sim.virtual_time_s;old=sim.pos;old_ch=sim.ch
            response=getattr(sim,kind)(x,y,ch)
            cost=dict(move_time_s=((x-old[0])**2+(y-old[1])**2)**.5/5,
                      switch_time_s=float(kind=='measure' and old_ch!=ch),
                      measure_time_s=5. if kind=='measure' else 0.,
                      clear_time_s=(5. if response.get('clear_result')=='success' else 3.) if kind=='clear' else 0.)
            trace.append(dict(action=kind,pos=[x,y],ch=ch,result=response.get('measure_result',response.get('clear_result')),
                              svd_deg=response.get('svd_deg'),virtual_time_s=sim.virtual_time_s,
                              delta_time_s=sim.virtual_time_s-before,cost=cost,
                              stage=getattr(strategy,'action_stage',strategy.phase)))
            return response
        def measure(self,x,y,ch):return self.action('measure',x,y,ch)
        def clear(self,x,y,ch):return self.action('clear',x,y,ch)
    error=None;start=time.perf_counter()
    try:
        result=run_with_sim_strategy(strategy,Recorder(),max_steps=8000)
        result.pop('log',None)
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        result=dict(stop_reason='error',cleared=len(sim.cleared),virtual_time_s=sim.virtual_time_s)
    costs={k:sum(t['cost'][k] for t in trace) for k in ('move_time_s','switch_time_s','measure_time_s','clear_time_s')}
    stages={stage:{k:sum(t['cost'][k] for t in trace if t['stage']==stage) for k in costs} for stage in sorted({t['stage'] for t in trace})}
    result.update(**actual,scenario=spec,variant=variant,error=error,wall_s=time.perf_counter()-start,
                  full_clear=len(sim.cleared)==spec['N'],normal_stop=error is None and result['stop_reason'] in NORMAL,
                  T_per_N=sim.virtual_time_s/spec['N'],time_breakdown=costs,stage_costs=stages,
                  distance_m=costs['move_time_s']*5,measure_count=sum(t['action']=='measure' for t in trace),
                  clear_fail_count=sum(t['result']=='no_target_in_range' for t in trace),
                  diagnostics=strategy.diagnostics() if hasattr(strategy,'diagnostics') else {})
    result['accepted_run']=result['full_clear'] and result['normal_stop']
    assert abs(sum(costs.values())-sim.virtual_time_s)<1e-5
    path=Path(out)/f"{spec['seed']}_{variant}.json"
    path.write_text(json.dumps(dict(summary=result,actions=trace),ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def summarize(rows):
    result={};base={r['scenario']['seed']:r for r in rows if r['variant']=='FastP4'}
    for v in sorted({r['variant'] for r in rows}):
        group=[r for r in rows if r['variant']==v]
        paired=[(r['virtual_time_s']/base[r['scenario']['seed']]['virtual_time_s']-1,r['scenario']['seed']) for r in group]
        values=sorted(r['T_per_N'] for r in group)
        result[v]=dict(rounds=len(group),full_clear=sum(r['full_clear'] for r in group),normal_stop=sum(r['normal_stop'] for r in group),
          accepted=sum(r['accepted_run'] for r in group),mean_T_per_N=statistics.mean(values),
          mean_T=statistics.mean(r['virtual_time_s'] for r in group),p95_T_per_N=values[math_ceil(.95*len(values))-1],
          p95_T=sorted(r['virtual_time_s'] for r in group)[math_ceil(.95*len(group))-1],
          by_N={str(n):statistics.mean(r['T_per_N'] for r in group if r['scenario']['N']==n) for n in range(10,17)},
          mean_distance_m=statistics.mean(r['distance_m'] for r in group),mean_measure=statistics.mean(r['measure_count'] for r in group),
          total_clear_failures=sum(r['clear_fail_count'] for r in group),worst_regression_fraction=max(paired)[0],worst_seed=max(paired)[1],
          regressions=[dict(seed=seed,fraction=d) for d,seed in paired if d>1e-9],
          failures=[r['scenario']['seed'] for r in group if not r['accepted_run']],
          mean_cost={k:statistics.mean(r['time_breakdown'][k] for r in group) for k in group[0]['time_breakdown']},
          stages={s:{k:sum(r['stage_costs'].get(s,{}).get(k,0) for r in group)/len(group) for k in group[0]['time_breakdown']} for s in sorted({s for r in group for s in r['stage_costs']})},
          triggers={k:sum(r['diagnostics'].get('triggers',{}).get(k,0) for r in group) for k in sorted({k for r in group for k in r['diagnostics'].get('triggers',{})})})
    if 'ABC' in result and 'AB' in result:
        ab={r['scenario']['seed']:r for r in rows if r['variant']=='AB'}
        abc=[r for r in rows if r['variant']=='ABC']
        worst=max(r['virtual_time_s']/ab[r['scenario']['seed']]['virtual_time_s']-1 for r in abc)
        improvement=1-result['ABC']['mean_T_per_N']/result['AB']['mean_T_per_N']
        result['C_gate']=dict(improvement_vs_AB=improvement,worst_regression_vs_AB=worst,
            pass_gate=result['ABC']['accepted']==len(abc) and result['AB']['accepted']==len(abc) and improvement>=.05 and worst<=.10)
    return result

def math_ceil(x):
    import math
    return math.ceil(x)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=('development','confirmation','boundary'),default='development')
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--output',type=Path)
    p.add_argument('--single',type=int,help='single fixed-error FastP4 run for portability check')
    a=p.parse_args()
    if a.single is not None:
        out=a.output or HERE/'cost_round/portable';out.mkdir(parents=True,exist_ok=True)
        row=run_case((dict(seed=a.single,N=10,dir_frac=.5,error_mode='fixed',reception_range=[1000,1500]),'FastP4',out))
        print(json.dumps(row,ensure_ascii=False));return
    out=a.output or HERE/'cost_round'/a.stage
    out.mkdir(parents=True,exist_ok=False);(out/'runs').mkdir()
    variants=['FastP4','off','A','B','AB','ABC'] if a.stage=='development' else ['FastP4','AB','ABC']
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
    manifest=dict(stage=a.stage,scenarios=specs(a.stage),variants=variants,sha256=hashes,
                  C_gate=dict(min_mean_T_per_N_gain=.05,max_single_T_increase=.10),confirmation_policy='one pass; no retuning after confirmation')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for row in pool.map(run_case,[(s,v,out/'runs') for s in manifest['scenarios'] for v in variants]):
            rows.append(row)
            print(f"{len(rows)} {row['variant']} seed={row['scenario']['seed']} clear={row['cleared']} normal={row['normal_stop']} T={row['virtual_time_s']:.2f}",flush=True)
    report=dict(manifest=manifest,summary=summarize(rows),records=rows)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2),flush=True)
    return 0 if all(r['accepted_run'] for r in rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
