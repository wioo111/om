# -*- coding: utf-8 -*-
r"""问题二 v5 —— 可执行的第二检测点选择策略（彻底去掉 oracle 信息泄漏）。

核心事实
--------
机器狗在第二次移动之前 **只能知道**：
    S1、第一次示向度读数 theta1_hat（含 ±1° 误差）、Omega、epsilon、R_eff 的取值范围。
真实源位置 G 与真实距离 d = |S1 - G| **完全未知**。
因此任何使用 G 或 d 的选点函数（例如旧版 place_thales(G, d, ...)）都是不可实现的
oracle 策略，v5 全部弃用（仅保留一个显式标注的 oracle 参考项，用来量化旧版虚高的性能）。

第一次可行域
------------
    F1 = Omega ∩ {G : 5 < |G - S1| <= 1500, |wrap(angle(G - S1) - theta1_hat)| <= epsilon}
注意角度误差只有 ±epsilon（= 1°），不是 ±2epsilon。

鲁棒选点判据（主判据，唯一）
----------------------------
对候选 S2 in Omega 与潜在源 G in F1：
    C(S2, G) = 0            , |S2-G| <= 5
             = D2(S2, G)    , 5 < |S2-G| <= 1000   （R_eff >= 1000，保证能收到第二次示向度）
             = lambda       , |S2-G| > 1000        （R_eff 可能小于该距离，按最坏情形计失败）
    J(S2) = max_{G in F1} C(S2, G)
    S2*   = argmin_{S2 in Omega} J(S2)
    C_eta = {S2 in Omega : J(S2) <= (1+eta) * J(S2*)},   lambda = diam(F1)

D2(S2,G) = max over e2 in [-eps, eps] 的"两次示向度交会后定位区域直径"。

次判据（仅作对照，不参与选点）
------------------------------
J_RN(S2) = 在 F1 上按面积均匀、R_eff ~ U[1000,1500] 下的期望代价（风险中性）。
"""
from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# 复用第一问 v5 的几何内核（兼容中文路径，直接按文件加载）
import importlib.util as _ilu

_HERE = os.path.dirname(os.path.abspath(__file__))
_P1_FILE = os.path.normpath(os.path.join(_HERE, '..', '..', '第一问', 'v5', 'problem1_core.py'))
_spec = _ilu.spec_from_file_location('problem1_core', _P1_FILE)
p1 = _ilu.module_from_spec(_spec)          # type: ignore
_spec.loader.exec_module(p1)               # type: ignore

# ---------------------------------------------------------------- 常量
R_TARGET = 1800.0
R_EFF_LO = 1000.0          # 有效接收半径下界（未知量，最坏情形）
R_EFF_HI = 1500.0          # 有效接收半径上界
EPS_DEG = 1.0              # 示向度误差（度）
NEAR_M = 5.0               # 近距阈值
N_DISK = p1.N_DISK


@dataclass
class Cfg:
    r"""一组可复现的算法超参数。"""
    grid_step: float = 60.0        # 候选 S2 粗网格间距（米）
    refine_step: float = 12.0      # 局部精化间距（米）
    refine_span: float = 90.0      # 局部精化范围（米）
    k_dir: int = 25                # 可能实测第二次示向度的扫描点数（均匀粗扫）
    k_dir_refine: int = 2          # 粗扫峰值附近的局部加密轮数
    n_d: int = 25                  # F1 沿射线方向采样点数
    n_phi: int = 5                 # F1 横向采样点数
    n_disk: int = N_DISK
    seed: int = 20260912


# ================================================================ F1
def f1_convex(S1, th1_hat, r_target=R_TARGET, r_eff_hi=R_EFF_HI,
              eps_deg=EPS_DEG, n_disk=N_DISK):
    r"""F1 的凸包版本（不含 |G-S1| > 5 的小球约束，采样阶段再排除）。"""
    poly = p1.clip_halfplanes(p1.bbox_polygon(2 * r_target + 2 * r_eff_hi + 100.0),
                              list(p1.sector_halfplanes(S1, th1_hat, eps_deg)))
    if poly is None:
        return None
    poly = p1.clip_disk(poly, p1.ORIGIN, r_target, n_disk)
    if poly is None:
        return None
    poly = p1.clip_disk(poly, S1, r_eff_hi, n_disk)
    if poly is None:
        return None
    return p1.simplify_convex(poly, p1.SIMPLIFY_TOL)


