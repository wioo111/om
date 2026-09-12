# -*- coding: utf-8 -*-
"""三机统一评测：固定场景、缓存基线、候选隔离、成对比较。"""
import argparse
import hashlib
import importlib
import json
import math
import random
import re
import secrets
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from evaluate_v8 import FACTORIES, run_one, summarize

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ('strategy.py', 'strategy_v7.py', 'strategy_v8.py',
          'problem1_v4_inline.py', 'mock_simulator.py', 'robot.py',
          'robot_iter.py', 'evaluate_v8.py', 'collab/bench.py')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def foundation():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in FROZEN}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False),
                    encoding='utf-8')


def make_suite(kind, seed=None):
    seed = seed if seed is not None else (2026091203 if kind == 'screen' else secrets.randbits(64))
    rng = random.Random(seed)
    cases = []
    per_n = 3 if kind == 'screen' else 10
    counts = (10, 16) if kind == 'smoke' else range(10, 17)
    for n in counts:
        for k in range(1 if kind == 'smoke' else per_n):
            cases.append(dict(id=f'N{n}_{k:02d}', seed=rng.getrandbits(63),
                              N=n, error_mode='fixed', receive_radius=None, group='main'))
    if kind == 'validation':
        for mode in ('fixed', 'bias', 'smooth', 'edge'):
            for n in (10, 13, 16):
                for radius in (1000, 1500):
                    cases.append(dict(id=f'stress_{mode}_{n}_{radius}', seed=rng.getrandbits(63),
                                      N=n, error_mode=mode, receive_radius=radius, group='stress'))
    return dict(kind=kind, generation_seed=seed, cases=cases)


def validate_suite(suite):
    cases = suite['cases']
    if not cases or len({r['id'] for r in cases}) != len(cases):
        raise ValueError('场景清单为空或 case id 重复')
    if len({r['seed'] for r in cases}) != len(cases):
        raise ValueError('场景种子重复')
    for r in cases:
        if (not isinstance(r['N'], int) or not 10 <= r['N'] <= 16
                or not isinstance(r['seed'], int)
                or r['error_mode'] not in ('fixed', 'bias', 'smooth', 'edge')
                or r['group'] not in ('main', 'stress')
                or (r['receive_radius'] is not None and not 1000 <= r['receive_radius'] <= 1500)):
            raise ValueError(f'不符合题目范围的场景: {r}')


def paired_summary(base, candidate):
    if [r['case_id'] for r in base] != [r['case_id'] for r in candidate]:
        raise ValueError('两组结果的场景不一致，不能比较')
    good = all(not r.get('error') and r['cleared'] == r['N']
               and r['clear_rate'] == 1.0 for r in base + candidate)
    a, b = summarize(base), summarize(candidate)
    result = dict(baseline=a, candidate=b, all_full_clear=good,
                  mean_delta_s=None, paired_ci95_normal=None, improvement_percent=None,
                  p95_delta_s=None, wins=None, screening_pass=False)
    if not good:
        return result
    differences = [y['avg_time_per_cleared'] - x['avg_time_per_cleared']
                   for x, y in zip(base, candidate)]
    delta = statistics.mean(differences)
    margin = (1.96 * statistics.stdev(differences) / math.sqrt(len(differences))
              if len(differences) > 1 else None)
    result.update(mean_delta_s=delta,
                  paired_ci95_normal=[delta - margin, delta + margin] if margin is not None else None,
                  improvement_percent=-100 * delta / a['avg_time_per_cleared_mean'],
                  p95_delta_s=b['avg_time_p95'] - a['avg_time_p95'],
                  wins=sum(d < -1e-8 for d in differences),
                  screening_pass=(len(base) >= 21 and delta <= -.03 * a['avg_time_per_cleared_mean']
                                  and b['avg_time_p95'] <= 1.05 * a['avg_time_p95']))
    return result


def run_cases(cases, name):
    records, worst = [], None
    for i, case in enumerate(cases):
        try:
            row = run_one(case['seed'], name, case['error_mode'], case['receive_radius'], case['N'])
        except Exception as exc:
            row = dict(N=case['N'], cleared=0, clear_rate=0.0, virtual_time_s=0.0,
                       avg_time_per_cleared=None, measure_count=0, clear_count=0,
                       error=f'{type(exc).__name__}: {exc}', stop_reason='runner_error')
        trace = row.pop('log', [])
        # clear_rate 来自模拟器的赛后真值；策略自己的计数不能替代真清除数。
        if row['clear_rate'] != row['cleared'] / row['N']:
            row['error'] = '策略清除计数与模拟器赛后真值不一致'
        row.update(case_id=case['id'], case_group=case['group'])
        records.append(row)
        # 失败日志优先保留，否则保留单源时间最长的一局。
        score = math.inf if row.get('error') or row['cleared'] != row['N'] else row['avg_time_per_cleared']
        if worst is None or score > worst[0]:
            worst = score, {**row, 'log': trace}
        if (i + 1) % 7 == 0 or i + 1 == len(cases):
            print(f'{name}: {i + 1}/{len(cases)}，已全清 '
                  f'{sum(r["cleared"] == r["N"] and not r.get("error") for r in records)} 局', flush=True)
    return records, worst[1]


