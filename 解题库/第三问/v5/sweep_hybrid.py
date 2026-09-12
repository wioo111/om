# -*- coding: utf-8 -*-
# sweep_hybrid.py
# 机器 B 用：Hybrid 策略超参扫描
#
# 扫描 2 个维度：
#   - 切换阈值 switch_at = [1, 3, 5, 8]  （已清除几个频道后从 hop 切到 static）
#   - 闪烁跳跃距离 hop_dist = [500, 800, 1200]
# 共 12 种组合 × N_ROUNDS 局
#
# 用法：
#   python sweep_hybrid.py
#   python sweep_hybrid.py --rounds 50
#
# 输出：results/sweep.json + results/sweep.md + results/figures/sweep_*.png

import os
import json
import statistics
import argparse
from collections import defaultdict
from typing import List

from mock_simulator import MockSimulator
import strategy as st_mod
from robot import run_with_sim

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
os.makedirs(OUT, exist_ok=True)

SWITCH_ATS = [1, 3, 5, 8]
HOP_DISTS = [500, 800, 1200]
SEED_BASE = 20260912


def make_hybrid(switch_at: int, hop_dist: float) -> st_mod.Hybrid:
    h = st_mod.Hybrid()
    h._switch_at = switch_at
    # HOP_DIST 在 BlinkHop.second_pos 和 _extra_pos 用到，要 patch 模块级常量
    st_mod.HOP_DIST = hop_dist
    return h


def run_one(switch_at: int, hop_dist: float, seed: int) -> dict:
    sim = MockSimulator(seed=seed)
    h = make_hybrid(switch_at, hop_dist)
    state = st_mod.State(pos=(0.0, 0.0), ch=1)
    sim.enter()
    state.virtual_time = 0.0
    n_steps = 0
    while n_steps < 8000:
        a = h.step(state)
        if a.kind == 'done':
            break
        if a.kind in ('measure', 'clear'):
            state.pos = a.pos
            state.ch = a.ch
        if a.kind == 'measure':
            resp = sim.measure(a.pos[0], a.pos[1], a.ch)
            r = resp.measure_result
            svd = resp.svd_deg if r == 'direction' else None
            h.on_measure(state, a.ch, r, svd)
        elif a.kind == 'clear':
            resp = sim.clear(a.pos[0], a.pos[1], a.ch)
            h.on_clear(state, a.ch, resp.clear_result == 'success')
        state.virtual_time = resp.virtual_time_s
        n_steps += 1
    sim.exit()
    s = sim.stats()
    s['switch_at'] = switch_at
    s['hop_dist'] = hop_dist
    s['seed'] = seed
    return s


