# -*- coding: utf-8 -*-
# problem1_v4.py
# 第一问：算法实现（修正版）
#
# 相对 v3.5.6.1 的关键修正：
#   1. 扇形方向：用 cross-product 直接构造扇形内部，方向与示向度一致（不再翻 180°）
#   2. 距离约束：每个检测点 D(S, R_eff)，原点 D(O, R_target)
#   3. 自检：含方向正交测试（验证扇形确实指向 θ 方向）
#   4. 统计：Welzl 最小包围圆 + 直径圆对比，给出 2R*/D、覆盖率
#
# 算法（与"他人思路"一致）：
#   - 几何：Sutherland-Hodgman 多边形裁剪（截半平面 + 截圆盘）
#   - 直径：旋转卡尺（rotating calipers）
#   - MEC：Welzl 随机算法
#
# 用法：
#   python problem1_v4.py                  # 跑自检
#   python problem1_v4.py stats            # 跑统计与画图

import math
import random
import json
import os
from typing import List, Tuple, Optional, Sequence

Vec = Tuple[float, float]
Poly = List[Vec]


# ============================================================
# 几何原语
# ============================================================
class HalfPlane:
    """半平面 n·P <= d（外向法向 n，闭合侧为内侧）。"""
    __slots__ = ('n', 'd')
    def __init__(self, n: Vec, d: float):
        self.n = n
        self.d = d
    def contains(self, P: Vec) -> bool:
        return self.n[0]*P[0] + self.n[1]*P[1] <= self.d + 1e-9


def make_sector_halfplanes(S: Vec, theta_deg: float, eps_deg: float
                           ) -> Tuple[HalfPlane, HalfPlane]:
    """扇形构造：cross-product 形式（修正版 — 含 HalfPlane 符号约定）。

    扇形：点 P 与 S 的连线方向 ∈ [θ−ε, θ+ε]。

    设 u_lo = (cos(θ−ε), sin(θ−ε))，u_hi = (cos(θ+ε), sin(θ+ε))。
    对 P 在扇形内部：
        cross(u_lo, P−S) >= 0   (P 在 u_lo 左侧 = 扇形内部)
        cross(u_hi, P−S) <= 0   (P 在 u_hi 右侧 = 扇形内部)

    改写：
        cross(u, P−S) >= 0
            ⇔ u_x*(P_y−S_y) − u_y*(P_x−S_x) >= 0
            ⇔ (−u_y, u_x)·P >= (−u_y, u_x)·S

    HalfPlane.contains 用 n·P <= d（外向法向）。把不等式"翻"：
        (−u_y, u_x)·P >= (−u_y, u_x)·S
        ⇔ (u_y, −u_x)·P <= (u_y, −u_x)·S
        所以 n_lo = (u_y, −u_x), d_lo = n_lo·S。  ← v4 初版其实是对的

    类似地：cross(u_hi, P−S) <= 0
            ⇔ (u_hi_y, −u_hi_x)·P >= (u_hi_y, −u_hi_x)·S
            ⇔ (−u_hi_y, u_hi_x)·P <= (−u_hi_y, u_hi_x)·S
        n_hi = (−u_hi_y, u_hi_x), d_hi = n_hi·S。

    历史：v4.1 曾把 n_lo 改成 (−u_lo_y, u_lo_x)，但这与 HalfPlane 的 n·P ≤ d 约定反了，
    导致 +x 方向单扇形退化成一个朝 +y 的薄条，扇形反向。已修正。
    """
    lo = math.radians(theta_deg - eps_deg)
    hi = math.radians(theta_deg + eps_deg)
    u_lo = (math.cos(lo), math.sin(lo))
    u_hi = (math.cos(hi), math.sin(hi))
    # 下边界：n_lo = (u_lo_y, −u_lo_x)，d_lo = n_lo·S
    n_lo = (u_lo[1], -u_lo[0])
    # 上边界：n_hi = (−u_hi_y, u_hi_x)，d_hi = n_hi·S
    n_hi = (-u_hi[1], u_hi[0])
    d_lo = n_lo[0]*S[0] + n_lo[1]*S[1]
    d_hi = n_hi[0]*S[0] + n_hi[1]*S[1]
    return HalfPlane(n_lo, d_lo), HalfPlane(n_hi, d_hi)


