# -*- coding: utf-8 -*-
# run_eval_v6.py
# v6 baseline 评估 + vs v5 对比
#
# 用法：python run_eval_v6.py

import os
import json
import statistics
from collections import defaultdict
from typing import List, Dict

from mock_simulator import MockSimulator
from robot import run_with_sim
import strategy_v6 as v6

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
os.makedirs(OUT, exist_ok=True)

# 与 v5 run_eval.py 的 SEED 公式保持一致，让 v5 / v6 对照公平
SEED_BASE = 20260912
SEED_OFFSET_V6 = 4000   # 跟 v5 错开，避免伪"同一局"
N_ROUNDS = 50            # 比 v5 多跑点，让 95% 区间稳


def run_one_v6(seed: int) -> dict:
    sim = MockSimulator(seed=seed)
    s = v6.V6Strategy()
    state = v6.State(pos=(0.0, 0.0), ch=1)
    sim.enter()
    state.virtual_time = 0.0
    n_steps = 0
    while n_steps < 12000:
        a = s.step(state)
        if a.kind == 'done':
            break
        if a.kind in ('measure', 'clear'):
            state.pos = a.pos
            state.ch = a.ch
        if a.kind == 'measure':
            resp = sim.measure(a.pos[0], a.pos[1], a.ch)
            r = resp.measure_result
            svd = resp.svd_deg if r == 'direction' else None
            s.on_measure(state, a.ch, r, svd)
        elif a.kind == 'clear':
            resp = sim.clear(a.pos[0], a.pos[1], a.ch)
            s.on_clear(state, a.ch, resp.clear_result == 'success')
        state.virtual_time = resp.virtual_time_s
        n_steps += 1
    sim.exit()
    st = sim.stats()
    st['strategy'] = 'V6'
    st['seed'] = seed
    st['steps'] = n_steps
    return st


def summarize(records: List[dict]) -> dict:
    if not records:
        return {}
    n = len(records)
    cleared = [r['cleared'] for r in records]
    times = [r['avg_time_per_cleared'] for r in records
             if r['cleared'] > 0]
    return {
        'N_rounds': n,
        'cleared_mean': statistics.mean(cleared),
        'cleared_median': statistics.median(cleared),
        'cleared_min': min(cleared),
        'cleared_max': max(cleared),
        'clear_rate_mean': statistics.mean([r['clear_rate'] for r in records]),
        'clear_rate_full': sum(1 for r in records if r['cleared'] == r['N']) / n,
        'avg_time_mean': (statistics.mean(times) if times else float('inf')),
        'avg_time_median': (statistics.median(times) if times else float('inf')),
        'virtual_time_mean': statistics.mean([r['virtual_time_s'] for r in records]),
        'measures_mean': statistics.mean([r['measure_count'] for r in records]),
        'clears_mean': statistics.mean([r['clear_count'] for r in records]),
    }


def by_N(records: List[dict]) -> Dict[int, dict]:
    groups = defaultdict(list)
    for r in records:
        groups[r['N']].append(r)
    return {N: summarize(rs) for N, rs in sorted(groups.items())}


def load_v5() -> dict:
    """读 v5 baseline summary.json 用于对比。"""
    p = os.path.join(OUT, 'summary.json')
    if not os.path.isfile(p):
        return None
    with open(p, 'r') as f:
        return json.load(f)


