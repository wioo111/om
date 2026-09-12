# -*- coding: utf-8 -*-
r"""问题一 v5 —— 全部数值实验（自检 + 圆盘逼近收敛 + Monte Carlo + 敏感度）。

产出（全部落到 results/ 与 logs/）：
    results/selftest.json            自检 T1–T8 结果
    results/disk_convergence.csv     N_disk 对 D / R* / q 的收敛
    results/disk_convergence.json
    results/mc_samples.csv           Monte Carlo 全部样本（每 n 一行 a 组）
    results/mc_summary.json          Monte Carlo 汇总统计量
    results/eps_sensitivity.csv      D 对 epsilon 的敏感度
    results/eps_sensitivity.json
    results/key_numbers.json         报告中引用的全部关键数字（唯一真源）
    logs/run_experiments.log

运行： python -X utf8 run_experiments.py
"""
from __future__ import annotations

# Historical implementation below is retained for import compatibility only.
# Direct execution delegates to the single formal Q1/Q2 implementation.
if __name__ == '__main__':
    from pathlib import Path as _Path
    import subprocess as _subprocess
    import sys as _sys
    raise SystemExit(_subprocess.call([_sys.executable, str(_Path(__file__).resolve().parents[2] / '第一二问' / 'run.py'), 'experiments', *_sys.argv[1:]]))

import csv
import json
import math
import os
import random
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
LOG = os.path.join(HERE, 'logs')
os.makedirs(RES, exist_ok=True)
os.makedirs(LOG, exist_ok=True)

import problem1_core as p1  # noqa: E402

SEED = 20260912
N_DISK = p1.N_DISK           # 256
NS_GRID = [2, 3, 4, 5, 6, 8, 10, 15]
N_PER = 500
EPS_GRID = [0.1, 0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]
N_EPS_PER = 300
N_DET_EPS = 4

_log_lines: list = []


def log(msg: str) -> None:
    print(msg)
    _log_lines.append(msg)


def dump(obj, name: str) -> None:
    path = os.path.join(RES, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=float)
    log(f'  -> 写出 {path}')


def write_csv(rows: list, header: list, name: str) -> None:
    path = os.path.join(RES, name)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    log(f'  -> 写出 {path}')