def f1_diameter(S1, th1_hat, **kw) -> float:
    poly = f1_convex(S1, th1_hat, **kw)
    return p1.polygon_diameter(poly)[0] if poly else 0.0


def sample_F1(S1, th1_hat, cfg: Cfg, r_target=R_TARGET, r_eff_hi=R_EFF_HI,
              eps_deg=EPS_DEG, prior: str = 'observable'):
    r"""在 F1 上取 (d, phi) 网格样本，返回 (pts[N,2], weights[N], wsum)。

    prior='observable'（默认，与仿真评估分布一致）：
        设 R_eff~U[1000,1500] 且与源位置独立、源在 Omega 内按面积均匀，
        并条件在"在 S1 处确实读到了示向度"（即 d <= R_eff）上，则 (d,phi) 的
        密度正比于  d * P(R_eff >= d) = d * (1500 - max(d,1000)) / 500 。
        （注意 d>1000 时权重随 d 增大而衰减到 0 —— 这是"可观测性"带来的先验修正。）
    prior='uniform_area'：只按面积元 d*dd*dphi 加权（"F1 上均匀"）。

    该权重只用于对照判据 J_RN；主判据 J（最坏代价）与先验无关。
    """
    ds = np.linspace(NEAR_M + 1.0, r_eff_hi, cfg.n_d)
    phis = np.deg2rad(np.linspace(-eps_deg, eps_deg, cfg.n_phi))
    th = math.radians(th1_hat)
    dd = (ds[1] - ds[0]) if len(ds) > 1 else 1.0
    dphi = (phis[1] - phis[0]) if len(phis) > 1 else 1.0
    rows = []
    ws = []
    for d in ds:
        if prior == 'observable':
            w_obs = max(r_eff_hi - max(d, R_EFF_LO), 0.0)
        else:
            w_obs = 1.0
        for ph in phis:
            a = th + ph
            P = (S1[0] + d * math.cos(a), S1[1] + d * math.sin(a))
            if P[0] ** 2 + P[1] ** 2 > r_target ** 2 + 1e-9:
                continue
            rows.append(P)
            ws.append(d * dd * dphi * w_obs)
    if not rows:
        return np.zeros((0, 2)), np.zeros(0), 0.0
    return np.array(rows), np.array(ws), float(np.sum(ws))


# ================================================================ S2 候选网格
def candidate_grid(cfg: Cfg, r_target=R_TARGET, step: Optional[float] = None):
    step = step or cfg.grid_step
    xs = np.arange(-r_target + step / 2, r_target, step)
    XX, YY = np.meshgrid(xs, xs)
    X = XX.ravel()
    Y = YY.ravel()
    m = X * X + Y * Y <= (r_target - step * 0.25) ** 2
    return X[m], Y[m]


def project_into_omega(S, r_target=R_TARGET):
    r = math.hypot(S[0], S[1])
    if r <= r_target:
        return S
    k = r_target / r
    return (S[0] * k, S[1] * k)


# ================================================================ D2
def region_diameter(S1, S2, th1_hat, th2_meas, eps_deg=EPS_DEG, n_disk=N_DISK):
    res = p1.solve([S1, S2], [th1_hat, th2_meas], eps_deg=eps_deg,
                   R_eff=R_EFF_HI, R_target=R_TARGET, N_disk=n_disk)
    if res['is_empty'] or res['D'] <= 0:
        return None
    return res['D']


