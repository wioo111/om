"""Frozen, offline P4 comparison. Each stage requires an explicit invocation."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import statistics
import sys
import time
import traceback

import cost_experiment as previous

HERE=Path(__file__).resolve().parent
VARIANTS=('FastP4','FinishP4','MeshP4','HuntP4')
COST_KEYS=('move_time_s','switch_time_s','measure_time_s','clear_time_s')


def make(variant):
    if variant=='FastP4':
        from strategy_fast import FastP4
        return FastP4()
    if variant=='FinishP4':
        from strategy_finish import FinishP4
        return FinishP4(enabled=True,trim_corners=True)
    if variant in ('MeshP4','HuntP4'):
        from strategy_hunt import HuntP4
        return HuntP4(hunt=variant=='HuntP4')
    raise ValueError(f'Unknown variant: {variant}')


def specs(stage):
    if stage=='development':
        return [dict(seed=951000+i,N=10+i%7,dir_frac=(.25,.5,.75,1.)[i%4],
                     error_mode=('random','fixed','edge')[i%3],reception_range=[1000,1500])
                for i in range(14)]
    grid=list(itertools.product(range(10,17),(.25,.5,.75,1.),('fixed','edge')))
    if stage=='confirmation':
        return [dict(seed=952000+i,N=n,dir_frac=f,error_mode=m,reception_range=[1000,1500])
                for i,(n,f,m) in enumerate(grid)]
    if stage=='boundary':
        return [dict(seed=953000+100*j+i,N=n,dir_frac=f,error_mode=m,reception_range=[radius,radius])
                for j,radius in enumerate((1000,1500)) for i,(n,f,m) in enumerate(grid)]
    raise ValueError(f'Unknown stage: {stage}')


def _frozen_worker_init(source):
    """Import every simulator/strategy dependency from this label's saved code."""
    global previous
    source=Path(source)
    sys.path.insert(0,str(source))
    module_spec=importlib.util.spec_from_file_location('hunt_frozen_cost_experiment',source/'cost_experiment.py')
    previous=importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(previous)


def run(job):
    scenario,variant,out=job
    original=previous.make
    previous.make=make
    started=time.perf_counter()
    try:
        row=previous.run_case(job)
        row['metrics_available']=True
        return row
    except Exception as exc:
        # run_case already retains in-run policy failures. Preserve setup,
        # accounting, and recording failures too, without inventing costs.
        row=dict(scenario=scenario,variant=variant,error=f'{type(exc).__name__}: {exc}',
                 stop_reason='experiment_error',full_clear=False,normal_stop=False,
                 accepted_run=False,metrics_available=False,wall_s=time.perf_counter()-started)
        path=Path(out)/f"{scenario['seed']}_{variant}.error.json"
        path.write_text(json.dumps(dict(summary=row,traceback=traceback.format_exc()),
                                   ensure_ascii=False,indent=2),encoding='utf-8')
        return row
    finally:
        previous.make=original


def _p95(values):
    values=sorted(values)
    return values[math.ceil(.95*len(values))-1]


def _paired(group,reference,reference_name):
    if not reference:
        return dict(status='reference_not_selected',reference=reference_name,paired_rounds=0)
    pairs=[(row,reference[row['scenario']['seed']]) for row in group
           if row['scenario']['seed'] in reference and row.get('metrics_available',True)
           and reference[row['scenario']['seed']].get('metrics_available',True)]
    if not pairs:
        return dict(status='no_pair_with_measured_costs',reference=reference_name,paired_rounds=0)
    regressions=[dict(seed=row['scenario']['seed'],N=row['scenario']['N'],
                      reception_range=row['scenario']['reception_range'],
                      fraction=row['virtual_time_s']/base['virtual_time_s']-1,
                      delta_T_s=row['virtual_time_s']-base['virtual_time_s'],
                      candidate_accepted=row['accepted_run'],reference_accepted=base['accepted_run'])
                 for row,base in pairs]
    worst=max(regressions,key=lambda row:row['fraction'])
    mean_candidate=statistics.mean(row['T_per_N'] for row,_ in pairs)
    mean_reference=statistics.mean(base['T_per_N'] for _,base in pairs)
    return dict(status='complete' if len(pairs)==len(group) else 'partial_missing_costs',
                reference=reference_name,paired_rounds=len(pairs),
                mean_T_per_N_improvement_fraction=1-mean_candidate/mean_reference,
                mean_T_improvement_fraction=1-statistics.mean(row['virtual_time_s'] for row,_ in pairs)
                                              /statistics.mean(base['virtual_time_s'] for _,base in pairs),
                p95_regression_fraction=_p95([row['fraction'] for row in regressions]),
                worst_regression_fraction=worst['fraction'],worst_seed=worst['seed'],
                worst_case=worst,regressions=[row for row in regressions if row['fraction']>1e-9],
                all_pairs_accepted=all(row['accepted_run'] and base['accepted_run'] for row,base in pairs))


