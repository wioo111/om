# -*- coding: utf-8 -*-
r"""问题二 v5 —— 全部正式插图（一键重生成，禁止手工改图）。

产出 figures/：
    fig1_F1_first_detection.png   第一次测量信息、F1、第二检测点可行域与 S2*
    fig2_J_heatmap.png            鲁棒代价 J(S2) 在 Ω 上的热图 + S2* + 候选区域 + 高风险区
    fig3_strategies.png           同批场景下各策略的成功率与定位误差对比
    fig4_candidate_region.png     候选区域 C_eta 随 eta 的演化（仅由第一次测量信息决定）
    fig5_convergence.png          数值超参收敛性
    fig6_decision_flow.png        决策流程

运行： python -X utf8 plot_figures.py  （需先运行 run_experiments.py）
"""
from __future__ import annotations

# Historical implementation below is retained for import compatibility only.
# Direct execution delegates to the single formal Q1/Q2 implementation.
if __name__ == '__main__':
    from pathlib import Path as _Path
    import subprocess as _subprocess
    import sys as _sys
    raise SystemExit(_subprocess.call([_sys.executable, str(_Path(__file__).resolve().parents[2] / '第一二问' / 'run.py'), 'figures', *_sys.argv[1:]]))

import json
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Circle, Polygon as MplPolygon, Rectangle, FancyBboxPatch, Wedge
import numpy as np

import problem2_core as p2

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
FIG = os.path.join(HERE, 'figures')
os.makedirs(FIG, exist_ok=True)

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

C_F1 = '#f6bd60'
C_FEAS = '#84c5a0'
C_S2 = '#c1121f'
C_S1 = '#1f4e79'
C_SRC = '#d4a017'
C_GRIDC = '#d9d9d9'
C_HIGH = '#bdbdbd'
RSQ = r'2/\sqrt{3}'


