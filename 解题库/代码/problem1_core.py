"""
问题1 核心算法实现
==================

功能：
1. 由示向度构造定位区域（半平面交 + 圆盘裁剪）
2. 计算定位多边形直径（旋转卡壳）
3. 判断直径圆是否覆盖定位区域
4. 含退化情形处理与数值稳定性

作者：国赛B题建模组
"""

import numpy as np
from typing import List, Tuple, Optional

# ============================================================
# 基础几何工具
# ============================================================

def wrap_deg(alpha: float) -> float:
    """角度归一化到 [-180, 180)"""
    a = ((alpha + 180.0) % 360.0 + 360.0) % 360.0 - 180.0
    return a


def cross2(a: np.ndarray, b: np.ndarray) -> float:
    """二维向量叉积 a x b = a_x*b_y - a_y*b_x"""
    return float(a[0] * b[1] - a[1] * b[0])


def dot2(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def normalize_angle(theta_deg: float) -> float:
    """归一化角度到 [0, 360)"""
    return theta_deg % 360.0


# ============================================================
# 半平面表示
# ============================================================

class HalfPlane:
    """
    半平面：n·P <= d
    闭半平面（包含边界）以 EPS 容差判断。
    """
    __slots__ = ("n", "d")

    def __init__(self, n: np.ndarray, d: float):
        n = np.asarray(n, dtype=float)
        norm = np.linalg.norm(n)
        if norm < 1e-15:
            raise ValueError("Zero normal vector")
        self.n = n / norm   # 单位法向量
        self.d = d / norm   # 相应归一化

    def contains(self, P: np.ndarray, eps: float = 1e-9) -> bool:
        return float(np.dot(self.n, P)) <= self.d + eps

    def __repr__(self):
        return f"HalfPlane(n=({self.n[0]:.4f},{self.n[1]:.4f}), d={self.d:.4f})"


def make_sector_halfplanes(S: np.ndarray, theta_deg: float, eps_deg: float
                           ) -> Tuple[HalfPlane, HalfPlane]:
    """
    对检测点 S、示向度 theta、误差 eps 构造两条边界半平面。
    扇形内点 P 需同时满足：
       cross(u_lo, P-S) >= 0  与  cross(u_hi, P-S) <= 0
    其中 u_lo = (cos(theta-eps), sin(theta-eps))，u_hi = (cos(theta+eps), sin(theta+eps))。

    等价的半平面形式 (n·P <= d)：
       cross(u_lo, P-S) >= 0  ⇔  (u_y, -u_x)·P <= (u_y, -u_x)·S
       cross(u_hi, P-S) <= 0  ⇔  (-u_y, u_x)·P <= (-u_y, u_x)·S
    """
    S = np.asarray(S, dtype=float)
    lo = np.deg2rad(theta_deg - eps_deg)
    hi = np.deg2rad(theta_deg + eps_deg)
    u_lo = np.array([np.cos(lo), np.sin(lo)])
    u_hi = np.array([np.cos(hi), np.sin(hi)])

    # 下边界 cross(u_lo, P-S) >= 0 → (u_y, -u_x)·P <= (u_y, -u_x)·S
    n_lo = np.array([u_lo[1], -u_lo[0]])
    d_lo = float(np.dot(n_lo, S))
    hp_lower = HalfPlane(n_lo, d_lo)

    # 上边界 cross(u_hi, P-S) <= 0 → (-u_y, u_x)·P <= (-u_y, u_x)·S
    n_hi = np.array([-u_hi[1], u_hi[0]])
    d_hi = float(np.dot(n_hi, S))
    hp_upper = HalfPlane(n_hi, d_hi)

    return hp_lower, hp_upper


def make_disk_halfplanes(R: float, n_dirs: int = 64) -> List[HalfPlane]:
    """
    用 n_dirs 个外向法线近似半径 R 的圆盘 Ω：
       n_i · P <= R
    n_dirs 越大越精确。
    """
    planes = []
    for k in range(n_dirs):
        ang = 2.0 * np.pi * k / n_dirs
        n = np.array([np.cos(ang), np.sin(ang)])
        planes.append(HalfPlane(n, R))
    return planes


# ============================================================
# 半平面交（Sutherland-Hodgman）
# ============================================================

def clip_polygon_by_hp(poly: List[np.ndarray], hp: HalfPlane
                       ) -> List[np.ndarray]:
    """单次半平面裁剪，返回新顶点列表（保持逆时针顺序）。"""
    if not poly:
        return []
    out = []
    n = len(poly)
    for i in range(n):
        A = poly[i]
        B = poly[(i + 1) % n]
        Ain = hp.contains(A)
        Bin = hp.contains(B)
        if Ain and Bin:
            out.append(B)
        elif Ain and not Bin:
            # A 内 B 外：加入交点
            out.append(_seg_hp_intersect(A, B, hp))
        elif not Ain and Bin:
            # A 外 B 内：加入交点 + B
            out.append(_seg_hp_intersect(A, B, hp))
            out.append(B)
        # else 两点都在外，跳过
    return out


def _seg_hp_intersect(A: np.ndarray, B: np.ndarray, hp: HalfPlane
                      ) -> np.ndarray:
    """线段 AB 与半平面边界 n·P = d 的交点"""
    denom = float(np.dot(hp.n, B - A))
    if abs(denom) < 1e-15:
        return A.copy()
    t = (hp.d - float(np.dot(hp.n, A))) / denom
    t = max(0.0, min(1.0, t))
    return A + t * (B - A)


def halfplane_intersection(initial: List[np.ndarray],
                           halfplanes: List[HalfPlane]
                           ) -> List[np.ndarray]:
    """依次用所有半平面裁剪初始多边形"""
    poly = list(initial)
    for hp in halfplanes:
        poly = clip_polygon_by_hp(poly, hp)
        if not poly:
            return []
    return poly


# ============================================================
# 凸包（Andrew 算法）
# ============================================================

def convex_hull(points: List[np.ndarray]) -> List[np.ndarray]:
    """Andrew 算法的凸包，逆时针返回；若点数 < 3 直接返回排序点"""
    if len(points) < 3:
        return sorted(points, key=lambda p: (p[0], p[1]))
    pts = sorted(set((float(p[0]), float(p[1])) for p in points))

    def cross(O, A, B):
        return (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-12:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-12:
            upper.pop()
        upper.append(p)
    return [np.array(p) for p in lower[:-1] + upper[:-1]]


# ============================================================
# 多边形直径（旋转卡壳）
# ============================================================

def polygon_diameter(poly: List[np.ndarray]) -> Tuple[float, int, int]:
    """
    返回 (D, idx_i, idx_j) 表示直径长度和两个顶点下标。
    poly 必须是逆时针凸包。
    """
    m = len(poly)
    if m == 0:
        return 0.0, -1, -1
    if m == 1:
        return 0.0, 0, 0
    if m == 2:
        return float(np.linalg.norm(poly[1] - poly[0])), 0, 1

    # 找 y 最小点（也找 y 最大）作起点
    def farthest_from_edge():
        best, best_dist = 0, -1.0
        for i in range(m):
            # 边 poly[i] -> poly[(i+1)%m]
            j = (i + 1) % m
            e = poly[j] - poly[i]
            # 取与 e 垂直方向距离最大的点
            for k in range(m):
                d = abs(cross2(e, poly[k] - poly[i]))
                if d > best_dist:
                    best_dist = d
                    best = k
        return best

    # 旋转卡壳
    i0 = farthest_from_edge()
    j = (i0 + 1) % m
    best_d2 = 0.0
    best_i, best_j = i0, j
    eps = 1e-12

    while True:
        next_i = (i0 + 1) % m
        e_i = poly[next_i] - poly[i0]
        e_j = poly[(j + 1) % m] - poly[j]
        # 判断是否该移动 i 或 j
        area_next_i = abs(cross2(e_i, poly[(j + 1) % m] - poly[next_i]))
        area_j = abs(cross2(poly[j] - poly[i0], e_j))
        if area_next_i > area_j + eps:
            i0 = next_i
        else:
            j = (j + 1) % m
        # 当前距离
        d2 = float(np.sum((poly[i0] - poly[j]) ** 2))
        if d2 > best_d2:
            best_d2 = d2
            best_i, best_j = i0, j
        # 终止：j 回到起点
        if j == 0 or (i0 == best_i and j == best_j and False):
            break
        # 防止死循环：最多 m*2 次
        if j == 0 and i0 == best_i:
            break

    # 再做一遍穷举保证正确性（小多边形时）
    for ii in range(m):
        for jj in range(ii + 1, m):
            d2 = float(np.sum((poly[ii] - poly[jj]) ** 2))
            if d2 > best_d2:
                best_d2 = d2
                best_i, best_j = ii, jj

    return float(np.sqrt(best_d2)), best_i, best_j


def naive_diameter(poly: List[np.ndarray]) -> Tuple[float, int, int]:
    m = len(poly)
    if m == 0:
        return 0.0, -1, -1
    if m == 1:
        return 0.0, 0, 0
    best_d2, bi, bj = 0.0, 0, 1
    for i in range(m):
        for j in range(i + 1, m):
            d2 = float(np.sum((poly[i] - poly[j]) ** 2))
            if d2 > best_d2:
                best_d2, bi, bj = d2, i, j
    return float(np.sqrt(best_d2)), bi, bj


# ============================================================
# 直径圆覆盖性
# ============================================================

def diameter_circle_covers(poly: List[np.ndarray], A: np.ndarray, B: np.ndarray
                           ) -> Tuple[bool, float]:
    """
    判断以 A, B 为直径的圆是否覆盖整个多边形（凸包）。
    返回 (覆盖?, 最远顶点距圆心距离)
    """
    if len(poly) == 0:
        return True, 0.0
    O = (A + B) / 2.0
    r = float(np.linalg.norm(A - B)) / 2.0
    max_d = 0.0
    for V in poly:
        d = float(np.linalg.norm(V - O))
        if d > max_d:
            max_d = d
    return max_d <= r + 1e-7, max_d


# ============================================================
# 顶层接口：构造定位区域
# ============================================================

def build_localization_polygon(detectors: List[Tuple[float, float]],
                               bearings: List[float],
                               eps_deg: float = 1.0,
                               R: float = 1800.0,
                               n_disk: int = 64
                               ) -> Tuple[List[np.ndarray], bool]:
    """
    输入：
      detectors : 检测点列表 [(xi, yi), ...]
      bearings  : 对应示向度 [theta_i, ...]
      eps_deg   : 示向度误差（度）
      R         : 目标圆盘半径
      n_disk    : 圆盘近似方向数
    输出：
      poly      : 定位多边形顶点（逆时针凸包）
      feasible  : 是否非空
    """
    assert len(detectors) == len(bearings)

    # 初始多边形：用圆盘近似多边形
    initial = []
    for k in range(n_disk):
        ang = 2.0 * np.pi * k / n_disk
        initial.append(np.array([R * np.cos(ang), R * np.sin(ang)]))

    halfplanes: List[HalfPlane] = []
    for (xi, yi), theta in zip(detectors, bearings):
        Si = np.array([xi, yi])
        hp1, hp2 = make_sector_halfplanes(Si, theta, eps_deg)
        halfplanes.append(hp1)
        halfplanes.append(hp2)

    # 用圆盘多边形近似 Ω，然后裁剪所有半平面
    poly = halfplane_intersection(initial, halfplanes)
    if not poly:
        return [], False

    # 凸包保证 + 数值清理
    poly = convex_hull(poly)
    # 删除近似共线点
    poly = _remove_collinear(poly, tol=1e-7)
    return poly, len(poly) >= 3


def _remove_collinear(poly: List[np.ndarray], tol: float = 1e-7) -> List[np.ndarray]:
    if len(poly) < 3:
        return poly
    out = []
    m = len(poly)
    for i in range(m):
        A = poly[(i - 1) % m]
        B = poly[i]
        C = poly[(i + 1) % m]
        if abs(cross2(B - A, C - A)) > tol:
            out.append(B)
    return out if len(out) >= 3 else poly


# ============================================================
# 自检：示例数据
# ============================================================

if __name__ == "__main__":
    # 示例：3 个检测点，扇形交汇于一个三角形
    detectors = [(-500, -300), (600, -200), (0, 700)]
    bearings = [60.0, 110.0, 230.0]   # 单位：度
    eps = 1.0

    poly, ok = build_localization_polygon(detectors, bearings, eps_deg=eps)
    print(f"定位多边形顶点数 = {len(poly)}, feasible = {ok}")
    if ok:
        # 直径
        D, iA, iB = naive_diameter(poly)
        A, B = poly[iA], poly[iB]
        print(f"直径 D = {D:.4f} m, 端点 A = {A}, B = {B}")
        # 覆盖判别
        cov, maxd = diameter_circle_covers(poly, A, B)
        print(f"直径圆覆盖定位区域？ {cov}, 最远顶点距圆心 = {maxd:.4f}, 半径 = {D/2:.4f}")

    # 退化示例：单点
    poly, ok = build_localization_polygon([(0, 0)], [45.0], eps_deg=1.0)
    print(f"\n单检测点：顶点数 = {len(poly)}, feasible = {ok}")
    if ok:
        D, iA, iB = naive_diameter(poly)
        print(f"直径 D = {D:.4f} m (期望 ≈ 3600)")

    # 退化示例：空集（矛盾的示向度）
    poly, ok = build_localization_polygon([(0, 0), (100, 0)], [90.0, 270.0], eps_deg=1.0)
    print(f"\n矛盾示向度：顶点数 = {len(poly)}, feasible = {ok}")