def direction_arc(S2, pts: np.ndarray):
    r"""F1 中的点在 S2 处张成的方位角弧 [start, end]（弧度，end >= start）。

    用"最大角度空隙"法稳健求弧：凸区域对任意外部点张成一条连续弧；
    若所有方向几乎铺满整圈（S2 落在 F1 内部附近），返回整圈。
    """
    ang = np.arctan2(pts[:, 1] - S2[1], pts[:, 0] - S2[0])
    n = ang.size
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return float(ang[0]), float(ang[0])
    s = np.sort(ang)
    d = np.diff(np.concatenate([s, [s[0] + 2.0 * math.pi]]))
    k = int(np.argmax(d))
    # 方位角集合的凸包必为"最大空隙的补弧"（空隙内没有样本点）。
    # 注意：不能按"空隙是否 >= 180°"来判断，张角可以超过 180°（S2 近轴退化时）。
    start = float(s[(k + 1) % n])
    end = float(s[k])
    if end < start:
        end += 2.0 * math.pi
    return start, end


def arc_positions(S2, pts: np.ndarray, start: float):
    r"""把各潜在源的方位角平移到以 start 为基准的 [0, 2pi) 偏移量。"""
    ang = np.arctan2(pts[:, 1] - S2[1], pts[:, 0] - S2[0])
    return np.mod(ang - start, 2.0 * math.pi)


# ================================================================ 目标函数
def distance_map(X, Y, pts):
    r"""返回每个候选 (X,Y) 到全部潜在源样本的最近/最远距离矩阵与最大值。"""
    dx = X[:, None] - pts[None, :, 0]
    dy = Y[:, None] - pts[None, :, 1]
    D = np.sqrt(dx * dx + dy * dy)
    return D, D.max(axis=1)


def objective_map(S1, th1_hat, cfg: Cfg, X, Y, pts, ws, wsum, lam,
                  r_target=R_TARGET, scan_mask=None):
    r"""在候选网格上计算主判据 J 与对照判据 J_RN。

    scan_mask[i] = False 的候选点不做昂贵的"第二次示向度扫描"，直接取失败惩罚；
    这是**安全**的：只有 |S2-G| <= 1000 对 F1 全体成立的候选才可能是主判据的最优解，
    我们永远把这一批候选全部扫描（见 optimize_S2）。
    """
    n = len(X)
    J = np.full(n, lam, dtype=float)
    J_rn = np.full(n, lam, dtype=float)
    Dmat, dmax = distance_map(X, Y, pts)
    ok = dmax <= R_EFF_LO
    near = Dmat <= NEAR_M
    n_eval = 0
    if scan_mask is None:
        scan_mask = ok

    for i in range(n):
        if not scan_mask[i]:
            continue
        # ---------- 可能的实测第二次示向度集合 ----------
        a0, a1 = direction_arc((X[i], Y[i]), pts)
        span_deg = math.degrees(a1 - a0)
        lo = math.degrees(a0) - EPS_DEG
        hi = math.degrees(a1) + EPS_DEG
        k_dir = cfg.k_dir if span_deg <= 270.0 else max(cfg.k_dir, 37)
        dirs = np.linspace(lo, hi, k_dir)
        vals = []
        for th2 in dirs:
            D = region_diameter(S1, (X[i], Y[i]), th1_hat, float(th2),
                                n_disk=cfg.n_disk)
            n_eval += 1
            vals.append(np.nan if D is None else D)
        vals = np.array(vals, dtype=float)

        # 空可行域只可能出现在"该扫描方向其实不可达"的退化边界上：跳过而不是判失败。
        # （若某个 G 真的产生了该读数，则 G 本身必落在定位区域内，区域不可能为空。）
        valid = ~np.isnan(vals)
        if valid.any():
            idxv = np.flatnonzero(valid)
            vals_filled = np.interp(np.arange(len(vals)), idxv, vals[idxv])
            j_best = float(np.max(vals[idxv]))
            # ---- 局部加密：单向扫描峰值很窄，均匀网格会漏掉尖峰 ----
            step_d = (hi - lo) / max(k_dir - 1, 1)
            th_best = float(dirs[int(np.argmax(vals))])
            for _r in range(cfg.k_dir_refine):
                step_d /= 4.0
                fine = np.linspace(th_best - 2 * step_d, th_best + 2 * step_d, 9)
                fvals = []
                for th2 in fine:
                    D = region_diameter(S1, (X[i], Y[i]), th1_hat, float(th2),
                                        n_disk=cfg.n_disk)
                    n_eval += 1
                    fvals.append(-1.0 if D is None else D)
                fvals = np.array(fvals, dtype=float)
                kbest = int(np.argmax(fvals))
                if fvals[kbest] > j_best:
                    j_best = float(fvals[kbest])
                th_best = float(fine[kbest])
        else:
            vals_filled = np.full(len(vals), lam)
            j_best = lam
        empty_flag = not valid.any()

        # 把每个潜在源 G 映射到最近的扫描方向
        pos = np.degrees(arc_positions((X[i], Y[i]), pts, a0)) - EPS_DEG
        idx = np.clip(np.searchsorted(dirs, pos), 0, len(dirs) - 1)
        idx_lo = np.clip(idx - 1, 0, len(dirs) - 1)
        closer_lo = np.abs(dirs[idx_lo] - pos) < np.abs(dirs[idx] - pos)
        idx = np.where(closer_lo, idx_lo, idx)
        Dloc = vals_filled[idx]
        Dloc = np.where(near[i], 0.0, Dloc)        # 近距可直接清除，代价 0

        # ---------- 主判据 ----------
        # J = max over 可能实测示向度 的 D2（也把"近距可直接清除"的方向计入上界，偏保守）
        if dmax[i] > R_EFF_LO:
            J[i] = lam
        elif empty_flag:
            J[i] = lam
        else:
            J[i] = j_best

        # ---------- 风险中性（对照）----------
        p_recv = np.where(Dmat[i] <= R_EFF_LO, 1.0,
                          np.clip((R_EFF_HI - Dmat[i]) / (R_EFF_HI - R_EFF_LO), 0.0, 1.0))
        c = p_recv * Dloc + (1.0 - p_recv) * lam
        J_rn[i] = float(np.sum(ws * c) / wsum) if wsum > 0 else lam

    return {'J': J, 'J_rn': J_rn, 'dmax': dmax, 'ok_mask': ok, 'n_eval': n_eval}