# ================================================================ T1–T8 自检
def run_selftest() -> dict:
    log('=' * 72)
    log('[自检] T1–T8')
    out: dict = {}

    # T1 扇形方向：8 个角度，射线上的内点在内部、反向外点不在内部
    t1 = []
    for th in [0, 45, 90, 135, 180, 225, 270, 315]:
        S = (0.0, 0.0)
        r = 800.0
        Pin = (r * math.cos(math.radians(th)), r * math.sin(math.radians(th)))
        Pout = (r * math.cos(math.radians(th + 180)), r * math.sin(math.radians(th + 180)))
        ok = p1.point_in_sector(Pin, S, th, p1.EPS_DEG) and not p1.point_in_sector(Pout, S, th, p1.EPS_DEG)
        # 侧向 90 度必不在扇形内
        Pl = (r * math.cos(math.radians(th + 90)), r * math.sin(math.radians(th + 90)))
        ok = ok and not p1.point_in_sector(Pl, S, th, p1.EPS_DEG)
        t1.append({'theta_deg': th, 'pass': bool(ok)})
    out['T1_sector_direction'] = {'detail': t1, 'pass': all(x['pass'] for x in t1)}
    log(f"  T1 扇形方向（8 方向 x 3 判据）: {'PASS' if out['T1_sector_direction']['pass'] else 'FAIL'}")

    # T2 协调算例：3 个检测点共源，源必须落在定位区域内
    src = (50.0, 30.0)
    dets = [(0.0, 0.0), (100.0, 0.0), (50.0, 100.0)]
    ths = [math.degrees(math.atan2(src[1] - d[1], src[0] - d[0])) % 360 for d in dets]
    r2 = p1.solve(dets, ths, N_disk=N_DISK)
    out['T2_consistent'] = {
        'D': r2['D'], 'R_star': r2['R_star'], 'q': r2['q'], 'off': r2['off'],
        'covered': r2['covered'], 'source_inside': bool(p1.point_in_convex_poly(src, r2['poly'])),
        'pass': bool((not r2['is_empty']) and p1.point_in_convex_poly(src, r2['poly'])),
    }
    log(f"  T2 协调算例: D={r2['D']:.4f} m, R*={r2['R_star']:.4f} m, q={r2['q']:.6f}, "
        f"covered={r2['covered']}, off={r2['off']:.6f}  -> {'PASS' if out['T2_consistent']['pass'] else 'FAIL'}")

    # T3 反向扇形必为空
    r3 = p1.solve([(0.0, 0.0), (500.0, 0.0)], [90.0, 270.0], N_disk=N_DISK)
    out['T3_opposite_empty'] = {'is_empty': r3['is_empty'], 'pass': bool(r3['is_empty'])}
    log(f"  T3 反向扇形: empty={r3['is_empty']} -> {'PASS' if r3['is_empty'] else 'FAIL'}")

    # T4 Jung 上界取等：正三角形 D=100 -> R* = D/sqrt3, q = 2/sqrt3（严格 Jung 紧）
    D_eq = 100.0
    tri = [(0.0, 0.0), (D_eq, 0.0), (D_eq / 2, D_eq * math.sqrt(3) / 2)]
    r4 = p1.analyze_region(tri)
    err = abs(r4['q'] - p1.JUNG_Q)
    out['T4_jung_tight_triangle'] = {
        'D': r4['D'], 'R_star': r4['R_star'], 'q': r4['q'], 'off': r4['off'],
        'covered': r4['covered'], 'abs_err_vs_2_over_sqrt3': err,
        'pass': bool((not r4['covered']) and err < 1e-9),
    }
    log(f"  T4  Jung 紧正三角: D={r4['D']:.4f}, R*={r4['R_star']:.4f}, q={r4['q']:.6f} "
        f"(理论 {p1.JUNG_Q:.6f}, 误差 {err:.2e}), covered={r4['covered']} -> "
        f"{'PASS' if out['T4_jung_tight_triangle']['pass'] else 'FAIL'}")

    # T5 Jung 界与覆盖判据的等价性：covered <=> q == 1
    rng = random.Random(SEED)
    n_cov = n_unc = 0
    max_dev_cov = 0.0     # covered 样本 |q-1| 的最大值（应 ~1e-12）
    min_dev_unc = 1e9     # 不覆盖样本 (q-1) 的最小值（应明显 > 0）
    q_min, q_max = 1e9, -1e9
    for _ in range(600):
        nn = rng.choice([2, 3, 4])
        sc = p1.random_scene(nn, rng)
        if not sc['ok']:
            continue
        rr = p1.solve(sc['dets'], sc['thetas'], N_disk=N_DISK)
        if rr['is_empty'] or rr['D'] <= 0:
            continue
        q = rr['q']
        q_min = min(q_min, q)
        q_max = max(q_max, q)
        if rr['covered']:
            n_cov += 1
            max_dev_cov = max(max_dev_cov, abs(q - 1.0))
        else:
            n_unc += 1
            min_dev_unc = min(min_dev_unc, q - 1.0)
    ok = (max_dev_cov < 1e-6) and (min_dev_unc > 0) and (q_min >= 1.0 - 1e-9) and (q_max <= p1.JUNG_Q + 1e-9)
    out['T5_jung_bounds'] = {
        'n_covered': n_cov, 'n_uncovered': n_unc,
        'max_abs_q_minus_1_when_covered': max_dev_cov,
        'min_q_minus_1_when_uncovered': min_dev_unc,
        'q_min': q_min, 'q_max': q_max, 'jung_upper': p1.JUNG_Q,
        'pass': bool(ok),
    }
    log(f"  T5  Jung 界 1<=q<=2/sqrt3 且 covered<=>q=1: 覆盖 {n_cov} / 不覆盖 {n_unc}, "
        f"q 范围 [{q_min:.6f}, {q_max:.6f}], covered 时 max|q-1|={max_dev_cov:.2e}, "
        f"不覆盖时 min(q-1)={min_dev_unc:.4f} -> {'PASS' if ok else 'FAIL'}")

    # T6 单扇形退化：D 应接近 R_eff
    r6 = p1.solve([(0.0, 0.0)], [45.0], N_disk=N_DISK)
    out['T6_single_sector'] = {'D': r6['D'], 'R_eff': p1.R_EFF,
                               'rel_err': abs(r6['D'] - p1.R_EFF) / p1.R_EFF,
                               'pass': bool(abs(r6['D'] - p1.R_EFF) / p1.R_EFF < 0.02)}
    log(f"  T6  单扇形退化: D={r6['D']:.3f} m (R_eff=1500), 相对误差 "
        f"{out['T6_single_sector']['rel_err']*100:.2f}% -> {'PASS' if out['T6_single_sector']['pass'] else 'FAIL'}")

    # T7 圆盘外逼近误差的理论值校验：一次直线极易酥
    #     用外切正 N 边形的顶点半径直接核对 r*sec(pi/N)
    rows = []
    ok7 = True
    for N in [16, 32, 64, 128, 256, 512, 1024]:
        theo = p1.disk_outer_error(p1.R_EFF, N)
        # 数值核对：N 边形顶点到圆心距离 - r
        vert = p1.R_EFF / math.cos(math.pi / N)
        num = vert - p1.R_EFF
        rows.append({'N': N, 'theory_delta_r_m': theo, 'numeric_delta_r_m': num,
                     'abs_diff': abs(theo - num)})
        ok7 = ok7 and abs(theo - num) < 1e-9
    out['T7_disk_error_formula'] = {'rows': rows, 'pass': bool(ok7)}
    log(f"  T7  外逼近误差公式 r(sec(pi/N)-1): N=64 -> {p1.disk_outer_error(1500.,64):.4f} m, "
        f"N=256 -> {p1.disk_outer_error(1500.,256):.4f} m -> {'PASS' if ok7 else 'FAIL'}")

    # T8 全部随机检测点必须在 Omega 内
    rng = random.Random(SEED + 1)
    bad = 0
    for _ in range(400):
        sc = p1.random_scene(4, rng)
        if not sc['ok']:
            bad += 1
            continue
        for S in sc['dets']:
            if math.hypot(*S) > p1.R_TARGET + 1e-9:
                bad += 1
    out['T8_detectors_in_omega'] = {'n_violation': bad, 'pass': bool(bad == 0)}
    log(f"  T8  检测点位于 Omega 内: 违规 {bad} 次 -> {'PASS' if bad == 0 else 'FAIL'}")

    out['ALL_PASS'] = all(v.get('pass', False) for k, v in out.items() if isinstance(v, dict) and 'pass' in v)
    log(f"自检总判定: {'ALL PASS' if out['ALL_PASS'] else 'HAS FAILURE'}")
    return out


