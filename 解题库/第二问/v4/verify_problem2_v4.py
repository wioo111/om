# -*- coding: utf-8 -*-
r"""问题二 v4 一站式验证脚本。

顺序执行：
  1) 第一问 v4 自检（11 项：T0 单扇形、T1 方向正交 8 项、T2-T6）
  2) 第二问 v4 5 策略仿真 + 统计输出
  3) 画图（3 张：fig_strategies / fig_thales_geometry / fig_heatmap_L）
  4) 与报告数字核对（assertion 形式）

运行：
  cd C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第二问\v4
  set PYTHONPATH=..\..\第一问\v4
  python -X utf8 verify_problem2_v4.py
"""
from __future__ import annotations
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
PY = sys.executable
P1 = HERE.parent.parent / '第一问' / 'v4'


def run(label, args, env=None):
    print(f"\n=== {label} ===")
    e = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    if env:
        e.update(env)
    r = subprocess.run([PY, '-X', 'utf8'] + args, cwd=str(HERE), env=e)
    if r.returncode != 0:
        print(f"[FAIL] {label} 返回 {r.returncode}")
        sys.exit(1)


def main():
    # 1) 第一问 v4 自检
    run("1) 第一问 v4 自检", [str(P1 / 'problem1_v4.py')])

    # 2) 第二问 v4 仿真
    run("2) 第二问 v4 5 策略仿真", [str(HERE / 'problem2_v4.py')])

    # 3) 画图
    run("3) 画图（3 张）", [str(HERE / 'plot_problem2.py')])

    # 4) 核对 strategy_results.json 与报告数字
    print("\n=== 4) 报告数字核对 ===")
    with open(HERE / 'strategy_results.json', encoding='utf-8') as f:
        data = json.load(f)

    expected = {
        'Thales 圆 (L=d·tan ε)': {'med_D_max': 40, 'min_D': 15, 'cover_min': 99.0},
        '最佳共线 (L*=1.56d)':   {'med_D_max': 90, 'min_D': 0,  'cover_min': 90.0},
        '随机':                  {'med_D_max': 100, 'min_D': 0, 'cover_min': 85.0},
        '平行共线':              {'med_D_min': 1300, 'cover_max': 75.0},
        '反平行':                {'med_D_min': 1300, 'cover_max': 75.0},
    }

    print(f"{'策略':<28}{'N':>5}{'中位D':>10}{'P95':>10}{'最大':>10}{'中位2R/D':>11}{'覆盖率':>9}")
    print('-' * 84)

    failed = []
    for name, data_dict in data.items():
        Ds = data_dict.get('D', [])
        rs = data_dict.get('ratios', [])
        cs = data_dict.get('covered', [])
        N = len(Ds)
        if N == 0:
            print(f"{name:<28} 空")
            continue
        Ds_sorted = sorted(Ds)
        p95 = Ds_sorted[int(0.95 * N)]
        med_D = statistics.median(Ds)
        max_D = max(Ds)
        med_r = statistics.median(rs)
        cov = sum(cs) / len(cs) * 100
        print(f"{name:<28}{N:>5}{med_D:>10.1f}{p95:>10.1f}{max_D:>10.1f}{med_r:>11.4f}{cov:>8.1f}%")

        exp = expected.get(name, {})
        if 'med_D_max' in exp and med_D > exp['med_D_max']:
            failed.append(f"{name}: 中位 D={med_D:.1f} 超过预期上界 {exp['med_D_max']}")
        if 'med_D_min' in exp and med_D < exp['med_D_min']:
            failed.append(f"{name}: 中位 D={med_D:.1f} 低于预期下界 {exp['med_D_min']}")
        if 'min_D' in exp and min(Ds) < exp['min_D']:
            failed.append(f"{name}: 最小 D={min(Ds):.2f} 低于预期下界 {exp['min_D']}")
        if 'cover_min' in exp and cov < exp['cover_min']:
            failed.append(f"{name}: 覆盖率={cov:.1f}% 低于预期下界 {exp['cover_min']}%")
        if 'cover_max' in exp and cov > exp['cover_max']:
            failed.append(f"{name}: 覆盖率={cov:.1f}% 高于预期上界 {exp['cover_max']}%")

    print()
    if failed:
        print("[FAIL] 以下核对失败：")
        for f in failed:
            print(f"   - {f}")
        sys.exit(1)
    else:
        print("[OK] 所有数字核对通过（与报告预期区间一致）")

    # 5) Thales 圆公式核对
    print("\n=== 5) Thales 圆公式核对 ===")
    import math
    eps = math.radians(1.0)
    for d in [500, 1000, 1500]:
        L = d * math.tan(eps)
        print(f"  d={d:>4} m  →  L = d·tan(1°) = {L:.2f} m")


if __name__ == '__main__':
    main()
