# -*- coding: utf-8 -*-
r"""问题一 v5 —— 全部正式插图（一键重生成，禁止手工改图）。

产出 figures/：
    fig1_geometry_examples.png   典型几何：覆盖算例 / 不覆盖算例 / Jung 紧算例（含局部放大）
    fig2_D_vs_n.png              定位区域直径随检测点数量变化
    fig3_eps_sensitivity.png     D 对示向度误差 ε 的数值敏感度
    fig4_disk_approx_convergence.png  圆盘外切多边形边数 N 的误差收敛
    fig5_MEC_vs_D.png            全体 MC 样本的 (D, 2R*) 散点与 Jung 上下界
    fig6_cover_geometry.png      直径圆覆盖成功 vs 失败的几何机理

运行： python -X utf8 plot_figures.py   （需先运行 run_experiments.py）
"""
from __future__ import annotations

# Historical implementation below is retained for import compatibility only.
# Direct execution delegates to the single formal Q1/Q2 implementation.
if __name__ == '__main__':
    from pathlib import Path as _Path
    import subprocess as _subprocess
    import sys as _sys
    raise SystemExit(_subprocess.call([_sys.executable, str(_Path(__file__).resolve().parents[2] / '第一二问' / 'run.py'), 'figures', *_sys.argv[1:]]))

import csv
import json
import math
import os
import random

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Circle, Polygon as MplPolygon, Rectangle

import problem1_core as p1

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
FIG = os.path.join(HERE, 'figures')
os.makedirs(FIG, exist_ok=True)

# ---------------- 字体（中文优先） ----------------
_cands = ['Microsoft YaHei', 'SimHei', 'Source Han Sans CN', 'Noto Sans CJK SC',
          'WenQuanYi Zen Hei', 'PingFang SC', 'Hiragino Sans GB', 'DejaVu Sans']
_avail = {f.name for f in fm.fontManager.ttflist}
FONT = 'DejaVu Sans'
for _c in _cands:
    if _c in _avail:
        FONT = _c
        break