# ================================================================ 优化主入口
def optimize_S2(S1, th1_hat, cfg: Optional[Cfg] = None, r_target=R_TARGET,
                fine: bool = True, rn_step: float = 150.0) -> dict:
    r"""主判据下的最优第二检测点 S2*、J* 与候选区域（含对照的风险中性最优）。"""
    cfg = cfg or Cfg()
    F1 = f1_convex(S1, th1_hat, n_disk=cfg.n_disk)
    lam = p1.polygon_diameter(F1)[0] if F1 else 0.0
    pts, ws, wsum = sample_F1(S1, th1_hat, cfg)
    # 追加 F1 的顶点（权重 0）：使 max_{G in F1}|S2-G| 与方位角弧的估计精确
    # （凸函数在凸多边形上的最大值必在顶点取到）。
    # 关键：必须剔除落在 |G-S1| <= 5 内的顶点（扇形的顶点 S1 本身），因为
    # 那部分不属于 F1。
    if F1:
        vp = np.array([(v[0], v[1]) for v in F1
                       if math.hypot(v[0] - S1[0], v[1] - S1[1]) > NEAR_M])
        if len(vp):
            pts = np.vstack([pts, vp])
            ws = np.concatenate([ws, np.zeros(len(vp))])

    X, Y = candidate_grid(cfg, r_target)
    _, dm = distance_map(X, Y, pts)
    scan = dm <= R_EFF_LO                      # 保证能收到第二次示向度的候选
    coarse = objective_map(S1, th1_hat, cfg, X, Y, pts, ws, wsum, lam, r_target, scan)
    Jc = coarse['J']
    best_idx = int(np.argmin(Jc))
    Jstar = float(Jc[best_idx])
    cands = np.where(Jc <= Jstar + 1e-9)[0]
    if len(cands) > 1:                     # 平局取离 S1 最近（省移动时间）
        dist = np.hypot(X[cands] - S1[0], Y[cands] - S1[1])
        best_idx = int(cands[int(np.argmin(dist))])
        Jstar = float(Jc[best_idx])

    n_fine = 0
    x0, y0 = float(X[best_idx]), float(Y[best_idx])
    if fine:
        xs = np.arange(x0 - cfg.refine_span, x0 + cfg.refine_span + 1e-9, cfg.refine_step)
        ys = np.arange(y0 - cfg.refine_span, y0 + cfg.refine_span + 1e-9, cfg.refine_step)
        XX, YY = np.meshgrid(xs, ys)
        Xr = XX.ravel()
        Yr = YY.ravel()
        m = Xr * Xr + Yr * Yr <= (r_target - 1.0) ** 2
        Xr, Yr = Xr[m], Yr[m]
        _, dmr = distance_map(Xr, Yr, pts)
        fine_map = objective_map(S1, th1_hat, cfg, Xr, Yr, pts, ws, wsum, lam,
                                 r_target, dmr <= R_EFF_LO)
        n_fine = fine_map['n_eval']
        bi = int(np.argmin(fine_map['J']))
        if fine_map['J'][bi] <= Jstar + 1e-12:
            x0, y0, Jstar = float(Xr[bi]), float(Yr[bi]), float(fine_map['J'][bi])

    # ---- 极坐标精化（以 (S1, theta1_hat) 为基准的 (L, alpha) 参数）----
    # 目标函数在 (L, alpha) 平面上的条件数远好于笛卡尔网格，用于把 S2* 精确定位。
    n_polar = 0
    L0 = math.hypot(x0 - S1[0], y0 - S1[1])
    a0 = math.degrees(math.atan2(y0 - S1[1], x0 - S1[0])) - th1_hat
    polar_track = []
    for (dl, da, sl, sa) in ((60.0, 8.0, 5.0, 1.0), (12.0, 1.6, 1.0, 0.2)):
        Ls = np.arange(L0 - dl, L0 + dl + 1e-9, sl)
        As = np.arange(a0 - da, a0 + da + 1e-9, sa)
        LL, AA = np.meshgrid(Ls, As)
        PX = S1[0] + LL.ravel() * np.cos(np.deg2rad(th1_hat + AA.ravel()))
        PY = S1[1] + LL.ravel() * np.sin(np.deg2rad(th1_hat + AA.ravel()))
        keep = (PX * PX + PY * PY <= (r_target - 1.0) ** 2) & (LL.ravel() > 1.0)
        PX, PY = PX[keep], PY[keep]
        AL = AA.ravel()[keep]
        _, dmp = distance_map(PX, PY, pts)
        pm = objective_map(S1, th1_hat, cfg, PX, PY, pts, ws, wsum, lam,
                           r_target, dmp <= R_EFF_LO)
        n_polar += pm['n_eval']
        if len(pm['J']):
            bi = int(np.argmin(pm['J']))
            if pm['J'][bi] <= Jstar + 1e-12:
                x0, y0, Jstar = float(PX[bi]), float(PY[bi]), float(pm['J'][bi])
                L0, a0 = float(np.hypot(x0 - S1[0], y0 - S1[1])), float(AL[bi])
            polar_track.append({'n': len(pm['J']),
                                'L_best': float(L0), 'alpha_best': float(a0),
                                'J_best': float(Jstar)})

    etas = [0.0, 0.05, 0.2, 0.5]
    regions = {e: (Jc <= Jstar * (1.0 + e) + 1e-9) for e in etas}
    L_star = math.hypot(x0 - S1[0], y0 - S1[1])
    alpha_star = math.degrees(math.atan2(y0 - S1[1], x0 - S1[0])) - th1_hat
    alpha_star = (alpha_star + 180.0) % 360.0 - 180.0

    # ---- 风险中性最优（对照策略，粗网格，覆盖"可能收到"的候选）----
    Xr2, Yr2 = candidate_grid(cfg, r_target, step=rn_step)
    _, dm2 = distance_map(Xr2, Yr2, pts)
    rn_map = objective_map(S1, th1_hat, cfg, Xr2, Yr2, pts, ws, wsum, lam,
                           r_target, dm2 <= R_EFF_HI)
    jrn = rn_map['J_rn']
    bi_rn = int(np.argmin(jrn))

    return {
        'S1': tuple(S1), 'theta1_hat': th1_hat,
        'S2_star': (x0, y0), 'J_star': Jstar, 'lambda': lam,
        'L_star': L_star, 'alpha_star': alpha_star,
        'J_map': Jc, 'J_rn_map': rn_map['J_rn'], 'grid_X': X, 'grid_Y': Y,
        'ok_mask': coarse['ok_mask'], 'dmax_map': coarse['dmax'],
        'regions': regions, 'etas': etas,
        'F1_poly': F1, 'F1_diam': lam,
        'G_pts': pts, 'G_w': ws, 'G_wsum': wsum,
        'n_eval': coarse['n_eval'] + n_fine + n_polar + rn_map['n_eval'],
        'polar_track': polar_track,
        'S2_rn': (float(Xr2[bi_rn]), float(Yr2[bi_rn])), 'J_rn_star': float(jrn[bi_rn]),
        'rn_grid_X': Xr2, 'rn_grid_Y': Yr2,
    }