def _save(fig, name):
    out = os.path.join(FIG, name)
    fig.savefig(out, dpi=160, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    print(f'  写出 {out}')


# ================================================================ 图 1
def fig1():
    d = np.load(os.path.join(RES, 'representative_case.npz'))
    th = float(d['theta1_hat'])
    S2 = d['S2_star']
    F1 = d['F1_poly']
    Gp = d['G_pts']
    ok = d['ok_mask']
    gx, gy = d['grid_X'], d['grid_Y']
    th_r = math.radians(th)

    fig, axes = plt.subplots(1, 2, figsize=(14.2, 6.6),
                             gridspec_kw={'width_ratios': [1.0, 1.05]})

    # ---------------- (a) 全局几何 ----------------
    ax = axes[0]
    ax.add_patch(Circle((0, 0), p2.R_TARGET, fill=False, ec='#8c8c8c', lw=1.5,
                        label='目标区域 $\\Omega$（$R=1800$ m）'))
    ax.add_patch(Circle((0, 0), p2.R_EFF_HI, fill=False, ec='#4292c6', ls='--', lw=1.0,
                        label='$D(S_1,1500)$ 有效接收圆'))
    ax.add_patch(Circle((0, 0), p2.R_EFF_LO, fill=False, ec='#4292c6', ls=':', lw=1.0,
                        label='$D(S_1,1000)$（保证接收内界）'))
    # ±1° 扇形
    ax.add_patch(Wedge((0, 0), p2.R_EFF_HI, th - p2.EPS_DEG, th + p2.EPS_DEG,
                       facecolor='#fdae61', alpha=0.30, lw=0, zorder=1))
    for sgn in (-1, 1):
        a = math.radians(th + sgn * p2.EPS_DEG)
        ax.plot([0, p2.R_EFF_HI * math.cos(a)], [0, p2.R_EFF_HI * math.sin(a)],
                color='#e07b39', lw=1.0, zorder=2)
    ax.annotate('第一次示向度 $\\hat\\theta_1$', (0.55 * p2.R_EFF_HI * math.cos(th_r),
                                            0.55 * p2.R_EFF_HI * math.sin(th_r)),
                fontsize=9.5, fontweight='bold', color='#b35c00', rotation=th,
                ha='center', va='bottom')
    # F1
    if len(F1) >= 3:
        ax.add_patch(MplPolygon(F1, closed=True, facecolor=C_F1, edgecolor='#b35c00',
                                lw=1.4, alpha=0.95, zorder=3, label='第一次可行域 $\\mathcal{F}_1$'))
    # 潜在源采样
    ax.scatter(Gp[:, 0], Gp[:, 1], s=3, c='black', alpha=0.5, zorder=4,
               label='潜在源采样点 $G\\in\\mathcal{F}_1$')
    # 第二检测点可行域（保证能收到第二次示向度）
    if ok.any():
        ax.scatter(gx[ok], gy[ok], s=9, c=C_FEAS, marker='s', alpha=0.75, zorder=5,
                   edgecolors='none',
                   label='保证第二次测向的 $S_2$ 位置（$\\max_G|S_2-G|\\le1000$）')
    ax.scatter(gx[~ok], gy[~ok], s=5, c=C_HIGH, marker='x', alpha=0.5, zorder=4,
               edgecolors='none', label='存在收不到风险的 $S_2$（$J=\\lambda$）')
    # 候选区域 eta=0.2
    reg = d['region_02']
    if reg.any():
        ax.scatter(gx[reg], gy[reg], s=26, facecolors='none', edgecolors='#0b6e4f',
                   linewidths=1.6, zorder=7, label='候选区域 $\\mathcal{C}_{20\\%}$')
    # S2*
    ax.plot(S2[0], S2[1], marker='*', color=C_S2, ms=22, mec='black', mew=0.9, zorder=9,
            label='最优第二检测点 $S_2^*$')
    # 镜像解
    mx = np.array([math.cos(th_r) * S2[0] + math.sin(th_r) * S2[1],
                   math.sin(th_r) * S2[0] - math.cos(th_r) * S2[1]])
    ax.plot(mx[0], mx[1], marker='*', color=C_S2, ms=22, mec='black', mew=0.9,
            alpha=0.45, zorder=9, label='镜像最优解（同样最优）')
    ax.plot(0, 0, 'o', color=C_S1, ms=9, mec='white', mew=1.3, zorder=10)
    ax.annotate('$S_1$', (0, 0), textcoords='offset points', xytext=(7, -15),
                fontsize=11, fontweight='bold', zorder=11)
    ax.plot([0, S2[0]], [0, S2[1]], color=C_S2, lw=1.0, ls='-', zorder=6)
    ax.set_xlim(-1950, 1950)
    ax.set_ylim(-1950, 1950)
    ax.set_aspect('equal')
    ax.grid(alpha=0.3, ls=':', lw=0.6, color=C_GRIDC)
    ax.set_xlabel('东坐标 $x$ (m)', fontsize=10.5)
    ax.set_ylabel('北坐标 $y$ (m)', fontsize=10.5)
    ax.set_title('(a) 第二次移动前可获得的信息：$S_1$、$\\hat\\theta_1$、$\\mathcal{F}_1$、'
                 '可行 $S_2$ 区域', fontsize=11.5, fontweight='bold')
    ax.legend(loc='lower left', fontsize=8, framealpha=0.94)

    # ---------------- (b) (L, alpha) 平面 ----------------
    ax = axes[1]
    cfg = p2.Cfg()
    F1c, lam, pts, ws, wsum = p2._f1_points((0.0, 0.0), th, cfg)
    alphas = np.arange(-90.0, 90.0 + 1e-9, 1.0)
    L_lo = np.full_like(alphas, np.nan)
    L_hi = np.full_like(alphas, np.nan)
    for i, al in enumerate(alphas):
        iv = p2._l_interval((0.0, 0.0), th, pts, float(al), p2.R_TARGET)
        if iv:
            L_lo[i], L_hi[i] = iv
    # J 在边界上的取值
    J_hi = np.full_like(alphas, np.nan)
    J_lo = np.full_like(alphas, np.nan)
    for i, al in enumerate(alphas):
        if np.isnan(L_hi[i]):
            continue
        for L, store in ((L_hi[i], J_hi), (max(L_lo[i], 1.0), J_lo)):
            A = math.radians(th + al)
            S2t = (L * math.cos(A), L * math.sin(A))
            m = p2.objective_map((0.0, 0.0), th, cfg, np.array([S2t[0]]),
                                 np.array([S2t[1]]), pts, ws, wsum, lam,
                                 p2.R_TARGET, None)
            store[i] = m['J'][0]
    good = ~np.isnan(L_hi)
    ax.fill_between(alphas[good], L_lo[good], L_hi[good], color=C_FEAS, alpha=0.35,
                    label='满足 $\\max_G|S_2-G|\\le1000$ 的 $(L,\\alpha)$ 区域')
    ax.plot(alphas[good], L_hi[good], color='#0b6e4f', lw=1.6, label='上边界 $L_{\\rm hi}(\\alpha)$')
    ax.plot(alphas[good], np.maximum(L_lo[good], 1.0), color='#0b6e4f', lw=1.0, ls='--',
            label='下边界 $L_{\\rm lo}(\\alpha)$')
    # 用 J 上色
    m_hi = np.ma.masked_invalid(J_hi)
    sc = ax.scatter(alphas[good], L_hi[good], c=m_hi, cmap='viridis_r',
                    s=20, zorder=6, vmin=100, vmax=600)
    plt.colorbar(sc, ax=ax, label='边界上的最坏代价 $J$ (m)')
    Jstar = float(d['J_star'])
    ax.plot([math.degrees(np.arctan2(S2[1], S2[0])) - th], [np.hypot(*S2)],
            marker='*', color=C_S2, ms=20, mec='black', mew=0.8, zorder=9,
            label=f'$S_2^*$：$L^*$={np.hypot(*S2):.1f} m，$\\alpha^*$='
                  f'{math.degrees(math.atan2(S2[1], S2[0])) - th:+.2f}°')
    ax.axhline(1005.1, color='#888888', ls=':', lw=1.0)
    ax.set_xlim(-90, 90)
    ax.set_ylim(0, 1800)
    ax.set_xlabel('相对第一次测向方向的偏角 $\\alpha$ (°)', fontsize=11)
    ax.set_ylabel('基线长 $L=|S_1S_2|$ (m)', fontsize=11)
    ax.set_title('(b) $(L,\\alpha)$ 平面：可行域与最坏代价 $J$\n'
                 f'$J^*$={Jstar:.2f} m（$\\lambda$={float(d["lam"]):.1f} m）',
                 fontsize=11.5, fontweight='bold')
    ax.grid(alpha=0.3, ls=':', lw=0.6, color=C_GRIDC)
    ax.legend(loc='upper right', fontsize=8.5, framealpha=0.94)

    fig.suptitle('图 1  第二问：第一次测向后可获得的信息与第二检测点选择'
                 f'（$\\varepsilon$=1°，$R_{{\\rm eff}}\\in[1000,1500]$ m，'
                 f'$S_1$=(0,0)，$\\hat\\theta_1$={th:.0f}°）',
                 fontsize=13, fontweight='bold', y=0.99)
    _save(fig, 'fig1_F1_first_detection.png')


# ================================================================ 图 2
def fig2():
    d = np.load(os.path.join(RES, 'representative_case.npz'))
    th = float(d['theta1_hat'])
    gx, gy = d['grid_X'], d['grid_Y']
    J = d['J_map']
    lam = float(d['lam'])
    S2 = d['S2_star']
    F1 = d['F1_poly']
    jmax = min(600.0, np.nanmax(J))

    fig, axes = plt.subplots(1, 2, figsize=(14.2, 6.6))
    for ax, key, title in ((axes[0], 'J_map', '(a) 鲁棒最坏代价 $J(S_2)$'),
                           (axes[1], 'J_rn_map', r'(b) 风险中性期望代价 $J_{\rm RN}(S_2)$')):
        if key == 'J_map':
            X, Y, Z = gx, gy, J
        else:
            X, Y, Z = d['rn_grid_X'], d['rn_grid_Y'], d['J_rn_map']
        Zm = np.ma.masked_greater(Z, jmax)
        m = ax.scatter(X, Y, c=Zm, cmap='viridis_r', s=9, vmin=0, vmax=jmax,
                       edgecolors='none')
        plt.colorbar(m, ax=ax, label='代价 (m)')
        ax.scatter(X[Z > jmax], Y[Z > jmax], s=4, c=C_HIGH, marker='x',
                   edgecolors='none', alpha=0.6)
        ax.add_patch(Circle((0, 0), p2.R_TARGET, fill=False, ec='#8c8c8c', lw=1.2))
        ax.add_patch(Circle((0, 0), p2.R_EFF_LO, fill=False, ec='#4292c6', ls=':', lw=1.0))
        if len(F1) >= 3:
            ax.add_patch(MplPolygon(F1, closed=True, facecolor='none', edgecolor='#b35c00',
                                    lw=1.2, zorder=6))
            ax.annotate(r'$\mathcal{F}_1$', (F1[0][0] * 0.6, F1[0][1] * 0.6), fontsize=10,
                        color='#b35c00', fontweight='bold')
        ax.plot(0, 0, 'o', color=C_S1, ms=8, mec='white', mew=1.2, zorder=9)
        ax.set_xlim(-1950, 1950)
        ax.set_ylim(-1950, 1950)
        ax.set_aspect('equal')
        ax.grid(alpha=0.25, ls=':', lw=0.6, color=C_GRIDC)
        ax.set_xlabel('东坐标 $x$ (m)', fontsize=10.5)
        ax.set_ylabel('北坐标 $y$ (m)', fontsize=10.5)
        ax.set_title(title, fontsize=11.5, fontweight='bold')
        ax.annotate('灰色 ×：$J=\\lambda$（存在收不到第二次示向度的风险）',
                    (0.02, 0.02), xycoords='axes fraction', fontsize=8.5, color='#666666')
    # 标 S2* 与候选区域
    S2s = d['S2_star']
    reg = d['region_02']
    axes[0].plot(S2s[0], S2s[1], marker='*', color=C_S2, ms=22, mec='black', mew=0.9,
                 zorder=10, label='$S_2^*$')
    axes[0].scatter(gx[reg], gy[reg], s=40, facecolors='none', edgecolors=C_S2,
                    linewidths=1.6, zorder=9, label='$\\mathcal{C}_{20\\%}$')
    axes[0].legend(loc='upper right', fontsize=9, framealpha=0.94)
    rn = d['S2_rn']
    axes[1].plot(rn[0], rn[1], marker='*', color='#6a3d9a', ms=22, mec='black', mew=0.9,
                 zorder=10, label='风险中性最优 $S_2^{\\rm RN}$')
    axes[1].legend(loc='upper right', fontsize=9, framealpha=0.94)
    fig.suptitle('图 2  第二检测点代价场（$\\hat\\theta_1$=45°，粗网格 20 m）'
                 '：主判据为最坏代价，对照判据为风险中性期望代价',
                 fontsize=12.5, fontweight='bold', y=0.99)
    _save(fig, 'fig2_J_heatmap.png')


# ================================================================ 图 3
def fig3():
    with open(os.path.join(RES, 'strategy_summary.json'), encoding='utf-8') as f:
        S = json.load(f)
    names = [k for k in S if k != 'key']
    short = ['鲁棒最优\n$S_2^*$', '风险中性\n最优', '随机可行点', '沿测向\n方向 750 m',
             '测向垂线\n方向 1000 m', 'oracle-Thales\n(不可实现)']
    succ = [S[n]['success_rate'] * 100 for n in names]
    nfail = [S[n]['n_no_signal'] + S[n]['n_empty_region'] for n in names]
    N = S[names[0]]['N_total']

    fig, axes = plt.subplots(1, 3, figsize=(15.6, 5.2))
    ax = axes[0]
    cols = ['#0b6e4f'] + ['#4c9f70'] * 2 + ['#e79f9f'] * 2 + ['#999999']
    bars = ax.bar(short, succ, color=cols, edgecolor='#333333', lw=0.8)
    for b, v, nf in zip(bars, succ, nfail):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f'{v:.1f}%\n(失败 {nf})',
                ha='center', fontsize=8.5, fontweight='bold')
    ax.set_ylim(0, 118)
    ax.set_ylabel('成功定位率 (%)', fontsize=11)
    ax.set_title(f'(a) 成功率（同一批 {N} 个场景，失败不剔除）', fontsize=11,
                 fontweight='bold')
    ax.grid(alpha=0.3, axis='y', ls=':', color=C_GRIDC)
    plt.setp(ax.get_xticklabels(), fontsize=8)
    ax.axhline(100, color='#cccccc', ls='--', lw=1.0)

    ax = axes[1]
    data = [[S[n]['D_median_among_localized'] or 0,
             S[n]['D_p95_among_localized'] or 0] for n in names]
    x = np.arange(len(names))
    ax.bar(x - 0.2, [d[0] for d in data], width=0.38, color='#1f4e79', label='中位数')
    ax.bar(x + 0.2, [d[1] for d in data], width=0.38, color='#fdae61', label='95% 分位')
    for xi, d_ in zip(x, data):
        ax.text(xi - 0.2, d_[0] + 1, f'{d_[0]:.1f}', ha='center', fontsize=8)
        ax.text(xi + 0.2, d_[1] + 1, f'{d_[1]:.1f}', ha='center', fontsize=8)
    ax.axhline(34.64, color='#2ca02c', ls='--', lw=1.4,
               label='停止阈值 $D=20\\sqrt3\\approx34.64$ m')
    ax.set_xticks(x)
    ax.set_xticklabels(short, fontsize=8)
    ax.set_ylabel('最终定位区域直径 $D$ (m)', fontsize=11)
    ax.set_title('(b) 成功定位样本的 $D$（分母为各自定位成功数）', fontsize=11,
                 fontweight='bold')
    ax.grid(alpha=0.3, axis='y', ls=':', color=C_GRIDC)
    ax.legend(fontsize=8.5)

    ax = axes[2]
    cost = [S[n]['cost_median'] for n in names]
    cost95 = [S[n]['cost_p95'] for n in names]
    ax.bar(x - 0.2, cost, width=0.38, color='#1f4e79', label='中位数')
    ax.bar(x + 0.2, cost95, width=0.38, color='#d62728', label='95% 分位')
    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(short, fontsize=8)
    ax.set_ylabel('综合代价 (m，失败按 $\\lambda=\\mathrm{diam}(\\mathcal F_1)$ 计入)',
                  fontsize=10.5)
    ax.set_title(f'(c) 全样本综合代价（$N$={N}，含失败样本）', fontsize=11,
                 fontweight='bold')
    ax.grid(alpha=0.3, axis='y', ls=':', which='both', color=C_GRIDC)
    ax.legend(fontsize=8.5)
    fig.suptitle('图 3  同一批场景下各第二检测点策略的对比（$\\theta_1,\\theta_2$ 均加 '
                 '$\\pm1^\\circ$ 测量误差；失败样本一律计入，不剔除）',
                 fontsize=12.5, fontweight='bold', y=1.0)
    _save(fig, 'fig3_strategies.png')


