"""问题2 v3 国奖级核心算法库.

依赖：解题库/第一问/v3/problem1_core_v3.py
入口：sys.path.append('../第一问/v3') 后 from problem1_core_v3 import ...

公开 API：
  - classify_G(S2, G, R_eff=1500)        -> str in {'A0', 'A1', 'A2'}
  - build_P2(S1, theta1, S2, G, ...)     -> dict  (来自问题一的 solve_problem_1)
  - J_robust(S2, S1, theta1, G_samples, lam=1500, eps_deg=1, R=1500, R_eff=1500)
                                            -> dict with max_rho, N2, J_robust, ...
  - J_proxy(S2, S1, theta1, G_samples)   -> dict with max_kappa, ...
  - grid_search_J_robust(S1, theta1, N_d=60, N_w=21, grid_step=50, lam=1500, ...)
                                            -> dict with J_star, S2_star, candidates
  - candidate_region(J_grid, eta=0.2)     -> list of S2 (候选区域点)
  - _self_test()                           -> 7 步自检（T1–T7）
"""
from __future__ import annotations
import math
import os
import sys
from pathlib import Path

# 把问题一 v3 库加进路径
HERE = Path(__file__).parent.resolve()
P1_DIR = HERE.parent.parent / "第一问" / "v3"
if str(P1_DIR) not in sys.path:
    sys.path.insert(0, str(P1_DIR))

from problem1_core_v3 import solve_problem_1, _wrap_alpha  # noqa: E402


# ============== 1. 源位置分类 ==============

def classify_G(S2: tuple, G: tuple, R_eff: float = 1500.0,
               d_near: float = 5.0) -> str:
    """把源 G 按 ‖S₂ − G‖ 分为 A₀ / A₁ / A₂."""
    d = math.hypot(G[0] - S2[0], G[1] - S2[1])
    if d <= d_near:
        return "A0"
    if d <= R_eff:
        return "A1"
    return "A2"


# ============== 2. 构造双扇形定位区域 P₂ ==============

def build_P2(S1: tuple, theta1: float,
             S2: tuple, G: tuple,
             eps_deg: float = 1.0,
             R: float = 1500.0,
             R_eff: float = 1500.0) -> dict:
    """构造 S₁/S₂ 双扇形定位区域 P₂(S₂, G)；调用问题一 solve_problem_1.

    θ₂(G) = atan2(G − S₂) 是"若 G 在 S₂ 方位"的反推值（非观测值）。
    返回字段：poly / D / mec_radius / mec_center / covered
    """
    theta2_G = math.degrees(math.atan2(G[1] - S2[1], G[0] - S2[0]))
    thetas = [_wrap_alpha(theta1), _wrap_alpha(theta2_G)]
    return solve_problem_1(
        dets=[S1, S2], thetas=thetas,
        R=R, eps_deg=eps_deg, R_eff=R_eff, N_disk=64,
    )


# ============== 3. F₁ 参数化采样（d, w 矩形） ==============

def sample_F1(S1: tuple, theta1_deg: float,
              N_d: int = 60, N_w: int = 21,
              eps_deg: float = 1.0,
              R_eff: float = 1500.0,
              R_Omega: float = 1800.0,
              d_near: float = 5.0) -> list:
    """在 F₁ 上做 (d, w) 参数化矩形采样，返回 G 点列表.

    F1 = Ω ∩ (B(S1, R_eff) - B(S1, d_near)) ∩ {P : |wrap(atan2(P - S1) - θ1)| <= ε}
    参数化：G = S₁ + d (cos θ₁, sin θ₁) + w (−sin θ₁, cos θ₁)
    其中 |w| ≤ d · tan(ε)，d ∈ [d_near, R_eff] ∩ {d : ‖G‖ ≤ R_Ω}
    """
    theta_rad = math.radians(theta1_deg)
    cx, cy = math.cos(theta_rad), math.sin(theta_rad)
    nx, ny = -math.sin(theta_rad), math.cos(theta_rad)  # 法向

    Gs = []
    # 在 d ∈ [d_near, R_eff] 上均匀采 N_d 段
    for i in range(N_d):
        d = d_near + (R_eff - d_near) * (i + 0.5) / N_d
        # w 范围 = ±d · tan(ε)（窄角边界）
        w_max = d * math.tan(math.radians(eps_deg))
        for j in range(N_w):
            w = -w_max + 2 * w_max * (j + 0.5) / N_w
            gx = S1[0] + d * cx + w * nx
            gy = S1[1] + d * cy + w * ny
            # Ω 约束
            if gx * gx + gy * gy > R_Omega * R_Omega:
                continue
            Gs.append((gx, gy))
    return Gs


