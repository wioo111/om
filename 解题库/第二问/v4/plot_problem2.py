# -*- coding: utf-8 -*-
r"""plot_problem2.py — 第二问 v4 绘图（高级感升级版 + 3 张新图）

6 张图：
  1. fig_strategies.png            — 5 策略 D + 覆盖率对比
  2. fig_thales_geometry.png       — 5 策略几何对比
  3. fig_heatmap_L.png             — D 关于 (d, L) 的真热图
  4. fig4_candidate_region.png     — 候选区域随 η 演化（新增）
  5. fig5_convergence_N_scan.png   — J* 随 N_per 收敛扫描（新增）
  6. fig6_decision_flow.png        — 决策流程图（新增）

注意：上一版错误的 `aspect='='Y_ratio` 是文档生成时笔误，未写入磁盘。
"""
import os
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, Polygon as MplPolygon, FancyBboxPatch
import numpy as np

import problem2_v4 as p2
p1 = p2.p1

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(HERE, 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 110

# 配色
COL_THALES = '#d62728'
COL_OPT = '#1f77b4'
COL_POLY = '#b8d8e8'
COL_EDGE = '#1f4e79'


def _draw_sector(ax, S, theta_deg, eps_deg, r=800, color='#fdae61',
                 alpha=0.18, label=None):
    a0 = np.deg2rad(theta_deg - eps_deg)
    a1 = np.deg2rad(theta_deg + eps_deg)
    n = 60
    angles = np.linspace(a0, a1, n)
    xs = [S[0]] + [S[0] + r * np.cos(a) for a in angles]
    ys = [S[1]] + [S[1] + r * np.sin(a) for a in angles]
    ax.fill(xs, ys, color=color, alpha=alpha, edgecolor=color, linewidth=0.6,
            label=label)


def _draw_polygon(ax, poly, color, label=None, alpha=0.4):
    if not poly or len(poly) < 3:
        return
    xs, ys = zip(*poly)
    ax.fill(xs, ys, facecolor=color, alpha=alpha,
            edgecolor=color, linewidth=1.6, label=label)


# ============================================================
# 图 1：5 策略对比（高级感升级）
# ============================================================
def fig_strategies(json_path):
    with open(json_path, encoding='utf-8') as f:
        results = json.load(f)
    names = list(results.keys())
    D_data = [results[n]['D'] for n in names]
    cov_data = [np.mean(results[n]['covered']) * 100
                if results[n]['covered'] else 0 for n in names]

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))

    # 左：D 箱线图（对数坐标）
    ax = axes[0]
    bp = ax.boxplot(D_data, tick_labels=names, patch_artist=True, showmeans=True)
    for patch in bp['boxes']:
        patch.set_facecolor(COL_POLY)
    ax.set_yscale('log')
    ax.set_ylabel('定位区域直径 $D$ (m，对数坐标)', fontsize=11)
    ax.set_title('各策略下的 $D$ 分布（越小越好）', fontsize=12)
    ax.grid(True, alpha=0.3, axis='y')
    plt.setp(ax.get_xticklabels(), rotation=15, ha='right', fontsize=9)

    # 右：覆盖率柱状图
    ax = axes[1]
    bars = ax.bar(names, cov_data, color=COL_OPT, edgecolor='#1f4e79')
    for b, v in zip(bars, cov_data):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f'{v:.1f}%',
                ha='center', fontsize=10)
    ax.axhline(50, color=COL_THALES, ls='--', alpha=0.5,
               label='50% 警戒线')
    ax.set_ylabel('覆盖率 (%)', fontsize=11)
    ax.set_ylim(0, 110)
    ax.set_title('各策略下的覆盖率', fontsize=12)
    ax.legend(loc='lower left', fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    plt.setp(ax.get_xticklabels(), rotation=15, ha='right', fontsize=9)

    plt.suptitle('第二问 · 5 策略对比（N 实测自 strategy_results.json）', fontsize=12)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, 'fig_strategies.png')
    plt.savefig(out, dpi=140, bbox_inches='tight')
    plt.close()
    print(f'已写出：{out}')