# ================================================================ 图 4
def fig4():
    d = np.load(os.path.join(RES, 'representative_case.npz'))
    th = float(d['theta1_hat'])
    gx, gy = d['grid_X'], d['grid_Y']
    J = d['J_map']
    Jstar = float(d['J_star'])
    lam = float(d['lam'])
    S2 = d['S2_star']
    F1 = d['F1_poly']
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 5.6))
    for ax, eta, key in zip(axes, (0.05, 0.2, 0.5),
                            ('region_005', 'region_02', 'region_05')):
        reg = d[key]
        ax.scatter(gx[reg], gy[reg], s=16, c=C_S2, alpha=0.85, edgecolors='none',
                   label=f'$\\mathcal{{C}}_{{{int(eta*100)}\\%}}$（{int(reg.sum())} 个网格点）')
        ax.plot(S2[0], S2[1], marker='*', color='#0b6e4f', ms=20, mec='black', mew=0.8,
                zorder=6, label='$S_2^*$')
        bad = J >= lam - 1e-9
        ax.scatter(gx[bad], gy[bad], s=4, c='#8c8c8c', marker='x', edgecolors='none',
                   alpha=0.7, label='高风险区 $J=\\lambda$')
        ax.add_patch(Circle((0, 0), p2.R_TARGET, fill=False, ec='#8c8c8c', lw=1.2))
        if len(F1) >= 3:
            ax.add_patch(MplPolygon(F1, closed=True, facecolor=C_F1, edgecolor='#b35c00',
                                    lw=1.0, alpha=0.9))
        ax.plot(0, 0, 'o', color=C_S1, ms=8, mec='white', mew=1.2, zorder=9)
        ax.set_xlim(-1950, 1950)
        ax.set_ylim(-1950, 1950)
        ax.set_aspect('equal')
        ax.grid(alpha=0.25, ls=':', lw=0.6, color=C_GRIDC)
        ax.set_xlabel('东坐标 $x$ (m)', fontsize=10.5)
        ax.set_ylabel('北坐标 $y$ (m)', fontsize=10.5)
        ax.set_title(f'$\\eta$={eta}：$\\mathcal{{C}}_\\eta=\\{{S_2:J(S_2)\\le'
                     f'(1+\\eta)J^*\\}}$', fontsize=11, fontweight='bold')
        ax.legend(loc='lower left', fontsize=8.5, framealpha=0.94)
    fig.suptitle('图 4  候选检测区域 $\\mathcal{C}_\\eta$ 随容许量 $\\eta$ 的演化\n'
                 '（完全由第一次测量可得的信息决定，不使用真实源位置；'
                 f'$\\hat\\theta_1$={th:.0f}°，$J^*$={Jstar:.2f} m）',
                 fontsize=12.5, fontweight='bold', y=1.0)
    _save(fig, 'fig4_candidate_region.png')


