"""New, preregistered P4 transfer round; separate from the prior CostAware round."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
import cost_experiment as previous

HERE=Path(__file__).resolve().parent

def make(v):
    from strategy_fast import FastP4
    from strategy_finish import FinishP4
    return FastP4() if v=='FastP4' else FinishP4(enabled=v in ('TailP4','FinishP4'), trim_corners=v in ('GridP4','FinishP4'))

def run(job):
    previous.make=make
    return previous.run_case(job)

def specs(stage):
    if stage=='development':
        return [dict(seed=946000+i,N=10+i%7,dir_frac=(.25,.5,.75,1.)[i%4],error_mode=('random','fixed','edge')[i%3],reception_range=[1000,1500]) for i in range(14)]
    grid=list(itertools.product(range(10,17),(.25,.5,.75,1.),('fixed','edge')))
    if stage=='confirmation':
        return [dict(seed=947000+i,N=n,dir_frac=f,error_mode=m,reception_range=[1000,1500]) for i,(n,f,m) in enumerate(grid)]
    return [dict(seed=948000+100*j+i,N=n,dir_frac=f,error_mode=m,reception_range=[radius,radius]) for j,radius in enumerate((1000,1500)) for i,(n,f,m) in enumerate(grid)]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=['development','confirmation','boundary'],required=True)
    p.add_argument('--workers',type=int,default=3);p.add_argument('--label');a=p.parse_args()
    out=HERE/'transfer_round'/(a.label or a.stage);out.mkdir(exist_ok=False);(out/'runs').mkdir()
    variants=['FastP4','off','TailP4','GridP4','FinishP4'] if a.stage=='development' else ['FastP4','GridP4','FinishP4']
    manifest=dict(stage=a.stage,started=datetime.now(timezone.utc).isoformat(),specs=specs(a.stage),variants=variants,
                  code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
                  gate=dict(full_clear_and_normal=True,min_mean_T_per_N_gain=.05,max_single_T_increase=.1))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for row in pool.map(run,[(s,v,out/'runs') for s in manifest['specs'] for v in variants]):
            rows.append(row);print(f"{len(rows)} {row['variant']} {row['scenario']['seed']} accepted={row['accepted_run']} T={row['virtual_time_s']:.2f}",flush=True)
    report=dict(manifest=manifest,records=rows,summary=previous.summarize(rows))
    s=report['summary'];gain=1-s['FinishP4']['mean_T_per_N']/s['FastP4']['mean_T_per_N']
    report['gate']=dict(gain=gain,worst=s['FinishP4']['worst_regression_fraction'],passed=all(r['accepted_run'] for r in rows) and gain>=.05 and s['FinishP4']['worst_regression_fraction']<=.1)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(summary=report['summary'],gate=report['gate']),ensure_ascii=False,indent=2))
    return 0 if all(r['accepted_run'] for r in rows) else 1

if __name__=='__main__':sys.exit(main())
