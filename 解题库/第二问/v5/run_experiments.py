# -*- coding: utf-8 -*-
r"""问题二 v5 —— 全部数值实验。

产出（results/ 与 logs/）：
    results/info_set.json            信息集验证（选点过程不访问真实 G）
    results/equivariance.json        旋转等变性验证
    results/convergence.json         数值超参收敛性
    results/strategy_scenarios.csv   同批场景下各策略的逐场记录
    results/strategy_summary.json    各策略汇总（含失败率、分位数、综合代价）
    results/representative_case.npz  代表性算例的 J 场（供绘图）
    results/key_numbers.json         第二问报告引用的全部关键数字
    logs/run_experiments.log

运行： python -X utf8 run_experiments.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import statistics as st
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
LOG = os.path.join(HERE, 'logs')
os.makedirs(RES, exist_ok=True)
os.makedirs(LOG, exist_ok=True)

import problem2_core as p2  # noqa: E402

SEED = 20260912
N_SCEN = 400
CFG = p2.Cfg(grid_step=20.0, refine_step=5.0, refine_span=30.0)

_log: list = []


def log(msg: str) -> None:
    print(msg)
    _log.append(msg)


def dump(obj, name):
    with open(os.path.join(RES, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=float)
    log(f'  -> 写出 results/{name}')


def write_csv(rows, header, name):
    with open(os.path.join(RES, name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    log(f'  -> 写出 results/{name}')


# ================================================================ 场景
def make_scenarios(n: int, seed: int):
    r"""生成同批测试场景。

    S1 = (0,0)（题设：机器狗从原点出发）；
    真实源方位角 ~ U[0,360°)；距离 d 密度 ~ d（Omega 内按面积均匀）且 5 < d <= R_eff_true；
    R_eff_true ~ U[1000,1500]；
    e1, e2 ~ U[-1°,1°]（e2 对所有策略相同，构成配对比较）。
    """
    rng = random.Random(seed)
    out = []
    for k in range(n):
        th_true = rng.uniform(0.0, 360.0)
        r_eff = rng.uniform(p2.R_EFF_LO, p2.R_EFF_HI)
        lo = 5.0
        hi = min(r_eff, p2.R_TARGET)
        d = math.sqrt(rng.uniform(lo * lo, hi * hi))      # 面积均匀
        a = math.radians(th_true)
        G = (d * math.cos(a), d * math.sin(a))
        e1 = rng.uniform(-p2.EPS_DEG, p2.EPS_DEG)
        e2 = rng.uniform(-p2.EPS_DEG, p2.EPS_DEG)
        out.append({'k': k, 'S1': (0.0, 0.0), 'theta_true': th_true, 'd': d,
                    'G': G, 'R_eff_true': r_eff, 'e1': e1, 'e2': e2,
                    'theta1_hat': (th_true + e1) % 360.0})
    return out


# ================================================================ 实验 A：信息集
def exp_info_set():
    log('=' * 74)
    log('[实验 A] 选点过程是否只使用 (S1, theta1_hat, Omega, eps, R_eff 范围)？')
    S1 = (0.0, 0.0)
    th_hat = 47.3
    sols = []
    for i, (d, th_true) in enumerate([(300.0, 46.0), (1200.0, 47.9), (900.0, 45.1),
                                      (1500.0, 48.0), (60.0, 46.6)]):
        # 每次"真实源"完全不同（甚至不在 F1 里），但输入的 (S1, theta1_hat) 一样
        r = p2.solve_robust_polar(S1, th_hat, CFG)
        sols.append((d, th_true, r['S2_star'], r['J_star']))
    xs = [s[2][0] for s in sols]
    ys = [s[2][1] for s in sols]
    spread = max(math.hypot(x - xs[0], y - ys[0]) for x, y in zip(xs, ys))
    ok = spread < 1e-9
    for d, th_true, S2, J in sols:
        log(f'  真值 G 距 S1 {d:6.1f} m、真方位 {th_true:5.1f}° -> S2*=({S2[0]:.2f},{S2[1]:.2f}), J*={J:.3f}')
    log(f'  不同真实源解出的 S2* 最大偏差 = {spread:.3g} -> {"PASS（无信息泄漏）" if ok else "FAIL"}')
    return {'S1': S1, 'theta1_hat': th_hat, 'spread': spread, 'pass': ok,
            'runs': [{'d': d, 'theta_true': t, 'S2_star': list(s), 'J_star': j}
                     for d, t, s, j in sols]}


# ================================================================ 实验 B：等变性
def exp_equivariance():
    log('=' * 74)
    log('[实验 B] 旋转等变性：S1=原点时，S2*(theta) 应为 S2*(0) 的旋转/镜像')
    base = p2.solve_robust_polar((0.0, 0.0), 0.0, CFG)
    b = np.array(base['S2_star'])
    rows = []
    for th in [0, 15, 30, 45, 90, 137, 210, 300, 315, 359]:
        r = p2.solve_robust_polar((0.0, 0.0), float(th), CFG)
        c, s = math.cos(math.radians(th)), math.sin(math.radians(th))
        rot = np.array([b[0] * c - b[1] * s, b[0] * s + b[1] * c])
        mir = np.array([b[0] * c + b[1] * s, b[0] * s - b[1] * c])
        d_rot = float(np.linalg.norm(rot - np.array(r['S2_star'])))
        d_mir = float(np.linalg.norm(mir - np.array(r['S2_star'])))
        rows.append({'theta1_hat': th, 'S2_star': list(r['S2_star']),
                     'L_star': r['L_star'], 'alpha_star': r['alpha_star'],
                     'J_star': r['J_star'],
                     'dev_rotate': d_rot, 'dev_mirror': d_mir})
        log(f'  θ̂1={th:6.1f}°  S2*=({r["S2_star"][0]:8.2f},{r["S2_star"][1]:8.2f})  '
            f'L*={r["L_star"]:7.2f}  α*={r["alpha_star"]:+7.2f}°  J*={r["J_star"]:7.3f}  '
            f'min(rot/mir 偏差)={min(d_rot, d_mir):.2f}')
    Js = [r['J_star'] for r in rows]
    Ls = [r['L_star'] for r in rows]
    al = [abs(r['alpha_star']) for r in rows]
    mindev = [min(r['dev_rotate'], r['dev_mirror']) for r in rows]
    summ = {'J_star_min': min(Js), 'J_star_max': max(Js),
            'J_star_rel_spread': (max(Js) - min(Js)) / st.mean(Js),
            'L_star_min': min(Ls), 'L_star_max': max(Ls),
            'alpha_abs_min': min(al), 'alpha_abs_max': max(al),
            'max_dev_rot_or_mirror': max(mindev),
            'pass': bool((max(Js) - min(Js)) / st.mean(Js) < 0.01)}
    log(f'  J* 相对波动 {summ["J_star_rel_spread"]*100:.3f}%，'
        f'L*∈[{summ["L_star_min"]:.1f},{summ["L_star_max"]:.1f}]，'
        f'|α*|∈[{summ["alpha_abs_min"]:.2f},{summ["alpha_abs_max"]:.2f}]°，'
        f'与旋转/镜像解的最大偏差 {summ["max_dev_rot_or_mirror"]:.2f} m -> '
        f'{"PASS" if summ["pass"] else "FAIL"}')
    return {'base_S2_star': list(base['S2_star']), 'rows': rows, 'summary': summ}


# ================================================================ 实验 C：收敛性
def exp_convergence():
    log('=' * 74)
    log('[实验 C] 数值超参收敛性（固定 (S1,θ̂1)=(0,0)）')
    rows = []
    # C1: 候选网格间距
    for gs in [200.0, 120.0, 80.0, 40.0, 20.0]:
        cfg = p2.Cfg(grid_step=gs, refine_step=5.0, refine_span=30.0)
        r = p2.optimize_S2((0.0, 0.0), 0.0, cfg)
        rows.append({'kind': 'grid_step', 'value': gs, 'J_star': r['J_star'],
                     'S2_star': list(r['S2_star']), 'L_star': r['L_star']})
        log(f'  grid_step={gs:6.1f} m -> J*={r["J_star"]:8.3f}  S2*=({r["S2_star"][0]:8.2f},{r["S2_star"][1]:8.2f})')
    # C2: 第二次示向度扫描点数
    for kd in [5, 9, 13, 17, 25, 33, 49]:
        cfg = p2.Cfg(grid_step=20.0, k_dir=kd)
        r = p2.optimize_S2((0.0, 0.0), 0.0, cfg, fine=False)
        rows.append({'kind': 'k_dir', 'value': kd, 'J_star': r['J_star'],
                     'S2_star': list(r['S2_star']), 'L_star': r['L_star']})
        log(f'  k_dir={kd:3d} -> J*={r["J_star"]:8.3f}  S2*=({r["S2_star"][0]:8.2f},{r["S2_star"][1]:8.2f})')
    # C3: F1 采样密度
    for nd, nph in [(5, 3), (13, 3), (25, 5), (41, 9), (61, 13)]:
        cfg = p2.Cfg(grid_step=20.0, n_d=nd, n_phi=nph)
        r = p2.optimize_S2((0.0, 0.0), 0.0, cfg, fine=False)
        rows.append({'kind': 'F1_samples', 'value': nd * nph, 'n_d': nd, 'n_phi': nph,
                     'J_star': r['J_star'], 'S2_star': list(r['S2_star']),
                     'L_star': r['L_star']})
        log(f'  F1 采样 {nd}x{nph}={nd*nph:4d} -> J*={r["J_star"]:8.3f}  '
            f'S2*=({r["S2_star"][0]:8.2f},{r["S2_star"][1]:8.2f})')
    # C4: 一维极坐标求解器 vs 二维网格求解器
    a = p2.solve_robust_polar((0.0, 0.0), 0.0, p2.Cfg())
    b = p2.optimize_S2((0.0, 0.0), 0.0, p2.Cfg(grid_step=20.0))
    rows.append({'kind': 'solver', 'value': 'polar1d', 'J_star': a['J_star'],
                 'S2_star': list(a['S2_star']), 'L_star': a['L_star']})
    rows.append({'kind': 'solver', 'value': 'grid2d', 'J_star': b['J_star'],
                 'S2_star': list(b['S2_star']), 'L_star': b['L_star']})
    log(f'  一维极坐标解 J*={a["J_star"]:.4f} S2*=({a["S2_star"][0]:.2f},{a["S2_star"][1]:.2f})')
    log(f'  二维网格解   J*={b["J_star"]:.4f} S2*=({b["S2_star"][0]:.2f},{b["S2_star"][1]:.2f})')
    # C5: 圆盘逼近边数
    for ndk in [32, 64, 128, 256]:
        cfg = p2.Cfg(grid_step=20.0, n_disk=ndk)
        r = p2.optimize_S2((0.0, 0.0), 0.0, cfg, fine=False)
        rows.append({'kind': 'n_disk', 'value': ndk, 'J_star': r['J_star'],
                     'S2_star': list(r['S2_star']), 'L_star': r['L_star']})
        log(f'  N_disk={ndk:4d} -> J*={r["J_star"]:8.3f}  S2*=({r["S2_star"][0]:8.2f},{r["S2_star"][1]:8.2f})')
    return {'rows': rows, 'cfg_default': vars(CFG)}


# ================================================================ 实验 D：策略对比
def exp_strategies(scen, lam_by_th=None):
    log('=' * 74)
    log(f'[实验 D] 同一批 {len(scen)} 个场景下的策略对比（禁止删样本）')

    # 主策略的闭式形式：S2 = S1 + L*·u(θ̂1 + α*)，(L*,α*) 由优化器一次性求出。
    # 这完全可执行：只依赖 S1 与 θ̂1（实验 B 已数值验证旋转等变性）。
    base = p2.solve_robust_polar((0.0, 0.0), 0.0, CFG)
    L_R, A_R = base['L_star'], base['alpha_star']
    base_rn = p2.optimize_S2((0.0, 0.0), 0.0, CFG)
    L_RN = math.hypot(*base_rn['S2_rn'])
    A_RN = math.degrees(math.atan2(base_rn['S2_rn'][1], base_rn['S2_rn'][0]))
    log(f'  主策略闭式解：L*={L_R:.3f} m，α*={A_R:+.3f}°（偏离 θ̂1 的方向）')
    log(f'  风险中性对照：L={L_RN:.1f} m，α={A_RN:+.2f}°')

    def robust_S2(S1, th):
        A = math.radians(th + A_R)
        return (S1[0] + L_R * math.cos(A), S1[1] + L_R * math.sin(A))

    def rn_S2(S1, th):
        A = math.radians(th + A_RN)
        return (S1[0] + L_RN * math.cos(A), S1[1] + L_RN * math.sin(A))

    lam = p2.f1_diameter((0.0, 0.0), 0.0)
    log(f'  失败惩罚 λ = diam(F1) = {lam:.2f} m（与 theta1_hat 无关：Ω 为圆域，问题旋转等变）')

    strat_names = ['鲁棒最优S2*（本文主策略）', '风险中性最优（对照）', '随机可行点',
                   '沿测向方向750m', '测向垂线方向1000m', 'oracle-Thales（不可实现，参考）']
    recs = {n: [] for n in strat_names}

    for sc in scen:
        S1 = sc['S1']
        th_hat = sc['theta1_hat']
        G = sc['G']
        r_eff = sc['R_eff_true']
        e2 = sc['e2']
        rng = random.Random(SEED + 7919 * sc['k'])
        S2s = {
            strat_names[0]: robust_S2(S1, th_hat),
            strat_names[1]: rn_S2(S1, th_hat),
            strat_names[2]: p2.strat_random_omega(S1, th_hat, rng),
            strat_names[3]: p2.strat_along_bearing(S1, th_hat, 750.0),
            strat_names[4]: p2.strat_perp(S1, th_hat, 1000.0),
            strat_names[5]: p2.strat_oracle_thales(S1, th_hat, G, sc['d']),
        }
        for name, S2 in S2s.items():
            ev = p2.evaluate_one(S1, th_hat, S2, G, r_eff, e2, lam)
            recs[name].append({
                'k': sc['k'], 'status': ev['status'], 'cost': ev['cost'],
                'D': ev['D'] if ev['D'] is not None else '',
                'd2': ev['d2'], 'move': math.hypot(S2[0] - S1[0], S2[1] - S1[1]),
                'S2x': S2[0], 'S2y': S2[1],
                'theta1_err': sc['e1'], 'theta2_err': e2 if ev['status'] == 'localized' else '',
                'theta_true': sc['theta_true'], 'd_true': sc['d'],
                'R_eff_true': r_eff, 'Gx': G[0], 'Gy': G[1],
            })

    def pct(a, p):
        a = sorted(a)
        i = min(int(p * len(a)), len(a) - 1)
        return a[i]

    summary = {'key': {'N_scen': len(scen), 'SEED': SEED, 'lambda': lam,
                       'cfg': vars(CFG)}}
    rows_csv = []
    log('')
    log(f'  {"策略":<26}{"N":>5}{"直清":>6}{"定位":>6}{"空域":>6}{"无信号":>7}'
        f'{"成功率":>8}{"代价均值":>10}{"代价中位":>10}{"代价P95":>10}{"代价最大":>10}'
        f'{"D均值(成功)":>12}{"D中位":>9}{"D_P95":>9}{"移动均值":>10}')
    for name in strat_names:
        rs = recs[name]
        N = len(rs)
        n_direct = sum(1 for r in rs if r['status'] == 'direct')
        n_loc = sum(1 for r in rs if r['status'] == 'localized')
        n_empty = sum(1 for r in rs if r['status'] == 'empty_region')
        n_nosig = sum(1 for r in rs if r['status'] == 'no_signal')
        costs = [r['cost'] for r in rs]
        Ds = [r['D'] for r in rs if r['status'] == 'localized']
        moves = [r['move'] for r in rs]
        success = (n_direct + n_loc) / N
        s = {
            'N_total': N, 'n_direct': n_direct, 'n_localized': n_loc,
            'n_empty_region': n_empty, 'n_no_signal': n_nosig,
            'n_failure': n_empty + n_nosig,
            'success_rate': success,
            'cost_mean': st.mean(costs), 'cost_median': st.median(costs),
            'cost_p90': pct(costs, .90), 'cost_p95': pct(costs, .95),
            'cost_max': max(costs),
            'D_mean_among_localized': (st.mean(Ds) if Ds else None),
            'D_median_among_localized': (st.median(Ds) if Ds else None),
            'D_p90_among_localized': (pct(Ds, .90) if Ds else None),
            'D_p95_among_localized': (pct(Ds, .95) if Ds else None),
            'D_max_among_localized': (max(Ds) if Ds else None),
            'n_used_for_D': len(Ds),
            'move_mean': st.mean(moves),
        }
        summary[name] = s
        log(f'  {name:<26}{N:>5}{n_direct:>6}{n_loc:>6}{n_empty:>6}{n_nosig:>7}'
            f'{success*100:>7.1f}%{s["cost_mean"]:>10.2f}{s["cost_median"]:>10.2f}'
            f'{s["cost_p95"]:>10.2f}{s["cost_max"]:>10.2f}'
            f'{(s["D_mean_among_localized"] or 0):>12.2f}'
            f'{(s["D_median_among_localized"] or 0):>9.2f}'
            f'{(s["D_p95_among_localized"] or 0):>9.2f}{s["move_mean"]:>10.1f}')
        for r in rs:
            rows_csv.append([name, r['k'], r['status'], f"{r['cost']:.4f}",
                             (f"{r['D']:.4f}" if r['D'] != '' else ''),
                             f"{r['d2']:.4f}", f"{r['move']:.4f}",
                             f"{r['S2x']:.4f}", f"{r['S2y']:.4f}",
                             f"{r['theta1_err']:.6f}",
                             (f"{r['theta2_err']:.6f}" if r['theta2_err'] != '' else ''),
                             f"{r['theta_true']:.4f}", f"{r['d_true']:.4f}",
                             f"{r['R_eff_true']:.4f}", f"{r['move']/5.0:.4f}"])
    write_csv(rows_csv,
              ['strategy', 'scenario', 'status', 'cost_m', 'D_m', 'd2_m', 'move_m',
               'S2x', 'S2y', 'theta1_err_deg', 'theta2_err_deg', 'theta_true_deg',
               'd_true_m', 'R_eff_true_m', 'move_time_s'], 'strategy_scenarios.csv')
    dump(summary, 'strategy_summary.json')
    return summary


# ================================================================ 实验 E：代表性算例
def exp_representative():
    log('=' * 74)
    th = 45.0
    log(f'[实验 E] 代表性算例 θ̂1={th}°，生成 J 场与候选区域（供绘图）')
    r = p2.optimize_S2((0.0, 0.0), th, CFG)
    log(f'  S2*=({r["S2_star"][0]:.2f},{r["S2_star"][1]:.2f})  L*={r["L_star"]:.2f}  '
        f'α*={r["alpha_star"]:+.2f}°  J*={r["J_star"]:.3f} m')
    for e in r['etas']:
        log(f'  η={e:.2f}: |C_η|={int(r["regions"][e].sum())} 个网格点')
    np.savez_compressed(
        os.path.join(RES, 'representative_case.npz'),
        J_map=r['J_map'], grid_X=r['grid_X'], grid_Y=r['grid_Y'],
        ok_mask=r['ok_mask'], dmax_map=r['dmax_map'],
        S2_star=np.array(r['S2_star']), J_star=r['J_star'], lam=r['lambda'],
        theta1_hat=th,
        F1_poly=np.array(r['F1_poly']) if r['F1_poly'] else np.zeros((0, 2)),
        G_pts=r['G_pts'],
        region_0=r['regions'][0.0], region_005=r['regions'][0.05],
        region_02=r['regions'][0.2], region_05=r['regions'][0.5],
        S2_rn=np.array(r['S2_rn']), J_rn_map=r['J_rn_map'],
        rn_grid_X=r['rn_grid_X'], rn_grid_Y=r['rn_grid_Y'],
    )
    log('  -> 写出 results/representative_case.npz')
    return {'theta1_hat': th, 'S2_star': list(r['S2_star']), 'L_star': r['L_star'],
            'alpha_star': r['alpha_star'], 'J_star': r['J_star'],
            'lambda': r['lambda'],
            'n_region': {str(e): int(r['regions'][e].sum()) for e in r['etas']},
            'S2_rn': list(r['S2_rn']), 'J_rn_star': r['J_rn_star']}


# ================================================================ 实验 F：S1≠原点
def exp_general_S1(n: int = 40):
    log('=' * 74)
    log(f'[实验 F] 一般性检验：S1 不在原点时算法仍然可执行（{n} 个随机 S1）')
    rng = random.Random(SEED + 999)
    rows = []
    for k in range(n):
        S1 = p1_uniform(rng, 1500.0)
        th = rng.uniform(0, 360)
        try:
            r = p2.solve_robust_polar(S1, th, CFG)
        except Exception as e:                       # noqa: BLE001
            rows.append({'k': k, 'S1': list(S1), 'error': str(e)})
            continue
        rows.append({'k': k, 'S1': list(S1), 'theta1_hat': th,
                     'S2_star': list(r['S2_star']), 'J_star': r['J_star'],
                     'L_star': r['L_star'], 'alpha_star': r['alpha_star'],
                     'feasible': bool(r.get('feasible', True)),
                     'S2_in_omega': math.hypot(*r['S2_star']) <= p2.R_TARGET})
    ok = [r for r in rows if 'error' not in r]
    feas = [r for r in ok if r.get('feasible', True)]
    n_fb = len(ok) - len(feas)
    if not feas:
        feas = ok
    Ls = [r['L_star'] for r in feas]
    Js = [r['J_star'] for r in feas]
    log(f'  成功求解 {len(ok)}/{n}；其中"存在保证接收的 S2"的场景 {len(feas)} 个，'
        f'退化为最小最坏距离兜底的场景 {n_fb} 个')
    log(f'  可行场景的 L* ∈ [{min(Ls):.1f}, {max(Ls):.1f}]，J* ∈ [{min(Js):.1f}, {max(Js):.1f}]，'
        f'全部 S2*∈Ω = {all(r["S2_in_omega"] for r in ok)}')
    return {'rows': rows, 'n_ok': len(ok), 'n_feasible': len(feas), 'n_fallback': n_fb,
            'L_min': min(Ls), 'L_max': max(Ls),
            'J_min': min(Js), 'J_max': max(Js),
            'all_in_omega': bool(all(r['S2_in_omega'] for r in ok))}


def p1_uniform(rng: random.Random, R: float):
    while True:
        x = rng.uniform(-R, R)
        y = rng.uniform(-R, R)
        if x * x + y * y <= R * R:
            return (x, y)


# ================================================================ main
if __name__ == '__main__':
    t0 = time.time()
    info = exp_info_set()
    eq = exp_equivariance()
    conv = exp_convergence()
    scen = make_scenarios(N_SCEN, SEED)
    strat = exp_strategies(scen)
    rep = exp_representative()
    gen = exp_general_S1()

    key = {
        'version': 'v5', 'seed': SEED, 'N_scen': N_SCEN, 'cfg': vars(CFG),
        'info_set_pass': info['pass'],
        'info_set_spread': info['spread'],
        'equivariance_summary': eq['summary'],
        'convergence': conv['rows'],
        'strategy_summary': strat,
        'representative': rep,
        'general_S1': {k: v for k, v in gen.items() if k != 'rows'},
        'lambda': strat['key']['lambda'],
    }
    dump(key, 'key_numbers.json')
    log('=' * 74)
    log(f'全部实验完成，用时 {time.time() - t0:.1f} s')
    with open(os.path.join(LOG, 'run_experiments.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(_log))
