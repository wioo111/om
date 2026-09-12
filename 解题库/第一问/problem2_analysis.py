"""
问题1 完整示例与可视化
========================

覆盖：
- 单点 (n=1)
- 两点 (n=2)
- 三点非共线 (n=3)
- 四点共圆 (n=4)
- 矛盾情形 (空集)

输出各情形的直径、覆盖判别、可视化。
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from problem1_core import (
    build_localization_polygon, naive_diameter, diameter_circle_covers,
    make_sector_halfplanes, HalfPlane, convex_hull
)


def compute_diameter_and_check(detectors, bearings, eps=1.0, R=1800.0):
    poly, ok = build_localization_polygon(detectors, bearings, eps, R)
    if not ok or len(poly) < 2:
        return 0.0, None, None, False, poly
    D, iA, iB = naive_diameter(poly)
    A, B = poly[iA], poly[iB]
    cov, _ = diameter_circle_covers(poly, A, B)
    return D, A, B, cov, poly


def plot_case(ax, detectors, bearings, title, eps=1.0, R=1800.0):
    D, A, B, cov, poly = compute_diameter_and_check(detectors, bearings, eps, R)
    # 画 Ω
    theta_c = np.linspace(0, 2 * np.pi, 200)
    ax.plot(R * np.cos(theta_c), R * np.sin(theta_c), 'k--', alpha=0.4, label='Ω')
    # 画扇形
    for (xi, yi), th in zip(detectors, bearings):
        Si = np.array([xi, yi], dtype=float)
        for sign, ls in [(-1, ':'), (+1, ':')]:
            ang = np.deg2rad(th + sign * eps)
            ax.plot([Si[0], Si[0] + 3000 * np.cos(ang)],
                    [Si[1], Si[1] + 3000 * np.sin(ang)], ls, color='gray', alpha=0.5)
    # 画检测点
    if detectors:
        dets = np.array(detectors)
        ax.scatter(dets[:, 0], dets[:, 1], c='blue', marker='s', s=60, zorder=5, label='detector')
    # 画多边形
    if len(poly) >= 3:
        P = np.array(poly)
        closed = np.vstack([P, P[:1]])
        ax.fill(closed[:, 0], closed[:, 1], alpha=0.25, color='red', label='定位区域')
        ax.plot(closed[:, 0], closed[:, 1], 'r-', linewidth=1.5)
        # 直径
        if D > 0 and A is not None:
            ax.plot([A[0], B[0]], [A[1], B[1]], 'g-', linewidth=2, label=f'D={D:.1f}m')
            # 直径圆
            O = (A + B) / 2
            r = D / 2
            cir = plt.Circle(O, r, fill=False, color='green', linestyle='--',
                             linewidth=1, label='覆盖圆' if cov else '未覆盖圆')
            ax.add_patch(cir)
    ax.set_aspect('equal')
    ax.set_title(f"{title}\nD={D:.2f}m 覆盖={cov}")
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=7)


def main():
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # 情形 1: n=1
    plot_case(axes[0, 0], [(0, 0)], [45.0], 'n=1 (单检测点)', eps=1.0)
    # 情形 2: n=2
    plot_case(axes[0, 1], [(-800, 0), (800, 0)], [90.0, 270.0], 'n=2 (两点相对)', eps=1.0)
    # 情形 3: n=3 真方位角度对齐 (真实 G≈(0,0))
    plot_case(axes[0, 2], [(-500, -300), (600, -200), (0, 700)],
              [31.0, 162.0, 270.0], 'n=3 (三点协调)', eps=1.0)
    # 情形 4: n=4 包围
    plot_case(axes[1, 0], [(-800, -800), (800, -800), (800, 800), (-800, 800)],
              [45.0, 135.0, 225.0, 315.0], 'n=4 (四点包围)', eps=1.0)
    # 情形 5: 矛盾示向度
    plot_case(axes[1, 1], [(-500, 0), (500, 0)], [45.0, 45.0],
              '矛盾示向度 (空集)', eps=1.0)
    # 情形 6: n=5 真实 G≈原点, 5 个检测点
    detectors5 = [(-700, -200), (500, -300), (300, 500), (-300, 600), (-700, 200)]
    bearings5 = []
    G_true = np.array([0.0, 0.0])
    for (xi, yi) in detectors5:
        ang = np.rad2deg(np.arctan2(-yi, -xi)) % 360
        bearings5.append(ang)
    plot_case(axes[1, 2], detectors5, bearings5, 'n=5 (5点协调)', eps=1.0)

    plt.tight_layout()
    plt.savefig('problem1_cases.png', dpi=120, bbox_inches='tight')
    print("已保存 problem1_cases.png")

    # 同时打印数值结果
    print("\n=== 各情形数值结果 ===")
    cases = [
        ('n=1', [(0, 0)], [45.0]),
        ('n=2 对称', [(-800, 0), (800, 0)], [90.0, 270.0]),
        ('n=3 协调', [(-500, -300), (600, -200), (0, 700)], [31.0, 162.0, 270.0]),
        ('n=4 包围', [(-800, -800), (800, -800), (800, 800), (-800, 800)],
         [45.0, 135.0, 225.0, 315.0]),
        ('矛盾', [(-500, 0), (500, 0)], [45.0, 45.0]),
        ('n=5 协调', [(-700, -200), (500, -300), (300, 500), (-300, 600), (-700, 200)],
         bearings5),
    ]
    for name, dets, bears in cases:
        D, A, B, cov, poly = compute_diameter_and_check(dets, bears, eps=1.0)
        print(f"{name:15s}: D={D:8.4f} m, vertices={len(poly):3d}, covered={cov}")


if __name__ == "__main__":
    main()