plt.rcParams['font.sans-serif'] = [FONT, 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['mathtext.fontset'] = 'dejavusans'

BG = 'white'
C_POLY_F = '#9ecae1'
C_POLY_E = '#084594'
C_DIAM = '#d62728'
C_MEC = '#2ca02c'
C_DET = '#1b1b1b'
C_OMEGA = '#8c8c8c'
C_SEC = '#fdae61'
C_SRC = '#d4a017'
C_GRID = '#d9d9d9'
JUNG_S = r'2/\sqrt{3}'

FIG_INPUTS: dict = {}


def _save(fig, name: str) -> None:
    out = os.path.join(FIG, name)
    fig.savefig(out, dpi=160, facecolor=BG, bbox_inches='tight')
    plt.close(fig)
    print(f'  写出 {out}')


# ================================================================ 绘图原语
def _draw_sector(ax, S, th, eps, r=1600.0, alpha=0.16):
    a0 = math.radians(th - eps)
    a1 = math.radians(th + eps)
    ang = [a0 + (a1 - a0) * i / 40.0 for i in range(41)]
    xs = [S[0]] + [S[0] + r * math.cos(a) for a in ang] + [S[0]]
    ys = [S[1]] + [S[1] + r * math.sin(a) for a in ang] + [S[1]]
    ax.fill(xs, ys, color=C_SEC, alpha=alpha, zorder=1, lw=0)
    for a in (a0, a1):
        ax.plot([S[0], S[0] + r * math.cos(a)], [S[1], S[1] + r * math.sin(a)],
                color=C_SEC, lw=0.8, alpha=0.75, zorder=2)


def _draw_result(ax, res, dets, thetas, eps, r_sec=1600.0, draw_sectors=True,
                 show_mec=True, annotate_far=True, far_rel=0.01):
    if draw_sectors:
        for S, th in zip(dets, thetas):
            _draw_sector(ax, S, th, eps, r=r_sec)
    poly = res['poly']
    if poly and len(poly) >= 3:
        ax.add_patch(MplPolygon(poly, closed=True, facecolor=C_POLY_F,
                                edgecolor=C_POLY_E, lw=1.8, alpha=0.85, zorder=4,
                                label='定位区域 $\\mathcal{L}$'))
    if res['D'] > 0:
        C = res['C']
        ax.add_patch(Circle(C, res['D'] / 2, fill=False, edgecolor=C_DIAM, lw=1.8,
                            ls='--', zorder=5, label=f'直径圆（半径 $D/2$={res["D"]/2:.2f} m）'))
        ax.plot([res['A'][0], res['B'][0]], [res['A'][1], res['B'][1]],
                color=C_DIAM, lw=1.3, ls='-', zorder=5, label='直径 $AB$')
        ax.plot([res['A'][0]], [res['A'][1]], 'X', color=C_DIAM, ms=9, mew=2, zorder=6)
        ax.plot([res['B'][0]], [res['B'][1]], 'X', color=C_DIAM, ms=9, mew=2, zorder=6)
        if show_mec:
            same = abs(2.0 * res['R_star'] - res['D']) <= max(1e-9, 1e-6 * res['D'])
            extra = '（与直径圆重合）' if same else ''
            ax.add_patch(Circle(res['mec_center'], res['R_star'], fill=False,
                                edgecolor=C_MEC, lw=1.6, ls=':', zorder=5,
                                label=f'最小包围圆 $R^*$={res["R_star"]:.2f} m{extra}'))
        if annotate_far:
            thr = res['D'] / 2 + max(1e-3, res['D'] * far_rel)
            n_far = 0
            for P in poly:
                d = math.hypot(P[0] - C[0], P[1] - C[1])
                if d > thr:
                    dy = 8 if n_far % 2 == 0 else -16
                    ax.annotate(f'外溢 {d - res["D"]/2:.2f} m', P, textcoords='offset points',
                                xytext=(7, dy), fontsize=8, color=C_DIAM, fontweight='bold',
                                zorder=9)
                    n_far += 1
    for i, S in enumerate(dets):
        ax.plot(S[0], S[1], 'o', color=C_DET, ms=7, mec='white', mew=1.2, zorder=7)
        ax.annotate(f'$S_{i+1}$', S, textcoords='offset points', xytext=(7, 5),
                    fontsize=9, fontweight='bold', zorder=8)


def _zoom_axes(ax, res, pad_ratio=1.45, min_half=25.0):
    poly = res['poly']
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    h = max((max(xs) - min(xs)) / 2.0, (max(ys) - min(ys)) / 2.0, min_half) * pad_ratio
    ax.set_xlim(cx - h, cx + h)
    ax.set_ylim(cy - h, cy + h)
    return cx - h, cx + h, cy - h, cy + h


def _inset_global(ax, res, dets, thetas, eps, box=None, r_sec=1900.0):
    ins = ax.inset_axes([0.015, 0.585, 0.40, 0.39])
    ins.add_patch(Circle((0, 0), p1.R_TARGET, fill=False, ec=C_OMEGA, ls=':', lw=0.9, zorder=0))
    for S, th in zip(dets, thetas):
        _draw_sector(ins, S, th, eps, r=r_sec, alpha=0.22)
    poly = res['poly']
    if poly and len(poly) >= 3:
        ins.add_patch(MplPolygon(poly, closed=True, facecolor=C_POLY_F,
                                 edgecolor=C_POLY_E, lw=1.0, alpha=0.95, zorder=4))
    for S in dets:
        ins.plot(S[0], S[1], 'o', color=C_DET, ms=4.5, mec='white', mew=0.9, zorder=6)
    if box is not None:
        ins.add_patch(Rectangle((box[0], box[2]), box[1] - box[0], box[3] - box[2],
                                fill=False, ec=C_DIAM, lw=1.5, ls='--', zorder=8))
    ins.set_xlim(-1950, 1950)
    ins.set_ylim(-1950, 1950)
    ins.set_aspect('equal')
    ins.tick_params(labelsize=6)
    ins.set_title('(全局布局，红框为放大区)', fontsize=7.5, pad=2)
    for sp in ins.spines.values():
        sp.set_linewidth(0.8)
    return ins


def _autoview(res, dets, pad=1.35, minhalf=60.0):
    poly = res['poly'] if res['poly'] else []
    pts = list(poly) + list(dets)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h = max((x1 - x0) / 2, (y1 - y0) / 2, minhalf) * pad
    return cx - h, cx + h, cy - h, cy + h


# ================================================================ 挑算例
def pick_examples():
    r"""在同一批 Monte Carlo 场景（相同种子重放）里挑代表性算例。"""
    SEED = 20260912
    picked = {}
    best = None
    for k in range(500):
        rng = random.Random(SEED + 1000 * 3 + k)
        sc = p1.random_scene(3, rng)
        if not sc['ok']:
            continue
        r = p1.solve(sc['dets'], sc['thetas'], N_disk=p1.N_DISK)
        if r['is_empty'] or r['D'] <= 0 or not r['covered']:
            continue
        if 20.0 <= r['D'] <= 45.0:
            best = (k, sc, r)
            break
    picked['covered_mc'] = best

    # (b) 不覆盖算例：在固定种子下确定性搜索"覆盖失败且区域足够大"的典型场景
    rng = random.Random(2026)
    best2 = None
    for _ in range(30000):
        n = 3
        G = p1.sample_uniform_disk(rng, 1800.0)
        dets, ths, ok = [], [], True
        for _i in range(n):
            placed = False
            for _t in range(50):
                a = rng.uniform(0.0, 2.0 * math.pi)
                rr = rng.uniform(900.0, 1450.0)
                S = (G[0] + rr * math.cos(a), G[1] + rr * math.sin(a))
                if S[0] ** 2 + S[1] ** 2 > 1800.0 ** 2:
                    continue
                dets.append(S)
                ths.append((math.degrees(math.atan2(G[1] - S[1], G[0] - S[0]))
                            + rng.uniform(-1.0, 1.0)) % 360.0)
                placed = True
                break
            if not placed:
                ok = False
                break
        if not ok:
            continue
        r = p1.solve(dets, ths, N_disk=p1.N_DISK)
        if r['is_empty'] or r['D'] <= 0 or r['covered']:
            continue
        if not (1.05 <= r['q'] <= 1.12):
            continue
        if best2 is None or r['D'] > best2[2]['D']:
            best2 = (None, {'G': G, 'dets': dets, 'thetas': ths}, r)
    picked['uncovered'] = best2
    return picked


# ================================================================ 图 1
def fig1(jt):
    pick = pick_examples()
    fig = plt.figure(figsize=(14.0, 11.4))
    gs = fig.add_gridspec(2, 2, hspace=0.34, wspace=0.18)

    # ---------- (a) 覆盖算例：两检测点对称交会 ----------
    ax = fig.add_subplot(gs[0, 0])
    det_a = [(-400.0, 0.0), (400.0, 0.0)]
    src_a = (0.0, 100.0)
    th_a = [math.degrees(math.atan2(src_a[1] - S[1], src_a[0] - S[0])) % 360 for S in det_a]
    r_a = p1.solve(det_a, th_a, N_disk=p1.N_DISK)
    box_a = _zoom_axes(ax, r_a, pad_ratio=1.6, min_half=45.0)
    _draw_result(ax, r_a, det_a, th_a, p1.EPS_DEG, r_sec=150.0)
    ax.plot(src_a[0], src_a[1], marker='*', color=C_SRC, ms=14, mec='black', mew=0.8, zorder=9)
    ax.annotate('真实源 $G$', src_a, textcoords='offset points', xytext=(8, -14),
                fontsize=9, fontweight='bold', color='#8a6d00', zorder=9)
    ax.set_aspect('equal')
    ax.grid(alpha=0.3, ls=':', lw=0.6, color=C_GRID)
    ax.set_title('(a) 直径圆覆盖成立的算例（两个检测点对称交会）\n'
                 f'$D$={r_a["D"]:.2f} m，$R^*$={r_a["R_star"]:.2f} m，'
                 f'$q=2R^*/D$={r_a["q"]:.4f}，off={r_a["off"]:.1e} m —— 直径圆覆盖成立',
                 fontsize=10.5, color=C_MEC, fontweight='bold')
    ax.set_xlabel('东坐标 $x$ (m)', fontsize=10)
    ax.set_ylabel('北坐标 $y$ (m)', fontsize=10)
    _inset_global(ax, r_a, det_a, th_a, p1.EPS_DEG, box=box_a, r_sec=1900.0)
    ax.legend(loc='lower right', fontsize=8, framealpha=0.93)
    FIG_INPUTS['fig1a_covered'] = {
        'kind': 'designed_two_detector', 'G': src_a,
        'D': r_a['D'], 'R_star': r_a['R_star'], 'q': r_a['q'], 'off': r_a['off'],
        'covered': r_a['covered'], 'n_vertices': r_a['n_vertices'],
        'dets': det_a, 'thetas': th_a}

    # ---------- (b) 不覆盖算例：随机四检测点 ----------
    ax = fig.add_subplot(gs[0, 1])
    k, sc, r_b = pick['uncovered']
    box_b = _zoom_axes(ax, r_b, pad_ratio=1.6, min_half=12.0)
    _draw_result(ax, r_b, sc['dets'], sc['thetas'], p1.EPS_DEG, r_sec=60.0)
    ax.plot(sc['G'][0], sc['G'][1], marker='*', color=C_SRC, ms=14, mec='black',
            mew=0.8, zorder=9)
    ax.annotate('真实源 $G$', sc['G'], textcoords='offset points', xytext=(8, -14),
                fontsize=9, fontweight='bold', color='#8a6d00', zorder=9)
    ax.set_aspect('equal')
    ax.grid(alpha=0.3, ls=':', lw=0.6, color=C_GRID)
    ax.set_title('(b) 直径圆覆盖失败的典型算例（搜索得到，$n=4$ 场景）\n'
                 f'$D$={r_b["D"]:.2f} m，$R^*$={r_b["R_star"]:.2f} m，'
                 f'$q$={r_b["q"]:.4f}，off={r_b["off"]:.2f} m —— 直径圆覆盖失败',
                 fontsize=10.5, color=C_DIAM, fontweight='bold')
    ax.set_xlabel('东坐标 $x$ (m)', fontsize=10)
    ax.set_ylabel('北坐标 $y$ (m)', fontsize=10)
    _inset_global(ax, r_b, sc['dets'], sc['thetas'], p1.EPS_DEG, box=box_b, r_sec=1900.0)
    ax.legend(loc='lower right', fontsize=8, framealpha=0.93)
    FIG_INPUTS['fig1b_uncovered'] = {
        'kind': 'searched_uncovered', 'search_seed': 2026, 'G': sc['G'],
        'D': r_b['D'], 'R_star': r_b['R_star'], 'q': r_b['q'], 'off': r_b['off'],
        'covered': r_b['covered'], 'n_vertices': r_b['n_vertices'],
        'dets': sc['dets'], 'thetas': sc['thetas']}

    # ---------- (c) Jung 紧算例：全局布局 ----------
    dets, ths = jt['dets'], jt['thetas']
    rho = jt['rho']
    poly = jt['poly']
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    pad = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.9 + 60.0
    box_c = (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)
    ax = fig.add_subplot(gs[1, 0])
    ax.add_patch(Circle((0, 0), p1.R_TARGET, fill=False, ec=C_OMEGA, ls='-', lw=1.4,
                        label='目标区域 $\\Omega$（$R=1800$ m）'))
    for i, S in enumerate(dets):
        ax.add_patch(Circle(S, p1.R_EFF, fill=False, ec='#4292c6', ls='--', lw=1.0, alpha=0.85,
                            label='$D(S_i,R_{\\rm eff})$ 圆盘' if i == 0 else None))
    for S, th in zip(dets, ths):
        _draw_sector(ax, S, th, p1.EPS_DEG, r=1800, alpha=0.28)
    for i, S in enumerate(dets):
        ax.plot(S[0], S[1], 'o', color=C_DET, ms=8, mec='white', mew=1.2, zorder=7)
        ax.annotate(f'$S_{i+1}$', S, textcoords='offset points', xytext=(8, 6),
                    fontsize=10, fontweight='bold', zorder=8)
    ax.plot(0, 0, marker='*', color=C_SRC, ms=16, mec='black', mew=0.8, zorder=8)
    ax.annotate('真实源 $G$', (0, 0), textcoords='offset points', xytext=(10, -16),
                fontsize=9.5, fontweight='bold', color='#8a6d00', zorder=9)
    ax.add_patch(Circle((0, 0), rho, fill=False, ec='#9467bd', ls=':', lw=1.0,
                        label=f'检测点所在圆 $\\rho$={rho:.1f} m'))
    ax.add_patch(Rectangle((box_c[0], box_c[2]), box_c[1] - box_c[0], box_c[3] - box_c[2],
                           fill=False, ec=C_DIAM, lw=1.8, ls='--', zorder=9, label='(d) 放大区'))
    ax.set_xlim(-1950, 1950)
    ax.set_ylim(-1950, 1950)
    ax.set_aspect('equal')
    ax.set_xlabel('东坐标 $x$ (m)', fontsize=10)
    ax.set_ylabel('北坐标 $y$ (m)', fontsize=10)
    ax.legend(loc='upper right', fontsize=8, framealpha=0.93)
    ax.set_title('(c) Jung 紧构造的全局布局：3 个检测点距源 '
                 f'$\\rho$={rho:.1f} m（接近 $R_{{\\rm eff}}$）\n'
                 f'定位区域只有 {jt["D"]:.1f} m，红框为 (d) 的放大区',
                 fontsize=10.5, fontweight='bold')

    # ---------- (d) Jung 紧算例：局部放大 ----------
    ax = fig.add_subplot(gs[1, 1])
    rfull = {'poly': poly, 'D': jt['D'], 'R_star': jt['R_star'], 'q': jt['q'],
             'A': tuple(jt['A']), 'B': tuple(jt['B']), 'C': tuple(jt['C']),
             'covered': jt['covered'], 'off': jt['off'],
             'mec_center': tuple(jt['mec_center'])}
    _draw_result(ax, rfull, dets, ths, p1.EPS_DEG, r_sec=1e5, draw_sectors=False)
    ax.set_xlim(box_c[0], box_c[1])
    ax.set_ylim(box_c[2], box_c[3])
    ax.set_aspect('equal')
    ax.grid(alpha=0.3, ls=':', lw=0.6, color=C_GRID)
    ax.plot(0, 0, marker='*', color=C_SRC, ms=15, mec='black', mew=0.8, zorder=9)
    ax.annotate('$G$', (0, 0), textcoords='offset points', xytext=(8, -14),
                fontsize=10, fontweight='bold', color='#8a6d00', zorder=9)
    ax.set_title(f'(d) Jung 紧局部放大：$q$={jt["q"]:.5f}，'
                 f'Jung 上界 ${JUNG_S}$={p1.JUNG_Q:.5f}\n'
                 f'$D$={jt["D"]:.2f} m，$R^*$={jt["R_star"]:.2f} m，'
                 f'off={jt["off"]:.2f} m —— 直径圆覆盖失败',
                 fontsize=10.5, color=C_DIAM, fontweight='bold')
    ax.legend(loc='upper right', fontsize=8, framealpha=0.93)
    ax.set_xlabel('东坐标 $x$ (m)', fontsize=10)
    ax.set_ylabel('北坐标 $y$ (m)', fontsize=10)

    fig.suptitle('图 1  第一问定位区域的几何构造与"直径圆覆盖"判据'
                 f'（$\\varepsilon=1^\\circ$，$R_{{\\rm eff}}$={p1.R_EFF:.0f} m，'
                 f'圆盘以 $N_{{\\rm disk}}$={p1.N_DISK} 条切线的外切正多边形逼近）',
                 fontsize=13.0, fontweight='bold', y=0.975)
    FIG_INPUTS['fig1cd_jung_tight'] = {k2: v for k2, v in jt.items() if k2 != 'poly'}
    _save(fig, 'fig1_geometry_examples.png')


# ================================================================ 图 2
def fig2(mc_summary):
    rows = mc_summary['summary']
    ns = sorted(int(k) for k in rows)
    med = [rows[str(n)]['D_median'] for n in ns]
    mean = [rows[str(n)]['D_mean'] for n in ns]
    p25 = [rows[str(n)]['D_p25'] for n in ns]
    p75 = [rows[str(n)]['D_p75'] for n in ns]
    p95 = [rows[str(n)]['D_p95'] for n in ns]
    cov = [rows[str(n)]['cover_rate'] * 100 for n in ns]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.4, 5.2))
    ax.fill_between(ns, p25, p75, color=C_POLY_E, alpha=0.18, label='25%–75% 分位区间', zorder=2)
    ax.plot(ns, med, 'o-', color=C_POLY_E, lw=2.2, ms=8, label='中位数 $D$', zorder=4)
    ax.plot(ns, mean, 's--', color=C_DIAM, lw=1.6, ms=6, alpha=0.9, label='均值 $D$', zorder=3)
    ax.plot(ns, p95, '^:', color=C_SEC, lw=1.6, ms=6, label='95% 分位 $D$', zorder=3)
    lx = [math.log(x) for x in ns]
    ly = [math.log(y) for y in med]
    mx = sum(lx) / len(lx)
    my = sum(ly) / len(ly)
    slope = sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)
    inter = my - slope * mx
    ax.plot(ns, [math.exp(inter) * x ** slope for x in ns], '-.', color='#7f7f7f', lw=1.2,
            label=f'最小二乘参考线 $D\\propto n^{{{slope:.2f}}}$')
    ax.set_yscale('log')
    ax.set_xlabel('检测点数量 $n$', fontsize=11)
    ax.set_ylabel('定位区域直径 $D$ (m，对数坐标)', fontsize=11)
    ax.set_title('(a) 定位区域直径随检测点数量变化', fontsize=11.5, fontweight='bold')
    ax.set_xticks(ns)
    ax.grid(alpha=0.3, ls=':', lw=0.7, which='both', color=C_GRID)
    ax.legend(fontsize=9, loc='upper right')

    ax2.plot(ns, cov, 'o-', color=C_MEC, lw=2.2, ms=8)
    ax2.axhline(100.0, color='#cccccc', lw=1.0, ls='--')
    ax2.set_xlabel('检测点数量 $n$', fontsize=11)
    ax2.set_ylabel('直径圆覆盖率 (%)', fontsize=11)
    ax2.set_ylim(0, 105)
    ax2.set_xticks(ns)
    ax2.grid(alpha=0.3, ls=':', lw=0.7, color=C_GRID)
    ax2.set_title('(b) 直径圆覆盖率随 $n$ 变化（与 (a) 同一批样本）', fontsize=11.5, fontweight='bold')
    for x, y in zip(ns, cov):
        ax2.annotate(f'{y:.1f}%', (x, y), textcoords='offset points', xytext=(0, 7),
                     ha='center', fontsize=9, fontweight='bold', color=C_MEC)
    fig.suptitle('图 2  定位区域直径与直径圆覆盖率随检测点数量的变化'
                 f'（每档 $n$ 取 {mc_summary["key"]["N_per"]} 例随机场景；检测点全部限制在 '
                 f'$\\Omega$ 内；$N_{{\\rm disk}}$={p1.N_DISK}）',
                 fontsize=12.0, fontweight='bold', y=1.0)
    FIG_INPUTS['fig2_powerlaw_slope'] = slope
    _save(fig, 'fig2_D_vs_n.png')