def execute(args):
    manifest = json.loads((ROOT / 'collab/frozen.json').read_text(encoding='utf-8'))
    hashes = foundation()
    changed = [p for p in FROZEN if hashes[p] != manifest['files'].get(p)]
    if changed:
        raise ValueError('公共基线发生变化，不能与冻结版混比；请由 C 统一更新公共版本: ' + ', '.join(changed))
    suite = json.loads(Path(args.suite).read_text(encoding='utf-8'))
    validate_suite(suite)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.label):
        raise ValueError('label 只能包含英文字母、数字、下划线和连字符')
    out = ROOT / 'collab/results' / f'{args.label}.json'
    if out.exists():
        raise ValueError(f'结果已存在，请为新版本使用新 label: {out}')
    module_name, factory_name = args.candidate.split(':', 1)
    if not module_name.startswith('collab.'):
        raise ValueError('候选模块应位于 collab 目录')
    factory = getattr(importlib.import_module(module_name), factory_name)
    if not callable(factory):
        raise ValueError('候选入口不可调用')
    environment = {'python': sys.version.split()[0], 'numpy': np.__version__}
    suite_hash = digest(suite['cases'])
    foundation_hash = digest(hashes)
    key = digest([suite_hash, foundation_hash, environment])
    cache = ROOT / 'collab/cache' / f'baseline_{key}.json'
    cache_used = cache.exists()
    if cache_used:
        base = json.loads(cache.read_text(encoding='utf-8'))['records']
        if [r['case_id'] for r in base] != [r['id'] for r in suite['cases']]:
            raise ValueError('基线缓存场景与清单不匹配')
        print('复用同环境、同基线、同场景的基线成绩。', flush=True)
    else:
        base, baseline_worst = run_cases(suite['cases'], 'v8')
        if not all(not r.get('error') and r['cleared'] == r['N'] for r in base):
            write_json(out.with_name(args.label + '_baseline_failure.json'),
                       {'records': base, 'worst_trace': baseline_worst})
            raise RuntimeError('冻结基线在本批场景未全清或报错，请保留场景供 C 处理')
        write_json(cache, {'records': base, 'environment': environment, 'suite_hash': suite_hash})
    candidate_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (ROOT / 'collab').glob('*candidate.py')}
    FACTORIES['_candidate'] = factory
    rows, worst = run_cases(suite['cases'], '_candidate')
    if candidate_hashes != {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (ROOT / 'collab').glob('*candidate.py')}:
        raise RuntimeError('运行中候选文件发生变化；本次不发布成绩，请固定代码后使用新 label')
    main_pairs = ([r for r in base if r['case_group'] == 'main'],
                  [r for r in rows if r['case_group'] == 'main'])
    result = dict(label=args.label, role=args.role, candidate_entry=args.candidate,
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  suite_kind=suite['kind'], suite_hash=suite_hash, foundation_hash=foundation_hash,
                  environment=environment, candidate_files=candidate_hashes, baseline_cache_used=cache_used,
                  comparison=paired_summary(*main_pairs),
                  by_N={str(n): paired_summary([r for r in main_pairs[0] if r['N'] == n],
                                               [r for r in main_pairs[1] if r['N'] == n])
                        for n in range(10, 17) if any(r['N'] == n for r in main_pairs[0])},
                  stress_summary=summarize([r for r in rows if r['case_group'] == 'stress']),
                  baseline_records=base, candidate_records=rows)
    result['all_cases_full_clear'] = all(not r.get('error') and r['cleared'] == r['N'] for r in rows)
    write_json(out, result)
    write_json(out.with_name(args.label + '_worst_trace.json'), worst)
    c = result['comparison']
    print(json.dumps({'label': args.label, 'all_cases_full_clear': result['all_cases_full_clear'],
                      'baseline_mean_s': c['baseline']['avg_time_per_cleared_mean'],
                      'candidate_mean_s': c['candidate']['avg_time_per_cleared_mean'],
                      'paired_delta_s': c['mean_delta_s'], 'improvement_percent': c['improvement_percent'],
                      'p95_delta_s': c['p95_delta_s'], 'screening_pass': c['screening_pass'],
                      'output': str(out)}, ensure_ascii=False, allow_nan=False), flush=True)
    return 0 if result['all_cases_full_clear'] else 1


def table(paths):
    reports = [json.loads(Path(p).read_text(encoding='utf-8')) for p in paths]
    for field in ('suite_hash', 'foundation_hash', 'environment'):
        if any(r[field] != reports[0][field] for r in reports):
            raise ValueError(f'{field} 不一致；请在 C 上使用同一批场景与环境评测后再比较')
    print('| 候选 | 全清 | 均值/s | 相对基线变化/s | P95/s |')
    print('|---|---|---:|---:|---:|')
    def fmt(v):
        return f'{v:.2f}' if v is not None else '无有效值'
    for r in reports:
        c = r['comparison']
        print(f'| {r["label"]} | {r["all_cases_full_clear"]} | '
              f'{fmt(c["candidate"]["avg_time_per_cleared_mean"])} | '
              f'{fmt(c["mean_delta_s"])} | {fmt(c["candidate"]["avg_time_p95"])} |')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('make-suite')
    create.add_argument('--kind', choices=('screen', 'validation', 'smoke'), required=True)
    create.add_argument('--out', required=True)
    create.add_argument('--seed', type=int)
    run = sub.add_parser('run')
    run.add_argument('--candidate', required=True)
    run.add_argument('--suite', default='collab/screen.json')
    run.add_argument('--label', required=True)
    run.add_argument('--role', choices=('A', 'B', 'C'), required=True)
    compare = sub.add_parser('table')
    compare.add_argument('reports', nargs='+')
    args = parser.parse_args()
    try:
        if args.command == 'make-suite':
            path = Path(args.out)
            if path.exists():
                raise ValueError('场景清单已存在，请使用新文件名')
            suite = make_suite(args.kind, args.seed)
            validate_suite(suite)
            write_json(path, suite)
            print(f'已写入 {len(suite["cases"])} 个场景: {path.resolve()}')
            return 0
        if args.command == 'run':
            return execute(args)
        table(args.reports)
        return 0
    except (ValueError, RuntimeError, KeyError, ImportError, AttributeError) as exc:
        print(f'协作评测未完成: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
