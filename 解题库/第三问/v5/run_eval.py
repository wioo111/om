# -*- coding: utf-8 -*-
# run_eval.py
# 第三问：脱机评估 driver
#
# 对 4 套策略各跑 N 局 mock 模拟器，统计：
#   - 清除率（cleared / N_total）
#   - 平均定位清除时间（virtual_time / cleared）
#   - 单局测量次数 / 清除次数
#   - 不同 N_total（10-16）下的分布
#
# 输出：summary.json + summary.md

import json
import os
import statistics
from collections import defaultdict
from typing import List, Dict

from mock_simulator import MockSimulator
from robot import run_with_sim

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
os.makedirs(OUT, exist_ok=True)

STRATEGIES = ['BlinkHop', 'StaticScan', 'Patrol', 'Hybrid']
N_ROUNDS = 30          # 每策略局数
SEED_BASE = 20260912
SEED_OFFSETS = {
    'BlinkHop': 0,
    'StaticScan': 1000,
    'Patrol': 2000,
    'Hybrid': 3000,
}


def run_one(strategy: str, seed: int) -> dict:
    sim = MockSimulator(seed=seed)
    stats = run_with_sim(strategy, sim, max_steps=8000)
    stats['seed'] = seed
    stats['strategy'] = strategy
    return stats


def summarize(records: List[dict]) -> dict:
    """对一组（同策略）记录做统计。"""
    if not records:
        return {}
    n = len(records)
    cleared = [r['cleared'] for r in records]
    rates = [r['clear_rate'] for r in records]
    times = [r['avg_time_per_cleared'] for r in records
             if r['cleared'] > 0]
    virtual = [r['virtual_time_s'] for r in records]
    measures = [r['measure_count'] for r in records]
    clears = [r['clear_count'] for r in records]

    return {
        'N_rounds': n,
        'cleared_mean': statistics.mean(cleared),
        'cleared_median': statistics.median(cleared),
        'cleared_min': min(cleared),
        'cleared_max': max(cleared),
        'clear_rate_mean': statistics.mean(rates),
        'clear_rate_full': sum(1 for r in records
                                if r['cleared'] == r['N']) / n,
        'avg_time_mean': (statistics.mean(times) if times else float('inf')),
        'avg_time_median': (statistics.median(times) if times else float('inf')),
        'virtual_time_mean': statistics.mean(virtual),
        'measures_mean': statistics.mean(measures),
        'clears_mean': statistics.mean(clears),
    }


def by_N(records: List[dict]) -> Dict[int, dict]:
    """按干扰源数 N 分组统计。"""
    groups = defaultdict(list)
    for r in records:
        groups[r['N']].append(r)
    return {N: summarize(rs) for N, rs in sorted(groups.items())}


def main():
    all_records = []
    for s in STRATEGIES:
        print(f"\n=== 策略 {s}（{N_ROUNDS} 局）===")
        for k in range(N_ROUNDS):
            seed = SEED_BASE + SEED_OFFSETS[s] + k * 7
            r = run_one(s, seed)
            print(f"  [{k+1:2d}/{N_ROUNDS}] N={r['N']:2d} "
                  f"cleared={r['cleared']:2d} "
                  f"virt={r['virtual_time_s']:.1f}s "
                  f"m={r['measure_count']:3d} c={r['clear_count']:2d}")
            all_records.append(r)

    # 按策略汇总
    summary_by_strategy = {}
    for s in STRATEGIES:
        sub = [r for r in all_records if r['strategy'] == s]
        summary_by_strategy[s] = {
            'overall': summarize(sub),
            'by_N': by_N(sub),
        }

    # 保存
    out = {
        'N_ROUNDS': N_ROUNDS,
        'SEED_BASE': SEED_BASE,
        'by_strategy': summary_by_strategy,
    }
    with open(os.path.join(OUT, 'summary.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    # 原始记录
    with open(os.path.join(OUT, 'raw_records.json'), 'w') as f:
        json.dump(all_records, f, indent=2, default=str)

    # Markdown 报告
    md = ["# 第三问：策略对比（脱机 baseline）\n"]
    md.append(f"每策略 {N_ROUNDS} 局 mock 模拟器。\n")
    md.append("\n## 整体对比\n")
    md.append("| 策略 | 平均清除数 | 清除率 | 全部清除局数占比 | "
              "平均定位清除时间 (s) | 平均测量次数 | 平均清除次数 |"
              "\n|---|---|---|---|---|---|---|")
    for s in STRATEGIES:
        o = summary_by_strategy[s]['overall']
        md.append(
            f"| {s} | {o['cleared_mean']:.1f} | {o['clear_rate_mean']*100:.1f}% | "
            f"{o['clear_rate_full']*100:.1f}% | "
            f"{o['avg_time_mean']:.1f} | {o['measures_mean']:.0f} | "
            f"{o['clears_mean']:.1f} |"
        )
    md.append("\n## 按干扰源数 N 分组（平均定位清除时间 s）\n")
    md.append("| 策略 | N=10 | N=11 | N=12 | N=13 | N=14 | N=15 | N=16 |")
    md.append("|---|---|---|---|---|---|---|---|")
    for s in STRATEGIES:
        row = [s]
        for N in range(10, 17):
            x = summary_by_strategy[s]['by_N'].get(N, {})
            t = x.get('avg_time_mean', float('inf'))
            row.append(f"{t:.1f}" if t != float('inf') else '—')
        md.append("| " + " | ".join(row) + " |")
    with open(os.path.join(OUT, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write("\n".join(md))

    print(f"\n结果已写入 {OUT}/")
    print("\n整体对比：")
    print("策略          清除数  清除率  全清率   平均时(s)  测量数  清除数")
    for s in STRATEGIES:
        o = summary_by_strategy[s]['overall']
        print(f"{s:<12} {o['cleared_mean']:6.1f}  "
              f"{o['clear_rate_mean']*100:5.1f}%  "
              f"{o['clear_rate_full']*100:5.1f}%   "
              f"{o['avg_time_mean']:7.1f}  "
              f"{o['measures_mean']:5.0f}  "
              f"{o['clears_mean']:5.1f}")


if __name__ == "__main__":
    main()
