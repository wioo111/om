"""Frozen P4 route round 2, offline only; each stage is explicitly requested.

Development uses only 14 new scenarios. Confirmation/boundary are separate
invocations with new seeds and are never launched automatically. The generic
Hunt recorder is reused, but both its factory and its dependencies are loaded
from the label's saved source folder. Existing evaluators are not modified.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import importlib.util
import inspect
import itertools
import json
from pathlib import Path
import sys
import traceback


HERE=Path(__file__).resolve().parent
VARIANTS=('HuntP4','RouteAwareP4','RouteProbeP4','FinishP4','FastP4')
_FROZEN_RUNNER=None
_FACTORY_INFO={}


def make(variant):
    if variant=='HuntP4':
        from strategy_hunt import HuntP4
        return HuntP4()
    if variant=='RouteAwareP4':
        from strategy_route import RouteAwareP4
        return RouteAwareP4()
    if variant=='RouteProbeP4':
        from strategy_route_probe import RouteProbeP4
        return RouteProbeP4()
    if variant=='FinishP4':
        from strategy_finish import FinishP4
        return FinishP4(enabled=True,trim_corners=True)
    if variant=='FastP4':
        from strategy_fast import FastP4
        return FastP4()
    raise ValueError(f'Unknown variant: {variant}')


def specs(stage):
    if stage=='development':
        return [dict(seed=961000+i,N=10+i%7,dir_frac=(.25,.5,.75,1.)[i%4],
                     error_mode=('random','fixed','edge')[i%3],reception_range=[1000,1500]) for i in range(14)]
    grid=list(itertools.product(range(10,17),(.25,.5,.75,1.),('fixed','edge')))
    if stage=='confirmation':
        return [dict(seed=962000+i,N=n,dir_frac=f,error_mode=m,reception_range=[1000,1500])
                for i,(n,f,m) in enumerate(grid)]
    if stage=='boundary':
        return [dict(seed=963000+100*j+i,N=n,dir_frac=f,error_mode=m,reception_range=[radius,radius])
                for j,radius in enumerate((1000,1500)) for i,(n,f,m) in enumerate(grid)]
    raise ValueError(f'Unknown stage: {stage}')


def _load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def _frozen_worker_init(source):
    global _FROZEN_RUNNER,_FACTORY_INFO
    source=Path(source).resolve()
    sys.path.insert(0,str(source))
    # Spawned workers start clean, but explicitly evict local modules as well so
    # callers cannot accidentally reuse a policy previously imported elsewhere.
    for path in source.glob('*.py'):
        if path.stem not in (__name__,'__main__','__mp_main__'):
            sys.modules.pop(path.stem,None)
    frozen_factory=_load(source/'route_round2_experiment.py','route_round2_saved_factory')
    runner=_load(source/'hunt_experiment.py','route_round2_saved_hunt_runner')
    runner._frozen_worker_init(source)
    runner.make=frozen_factory.make
    factory_source=Path(inspect.getfile(runner.make)).resolve()
    if factory_source!=source/'route_round2_experiment.py':
        raise RuntimeError('Factory was not loaded from the frozen source folder')
    _FACTORY_INFO=dict(factory_source=str(factory_source),
                       factory_sha256=hashlib.sha256(factory_source.read_bytes()).hexdigest())
    _FROZEN_RUNNER=runner


def run(job):
    if _FROZEN_RUNNER is None:raise RuntimeError('Frozen worker initializer was not called')
    row=_FROZEN_RUNNER.run(job)
    row.update(_FACTORY_INFO)
    return row


def summarize(rows,source=None):
    """Reuse all-run metrics and add the currently deployed HuntP4 comparison."""
    source=Path(source) if source is not None else HERE
    helper=_load(source/'hunt_experiment.py','route_round2_summary_helper')
    summary=helper.summarize(rows)
    references={name:{row['scenario']['seed']:row for row in rows if row['variant']==name}
                for name in ('HuntP4','FastP4','FinishP4')}
    for variant,value in summary.items():
        group=[row for row in rows if row['variant']==variant]
        value['comparisons']={name:helper._paired(group,reference,name) for name,reference in references.items()}
        measured=[row for row in group if row.get('metrics_available',True)]
        if measured:
            value['total_T']=sum(row['virtual_time_s'] for row in measured)
            value['weighted_T_per_N']=value['total_T']/sum(row['scenario']['N'] for row in measured)
            value['worst_T_per_N']=max(row['T_per_N'] for row in measured)
            value['by_N_worst_T_per_N']={str(n):max(row['T_per_N'] for row in measured if row['scenario']['N']==n)
                                        for n in sorted({row['scenario']['N'] for row in measured})}
    return summary


def _freeze(out,variants):
    source=out/'source'
    source.mkdir()
    files=sorted(list(HERE.glob('*.py'))+list(HERE.glob('requirements*.txt')))
    hashes={}
    for path in files:
        data=path.read_bytes()
        (source/path.name).write_bytes(data)
        hashes[path.name]=hashlib.sha256(data).hexdigest()
    required=['route_round2_experiment.py','hunt_experiment.py','cost_experiment.py',
              'mock_simulator_p4.py','robot_iter.py','strategy.py','strategy_hunt.py',
              'problem1_v4_inline.py']
    if 'RouteAwareP4' in variants:required.append('strategy_route.py')
    missing=[name for name in required if name not in hashes]
    if missing:raise RuntimeError('Missing frozen dependencies: '+', '.join(missing))
    return hashes


def _job_key(scenario,variant):
    return (scenario['seed'],variant)


def _worker_error(job,exc):
    scenario,variant,out=job
    row=dict(scenario=scenario,variant=variant,error=f'{type(exc).__name__}: {exc}',
             stop_reason='worker_error',full_clear=False,normal_stop=False,
             accepted_run=False,metrics_available=False)
    (Path(out)/f"{scenario['seed']}_{variant}.worker_error.json").write_text(
        json.dumps(dict(summary=row,traceback=traceback.format_exc()),ensure_ascii=False,indent=2),encoding='utf-8')
    return row


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('development','confirmation','boundary'),required=True)
    parser.add_argument('--label',help='New label below route_round2; existing labels are never overwritten')
    parser.add_argument('--variants',choices=VARIANTS,nargs='+',default=['HuntP4','RouteAwareP4'])
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args(argv)
    if args.workers<1:parser.error('--workers must be positive')
    if len(args.variants)!=len(set(args.variants)):parser.error('--variants must not contain duplicates')
    label=args.label or args.stage
    if label in ('.','..') or Path(label).name!=label or '/' in label or '\\' in label:
        parser.error('--label must be a single directory name')
    root=HERE/'route_round2'
    root.mkdir(exist_ok=True)
    out=root/label
    out.mkdir(exist_ok=False)
    (out/'runs').mkdir()
    hashes=_freeze(out,args.variants)
    scenarios=specs(args.stage)
    manifest=dict(stage=args.stage,label=label,started=datetime.now(timezone.utc).isoformat(),
                  scenarios=scenarios,variants=args.variants,code_sha256=hashes,
                  execution_source=str(out/'source'),factory_source='source/route_round2_experiment.py',
                  factory_sha256=hashes['route_round2_experiment.py'],
                  dynamic_dependency_sha256={'problem1_v4_inline.py':hashes['problem1_v4_inline.py']},
                  command=['route_round2_experiment.py']+(list(argv) if argv is not None else sys.argv[1:]),
                  comparison_references=['HuntP4','FastP4','FinishP4'],
                  development_policy='Use only these same 14 new development scenarios to fix parameters',
                  confirmation_policy='Explicit invocation only; new seeds; do not retune on confirmation then call it independent',
                  acceptance='full_clear AND normal_stop; step_limit is not accepted',
                  target=dict(mean_T_per_N_s=[300,400]),
                  metric_policy='all runs with measured costs including failures; unavailable costs are not replaced by zero')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'execution.json').write_text(json.dumps(dict(status='running',started=manifest['started'])),encoding='utf-8')
    jobs=[(scenario,variant,out/'runs') for scenario in scenarios for variant in args.variants]
    rows=[];interrupted=False;fatal_error=None
    pool=ProcessPoolExecutor(max_workers=args.workers,initializer=_frozen_worker_init,initargs=(out/'source',))
    try:
        futures={pool.submit(run,job):job for job in jobs}
        for future in as_completed(futures):
            job=futures[future]
            try:row=future.result()
            except Exception as exc:row=_worker_error(job,exc)
            rows.append(row)
            with (out/'progress.jsonl').open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            cost=f"{row['virtual_time_s']:.2f}" if row.get('metrics_available') else 'unavailable'
            print(f"{len(rows)}/{len(jobs)} {row['variant']} seed={row['scenario']['seed']} accepted={row['accepted_run']} T={cost}",flush=True)
    except KeyboardInterrupt:
        interrupted=True
        fatal_error='Interrupted by user; saved run files are retained, and already running workers may still finish'
    except Exception as exc:
        interrupted=True
        fatal_error=f'{type(exc).__name__}: {exc}'
        (out/'experiment_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        pool.shutdown(wait=not interrupted,cancel_futures=interrupted)
        completed={_job_key(row['scenario'],row['variant']) for row in rows}
        pending=[dict(scenario=scenario,variant=variant) for scenario,variant,_ in jobs
                 if _job_key(scenario,variant) not in completed]
        status='complete' if not pending and not interrupted else 'incomplete'
        report=dict(manifest=manifest,finished=datetime.now(timezone.utc).isoformat(),status=status,
                    expected_runs=len(jobs),observed_runs=len(rows),records=rows,pending_runs=pending,
                    summary=summarize(rows,out/'source'))
        if fatal_error:report['error']=fatal_error
        report_name='report.json' if status=='complete' else 'partial_report.json'
        (out/report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (out/'execution.json').write_text(json.dumps(dict(status=status,finished=report['finished'],
                                                         completed_runs=len(rows),expected_runs=len(jobs),report=report_name),
                                                    ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2,allow_nan=False),flush=True)
    return 0 if report['status']=='complete' and all(row['accepted_run'] for row in rows) else 130 if interrupted else 1


if __name__=='__main__':
    raise SystemExit(main())