# ============================================================
# 图 2：Thales 圆 + 5 策略几何对比（升级版）
# ============================================================
def fig_thales_geometry():
    G = (600.0, 400.0)
    S1 = (0.0, 0.0)
    eps = p2.EPS_DEG
    theta1 = math.degrees(math.atan2(G[1] - S1[1], G[0] - S1[0]))
    d = math.hypot(G[0] - S1[0], G[1] - S1[1])

    th_rad = math.radians(theta1)
    L_thales = d * math.tan(math.radians(eps))
    perp = th_rad + math.pi / 2
    candidates = {
        'Thales 圆': (G[0] + L_thales * math.cos(perp),
                      G[1] + L_thales * math.sin(perp)),
        '最佳共线': (S1[0] + 1000 * math.cos(perp), S1[1] + 1000 * math.sin(perp)),
        '平行共线': (S1[0] + 100 * math.cos(th_rad), S1[1] + 100 * math.sin(th_rad)),
        '反平行':   (S1[0] - 100 * math.cos(th_rad), S1[1] - 100 * math.sin(th_rad)),
        '随机':     (S1[0] + 600 * math.cos(perp + 0.5),
                     S1[1] + 600 * math.sin(perp + 0.5)),
    }

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    axes_flat = axes.flatten()

    for idx, (name, S2) in enumerate(candidates.items()):
        ax = axes_flat[idx]
        theta2 = math.degrees(math.atan2(G[1] - S2[1], G[0] - S2[0])) % 360
        res = p1.solve_problem_1(
            dets=[S1, S2], thetas=[theta1, theta2],
            eps_deg=eps, R_eff=1500.0, R_target=1800.0,
        )
        poly = res['poly']
        D = res['D']

        if poly and len(poly) >= 3:
            xs, ys = zip(*poly)
            ext = max(max(abs(x) for x in xs), max(abs(y) for y in ys))
        else:
            ext = 0
        ext = max(ext, abs(S1[0]), abs(S1[1]), abs(S2[0]), abs(S2[1]),
                  abs(G[0]), abs(G[1]), 500)
        v = ext * 1.4
        ax.set_xlim(-v, v)
        ax.set_ylim(-v, v)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.25, ls=':')

        ax.add_patch(Circle((0, 0), 1800, fill=False, ls=':', lw=0.8, color='gray'))
        ax.add_patch(Circle(S1, 1500, fill=False, ls='--', lw=0.7,
                            color='#1f77b4', alpha=0.4))
        ax.add_patch(Circle(S2, 1500, fill=False, ls='--', lw=0.7,
                            color='#d62728', alpha=0.4))
        _draw_sector(ax, S1, theta1, eps, r=ext * 0.85, color='#1f77b4',
                     label='$S_1$ 扇形')
        _draw_sector(ax, S2, theta2, eps, r=ext * 0.85, color='#d62728',
                     label='$S_2$ 扇形')
        if 'Thales' in name:
            ax.add_patch(Circle(G, L_thales, fill=False, ls='--', lw=1.6,
                                color=COL_THALES,
                                label=f'Thales 圆 $L$={L_thales:.1f} m'))
        _draw_polygon(ax, poly, '#fdae61', label='定位多边形')
        if D > 0:
            A, B = res['A'], res['B']
            ax.plot([A[0], B[0]], [A[1], B[1]], 'k-', lw=2.5)
            ax.scatter(*A, c='red', marker='x', s=80, zorder=5)
            ax.scatter(*B, c='red', marker='x', s=80, zorder=5)
        ax.plot(*S1, 'o', c='#1f77b4', ms=8, zorder=6)
        ax.plot(*S2, 'o', c='#d62728', ms=8, zorder=6)
        ax.plot(*G, '*', c='gold', ms=14, mec='black', zorder=7)
        ax.set_title(f'{name}\n$D$={D:.2f} m', fontsize=11)
        ax.legend(loc='upper right', fontsize=7)

    # 第 6 子图：策略说明表
    ax = axes_flat[5]
    ax.axis('off')
    ax.text(0.5, 0.95, '策略几何对比', ha='center', fontsize=14,
            fontweight='bold', transform=ax.transAxes)
    table = [
        ('Thales 圆',  '$S_2$ 在过 G 的垂线上、距 G=$d\\tan\\varepsilon$',  '最佳'),
        ('最佳共线',  '$S_2$ 与 $\\theta_1$ 垂直、距 $S_1$=1000 m',             '次优'),
        ('平行共线',  '$S_2$ 在 $S_1$ 沿 $\\theta_1$ 方向 100 m',                 '退化'),
        ('反平行',    '$S_2$ 在 $S_1$ 反方向 100 m',                              '退化'),
        ('随机',      '$S_2$ 在 $S_1$ 周围均匀随机',                                  '中等'),
    ]
    for i, (n, desc, r_) in enumerate(table):
        y = 0.82 - i * 0.15
        ax.text(0.05, y, n, fontsize=10, fontweight='bold',
                transform=ax.transAxes)
        ax.text(0.05, y - 0.06, desc, fontsize=8.5, color='gray',
                transform=ax.transAxes)
        ax.text(0.95, y - 0.02, r_, fontsize=10, ha='right',
                color=COL_OPT, fontweight='bold', transform=ax.transAxes)

    fig.suptitle(f'第二问 · 5 策略几何对比 ($G$=({int(G[0])},{int(G[1])}), '
                 f'$S_1$=(0,0), $\\varepsilon$={eps}°, $d$={d:.0f} m)',
                 fontsize=14)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, 'fig_thales_geometry.png')
    plt.savefig(out, dpi=140, bbox_inches='tight')
    plt.close()
    print(f'已写出：{out}')