# ================================================================ 圆盘逼近收敛
def run_disk_convergence(n_scene: int = 250, N_ref: int = 2048) -> dict:
    log('=' * 72)
    log(f'[实验 A] 圆盘外逼近边数 N 的收敛性（{n_scene} 个固定场景，真值参考 N={N_ref}）')
    rng = random.Random(SEED)
    scenes = []
    while len(scenes) < n_scene:
        sc = p1.random_scene(rng.choice([2, 3, 4, 6]), rng)
        if sc['ok']:
            scenes.append(sc)
    Ns = [16, 32, 64, 128, 256, 512, 1024]
    rows = []
    summary = []
    for N in Ns:
        dD_rel, dR_rel, dq_abs = [], [], []
        for sc in scenes:
            ref = p1.solve(sc['dets'], sc['thetas'], N_disk=N_ref)
            cur = p1.solve(sc['dets'], sc['thetas'], N_disk=N)
            if ref['is_empty'] or cur['is_empty'] or ref['D'] <= 0:
                continue
            dD_rel.append(abs(cur['D'] - ref['D']) / ref['D'])
            dR_rel.append(abs(cur['R_star'] - ref['R_star']) / ref['R_star'])
            dq_abs.append(abs(cur['q'] - ref['q']))
            rows.append({
                'N': N, 'scene': len(rows) % n_scene,
                'D': cur['D'], 'D_ref': ref['D'],
                'R_star': cur['R_star'], 'R_star_ref': ref['R_star'],
                'q': cur['q'], 'q_ref': ref['q'],
            })
        s = {
            'N': N,
            'theoretical_delta_r_m': p1.disk_outer_error(p1.R_EFF, N),
            'mean_rel_err_D': st.mean(dD_rel), 'max_rel_err_D': max(dD_rel),
            'mean_rel_err_R': st.mean(dR_rel), 'max_rel_err_R': max(dR_rel),
            'mean_abs_err_q': st.mean(dq_abs), 'max_abs_err_q': max(dq_abs),
        }
        summary.append(s)
        log(f"  N={N:5d}: D 平均相对误差 {s['mean_rel_err_D']*100:7.4f}% (最大 {s['max_rel_err_D']*100:7.4f}%), "
            f"R* 平均相对误差 {s['mean_rel_err_R']*100:7.4f}%, |Δq| 平均 {s['mean_abs_err_q']:.3e} "
            f"(理论径向外扩 {s['theoretical_delta_r_m']:.4f} m)")
    write_csv([[r['N'], r['scene'], f"{r['D']:.6f}", f"{r['D_ref']:.6f}",
                f"{r['R_star']:.6f}", f"{r['R_star_ref']:.6f}",
                f"{r['q']:.6f}", f"{r['q_ref']:.6f}"] for r in rows],
              ['N', 'scene_idx', 'D_m', 'D_ref_m', 'R_star_m', 'R_star_ref_m', 'q', 'q_ref'],
              'disk_convergence.csv')
    dump({'n_scene': n_scene, 'N_reference': N_ref, 'summary': summary},
         'disk_convergence.json')
    return {'summary': summary, 'n_scene': n_scene, 'N_reference': N_ref}