def hpi_intersect(poly: Poly, halfplanes: Sequence[HalfPlane]
                  ) -> Optional[Poly]:
    """Sutherland-Hodgman：给定初始凸多边形 poly，依次用各半平面裁剪，返回 CCW 凸多边形。"""
    for hp in halfplanes:
        if poly is None or len(poly) == 0:
            return None
        new_poly: List[Vec] = []
        n, d = hp.n, hp.d
        m = len(poly)
        for i in range(m):
            cur = poly[i]
            prv = poly[i - 1]
            cur_in = (n[0]*cur[0] + n[1]*cur[1]) <= d + 1e-9
            prv_in = (n[0]*prv[0] + n[1]*prv[1]) <= d + 1e-9
            if cur_in:
                if not prv_in:
                    new_poly.append(_seg_line_intersect(prv, cur, n, d))
                new_poly.append(cur)
            elif prv_in:
                new_poly.append(_seg_line_intersect(prv, cur, n, d))
        poly = new_poly
    if poly is None or len(poly) < 3:
        return None
    return poly


def _bbox_polygon(bbox: float) -> Poly:
    """返回一个以原点为中心、边长 2*bbox 的 CCW 正方形（用于无初始多边形时）。"""
    b = float(bbox)
    return [(-b, -b), (b, -b), (b, b), (-b, b)]


def halfplane_intersect(halfplanes: Sequence[HalfPlane], bbox: float = 5000.0
                        ) -> Optional[Poly]:
    """从 bbox 正方形起步，对所有半平面求交，返回 CCW 凸多边形。"""
    return hpi_intersect(_bbox_polygon(bbox), halfplanes)


def _seg_line_intersect(p1: Vec, p2: Vec, n: Vec, d: float) -> Vec:
    """线段 p1→p2 与直线 n·P = d 的交点。"""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    denom = n[0]*dx + n[1]*dy
    if abs(denom) < 1e-12:
        return p1
    t = (d - n[0]*p1[0] - n[1]*p1[1]) / denom
    return (p1[0] + t*dx, p1[1] + t*dy)


def clip_polygon_by_disk(poly: Poly, c: Vec, r: float, N: int = 64
                         ) -> Optional[Poly]:
    """用 N 条线段近似圆盘 |P−c| ≤ r，截多边形 poly（增量式：保留之前的裁剪结果）。

    输入的 poly 应当已是当前求交结果；此函数只是追加 N 个半平面继续裁剪 poly，
    而**不是**重新从 bbox 起步。
    """
    if poly is None or len(poly) < 3:
        return None
    hps = []
    for k in range(N):
        a = 2 * math.pi * k / N
        n = (math.cos(a), math.sin(a))
        d = r + n[0]*c[0] + n[1]*c[1]
        hps.append(HalfPlane(n, d))
    return hpi_intersect(poly, hps)


# ============================================================
# 多边形工具：直径与最小包围圆
# ============================================================
def polygon_diameter(poly: Poly) -> Tuple[float, Vec, Vec]:
    """返回 (D, A, B)。O(n²) 暴力（多边形顶点数小，绝对正确）。
    适用 n ≤ 30 左右，定位多边形实际顶点数 ≤ 8。"""
    n = len(poly)
    if n < 2:
        p = poly[0] if poly else (0.0, 0.0)
        return 0.0, p, p
    best_d2 = -1.0
    best_i, best_j = 0, 1
    for i in range(n):
        xi, yi = poly[i]
        for j in range(i + 1, n):
            dx = xi - poly[j][0]
            dy = yi - poly[j][1]
            d2 = dx*dx + dy*dy
            if d2 > best_d2:
                best_d2, best_i, best_j = d2, i, j
    return math.sqrt(best_d2), poly[best_i], poly[best_j]


def _in_circle(pts: Sequence[Vec], c: Vec, r2: float) -> bool:
    return all((p[0]-c[0])**2 + (p[1]-c[1])**2 <= r2 + 1e-9 for p in pts)


def _circle_from_2(a: Vec, b: Vec) -> Tuple[Vec, float]:
    c = ((a[0]+b[0])*0.5, (a[1]+b[1])*0.5)
    r2 = (a[0]-c[0])**2 + (a[1]-c[1])**2
    return c, r2