# ============================================================
# 图 3：D 关于 (d, L) 真热图
# ============================================================
def fig_heatmap_L():
    ds = np.linspace(200, 1500, 14)
    Ls = np.linspace(100, 1500, 15)
    D_grid = np.zeros((len(Ls), len(ds)))
    eps = p2.EPS_DEG

    for i, L in enumerate(Ls):
        for j, d in enumerate(ds):
            S1 = (0.0, 0.0)
            G = (d, 0.0)
            S2 = (0.0, L)
            theta1 = 0.0
            theta2 = np.degrees(np.arctan2(G[1] - S2[1], G[0] - S2[0])) % 360
            res = p1.solve_problem_1(
                dets=[S1, S2], thetas=[theta1, theta2],
                eps_deg=eps, R_eff=1500.0, R_target=1800.0,
            )
            D_grid[i, j] = res['D']

    fig, ax = plt.subplots(figsize=(10, 6.5))
    im = ax.imshow(D_grid, origin='lower', aspect='auto',
                   extent=[ds[0], ds[-1], Ls[0], Ls[-1]],
                   cmap='viridis_r', vmin=0, vmax=200)
    cbar = plt.colorbar(im, ax=ax, label='$D$ (m，越小越好)')
    cs = ax.contour(ds, Ls, D_grid, levels=[20, 40, 60, 80, 100],
                    colors='white', linewidths=0.8, alpha=0.6)
    ax.clabel(cs, fmt='%.0f', fontsize=8)

    L_thales = ds * np.tan(np.radians(eps))
    ax.plot(ds, L_thales, 'r--', lw=2,
            label=f'Thales 圆: $L = d\\tan({eps}°)$')
    ax.plot(ds, 1.56 * ds, 'b:', lw=1.5, alpha=0.7,
            label='$L^* = 1.56\\cdot d$（工程近似）')

    # 标最小值
    i_min, j_min = np.unravel_index(D_grid.argmin(), D_grid.shape)
    d_min = ds[j_min]
    L_min = Ls[i_min]
    ax.plot(d_min, L_min, 'r*', ms=20, mec='black', mew=1.2,
            label=f'最小值 $D$={D_grid[i_min, j_min]:.1f} m')

    ax.set_xlabel('源距 $|S_1G| = d$ (m)', fontsize=11)
    ax.set_ylabel('基线 $|S_1S_2| = L$ (m)', fontsize=11)
    ax.set_title(f'第二问 · $D$ 关于 $(d, L)$ 的热图（$\\varepsilon$={eps}°，$R_{{\\rm eff}}$=1500 m）', fontsize=12)
    ax.legend(loc='upper left', fontsize=9)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, 'fig_heatmap_L.png')
    plt.savefig(out, dpi=140, bbox_inches='tight')
    plt.close()
    print(f'已写出：{out}')


