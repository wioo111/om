# -*- coding: utf-8 -*-
r"""问题一 v5 —— 定位区域的几何刻画、直径与"直径圆覆盖判据"。

相对 v4 的关键修正
------------------
1. Jung 定理方向：D/2 <= R* <= D/sqrt(3)，即 1 <= q = 2R*/D <= 2/sqrt(3)。
   直径圆（半径 D/2、圆心为直径端点中点）覆盖定位区域 <=> R* = D/2 <=> q = 1。
2. 圆盘约束为**外切正 N 边形外逼近**（不是内接多边形）：
   最大径向外扩 Delta r = r * (sec(pi/N) - 1)。
   正式计算统一 N = 256（1500 m 时 0.113 m）。
3. 检测点必须位于目标区域 Omega 内（采样逻辑修正）。
4. 精确定位区域是**凸集**，边界可由直线段与圆弧共同组成；
   数值上把圆约束换成外切正 N 边形，才得到"凸多边形近似"。
5. 去掉"顶点数 <= 8""n>=3 才可能不覆盖"等无根据的一般性断言。

作者：v5 重构
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

Vec = Tuple[float, float]
Poly = List[Vec]
HalfPlane = Tuple[float, float, float]   # (nx, ny, d) 表示 nx*x + ny*y <= d

# ---------------------------------------------------------------- 常量
EPS_DEG = 1.0            # 示向度误差（度）
R_TARGET = 1800.0        # 目标区域半径 Omega = {|P| <= 1800}
R_EFF = 1500.0           # 有效接收半径上界（未知半径的最坏取值）
N_DISK = 256             # 圆盘外切正 N 边形的边数（正式计算）
TOL_LIN = 1e-9           # 半平面包含判据的线性容差（米）
TOL_COVER = 1e-6         # "覆盖"判据容差（米）
SIMPLIFY_TOL = 1e-3      # 凸多边形顶点简化容差（米）
ORIGIN: Vec = (0.0, 0.0)

# Jung 定理常数
JUNG_Q = 2.0 / math.sqrt(3.0)      # 1.1547005383792515


# ================================================================ 角度工具
def wrap_deg(a: float) -> float:
    r"""把角度归一化到 [-180, 180)。"""
    return a - 360.0 * math.floor((a + 180.0) / 360.0)


# ================================================================ 圆盘逼近误差
def disk_outer_error(r: float, N: int) -> float:
    r"""外切正 N 边形相对圆盘的最大径向外扩：Delta r = r (sec(pi/N) - 1)。

    半平面 n_k . P <= r + n_k . c（k = 0..N-1）把圆盘 {|P-c| <= r} 包在内部，
    得到的是**包含圆盘的最小外切正 N 边形**，其顶点半径为 r / cos(pi/N)。
    """
    if N <= 2:
        raise ValueError("N 必须 >= 3")
    return r * (1.0 / math.cos(math.pi / N) - 1.0)


# ================================================================ 扇形半平面
def sector_halfplanes(S: Vec, theta_deg: float, eps_deg: float
                      ) -> Tuple[HalfPlane, HalfPlane]:
    r"""扇形 {P : angle(P - S) in [theta - eps, theta + eps]} 的两个半平面。

    用叉积形式构造（方向与示向度严格一致）：
        cross(u_lo, P-S) >= 0  且  cross(u_hi, P-S) <= 0
    其中 u_lo = dir(theta - eps), u_hi = dir(theta + eps)。
    统一写成 n . P <= d 的形式返回。
    """
    lo = math.radians(theta_deg - eps_deg)
    hi = math.radians(theta_deg + eps_deg)
    ulo = (math.cos(lo), math.sin(lo))
    uhi = (math.cos(hi), math.sin(hi))
    # 下边界（左侧）：cross(u_lo, P-S) >= 0  <=>  (u_lo_y, -u_lo_x) . P <= (u_lo_y,-u_lo_x).S
    n_lo = (ulo[1], -ulo[0], ulo[1] * S[0] - ulo[0] * S[1])
    # 上边界（右侧）：cross(u_hi, P-S) <= 0  <=>  (-u_hi_y, u_hi_x) . P <= (-u_hi_y, u_hi_x).S
    n_hi = (-uhi[1], uhi[0], -uhi[1] * S[0] + uhi[0] * S[1])
    return n_lo, n_hi


def point_in_sector(P: Vec, S: Vec, theta_deg: float, eps_deg: float) -> bool:
    hp_lo, hp_hi = sector_halfplanes(S, theta_deg, eps_deg)
    return (_le(P, hp_lo) and _le(P, hp_hi))


def _le(P: Vec, hp: HalfPlane) -> bool:
    return hp[0] * P[0] + hp[1] * P[1] <= hp[2] + TOL_LIN


# ================================================================ 凸多边形裁剪
def _seg_line_intersect(p1: Vec, p2: Vec, hp: HalfPlane) -> Vec:
    nx, ny, d = hp
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    denom = nx * dx + ny * dy
    if abs(denom) < 1e-15:
        return p1
    t = (d - nx * p1[0] - ny * p1[1]) / denom
    return (p1[0] + t * dx, p1[1] + t * dy)


def simplify_convex(poly: Poly, tol: float = SIMPLIFY_TOL) -> Poly:
    r"""删除"几乎落在邻点连线上的顶点"。凸多边形的这种删除只把区域缩小 <= tol，
    不影响任何后续量（D、R*）超过 tol 量级。

    目的：连续被 256 条切线裁切时，顶点数会累积膨胀；这里把它压回真实几何规模。
    """
    pts = list(poly)
    if len(pts) < 3:
        return pts
    changed = True
    while changed and len(pts) > 3:
        changed = False
        i = 0
        while i < len(pts) and len(pts) > 3:
            a = pts[i - 1]
            b = pts[i]
            c = pts[(i + 1) % len(pts)]
            ex, ey = c[0] - a[0], c[1] - a[1]
            L = math.hypot(ex, ey)
            if L < 1e-12:
                pts.pop(i)
                changed = True
                continue
            cross = ex * (b[1] - a[1]) - ey * (b[0] - a[0])
            if abs(cross) / L <= tol:
                pts.pop(i)
                changed = True
            else:
                i += 1
    return pts


def clip_halfplane(poly: Poly, hp: HalfPlane) -> Optional[Poly]:
    r"""Sutherland-Hodgman：用单个半平面裁剪凸多边形（CCW）。"""
    if not poly:
        return None
    nx, ny, d = hp
    m = len(poly)
    vals = [nx * x + ny * y for (x, y) in poly]
    out: Poly = []
    for i in range(m):
        cur = poly[i]
        prv = poly[i - 1]
        cin = vals[i] <= d + TOL_LIN
        pin = vals[i - 1] <= d + TOL_LIN
        if cin:
            if not pin:
                out.append(_seg_line_intersect(prv, cur, hp))
            out.append(cur)
        elif pin:
            out.append(_seg_line_intersect(prv, cur, hp))
    if len(out) < 3:
        return None
    # 去掉相邻重复点
    ded: Poly = []
    for p in out:
        if ded and abs(p[0] - ded[-1][0]) < 1e-12 and abs(p[1] - ded[-1][1]) < 1e-12:
            continue
        ded.append(p)
    if len(ded) > 1 and abs(ded[0][0] - ded[-1][0]) < 1e-12 and abs(ded[0][1] - ded[-1][1]) < 1e-12:
        ded.pop()
    if len(ded) < 3:
        return None
    return ded


def clip_halfplanes(poly: Poly, hps: Sequence[HalfPlane]) -> Optional[Poly]:
    for hp in hps:
        if poly is None:
            return None
        poly = clip_halfplane(poly, hp)
        if poly is None:
            return None
    return poly


def bbox_polygon(half: float) -> Poly:
    return [(-half, -half), (half, -half), (half, half), (-half, half)]


# ================================================================ 圆盘裁剪
def max_dist_from(poly: Poly, c: Vec) -> float:
    return max(math.hypot(p[0] - c[0], p[1] - c[1]) for p in poly)


def disk_tangent_halfplanes(c: Vec, r: float, N: int,
                            phase: float = 0.0) -> List[HalfPlane]:
    r"""圆盘 {|P-c| <= r} 的外切正 N 边形的 N 条切线（法向单位向量均匀分布）。"""
    out: List[HalfPlane] = []
    for k in range(N):
        a = phase + 2.0 * math.pi * k / N
        nx, ny = math.cos(a), math.sin(a)
        out.append((nx, ny, r + nx * c[0] + ny * c[1]))
    return out


def clip_disk(poly: Poly, c: Vec, r: float, N: int = N_DISK) -> Optional[Poly]:
    r"""把凸多边形裁到圆盘 {|P-c| <= r} 的外切正 N 边形内。

    数学上等价于施加全部 N 条切线半平面：

    * 快速路径：若所有顶点满足 |P-c| <= r，由凸性整个多边形都在圆盘内，
      任何切线都不可能切割 —— 直接返回。
    * 自适应路径：只有当顶点 P 满足 |P-c| > r 时，法向角 alpha 的切线才可能
      切割它，且必须满足
              |P-c| * cos(alpha - angle(P-c)) > r
          <=> |alpha - angle(P-c)| < arccos(r/|P-c|) 。
      于是只需在若干"角度窗口"内取切线（按 2*pi/N 的同一网格），窗口外的切线
      对原多边形无切割作用，裁剪后多边形只会更小，故结论完全等价。
    该路径把 256 条切线缩减到几十条，是第二问大批量求解的关键加速。
    """
    if poly is None or len(poly) < 3:
        return None
    step = 2.0 * math.pi / N
    dists = [math.hypot(p[0] - c[0], p[1] - c[1]) for p in poly]
    dmax = max(dists)
    if dmax <= r:
        return poly

    windows = []
    for p, d in zip(poly, dists):
        if d <= r:
            continue
        half = math.acos(min(1.0, r / d)) + step      # 多留一个网格步长
        ang = math.atan2(p[1] - c[1], p[0] - c[0])
        windows.append([ang - half, ang + half])

    # 把窗口平移到同一 2*pi 分支后合并
    windows.sort()
    base = windows[0][0]
    norm = []
    for lo_a, hi_a in windows:
        while lo_a - base > math.pi:
            lo_a -= 2.0 * math.pi
            hi_a -= 2.0 * math.pi
        while lo_a - base < -math.pi:
            lo_a += 2.0 * math.pi
            hi_a += 2.0 * math.pi
        norm.append([lo_a, hi_a])
    norm.sort()
    merged: List[List[float]] = []
    for w in norm:
        if merged and w[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], w[1])
        else:
            merged.append([w[0], w[1]])

    hps: List[HalfPlane] = []
    seen = set()
    for lo_a, hi_a in merged:
        k0 = int(math.floor(lo_a / step)) - 1
        k1 = int(math.ceil(hi_a / step)) + 1
        for k in range(k0, k1 + 1):
            kk = k % N
            if kk in seen:
                continue
            seen.add(kk)
            a = kk * step
            nx, ny = math.cos(a), math.sin(a)
            hps.append((nx, ny, r + nx * c[0] + ny * c[1]))

    res = clip_halfplanes(poly, hps)
    if res is None:
        return None
    return simplify_convex(res, SIMPLIFY_TOL)


def clip_disk_complement(poly: Poly, c: Vec, r: float, N: int = N_DISK) -> Optional[Poly]:
    r"""裁到圆盘外部 {|P-c| >= r} 的内切正 N 边形的补（用于"距离 > 1000 m"这类约束）。

    返回 None 表示结果为空。注意：结果为非凸，本函数只在调用方明确需要时使用。
    """
    hps = []
    for k in range(N):
        a = 2.0 * math.pi * k / N
        nx, ny = -math.cos(a), -math.sin(a)
        hps.append((nx, ny, -r - nx * c[0] - ny * c[1]))
    return clip_halfplanes(poly, hps)


# ================================================================ 定位区域
def localization_region(dets: Sequence[Vec], thetas: Sequence[float],
                        eps_deg: float = EPS_DEG,
                        R_eff: float = R_EFF,
                        R_target: float = R_TARGET,
                        N_disk: int = N_DISK) -> Optional[Poly]:
    r"""构造定位区域

        L = Omega cap (cap_i Disk(S_i, R_eff)) cap (cap_i Sector(S_i, theta_i, eps))

    **精确可行域是凸集**（扇形、圆盘都是凸集），其边界可由直线段与圆弧共同组成；
    数值上把圆盘换成外切正 N 边形后，得到的才是凸多边形（外逼近）。
    """
    if len(dets) == 0:
        return None
    hps: List[HalfPlane] = []
    for S, th in zip(dets, thetas):
        lo, hi = sector_halfplanes(S, th, eps_deg)
        hps.append(lo)
        hps.append(hi)
    # 先用目标圆域把无界扇形裁剪掉：初始盒子取 Omega 的外接正方形即可，
    # 既保证包含全部可行点，又让后续圆盘裁剪的顶点数很少（性能关键）。
    poly = clip_halfplanes(bbox_polygon(R_target * 1.0001), hps)
    if poly is None:
        return None
    poly = clip_disk(poly, ORIGIN, R_target, N_disk)
    if poly is None:
        return None
    for S in dets:
        poly = clip_disk(poly, S, R_eff, N_disk)
        if poly is None:
            return None
    return simplify_convex(poly, SIMPLIFY_TOL)


# ================================================================ 直径与 MEC
def polygon_diameter(poly: Poly) -> Tuple[float, Vec, Vec]:
    r"""凸多边形直径（顶点对全扫描，m 很小时等价于旋转卡壳且绝对正确）。"""
    n = len(poly)
    if n < 2:
        p = poly[0] if poly else (0.0, 0.0)
        return 0.0, p, p
    best = -1.0
    bi, bj = 0, 1
    for i in range(n):
        xi, yi = poly[i]
        for j in range(i + 1, n):
            dx = xi - poly[j][0]
            dy = yi - poly[j][1]
            d2 = dx * dx + dy * dy
            if d2 > best:
                best, bi, bj = d2, i, j
    return math.sqrt(best), poly[bi], poly[bj]


def _circle_from_2(a: Vec, b: Vec) -> Tuple[Vec, float]:
    c = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
    return c, (a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2


def _circle_from_3(a: Vec, b: Vec, c: Vec) -> Optional[Tuple[Vec, float]]:
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) +
          (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) +
          (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), (ax - ux) ** 2 + (ay - uy) ** 2


def mec_welzl(points: Sequence[Vec], seed: int = 12345) -> Tuple[Vec, float]:
    r"""Welzl 最小包围圆（迭代实现，使用局部随机源，不污染全局随机状态）。"""
    rng = random.Random(seed)
    P = list(points)
    rng.shuffle(P)
    cache: dict = {}

    def solve(n: int, R: tuple) -> Tuple[Vec, float]:
        key = (n, R)
        if key in cache:
            return cache[key]
        if n == 0 or len(R) == 3:
            if len(R) == 0:
                res = ((0.0, 0.0), 0.0)
            elif len(R) == 1:
                res = (R[0], 0.0)
            elif len(R) == 2:
                res = _circle_from_2(R[0], R[1])
            else:
                got = _circle_from_3(R[0], R[1], R[2])
                if got is None:
                    m = max((R[0][0] - R[1][0]) ** 2 + (R[0][1] - R[1][1]) ** 2,
                            (R[0][0] - R[2][0]) ** 2 + (R[0][1] - R[2][1]) ** 2,
                            (R[1][0] - R[2][0]) ** 2 + (R[1][1] - R[2][1]) ** 2)
                    res = (_circle_from_2(R[0], R[1])[0], m * 0.25)
                else:
                    res = got
            cache[key] = res
            return res
        p = P[n - 1]
        c, r2 = solve(n - 1, R)
        if (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 <= r2 + 1e-9:
            cache[key] = (c, r2)
            return c, r2
        res = solve(n - 1, R + (p,))
        cache[key] = res
        return res

    import sys
    sys.setrecursionlimit(100000)
    c, r2 = solve(len(P), ())
    return c, math.sqrt(max(r2, 0.0))


def polygon_area(poly: Poly) -> float:
    if poly is None or len(poly) < 3:
        return 0.0
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


# ================================================================ 完整分析
def analyze_region(poly: Optional[Poly]) -> dict:
    r"""对定位多边形求 D、直径端点、MEC、覆盖判据与 q = 2R*/D。

    覆盖判据（covered）：以 AB 为直径的圆（圆心 C=(A+B)/2，半径 D/2）覆盖全部顶点。
      - off = max_P |P - C| - D/2，off <= 0 即覆盖。
    定理（本项目统一口径）：covered <=> R* = D/2 <=> q = 1。
      证明：covered => 存在半径 D/2 的圆覆盖该集 => R* <= D/2；
            另一方面 A、B 都在集内且 |AB| = D，任何覆盖圆半径 >= D/2 => R* >= D/2。
            故 covered => R* = D/2。反之若 R* = D/2，达到该半径的覆盖圆必须同时包含
            A、B，半径恰为 |AB|/2 的覆盖圆圆心必为 AB 中点，故 D(C, D/2) 覆盖全集的 MEC
            半径恰为 D/2 且圆心为 C，于是全集被其覆盖。
    """
    empty = {
        'poly': [], 'D': 0.0, 'A': (0.0, 0.0), 'B': (0.0, 0.0),
        'C': (0.0, 0.0), 'R_star': 0.0, 'mec_center': (0.0, 0.0),
        'q': 0.0, 'off': 0.0, 'covered': False, 'n_vertices': 0,
        'area': 0.0, 'is_empty': True,
    }
    if poly is None or len(poly) < 3:
        return empty
    D, A, B = polygon_diameter(poly)
    C = ((A[0] + B[0]) * 0.5, (A[1] + B[1]) * 0.5)
    R = D * 0.5
    off = max_dist_from(poly, C) - R
    covered = (off <= TOL_COVER)
    mc, r_star = mec_welzl(poly)
    return {
        'poly': poly, 'D': D, 'A': A, 'B': B, 'C': C,
        'R_star': r_star, 'mec_center': mc,
        'q': (2.0 * r_star / D) if D > 0 else 0.0,
        'off': off, 'covered': covered,
        'n_vertices': len(poly), 'area': polygon_area(poly),
        'is_empty': False,
    }


def solve(dets: Sequence[Vec], thetas: Sequence[float],
          eps_deg: float = EPS_DEG, R_eff: float = R_EFF,
          R_target: float = R_TARGET, N_disk: int = N_DISK) -> dict:
    poly = localization_region(dets, thetas, eps_deg, R_eff, R_target, N_disk)
    return analyze_region(poly)


# ================================================================ 采样工具
def sample_uniform_disk(rng: random.Random, R: float) -> Vec:
    r"""在 {|P| <= R} 内均匀采样。"""
    while True:
        x = rng.uniform(-R, R)
        y = rng.uniform(-R, R)
        if x * x + y * y <= R * R:
            return (x, y)


def random_scene(n: int, rng: random.Random,
                 R_eff: float = R_EFF, R_target: float = R_TARGET,
                 eps_deg: float = EPS_DEG,
                 r_min: float = 5.0, max_try: int = 400) -> dict:
    r"""随机生成一个"n 个检测点 + 一个源"的场景，并**强制所有检测点位于 Omega 内**。

    约束：
      G        在 Omega 内均匀；
      S_i      在 Omega 内，且 5 < |S_i - G| <= R_eff（保证在 S_i 能读到示向度）；
      theta_i  = wrap(atan2(G - S_i) + e_i)，e_i ~ U[-eps, +eps]。
    """
    G = sample_uniform_disk(rng, R_target)
    dets: List[Vec] = []
    thetas: List[float] = []
    for _ in range(n):
        placed = False
        for _t in range(max_try):
            a = rng.uniform(0.0, 2.0 * math.pi)
            r = rng.uniform(r_min, R_eff)
            S = (G[0] + r * math.cos(a), G[1] + r * math.sin(a))
            if S[0] * S[0] + S[1] * S[1] > R_target * R_target:
                continue                      # 检测点必须在目标区域内
            if math.hypot(S[0] - G[0], S[1] - G[1]) <= r_min:
                continue                      # 5 m 内读不到示向度
            dets.append(S)
            true_th = math.degrees(math.atan2(G[1] - S[1], G[0] - S[0]))
            e = rng.uniform(-eps_deg, eps_deg)
            thetas.append((true_th + e) % 360.0)
            placed = True
            break
        if not placed:
            return {'G': G, 'dets': [], 'thetas': [], 'ok': False}
    return {'G': G, 'dets': dets, 'thetas': thetas, 'ok': True}


# ================================================================ 点在多边形内
def point_in_convex_poly(P: Vec, poly: Poly, tol: float = 1e-9) -> bool:
    n = len(poly)
    if n < 3:
        return False
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        cross = (b[0] - a[0]) * (P[1] - a[1]) - (b[1] - a[1]) * (P[0] - a[0])
        if cross < -tol:
            return False
    return True


if __name__ == '__main__':
    # 快速冒烟测试
    import time
    rng = random.Random(0)
    t0 = time.perf_counter()
    for _ in range(200):
        sc = random_scene(3, rng)
        if sc['ok']:
            solve(sc['dets'], sc['thetas'])
    print(f"200 次 (n=3, N_disk={N_DISK}) 求解用时 {time.perf_counter() - t0:.3f} s")
    print(f"N=256 时 r=1500 的外扩误差 = {disk_outer_error(1500.0, 256):.4f} m")
    print(f"N=64  时 r=1500 的外扩误差 = {disk_outer_error(1500.0, 64):.4f} m")
    print(f"N=32  时 r=1500 的外扩误差 = {disk_outer_error(1500.0, 32):.4f} m")