# ================================================================ 策略
def _f1_points(S1, th1_hat, cfg):
    F1 = f1_convex(S1, th1_hat, n_disk=cfg.n_disk)
    lam = p1.polygon_diameter(F1)[0] if F1 else 0.0
    pts, ws, wsum = sample_F1(S1, th1_hat, cfg)
    if F1:
        vp = np.array([(v[0], v[1]) for v in F1
                       if math.hypot(v[0] - S1[0], v[1] - S1[1]) > NEAR_M])
        if len(vp):
            pts = np.vstack([pts, vp])
            ws = np.concatenate([ws, np.zeros(len(vp))])
    return F1, lam, pts, ws, wsum


def _l_interval(S1, th1_hat, pts, alpha_deg, r_target, n=240):
    r"""在方向 theta1_hat+alpha 上，满足 max_G|S2-G| <= R_EFF_LO 且 S2 ∈ Omega 的 L 区间。

    dmax(L) = max_G |S1 + L*u - G| 是 L 的凸函数（凸函数之最大值），
    因此可行集是单一区间 [L_lo, L_hi]。返回 (L_lo, L_hi) 或 None。
    """
    A = math.radians(th1_hat + alpha_deg)
    ca, sa = math.cos(A), math.sin(A)
    rho = S1[0] * ca + S1[1] * sa
    # |S1 + L u|^2 <= R^2  <=>  L^2 + 2 rho L + (|S1|^2 - R^2) <= 0
    disc = rho * rho - (S1[0] ** 2 + S1[1] ** 2 - r_target ** 2)
    if disc <= 0:
        return None
    rt = math.sqrt(disc)
    hi_omega = -rho + rt
    L_lo_om = max(0.0, -rho - rt)
    if hi_omega <= L_lo_om:
        return None
    Ls = np.linspace(L_lo_om, hi_omega, n)
    X = S1[0] + Ls * ca
    Y = S1[1] + Ls * sa
    dx = X[:, None] - pts[None, :, 0]
    dy = Y[:, None] - pts[None, :, 1]
    D = np.sqrt(dx * dx + dy * dy).max(axis=1)
    ok = D <= R_EFF_LO
    if not ok.any():
        return None
    k = int(np.argmin(D))
    if not ok[k]:                                    # 取最长的可行连通段
        idx = np.flatnonzero(ok)
        segs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
        idx = max(segs, key=len)
        k = int(idx[len(idx) // 2])
    i0 = k
    while i0 - 1 >= 0 and ok[i0 - 1]:
        i0 -= 1
    i1 = k
    while i1 + 1 < n and ok[i1 + 1]:
        i1 += 1

    def dmax(L):
        x, y = S1[0] + L * ca, S1[1] + L * sa
        return float(np.max(np.hypot(pts[:, 0] - x, pts[:, 1] - y)))

    a, b = (Ls[max(i0 - 1, 0)], Ls[i0])
    if dmax(a) <= R_EFF_LO:
        L_lo = a
    else:
        for _ in range(40):
            m = 0.5 * (a + b)
            if dmax(m) <= R_EFF_LO:
                b = m
            else:
                a = m
        L_lo = b
    a, b = (Ls[i1], Ls[min(i1 + 1, n - 1)])
    if dmax(b) <= R_EFF_LO:
        L_hi = b
    else:
        for _ in range(40):
            m = 0.5 * (a + b)
            if dmax(m) <= R_EFF_LO:
                a = m
            else:
                b = m
        L_hi = a
    if L_hi <= max(L_lo, 1.0):
        return None
    return (L_lo, L_hi)


def solve_robust_polar(S1, th1_hat, cfg: Optional[Cfg] = None, r_target=R_TARGET,
                       alpha_spans=((180.0, 2.0), (4.0, 0.2), (0.5, 0.05))):
    r"""一维高效求解主判据：沿"正好用满 R_eff 下界"的可行边界扫描偏角 alpha。

    可行集在 (alpha, L) 平面上对每个 alpha 是区间 [L_lo, L_hi]；
    最坏代价 J 的最优解必落在该集合的边界（L=L_lo 或 L=L_hi）上，故只需扫描边界。
    这是 optimize_S2 的高效等价实现，也用于一般 S1 的求解。
    """
    cfg = cfg or Cfg()
    F1, lam, pts, ws, wsum = _f1_points(S1, th1_hat, cfg)
    best = None
    centre = 0.0
    hist = []
    n_eval = 0
    for (half, step) in alpha_spans:
        alphas = np.arange(centre - half, centre + half + 1e-9, step)
        for al in alphas:
            iv = _l_interval(S1, th1_hat, pts, float(al), r_target)
            if iv is None:
                continue
            Llo, Lhi = iv
            trials = {Lhi}
            trials.add(max(Llo, 1.0))
            trials.add(max(0.97 * Lhi, 1.0))
            for Ls_ in trials:
                A = math.radians(th1_hat + al)
                S2 = (S1[0] + Ls_ * math.cos(A), S1[1] + Ls_ * math.sin(A))
                X = np.array([S2[0]])
                Y = np.array([S2[1]])
                m = objective_map(S1, th1_hat, cfg, X, Y, pts, ws, wsum, lam,
                                  r_target, None)
                n_eval += m['n_eval']
                J = float(m['J'][0])
                if best is None or J < best['J'] - 1e-12:
                    best = {'J': J, 'L': Ls_, 'alpha': float(al), 'S2': S2}
        if best is None:
            break
        centre = best['alpha']
        hist.append({'half': half, 'step': step, 'alpha_best': best['alpha'],
                     'L_best': best['L'], 'J_best': best['J']})
    if best is None:
        # 兜底：不存在任何能对所有 G∈F1 保证收到第二次示向度的 S2
        # （例如 S1 已靠近 Ω 边界）。退化为"最小化最坏距离"：
        # 取 F1 采样点最小包围圆圆心（投影回 Ω），使接收失败风险尽可能小。
        c, _rad = p1.mec_welzl([tuple(p) for p in pts])
        S2f = project_into_omega(c, r_target)
        Lf = math.hypot(S2f[0] - S1[0], S2f[1] - S1[1])
        af = math.degrees(math.atan2(S2f[1] - S1[1], S2f[0] - S1[0])) - th1_hat
        af = (af + 180.0) % 360.0 - 180.0
        m = objective_map(S1, th1_hat, cfg, np.array([S2f[0]]), np.array([S2f[1]]),
                          pts, ws, wsum, lam, r_target, None)
        n_eval += m['n_eval']
        return {'S2_star': S2f, 'L_star': Lf, 'alpha_star': af,
                'J_star': float(m['J'][0]), 'lambda': lam, 'F1_poly': F1,
                'G_pts': pts, 'G_w': ws, 'G_wsum': wsum, 'stages': hist,
                'n_eval': n_eval, 'feasible': False,
                'fallback': 'minimax_distance'}
    return {'S2_star': best['S2'], 'L_star': best['L'], 'alpha_star': best['alpha'],
            'J_star': best['J'], 'lambda': lam, 'F1_poly': F1,
            'G_pts': pts, 'G_w': ws, 'G_wsum': wsum,
            'stages': hist, 'n_eval': n_eval, 'feasible': True}


def strat_random_omega(S1, th1_hat, rng: random.Random, **_):
    r"""基线 1：在 Omega 内随机取一点。"""
    return p1.sample_uniform_disk(rng, R_TARGET)


def strat_along_bearing(S1, th1_hat, L=750.0, **_):
    r"""基线 2：沿第一次测向方向前进 L 米。"""
    th = math.radians(th1_hat)
    return project_into_omega((S1[0] + L * math.cos(th), S1[1] + L * math.sin(th)))


def strat_perp(S1, th1_hat, L=1000.0, **_):
    r"""基线 3：沿第一次测向的垂线方向移动 L 米。"""
    th = math.radians(th1_hat + 90.0)
    return project_into_omega((S1[0] + L * math.cos(th), S1[1] + L * math.sin(th)))


def strat_oracle_thales(S1, th1_hat, G_true, d_true=None, **_):
    r"""旧版 oracle 策略（**不可实现**，仅用于量化信息泄漏带来的虚高性能）。

    旧代码 place_thales 用真实距离 d = |S1 - G| 把 S2 放在
        S2 = G_true + d*tan(eps) * n_perp(theta1_true)
    即"几乎直接站在干扰源旁边"，这在第二次移动前是不可能的。
    """
    d = d_true if d_true is not None else math.hypot(G_true[0] - S1[0], G_true[1] - S1[1])
    th_true = math.degrees(math.atan2(G_true[1] - S1[1], G_true[0] - S1[0]))
    L = d * math.tan(math.radians(EPS_DEG))
    perp = math.radians(th_true + 90.0)
    return project_into_omega((G_true[0] + L * math.cos(perp),
                               G_true[1] + L * math.sin(perp)))


# ================================================================ 单场评估
def evaluate_one(S1, th1_hat, S2, G_true, R_eff_true, e2,
                 lam, n_disk=N_DISK) -> dict:
    r"""在一个场景上评估给定 S2 的实际表现（使用真实源与真实接收半径）。"""
    d2 = math.hypot(G_true[0] - S2[0], G_true[1] - S2[1])
    out = {'d2': d2, 'S2': tuple(S2)}
    th2_true = math.degrees(math.atan2(G_true[1] - S2[1], G_true[0] - S2[0]))
    out['theta2_true'] = th2_true
    if d2 <= NEAR_M:
        out.update(status='direct', cost=0.0, D=0.0, n_vertices=0,
                   theta2_meas=None, ratio=None, covered=None)
        return out
    if d2 > R_eff_true:
        out.update(status='no_signal', cost=lam, D=None, n_vertices=0,
                   theta2_meas=None, ratio=None, covered=None)
        return out
    th2_meas = (th2_true + e2) % 360.0
    res = p1.solve([S1, S2], [th1_hat, th2_meas], eps_deg=EPS_DEG,
                   R_eff=R_EFF_HI, R_target=R_TARGET, N_disk=n_disk)
    out['theta2_meas'] = th2_meas
    if res['is_empty'] or res['D'] <= 0:
        out.update(status='empty_region', cost=lam, D=None, n_vertices=0,
                   ratio=None, covered=None)
        return out
    out.update(status='localized', cost=res['D'], D=res['D'],
               n_vertices=res['n_vertices'], ratio=res['ratio_2R_D'] if 'ratio_2R_D' in res else res['q'],
               covered=res['covered'])
    return out