# ============================================================
# 图 4：候选区域 $\mathcal{C}_\eta$ 随 $\eta$ 演化（新增）
# ============================================================
def fig_candidate_region():
    """固定源 G=(600,400)，扫描 S2 网格计算 J_robust，画 C_η 的 4 个 η 边界。

    用 d 区间内最坏情况源（最坏 d），让候选区域有可观察的大小。
    """
    G = (600.0, 400.0)
    S1 = (0.0, 0.0)
    eps = p2.EPS_DEG
    d_nominal = math.hypot(G[0] - S1[0], G[1] - S1[1])
    theta1 = math.degrees(math.atan2(G[1] - S1[1], G[0] - S1[0]))

    # 网格扫描 S2
    grid_x = np.linspace(-1700, 1700, 50)
    grid_y = np.linspace(-1700, 1700, 50)
    # 取最坏情况：源距 d 不确定，且方向也随机（最坏情况随机源）
    d_grid = [200, 500, 800, 1100, 1400]
    # 源的方位：在 θ1 ± 2° 内随机（与 2ε 一致：第一次读数误差+源位置误差）
    th1_rad = math.radians(theta1)
    L_thales_nominal = d_nominal * math.tan(math.radians(eps))

    # 对每个 S2，对每个 d 的 G（再加角度扰动 ±2°）计算 rho_2，取最坏
    J_map = np.full((len(grid_y), len(grid_x)), 1500.0)
    np.random.seed(42)
    for i, y in enumerate(grid_y):
        for j, x in enumerate(grid_x):
            S2 = (x, y)
            rhos = []
            for d_val in d_grid:
                # 源在 S1 朝 G 方向但距离为 d_val，方向扰动 ±2°
                ux, uy = math.cos(th1_rad), math.sin(th1_rad)
                dth = np.random.uniform(-2, 2)
                G_d = (d_val * (ux * math.cos(math.radians(dth)) - uy * math.sin(math.radians(dth))),
                       d_val * (ux * math.sin(math.radians(dth)) + uy * math.cos(math.radians(dth))))
                # 检查是否在 Ω 内
                if G_d[0] ** 2 + G_d[1] ** 2 > 1800 ** 2:
                    continue
                theta2 = math.degrees(math.atan2(G_d[1] - S2[1], G_d[0] - S2[0])) % 360
                res = p1.solve_problem_1(
                    dets=[S1, S2], thetas=[theta1, theta2],
                    eps_deg=eps, R_eff=1500.0, R_target=1800.0,
                )
                if res['D'] > 1:
                    rhos.append(res['mec_radius'])
                else:
                    rhos.append(1500.0)
            J_map[i, j] = max(rhos) if rhos else 1500.0

    J_star = np.min(J_map)
    print(f"  J* = {J_star:.2f} m (最坏 d ∈ {d_grid}, 角度扰动 ±2°)")

    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    etas = [0.0, 0.05, 0.2, 0.5]
    cmap = plt.cm.Reds
    for ax, eta in zip(axes.flat, etas):
        bound = J_star * (1 + eta)
        mask = J_map <= bound
        XX, YY = np.meshgrid(grid_x, grid_y)
        in_omega = XX ** 2 + YY ** 2 <= 1800 ** 2
        ax.contourf(XX, YY, mask & in_omega, levels=[0.5, 1.5],
                    colors=[cmap(0.3 + eta * 0.5)], alpha=0.85)
        ax.contour(XX, YY, J_map, levels=[bound],
                   colors=[cmap(0.5 + eta * 0.5)], linewidths=1.6)

        # Thales 圆（标在最坏 d 对应的最大 L 上）
        L_thales_max = 1400 * math.tan(math.radians(eps))
        ax.add_patch(Circle(G, L_thales_max, fill=False, ls='--',
                            lw=1.4, color=COL_THALES,
                            label=f'Thales 圆 $d$=1400, $L$={L_thales_max:.1f} m'))
        ax.add_patch(Circle((0, 0), 1800, fill=False, ls=':',
                            lw=0.7, color='gray'))
        ax.plot(*S1, '^', c='#1f77b4', ms=10, mec='black', mew=1, zorder=5)
        ax.plot(*G, '*', c='gold', ms=14, mec='black', mew=1, zorder=5)

        area = np.sum(mask & in_omega) * (grid_x[1] - grid_x[0]) * (grid_y[1] - grid_y[0])
        ax.set_title(f'$\\eta$={eta}, $\\mathcal{{C}}_{{\\eta}}$ 面积≈{area/1e6:.2f} km²',
                     fontsize=11)
        ax.set_xlim(-1800, 1800)
        ax.set_ylim(-1800, 1800)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3, ls=':')
        ax.legend(loc='upper right', fontsize=8)

    fig.suptitle(f'第二问 · 候选区域 $\\mathcal{{C}}_{{\\eta}}$ 随 $\\eta$ 演化 ($J^*$={J_star:.1f} m, 最坏 $d\\in$[500,1400])',
                 fontsize=13, fontweight='bold', y=0.995)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, 'fig4_candidate_region.png')
    plt.savefig(out, dpi=140, bbox_inches='tight')
    plt.close()
    print(f'已写出：{out}')


