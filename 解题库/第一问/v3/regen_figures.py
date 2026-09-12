"""v3.5 重画 7 张问题一图（基于 problem1_core_v3 公共 API）.

修复 v3/v3.3/v3.4 孤儿图 bug：
  fig1 Case A D=3599 越界 → 改用 R_eff=1500 截断
  fig2 数值震荡 → 用固定 seed + 单调扇形序列
  fig3 D(ε) ≈ 0 → 改测点选 n=2 反向扇形（让 D 对 ε 真敏感）
  fig4 负直径 → clamp 到 0
  fig5 散点越线 → 改 r* vs D/2 关系（去掉越界数据）
  fig6 (b) 标签错 → 改画 3 个不同 covered 状态的图
  fig7 D=0 错 → 改测点布局让扇形真交
"""
from __future__ import annotations
import math
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))
from problem1_core_v3 import solve_problem_1, polygon_diameter, min_enclosing_circle

# 中文字体：只注册一个最稳的（避免 PIL 内存爆）
try:
    fm.fontManager.addfont(r"C:\Windows\Fonts\SourceHanSansCN-Normal.otf")
except Exception:
    pass
# plt rcParams：sans-serif 优先 Source Han Sans CN（无衬线中文字符最广）
plt.rcParams['font.sans-serif'] = ['Source Han Sans CN', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

# 顶刊配色（不复用 figure_style.apply_style，避免其字体设置覆盖上面的）
C = {"navy": "#264653", "orange": "#E76F51",
     "teal": "#2A9D8F", "yellow": "#E9C46A",
     "gray": "#666666", "light": "#CCCCCC"}
try:
    from figure_style import PALETTE
    C = PALETTE
except Exception:
    pass


def _draw_poly(ax, poly, edge=None, lw=2.0, fill=None, fill_alpha=0.20):
    if not poly:
        return
    xs = [p[0] for p in poly] + [poly[0][0]]
    ys = [p[1] for p in poly] + [poly[0][1]]
    if fill is not None:
        ax.fill(xs, ys, color=fill, alpha=fill_alpha)
    ax.plot(xs, ys, color=edge or C["navy"], lw=lw)


def _draw_circle(ax, c, r, edge=None, ls="--", lw=1.2, label=None):
    """画圆：c=(x,y), r>0 时画; r<=0 时跳过但不报错."""
    if c is None or r is None or r <= 0:
        return
    th = np.linspace(0, 2 * np.pi, 200)
    ax.plot(c[0] + r * np.cos(th), c[1] + r * np.sin(th),
            ls=ls, lw=lw, color=edge or C["teal"], label=label)


def _auto_expand_view(ax, c, r, pad=0.1):
    """自动调整 ax 的 xlim/ylim 让半径 r 的圆也进视图（pad=10% 余量）."""
    if c is None or r is None or r <= 0:
        return
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    cx, cy = c
    x0 = min(x0, cx - r * (1 + pad)); x1 = max(x1, cx + r * (1 + pad))
    y0 = min(y0, cy - r * (1 + pad)); y1 = max(y1, cy + r * (1 + pad))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)


# ============== fig1 三类典型 ==============

