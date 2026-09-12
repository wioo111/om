"""Read completed P3 practice actions, not encrypted payloads or live source truth."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parent

def main():
    rows=[];inputs={}
    for folder in sorted((ROOT/'results').glob('20260913_*_p3_*')):
        result_file=folder/'result.json';actions_file=folder/'actions.jsonl'
        if not result_file.exists() or not actions_file.exists():continue
        result=json.loads(result_file.read_text(encoding='utf-8'))
        if result.get('mode')!='practice':continue
        actions=[json.loads(line) for line in actions_file.read_text(encoding='utf-8').splitlines() if line.strip()]
        last_clear=0.;prev=(0.,0.);seen=set();duplicates=0;counts=Counter();long_moves=[]
        for row in actions:
            response=row.get('response',{})
            if response.get('accepted') is not True:continue
            path=row['path'];request=row['request']
            if path=='/clear' and response.get('clear_result')=='success':last_clear=response['virtual_time_s']
            if path not in ('/measure','/clear'):continue
            pos=(request['position']['x'],request['position']['y']);d=math.dist(prev,pos)
            if d>500:long_moves.append(d)
            prev=pos
            if path=='/measure':
                counts[response['measure_result']]+=1
                key=(*pos,request['channel'])
                duplicates+=int(key in seen);seen.add(key)
        official=result.get('simulator_summary',{})
        rows.append(dict(folder=folder.name,case=result.get('case'),strategy=result['strategy'],
            total=official.get('jammer_count'),cleared=result['cleared'],virtual_s=result['virtual_time_s'],
            wall_s=result['runtime_s'],counts=dict(counts),clear_failures=result['clear_fail_count'],
            duplicate_measurements=duplicates,post_last_clear_s=result['virtual_time_s']-last_clear,
            long_moves_over_500m=len(long_moves),long_move_distance_m=sum(long_moves),
            time_breakdown=result['time_breakdown']))
        for file in (result_file,actions_file):inputs[str(file.relative_to(ROOT))]=hashlib.sha256(file.read_bytes()).hexdigest()
    groups={}
    for name in sorted({r['strategy'] for r in rows}):
        group=[r for r in rows if r['strategy']==name]
        total_time=sum(r['virtual_s'] for r in group)
        groups[name]=dict(runs=len(group),all_cleared=sum(r['total']==r['cleared'] for r in group),
            mean_virtual_s=statistics.mean(r['virtual_s'] for r in group),mean_wall_s=statistics.mean(r['wall_s'] for r in group),
            max_virtual_s=max(r['virtual_s'] for r in group),
            time_fraction={key:sum(r['time_breakdown'][key] for r in group)/total_time for key in group[0]['time_breakdown']},
            total_clear_failures=sum(r['clear_failures'] for r in group),
            mean_post_last_clear_s=statistics.mean(r['post_last_clear_s'] for r in group),
            max_post_last_clear_s=max(r['post_last_clear_s'] for r in group),
            duplicate_measurements=sum(r['duplicate_measurements'] for r in group),
            mean_direction=statistics.mean(r['counts'].get('direction',0) for r in group),
            mean_no_signal=statistics.mean(r['counts'].get('no_signal',0) for r in group))
    report=dict(created=datetime.now(timezone.utc).isoformat(),scope='completed local P3 practice records from 2026-09-13',
        input_sha256=inputs,summary=groups,records=rows)
    folder=ROOT/'results'/'p3_night_analysis_0407';folder.mkdir(exist_ok=False)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(groups,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