# ============================================================
# 图 5：J* 随 N_per 收敛扫描（新增）
# ============================================================
def fig_convergence_N_scan():
    """扫描 N_per ∈ {50,100,200,500,1000} 看 J* 收敛。"""
    rng = np.random.default_rng(42)
    Ns = [50, 100, 200, 500, 1000]
    eps = p2.EPS_DEG

    # Thales 圆策略下 J* 收敛
    Jstar_thales = []
    for N_per in Ns:
        J_list = []
        for k in range(N_per):
            d = rng.uniform(500, 1400)
            th = rng.uniform(0, 360)
            S1 = (0, 0)
            G = (d * math.cos(math.radians(th)),
                 d * math.sin(math.radians(th)))
            theta1 = th + rng.uniform(-1, 1)
            theta1 = theta1 % 360
            # Thales S2
            perp = math.radians(theta1) + math.pi / 2
            L = d * math.tan(math.radians(eps))
            S2 = (G[0] + L * math.cos(perp),
                  G[1] + L * math.sin(perp))
            theta2 = math.degrees(math.atan2(G[1] - S2[1], G[0] - S2[0])) % 360
            res = p1.solve_problem_1(
                dets=[S1, S2], thetas=[theta1, theta2],
                eps_deg=eps, R_eff=1500.0, R_target=1800.0,
            )
            if res['D'] > 1:
                J_list.append(res['mec_radius'])
        Jstar_thales.append(np.median(J_list) if J_list else 0)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot(Ns, Jstar_thales, 'o-', color=COL_THALES, lw=2.2, ms=10,
            label='Thales 圆策略 $J^*$ 中位')
    ax.axhline(Jstar_thales[-1], ls='--', color=COL_EDGE, alpha=0.6,
               label=f'$N$=1000 参考 {Jstar_thales[-1]:.1f} m')
    ax.set_xlabel('每配置仿真数 $N_{\\mathrm{per}}$', fontsize=11)
    ax.set_ylabel('$J^*$ 中位 (m)', fontsize=11)
    ax.set_title('第二问 · 采样数 $N_{\\mathrm{per}}$ 对 $J^*$ 收敛性的影响', fontsize=12)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3, ls='--')
    ax.set_xscale('log')
    ax.set_xticks(Ns)
    ax.set_xticklabels([str(n) for n in Ns])
    plt.tight_layout()
    out = os.path.join(FIG_DIR, 'fig5_convergence_N_scan.png')
    plt.savefig(out, dpi=140, bbox_inches='tight')
    plt.close()
    print(f'已写出：{out}')