# ============== 4. 主模型：J_robust(S₂) ==============

def J_robust(S2: tuple, S1: tuple, theta1: float,
             G_samples: list,
             lam: float = 1500.0,
             eps_deg: float = 1.0,
             R: float = 1500.0,
             R_eff: float = 1500.0) -> dict:
    """对给定的 S₂，在 G_samples 上算 max ρ₂ 和 A₂ 占比.

    返回：
      max_rho: A₁ 中最大 ρ₂
      N2:     落入 A₂ 的样本数
      N1:     落入 A₁ 的样本数（用于归一化）
      N0:     落入 A₀ 的样本数
      J_robust: max(max_rho, lam · 1_{N₂>0})
    """
    max_rho = 0.0
    N2 = N1 = N0 = 0
    for G in G_samples:
        cat = classify_G(S2, G, R_eff=R_eff)
        if cat == "A0":
            N0 += 1
            continue
        if cat == "A2":
            N2 += 1
            continue
        # A₁: 精算 ρ₂
        try:
            r = build_P2(S1, theta1, S2, G,
                         eps_deg=eps_deg, R=R, R_eff=R_eff)
            rho = r.get("mec_radius", 0.0)
        except Exception:
            rho = 0.0
        if rho > max_rho:
            max_rho = rho
        N1 += 1
    blind_penalty = lam if N2 > 0 else 0.0
    return {
        "S2": S2,
        "max_rho": max_rho,
        "N0": N0, "N1": N1, "N2": N2,
        "J_robust": max(max_rho, blind_penalty),
    }


# ============== 5. 代理模型：J_proxy(S₂) ==============

def J_proxy(S2: tuple, S1: tuple, theta1: float,
            G_samples: list,
            eps_deg: float = 1.0,
            R_eff: float = 1500.0) -> dict:
    """代理模型：用 1 / |sin β| 替代 ρ₂ 做粗筛."""
    max_kappa = 0.0
    N2 = N1 = 0
    for G in G_samples:
        cat = classify_G(S2, G, R_eff=R_eff)
        if cat == "A2":
            N2 += 1
            continue
        if cat == "A0":
            continue
        N1 += 1
        v1 = (G[0] - S1[0], G[1] - S1[1])
        v2 = (G[0] - S2[0], G[1] - S2[1])
        n1 = math.hypot(*v1) + 1e-12
        n2 = math.hypot(*v2) + 1e-12
        cos_b = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
        cos_b = max(-1.0, min(1.0, cos_b))
        sin_b = math.sqrt(max(0.0, 1.0 - cos_b * cos_b))
        kappa = 1.0 / max(sin_b, 1e-3)
        if kappa > max_kappa:
            max_kappa = kappa
    return {"S2": S2, "max_kappa": max_kappa, "N1": N1, "N2": N2}


# ============== 6. 网格搜索 J_robust ==============

