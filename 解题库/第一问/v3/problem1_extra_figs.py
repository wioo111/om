"""v3.4 新增算例图（顶刊配图风格）。"""
from __future__ import annotations
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))
from figure_style import (apply_style, PALETTE, style_axes, legend,
                          reserve_legend_room)
from problem1_core_v3 import (solve_problem_1, polygon_diameter,
                               diameter_circle_covers, min_enclosing_circle)

apply_style()
C = PALETTE


def _draw_poly(ax, poly, edge=None, lw=2.0, fill=None, fill_alpha=0.20):
    if not poly:
        return
    xs = [p[0] for p in poly] + [poly[0][0]]
    ys = [p[1] for p in poly] + [poly[0][1]]
    if fill is not None:
        ax.fill(xs, ys, color=fill, alpha=fill_alpha, zorder=2)
    ax.plot(xs, ys, color=(edge or C["ink"]), linewidth=lw, zorder=3)


def _draw_circle(ax, c, r, color, ls="--", lw=1.4, label=None, zorder=2):
    th = np.linspace(0.0, 2.0 * math.pi, 256)
    ax.plot(c[0] + r * np.cos(th), c[1] + r * np.sin(th),
            color=color, linestyle=ls, linewidth=lw, label=label, zorder=zorder)


def _set_equal(ax):
    ax.set_aspect("equal", "box")


def _diameter_mark(ax, A, B):
    ax.plot([A[0], B[0]], [A[1], B[1]],
            color=C["orange"], linewidth=2.0, zorder=5)
    ax.scatter([A[0], B[0]], [A[1], B[1]],
               s=26, c=C["orange"], edgecolors="white",
               linewidths=1.0, zorder=6)


def fig_two_detectors():
    """图 8：两检测点窄长四边形示例（题面附录 2 图 2 的标准情形）。"""
    fig, ax = plt.subplots(figsize=(8, 6))
    dets = [(0, 0), (500, 0)]
    thetas = [90.0, 92.0]
    r = solve_problem_1(dets, thetas, R=1800.0, eps_deg=1.0, R_eff=1500.0)
    for (x, y), th in zip(dets, thetas):
        ax.add_patch(mpatches.Wedge(
            (x, y), 1800.0, th - 1.0, th + 1.0,
            facecolor=C["teal"], alpha=0.16,
            edgecolor=C["teal"], linestyle="--", linewidth=0.9, zorder=1))
        ax.scatter([x], [y], s=46, c=C["ink"],
                   edgecolors="white", linewidths=1.2, zorder=6)
        ax.annotate("$S_{%d}$" % (dets.index((x, y)) + 1), (x, y),
                    xytext=(8, 8), textcoords="offset points",
                    color=C["muted"], fontsize=10)
    _draw_poly(ax, r["poly"], edge=C["orange"], lw=2.0,
               fill=C["orange"], fill_alpha=0.20)
    _diameter_mark(ax, r["A"], r["B"])
    _draw_circle(ax, r["O"], r["r"], C["navy"], ls="--", lw=1.5,
                 label="Diameter circle  ($r = D/2$)")
    _draw_circle(ax, r["mec_center"], r["mec_radius"], C["teal"],
                 ls=":", lw=1.4,
                 label="MEC  ($r^*$ = %.2f)" % r["mec_radius"])
    ax.scatter([r["O"][0]], [r["O"][1]], marker="+", s=120,
               c=C["orange"], linewidths=2, zorder=6)
    style_axes(ax,
               title="Two-detector narrow quadrilateral  ($D = %.2f$ m, covered = %s)"
                     % (r["D"], r["covered"]),
               xlabel="x (m)", ylabel="y (m)")
    _set_equal(ax)
    legend(ax, place="right")
    reserve_legend_room(fig, place="right", right=0.78)
    fig.savefig(HERE / "figures" / "fig8_two_detectors.png", dpi=180)
    plt.close(fig)
    print("done fig8")


def fig_equilateral_counterexample():
    """图 9：等边三角形反例（Jung 紧性）。"""
    fig, ax = plt.subplots(figsize=(8, 7))
    D_eq = 100.0
    tri = [(0.0, 0.0), (D_eq, 0.0),
           (D_eq / 2, D_eq * math.sqrt(3) / 2)]
    D, A, B = polygon_diameter(tri)
    O = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
    cov, off = diameter_circle_covers(tri, A, B)
    mec_cen, mec_r = min_enclosing_circle(tri)

    _draw_poly(ax, tri, edge=C["teal"], lw=2.0,
               fill=C["teal"], fill_alpha=0.18)
    for i, v in enumerate(tri):
        ax.scatter([v[0]], [v[1]], s=60, c=C["ink"],
                   edgecolors="white", linewidths=1.2, zorder=6)
        ax.annotate("$V_{%d}$" % (i + 1), v, xytext=(8, 8),
                    textcoords="offset points", fontsize=11, color=C["muted"])
    _diameter_mark(ax, A, B)
    _draw_circle(ax, O, D / 2, C["navy"], ls="--", lw=1.6,
                 label="Diameter circle  ($r = D/2 = %.2f$)" % (D / 2))
    _draw_circle(ax, mec_cen, mec_r, C["teal"], ls=":", lw=1.4,
                 label="MEC  ($r^*$ = %.2f)" % mec_r)
    apex = tri[2]
    apex_to_O = math.hypot(apex[0] - O[0], apex[1] - O[1])
    ax.annotate("$V_3$ outside the circle\n$|OV_3| = %.2f > %.2f$"
                % (apex_to_O, D / 2),
                apex, xytext=(-95, -65), textcoords="offset points",
                fontsize=10, color=C["orange"], weight="bold",
                arrowprops=dict(arrowstyle="->", color=C["orange"], lw=1.6))
    style_axes(ax,
               title="Equilateral triangle counterexample  "
                     "(Jung tightness, max offset = %.2f)" % off,
               xlabel="x (m)", ylabel="y (m)")
    _set_equal(ax)
    legend(ax, place="right")
    reserve_legend_room(fig, place="right", right=0.78)
    fig.savefig(HERE / "figures" / "fig9_equilateral_counterexample.png", dpi=180)
    plt.close(fig)
    print("done fig9")


if __name__ == "__main__":
    fig_two_detectors()
    fig_equilateral_counterexample()