# -*- coding: utf-8 -*-
# problem1_v4_inline.py  （v5 自包含的 Q1 v4 算法副本）
#
# 这是 Q1 v4（problem1_v4.py）的完整内联版，src 在 解题库/第一问/v4/。
# v5 不依赖外部 Q1 v4 源码；本文件已经包含：
#   - HalfPlane、make_sector_halfplanes（楔形张角）
#   - hpi_intersect、halfplane_intersect、clip_polygon_by_disk（Sutherland-Hodgman）
#   - polygon_diameter、mec_welzl、diameter_circle_covers（直径 + Welzl MEC）
#   - localization_polygon、solve_problem_1（定位 + 直径圆覆盖判据）

import math
import random
from typing import List, Tuple, Optional, Sequence

Vec = Tuple[float, float]
Poly = List[Vec]


class HalfPlane:
    """半平面 n·P <= d（外向法向 n，闭合侧为内侧）。"""
    __slots__ = ('n', 'd')

    def __init__(self, n: Vec, d: float):
        self.n = n
        self.d = d

    def contains(self, P: Vec) -> bool:
        return self.n[0] * P[0] + self.n[1] * P[1] <= self.d + 1e-9


def make_sector_halfplanes(S: Vec, theta_deg: float, eps_deg: float
                           ) -> Tuple[HalfPlane, HalfPlane]:
    """扇形构造：点 P 与 S 的连线方向 ∈ [θ−ε, θ+ε]。"""
    lo = math.radians(theta_deg - eps_deg)
    hi = math.radians(theta_deg + eps_deg)
    u_lo = (math.cos(lo), math.sin(lo))
    u_hi = (math.cos(hi), math.sin(hi))
    n_lo = (u_lo[1], -u_lo[0])
    n_hi = (-u_hi[1], u_hi[0])
    d_lo = n_lo[0] * S[0] + n_lo[1] * S[1]
    d_hi = n_hi[0] * S[0] + n_hi[1] * S[1]
    return HalfPlane(n_lo, d_lo), HalfPlane(n_hi, d_hi)


def _seg_line_intersect(p1: Vec, p2: Vec, n: Vec, d: float) -> Vec:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    denom = n[0] * dx + n[1] * dy
    if abs(denom) < 1e-12:
        return p1
    t = (d - n[0] * p1[0] - n[1] * p1[1]) / denom
    return (p1[0] + t * dx, p1[1] + t * dy)


def hpi_intersect(poly: Poly, halfplanes: Sequence[HalfPlane]
                  ) -> Optional[Poly]:
    """Sutherland-Hodgman：给定初始凸多边形 poly，依次用各半平面裁剪。"""
    for hp in halfplanes:
        if poly is None or len(poly) == 0:
            return None
        new_poly: List[Vec] = []
        n, d = hp.n, hp.d
        m = len(poly)
        for i in range(m):
            cur = poly[i]
            prv = poly[i - 1]
            cur_in = (n[0] * cur[0] + n[1] * cur[1]) <= d + 1e-9
            prv_in = (n[0] * prv[0] + n[1] * prv[1]) <= d + 1e-9
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
    b = float(bbox)
    return [(-b, -b), (b, -b), (b, b), (-b, b)]


def halfplane_intersect(halfplanes: Sequence[HalfPlane], bbox: float = 5000.0
                        ) -> Optional[Poly]:
    return hpi_intersect(_bbox_polygon(bbox), halfplanes)


def clip_polygon_by_disk(poly: Poly, c: Vec, r: float, N: int = 64
                         ) -> Optional[Poly]:
    """用 N 条线段近似圆盘 |P−c| ≤ r，截多边形 poly。"""
    if poly is None or len(poly) < 3:
        return None
    hps = []
    for k in range(N):
        a = 2 * math.pi * k / N
        n = (math.cos(a), math.sin(a))
        d = r + n[0] * c[0] + n[1] * c[1]
        hps.append(HalfPlane(n, d))
    return hpi_intersect(poly, hps)


def polygon_diameter(poly: Poly) -> Tuple[float, Vec, Vec]:
    """返回 (D, A, B)。O(n²) 暴力。"""
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
            d2 = dx * dx + dy * dy
            if d2 > best_d2:
                best_d2, best_i, best_j = d2, i, j
    return math.sqrt(best_d2), poly[best_i], poly[best_j]


def _circle_from_2(a: Vec, b: Vec) -> Tuple[Vec, float]:
    c = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
    r2 = (a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2
    return c, r2


def _circle_from_3(a: Vec, b: Vec, c: Vec) -> Optional[Tuple[Vec, float]]:
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) +
          (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) +
          (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d
    ctr = (ux, uy)
    r2 = (ax - ux) ** 2 + (ay - uy) ** 2
    return ctr, r2


def mec_welzl(points: Sequence[Vec]) -> Tuple[Vec, float]:
    """Welzl 最小包围圆（迭代版，O(n) 期望时间）。"""
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
                (R[0][0] - R[1][0]) ** 2 + (R[0][1] - R[1][1]) ** 2,
                (R[0][0] - R[2][0]) ** 2 + (R[0][1] - R[2][1]) ** 2,
                (R[1][0] - R[2][0]) ** 2 + (R[1][1] - R[2][1]) ** 2,
            ) * 0.25
        return c, r2

    def mec(P: List[Vec], R: List[Vec], n: int) -> Tuple[Vec, float]:
        if n == 0 or len(R) == 3:
            return circle_trivial(R)
        p = P[n - 1]
        c, r2 = mec(P, R, n - 1)
        if (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 <= r2 + 1e-9:
            return c, r2
        return mec(P, R + [p], n - 1)

    c, r2 = mec(P, [], len(P))
    return c, math.sqrt(r2)


def diameter_circle_covers(poly: Poly, A: Vec, B: Vec
                           ) -> Tuple[bool, float, Tuple[Vec, float]]:
    """判断以 AB 为直径的圆是否能覆盖多边形。"""
    mid = ((A[0] + B[0]) * 0.5, (A[1] + B[1]) * 0.5)
    D = math.hypot(A[0] - B[0], A[1] - B[1])
    R = D / 2
    off = -1e9
    for p in poly:
        d = math.hypot(p[0] - mid[0], p[1] - mid[1])
        off = max(off, d - R)
    covered = off <= 1e-9
    c_mec, r_mec = mec_welzl(poly)
    return covered, off, (c_mec, r_mec)


def localization_polygon(dets: Sequence[Vec], thetas: Sequence[float],
                         eps_deg: float = 1.0,
                         R_eff: float = 1500.0,
                         R_target: float = 1800.0,
                         N_disk: int = 64) -> Optional[Poly]:
    """构造定位多边形 P = ∩扇形_i ∩ D(S_i, R_eff) ∩ D(O, R_target)。"""
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
    """完整求解第一问。返回含 mec_center, mec_radius, D 等的字典。"""
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