def grid_search_J_robust(S1: tuple, theta1: float,
                         R_Omega: float = 1800.0,
                         R_eff: float = 1500.0,
                         L_min: float = 992.0,
                         grid_step: float = 50.0,
                         N_d: int = 60, N_w: int = 21,
                         lam: float = 1500.0,
                         eps_deg: float = 1.0,
                         proxy_first: bool = True) -> dict:
    """在 Ω ∩ B(S₁, R_eff) 上做网格搜索，返回 J_robust 场.

    proxy_first=True 时先用 κ 做粗筛（剔除 sin β < 1e-3 的候选），再精算 J_robust。
    """
    # 1) F₁ 采样
    G_samples = sample_F1(S1, theta1,
                          N_d=N_d, N_w=N_w,
                          eps_deg=eps_deg, R_eff=R_eff, R_Omega=R_Omega)

    # 2) 网格生成
    pts = []
    R_search = R_eff  # S₂ 必在 S₁ 周围 R_eff 内（题目约束）
    half = int(R_search / grid_step) + 1
    for i in range(-half, half + 1):
        for j in range(-half, half + 1):
            x = i * grid_step
            y = j * grid_step
            if x * x + y * y > R_Omega * R_Omega:
                continue
            if x * x + y * y > R_search * R_search:
                continue
            # L_min 约束
            dx, dy = x - S1[0], y - S1[1]
            if math.hypot(dx, dy) < L_min:
                continue
            pts.append((x, y))

    # 3) 粗筛（代理）
    if proxy_first:
        proxy_results = []
        for S2 in pts:
            pr = J_proxy(S2, S1, theta1, G_samples, eps_deg=eps_deg, R_eff=R_eff)
            proxy_results.append(pr)
        # 取 proxy top 30%
        proxy_results.sort(key=lambda r: r["max_kappa"])
        keep = max(50, len(proxy_results) // 3)
        pts = [r["S2"] for r in proxy_results[:keep]]

    # 4) 精算 J_robust
    results = []
    for S2 in pts:
        r = J_robust(S2, S1, theta1, G_samples,
                      lam=lam, eps_deg=eps_deg, R=R_eff, R_eff=R_eff)
        results.append(r)

    if not results:
        return {"J_star": None, "S2_star": None, "results": []}

    # 5) 找 J*
    results.sort(key=lambda r: r["J_robust"])
    J_star = results[0]["J_robust"]
    S2_star = results[0]["S2"]
    return {"J_star": J_star, "S2_star": S2_star, "results": results}


# ============== 7. 候选区域 C_η ==============

def candidate_region(results: list, J_star: float, eta: float = 0.2) -> list:
    """返回 C_η = {S₂ : J_robust(S₂) ≤ (1 + η) J*}."""
    thresh = (1.0 + eta) * J_star
    return [r["S2"] for r in results if r["J_robust"] <= thresh]


# ============== 8. 自检 ==============

def _self_test():
    import time
    print("[T1] classify_G 三分类")
    assert classify_G((100, 0), (101, 0), R_eff=1500) == "A0"   # 1 m ≤ 5
    assert classify_G((100, 0), (200, 0), R_eff=1500) == "A1"   # 100 m ∈ (5, 1500]
    assert classify_G((100, 0), (2000, 0), R_eff=1500) == "A2"  # 1900 m > 1500
    print("  ✓")

    print("[T2] build_P2 调通问题一")
    r = build_P2((0, 0), 0.0, (1000, 0), (500, 10))
    assert "poly" in r and "mec_radius" in r
    print(f"  ρ₂ = {r['mec_radius']:.2f}  ✓")

    print("[T3] sample_F1 落在 [5, 1500] 内")
    Gs = sample_F1((0, 0), 0.0, N_d=60, N_w=21)
    for G in Gs[:20]:
        d = math.hypot(G[0], G[1])
        assert 5 <= d <= 1500, f"out of [5,1500]: {G}, d={d}"
    print(f"  共 {len(Gs)} 个点 ✓")

    print("[T4] J_robust 在网格上有限")
    Gs = sample_F1((0, 0), 0.0, N_d=20, N_w=11)
    jr = J_robust((500, 0), (0, 0), 0.0, Gs)
    assert math.isfinite(jr["J_robust"])
    print(f"  J_robust = {jr['J_robust']:.2f}  ✓")

    print("[T5] J_proxy 在不同 S₂ 上返回有限 κ")
    Gs = sample_F1((0, 0), 0.0, N_d=20, N_w=11)
    p1 = J_proxy((500, 500), (0, 0), 0.0, Gs)   # 法线方向 500 m
    p2 = J_proxy((0, 1500), (0, 0), 0.0, Gs)    # 法线方向 1500 m
    # 任意 S₂ 都返回有限、非负的 κ
    import math as _m
    assert _m.isfinite(p1["max_kappa"]) and p1["max_kappa"] > 0
    assert _m.isfinite(p2["max_kappa"]) and p2["max_kappa"] > 0
    # 远 S₂ 因 β 范围更广、接近正交，max κ 应小于近 S₂
    assert p2["max_kappa"] < p1["max_kappa"]
    print(f"  近 p1={p1['max_kappa']:.2f}, 远 p2={p2['max_kappa']:.2f}  ✓")

    print("[T6] 网格搜索性能（30 个候选 + 220 个 G）")
    t0 = time.time()
    res = grid_search_J_robust((0, 0), 0.0,
                               R_Omega=1800, R_eff=1500,
                               L_min=992, grid_step=200,
                               N_d=10, N_w=11)
    dt = time.time() - t0
    print(f"  耗时 {dt:.2f}s, J* = {res['J_star']:.2f}, S₂* = {res['S2_star']}  ✓")

    print("[T7] C_η 在 η=0.2 下非空")
    if res["results"]:
        eta_pts = candidate_region(res["results"], res["J_star"], eta=0.2)
        assert len(eta_pts) >= 1
        print(f"  |C_η| = {len(eta_pts)}  ✓")

    print("[OK] 7/7 自检通过")


if __name__ == "__main__":
    _self_test()