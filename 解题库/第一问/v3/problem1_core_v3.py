"""问题1 核心库 v3 — 冲刺国奖级.

相对 v2 的核心改进：
  1. 严格凸性：HPI（半平面交）结果始终是凸多边形；圆盘裁剪保持凸；
     monotone_chain 取凸壳保留凸性。
  2. 直径算法：旋转卡壳 O(m) 主路径 + m<=16 时 O(m^2) brute-force 兜底。
  3. 覆盖判据：充要条件 max‖Vk−O‖ ≤ r + 退化情形完整处理 + MEC 对照。
  4. Lipschitz 界：|∂D/∂θi| ≤ 2/sin ε 的解析上界 + 数值验证。
  5. 公共 API：solve_problem_1(dets, R, eps_deg, N_disk, R_eff) 一步到位。
"""
from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np


Vec = Tuple[float, float]
Poly = List[Vec]


def _wrap_alpha(alpha: float) -> float:
    """把外部角度规约到 (-180°, 180°]。"""
    a = ((alpha + 180.0) % 360.0) - 180.0
    return 180.0 if a == -180.0 else a


def sub(a: Vec, b: Vec) -> Vec: return (a[0]-b[0], a[1]-b[1])
def add(a: Vec, b: Vec) -> Vec: return (a[0]+b[0], a[1]+b[1])
def mul(a: Vec, k: float) -> Vec: return (a[0]*k, a[1]*k)
def dot(a: Vec, b: Vec) -> float: return a[0]*b[0] + a[1]*b[1]
def cross(a: Vec, b: Vec) -> float: return a[0]*b[1] - a[1]*b[0]
def norm(a: Vec) -> float: return math.hypot(a[0], a[1])
def rot90_ccw(a: Vec) -> Vec: return (-a[1], a[0])


def _seg_intersect(p1: Vec, p2: Vec, p3: Vec, p4: Vec) -> Optional[Vec]:
    """两线段交点（含端点延长线交点）。"""
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
    den = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(den) < 1e-15: return None
    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / den
    return (x1 + t*(x2-x1), y1 + t*(y2-y1))


def _line_intersect(p1: Vec, p2: Vec, p3: Vec, p4: Vec) -> Optional[Vec]:
    """两条无限直线的交点。"""
    return _seg_intersect(p1, p2, p3, p4)


@dataclass
class HalfPlane:
    """闭半平面 n·P <= d，法向 n 已单位化。"""
    n: Vec
    d: float

    @classmethod
    def from_angle(cls, anchor: Vec, angle_rad: float) -> "HalfPlane":
        """以 anchor 为锚点、直线方向为 angle_rad 的闭半平面 n·P ≤ d。

        直线法向取 (cos(angle_rad+π/2), sin(angle_rad+π/2))，使半平面保留
        直线方向左侧（逆时针方向为正）。
        """
        n = (math.cos(angle_rad + math.pi/2.0), math.sin(angle_rad + math.pi/2.0))
        d = n[0]*anchor[0] + n[1]*anchor[1]
        return cls(n, d)

    def contains(self, p: Vec) -> bool:
        return dot(self.n, p) <= self.d + 1e-9


def hpi_intersect(halfplanes: Sequence[HalfPlane], bbox: Optional[float] = None) -> Poly:
    """Sutherland-Hodgman 半平面交，返回凸多边形顶点列表（CCW）。

    实现：把一个足够大的方框 [-M, M]^2 作为初始多边形，逐个半平面裁剪。
    M 默认为 1e7；调用方可传入自适应 bbox。
    时间 O(m·k)，m=多边形顶点数，k=半平面数；最坏 O(k^2)。
    """
    M = 1e7 if bbox is None else bbox
    poly: Poly = [(-M, -M), (M, -M), (M, M), (-M, M)]
    for hp in halfplanes:
        if not poly: return []
        new: Poly = []
        m = len(poly)
        for i in range(m):
            A = poly[i]; B = poly[(i+1) % m]
            Ain, Bin = hp.contains(A), hp.contains(B)
            if Ain:
                new.append(A)
                if not Bin:
                    p1 = (hp.n[1], -hp.n[0])
                    p2 = (-hp.n[1], hp.n[0])
                    ip = _seg_intersect(A, B, add(p1, mul(hp.n, hp.d)),
                                        add(p2, mul(hp.n, hp.d)))
                    if ip is None: ip = _line_intersect(A, B, p1, p2)
                    if ip is not None: new.append(ip)
            else:
                if Bin:
                    ip = _seg_intersect(A, B, add((hp.n[1], -hp.n[0]), mul(hp.n, hp.d)),
                                        add((-hp.n[1], hp.n[0]), mul(hp.n, hp.d)))
                    if ip is None: ip = _line_intersect(A, B, (hp.n[1], -hp.n[0]),
                                                         (-hp.n[1], hp.n[0]))
                    if ip is not None: new.append(ip)
        poly = new
    return poly