# ============================================================
# 图 6：决策流程图（新增）
# ============================================================
def fig_decision_flow():
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.axis('off')
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 12)

    # 节点定义 (x, y, width, height, text)
    nodes = [
        (1, 10.5, 2.2, 1.0, '机器狗进入\n$S_1$=(0,0), $\\theta_1$'),
        (4.5, 10.5, 3.0, 1.0, '$\\theta_1 \\pm \\varepsilon$\n$\\rightarrow \\mathcal{F}_1$'),
        (8.5, 10.5, 3.0, 1.0, '鲁棒最坏最小化\n$S_2^*=\\arg\\min J_{\\mathrm{robust}}$'),
        (1, 8.0, 2.5, 1.0, 'Thales 圆:\n$L=d\\tan\\varepsilon$'),
        (4.5, 8.0, 2.5, 1.0, '选 $S_2$ 候选\n$\\mathcal{C}_{\\eta}$'),
        (8.5, 8.0, 2.5, 1.0, '移动到 $S_2$\n5 秒移动 + 5 秒检测'),
        (4.5, 5.5, 3.5, 1.2, '$\\rho_2\\leq 20\\,m$ ?\n(Jung 界 $D_2\\leq 20\\sqrt{3}\\approx 34.6$)'),
        (2, 2.5, 3.0, 1.0, '✓ 直接清除\n移动到 $c^*$ + /clear'),
        (7, 2.5, 3.0, 1.0, '✗ 补充 $S_3$\n进入问题三'),
    ]

    colors = {
        'input': '#e3f2fd',
        'compute': '#fff3e0',
        'decision': '#fff9c4',
        'output': '#c8e6c9',
    }
    color_map = [colors['input'], colors['compute'], colors['compute'],
                 colors['compute'], colors['compute'], colors['compute'],
                 colors['decision'], colors['output'], colors['output']]

    for (x, y, w, h, t), col in zip(nodes, color_map):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                     boxstyle='round,pad=0.1',
                                     facecolor=col,
                                     edgecolor='#444', linewidth=1.2))
        ax.text(x + w / 2, y + h / 2, t, ha='center', va='center',
                fontsize=9, fontweight='bold')

    # 箭头
    arrows = [
        ((2.1, 10.5), (4.5, 10.5)),
        ((6.0, 10.5), (8.5, 10.5)),
        ((2.1, 9.5), (2.1, 9.0)),
        ((5.5, 9.5), (5.5, 9.0)),
        ((8.5, 10.0), (5.5, 9.0)),
        ((5.5, 8.0), (8.5, 8.5)),  # 候选 → 移动
        ((9.75, 8.0), (7.5, 6.7)),  # 移动 → 决策
        ((4.5, 5.5), (3.5, 3.5)),  # 决策左
        ((7.5, 5.5), (8.5, 3.5)),  # 决策右
    ]
    for (x1, y1), (x2, y2) in arrows:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', lw=1.5, color='#444'))

    # 决策标签
    ax.text(3.0, 4.5, '是', ha='center', fontsize=11,
            color='#2ca02c', fontweight='bold')
    ax.text(8.0, 4.5, '否', ha='center', fontsize=11,
            color='#d62728', fontweight='bold')

    ax.set_title('第二问 · 机器狗决策流程图', fontsize=13,
                 fontweight='bold', pad=10)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, 'fig6_decision_flow.png')
    plt.savefig(out, dpi=140, bbox_inches='tight')
    plt.close()
    print(f'已写出：{out}')


# ============================================================
# 主入口
# ============================================================
if __name__ == '__main__':
    json_path = os.path.join(HERE, 'strategy_results.json')
    print('=== 第二问 v4 高级感绘图 ===')
    fig_strategies(json_path)
    fig_thales_geometry()
    fig_heatmap_L()
    fig_candidate_region()
    fig_convergence_N_scan()
    fig_decision_flow()
    print('\n6 张图全部生成。')