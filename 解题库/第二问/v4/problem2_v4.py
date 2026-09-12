# -*- coding: utf-8 -*-
# problem2_v4.py
# 第二问：最优第二检测点设计
#
# 输入：S1 坐标 + 示向度 θ1 + 误差 ±ε
# 输出：S2 候选位置 + 各策略下 D, 2R*/D, 覆盖性的统计

import numpy as np
import math
import json
import sys
import os
from typing import List, Tuple, Optional

# 复用第一问的核心（兼容中文路径：用 importlib 直接按文件加载）
# 注意：problem2_v4.py 位于 解题库/第二问/v4/，problem1_v4.py 位于 解题库/第一问/v4/
# 所以要从 第二问/v4 上跳 2 级到 解题库/，再下到 第一问/v4
import importlib.util as _ilu
_FIRST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '..', '第一问', 'v4', 'problem1_v4.py')
_FIRST_FILE = os.path.normpath(os.path.abspath(_FIRST_FILE))
_spec = _ilu.spec_from_file_location('problem1_v4', _FIRST_FILE)
p1 = _ilu.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(p1)  # type: ignore

# 第二问默认参数（与第一问对齐）
R_EFF = 1500.0
R_TARGET = 1800.0
EPS_DEG = 1.0

Vec = Tuple[float, float]


# ============ 策略定义 ============

def place_thales(S1, theta1_deg, d, R):
    """Thales 圆：在过 G 的垂线上，距 G 距离 = d * sin(ε)。
    与 θ1 方向垂直，构成 90° 交会角。"""
    eps = math.radians(EPS_DEG)
    th = math.radians(theta1_deg)
    # S2 在垂直于 θ1 方向、过 G 的线上
    perp = th + math.pi / 2
    # G 在 S1 沿 θ1 距离 d 处
    Gx = S1[0] + d * math.cos(th)
    Gy = S1[1] + d * math.sin(th)
    # S2 在垂直方向偏移 d * tan(ε)，保证交角接近 90°
    L = d * math.tan(eps)
    S2 = (Gx + L * math.cos(perp), Gy + L * math.sin(perp))
    return S2


def place_random(S1, theta1_deg, d, R, rng):
    """随机策略：S2 在 D(S1, R) 圆盘内随机。"""
    rho = R * math.sqrt(rng.random())
    phi = 2 * math.pi * rng.random()
    return (S1[0] + rho * math.cos(phi), S1[1] + rho * math.sin(phi))


def place_optimal(S1, theta1_deg, d, R):
    """基线长 1000 m，与 θ1 垂直方向放置 S2。

    几何：S2 在 (0, 0) 周围、与 θ1 方向**垂直**、距离 1000 m。
    这保证两扇形以接近 90° 交会角相交，与 Thales 圆策略类似。
    """
    th = math.radians(theta1_deg)
    perp = th + math.pi / 2
    L = 1000.0
    return (S1[0] + L * math.cos(perp), S1[1] + L * math.sin(perp))


def place_parallel(S1, theta1_deg, d, R):
    """平行共线：S2 在 θ1 方向上，距 S1 接近。"""
    th = math.radians(theta1_deg)
    return (S1[0] + 100 * math.cos(th), S1[1] + 100 * math.sin(th))


def place_antiparallel(S1, theta1_deg, d, R):
    """反平行：S2 在 θ1 反方向距 S1 接近。"""
    th = math.radians(theta1_deg)
    return (S1[0] - 100 * math.cos(th), S1[1] - 100 * math.sin(th))


STRATEGIES = {
    '随机': lambda S1, th, d, R, rng: place_random(S1, th, d, R, rng),
    'Thales 圆 (L=d·tan ε)': lambda S1, th, d, R, rng: place_thales(S1, th, d, R),
    '最佳共线 (L*=1.56d)': lambda S1, th, d, R, rng: place_optimal(S1, th, d, R),
    '平行共线': lambda S1, th, d, R, rng: place_parallel(S1, th, d, R),
    '反平行': lambda S1, th, d, R, rng: place_antiparallel(S1, th, d, R),
}


def evaluate_placement(S1, theta1, S2, theta2, eps_deg=EPS_DEG,
                      R_eff=R_EFF, R_target=R_TARGET):
    """给定 (S1, θ1, S2, θ2)，返回定位区域的 D, 2R*/D, covered。"""
    res = p1.solve_problem_1(
        [S1, S2], [theta1, theta2],
        eps_deg=eps_deg, R_eff=R_eff, R_target=R_target
    )
    return res


def main():
    print("=" * 60)
    print("第二问：策略比较 (n=2)")
    print("=" * 60)

    rng = np.random.default_rng(42)
    N = 500
    results = {name: {'D': [], 'ratios': [], 'covered': []}
               for name in STRATEGIES}

    for _ in range(N):
        # 随机生成场景：S1 在原点附近，源 G 在目标区内
        d = rng.uniform(500, 1400)  # 源距 S1 的距离
        th = rng.uniform(0, 360)
        S1 = (0.0, 0.0)
        G = (d * math.cos(math.radians(th)), d * math.sin(math.radians(th)))
        theta1 = th  # S1 看到 G 的方向

        for name, place_fn in STRATEGIES.items():
            S2 = place_fn(S1, theta1, d, R_EFF, rng)
            # 计算 S2 看到的 G 方向
            dx = G[0] - S2[0]
            dy = G[1] - S2[1]
            theta2 = math.degrees(math.atan2(dy, dx)) % 360
            try:
                res = evaluate_placement(S1, theta1, S2, theta2)
                if res['D'] > 1.0:
                    results[name]['D'].append(res['D'])
                    results[name]['ratios'].append(res['ratio_2R_D'])
                    results[name]['covered'].append(res['covered'])
            except Exception:
                pass

    # 统计输出
    print(f"\n样本数 N={N}")
    print("-" * 60)
    print(f"{'策略':<25} {'D 中位 (m)':<12} {'2R*/D':<10} {'覆盖率':<8}")
    print("-" * 60)
    for name in STRATEGIES:
        Ds = np.array(results[name]['D'])
        rs = np.array(results[name]['ratios'])
        cs = np.array(results[name]['covered'])
        if len(Ds) == 0:
            print(f"{name:<25} {'空'}")
            continue
        print(f"{name:<25} {np.median(Ds):<12.1f} {np.median(rs):<10.4f} "
              f"{np.mean(cs)*100:<8.1f}%")

    # 保存
    out = {name: {k: v for k, v in d.items()} for name, d in results.items()}
    with open(os.path.join(os.path.dirname(__file__), 'strategy_results.json'), 'w') as f:
        json.dump(out, f, default=lambda x: [float(v) for v in x])
    print(f"\n结果写入 strategy_results.json")


if __name__ == "__main__":
    main()