# ================================================================ Monte Carlo
def run_montecarlo(n_per: int = N_PER) -> dict:
    log('=' * 72)
    log(f'[实验 B] Monte Carlo：每个 n 取 {n_per} 例（N_disk={N_DISK}，检测点强制在 Ω 内）')
    rows = []
    summary = {}
    key = {
        'SEED': SEED, 'N_disk': N_DISK, 'N_per': n_per,
        'R_target': p1.R_TARGET, 'R_eff': p1.R_EFF, 'eps_deg': p1.EPS_DEG,
        'detector_constraint': 'S_i in Omega and 5<|S_i-G|<=R_eff',
    }
    for n in NS_GRID:
        Ds, Rs, qs, offs = [], [], [], []
        verts, cov_n, empty_n = [], 0, 0
        for k in range(n_per):
            rng = random.Random(SEED + 1000 * n + k)
            sc = p1.random_scene(n, rng)
            if not sc['ok']:
                empty_n += 1
                rows.append([n, k, '', '', '', '', '', '', 'generator_failed'])
                continue
            rr = p1.solve(sc['dets'], sc['thetas'], N_disk=N_DISK)
            if rr['is_empty'] or rr['D'] <= 0:
                empty_n += 1
                rows.append([n, k, '', '', '', '', '', '', 'empty_polygon'])
                continue
            Ds.append(rr['D']); Rs.append(rr['R_star']); qs.append(rr['q'])
            offs.append(rr['off']); verts.append(rr['n_vertices'])
            cov_n += int(rr['covered'])
            rows.append([n, k, f"{rr['D']:.6f}", f"{rr['R_star']:.6f}", f"{rr['q']:.6f}",
                         f"{rr['off']:.6f}", int(rr['covered']), rr['n_vertices'], 'ok'])
        if not Ds:
            continue
        qq = sorted(qs)
        DD = sorted(Ds)

        def pct(a, p):
            if not a:
                return 0.0
            i = min(int(p * len(a)), len(a) - 1)
            return a[i]

        s = {
            'n': n, 'N_valid': len(Ds), 'N_invalid': empty_n,
            'D_mean': st.mean(Ds), 'D_median': st.median(Ds),
            'D_p25': pct(DD, .25), 'D_p75': pct(DD, .75),
            'D_p95': pct(DD, .95), 'D_max': max(Ds),
            'R_star_mean': st.mean(Rs), 'R_star_median': st.median(Rs),
            'q_mean': st.mean(qs), 'q_median': st.median(qs),
            'q_p95': pct(qq, .95), 'q_max': max(qs), 'q_min': min(qs),
            'off_mean': st.mean(offs), 'off_median': st.median(offs),
            'cover_rate': cov_n / len(Ds),
            'vertices_mean': st.mean(verts), 'vertices_max': max(verts),
        }
        summary[str(n)] = s
        log(f"  n={n:2d}: N有效={s['N_valid']:3d}, D均值={s['D_mean']:8.2f} m, D中位={s['D_median']:8.2f} m, "
            f"R*均值={s['R_star_mean']:7.2f} m, q中位={s['q_median']:.4f}, q最大={s['q_max']:.4f}, "
            f"覆盖率={s['cover_rate']*100:5.1f}%, 顶点均值={s['vertices_mean']:.2f}")
    write_csv(rows, ['n', 'sample_idx', 'D_m', 'R_star_m', 'q', 'off_m', 'covered',
                     'n_vertices', 'status'], 'mc_samples.csv')

    # 全局一致性检查
    allq = [r[4] for r in rows if r[8] == 'ok']
    allq = [float(x) for x in allq]
    consistency = {
        'n_total_valid': len(allq),
        'q_min': min(allq), 'q_max': max(allq),
        'jung_upper': p1.JUNG_Q,
        'violate_lower': int(sum(1 for x in allq if x < 1.0 - 1e-9)),
        'violate_upper': int(sum(1 for x in allq if x > p1.JUNG_Q + 1e-9)),
    }
    dump({'key': key, 'summary': summary, 'consistency': consistency}, 'mc_summary.json')
    log(f"  Jung 界一致性: q ∈ [{consistency['q_min']:.6f}, {consistency['q_max']:.6f}], "
        f"越下界 {consistency['violate_lower']} 例, 越上界 {consistency['violate_upper']} 例")
    return {'key': key, 'summary': summary, 'consistency': consistency}