# ================================================================ 图 3
def fig3(eps_summary):
    rows = eps_summary['summary']
    eps = [r['eps_deg'] for r in rows]
    med = [r['D_median'] for r in rows]
    mean = [r['D_mean'] for r in rows]
    p25 = [r['D_p25'] for r in rows]
    p75 = [r['D_p75'] for r in rows]
    p95 = [r['D_p95'] for r in rows]

    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    ax.fill_between(eps, p25, p75, color=C_POLY_E, alpha=0.20, label='25%–75% 分位区间')
    ax.plot(eps, med, 'o-', color=C_POLY_E, lw=2.3, ms=8, label='中位数 $D$')
    ax.plot(eps, mean, 's--', color=C_DIAM, lw=1.6, ms=6, alpha=0.9, label='均值 $D$')
    ax.plot(eps, p95, '^:', color=C_SEC, lw=1.6, ms=6, label='95% 分位 $D$')
    ax.axvline(1.0, color='#444444', lw=1.4, ls='--')
    ax.annotate('题设 $\\varepsilon=1^\\circ$', (1.0, max(p95) * 0.6), fontsize=10,
                rotation=90, va='center', xytext=(-9, 0), textcoords='offset points',
                color='#444444', fontweight='bold')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel(r'示向度误差 $\varepsilon$ (°)', fontsize=11.5)
    ax.set_ylabel('定位区域直径 $D$ (m，对数坐标)', fontsize=11.5)
    ax.set_title('图 3  直径 $D$ 对示向度误差 $\\varepsilon$ 的数值敏感度\n'
                 f'（每档 $\\varepsilon$ 取 {rows[0]["n_valid"] + rows[0]["n_invalid"]} 例随机场景，'
                 f'$n$={eps_summary["n_detectors"]}，检测点在 $\\Omega$ 内，'
                 f'$N_{{\\rm disk}}$={p1.N_DISK}）',
                 fontsize=11.0, fontweight='bold')
    ax.grid(alpha=0.3, ls=':', lw=0.7, which='both', color=C_GRID)
    ax.legend(fontsize=10, loc='upper left')
    FIG_INPUTS['fig3_eps_at_1deg'] = [r for r in rows if r['eps_deg'] == 1.0][0]
    _save(fig, 'fig3_eps_sensitivity.png')


