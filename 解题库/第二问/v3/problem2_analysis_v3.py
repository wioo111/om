"""问题2 v3 算例与可视化.

输出：
  - figures/fig1_F1_first_detection.png
  - figures/fig2_beta_isobands.png
  - figures/fig3_J_robust_heatmap.png
  - figures/fig4_three_categories_A0A1A2.png
  - figures/fig5_convergence_N_scan.png
  - problem2_v3_results.json  （合并 5 张图数据）
"""
from __future__ import annotations
import json
import math
import os
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))

from problem2_core_v3 import (
    classify_G, build_P2, sample_F1,
    J_robust, J_proxy, grid_search_J_robust, candidate_region,
)


# ============== 算例 1：F₁ 几何 ==============

def plot_F1_first_detection(S1=(0, 0), theta1=0.0):
    """画 F₁：以 S₁ 为顶点的 2° 窄角扇形被 Ω（半径 1800）和 B(S₁,1500)\B(S₁,5) 截出."""
    fig, ax = plt.subplots(figsize=(8, 8))
    # Ω
    theta_c = np.linspace(0, 2 * np.pi, 200)
    ax.plot(1800 * np.cos(theta_c), 1800 * np.sin(theta_c), "k--", label="Ω (R=1800)")
    # B(S₁, 1500) 和 B(S₁, 5)
    ax.plot(1500 * np.cos(theta_c) + S1[0], 1500 * np.sin(theta_c) + S1[1],
            "b--", alpha=0.5, label="B(S₁,1500)")
    ax.plot(5 * np.cos(theta_c) + S1[0], 5 * np.sin(theta_c) + S1[1],
            "r--", alpha=0.5, label="B(S₁,5) 死区")
    # F₁ 采样
    Gs = sample_F1(S1, theta1, N_d=60, N_w=21)
    if Gs:
        arr = np.array(Gs)
        ax.scatter(arr[:, 0], arr[:, 1], s=1, c="green", label="F₁ 采样 (N=1260)")
    # 方向箭头
    ax.annotate("", xy=(1500 * math.cos(math.radians(theta1)),
                        1500 * math.sin(math.radians(theta1))),
                xytext=S1,
                arrowprops=dict(arrowstyle="->", color="orange", lw=2))
    ax.text(S1[0] + 100, S1[1] + 100, f"S₁={S1}\nθ₁={theta1}°", fontsize=10)
    ax.set_xlim(-1850, 1850); ax.set_ylim(-1850, 1850)
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("图 1：第一次检测后源候选区域 F₁（窄角扇形被 Ω 与 B(S₁,1500)\\B(S₁,5) 截出）")
    out = HERE / "figures" / "fig1_F1_first_detection.png"
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return str(out)


# ============== 算例 2：β 等值带 ==============

def plot_beta_isobands(S1=(0, 0), theta1=0.0):
    """画 β 等值带 + 候选区域 C_all / C_robust 边界."""
    fig, ax = plt.subplots(figsize=(9, 9))
    R_eff, R_Omega = 1500.0, 1800.0
    grid_step = 50
    half = int(R_eff / grid_step) + 1
    betas = {}
    for i in range(-half, half + 1):
        for j in range(-half, half + 1):
            x, y = i * grid_step, j * grid_step
            if x * x + y * y > R_Omega * R_Omega: continue
            if x * x + y * y > R_eff * R_eff: continue
            # 假设 G 沿 θ₁ 方向 1000 米处
            G = (1000 * math.cos(math.radians(theta1)),
                 1000 * math.sin(math.radians(theta1)))
            v1 = (G[0] - S1[0], G[1] - S1[1])
            v2 = (G[0] - x, G[1] - y)
            n1 = math.hypot(*v1) + 1e-12
            n2 = math.hypot(*v2) + 1e-12
            cos_b = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
            cos_b = max(-1.0, min(1.0, cos_b))
            beta_deg = math.degrees(math.acos(cos_b))
            betas[(x, y)] = beta_deg
    if betas:
        xs = [k[0] for k in betas]; ys = [k[1] for k in betas]
        cs = [betas[k] for k in betas]
        sc = ax.scatter(xs, ys, c=cs, cmap="viridis_r", s=4)
        plt.colorbar(sc, ax=ax, label="β(°)")
    ax.plot(1800 * np.cos(np.linspace(0, 2 * np.pi, 200)),
            1800 * np.sin(np.linspace(0, 2 * np.pi, 200)), "k--", lw=1)
    ax.set_xlim(-1850, 1850); ax.set_ylim(-1850, 1850)
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
    ax.set_title(f"图 2：β 等值带（假设 G 沿 θ₁={theta1}° 方向 1000 米处）")
    out = HERE / "figures" / "fig2_beta_isobands.png"
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return str(out)


# ============== 算例 3：J_robust 热图 ==============

