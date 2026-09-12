# 临时：单跑 fig3
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import problem1_v4 as p1

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(HERE, 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

COL_POLY_EDGE = '#1f4e79'
COL_DIAM_CIRC = '#d62728'

eps_grid = [0.1, 0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]
R_eff = 1500.0
D_vals = []
bound_vals = []
for eps in eps_grid:
    res = p1.solve_problem_1([(0, 0)], [0.0], eps_deg=eps,
                             R_eff=R_eff, R_target=1800.0, N_disk=64)
    D_vals.append(res['D'])
    bound_vals.append(2 * R_eff * math.tan(math.radians(eps)))

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.plot(eps_grid, D_vals, 'o-', label='单扇形 $D$（实测）',
        color=COL_POLY_EDGE, linewidth=2.2, markersize=8)
ax.plot(eps_grid, bound_vals, 's--',
        label=r'解析上界 $2 R_{\mathrm{eff}} \tan \varepsilon$',
        color=COL_DIAM_CIRC, linewidth=1.6, markersize=7)
ax.set_yscale('log')
ax.set_xlabel(r'示向度误差 $\varepsilon$ (°)', fontsize=11)
ax.set_ylabel(r'直径 $D$ (m，对数坐标)', fontsize=11)
ax.set_title(r'单扇形定位多边形直径对 $\varepsilon$ 的敏感度', fontsize=12)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, which='both')
plt.tight_layout()
out = os.path.join(FIG_DIR, 'fig3_sensitivity_eps.png')
plt.savefig(out, dpi=140, bbox_inches='tight')
plt.close()
print(f'已写出：{out}')
print(f'D 实测值：{[f"{v:.1f}" for v in D_vals]}')
print(f'解析上界：{[f"{v:.1f}" for v in bound_vals]}')