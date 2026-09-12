"""一次性独立对照：两个进程分别评估 v8 与已固定的 v9。"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import numpy as np

from collab.bench import (ROOT, candidate_files, digest, foundation, paired_summary,
                          run_cases, validate_suite, write_json)
from evaluate_v8 import FACTORIES, summarize
from strategy_v9 import make_strategy


def evaluate(name, cases):
    FACTORIES['v9'] = make_strategy
    return run_cases(cases, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', default='validation_suite.json')
    parser.add_argument('--output', default='results/validation_v9.json')
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise SystemExit('结果已存在，请使用新文件名。')
    frozen = json.loads((ROOT/'collab/frozen.json').read_text(encoding='utf-8'))
    public = foundation()
    if public != frozen['files']:
        raise SystemExit('公共代码与冻结版本不一致。')
    sources = candidate_files()
    suite = json.loads(Path(args.suite).read_text(encoding='utf-8'))
    validate_suite(suite)
    with ProcessPoolExecutor(max_workers=2) as pool:
        baseline_future = pool.submit(evaluate, 'v8', suite['cases'])
        candidate_future = pool.submit(evaluate, 'v9', suite['cases'])
        baseline, baseline_worst = baseline_future.result()
        rows, worst = candidate_future.result()
    if foundation() != public or candidate_files() != sources:
        raise SystemExit('运行期间代码发生变化，不发布本次成绩。')
    main_base = [r for r in baseline if r['case_group']=='main']
    main_rows = [r for r in rows if r['case_group']=='main']
    stress_base = [r for r in baseline if r['case_group']=='stress']
    stress_rows = [r for r in rows if r['case_group']=='stress']
    comparison = paired_summary(main_base, main_rows)
    all_full = all(not r.get('error') and r['cleared']==r['N'] and r['clear_rate']==1
                   for r in baseline + rows)
    environment = {'python':sys.version.split()[0], 'numpy':np.__version__}
    groups = {}
    for label, indices in [('01',range(4)), ('02',range(4,7)), ('03',range(7,10))]:
        groups[label] = summarize([r for r in main_rows
                                  if int(r['case_id'].rsplit('_',1)[1]) in indices])
    mean = comparison['candidate']['avg_time_per_cleared_mean']
    goal_met = (all_full and mean is not None and 180 <= mean <= 220
                and all(180 <= s['avg_time_per_cleared_mean'] <= 220 for s in groups.values()))
    ci = comparison['paired_ci95_normal']
    improved = (all_full and ci is not None and ci[1] < 0
                and comparison['candidate']['avg_time_p95'] <=
                    1.05*comparison['baseline']['avg_time_p95'])
    report = dict(label='V9_final', candidate_entry='collab.merged_candidate:make_strategy',
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  evaluation='offline_mock_not_official_simulator',
                  suite_kind=suite['kind'], suite_hash=digest(suite['cases']),
                  foundation_hash=digest(public), environment=environment,
                  candidate_files=sources, comparison=comparison,
                  by_N={str(n):paired_summary([r for r in main_base if r['N']==n],
                                              [r for r in main_rows if r['N']==n])
                        for n in range(10,17)},
                  by_validation_group=groups,
                  stress_comparison=paired_summary(stress_base,stress_rows),
                  stress_summary=summarize(stress_rows),
                  all_cases_full_clear=all_full, improvement_supported=improved,
                  goal_band_s=[180,220], goal_met=goal_met,
                  baseline_records=baseline, candidate_records=rows)
    write_json(path,report)
    write_json(path.with_name(path.stem+'_worst_trace.json'),worst)
    write_json(path.with_name('validation_v8_worst_trace.json'),baseline_worst)
    if all(not r.get('error') and r['cleared']==r['N'] and r['clear_rate']==1 for r in baseline):
        key=digest([digest(suite['cases']),digest(public),environment])
        write_json(ROOT/'collab/cache'/f'baseline_{key}.json',
                   {'records':baseline,'environment':environment,'suite_hash':digest(suite['cases'])})
    print(json.dumps({'all_full_clear':all_full,'baseline_mean_s':comparison['baseline']['avg_time_per_cleared_mean'],
                      'v9_mean_s':mean,'paired_delta_s':comparison['mean_delta_s'],
                      'paired_ci95':ci,'v9_p95':comparison['candidate']['avg_time_p95'],
                      'improvement_supported':improved,'goal_met':goal_met,'output':str(path.resolve())},
                     ensure_ascii=False),flush=True)
    return 0 if all_full else 1


if __name__ == '__main__':
    raise SystemExit(main())
