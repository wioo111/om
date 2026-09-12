# -*- coding: utf-8 -*-
# reproduce.py
# 机器 C 用：基线复现 + 极端 case 测试
#
# 两个部分：
#   Part A. 多 seed 复现：用不同 seed_base 跑同样 4 套策略 × 30 局，
#           验证结果是否稳定（不应只对某个 seed 偶然高/低）
#   Part B. 极端 case：干扰源全部聚集在 (1500, 0) 附近（最坏情况）：
#           - 同位置干扰源：所有源挤在直径 100 m 圆盘内
#           - 远场源：所有源在距离原点 > 1600 m 处
#           - 边界源：所有源紧贴目标区边缘
#
# 用法：python reproduce.py

import os
import json
import statistics
from collections import defaultdict
from typing import List
import random
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from mock_simulator import MockSimulator, ARENA_RADIUS, CHANNELS
import strategy as st_mod
from robot import run_with_sim

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
os.makedirs(OUT, exist_ok=True)

STRATEGIES = ['BlinkHop', 'StaticScan', 'Patrol', 'Hybrid']
N_ROUNDS = 30
SEED_BASES = [42, 2024, 12345]   # 3 批不同 seed


# ============================================================
# Part A. 多 seed 复现
# ============================================================
def part_a():
    print("=" * 60)
    print("Part A. 多 seed 复现")
    print("=" * 60)
    results = []
    for sb in SEED_BASES:
        print(f"\n--- seed_base={sb} ---")
        for s_name in STRATEGIES:
            cleared_list = []
            for k in range(N_ROUNDS):
                sim = MockSimulator(seed=sb + k * 7)
                stats = run_with_sim(s_name, sim, max_steps=8000)
                cleared_list.append(stats['cleared'])
            mean = statistics.mean(cleared_list)
            std = statistics.stdev(cleared_list) if len(cleared_list) > 1 else 0
            print(f"  {s_name:12s}  mean={mean:5.1f}  std={std:4.2f}  "
                  f"min={min(cleared_list)}  max={max(cleared_list)}")
            results.append({
                'part': 'A', 'seed_base': sb, 'strategy': s_name,
                'mean': mean, 'std': std,
                'min': min(cleared_list), 'max': max(cleared_list),
            })
    return results


# ============================================================
# Part B. 极端 case
# ============================================================
class ExtremeMockSimulator(MockSimulator):
    """支持指定源分布的极端 mock。"""
    def __init__(self, seed: int, source_pos_fn, N: int = 12,
                 R_eff_range=(1000.0, 1500.0), verbose: bool = False):
        self.seed = seed
        self.rng = random.Random(seed)
        self.N = N
        self.R_eff_range = R_eff_range
        self.verbose = verbose
        self.pos = (0.0, 0.0)
        self.cur_ch = 1
        self.entered = False
        self.virtual_time = 0.0
        self.measure_count = 0
        self.clear_count = 0
        self.log = []
        # 用 source_pos_fn(i, rng) 生成第 i 个源位置
        chs = self.rng.sample(CHANNELS, N)
        from mock_simulator import Source
        self.sources = {}
        for i, ch in enumerate(chs):
            pos = source_pos_fn(i, self.rng)
            R_eff = self.rng.uniform(*R_eff_range)
            self.sources[ch] = Source(ch=ch, pos=pos, R_eff=R_eff)


def cluster_sources(i, rng):
    """所有源挤在 (1500, 0) 附近 100 m 圆盘内。"""
    r = 100 * math.sqrt(rng.random())
    a = 2 * math.pi * rng.random()
    return (1500 + r * math.cos(a), r * math.sin(a))


def far_sources(i, rng):
    """所有源距离原点 > 1600 m（在 R_eff=1500 内基本都接不到，只有 1000-1500 那部分能）。"""
    while True:
        x = rng.uniform(-ARENA_RADIUS, ARENA_RADIUS)
        y = rng.uniform(-ARENA_RADIUS, ARENA_RADIUS)
        if x*x + y*y >= 1600*1600 and x*x + y*y <= ARENA_RADIUS*ARENA_RADIUS:
            return (x, y)


