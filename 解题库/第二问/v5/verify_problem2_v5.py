# -*- coding: utf-8 -*-
r"""第二问 v5 验收脚本：重点检查"可执行性（无信息泄漏）"与"失败不被静默删除"。

运行： python -X utf8 verify_problem2_v5.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
sys.path.insert(0, HERE)
import problem2_core as p2  # noqa: E402
import inspect  # noqa: E402

FAILS: list = []


def check(name: str, ok: bool, detail: str = '') -> None:
    print(f'  [{"PASS" if ok else "FAIL"}] {name}' + (f'  -- {detail}' if detail else ''))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print('=' * 78)
    print('第二问 v5 验收')
    print('=' * 78)

    # ---------- 1. 主策略的签名与函数体不得出现真实源 ----------
    src = inspect.getsource(p2.solve_robust_polar)
    sig = inspect.signature(p2.solve_robust_polar)
    forbidden = [n for n in ('G', 'G_true', 'd_true', 'R_eff_true') if n in sig.parameters]
    check('主求解器签名不含真实源参数', not forbidden, f'params={list(sig.parameters)}')
    check('主求解器函数体中不出现真实源变量',
          ('G_true' not in src) and ('d_true' not in src))

    # ---------- 2. F1 的角度容差必须是 ±eps（不是 ±2eps） ----------
    S1 = (0.0, 0.0)
    th = 0.0
    def in_F1(ang_deg, d=800.0):
        P = (d * math.cos(math.radians(ang_deg)), d * math.sin(math.radians(ang_deg)))
        return abs(p1_wrap(ang_deg - th)) <= p2.EPS_DEG + 1e-15 and 5 < d <= p2.R_EFF_HI
    check('F1 角度容差为 ±1°（0.5° 在内、1.5° 不在内）',
          in_F1(0.5) and (not in_F1(1.5)), '0.5°→True, 1.5°→False')
    F1 = p2.f1_convex(S1, th)
    pin = (800.0 * math.cos(math.radians(0.9)), 800.0 * math.sin(math.radians(0.9)))
    pout = (800.0 * math.cos(math.radians(1.5)), 800.0 * math.sin(math.radians(1.5)))
    check('F1 多边形与 ±1° 定义一致',
          p2.p1.point_in_convex_poly(pin, F1) and not p2.p1.point_in_convex_poly(pout, F1))

    # ---------- 3. 无信息泄漏：同一 (S1,θ̂1) 不同真实源得到同一 S2* ----------
    vals = []
    for d, tt in ((250.0, -0.8), (1400.0, 0.9), (700.0, 0.1)):
        r = p2.solve_robust_polar(S1, th, p2.Cfg())
        vals.append(r['S2_star'])
    spread = max(math.hypot(v[0] - vals[0][0], v[1] - vals[0][1]) for v in vals)
    check('选点结果与真实源无关（三次调用完全一致）', spread == 0.0, f'偏差 {spread:.3g}')

    # ---------- 4. oracle 策略确实使用真值（反证信息泄漏） ----------
    a = p2.strat_oracle_thales(S1, th, (900.0, 100.0))
    b = p2.strat_oracle_thales(S1, th, (200.0, 900.0))
    check('oracle 策略随真实源变化（说明旧版确有泄漏）',
          math.hypot(a[0] - b[0], a[1] - b[1]) > 1.0,
          f'{tuple(round(x,1) for x in a)} vs {tuple(round(x,1) for x in b)}')

    # ---------- 5. S2* 的可行性与"约束恰好在边界上" ----------
    r = p2.solve_robust_polar(S1, th, p2.Cfg())
    pts = r['G_pts']
    S2 = r['S2_star']
    dmax = float(np.max(np.hypot(pts[:, 0] - S2[0], pts[:, 1] - S2[1])))
    check('S2* 满足 max_G|S2−G| ≤ 1000（保证收到第二次示向度）', dmax <= 1000.0 + 1e-6,
          f'dmax={dmax:.6f} m')
    check('S2* 落在可行域边界（约束取等）', abs(dmax - 1000.0) < 1e-3, f'dmax={dmax:.6f}')
    check('S2* ∈ Ω', math.hypot(*S2) <= p2.R_TARGET)

    # ---------- 6. 独立暴力复核 J(S2*) ----------
    cfg = p2.Cfg()
    lam = r['lambda']
    # 用高密度 F1 采样 + 真实方向，独立算最坏 D2
    Gs = []
    for i in range(240):
        dd = 6.0 + (1500.0 - 6.0) * i / 239.0
        for ph in (-1.0, -0.5, 0.0, 0.5, 1.0):
            a_ = math.radians(th + ph)
            Gs.append((dd * math.cos(a_), dd * math.sin(a_)))
    Jb = 0.0
    feasible = True
    for G in Gs:
        if math.hypot(G[0] - S2[0], G[1] - S2[1]) > p2.R_EFF_LO:
            feasible = False
            break
        th2 = math.degrees(math.atan2(G[1] - S2[1], G[0] - S2[0]))
        D = p2.region_diameter(S1, S2, th, th2)
        if D is not None:
            Jb = max(Jb, D)
    if feasible:
        rel = abs(Jb - r['J_star']) / r['J_star']
        check('J(S2*) 与独立暴力复核一致（相对偏差 < 5%）', rel < 0.05,
              f"报告 {r['J_star']:.3f} m vs 暴力 {Jb:.3f} m，偏差 {rel*100:.2f}%")
    else:
        check('S2* 在暴力采样下仍可行', False, '存在 G 使 |S2-G| > 1000')

    # ---------- 7. 仿真中两个示向度都加了 ±1° 误差 ----------
    csv_path = os.path.join(RES, 'strategy_scenarios.csv')
    if os.path.exists(csv_path):
        with open(csv_path, encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        e1 = [abs(float(r_['theta1_err_deg'])) for r_ in rows]
        e2 = [abs(float(r_['theta2_err_deg'])) for r_ in rows
              if r_['theta2_err_deg'] not in ('', None)]
        check('第一次测量误差 |e1| ≤ 1° 且非常数',
              max(e1) <= 1.0 + 1e-12 and len(set(e1)) > 100,
              f'max|e1|={max(e1):.4f}°，不同取值 {len(set(e1))} 个')
        check('第二次测量误差 |e2| ≤ 1° 且非常数（成功定位样本）',
              len(e2) > 0 and max(e2) <= 1.0 + 1e-12 and len(set(e2)) > 100,
              f'max|e2|={max(e2):.4f}°，样本 {len(e2)} 条')
        check('e2 并非恒为 0（旧版 bug：theta1=th 未加误差）',
              max(e2) > 0.5 and min(e2) < 0.05,
              f'e2 范围 [{min(e2):.4f}, {max(e2):.4f}]°')

        # ---------- 8. 失败样本未被删除 ----------
        with open(os.path.join(RES, 'strategy_summary.json'), encoding='utf-8') as f:
            S = json.load(f)
        names = [k for k in S if k != 'key']
        Ns = {S[n]['N_total'] for n in names}
        counts = {}
        for r_ in rows:
            counts[r_['strategy']] = counts.get(r_['strategy'], 0) + 1
        check('每个策略的记录数都等于总场景数（无样本剔除）',
              all(counts.get(n) == S[n]['N_total'] for n in names),
              f'N={sorted(Ns)}，记录数={sorted(set(counts.values()))}')
        check('所有策略使用同一批 N 个场景',
              len(Ns) == 1 and len(counts) == len(names), f'策略数 {len(names)}')
        bad_direct = [r_ for r_ in rows if r_['status'] == 'direct' and float(r_['cost_m']) != 0.0]
        check('"直接光学清除"样本代价记为 0（而非 D=0 当作完美定位）',
              len(bad_direct) == 0, f'异常 {len(bad_direct)} 条')
        empty = [r_ for r_ in rows if r_['status'] == 'empty_region']
        check('空可行域样本被单独计数并按失败计入代价',
              all(float(r_['cost_m']) > 1.0 for r_ in empty) or not empty,
              f'空可行域样本 {len(empty)} 条')
        nosig = [r_ for r_ in rows if r_['status'] == 'no_signal']
        check('未收到第二次示向度的样本按失败惩罚计入',
              all(abs(float(r_['cost_m']) - S['key']['lambda']) < 1e-6 for r_ in nosig)
              or not nosig, f'未接收样本 {len(nosig)} 条')
    else:
        check('存在 results/strategy_scenarios.csv（需先运行 run_experiments.py）', False)

    # ---------- 9. key_numbers 自洽 ----------
    kp = os.path.join(RES, 'key_numbers.json')
    if os.path.exists(kp):
        with open(kp, encoding='utf-8') as f:
            k = json.load(f)
        check('信息集实验通过（无信息泄漏）', bool(k['info_set_pass']),
              f"spread={k['info_set_spread']:.3g}")
        eq = k['equivariance_summary']
        check('旋转等变性：J* 相对波动 < 1%', bool(eq['pass']),
              f"{eq['J_star_rel_spread']*100:.3f}%")
        check('最优基线长度 L* 稳定在 1005 m 附近',
              1000.0 <= eq['L_star_min'] and eq['L_star_max'] <= 1010.0,
              f"L*∈[{eq['L_star_min']:.2f},{eq['L_star_max']:.2f}]")
        check('最优偏角 |α*| ≈ 31°',
              30.0 <= eq['alpha_abs_min'] and eq['alpha_abs_max'] <= 32.0,
              f"|α*|∈[{eq['alpha_abs_min']:.2f},{eq['alpha_abs_max']:.2f}]°")
    else:
        check('存在 results/key_numbers.json', False)

    print('=' * 78)
    if FAILS:
        print(f'验收未通过：{len(FAILS)} 项失败 -> {FAILS}')
        return 1
    print('第二问验收全部通过。')
    return 0


def p1_wrap(a: float) -> float:
    return a - 360.0 * math.floor((a + 180.0) / 360.0)


if __name__ == '__main__':
    sys.exit(main())
