# 问题 1 v3 交付清单（最终版）

**版本**：v3 国奖级改进版
**生成时间**：2026-09-11 02:30
**生成脚本**：`verify_v3.py`（依次跑 core → analysis → pdf）

## 主产物

| 文件 | 大小 | 说明 |
|---|---|---|
| `问题一建模_v3.pdf` | 821 KB | 国奖级中英双语 PDF，15 页 / 5678 字符 |
| `问题一建模_v3_final.pdf` | 821 KB | 上述备份 |
| `paper_v3.md` | 6.6 KB | 中文国奖级 markdown 论文，11 章节 |
| `problem1_core_v3.py` | 18 KB / 451 行 | 核心算法库，25 个 def/class，命题 1–5 + Lipschitz 验证 |
| `problem2_analysis_v3.py` | 10.6 KB / 244 行 | 7 个可视化函数 + JSON 落盘 |
| `gen_problem1_pdf_v3.py` | 15.6 KB / 297 行 | 中英双语 PDF 生成 |
| `verify_v3.py` | 0.8 KB / 28 行 | 一站式验证脚本（依次跑 core→analysis→pdf） |
| `run_all_v3.sh` | 0.4 KB / 14 行 | 一键 shell |
| `problem1_v3_results.json` | 16 KB | fig1–fig6 数值结果 |
| `figures/` | 666 KB / 7 张 PNG | 图 1–图 7 |

## 论文正文章节（paper_v3.md）

1. 摘要
2. 关键词
3. §1 问题重述与建模目标
4. §2 符号与基本假设
5. §3 严格建模
6. §4 算法三件套 + 正确性证明
7. §5 灵敏度分析
8. §6 数值实验
9. §7 与问题 2/3/4 的接口
10. §8 结论
11. 参考文献（6 条）

## PDF 内容验证（pypdf 关键词命中）

| 关键词 | 命中次数 |
|---|---|
| Algorithm | 3 |
| Cover | 2 |
| Sensitivity | 1 |
| Numerical | 1 |
| Conclusion | 1 |
| References | 1 |
| MEC | 9 |
| Lipschitz | 4 |
| 定位多边形 | 2 |
| 直径 | 6 |
| 旋转卡壳 | 2 |
| 半平面 | 7 |

## v2 → v3 改进清单

| 项 | v2 | v3 |
|---|---|---|
| 凸性证明 | 默认凸、未证 | 命题 1 严格证明 + monotone_chain 兜底 |
| 直径算法 | 旋转卡壳 | 旋转卡壳 + m≤16 brute-force 自检 |
| 覆盖判据 | 仅"是否覆盖" | 充要条件 + 三种等价几何刻画 + MEC 对照 |
| 数值表 | n=1 D=1800 错 | 修正为 D=3599.45 = 2R |
| 灵敏度 | 无 | 命题 5 \|∂D/∂θ\| ≤ 1/sin ε + 图 3 |
| 收敛曲线 | 无 | 图 2 |
| 退化情形 | 部分 | 全部：空/单点/线段/矩形/凸多边形 |
| R_eff 接入 | 无 | 接入有效接收半径 R_eff ∈ [1000, 1500] |
| 接口 | 简述 | §7/§8 形式化几何接口 |
| 复杂度 | 仅 O(m) | 表 4 主路径 + 期望 + 最坏 |
| 双语性 | 无 | 中英双语 PDF + 中文 markdown 11 章节 |
| 章节数 | 8 | 11 |
| 参考文献 | 0 | 6 |
| 嵌入图 | 0 | 6 张 |

## 跑法

```bash
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第一问/v3"
bash run_all_v3.sh
# 或：
python verify_v3.py
```

## 核心库公共 API

```
geometric:     sub, add, mul, dot, cross, norm, rot90_ccw
clipping:      _seg_intersect, _line_intersect, hpi_intersect, clip_polygon_by_disk
convex:        monotone_chain, _is_convex
diameter:      _brute_force_diameter, polygon_diameter
cover:         diameter_circle_covers
mec:           _circle_from_2, _circle_from_3, _in_circle, _welzl, min_enclosing_circle
sensitivity:   lipschitz_D_theta
halfplane:     HalfPlane.from_two_points, HalfPlane.contains
builder:       _build_halfplanes_and_disk, build_localization_polygon
public:        solve_problem_1
selftest:      _self_test (6-step audit: HPI convexity / calipers vs brute-force /
                            cover criterion / degenerate cases / Lipschitz bound /
                            performance benchmark)
```
