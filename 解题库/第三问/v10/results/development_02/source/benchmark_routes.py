"""路线候选的成对完整演练。种子只传给模拟器；保存逐局结果与源码哈希。"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

from evaluate_v8 import run_one, summarize, FACTORIES
from strategy_v10 import RouteV10
from route_trials import CautiousRouteV10
from route_reactive import ReactiveRouteV10

ROOT = Path(__file__).resolve().parent
FACTORIES.update(route=RouteV10, cautious=CautiousRouteV10, reactive=ReactiveRouteV10)


def run_case(case, name):
    row = run_one(case['seed'], name, case['error_mode'],
                  case.get('receive_radius'), case['N'])
    trace = row.pop('log', [])
    row.update(case_id=case['id'], group=case['group'],
               receive_radius=case.get('receive_radius'))
    row['distance_m'] = row.get('time_breakdown', {}).get('move_time_s', 0) * 5
    return row, trace


def paired(rows, candidate, group):
    old = {r['case_id']: r for r in rows if r['strategy'] == 'v8' and r['group'] == group}
    new = {r['case_id']: r for r in rows if r['strategy'] == candidate and r['group'] == group}
    ids = sorted(old.keys() & new.keys())
    if not ids:
        return {}
    delta = [new[i]['avg_time_per_cleared'] - old[i]['avg_time_per_cleared']
             for i in ids if new[i]['avg_time_per_cleared'] is not None
             and old[i]['avg_time_per_cleared'] is not None]
    mean = statistics.mean(delta)
    margin = 1.96 * statistics.stdev(delta) / math.sqrt(len(delta)) if len(delta) > 1 else 0
    return dict(rounds=len(ids), mean_delta_s=mean,
                mean_delta_ci95_normal=[mean - margin, mean + margin],
                distance_delta_m=statistics.mean(new[i]['distance_m'] - old[i]['distance_m'] for i in ids),
                improved_rounds=sum(d < -1e-7 for d in delta),
                worse_rounds=sum(d > 1e-7 for d in delta),
                worst_regression_s=max(delta), best_gain_s=min(delta))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', required=True)
    parser.add_argument('--strategies', default='v8,route,cautious')
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    names = args.strategies.split(',')
    if not set(names) <= FACTORIES.keys() or Path(args.output).name != args.output:
        parser.error('策略或结果文件名无效')
    suite_path = Path(args.cases)
    suite = json.loads(suite_path.read_text(encoding='utf-8'))
    cases = suite['cases']
    output = ROOT / 'results' / args.output
    output.mkdir(parents=True, exist_ok=False)
    source_names = ('strategy_v8.py', 'strategy_v10.py', 'route_search.py', 'route_trials.py', 'route_reactive.py',
                    'mock_simulator.py', 'robot.py', 'robot_iter.py', 'strategy.py',
                    'problem1_v4_inline.py', 'evaluate_v8.py', 'benchmark_routes.py')
    snapshots = output / 'source'
    snapshots.mkdir()
    hashes = {}
    for name in source_names:
        source = (ROOT / name).read_bytes()
        (snapshots / name).write_bytes(source)
        hashes[name] = hashlib.sha256(source).hexdigest()
    metadata = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                    evaluation='offline_mock_not_official_simulator',
                    suite=suite, suite_sha256=hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                    code_sha256=hashes, strategies=names)
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    rows, worst = [], {}
    with (output / 'records.jsonl').open('w', encoding='utf-8') as stream:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            tasks = {pool.submit(run_case, case, name): (case, name)
                     for case in cases for name in names}
            for task in as_completed(tasks):
                case, name = tasks[task]
                row, trace = task.result()
                rows.append(row)
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                stream.flush()
                score = row['avg_time_per_cleared'] or math.inf
                if name not in worst or score > (worst[name]['avg_time_per_cleared'] or math.inf):
                    worst[name] = {**row, 'log': trace}
                if row['error'] or row['cleared'] != row['N']:
                    print(json.dumps({'failure': row}, ensure_ascii=False), flush=True)
                if len(rows) % 7 == 0 or len(rows) == len(tasks):
                    print(json.dumps(dict(done=len(rows), total=len(tasks), last=case['id'], strategy=name,
                                          mean_s=round(score, 3)), ensure_ascii=False), flush=True)
    for name in source_names:
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != hashes[name]:
            raise RuntimeError(f'运行中源文件变更，结果不能验收: {name}')
    groups = sorted({case['group'] for case in cases})
    summary = {name: {group: summarize([r for r in rows if r['strategy'] == name and r['group'] == group])
                      for group in groups} for name in names}
    comparison = {name: {group: paired(rows, name, group) for group in groups}
                  for name in names if name != 'v8'}
    by_n = {name: {str(n): summarize([r for r in rows if r['strategy'] == name and r['N'] == n
                                     and r['group'] == 'main']) for n in range(10, 17)}
            for name in names}
    result = dict(**metadata, summary=summary, paired=comparison, by_N=by_n, records=rows)
    (output / 'report.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    for name, row in worst.items():
        (output / f'worst_{name}.json').write_text(json.dumps(row, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(summary=summary, paired=comparison), ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