# ================================================================ 图 5
def fig5():
    with open(os.path.join(RES, 'key_numbers.json'), encoding='utf-8') as f:
        conv = json.load(f)
    rows = conv['convergence']
    kinds = [('grid_step', '候选网格间距 (m)'),
             ('k_dir', '第二次示向度扫描点数 $k_{\\rm dir}$'),
             ('F1_samples', '$\\mathcal F_1$ 采样点数'),
             ('n_disk', '圆盘外接多边形边数 $N_{\\rm disk}$')]
    fig, axes = plt.subplots(1, 4, figsize=(17.0, 4.6))
    for ax, (kind, xlab) in zip(axes, kinds):
        sel = [r for r in rows if r['kind'] == kind]
        if not sel:
            continue
        xs = [r['value'] for r in sel]
        Js = [r['J_star'] for r in sel]
        ax.plot(xs, Js, 'o-', color='#1f4e79', lw=2.0, ms=7)
        ref = Js[-1]
        ax.axhline(ref, color='#d62728', ls='--', lw=1.3,
                   label=f'最细设置 $J^*$={ref:.3f} m')
        ax.set_xlabel(xlab, fontsize=10.5)
        ax.set_ylabel('$J^*$ (m)', fontsize=10.5)
        ax.set_xscale('log' if kind != 'n_disk' else 'log')
        ax.grid(alpha=0.3, ls=':', lw=0.6, which='both', color=C_GRIDC)
        ax.legend(fontsize=8.5, loc='lower right')
        ax.set_title(kind, fontsize=10.5, fontweight='bold')
    sel = [r for r in rows if r['kind'] == 'solver']
    txt = '  '.join(f"{r['value']}: J*={r['J_star']:.3f}" for r in sel)
    fig.suptitle('图 5  第二问数值超参收敛性（$S_1$=(0,0)，$\\hat\\theta_1$=0°）\n'
                 f'不同求解路径一致性：{txt}',
                 fontsize=12, fontweight='bold', y=1.04)
    _save(fig, 'fig5_convergence.png')