def main():
    print(f"v6 baseline: {N_ROUNDS} 局")
    records = []
    for k in range(N_ROUNDS):
        seed = SEED_BASE + SEED_OFFSET_V6 + k * 7
        r = run_one_v6(seed)
        print(f"  [{k+1:2d}/{N_ROUNDS}] N={r['N']:2d} "
              f"cleared={r['cleared']:2d} "
              f"virt={r['virtual_time_s']:.1f}s "
              f"m={r['measure_count']:3d} c={r['clear_count']:2d}")
        records.append(r)

    overall = summarize(records)
    byn = by_N(records)

    out = {
        'N_ROUNDS': N_ROUNDS,
        'SEED_BASE': SEED_BASE,
        'overall': overall,
        'by_N': byn,
    }
    with open(os.path.join(OUT, 'summary_v6.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    with open(os.path.join(OUT, 'raw_records_v6.json'), 'w') as f:
        json.dump(records, f, indent=2, default=str)

    # 对比 v5
    v5 = load_v5()
    print("\n" + "=" * 60)
    print("v5 vs v6 对比（实测）")
    print("=" * 60)
    print(f"{'策略':<12} {'平均清除':>10} {'清除率':>10} {'全清率':>10} "
          f"{'单源时(s)':>12}")
    print(f"{'V6 (新方案)':<12} {overall['cleared_mean']:>10.2f} "
          f"{overall['clear_rate_mean']*100:>9.1f}% "
          f"{overall['clear_rate_full']*100:>9.1f}% "
          f"{overall['avg_time_mean']:>12.1f}")
    if v5:
        # v5 4 策略的平均作对比
        v5_means = []
        for s in ['BlinkHop', 'StaticScan', 'Patrol', 'Hybrid']:
            x = v5['by_strategy'][s]['overall']
            v5_means.append((s, x['cleared_mean'], x['clear_rate_mean'],
                             x['clear_rate_full'], x['avg_time_mean']))
        for name, cl, cr, fr, at in v5_means:
            print(f"v5/{name:<10} {cl:>10.2f} {cr*100:>9.1f}% "
                  f"{fr*100:>9.1f}% {at:>12.1f}")
        # 改进幅度（用 v5 最好的对比 v6）
        best_v5 = max(v5_means, key=lambda x: x[1])
        delta_cl = overall['cleared_mean'] - best_v5[1]
        delta_at = overall['avg_time_mean'] - best_v5[4]
        print(f"\n相对 v5 最优（{best_v5[0]}）："
              f"清除数 {'+' if delta_cl >= 0 else ''}{delta_cl:.2f}, "
              f"单源时 {'+' if delta_at >= 0 else ''}{delta_at:.1f}s")

    # Markdown
    md = ["# v6 baseline\n", f"共 {N_ROUNDS} 局 mock。\n",
          "\n## 整体\n",
          "| 指标 | 值 |",
          "|---|---|",
          f"| 平均清除数 | {overall['cleared_mean']:.2f} |",
          f"| 中位清除数 | {overall['cleared_median']:.1f} |",
          f"| min–max | {overall['cleared_min']}–{overall['cleared_max']} |",
          f"| 清除率 | {overall['clear_rate_mean']*100:.1f}% |",
          f"| 全清率 | {overall['clear_rate_full']*100:.1f}% |",
          f"| 平均定位清除时间 (s) | {overall['avg_time_mean']:.1f} |",
          f"| 平均虚拟时间 (s) | {overall['virtual_time_mean']:.1f} |",
          f"| 平均测量次数 | {overall['measures_mean']:.1f} |",
          f"| 平均清除次数 | {overall['clears_mean']:.2f} |",
          "\n## 按 N 分组\n",
          "| N | 局数 | 平均清除 | 清除率 | 全清率 | 单源时 (s) |",
          "|---|---|---|---|---|---|"]
    for N in sorted(byn.keys()):
        x = byn[N]
        t = x['avg_time_mean']
        ts = f"{t:.1f}" if t != float('inf') else "—"
        md.append(f"| {N} | {x['N_rounds']} | {x['cleared_mean']:.2f} | "
                  f"{x['clear_rate_mean']*100:.1f}% | "
                  f"{x['clear_rate_full']*100:.1f}% | {ts} |")
    if v5:
        md.append("\n## vs v5 baseline 对比\n")
        md.append("| 策略 | 平均清除 | 清除率 | 全清率 | 单源时 (s) |")
        md.append("|---|---|---|---|---|")
        for name, cl, cr, fr, at in v5_means:
            md.append(f"| v5/{name} | {cl:.2f} | {cr*100:.1f}% | "
                      f"{fr*100:.1f}% | {at:.1f} |")
        md.append(f"| **V6** | **{overall['cleared_mean']:.2f}** | "
                  f"**{overall['clear_rate_mean']*100:.1f}%** | "
                  f"**{overall['clear_rate_full']*100:.1f}%** | "
                  f"**{overall['avg_time_mean']:.1f}** |")
    with open(os.path.join(OUT, 'summary_v6.md'), 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    print(f"\n结果：results/summary_v6.{{json,md}}")


if __name__ == "__main__":
    main()