# ================================================================ 图 4
def fig4(conv):
    rows = conv['summary']
    N = [r['N'] for r in rows]
    mD = [r['mean_rel_err_D'] * 100 for r in rows]
    xD = [r['max_rel_err_D'] * 100 for r in rows]
    theo = [r['theoretical_delta_r_m'] for r in rows]
    N_ext = list(range(8, 4097))
    theo_curve = [p1.disk_outer_error(p1.R_EFF, n) for n in N_ext]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.4, 5.2))
    ax.loglog(N, mD, 'o-', color=C_POLY_E, lw=2.2, ms=8,
              label=f'平均相对误差（参考解 $N$={conv["N_reference"]}）')
    ax.loglog(N, xD, 's--', color=C_DIAM, lw=1.8, ms=7, label='最大相对误差')
    ax.loglog(N_ext, [mD[0] * (N[0] / n) ** 2 for n in N_ext], ':', color='#7f7f7f', lw=1.2,
              label='$\\mathcal{O}(N^{-2})$ 参考斜率')
    ax.axvline(32, color='#8c6d31', lw=1.6, ls='--')
    ax.annotate('旧版本曾用\n$N=32$', (32, min(mD) * 1.6), fontsize=9, color='#8c6d31',
                fontweight='bold', ha='right', xytext=(-9, 0), textcoords='offset points')
    ax.axvline(p1.N_DISK, color=C_MEC, lw=1.6, ls='--')
    ax.annotate(f'本文采用\n$N={p1.N_DISK}$', (p1.N_DISK, min(mD) * 1.6), fontsize=9,
                color=C_MEC, fontweight='bold', ha='left', xytext=(9, 0),
                textcoords='offset points')
    ax.set_xlabel('圆盘外切正 $N$ 边形的边数 $N$', fontsize=11)
    ax.set_ylabel('直径 $D$ 的相对误差 (%)', fontsize=11)
    ax.set_title('(a) $N$ 对定位区域直径的误差收敛', fontsize=11.5, fontweight='bold')
    ax.grid(alpha=0.3, ls=':', lw=0.7, which='both', color=C_GRID)
    ax.legend(fontsize=9, loc='lower left')

    ax2.loglog(N_ext, theo_curve, '-', color=C_SEC, lw=2.0,
               label='理论最大径向外扩 $r\\left(\\sec\\frac{\\pi}{N}-1\\right)$')
    ax2.loglog(N, theo, 'o', color=C_DIAM, ms=8, label='在 $N$ 网格上的取值')
    ax2.axhline(0.1, color=C_MEC, lw=1.3, ls=':', label='0.1 m 门槛')
    ax2.set_xlabel('圆盘外切正 $N$ 边形的边数 $N$', fontsize=11)
    ax2.set_ylabel('最大径向外扩 $\\Delta r$ (m，$r=1500$ m)', fontsize=11)
    ax2.set_title('(b) 外逼近理论误差随 $N$ 下降', fontsize=11.5, fontweight='bold')
    ax2.grid(alpha=0.3, ls=':', lw=0.7, which='both', color=C_GRID)
    ax2.legend(fontsize=9, loc='lower left')
    for n in (32, 64, 256):
        v = p1.disk_outer_error(p1.R_EFF, n)
        ax2.annotate(f'$N$={n}: {v:.3f} m', (n, v), textcoords='offset points',
                     xytext=(9, -3), fontsize=9)
    fig.suptitle('图 4  圆盘约束的外切正多边形逼近：$N$ 的误差收敛验证'
                 f'（固定 {conv["n_scene"]} 个场景，参考解 $N$={conv["N_reference"]}）',
                 fontsize=12.0, fontweight='bold', y=1.0)
    FIG_INPUTS['fig4_convergence'] = conv['summary']
    _save(fig, 'fig4_disk_approx_convergence.png')