# ================================================================ epsilon 敏感度
def run_eps_sensitivity() -> dict:
    log('=' * 72)
    log(f'[实验 C] D 对 ε 的敏感度（每个 ε 取 {N_EPS_PER} 例，n={N_DET_EPS}，N_disk={N_DISK}）')
    rows = []
    summary = []
    for eps in EPS_GRID:
        Ds = []
        dep = 0
        for k in range(N_EPS_PER):
            rng = random.Random(SEED + 50000 + int(eps * 100) * 1000 + k)
            sc = p1.random_scene(N_DET_EPS, rng, eps_deg=eps)
            if not sc['ok']:
                dep += 1
                continue
            rr = p1.solve(sc['dets'], sc['thetas'], eps_deg=eps, N_disk=N_DISK)
            if rr['is_empty'] or rr['D'] <= 0:
                dep += 1
                continue
            Ds.append(rr['D'])
            rows.append([eps, k, f"{rr['D']:.6f}", f"{rr['R_star']:.6f}", f"{rr['q']:.6f}"])
        Ds_sorted = sorted(Ds)

        def pct(a, p):
            i = min(int(p * len(a)), len(a) - 1)
            return a[i]

        s = {'eps_deg': eps, 'n_valid': len(Ds), 'n_invalid': dep,
             'D_mean': st.mean(Ds), 'D_median': st.median(Ds),
             'D_p05': pct(Ds_sorted, .05), 'D_p25': pct(Ds_sorted, .25),
             'D_p75': pct(Ds_sorted, .75), 'D_p95': pct(Ds_sorted, .95),
             'D_max': max(Ds)}
        summary.append(s)
        log(f"  ε={eps:4.1f}°: N有效={s['n_valid']:3d}, D中位={s['D_median']:8.2f} m, "
            f"D均值={s['D_mean']:8.2f} m, P25–P75=[{s['D_p25']:.2f}, {s['D_p75']:.2f}], P95={s['D_p95']:.2f}")
    write_csv(rows, ['eps_deg', 'sample_idx', 'D_m', 'R_star_m', 'q'], 'eps_sensitivity.csv')
    dump({'SEED': SEED, 'N_disk': N_DISK, 'n_detectors': N_DET_EPS,
          'N_per_eps': N_EPS_PER, 'summary': summary}, 'eps_sensitivity.json')
    return {'summary': summary}