def _circle_from_3(a: Vec, b: Vec, c: Vec) -> Optional[Tuple[Vec, float]]:
    ax, ay = a; bx, by = b; cx, cy = c
    d = 2 * (ax*(by - cy) + bx*(cy - ay) + cx*(ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax*ax + ay*ay)*(by - cy) + (bx*bx + by*by)*(cy - ay) + (cx*cx + cy*cy)*(ay - by)) / d
    uy = ((ax*ax + ay*ay)*(cx - bx) + (bx*bx + by*by)*(ax - cx) + (cx*cx + cy*cy)*(bx - ax)) / d
    ctr = (ux, uy)
    r2 = (ax - ux)**2 + (ay - uy)**2
    return ctr, r2


def mec_welzl(points: Sequence[Vec]) -> Tuple[Vec, float]:
    """Welzl 最小包围圆（迭代版，O(n) 期望时间）。返回 (c, r)。"""
    import sys
    sys.setrecursionlimit(10000)
    P = list(points)
    random.shuffle(P)

    def circle_trivial(R: Sequence[Vec]) -> Tuple[Vec, float]:
        if len(R) == 0:
            return (0.0, 0.0), 0.0
        if len(R) == 1:
            return R[0], 0.0
        if len(R) == 2:
            return _circle_from_2(R[0], R[1])
        c, r2 = _circle_from_3(R[0], R[1], R[2])
        if c is None:
            return _circle_from_2(R[0], R[1])[0], max(
                (R[0][0]-R[1][0])**2 + (R[0][1]-R[1][1])**2,
                (R[0][0]-R[2][0])**2 + (R[0][1]-R[2][1])**2,
                (R[1][0]-R[2][0])**2 + (R[1][1]-R[2][1])**2,
            ) * 0.25
        return c, r2

    def mec(P: List[Vec], R: List[Vec], n: int) -> Tuple[Vec, float]:
        if n == 0 or len(R) == 3:
            return circle_trivial(R)
        p = P[n - 1]
        c, r2 = mec(P, R, n - 1)
        if (p[0]-c[0])**2 + (p[1]-c[1])**2 <= r2 + 1e-9:
            return c, r2
        return mec(P, R + [p], n - 1)

    c, r2 = mec(P, [], len(P))
    return c, math.sqrt(r2)


def diameter_circle_covers(poly: Poly, A: Vec, B: Vec
                           ) -> Tuple[bool, float, Tuple[Vec, float]]:
    """判断以 AB 为直径的圆是否能覆盖多边形，返回 (covered, off, (c, r_mec))。
    off = max_i |P_i − mid| − D/2，即最大偏移距离（>0 表示不覆盖）。
    同时计算 Welzl 最小包围圆 (c, r_mec)。"""
    mid = ((A[0] + B[0]) * 0.5, (A[1] + B[1]) * 0.5)
    D = math.hypot(A[0]-B[0], A[1]-B[1])
    R = D / 2
    off = -1e9
    for p in poly:
        d = math.hypot(p[0]-mid[0], p[1]-mid[1])
        off = max(off, d - R)
    covered = off <= 1e-9
    c_mec, r_mec = mec_welzl(poly)
    return covered, off, (c_mec, r_mec)


# ============================================================
# 主算法：求定位多边形、直径、覆盖判据
# ============================================================
def localization_polygon(dets: Sequence[Vec], thetas: Sequence[float],
                         eps_deg: float = 1.0,
                         R_eff: float = 1500.0,
                         R_target: float = 1800.0,
                         N_disk: int = 64) -> Optional[Poly]:
    """构造定位多边形 P = ∩扇形_i ∩ D(S_i, R_eff) ∩ D(O, R_target)。

    几何含义：
      - 扇形_i：示向度 θ_i ± ε
      - D(S_i, R_eff)：检测点有效接收距离约束（默认 1500）
      - D(O, R_target)：目标区域约束（默认 1800）

    v4 顺序：先做扇形半平面求交 → 再裁剪 R_target 圆盘 → 再对每个 S_i 裁剪 R_eff 圆盘。
    此顺序对 n>=2 的多扇形情形正确（这是主用情形）；单扇形（n=1）情形下
    64 弦逼近圆盘对窄扇形有近似误差，导致 D 异常——本函数返回 None 时调用方应跳过。
    """
    if len(dets) == 0:
        return None

    hps = []
    for S, th in zip(dets, thetas):
        hp_lo, hp_hi = make_sector_halfplanes(S, th, eps_deg)
        hps.extend([hp_lo, hp_hi])

    poly = halfplane_intersect(hps, bbox=5000.0)
    if poly is None:
        return None

    poly = clip_polygon_by_disk(poly, (0.0, 0.0), R_target, N_disk)
    if poly is None:
        return None

    for S in dets:
        poly = clip_polygon_by_disk(poly, S, R_eff, N_disk)
        if poly is None:
            return None

    return poly