# ================================================================ 图 5
def fig5(csv_path):
    data = {}
    with open(csv_path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['status'] != 'ok':
                continue
            n = int(row['n'])
            data.setdefault(n, ([], []))
            data[n][0].append(float(row['D_m']))
            data[n][1].append(float(row['q']))
    ns = sorted(data)
    cmap = plt.get_cmap('viridis')
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.8, 6.0),
                                  gridspec_kw={'width_ratios': [1.25, 1.0]})
    # 左：q 随 D 的分布（Jung 带）
    for i, n in enumerate(ns):
        Ds, qs = data[n]
        ax.scatter(Ds, qs, s=9, alpha=0.55, color=cmap(i / max(1, len(ns) - 1)),
                   edgecolors='none', label=f'$n$={n}', zorder=3)
    ax.axhline(1.0, color=C_DIAM, lw=2.0, zorder=4,
               label='下界 $q=1$（$R^*=D/2$，直径圆覆盖成立）')
    ax.axhline(p1.JUNG_Q, color=C_MEC, lw=2.0, ls='--', zorder=4,
               label=f'上界 $q={JUNG_S}$（Jung 紧）')
    ax.axhspan(1.0, p1.JUNG_Q, color=C_MEC, alpha=0.07, zorder=1)
    jt = FIG_INPUTS['fig1cd_jung_tight']
    ax.plot([jt['D']], [jt['q']], marker='*', color=C_SRC, ms=20, mec='black', mew=1.0,
            zorder=6, label=f'Jung 紧构造（$q$={jt["q"]:.4f}）')
    ax.set_xscale('log')
    ax.set_ylim(0.995, 1.168)
    ax.set_xlabel('定位区域直径 $D$ (m，对数坐标)', fontsize=11.5)
    ax.set_ylabel('$q=2R^*/D$', fontsize=11.5)
    ax.set_title('(a) 全部样本的 $q$ 落在 $[1,\\,2/\\sqrt{3}]$ 带内', fontsize=11.5,
                 fontweight='bold')
    ax.grid(alpha=0.3, ls=':', lw=0.7, which='both', color=C_GRID)
    ax.legend(fontsize=8.5, loc='upper right', ncol=2)

    # 右：q 的箱线分布（按 n）
    groups = [data[n][1] for n in ns]
    bp = ax2.boxplot(groups, tick_labels=[str(n) for n in ns], patch_artist=True,
                     showmeans=False, widths=0.55)
    for patch in bp['boxes']:
        patch.set_facecolor(C_POLY_F)
        patch.set_edgecolor(C_POLY_E)
    ax2.axhline(1.0, color=C_DIAM, lw=2.0, zorder=4, label='$q=1$')
    ax2.axhline(p1.JUNG_Q, color=C_MEC, lw=2.0, ls='--', zorder=4, label=f'$q={JUNG_S}$')
    ax2.axhspan(1.0, p1.JUNG_Q, color=C_MEC, alpha=0.07, zorder=1)
    ax2.set_ylim(0.995, 1.168)
    ax2.set_xlabel('检测点数量 $n$', fontsize=11.5)
    ax2.set_ylabel('$q=2R^*/D$', fontsize=11.5)
    ax2.set_title('(b) $q$ 随 $n$ 的分布（箱线图）', fontsize=11.5, fontweight='bold')
    ax2.grid(alpha=0.3, ls=':', lw=0.7, axis='y', color=C_GRID)
    ax2.legend(fontsize=10, loc='upper left')
    fig.suptitle('图 5  全体 Monte Carlo 样本的 $q=2R^*/D$ 分布与 Jung 上下界'
                 f'（合计 {sum(len(v[1]) for v in data.values())} 个有效样本，'
                 f'全部满足 $1\\leq q\\leq {JUNG_S}$）',
                 fontsize=12.0, fontweight='bold', y=1.0)
    _save(fig, 'fig5_q_vs_D.png')


