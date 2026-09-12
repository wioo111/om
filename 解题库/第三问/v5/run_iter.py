# -*- coding: utf-8 -*-
"""第三问迭代入口：默认 v8，旧策略可用 --strategy v7 对照。

用法：python run_iter.py --rounds 30 --seeds 42,2024,12345
三个 seed 基准各生成 rounds 局，默认写入 results/iter_v8.json。
"""

import argparse
import json
import math
import os
import statistics

from mock_simulator import MockSimulator
from robot_iter import run_with_sim_strategy
from strategy_v7 import HybridV7


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
os.makedirs(OUT, exist_ok=True)


def summarize(records):
    if not records:
        return {}
    cleared = [r['cleared'] for r in records]
    rates = [r['clear_rate'] for r in records]
    finite_times = [r['avg_time_per_cleared'] for r in records
                    if r.get('avg_time_per_cleared') is not None
                    and math.isfinite(r['avg_time_per_cleared'])]
    return {
        'rounds': len(records),
        'cleared_mean': statistics.mean(cleared),
        'cleared_median': statistics.median(cleared),
        'cleared_min': min(cleared),
        'cleared_max': max(cleared),
        'clear_rate_mean': statistics.mean(rates),
        'full_clear_rate': statistics.mean(
            [r['cleared'] == r['N'] for r in records]),
        'avg_time_per_cleared_mean': (
            statistics.mean(finite_times) if finite_times else None),
        'virtual_time_mean': statistics.mean(
            [r['virtual_time_s'] for r in records]),
        'measure_count_mean': statistics.mean(
            [r['measure_count'] for r in records]),
        'clear_count_mean': statistics.mean(
            [r['clear_count'] for r in records]),
    }


def run_one(seed):
    sim = MockSimulator(seed=seed)
    result = run_with_sim_strategy(HybridV7(), sim, max_steps=8000)
    result.pop('log', None)
    if result['avg_time_per_cleared'] is not None and not math.isfinite(result['avg_time_per_cleared']):
        result['avg_time_per_cleared'] = None
    result['seed'] = seed
    result['strategy'] = 'HybridV7'
    return result


def _legacy_v7_main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=30)
    parser.add_argument('--seeds', default='42,2024,12345')
    args = parser.parse_args()
    seed_bases = [int(x.strip()) for x in args.seeds.split(',') if x.strip()]
    if args.rounds <= 0 or not seed_bases:
        raise SystemExit('--rounds 必须为正数，--seeds 不能为空')

    records = []
    print(f'v7 迭代评估：{len(seed_bases)} 个 seed × {args.rounds} 局')
    for base in seed_bases:
        group = []
        for k in range(args.rounds):
            seed = base + 7 * k
            result = run_one(seed)
            group.append(result)
            records.append(result)
            print(f'  seed_base={base} [{k + 1:2d}/{args.rounds}] '
                  f'seed={seed} N={result["N"]:2d} '
                  f'cleared={result["cleared"]:2d} '
                  f'virt={result["virtual_time_s"]:.1f}s '
                  f'm={result["measure_count"]:3d} '
                  f'c={result["clear_count"]:2d}')
        s = summarize(group)
        print(f'  -> seed_base={base}: '
              f'平均清除 {s["cleared_mean"]:.2f}，'
              f'清除率 {s["clear_rate_mean"] * 100:.1f}%，'
              f'全清率 {s["full_clear_rate"] * 100:.1f}%')

    summary = summarize(records)
    out = {
        'rounds_per_seed': args.rounds,
        'seed_bases': seed_bases,
        'total_records': len(records),
        'summary': summary,
        'records': records,
    }
    path = os.path.join(OUT, 'iter.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False, allow_nan=False)

    print('\n' + '=' * 60)
    print('v7 迭代汇总')
    print('=' * 60)
    print(f'总局数       : {len(records)}')
    print(f'平均清除数   : {summary["cleared_mean"]:.2f}')
    print(f'清除率       : {summary["clear_rate_mean"] * 100:.1f}%')
    print(f'全清率       : {summary["full_clear_rate"] * 100:.1f}%')
    if summary['avg_time_per_cleared_mean'] is None:
        print('平均单源时间 : —')
    else:
        print(f'平均单源时间 : '
              f'{summary["avg_time_per_cleared_mean"]:.1f}s')
    print(f'结果写入     : {path}')


def main():
    from evaluate_v8 import main as evaluate_main
    return evaluate_main()


if __name__ == '__main__':
    main()