def solve_problem_1(dets: Sequence[Vec], thetas: Sequence[float],
                    eps_deg: float = 1.0,
                    R_eff: float = 1500.0,
                    R_target: float = 1800.0,
                    N_disk: int = 64) -> dict:
    """完整求解第一问。"""
    poly = localization_polygon(dets, thetas, eps_deg, R_eff, R_target, N_disk)
    if poly is None:
        return {
            'D': 0.0, 'R_star': 0.0, 'ratio_2R_D': 0.0,
            'covered': False, 'max_offset': 0.0,
            'A': (0, 0), 'B': (0, 0), 'mec_center': (0, 0), 'mec_radius': 0.0,
            'n_vertices': 0, 'poly': [],
        }
    D, A, B = polygon_diameter(poly)
    covered, off, (c_mec, r_mec) = diameter_circle_covers(poly, A, B)
    return {
        'D': D,
        'R_star': r_mec,
        'ratio_2R_D': 2 * r_mec / D if D > 0 else 0.0,
        'covered': covered,
        'max_offset': off,
        'A': A,
        'B': B,
        'mec_center': c_mec,
        'mec_radius': r_mec,
        'n_vertices': len(poly),
        'poly': poly,
    }


# ============================================================
# 方向正交自检
# ============================================================
def direction_self_check(verbose: bool = True) -> List[str]:
    """关键自检：扇形方向必须与示向度 θ 一致。

    测试：对 θ = 0/45/90/135/180/225/270/315 各取 S = (0, 0)，
    验证以下"内点"在扇形内、"外点"在扇形外。
    """
    log = []
    thetas = [0, 45, 90, 135, 180, 225, 270, 315]
    eps = 1.0
    R_eff = 1500.0
    R_target = 1800.0

    n_pass = 0
    for theta in thetas:
        # 内点：方向 = θ，距离 = 800（远小于 R_eff 和 R_target）
        r_in = 800.0
        theta_in = math.radians(theta)
        P_in = (r_in * math.cos(theta_in), r_in * math.sin(theta_in))
        # 外点：方向 = θ + 180° + ε，距离相同（明确在对面）
        theta_out = math.radians((theta + 180) % 360)
        P_out = (r_in * math.cos(theta_out), r_in * math.sin(theta_out))

        poly = localization_polygon([(0, 0)], [theta], eps, R_eff, R_target, N_disk=32)
        if poly is None:
            log.append(f"θ={theta:3d}°: 扇形为空 ✗")
            continue
        in_in = _point_in_convex_poly(P_in, poly)
        in_out = _point_in_convex_poly(P_out, poly)
        ok = in_in and not in_out
        n_pass += int(ok)
        log.append(f"θ={theta:3d}°: 内点θ方向在内部={in_in}, 反向外点不在内部={not in_out},  {'✓' if ok else '✗'}")
        if verbose:
            print(log[-1])
    log.append(f"\n方向正交自检：{n_pass}/{len(thetas)} 通过")
    return log


def _point_in_convex_poly(P: Vec, poly: Poly) -> bool:
    """判断点是否在凸多边形内（含边界）。多边形须为 CCW 凸。

    对每条边 a→b（CCW 顺序），内点应在有向边的"左侧"：
    cross((b - a), (P - a)) ≥ 0。
    """
    n = len(poly)
    if n < 3:
        return False
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        cross = (b[0]-a[0])*(P[1]-a[1]) - (b[1]-a[1])*(P[0]-a[0])
        if cross < -1e-6:
            return False
    return True