# ================================================================ 图 6
def fig6():
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 6.0))
    rec_a = FIG_INPUTS['fig1a_covered']
    rec_j = FIG_INPUTS['fig1cd_jung_tight']
    cases = [(axes[0], '(a) ', rec_a),
             (axes[1], '(b) ', rec_j)]
    for ax, lab, rec in cases:
        res = p1.solve(rec['dets'], rec['thetas'], N_disk=p1.N_DISK)
        zoom = ('kind' not in rec) or rec.get('kind') != 'designed_two_detector'
        _draw_result(ax, res, rec['dets'], rec['thetas'], p1.EPS_DEG,
                     r_sec=(1e5 if zoom else 150.0), draw_sectors=(not zoom))
        if zoom:
            poly = res['poly']
            xs = [q[0] for q in poly]
            ys = [q[1] for q in poly]
            h = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.95 + 30.0
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            ax.set_xlim(cx - h, cx + h)
            ax.set_ylim(cy - h, cy + h)
            ax.plot(0, 0, marker='*', color=C_SRC, ms=15, mec='black', mew=0.8, zorder=9)
            ax.annotate('$G$', (0, 0), textcoords='offset points', xytext=(8, -14),
                        fontsize=10, fontweight='bold', color='#8a6d00', zorder=9)
        else:
            box = _zoom_axes(ax, res, pad_ratio=1.6, min_half=45.0)
            ax.plot(rec['G'][0], rec['G'][1], marker='*', color=C_SRC, ms=15, mec='black',
                    mew=0.8, zorder=9)
            ax.annotate('$G$', rec['G'], textcoords='offset points', xytext=(8, -14),
                        fontsize=10, fontweight='bold', color='#8a6d00', zorder=9)
        ax.set_aspect('equal')
        ax.grid(alpha=0.3, ls=':', lw=0.6, color=C_GRID)
        cov = '直径圆覆盖成立' if res['covered'] else '直径圆覆盖失败'
        col = C_MEC if res['covered'] else C_DIAM
        ax.set_title(f'{lab}$q=2R^*/D$={res["q"]:.4f}，$D$={res["D"]:.2f} m，'
                     f'$R^*$={res["R_star"]:.2f} m\n'
                     f'off={res["off"]:.3f} m —— {cov}',
                     fontsize=11, color=col, fontweight='bold')
        ax.legend(loc='lower right', fontsize=8.5, framealpha=0.93)
        ax.set_xlabel('东坐标 $x$ (m)', fontsize=10)
        ax.set_ylabel('北坐标 $y$ (m)', fontsize=10)
    fig.suptitle('图 6  直径圆覆盖成立与失败的几何机理对比'
                 '（红色 ╳ 为直径端点，红色虚线圆为直径圆，绿点线圆为最小包围圆）',
                 fontsize=12.0, fontweight='bold', y=1.0)
    _save(fig, 'fig6_cover_geometry.png')