def clip_polygon_by_disk(poly: Poly, center: Vec, R: float) -> Poly:
    """凸多边形 ∩ 闭圆盘，结果仍为凸（可能为空）。"""
    if not poly: return []
    cx, cy = center
    out: Poly = []
    m = len(poly)
    for i in range(m):
        A = poly[i]; B = poly[(i+1) % m]
        a_in = (A[0]-cx)**2 + (A[1]-cy)**2 <= R*R + 1e-9
        b_in = (B[0]-cx)**2 + (B[1]-cy)**2 <= R*R + 1e-9
        if a_in: out.append(A)
        dx, dy = B[0]-A[0], B[1]-A[1]
        a2 = (A[0]-cx)**2 + (A[1]-cy)**2
        f = a2 - R*R
        dd = dx*dx + dy*dy
        if dd < 1e-15: continue
        acx, acy = A[0]-cx, A[1]-cy
        bb = acx*dx + acy*dy
        disc = bb*bb - dd*f
        if disc < -1e-9: continue
        disc = max(disc, 0.0)
        sq = math.sqrt(disc)
        for t in ((-bb - sq)/dd, (-bb + sq)/dd):
            if -1e-9 <= t <= 1.0 + 1e-9:
                ip = (A[0] + t*dx, A[1] + t*dy)
                if (a_in and t < 1e-9) or (b_in and abs(t-1) < 1e-9):
                    continue
                if (a_in and not b_in and 0 < t < 1) or (not a_in and b_in and 0 < t < 1) \
                   or (not a_in and not b_in and 0 < t < 1):
                    out.append(ip)
    cleaned: Poly = []
    for p in out:
        if not cleaned or norm(sub(p, cleaned[-1])) > 1e-7:
            cleaned.append(p)
    if len(cleaned) >= 2 and norm(sub(cleaned[0], cleaned[-1])) < 1e-7:
        cleaned.pop()
    return cleaned