# ================================================================ 图 6
def fig6():
    fig, ax = plt.subplots(figsize=(12.6, 8.4))
    ax.axis('off')
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 12)

    nodes = [
        (0.6, 10.6, 2.6, 1.0, '机器狗在 $S_1$ 检测\n得到 $\\hat\\theta_1=\\theta_1+e_1$', '#e3f2fd'),
        (3.9, 10.6, 3.0, 1.0, '构造第一次可行域\n$\\mathcal F_1=\\Omega\\cap\\{5<|G-S_1|\\le1500\\}$\n$\\cap\\,|\\mathrm{wrap}(\\angle(G-S_1)-\\hat\\theta_1)|\\le1^\\circ$', '#fff3e0'),
        (7.6, 10.6, 4.8, 1.0, '在 $\\Omega$ 上枚举候选 $S_2$\n（只用 $S_1,\\hat\\theta_1,\\Omega,\\varepsilon$；**不使用真实 $G$**）', '#fff3e0'),
        (0.6, 8.4, 4.0, 1.0, '对每个 $S_2$：$\\;J(S_2)=\\max_{G\\in\\mathcal F_1}C(S_2,G)$\n'
                             '$C=0$（$\\le5$m）／$D_2$（$\\le1000$m）／$\\lambda$（$>1000$m）', '#e8f5e9'),
        (5.2, 8.4, 3.4, 1.0, '求解 $S_2^*=\\arg\\min J(S_2)$', '#e8f5e9'),
        (9.2, 8.4, 3.2, 1.0, '候选区域\n$\\mathcal C_\\eta=\\{J\\le(1+\\eta)J^*\\}$', '#e8f5e9'),
        (2.0, 6.2, 3.6, 1.0, '移动到 $S_2^*$（$L^*\\approx1005$ m，$\\alpha^*\\approx\\pm31^\\circ$）\n'
                             '5 s 检测，得到 $\\hat\\theta_2=\\theta_2+e_2$', '#e1f5fe'),
        (7.0, 6.2, 4.4, 1.0, '两次示向度交会：\n'
                             '$\\mathcal L=\\mathrm{Sector}(S_1,\\hat\\theta_1)\\cap\\mathrm{Sector}(S_2,\\hat\\theta_2)\\cap\\Omega\\cap D(\\cdot,1500)$', '#e1f5fe'),
        (4.6, 4.0, 4.0, 1.0, '计算 $R^*$（最小包围圆半径）\n$D$（定位区域直径）', '#f3e5f5'),
        (2.0, 1.6, 3.4, 1.1, '$R^*\\le20$ m？\n是：移动到 $c^*$\n光学定位 3 s + 清除 2 s', '#c8e6c9'),
        (7.2, 1.6, 3.8, 1.1, '否：进入问题三\n补充第三个检测点', '#ffe0b2'),
    ]
    for (x, y, w, h, t, col) in nodes:
        txt = t.replace('**', '')
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.09',
                                    facecolor=col, edgecolor='#555555', lw=1.1))
        ax.text(x + w / 2, y + h / 2, txt, ha='center', va='center', fontsize=8.6)
    arrows = [((3.2, 11.1), (3.9, 11.1)), ((6.9, 11.1), (7.6, 11.1)),
              ((2.6, 10.6), (2.6, 9.4)), ((10.0, 10.6), (10.0, 9.4)),
              ((8.6, 8.9), (8.8, 8.9)), ((4.6, 8.9), (5.2, 8.9)),
              ((6.9, 8.4), (6.9, 7.2)), ((4.6, 6.2), (8.0, 5.0)),
              ((8.0, 4.0), (6.6, 2.7)), ((7.9, 4.0), (8.6, 2.7))]
    for (x1, y1), (x2, y2) in arrows:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='-|>', lw=1.4, color='#444444'))
    ax.text(6.5, 0.6, '注：整个流程中机器狗只能访问 $S_1,\\hat\\theta_1,\\Omega,\\varepsilon$ 与'
                      '接收半径范围 $[1000,1500]$；真实 $G$、真实 $d$ 始终不可得。',
            ha='center', fontsize=9.5, color='#8a2b06', fontweight='bold')
    ax.set_title('图 6  第二问决策流程（可执行策略，无信息泄漏）', fontsize=13,
                 fontweight='bold', pad=12)
    _save(fig, 'fig6_decision_flow.png')


if __name__ == '__main__':
    print('=== 第二问 v5 绘图 ===')
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig6()
    print('\n6 张正式插图全部重新生成完毕。')