def summarize(rows):
    """All measured runs contribute, including failures; no baseline is mandatory."""
    summary={}
    references={name:{r['scenario']['seed']:r for r in rows if r['variant']==name}
                for name in ('FastP4','FinishP4')}
    for variant in sorted({r['variant'] for r in rows}):
        group=[r for r in rows if r['variant']==variant]
        measured=[r for r in group if r.get('metrics_available',True)]
        result=dict(rounds=len(group),full_clear=sum(r['full_clear'] for r in group),
                    normal_stop=sum(r['normal_stop'] for r in group),accepted=sum(r['accepted_run'] for r in group),
                    metric_rounds=len(measured),unmeasured_rounds=len(group)-len(measured),
                    metric_population='all runs with recorded costs, including failures',
                    failures=[dict(seed=r['scenario']['seed'],scenario=r['scenario'],
                                   stop_reason=r['stop_reason'],error=r.get('error') or 'acceptance_failed',
                                   metrics_available=r.get('metrics_available',True))
                              for r in group if not r['accepted_run']],
                    comparisons={name:_paired(group,reference,name) for name,reference in references.items()})
        if measured:
            # These are the same cost/outcome metrics as cost_experiment.summarize,
            # generalized to subsets without FastP4 and to unmeasured setup errors.
            result.update(mean_T_per_N=statistics.mean(r['T_per_N'] for r in measured),
                          mean_T=statistics.mean(r['virtual_time_s'] for r in measured),
                          p95_T_per_N=_p95([r['T_per_N'] for r in measured]),
                          p95_T=_p95([r['virtual_time_s'] for r in measured]),
                          by_N={str(n):statistics.mean(r['T_per_N'] for r in measured if r['scenario']['N']==n)
                                for n in sorted({r['scenario']['N'] for r in measured})},
                          by_N_rounds={str(n):sum(r['scenario']['N']==n for r in measured)
                                       for n in sorted({r['scenario']['N'] for r in measured})},
                          mean_distance_m=statistics.mean(r['distance_m'] for r in measured),
                          mean_measure=statistics.mean(r['measure_count'] for r in measured),
                          mean_clear_failures=statistics.mean(r['clear_fail_count'] for r in measured),
                          total_clear_failures=sum(r['clear_fail_count'] for r in measured),
                          mean_cost={key:statistics.mean(r['time_breakdown'][key] for r in measured) for key in COST_KEYS},
                          stages={stage:{key:sum(r['stage_costs'].get(stage,{}).get(key,0) for r in measured)/len(measured)
                                         for key in COST_KEYS}
                                  for stage in sorted({s for r in measured for s in r['stage_costs']})},
                          triggers={key:sum(r['diagnostics'].get('triggers',{}).get(key,0) for r in measured)
                                    for key in sorted({k for r in measured for k in r['diagnostics'].get('triggers',{})})})
        summary[variant]=result
    return summary


def _freeze(out):
    source=out/'source'
    source.mkdir()
    hashes={}
    files=list(HERE.glob('*.py'))+list(HERE.glob('requirements*.txt'))
    for path in sorted(files):
        data=path.read_bytes()
        (source/path.name).write_bytes(data)
        hashes[path.name]=hashlib.sha256(data).hexdigest()
    return hashes


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('development','confirmation','boundary'),required=True)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--label',help='New directory name below hunt_round; never overwrites a previous label')
    parser.add_argument('--variants',nargs='+',choices=VARIANTS,default=list(VARIANTS))
    args=parser.parse_args(argv)
    if args.workers<1:parser.error('--workers must be positive')
    if len(set(args.variants))!=len(args.variants):parser.error('--variants must not contain duplicates')
    label=args.label or args.stage
    if label in ('.','..') or Path(label).name!=label or '/' in label or '\\' in label:
        parser.error('--label must be a single directory name')
    root=HERE/'hunt_round'
    root.mkdir(exist_ok=True)
    out=root/label
    out.mkdir(exist_ok=False)
    (out/'runs').mkdir()
    hashes=_freeze(out)
    scenarios=specs(args.stage)
    manifest=dict(stage=args.stage,label=label,started=datetime.now(timezone.utc).isoformat(),
                  scenarios=scenarios,variants=args.variants,code_sha256=hashes,
                  execution_source=str(out/'source'),command=sys.argv,
                  confirmation_policy='explicit invocation only; one pass; do not tune on confirmation and relabel it independent',
                  acceptance='full_clear AND normal_stop; step_limit is not accepted',
                  target=dict(mean_T_per_N_s=[300,400]),
                  comparison_references=['FastP4','FinishP4'],
                  metric_policy='all measured runs including failures; setup errors retained with costs unavailable')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    jobs=[(scenario,variant,out/'runs') for scenario in scenarios for variant in args.variants]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=_frozen_worker_init,initargs=(out/'source',)) as pool:
        for row in pool.map(run,jobs):
            rows.append(row)
            with (out/'progress.jsonl').open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            cost=f"{row['virtual_time_s']:.2f}" if row['metrics_available'] else 'unavailable'
            print(f"{len(rows)}/{len(jobs)} {row['variant']} seed={row['scenario']['seed']} accepted={row['accepted_run']} T={cost}",flush=True)
    report=dict(manifest=manifest,finished=datetime.now(timezone.utc).isoformat(),
                records=rows,summary=summarize(rows))
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2,allow_nan=False),flush=True)
    return 0 if all(row['accepted_run'] for row in rows) else 1


if __name__=='__main__':
    raise SystemExit(main())