# ============================================================
# 统计与可视化
# ============================================================
def random_config(n: int, seed: int, R_eff: float = 1500.0,
                  R_target: float = 1800.0) -> Tuple[List[Vec], List[float]]:
    """随机生成配置：源在 D(O, R_target) 内均匀采样，n 个检测点散布在源周围。"""
    rng = random.Random(seed)
    # 源位置：在目标区域内均匀
    while True:
        x = rng.uniform(-R_target, R_target)
        y = rng.uniform(-R_target, R_target)
        if x*x + y*y <= R_target*R_target:
            src = (x, y)
            break
    # 检测点：在源周围 R_eff 内均匀（保证能检测到）
    dets = []
    thetas = []
    for _ in range(n):
        # 随机方向
        a = rng.uniform(0, 2*math.pi)
        # 距离：保证 |det − src| ≤ R_eff，但也要随机
        r = rng.uniform(100, R_eff)
        det = (src[0] + r*math.cos(a), src[1] + r*math.sin(a))
        # 示向度：从 det 指向 src
        theta = (math.degrees(math.atan2(src[1]-det[1], src[0]-det[0])) + 360) % 360
        # 加 ±ε 误差（最坏情况）
        theta = (theta + rng.uniform(-1.0, 1.0)) % 360
        dets.append(det)
        thetas.append(theta)
    return dets, thetas


def run_stats(N_per: int = 500, seed_base: int = 42) -> dict:
    """对每个 n 跑 N_per 例随机仿真，统计 2R*/D、覆盖率、n_vertices 分布。"""
    summary = {}
    for n in [2, 3, 4, 5, 6, 8, 10, 15]:
        ratios = []
        covered_count = 0
        vertex_counts = []
        D_list = []
        R_list = []
        for k in range(N_per):
            dets, thetas = random_config(n, seed_base + 1000*n + k)
            res = solve_problem_1(dets, thetas, eps_deg=1.0,
                                  R_eff=1500.0, R_target=1800.0, N_disk=32)
            D = res['D']
            if D < 1.0:
                continue
            ratios.append(res['ratio_2R_D'])
            covered_count += int(res['covered'])
            vertex_counts.append(res['n_vertices'])
            D_list.append(D)
            R_list.append(res['mec_radius'])
        if not ratios:
            continue
        import statistics
        ratios_sorted = sorted(ratios)
        summary[n] = {
            'N_valid': len(ratios),
            'mean_2R_D': statistics.mean(ratios),
            'median_2R_D': statistics.median(ratios),
            'p95_2R_D': ratios_sorted[int(0.95*len(ratios_sorted))],
            'max_2R_D': max(ratios),
            'cover_rate': covered_count / len(ratios),
            'mean_D': statistics.mean(D_list),
            'mean_R': statistics.mean(R_list),
            'mean_vertices': statistics.mean(vertex_counts),
            'ratios': ratios,
        }
    return summary


