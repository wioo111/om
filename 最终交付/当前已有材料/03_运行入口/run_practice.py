"""Practice-only P3/P4 runner; never starts a simulator session or a formal test."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
DEFAULT_DATA=REPO/'Jammers-simulator-win64/Jammers-simulator/JammersSimulatorData'

def p4_strategy_metadata(strategy):
    """Describe the loaded object without assuming one particular candidate class."""
    source=Path(inspect.getfile(type(strategy))).resolve()
    try:source_label=str(source.relative_to(REPO))
    except ValueError:source_label=str(source)
    diagnostic=getattr(strategy,'diagnostics',None)
    diagnostic=diagnostic() if callable(diagnostic) else {}
    diagnostic=diagnostic if isinstance(diagnostic,dict) else {}
    # Config may be top-level (FinishP4) or nested (CostAwareP4).
    config={k:v for k,v in diagnostic.items() if isinstance(v,(bool,int,float,str))}
    for key in ('switches','config','settings'):
        if isinstance(diagnostic.get(key),dict):config[key]=diagnostic[key]
    return dict(actual_class=type(strategy).__name__,strategy=strategy.name,
                strategy_source=source_label,
                strategy_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                feature_switches=diagnostic.get('switches',{}),feature_config=config)


def print_p4_strategy(metadata):
    print(f"[P4 practice] class={metadata['actual_class']} name={metadata['strategy']}",flush=True)
    print(f"来源：{metadata['strategy_source']}",flush=True)
    print(f"SHA256：{metadata['strategy_sha256']}",flush=True)
    config=metadata['feature_config']
    print('配置：'+(json.dumps(config,ensure_ascii=False) if config else '策略未提供配置诊断'),flush=True)


def p4_action_summary(sequence,path,payload,response):
    """Display actual endpoint fields; the full protocol response is kept separately."""
    summary=dict(action=sequence,path=path)
    missing=[]
    def required(field):
        value=response.get(field)
        if value is None:missing.append(field)
        return value
    accepted=required('accepted')
    if accepted is not None:summary['accepted']=accepted
    virtual_time=required('virtual_time_s')
    if virtual_time is not None:summary['virtual_time_s']=virtual_time
    for field in ('channel','position'):
        if payload.get(field) is not None:summary[field]=payload[field]
    if path in ('/measure','/clear'):
        result=required('measure_result' if path=='/measure' else 'clear_result')
        if result is not None:summary['result']=result
        if path=='/measure' and result=='direction':
            bearing=required('svd_deg')
            if bearing is not None:summary['svd_deg']=bearing
        # no_signal and near have no bearing, so no svd key is displayed.
    else:
        summary['result']=('entered' if path=='/enter' else 'exited') if accepted is True else 'acceptance_unknown' if accepted is None else 'rejected'
        if path=='/exit' and response.get('exit_reason') is not None:
            summary['exit_reason']=response['exit_reason']
    if missing:
        summary.setdefault('result','response_incomplete')
        summary['protocol_warning']='missing_required_fields'
        summary['missing_fields']=missing
    return summary


class PracticeNotReady(RuntimeError):
    pass

class PracticeGuard:
    def __init__(self,data,allow_waiting=False):
        self.data=Path(data)
        active=list((self.data/'behavior-runs').glob('*/behavior.journal.jsonl'))
        if not active:raise PracticeNotReady('Require exactly one active simulator journal')
        if len(active)!=1:raise RuntimeError('Multiple active journals; no request sent')
        self.journal=active[0]
        self.header=self.read_header()
        self.check()
        raw=self.journal.read_text(encoding='utf-8')
        lines=raw.splitlines()
        if raw and not raw.endswith('\n'):lines=lines[:-1]
        events=[json.loads(s) for s in lines if s.strip()]
        self.ready=any(e.get('event')=='api_opened' for e in events)
        if any(e.get('end_reason') for e in events):raise RuntimeError('Practice already ended; no request sent')
        if any(e.get('entered') for e in events):raise RuntimeError('Another robot has already entered this practice')
        if not self.ready and not allow_waiting:raise PracticeNotReady('Practice API is not ready')

    def read_header(self):
        with self.journal.open(encoding='utf-8') as f:line=f.readline()
        if not line.endswith('\n'):raise PracticeNotReady('Practice journal is still being written')
        return json.loads(line)

    def check(self):
        active=list((self.data/'behavior-runs').glob('*/behavior.journal.jsonl'))
        if active!=[self.journal]:raise RuntimeError('Practice session ended or changed; no request sent')
        header=self.read_header()
        if header.get('event')!='practice_authorized' or header!=self.header:
            raise RuntimeError('NOT A VERIFIED PRACTICE SESSION; no request sent')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--problem',type=int,choices=(3,4),required=True)
    p.add_argument('--robot-id',default=os.environ.get('JAMMERS_ROBOT_ID'))
    p.add_argument('--case',help='Optional observed case code; otherwise resolve from this run after exit')
    p.add_argument('--data',type=Path,default=DEFAULT_DATA)
    p.add_argument('--journal',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--strategy',choices=('baseline','candidate'),default='baseline')
    args=p.parse_args(argv)
    if not args.robot_id:p.error('Provide --robot-id or JAMMERS_ROBOT_ID; never hardcode team identifiers')
    guard=PracticeGuard(args.data)
    if args.journal and guard.journal.resolve()!=args.journal.resolve():
        raise RuntimeError('Session changed before entry; no request sent')
    # Only an existing row identifier is read before entry; never source counts or case truth.
    db=args.data/'practice-statistics-queue.sqlite3'
    with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as con:
        previous_result_id=con.execute('SELECT COALESCE(MAX(id),0) FROM practice_statistics_tasks').fetchone()[0]
    module=REPO/'解题库'/('第三问/v10' if args.problem==3 else '第四问/v6')
    sys.path.insert(0,str(module))
    if args.strategy=='candidate':
        from candidates import make_candidate
        strategy=make_candidate(args.problem)
    elif args.problem==3:
        from strategy_v8 import AdaptiveV8
        strategy=AdaptiveV8()
    else:
        from strategy_p4 import AdaptiveP4
        strategy=AdaptiveP4()
    from robot import SimulatorClient,_post
    from robot_iter import run_with_sim_strategy
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder=ROOT/'results'/f'{stamp}_p{args.problem}_{strategy.name}'
    folder.mkdir(parents=True,exist_ok=False)
    source=folder/'source';source.mkdir()
    files=list(module.glob('*.py'))+list(ROOT.glob('*.py'))
    files+=list((REPO/'tools').glob('practice_launch.*'))
    files+=list(REPO.glob('*_一键接入演练.cmd'))
    hashes={}
    for f in files:
        rel=f.relative_to(REPO);hashes[str(rel)]=hashlib.sha256(f.read_bytes()).hexdigest()
        target=source/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    metadata=dict(mode='practice',problem=args.problem,case=args.case,strategy=strategy.name,
                  started=datetime.now(timezone.utc).isoformat(),python=sys.version,
                  guard_event=guard.header['event'],journal_name=guard.journal.parent.name,
                  code_sha256=hashes,command=['run_practice.py','--problem',str(args.problem),'--strategy',args.strategy]+(['--case',args.case] if args.case else [])+['--robot-id','<redacted>'])
    if args.problem == 4:
        metadata.update(p4_strategy_metadata(strategy))
        print_p4_strategy(metadata)
    (folder/'version.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    class PracticeClient(SimulatorClient):
        def _send(self,path,payload):
            if path not in ('/enter','/measure','/clear','/exit'):raise RuntimeError('Unsupported action')
            guard.check()
            row=dict(path=path,request={k:('<redacted>' if k=='robot_id' else v) for k,v in payload.items()})
            try:
                response=_post(self.base_url,path,payload,deadline=self.deadline,before_attempt=guard.check)
                row['response']=response
                if args.problem==4:
                    summary=p4_action_summary(self._seq,path,payload,response)
                    if path in ('/enter','/clear','/exit') or self._seq%100==0 or summary.get('missing_fields'):
                        print(json.dumps(summary,ensure_ascii=False),flush=True)
                elif path in ('/enter','/clear') or self._seq%100==0:
                    print(json.dumps(dict(action=self._seq,path=path,virtual_time_s=response.get('virtual_time_s'),result=response.get('clear_result'))),flush=True)
                return response
            except Exception as e:
                row['error']=str(e).replace(args.robot_id,'<redacted>');raise
            finally:
                with (folder/'actions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    cli=PracticeClient('http://127.0.0.1:2026',args.robot_id)
    print('PRACTICE_ONLY',args.problem,(args.case or '待结束核对场景') if args.problem==4 else args.case,strategy.name,flush=True)
    code=1
    try:
        result=run_with_sim_strategy(strategy,cli,max_steps=8000)
        result.pop('log',None)
        result.update(mode='practice',problem=args.problem,case=args.case,strategy=strategy.name)
        result['distance_m']=result['time_breakdown']['move_time_s']*5
        if args.problem == 3 and hasattr(strategy, 'diagnostics'):
            result['policy_diagnostics'] = strategy.diagnostics()
        if args.problem == 4:
            result.update({key: metadata[key] for key in ('actual_class', 'strategy_source', 'strategy_sha256')})
            result['feature_config']=metadata['feature_config']
            if hasattr(strategy, 'diagnostics'):
                result['policy_diagnostics'] = strategy.diagnostics()
        # This post-run source count is evidence only and is never exposed to policy.
        with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as con:
            con.row_factory=sqlite3.Row
            row=con.execute('SELECT problem_no,case_code,end_reason,cleared_jammer_count,jammer_count,measure_accepted_count,virtual_time_us,clear_failure_count FROM practice_statistics_tasks WHERE id>? ORDER BY id DESC LIMIT 1',(previous_result_id,)).fetchone()
            if row:
                result['simulator_summary']=dict(row)
                result['case']=row['case_code']
                result['actual_problem']=row['problem_no']
                if row['problem_no']!=args.problem:result['problem_mismatch']=True
                if args.case and row['case_code']!=args.case:result['case_mismatch']=True
        resolved_case=result.get('case')
        matches=list((args.data/'behavior-logs').glob(f'practice-p{args.problem}-*-{resolved_case}.result.json')) if resolved_case else []
        if matches:
            output=json.loads(matches[0].read_text(encoding='utf-8'))
            (folder/'simulator_result.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),flush=True)
        if result.get('problem_mismatch') or result.get('case_mismatch'):
            raise RuntimeError('Simulator case/problem differs from launcher selection; see saved result')
        code=0
    except Exception as e:
        (folder/'error.txt').write_text(f'{type(e).__name__}: {str(e).replace(args.robot_id,"<redacted>")}',encoding='utf-8')
        raise
    finally:
        (folder/'execution.json').write_text(json.dumps(dict(exit_code=code,finished=datetime.now(timezone.utc).isoformat()),indent=2),encoding='utf-8')
        print('RUN_FOLDER',folder,flush=True)
    return folder,result

if __name__=='__main__':main()