def plot_J_robust_heatmap(S1=(0, 0), theta1=0.0):
    """画 J_robust 热图 + 最优点 + C_η 边界."""
    fig, ax = plt.subplots(figsize=(10, 9))
    R_eff, R_Omega = 1500.0, 1800.0
    grid_step = 200  # 粗网格出图快
    half = int(R_eff / grid_step) + 1
    pts = []
    for i in range(-half, half + 1):
        for j in range(-half, half + 1):
            x, y = i * grid_step, j * grid_step
            if x * x + y * y > R_Omega * R_Omega: continue
            if x * x + y * y > R_eff * R_eff: continue
            if math.hypot(x - S1[0], y - S1[1]) < 30: continue  # L_eng
            pts.append((x, y))

    # 采样 + 精算（小规模）
    Gs = sample_F1(S1, theta1, N_d=20, N_w=11)
    Jvals = {}
    for S2 in pts:
        r = J_robust(S2, S1, theta1, Gs)
        Jvals[S2] = r["J_robust"]
    if Jvals:
        xs = [k[0] for k in Jvals]; ys = [k[1] for k in Jvals]
        cs = [Jvals[k] for k in Jvals]
        sc = ax.scatter(xs, ys, c=cs, cmap="hot_r", s=30)
        plt.colorbar(sc, ax=ax, label="J_robust (米)")
        # 标最优点
        s2_star = min(Jvals, key=Jvals.get)
        ax.scatter([s2_star[0]], [s2_star[1]], c="blue", s=120, marker="*",
                   label=f"S₂* = {s2_star}, J* = {Jvals[s2_star]:.1f}")
        # C_η=0.2 边界
        J_star = Jvals[s2_star]
        thresh = 1.2 * J_star
        eta_pts = [k for k, v in Jvals.items() if v <= thresh]
        if eta_pts:
            arr = np.array(eta_pts)
            ax.scatter(arr[:, 0], arr[:, 1], s=60, facecolors="none",
                       edgecolors="cyan", linewidths=1.5,
                       label=f"C_{{η=0.2}} (|C|={len(eta_pts)})")
    ax.plot(1800 * np.cos(np.linspace(0, 2 * np.pi, 200)),
            1800 * np.sin(np.linspace(0, 2 * np.pi, 200)), "k--", lw=1)
    ax.set_xlim(-1850, 1850); ax.set_ylim(-1850, 1850)
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("图 3：J_robust 热图 + 最优点 S₂* + 候选区域 C_η=0.2")
    out = HERE / "figures" / "fig3_J_robust_heatmap.png"
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return str(out), Jvals


# ============== 算例 4：A₀/A₁/A₂ 三区域示例 ==============

def plot_three_categories(S1=(0, 0), theta1=0.0, S2=(800, 800)):
    """对固定 S₂，画 F₁ 中 G 按 ‖S₂ − G‖ 分类的三类区域."""
    fig, ax = plt.subplots(figsize=(8, 8))
    Gs = sample_F1(S1, theta1, N_d=40, N_w=11)
    cats = [classify_G(S2, G) for G in Gs]
    color_map = {"A0": "green", "A1": "blue", "A2": "red"}
    label_map = {"A0": "A₀ (≤5 m，可光学清除)",
                 "A1": "A₁ ((5, 1500] m，可精算)",
                 "A2": "A₂ (>1500 m，盲区)"}
    shown = set()
    for G, cat in zip(Gs, cats):
        ax.scatter(G[0], G[1], c=color_map[cat], s=8,
                   label=label_map[cat] if cat not in shown else None)
        shown.add(cat)
    ax.scatter([S1[0]], [S1[1]], c="black", s=120, marker="^", label="S₁")
    ax.scatter([S2[0]], [S2[1]], c="purple", s=120, marker="s", label=f"S₂={S2}")
    # B(S₂, 5) 与 B(S₂, 1500)
    theta_c = np.linspace(0, 2 * np.pi, 200)
    ax.plot(5 * np.cos(theta_c) + S2[0], 5 * np.sin(theta_c) + S2[1],
            "g-", lw=1.5, alpha=0.6)
    ax.plot(1500 * np.cos(theta_c) + S2[0], 1500 * np.sin(theta_c) + S2[1],
            "r-", lw=1.5, alpha=0.6)
    ax.set_xlim(-1850, 1850); ax.set_ylim(-1850, 1850)
    ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("图 4：固定 S₂ 时 F₁ 中 G 的三类划分 A₀ / A₁ / A₂")
    out = HERE / "figures" / "fig4_three_categories_A0A1A2.png"
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return str(out)


# ============== 算例 5：N 扫描收敛 ==============

def plot_convergence_N_scan(S1=(0, 0), theta1=0.0,
                            S2=(800, 0)):
    """画 J* 关于 N_d 的收敛曲线，证明 N_d=60 已稳定."""
    fig, ax = plt.subplots(figsize=(9, 6))
    J_star_list = []
    N_list = [10, 20, 40, 60, 90]
    for N_d in N_list:
        Gs = sample_F1(S1, theta1, N_d=N_d, N_w=11)
        r = J_robust(S2, S1, theta1, Gs)
        J_star_list.append(r["J_robust"])
    ax.plot(N_list, J_star_list, "o-", lw=2, color="navy")
    ax.axhline(J_star_list[-1], color="red", ls="--", alpha=0.5,
               label=f"N=90 渐近线 = {J_star_list[-1]:.1f}")
    ax.set_xlabel("N_d（沿距离的采样数）"); ax.set_ylabel("J_robust (米)")
    ax.set_title(f"图 5：J_robust 关于 N_d 的收敛（S₂={S2}）")
    ax.grid(True, alpha=0.3); ax.legend()
    out = HERE / "figures" / "fig5_convergence_N_scan.png"
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return str(out), N_list, J_star_list


def main():
    out = {}
    print("[算例 1] F₁ 几何...")
    out["fig1"] = plot_F1_first_detection()
    print("[算例 2] β 等值带...")
    out["fig2"] = plot_beta_isobands()
    print("[算例 3] J_robust 热图...")
    fig3, Jvals = plot_J_robust_heatmap()
    out["fig3"] = fig3
    out["J_robust_values"] = {str(k): v for k, v in Jvals.items()}
    print("[算例 4] 三区域示例...")
    out["fig4"] = plot_three_categories()
    print("[算例 5] N 扫描收敛...")
    fig5, N_list, J_list = plot_convergence_N_scan()
    out["fig5"] = fig5
    out["convergence"] = {"N_d": N_list, "J_robust": J_list}

    json_path = HERE / "problem2_v3_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {json_path}")
    return out


if __name__ == "__main__":
    main()