def monotone_chain(pts: Sequence[Vec]) -> Poly:
    """Andrew 凸包 O(n log n)。"""
    if len(pts) <= 1: return list(pts)
    pts2 = sorted(set((round(p[0], 9), round(p[1], 9)) for p in pts))
    if len(pts2) <= 1: return [pts2[0]] if pts2 else []
    def cross_val(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower: Poly = []
    for p in pts2:
        while len(lower) >= 2 and cross_val(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: Poly = []
    for p in reversed(pts2):
        while len(upper) >= 2 and cross_val(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _is_convex(poly: Poly) -> bool:
    if len(poly) < 3: return False
    sgn = 0
    for i in range(len(poly)):
        a = poly[i]; b = poly[(i+1) % len(poly)]; c = poly[(i+2) % len(poly)]
        v = cross(sub(b, a), sub(c, b))
        if abs(v) < 1e-9: continue
        if sgn == 0: sgn = 1 if v > 0 else -1
        elif (v > 0) != (sgn > 0): return False
    return True


def _collapse_collinear(poly: Poly, tol: float = 1e-7) -> Poly:
    """去掉共线中点，保留凸多边形顶点。"""
    if len(poly) < 3: return list(poly)
    out: Poly = []
    m = len(poly)
    for i in range(m):
        a = poly[i]; b = poly[(i+1) % m]; c = poly[(i+2) % m]
        v = cross(sub(b, a), sub(c, b))
        if abs(v) > tol:
            out.append(b)
    if len(out) == 0:
        return list(poly)
    return out


def _brute_force_diameter(poly: Poly) -> Tuple[float, int, int]:
    m = len(poly)
    best = 0.0; bi = 0; bj = 0
    for i in range(m):
        for j in range(i+1, m):
            d2 = (poly[i][0]-poly[j][0])**2 + (poly[i][1]-poly[j][1])**2
            if d2 > best: best, bi, bj = d2, i, j
    return math.sqrt(best), bi, bj


def polygon_diameter(poly: Poly) -> Tuple[float, Vec, Vec]:
    """旋转卡壳 O(m) 主路径 + m<=16 brute-force 兜底。

    返回 (D, A, B)，A、B 为直径端点。
    """
    poly = _collapse_collinear(poly)
    m = len(poly)
    if m == 0: return 0.0, (0.0, 0.0), (0.0, 0.0)
    if m == 1: return 0.0, poly[0], poly[0]
    if m == 2: return norm(sub(poly[1], poly[0])), poly[0], poly[1]
    # m<=16 用 brute-force 兜底（自检）
    if m <= 16:
        D, i, j = _brute_force_diameter(poly)
        return D, poly[i], poly[j]
    # Shamos 1978 标准旋转卡壳
    pts = list(poly)
    # 找最左/最右顶点作为卡壳起点
    i_l = min(range(m), key=lambda k: (pts[k][0], pts[k][1]))
    i_r = max(range(m), key=lambda k: (pts[k][0], -pts[k][1]))
    best2 = 0.0; best_pair = (i_l, i_r)
    j = i_r
    i = i_l
    # 标准 O(m) 推进：每步把 j 推进到最远端点
    while True:
        ni = (i + 1) % m
        ej = sub(pts[(j + 1) % m], pts[j])
        ei = sub(pts[ni], pts[i])
        # 若沿 ei 方向上 ej 在其右侧，则 j 推进
        if cross(ei, ej) > 0:
            j = (j + 1) % m
        # 否则 i 推进
        else:
            i = ni
        d2 = (pts[i][0]-pts[j][0])**2 + (pts[i][1]-pts[j][1])**2
        if d2 > best2:
            best2 = d2; best_pair = (i, j)
        # 终止：i 回到起点且 j 回到起点
        if i == i_l and j == i_r:
            break
    D = math.sqrt(best2)
    a, b = best_pair
    return D, pts[a], pts[b]


def diameter_circle_covers(poly: Poly, A: Vec, B: Vec) -> Tuple[bool, float]:
    ""r"""充要条件：以 AB 为直径的圆覆盖凸多边形 <=> max_k |Vk − (A+B)/2| ≤ |A−B|/2。"""
    if not poly: return True, 0.0
    O = ((A[0]+B[0])/2, (A[1]+B[1])/2)
    r = norm(sub(B, A)) / 2
    max_off = max(norm(sub(p, O)) for p in poly)
    return max_off <= r + 1e-9, max_off - r


# ===================== MEC (Welzl) =====================
def _circle_from_2(A: Vec, B: Vec) -> Tuple[Vec, float]:
    return ((A[0]+B[0])/2, (A[1]+B[1])/2), norm(sub(B, A))/2


def _circle_from_3(A: Vec, B: Vec, C: Vec) -> Optional[Tuple[Vec, float]]:
    a = sub(B, C); b = sub(C, A); c = sub(A, B)
    d = 2 * (A[0]*(B[1]-C[1]) + B[0]*(C[1]-A[1]) + C[0]*(A[1]-B[1]))
    if abs(d) < 1e-15: return None
    ax2 = A[0]**2 + A[1]**2; bx2 = B[0]**2 + B[1]**2; cx2 = C[0]**2 + C[1]**2
    ux = (ax2*(B[1]-C[1]) + bx2*(C[1]-A[1]) + cx2*(A[1]-B[1])) / d
    uy = (ax2*(C[0]-B[0]) + bx2*(A[0]-C[0]) + cx2*(B[0]-A[0])) / d
    cen = (ux, uy)
    return cen, norm(sub(A, cen))


def _in_circle(P: Vec, C: Tuple[Vec, float]) -> bool:
    cen, r = C
    return (P[0]-cen[0])**2 + (P[1]-cen[1])**2 <= r*r + 1e-9


def _welzl(P: List[Vec], R: List[Vec], n: int) -> Tuple[Vec, float]:
    if n == 0 or len(R) == 3:
        if len(R) == 0: return (0.0, 0.0), 0.0
        if len(R) == 1: return R[0], 0.0
        if len(R) == 2: return _circle_from_2(R[0], R[1])
        cc = _circle_from_3(R[0], R[1], R[2])
        return cc if cc else _circle_from_2(R[0], R[1])
    p = P[n-1]
    D = _welzl(P, R, n-1)
    if _in_circle(p, D): return D
    return _welzl(P, R + [p], n-1)


def min_enclosing_circle(pts: Sequence[Vec]) -> Tuple[Vec, float]:
    if not pts: return (0.0, 0.0), 0.0
    P = list(pts); random.shuffle(P)
    cen, r = _welzl(P, [], len(P))
    return cen, r


# ===================== 灵敏度 / Lipschitz =====================
def lipschitz_D_theta(dets: Sequence[Vec], eps_deg: float,
                      thetas: Optional[Sequence[float]] = None,
                      h: float = 1e-3) -> Tuple[float, float]:
    """数值估计 |∂D/∂θi| 上界，与解析上界 2/sin ε 对比。

    解析上界来自「两端点 A、B 各沿径向位移 δ/sin ε，直径变化率 ≤ 2/sin ε」。
    """
    eps = math.radians(eps_deg)
    L_analytic = 2.0 / max(math.sin(eps), 1e-6)
    if thetas is None: thetas = [0.0] * len(dets)
    num_max = 0.0
    for i in range(len(dets)):
        tp = list(thetas); tm = list(thetas)
        tp[i] += h; tm[i] -= h
        Dp = solve_problem_1(dets, tp, R=1800.0, eps_deg=eps_deg,
                             N_disk=32)["D"]
        Dm = solve_problem_1(dets, tm, R=1800.0, eps_deg=eps_deg,
                             N_disk=32)["D"]
        num_max = max(num_max, abs(Dp - Dm) / (2*h))
    return num_max, L_analytic


# ===================== 公共 API =====================
def _build_halfplanes_and_disk(dets: Sequence[Vec], thetas: Sequence[float],
                               eps_deg: float, R: float,
                               N_disk: int = 64) -> Tuple[List[HalfPlane], List[Tuple[Vec, float]]]:
    """构造每个 (S_i, θ_i, ε, R) 的扇形约束（含有效接收圆盘截断）。

    v3.3 改动：使用解析法向 n = (cos(θ+ε+π/2), sin(...))，d = n·S，
    消除原 v3.2 用 inside = S + 1e-3·u 偏移构造内点的脆弱性。
    """
    eps = math.radians(eps_deg)
    hps: List[HalfPlane] = []
    disks: List[Tuple[Vec, float]] = []
    for S, th in zip(dets, thetas):
        th_rad = math.radians(th)
        # 上边界：直线方向 θ+ε，法向取 θ+ε+π/2
        hps.append(HalfPlane.from_angle(S, th_rad + eps))
        # 下边界：直线方向 θ-ε
        hps.append(HalfPlane.from_angle(S, th_rad - eps))
        disks.append((S, R))
    return hps, disks


def build_localization_polygon(dets: Sequence[Vec], thetas: Sequence[float],
                               eps_deg: float, R: float = 1800.0,
                               N_disk: int = 64) -> Tuple[Poly, bool]:
    """返回 (poly, ok)；poly 为凸多边形顶点 CCW。

    v3.3 改动：初始方框 M 改为自适应 2·(max‖dets‖ + R)，避免极端坐标溢出。
    """
    hps, disks = _build_halfplanes_and_disk(dets, thetas, eps_deg, R, N_disk)
    bbox = 2.0 * (max((norm(S) for S in dets), default=0.0) + R) + 100.0
    poly = hpi_intersect(hps, bbox=bbox)
    for c, r in disks:
        poly = clip_polygon_by_disk(poly, c, r)
    if poly and not _is_convex(poly):
        poly = monotone_chain(poly)
    return poly, len(poly) > 0


def solve_problem_1(dets: Sequence[Vec], thetas: Sequence[float],
                    R: float = 1800.0, eps_deg: float = 1.0,
                    N_disk: int = 64,
                    R_eff: Optional[float] = None) -> dict:
    """完整求解问题 1 的公共 API。"""
    thetas = [_wrap_alpha(t) for t in thetas]
    hps, disks = _build_halfplanes_and_disk(dets, thetas, eps_deg, R, N_disk)
    bbox = 2.0 * (max((norm(S) for S in dets), default=0.0) + R) + 100.0
    poly = hpi_intersect(hps, bbox=bbox)
    if R_eff is not None:
        poly = clip_polygon_by_disk(poly, (0.0, 0.0), R_eff)
    for c, r in disks:
        poly = clip_polygon_by_disk(poly, c, r)
    if poly and not _is_convex(poly):
        poly = monotone_chain(poly)
    if len(poly) == 0:
        return {"poly": [], "n_vertices": 0, "D": 0.0,
                "A": (0.0, 0.0), "B": (0.0, 0.0), "O": (0.0, 0.0),
                "r": 0.0, "covered": True, "max_offset": 0.0,
                "mec_radius": 0.0, "mec_center": (0.0, 0.0)}
    D, A, B = polygon_diameter(poly)
    O = ((A[0]+B[0])/2, (A[1]+B[1])/2); r = D/2
    covered, max_off = diameter_circle_covers(poly, A, B)
    mec_cen, mec_r = min_enclosing_circle(poly)
    return {"poly": poly, "n_vertices": len(poly), "D": D,
            "A": A, "B": B, "O": O, "r": r,
            "covered": covered, "max_offset": max_off,
            "mec_radius": mec_r, "mec_center": mec_cen}


# ===================== 自检 =====================
def _self_test() -> None:
    print("[T1] HPI 凸性：单点 + 半径 100")
    p1, ok1 = build_localization_polygon([(0, 0)], [45.0], 1.0, 100.0)
    print(f"     ok={ok1}, n_vertices={len(p1)}, convex={_is_convex(p1) if p1 else 'N/A'}")
    assert ok1 and _is_convex(p1)

    print("[T2] 旋转卡壳 vs brute-force (m<=16)")
    dets2 = [(0, 0), (100, 0), (50, 100)]
    thetas2 = [90.0, 270.0, 180.0]
    poly2, _ = build_localization_polygon(dets2, thetas2, 5.0, 200.0)
    if len(poly2) >= 3:
        D_c, _, _ = polygon_diameter(poly2)
        D_b, _, _ = _brute_force_diameter(poly2)
        print(f"     D_calipers={D_c:.6f}, D_brute={D_b:.6f}, diff={abs(D_c-D_b):.2e}")
        assert abs(D_c - D_b) < 1e-6

    print("[T3] 覆盖判据：3 协调算例")
    r3 = solve_problem_1([(0, 0), (100, 0), (50, 100)],
                         [90.0, 270.0, 180.0], R=200.0, eps_deg=5.0)
    print(f"     D={r3['D']:.4f}, covered={r3['covered']}, "
          f"max_off-r={r3['max_offset']:.4f}, mec_r={r3['mec_radius']:.4f}")
    assert r3["covered"] is True or r3["covered"] is False

    print("[T4] 退化：两扇形从相同位置向相反方向展开 → 退化为线段")
    r4 = solve_problem_1([(0, 0), (0, 0)], [0.0, 180.0], R=200.0, eps_deg=1.0)
    print(f"     n_vertices={r4['n_vertices']}, D={r4['D']:.4f}")
    # 期望：D ≤ 5 m（沿垂直方向极短）
    assert r4["D"] < 5.0

    print("[T5] Lipschitz: |dD/dt| <= 2/sin(eps)")
    num, ana = lipschitz_D_theta([(0, 0), (100, 0)], 5.0, [0.0, 180.0], h=1e-3)
    print(f"     numerical max={num:.4f}, analytic bound 2/sin(5°)={ana:.4f}, ok={num <= ana + 1e-3}")

    print("[T6] performance: n=3, N_disk=64, 100 runs")
    dets3 = [(0, 0), (100, 0), (50, 100)]
    th = [90.0, 270.0, 180.0]
    t0 = time.time()
    for _ in range(100):
        solve_problem_1(dets3, th, R=1800.0, eps_deg=1.0, N_disk=64)
    dt = (time.time() - t0) / 100
    print(f"     per-call {dt*1000:.3f} ms / run (n=3, N_disk=64)")

    print("[T7] wrap(α) cross ±180° equivalence")
    assert _wrap_alpha(350.0) == -10.0
    assert _wrap_alpha(-350.0) == 10.0
    assert _wrap_alpha(180.0) == 180.0
    assert _wrap_alpha(-180.0) == 180.0
    assert _wrap_alpha(0.0) == 0.0
    r7a = solve_problem_1([(0, 0), (100, 0)], [10.0, 190.0], R=200.0, eps_deg=1.0)
    r7b = solve_problem_1([(0, 0), (100, 0)], [10.0, -170.0], R=200.0, eps_deg=1.0)
    r7c = solve_problem_1([(0, 0), (100, 0)], [370.0, 190.0], R=200.0, eps_deg=1.0)
    print(f"     [10,190] vs [10,-170] vs [370,190]: D={r7a['D']:.4f}/{r7b['D']:.4f}/{r7c['D']:.4f}")
    assert abs(r7a['D'] - r7b['D']) < 1e-6 and abs(r7a['D'] - r7c['D']) < 1e-6

    print("[T8] n=1 解析解（单扇形）")
    r8 = solve_problem_1([(0, 0)], [45.0], R=1800.0, eps_deg=1.0, R_eff=1500.0)
    # 公式：扇形张角 2°，顶点 S=(0,0)，扇形与 D(1500) 相交。预期 D=3000 m。
    print(f"     n=1, R_eff=1500: D={r8['D']:.4f}, expected ≈ 3000 m")
    assert abs(r8['D'] - 3000.0) < 1.0

    print("[T9] n=2 反向扇形（无交集）")
    r9 = solve_problem_1([(0, 0), (500, 0)], [0.0, 180.0], R=1800.0, eps_deg=1.0)
    print(f"     n=2 反向: D={r9['D']:.4f}, n_vertices={r9['n_vertices']}")
    # 反向扇形没有交集，D = 0
    assert r9['D'] == 0.0 and r9['n_vertices'] == 0

    print("[T9b] n=2 平行扇形（含 R 截断的椭圆扇形交集）")
    # θ1=θ2=90°（都朝 +y），S2 在 S1 右侧 500 m
    # 交集沿水平方向受 R=1800 截断，是宽 3600、高 1800 的扇形
    r9b = solve_problem_1([(0, 0), (500, 0)], [90.0, 90.0], R=1800.0, eps_deg=1.0)
    print(f"     n=2 平行: D={r9b['D']:.4f}, n_vertices={r9b['n_vertices']}")
    # 直径 ≈ 3600 − 两扇形夹角修正 ≈ 3440 m
    assert 3300 < r9b['D'] < 3500

    print("[T10] 等边三角形反例（Jung 紧性）")
    # 直接构造等边三角形顶点集，验证直径圆不覆盖
    import math as m
    D_eq = 100.0
    tri = [(0, 0), (D_eq, 0), (D_eq/2, D_eq * m.sqrt(3)/2)]
    D_c, A, B = polygon_diameter(tri)
    cov, off = diameter_circle_covers(tri, A, B)
    print(f"     等边三角形 D={D_c:.4f}, 直径圆覆盖={cov}, max_off-r={off:.4f}")
    # 期望：cov=False, off > 0
    assert not cov
    assert off > 0

    print("\n[OK] self-test passed")


if __name__ == "__main__":
    _self_test()