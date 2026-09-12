# -*- coding: utf-8 -*-
r"""第一问 v5 验收脚本（独立于 run_experiments.py 的断言式检查）。

运行： python -X utf8 verify_problem1_v5.py
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
sys.path.insert(0, HERE)
import problem1_core as p1  # noqa: E402

FAILS: list = []


def check(name: str, ok: bool, detail: str = '') -> None:
    print(f'  [{"PASS" if ok else "FAIL"}] {name}' + (f'  -- {detail}' if detail else ''))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print('=' * 78)
    print('第一问 v5 验收')
    print('=' * 78)

    # ---------- 1. 方向一致：反向扇形必为空 ----------
    r = p1.solve([(0.0, 0.0), (500.0, 0.0)], [90.0, 270.0])
    check('反向扇形交集为空', r['is_empty'])

    # ---------- 2. Jung 上下界与覆盖判据等价性 ----------
    rng = random.Random(20260912)
    qmin, qmax = 1e9, -1e9
    n_cov = n_unc = 0
    bad1 = bad2 = 0
    for _ in range(800):
        sc = p1.random_scene(rng.choice([2, 3, 4, 5, 6]), rng)
        if not sc['ok']:
            continue
        rr = p1.solve(sc['dets'], sc['thetas'])
        if rr['is_empty']:
            continue
        qmin, qmax = min(qmin, rr['q']), max(qmax, rr['q'])
        if rr['q'] < 1.0 - 1e-9 or rr['q'] > p1.JUNG_Q + 1e-9:
            bad1 += 1
        if rr['covered'] and abs(rr['q'] - 1.0) > 1e-6:
            bad2 += 1
        if (not rr['covered']) and rr['q'] <= 1.0 + 1e-12:
            bad2 += 1
        n_cov += int(rr['covered'])
        n_unc += int(not rr['covered'])
    check('Jung 界 1 <= q <= 2/sqrt(3)', bad1 == 0,
          f'q∈[{qmin:.9f},{qmax:.9f}]，越界 {bad1} 例')
    check('covered <=> q = 1', bad2 == 0,
          f'覆盖 {n_cov} 例 / 不覆盖 {n_unc} 例，反例 {bad2} 例')
    check('q 下界紧（最小 q ≈ 1）', abs(qmin - 1.0) < 1e-9, f'q_min={qmin:.15f}')

    # ---------- 3. 正三角形取到 Jung 上界 ----------
    D = 137.0
    tri = [(0.0, 0.0), (D, 0.0), (D / 2, D * math.sqrt(3) / 2)]
    rr = p1.analyze_region(tri)
    check('正三角形 q = 2/sqrt(3)（Jung 上界取等）',
          abs(rr['q'] - p1.JUNG_Q) < 1e-12 and not rr['covered'],
          f'q={rr["q"]:.15f}, off={rr["off"]:.3f}')

    # ---------- 4. 外逼近误差公式与几何定义一致 ----------
    ok4 = True
    for N in (8, 16, 32, 64, 128, 256, 512, 1024, 2048):
        theo = p1.disk_outer_error(p1.R_EFF, N)
        geo = p1.R_EFF / math.cos(math.pi / N) - p1.R_EFF
        ok4 = ok4 and abs(theo - geo) < 1e-9
    check('Δr = r(sec(π/N) − 1) 与顶点半径一致', ok4)

    # ---------- 5. 角度窗口自适应裁剪 ≡ 全 N 条切线 ----------
    def loc_full(dets, thetas, N):
        hps = []
        for S, th in zip(dets, thetas):
            lo, hi = p1.sector_halfplanes(S, th, 1.0)
            hps += [lo, hi]
        poly = p1.clip_halfplanes(p1.bbox_polygon(p1.R_TARGET * 1.0001), hps)
        poly = p1.clip_halfplanes(poly, p1.disk_tangent_halfplanes(p1.ORIGIN, p1.R_TARGET, N))
        for S in dets:
            poly = p1.clip_halfplanes(poly, p1.disk_tangent_halfplanes(S, p1.R_EFF, N))
        return p1.simplify_convex(poly, p1.SIMPLIFY_TOL) if poly else None

    def hausdorff(a, b):
        def d2poly(P, poly):
            best = 1e18
            n = len(poly)
            for i in range(n):
                A, B = poly[i], poly[(i + 1) % n]
                ex, ey = B[0] - A[0], B[1] - A[1]
                L = ex * ex + ey * ey
                t = 0.0 if L == 0 else max(0.0, min(1.0, ((P[0] - A[0]) * ex + (P[1] - A[1]) * ey) / L))
                q = (A[0] + t * ex, A[1] + t * ey)
                best = min(best, math.hypot(P[0] - q[0], P[1] - q[1]))
            return best
        return max(max(d2poly(P, b) for P in a), max(d2poly(P, a) for P in b))

    rng = random.Random(7)
    worst = 0.0
    for _ in range(60):
        sc = p1.random_scene(rng.choice([2, 3, 4]), rng)
        if not sc['ok']:
            continue
        A = p1.localization_region(sc['dets'], sc['thetas'], 1.0, p1.R_EFF, p1.R_TARGET, 256)
        B = loc_full(sc['dets'], sc['thetas'], 256)
        if A is None or B is None:
            continue
        worst = max(worst, hausdorff(A, B))
    check('角度窗口裁剪 ≡ 全 256 条切线', worst < 1e-9, f'最大 Hausdorff={worst:.3e} m')

    # ---------- 6. 检测点必须在 Ω 内 ----------
    rng = random.Random(11)
    bad = 0
    for _ in range(400):
        sc = p1.random_scene(5, rng)
        if not sc['ok']:
            bad += 1
            continue
        bad += sum(1 for S in sc['dets'] if math.hypot(*S) > p1.R_TARGET + 1e-9)
    check('随机场景的检测点全部位于 Ω 内', bad == 0, f'违规 {bad}')

    # ---------- 7. 顶点简化对 D 的影响可忽略 ----------
    rng = random.Random(13)
    worst_d = 0.0
    for _ in range(200):
        sc = p1.random_scene(rng.choice([2, 3, 4]), rng)
        if not sc['ok']:
            continue
        poly = p1.localization_region(sc['dets'], sc['thetas'], 1.0, p1.R_EFF, p1.R_TARGET, 256)
        if poly is None:
            continue
        D1 = p1.polygon_diameter(p1.simplify_convex(poly, 1e-3))[0]
        D0 = p1.polygon_diameter(p1.simplify_convex(poly, 0.0))[0]
        worst_d = max(worst_d, abs(D1 - D0))
    check('顶点简化对 D 的影响 < 0.02 m', worst_d < 0.02, f'最大影响 {worst_d:.4f} m')

    # ---------- 8. 报告数字与 key_numbers.json 完全同源 ----------
    kp = os.path.join(RES, 'key_numbers.json')
    if os.path.exists(kp):
        with open(kp, encoding='utf-8') as f:
            k = json.load(f)
        check('自检总判定为 ALL PASS', bool(k['selftest_all_pass']))
        chk = k['mc_consistency']
        check('MC 样本 Jung 界无越界',
              chk['violate_lower'] == 0 and chk['violate_upper'] == 0,
              f"q∈[{chk['q_min']:.6f},{chk['q_max']:.6f}]")
        jt = k['jung_tight']
        check('Jung 紧构造 q ≈ 2/sqrt(3)',
              abs(jt['q'] - p1.JUNG_Q) / p1.JUNG_Q < 1e-5,
              f"q={jt['q']:.7f} vs {p1.JUNG_Q:.7f}")
        conv = {r['N']: r for r in k['disk_convergence_summary']}
        check('N=256 的 D 平均相对误差 < 1e-4',
              conv[256]['mean_rel_err_D'] < 1e-4,
              f"{conv[256]['mean_rel_err_D']:.3e}")
        check('N=32 的最大相对误差 > 10 %（说明旧版精度不足）',
              conv[32]['max_rel_err_D'] > 0.10, f"{conv[32]['max_rel_err_D']:.4f}")
    else:
        check('存在 results/key_numbers.json（需先运行 run_experiments.py）', False)

    print('=' * 78)
    if FAILS:
        print(f'验收未通过：{len(FAILS)} 项失败 -> {FAILS}')
        return 1
    print('第一问验收全部通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