def edge_sources(i, rng):
    """所有源紧贴目标区边缘（1750-1800 m）。"""
    a = 2 * math.pi * rng.random()
    r = 1750 + 50 * rng.random()
    return (r * math.cos(a), r * math.sin(a))


EXTREME_CASES = {
    'cluster_1500': cluster_sources,
    'far_1600+': far_sources,
    'edge_1750+': edge_sources,
}


def part_b():
    print("\n" + "=" * 60)
    print("Part B. 极端 case")
    print("=" * 60)
    results = []
    for case_name, fn in EXTREME_CASES.items():
        print(f"\n--- case: {case_name} ---")
        for s_name in STRATEGIES:
            cleared_list = []
            times_list = []
            for k in range(N_ROUNDS):
                seed = 99000 + k * 7
                sim = ExtremeMockSimulator(seed=seed, source_pos_fn=fn, N=12)
                # 复用 run_with_sim 的逻辑但用 sim.measure 等
                from robot import run_with_sim
                # 临时把 sim 替换为带极端源分布的实例
                stats = run_with_sim(s_name, sim, max_steps=8000)
                cleared_list.append(stats['cleared'])
                if stats['cleared'] > 0:
                    times_list.append(stats['avg_time_per_cleared'])
            mean = statistics.mean(cleared_list)
            at = statistics.mean(times_list) if times_list else float('inf')
            print(f"  {s_name:12s}  cleared={mean:5.1f}  "
                  f"avg_time={at:6.1f}s  "
                  f"min={min(cleared_list)}  max={max(cleared_list)}")
            results.append({
                'part': 'B', 'case': case_name, 'strategy': s_name,
                'mean_cleared': mean, 'mean_avg_time': at,
                'min_cleared': min(cleared_list), 'max_cleared': max(cleared_list),
            })
    return results


def main():
    a_results = part_a()
    b_results = part_b()

    out = {'part_a': a_results, 'part_b': b_results}
    with open(os.path.join(OUT, 'reproduce.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Markdown
    md = ["# 复现 + 极端 case 测试\n", "## Part A. 多 seed 复现\n",
          "| seed_base | 策略 | 平均清除 | 标准差 | min | max |",
          "|---|---|---|---|---|---|"]
    for r in a_results:
        md.append(f"| {r['seed_base']} | {r['strategy']} | {r['mean']:.1f} | "
                  f"{r['std']:.2f} | {r['min']} | {r['max']} |")
    md.append("\n## Part B. 极端 case\n")
    md.append("| 场景 | 策略 | 平均清除 | 平均定位清除时间 (s) | min | max |")
    md.append("|---|---|---|---|---|---|")
    for r in b_results:
        at = r['mean_avg_time']
        at_s = f"{at:.1f}" if at != float('inf') else "—"
        md.append(f"| {r['case']} | {r['strategy']} | {r['mean_cleared']:.1f} | "
                  f"{at_s} | {r['min_cleared']} | {r['max_cleared']} |")
    with open(os.path.join(OUT, 'reproduce.md'), 'w', encoding='utf-8') as f:
        f.write("\n".join(md))

    # 画图：Part B
    fig, ax = plt.subplots(figsize=(9, 4))
    cases = list(EXTREME_CASES.keys())
    width = 0.2
    x = list(range(len(cases)))
    for i, s in enumerate(STRATEGIES):
        ys = []
        for c in cases:
            row = next((r for r in b_results
                        if r['case'] == c and r['strategy'] == s), None)
            ys.append(row['mean_cleared'] if row else 0)
        ax.bar([xi + i*width for xi in x], ys, width, label=s)
    ax.set_xticks([xi + 1.5*width for xi in x])
    ax.set_xticklabels(cases)
    ax.set_ylabel('平均清除数（满分 12）')
    ax.set_title('极端 case 下各策略表现')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, 'figures', 'extreme_cases.png'), dpi=150)
    plt.close()

    print(f"\n结果：results/reproduce.json + results/reproduce.md + "
          f"results/figures/extreme_cases.png")


if __name__ == "__main__":
    main()