# ================================================================ main
def main():
    print('=== 第一问 v5 绘图 ===')
    key = json.load(open(os.path.join(RES, 'key_numbers.json'), encoding='utf-8'))
    jt = dict(key['jung_tight'])
    jt['dets'] = [tuple(d) for d in jt['dets']]
    jt['thetas'] = list(jt['thetas'])
    rr = p1.solve(jt['dets'], jt['thetas'], N_disk=p1.N_DISK)
    jt['poly'] = rr['poly']
    jt['A'] = tuple(jt['A'])
    jt['B'] = tuple(jt['B'])
    jt['C'] = tuple(jt['C'])
    jt['mec_center'] = tuple(jt['mec_center'])

    fig1(jt)
    fig2(json.load(open(os.path.join(RES, 'mc_summary.json'), encoding='utf-8')))
    fig3(json.load(open(os.path.join(RES, 'eps_sensitivity.json'), encoding='utf-8')))
    fig4(json.load(open(os.path.join(RES, 'disk_convergence.json'), encoding='utf-8')))
    fig5(os.path.join(RES, 'mc_samples.csv'))
    fig6()

    with open(os.path.join(RES, 'figure_inputs.json'), 'w', encoding='utf-8') as f:
        json.dump(FIG_INPUTS, f, ensure_ascii=False, indent=2, default=float)
    print(f'  -> 写出 {os.path.join(RES, "figure_inputs.json")}')
    print('\n6 张正式插图全部重新生成完毕。')


if __name__ == '__main__':
    main()