# ============================================================
# 自检 + 主入口
# ============================================================
def _self_test():
    print("=" * 60)
    print("第一问：算法自检（v4）")
    print("=" * 60)

    # T0: 几何验证：单扇形在 +x 方向（θ=0°）应严格不包含 (-800, 0) 等反向点
    print("\n[T0] 单扇形几何验证（θ=0°，反向外点必须在多边形外）")
    poly0 = localization_polygon([(0, 0)], [0.0], 1.0, 1500.0, 1800.0, N_disk=32)
    print(f"  多边形顶点数 = {len(poly0)}")
    print(f"  全部顶点: {poly0}")
    in_fwd = _point_in_convex_poly((800, 0), poly0)   # +x 方向 800 m 必在内部
    in_bwd = _point_in_convex_poly((-800, 0), poly0)  # -x 方向 800 m 必不在内部
    in_lat = _point_in_convex_poly((0, 800), poly0)   # +y 方向 800 m 必不在内部（偏 90°）
    print(f"  (800, 0)  内? = {in_fwd}  (应 True)")
    print(f"  (-800, 0) 内? = {in_bwd}  (应 False)")
    print(f"  (0, 800)  内? = {in_lat}  (应 False)")

    # 直接用 HalfPlane.contains 验证 - 不依赖多边形顶点
    hp_lo, hp_hi = make_sector_halfplanes((0, 0), 0.0, 1.0)
    for label, P in [("(800,0)", (800, 0)), ("(-800,0)", (-800, 0)),
                     ("(0,800)", (0, 800)), ("(0,-800)", (0, -800))]:
        in_lo = hp_lo.contains(P)
        in_hi = hp_hi.contains(P)
        in_sector = in_lo and in_hi
        print(f"  HalfPlane 测 {label}: lo={in_lo}, hi={in_hi}, 扇形内={in_sector}")

    assert in_fwd and not in_bwd and not in_lat, "T0 单扇形几何失败"

    # T1: 方向正交自检（核心，v3 bug 漏检项）
    print("\n[T1] 方向正交自检（8 角度）")
    log = direction_self_check(verbose=True)
    n_pass = sum(1 for line in log if '✓' in line and '通过' not in line)
    print(f"\n  => {n_pass}/8 通过")
    assert n_pass == 8, f"方向正交 8/8 必须全过，实测 {n_pass}/8"
    print()

    # T2: 3 个协调算例：三个检测点都指向同一源 (50, 30)
    print("[T2] 协调算例（n=3，共源于 (50, 30)）")
    import math as m
    src = (50.0, 30.0)
    dets = [(0.0, 0.0), (100.0, 0.0), (50.0, 100.0)]
    thetas = [
        m.degrees(m.atan2(src[1] - d[1], src[0] - d[0])) % 360
        for d in dets
    ]
    print(f"  thetas = {[f'{t:.2f}°' for t in thetas]}")
    res = solve_problem_1(dets, thetas, eps_deg=1.0,
                          R_eff=1500.0, R_target=1800.0, N_disk=32)
    print(f"  D = {res['D']:.2f} m, R* = {res['mec_radius']:.2f} m, "
          f"2R*/D = {res['ratio_2R_D']:.4f}, covered = {res['covered']}")
    # 源在定位多边形内是基本要求
    assert _point_in_convex_poly(src, res['poly']), "源必须在定位多边形内"

    # T3: 几何反向扇形（θ=90° vs θ=270°，应为空）
    print("\n[T3] 几何反向扇形（n=2, θ=90° 与 θ=270°，应为空）")
    res = solve_problem_1([(0.0, 0.0), (500.0, 0.0)], [90.0, 270.0],
                          eps_deg=1.0, R_eff=1500.0, R_target=1800.0, N_disk=32)
    print(f"  D = {res['D']:.2f} m, n_vertices = {res['n_vertices']}")
    assert res['D'] < 1.0 and res['n_vertices'] == 0, "几何反向扇形应有空交集"

    # T4: 等边三角反例（Jung 紧）
    print("\n[T4] 等边三角反例（Jung 紧）")
    D_eq = 100.0
    tri = [(0.0, 0.0), (D_eq, 0.0), (D_eq / 2, D_eq * m.sqrt(3) / 2)]
    D, A, B = polygon_diameter(tri)
    cov, off, _ = diameter_circle_covers(tri, A, B)
    print(f"  D = {D:.2f}, 覆盖 = {cov}, off = {off:.3f}")
    assert not cov and off > 0

    # T5: 单扇形（退化）：D ≈ R_eff（扇形从原点向 R_eff 圆盘边界延伸）
    print("\n[T5] 单扇形（n=1）")
    res = solve_problem_1([(0.0, 0.0)], [45.0], eps_deg=1.0,
                          R_eff=1500.0, R_target=1800.0, N_disk=64)
    print(f"  D = {res['D']:.2f} m, 2R*/D = {res['ratio_2R_D']:.4f}")
    # 扇形端点距离 = R_eff
    assert abs(res['D'] - 1500.0) < 50.0, f"单扇形 D 应接近 R_eff=1500, 实测 {res['D']}"

    # T6: 统计（覆盖率随 n 变化，理论上限 Jung 2/√3 ≈ 1.1547）
    print("\n[T6] 覆盖率随 n 变化（统计验证）")
    summary = run_stats(N_per=300, seed_base=42)
    for n in sorted(summary.keys()):
        s = summary[n]
        print(f"  n={n:2d}: N={s['N_valid']:3d}, 2R*/D 中位={s['median_2R_D']:.4f}, "
              f"覆盖={s['cover_rate']*100:.1f}%, 平均D={s['mean_D']:.0f} m")

    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'stats':
        s = run_stats(N_per=500)
        # 写统计到文件
        out = {n: {k: v for k, v in d.items() if k != 'ratios'} for n, d in s.items()}
        with open(os.path.join(os.path.dirname(__file__), 'stats.json'), 'w') as f:
            json.dump(out, f, indent=2, default=str)
        # 也保存所有 ratios 用于画图
        with open(os.path.join(os.path.dirname(__file__), 'ratios.json'), 'w') as f:
            json.dump({n: d['ratios'] for n, d in s.items()}, f)
        print("统计已写入 stats.json / ratios.json")
    else:
        _self_test()
        print("\n全部自检通过。")