# ================================================================ Jung 紧构造
def jung_tight_case() -> dict:
    r""""Jung 紧"标准算例：3 个检测点位于半径 rho 的圆周上互成 120°，源在圆心。

    此时定位区域近似是"三个半径 1500 m 圆盘之交"，具有三次对称，
    于是 q = 2R*/D 逼近 Jung 上界 2/sqrt(3)。
    """
    lo, hi = 1480.0, 1499.0
    best = None
    rho = lo
    while rho <= hi:
        dets = [(rho * math.cos(math.radians(a)), rho * math.sin(math.radians(a)))
                for a in (0.0, 120.0, 240.0)]
        ths = [math.degrees(math.atan2(0.0 - S[1], 0.0 - S[0])) % 360 for S in dets]
        rr = p1.solve(dets, ths, N_disk=N_DISK)
        if not rr['is_empty'] and (best is None or rr['q'] > best[1]['q']):
            best = (rho, rr, dets, ths)
        rho += 0.5
    rho, rr, dets, ths = best
    log('=' * 72)
    log(f'[构造] Jung 紧算例 rho={rho:.1f} m: D={rr["D"]:.4f} m, R*={rr["R_star"]:.4f} m, '
        f'q={rr["q"]:.6f} (上限 {p1.JUNG_Q:.6f}), off={rr["off"]:.4f} m, covered={rr["covered"]}')
    return {'rho': rho, 'dets': dets, 'thetas': ths, 'D': rr['D'], 'R_star': rr['R_star'],
            'q': rr['q'], 'off': rr['off'], 'covered': rr['covered'],
            'poly': rr['poly'], 'A': rr['A'], 'B': rr['B'], 'C': rr['C'],
            'mec_center': rr['mec_center'], 'n_vertices': rr['n_vertices'],
            'source': (0.0, 0.0)}


if __name__ == '__main__':
    t0 = time.time()
    selftest = run_selftest()
    conv = run_disk_convergence()
    mc = run_montecarlo()
    epss = run_eps_sensitivity()
    jt = jung_tight_case()

    key = {
        'version': 'v5',
        'seed': SEED,
        'N_disk': N_DISK,
        'jung_upper_2_over_sqrt3': p1.JUNG_Q,
        'disk_outer_error_m': {str(N): p1.disk_outer_error(p1.R_EFF, N) for N in [32, 64, 128, 256, 512, 1024]},
        'selftest_all_pass': selftest['ALL_PASS'],
        'selftest': selftest,
        'disk_convergence_summary': conv['summary'],
        'mc_key': mc['key'],
        'mc_summary': mc['summary'],
        'mc_consistency': mc['consistency'],
        'eps_summary': epss['summary'],
        'jung_tight': {k: v for k, v in jt.items() if k not in ('poly',)},
    }
    dump(key, 'key_numbers.json')
    log('=' * 72)
    log(f'全部实验完成，用时 {time.time() - t0:.1f} s')
    with open(os.path.join(LOG, 'run_experiments.log'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(_log_lines))