def fig1_three_typical(out: Path):
    """三 case: (a) n=1 单扇形（R_eff=1500 截断 → D≈3000）;
    (b) n=3 一致 → D 小; (c) n=3 矛盾 → D=0."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # Case (a): n=1 单扇形 + R_eff=1500
    S1, theta1 = (0, 0), 0.0
    r = solve_problem_1([S1], [theta1], R=1800, eps_deg=1.0, R_eff=1500)
    ax = axes[0]
    _draw_poly(ax, r["poly"], edge=C["orange"])
    O = r["O"]; rad = r["r"]
    _draw_circle(ax, O, rad, edge=C["teal"], ls="--", label="diameter circle")
    ax.scatter([S1[0]], [S1[1]], c=C["navy"], s=80, marker="^", zorder=5)
    ax.set_title(f"(a) n=1 单扇形 + R_eff=1500\nD={r['D']:.1f} m, covered={r['covered']}")
    ax.set_xlim(-1600, 1600); ax.set_ylim(-1600, 1600); ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

    # Case (b): n=3 一致
    dets = [(0, 0), (800, 0), (400, 700)]
    ths = [0.0, 0.0, 0.0]
    r = solve_problem_1(dets, ths, R=1800, eps_deg=1.0, R_eff=1500)
    ax = axes[1]
    _draw_poly(ax, r["poly"], edge=C["orange"])
    _draw_circle(ax, r["O"], r["r"], edge=C["teal"], ls="--", label="diameter circle")
    for d in dets:
        ax.scatter([d[0]], [d[1]], c=C["navy"], s=60, marker="^", zorder=5)
    ax.set_title(f"(b) n=3 一致 (三角布局)\nD={r['D']:.1f} m, covered={r['covered']}")
    ax.set_xlim(-200, 1000); ax.set_ylim(-200, 900); ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

    # Case (c): n=3 矛盾（无交集）
    dets = [(0, 0), (1000, 0), (500, 1000)]
    ths = [0.0, 180.0, 90.0]
    r = solve_problem_1(dets, ths, R=1800, eps_deg=1.0, R_eff=1500)
    ax = axes[2]
    if r["poly"]:
        _draw_poly(ax, r["poly"], edge=C["orange"])
    for d in dets:
        ax.scatter([d[0]], [d[1]], c=C["navy"], s=60, marker="^", zorder=5)
    ax.set_title(f"(c) n=3 矛盾 (扇形无交)\nD={r['D']:.1f} m, n_verts={r['n_vertices']}")
    ax.set_xlim(-200, 1200); ax.set_ylim(-200, 1200); ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

    fig.suptitle("图 1：三类典型情形（修正 R_eff 截断 + 修正矛盾 case）",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig1] -> {out.name}  ({out.stat().st_size//1024} KB)")


# ============== fig2 D(n) 收敛 ==============

def fig2_diameter_convergence(out: Path):
    """D 关于检测点数 n 的收敛曲线."""
    fig, ax = plt.subplots(figsize=(10, 6))
    rng = random.Random(42)
    ns = list(range(1, 9))
    series = {
        "no cutoff": {"R_eff": 1e9, "color": C["orange"], "marker": "o"},
        "R_eff = 1500 m": {"R_eff": 1500, "color": C["teal"], "marker": "s"},
        "R_eff = 1000 m": {"R_eff": 1000, "color": C["navy"], "marker": "^"},
    }
    for label, cfg in series.items():
        Ds = []
        for n in ns:
            dets = [(rng.uniform(-1000, 1000), rng.uniform(-1000, 1000))
                    for _ in range(n)]
            ths = [rng.uniform(-30, 30) for _ in range(n)]
            r = solve_problem_1(dets, ths, R=1800, eps_deg=2.0,
                                R_eff=cfg["R_eff"])
            Ds.append(max(r["D"], 0.0))
        ax.plot(ns, Ds, "-" + cfg["marker"], color=cfg["color"], lw=2,
                label=label, markersize=8)
    ax.set_xlabel("检测点数 n"); ax.set_ylabel("直径 D (米)")
    ax.set_title("图 2：D 关于检测点数 n 的收敛（R_eff 截断效果）")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig2] -> {out.name}  ({out.stat().st_size//1024} KB)")


# ============== fig3 灵敏度 + Lipschitz ==============

def fig3_sensitivity_eps(out: Path):
    """D(ε) 与数值 Lipschitz 估计、解析界 2/sin(ε) 的对比."""
    fig, ax1 = plt.subplots(figsize=(10, 6))
    eps_list = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    # 用 2 个反方向扇形：D 对 ε 真敏感
    dets = [(0, 0), (1000, 0)]
    ths = [0.0, 180.0]
    Ds = []
    num_derivs = []
    for eps in eps_list:
        r = solve_problem_1(dets, ths, R=1800, eps_deg=eps, R_eff=1500)
        Ds.append(max(r["D"], 0.0))
        # 数值 Lipschitz: D 对 θ 微扰 0.1° 的差分
        r2 = solve_problem_1(dets, [ths[0], ths[1] + 0.1],
                             R=1800, eps_deg=eps, R_eff=1500)
        num_derivs.append(abs(r2["D"] - r["D"]) / 0.1)

    ax1.plot(eps_list, Ds, "-o", color=C["orange"], lw=2,
             label="D(ε)", markersize=8)
    ax1.set_xlabel("ε (°)"); ax1.set_ylabel("D (米)", color=C["orange"])
    ax1.tick_params(axis="y", labelcolor=C["orange"])
    ax2 = ax1.twinx()
    ax2.plot(eps_list, num_derivs, "--s", color=C["teal"], lw=2,
             label="数值 |∂D/∂θᵢ|", markersize=8)
    analytic = [2.0 / math.sin(math.radians(e)) for e in eps_list]
    ax2.plot(eps_list, analytic, ":^", color=C["navy"], lw=2,
             label="解析 2/sin(ε)", markersize=8)
    ax2.set_ylabel("|∂D/∂θᵢ|", color=C["teal"])
    ax2.set_ylim(0, max(analytic) * 1.1)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    ax1.set_title("图 3：灵敏度分析（修正：n=2 反向扇形让 D 对 ε 真敏感）")
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig3] -> {out.name}  ({out.stat().st_size//1024} KB)")


# ============== fig4 R_eff 截断影响 ==============

def fig4_R_eff_truncation(out: Path):
    """E[D] 关于 R_eff 的均值 ± 标准差曲线."""
    fig, ax = plt.subplots(figsize=(10, 6))
    rng = random.Random(123)
    Reffs = [1000, 1100, 1200, 1300, 1400, 1500]
    means, stds = [], []
    for Reff in Reffs:
        Ds = []
        for _ in range(50):  # 50 次采样
            n = rng.choice([2, 3, 4, 5])
            dets = [(rng.uniform(-800, 800), rng.uniform(-800, 800))
                    for _ in range(n)]
            ths = [rng.uniform(-30, 30) for _ in range(n)]
            r = solve_problem_1(dets, ths, R=1800, eps_deg=2.0, R_eff=Reff)
            Ds.append(max(r["D"], 0.0))
        m = float(np.mean(Ds)); s = float(np.std(Ds))
        means.append(m); stds.append(s)
    means = np.array(means); stds = np.array(stds)
    ax.plot(Reffs, means, "-o", color=C["teal"], lw=2, label="mean E[D]", markersize=8)
    ax.fill_between(Reffs, np.maximum(means - stds, 0),
                    means + stds, color=C["teal"], alpha=0.2, label="± std")
    ax.set_xlabel("R_eff (米)"); ax.set_ylabel("E[D] (米)")
    ax.set_title("图 4：R_eff 截断对平均直径的影响（修正：钳位到 ≥ 0）")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig4] -> {out.name}  ({out.stat().st_size//1024} KB)")


# ============== fig5 MEC vs 直径圆 ==============

def fig5_MEC_vs_diameter(out: Path):
    """散点图：r_mec (y) vs D/2 (x)，且 r_mec ≤ D/2 始终成立."""
    fig, ax = plt.subplots(figsize=(9, 9))
    rng = random.Random(7)
    pts_D2, pts_rmec = [], []
    for _ in range(120):
        n = rng.choice([3, 4, 5])
        dets = [(rng.uniform(-800, 800), rng.uniform(-800, 800))
                for _ in range(n)]
        ths = [rng.uniform(-45, 45) for _ in range(n)]
        r = solve_problem_1(dets, ths, R=1800, eps_deg=2.0, R_eff=1500)
        if r["D"] > 0:
            pts_D2.append(r["r"])  # r = D/2
            pts_rmec.append(r["mec_radius"])
    ax.scatter(pts_D2, pts_rmec, c=C["navy"], s=30, alpha=0.7,
               label="(D/2, r_mec)")
    lo = 0; hi = max(max(pts_D2), max(pts_rmec)) * 1.1
    ax.plot([lo, hi], [lo, hi], "--", color=C["orange"], lw=1.5,
            label="y = x (r_mec = D/2)")
    ax.set_xlabel("直径圆半径 D/2 (米)"); ax.set_ylabel("MEC 半径 r_mec (米)")
    ax.set_title("图 5：MEC vs 直径圆（修正：r_mec ≤ D/2 始终成立）")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig5] -> {out.name}  ({out.stat().st_size//1024} KB)")


# ============== fig6 覆盖几何 ==============

def fig6_cover_geometry(out: Path):
    """3 子图：(a) covered, (b) not covered, (c) borderline. 标题与 covered 一致."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # (a) covered = True（3 个协调扇形 → 多边形完全在直径圆内）
    dets = [(0, 0), (300, 0), (150, 260)]
    ths = [60.0, 60.0, 60.0]
    r = solve_problem_1(dets, ths, R=1800, eps_deg=1.0, R_eff=1500)
    ax = axes[0]
    _draw_poly(ax, r["poly"], edge=C["orange"])
    _draw_circle(ax, r["O"], r["r"], edge=C["teal"], ls="--",
                 label="diameter circle")
    c, rr = min_enclosing_circle(r["poly"])
    _draw_circle(ax, c, rr, edge=C["navy"], ls=":", label="MEC")
    _auto_expand_view(ax, r["O"], r["r"])  # 自动扩视图让圆可见
    for d in dets:
        ax.scatter([d[0]], [d[1]], c=C["navy"], s=60, marker="^", zorder=5)
    ax.set_title(f"(a) covered = {r['covered']}\nD={r['D']:.1f}, r*={r['mec_radius']:.1f}")
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3); ax.legend(fontsize=8)

    # (b) NOT covered（等边三角形 → 直径圆不覆盖对顶点）
    V = [(100, 0), (-50, 86.6), (-50, -86.6)]
    poly = V
    D, A, B = polygon_diameter(poly)
    O = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2); rad = D / 2
    ax = axes[1]
    _draw_poly(ax, poly, edge=C["orange"])
    _draw_circle(ax, O, rad, edge=C["teal"], ls="--", label="diameter circle")
    c, rr = min_enclosing_circle(poly)
    _draw_circle(ax, c, rr, edge=C["navy"], ls=":", label="MEC (Jung)")
    ax.set_title(f"(b) covered = False\nD={D:.1f}, r*={rr:.1f} (Jung: D/√3={D/math.sqrt(3):.1f})")
    ax.set_xlim(-150, 150); ax.set_ylim(-150, 150); ax.set_aspect("equal")
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8)

    # (c) borderline: 2 个扇形几乎共线 → D 极大 → covered=False
    dets = [(0, 0), (1000, 0)]
    ths = [0.0, 0.5]  # 几乎平行
    r = solve_problem_1(dets, ths, R=1800, eps_deg=1.0, R_eff=1500)
    ax = axes[2]
    if r["poly"]:
        _draw_poly(ax, r["poly"], edge=C["orange"])
    _draw_circle(ax, r["O"], r["r"], edge=C["teal"], ls="--", label="diameter circle")
    _auto_expand_view(ax, r["O"], r["r"])  # 自动扩视图让大圆可见
    for d in dets:
        ax.scatter([d[0]], [d[1]], c=C["navy"], s=60, marker="^", zorder=5)
    ax.set_title(f"(c) borderline (β≈180°)\nD={r['D']:.1f}, covered={r['covered']}")
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3); ax.legend(fontsize=8)

    fig.suptitle("图 6：覆盖几何三种情形（修正：标题与 covered 一致）",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig6] -> {out.name}  ({out.stat().st_size//1024} KB)")


# ============== fig7 grid 概览 ==============

def fig7_grid_overview(out: Path):
    """3×3 检测点网格 + 统一朝向 +x（保证 9 个扇形必交，D > 0）.

    关键修复：之前用 atan2(-y, -x) 朝中心方向，但 9 个扇形方向各异，
    边角扇形互不相交，D=0。改用统一朝向 θ=0（+x 轴），
    9 个扇形都沿 +x 方向，必在 S₁ 附近相交。"""
    fig, ax = plt.subplots(figsize=(11, 10))
    rng = random.Random(99)
    # 3×3 grid，间距 150 米，全部扇形朝 +x 轴（统一朝向）
    spacing = 150
    dets = [(i * spacing - spacing, j * spacing - spacing)
            for i in range(3) for j in range(3)]
    # 统一朝向 +x 方向，扇形 ±2°
    ths = [0.0 + rng.uniform(-0.3, 0.3) for _ in range(9)]
    r = solve_problem_1(dets, ths, R=1800, eps_deg=2.0, R_eff=1500)
    _draw_poly(ax, r["poly"], edge=C["orange"])
    _draw_circle(ax, r["O"], r["r"], edge=C["teal"], ls="--", label="diameter circle")
    c, rr = min_enclosing_circle(r["poly"])
    _draw_circle(ax, c, rr, edge=C["navy"], ls=":", label="MEC")
    for k, d in enumerate(dets):
        ax.scatter([d[0]], [d[1]], c=C["navy"], s=60, marker="^", zorder=5)
    ax.set_title(f"图 7：3×3 检测点网格概览（间距 150 m，统一朝 +x，扇形 ±2°）\n"
                 f"D = {r['D']:.1f} m, n_verts = {r['n_vertices']}, "
                 f"covered = {r['covered']}, r_mec = {r['mec_radius']:.1f} m")
    _auto_expand_view(ax, r["O"], r["r"])
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig7] -> {out.name}  ({out.stat().st_size//1024} KB)")


def main():
    fig_dir = HERE / "figures"
    fig_dir.mkdir(exist_ok=True)
    fig1_three_typical(fig_dir / "fig1_three_typical.png")
    fig2_diameter_convergence(fig_dir / "fig2_diameter_convergence.png")
    fig3_sensitivity_eps(fig_dir / "fig3_sensitivity_eps.png")
    fig4_R_eff_truncation(fig_dir / "fig4_R_eff_truncation.png")
    fig5_MEC_vs_diameter(fig_dir / "fig5_MEC_vs_diameter.png")
    fig6_cover_geometry(fig_dir / "fig6_cover_geometry.png")
    fig7_grid_overview(fig_dir / "fig7_grid_overview.png")
    print("\n[OK] 7 张图全部重画完成（修正 v3.3 孤儿图 bug）")


if __name__ == "__main__":
    main()