def summarize(records: List[dict]) -> dict:
    if not records:
        return {}
    cleared = [r['cleared'] for r in records]
    times = [r['avg_time_per_cleared'] for r in records if r['cleared'] > 0]
    return {
        'N': len(records),
        'cleared_mean': statistics.mean(cleared),
        'cleared_min': min(cleared),
        'cleared_max': max(cleared),
        'clear_rate_full': sum(1 for c in cleared if c == max(cleared)) / len(records),
        'avg_time_mean': (statistics.mean(times) if times else float('inf')),
        'avg_time_median': (statistics.median(times) if times else float('inf')),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=30)
    args = ap.parse_args()
    n_rounds = args.rounds
    print(f"Hybrid 超参扫描：{len(SWITCH_ATS)}×{len(HOP_DISTS)}={len(SWITCH_ATS)*len(HOP_DISTS)} 组，"
          f"每组 {n_rounds} 局，共 {len(SWITCH_ATS)*len(HOP_DISTS)*n_rounds} 局\n")

    all_records = []
    for sa in SWITCH_ATS:
        for hd in HOP_DISTS:
            print(f"\n=== switch_at={sa}, hop_dist={hd} ===")
            for k in range(n_rounds):
                seed = SEED_BASE + k * 13 + sa * 1000 + int(hd)
                r = run_one(sa, hd, seed)
                print(f"  [{k+1:2d}/{n_rounds}] N={r['N']:2d} "
                      f"cleared={r['cleared']:2d} "
                      f"virt={r['virtual_time_s']:.1f}s")
                all_records.append(r)

    # 按 (switch_at, hop_dist) 汇总
    by_param = defaultdict(list)
    for r in all_records:
        by_param[(r['switch_at'], r['hop_dist'])].append(r)
    summary = {f"{sa},{hd}": summarize(rs)
               for (sa, hd), rs in sorted(by_param.items())}

    out = {
        'N_ROUNDS': n_rounds,
        'SWITCH_ATS': SWITCH_ATS,
        'HOP_DISTS': HOP_DISTS,
        'by_param': summary,
    }
    with open(os.path.join(OUT, 'sweep.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    with open(os.path.join(OUT, 'sweep_raw.json'), 'w') as f:
        json.dump(all_records, f, indent=2, default=str)

    # Markdown 表
    md = ["# Hybrid 超参扫描结果\n",
          f"每组 {n_rounds} 局 mock。\n",
          "## 平均定位清除时间（秒）+ 全部清除率\n",
          "| switch_at \\ hop_dist | " + " | ".join(
              f"{hd} m" for hd in HOP_DISTS) + " |",
          "|---" * (len(HOP_DISTS) + 1) + "|"]
    for sa in SWITCH_ATS:
        row = [f"{sa}"]
        for hd in HOP_DISTS:
            x = summary[f"{sa},{hd}"]
            t = x['avg_time_mean']
            fr = x['clear_rate_full'] * 100
            row.append(f"{t:.1f}s / {fr:.0f}%")
        md.append("| " + " | ".join(row) + " |")

    md.append("\n## 平均清除数")
    md.append("| switch_at \\ hop_dist | " + " | ".join(
        f"{hd} m" for hd in HOP_DISTS) + " |")
    md.append("|---" * (len(HOP_DISTS) + 1) + "|")
    for sa in SWITCH_ATS:
        row = [f"{sa}"]
        for hd in HOP_DISTS:
            x = summary[f"{sa},{hd}"]
            row.append(f"{x['cleared_mean']:.1f}")
        md.append("| " + " | ".join(row) + " |")

    with open(os.path.join(OUT, 'sweep.md'), 'w', encoding='utf-8') as f:
        f.write("\n".join(md))

    # 画热力图
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        T = np.zeros((len(SWITCH_ATS), len(HOP_DISTS)))
        F = np.zeros((len(SWITCH_ATS), len(HOP_DISTS)))
        for i, sa in enumerate(SWITCH_ATS):
            for j, hd in enumerate(HOP_DISTS):
                x = summary[f"{sa},{hd}"]
                T[i, j] = x['avg_time_mean'] if x['avg_time_mean'] != float('inf') else 1e3
                F[i, j] = x['clear_rate_full'] * 100
        im0 = axes[0].imshow(T, aspect='auto', cmap='viridis_r')
        axes[0].set_xticks(range(len(HOP_DISTS))); axes[0].set_xticklabels(HOP_DISTS)
        axes[0].set_yticks(range(len(SWITCH_ATS))); axes[0].set_yticklabels(SWITCH_ATS)
        axes[0].set_xlabel('HOP_DIST (m)'); axes[0].set_ylabel('switch_at')
        axes[0].set_title('平均定位清除时间 (s)')
        for i in range(len(SWITCH_ATS)):
            for j in range(len(HOP_DISTS)):
                axes[0].text(j, i, f'{T[i,j]:.0f}', ha='center', va='center',
                             color='white', fontsize=8)
        plt.colorbar(im0, ax=axes[0])

        im1 = axes[1].imshow(F, aspect='auto', cmap='RdYlGn', vmin=0, vmax=100)
        axes[1].set_xticks(range(len(HOP_DISTS))); axes[1].set_xticklabels(HOP_DISTS)
        axes[1].set_yticks(range(len(SWITCH_ATS))); axes[1].set_yticklabels(SWITCH_ATS)
        axes[1].set_xlabel('HOP_DIST (m)'); axes[1].set_ylabel('switch_at')
        axes[1].set_title('全部清除率 (%)')
        for i in range(len(SWITCH_ATS)):
            for j in range(len(HOP_DISTS)):
                axes[1].text(j, i, f'{F[i,j]:.0f}%', ha='center', va='center',
                             color='black', fontsize=8)
        plt.colorbar(im1, ax=axes[1])
        plt.tight_layout()
        plt.savefig(os.path.join(OUT, 'figures', 'sweep_heatmap.png'), dpi=150)
        plt.close()
        print("\n热力图已写入 results/figures/sweep_heatmap.png")
    except Exception as e:
        print(f"画图失败（不影响结果）：{e}")

    print(f"\n结果：results/sweep.json + results/sweep.md")
    print("\n平均定位清除时间热力图（秒）：")
    print("       " + "  ".join(f"{hd:>6}m" for hd in HOP_DISTS))
    for sa in SWITCH_ATS:
        row = [f"sa={sa:2d}"]
        for hd in HOP_DISTS:
            t = summary[f"{sa},{hd}"]['avg_time_mean']
            row.append(f"  {t:6.1f}" if t != float('inf') else "  ----")
        print(" ".join(row))


if __name__ == "__main__":
    main()
