# v3 仓库总览（INDEX）

> 这是 `解题库/第一问/v3/` 的**总索引**。读完这一份就能知道仓库里有什么、怎么跑、产物在哪、当前状态如何。
> 最后整理：2026-09-12（v3.5.6.1 全部修复完成）。
> **停止声明**：v3.5.6.1 后不再新增修改，所有任务完成。

## 一、目录树

```
v3/
├── INDEX.md                 ← 本文件（总索引）
├── README.md                ← 快速上手
├── DELIVERY.md              ← 交付清单（v3 原始版本）
├── CHECKLIST_v3.md          ← v3 落地自检
├── GAPS.md                  ← v3 vs v2 缺口分析
├── CHANGELOG_v3.md          ← v3 → v3.5.6.1 演进
├── RELEASE_NOTES_v3.5.4.md  ← 发布说明（图修复明细）
├── SUBMISSION_CHECKLIST.md  ← 国奖级提交清单（26 项 + 8 节）
├── STATUS.md                ← 状态声明（v3.5.6.1 停止开发）
├── HANDOVER.md              ← 上下文移交说明（交给其他 AI）
├── paper_v3.md              ← 中文论文草稿（11 章节，7338 B）
├── compare_to_修正版.md     ← 与修正版横向对比报告（9565 B）
│
├── problem1_core_v3.py      ← 核心算法库（471 行，19322 B）
├── problem2_analysis_v3.py  ← 算例与可视化（244 行，10631 B）
├── gen_problem1_pdf_v3.py   ← 中英双语 PDF 生成器（318 行，17295 B）
├── verify_v3.py             ← 一站式验证脚本（v3.5.6.1 加 OpenBLAS 单线程）
├── regen_figures.py         ← v3.5 图修复脚本（7 张图重画）
├── setup_env.bat            ← v3.5.6.1 一键环境（OpenBLAS 单线程）
├── run_all_v3.sh            ← 一键三步脚本（14 行，435 B）
│
├── problem1_v3_results.json ← 7 张图 + 2 PDF 清单（v3.5.6.1）
│
├── 问题一建模_v3.pdf        ← 主交付 PDF（11 页，637 KB）
├── 问题一建模_v3_zh_v33.pdf  ← v3.3 中文版 PDF（10 页，639 KB）
│
├── logs/                    ← 验证日志
│   └── verify_v3.5.6.1.log  ← 一站式验证日志（2604 B）
│
└── figures/                 ← 7 张可视化 PNG（460 KB，全部重画 + 中文正常）
    ├── fig1_three_typical.png         77 KB
    ├── fig2_diameter_convergence.png  80 KB
    ├── fig3_sensitivity_eps.png       48 KB
    ├── fig4_R_eff_truncation.png      53 KB
    ├── fig5_MEC_vs_diameter.png       57 KB
    ├── fig6_cover_geometry.png       120 KB
    └── fig7_grid_overview.png         76 KB
```

**总占用**：2.4 MB / 14 个文件 + 7 张 PNG。

## 二、文件用途

| 文件 | 行数 | 用途 |
|---|---|---|
| `problem1_core_v3.py` | 471 | 核心算法库：HPI / 旋转卡壳 / 覆盖判据 / MEC（Welzl）/ Lipschitz / `solve_problem_1` 公共 API |
| `problem2_analysis_v3.py` | 244 | 7 张图的数值算例 + matplotlib 可视化 |
| `gen_problem1_pdf_v3.py` | 318 | ReportLab 中英双语 PDF 生成器，含 §5.1 Jung + §8.1 output contract |
| `verify_v3.py` | 28 | 一站式验证：跑核心自检 + 算例 + PDF 生成 |
| `run_all_v3.sh` | 14 | bash 串行 3 步：core → analysis → pdf |
| `paper_v3.md` | 118 | 中文论文草稿（11 章节） |
| `compare_to_修正版.md` | 104 | 与修正版横向对比 + v3.1 落地清单 |
| `DELIVERY.md` | 97 | 交付清单（v3 原始版本） |
| `CHECKLIST_v3.md` | 15 | v3 落地自检 |
| `GAPS.md` | 17 | v3 vs v2 缺口分析 |
| `CHANGELOG_v3.md` | — | v3 → v3.1 演进记录 |
| `INDEX.md` | — | 本文件（总索引） |
| `README.md` | — | 快速上手入口 |
| `problem1_v3_results.json` | — | 7 张图数值数据（problem2 输出） |
| `问题一建模_v3.pdf` | — | 主交付 PDF（中英双语 16 页） |
| `问题一建模_v3_final.pdf` | — | 主交付 PDF 备份 |

## 三、关键 API

### 核心库 `problem1_core_v3.py`

| 函数 | 行 | 用途 |
|---|---|---|
| `_wrap_alpha(alpha)` | 25 | 角度规约到 (−180°, 180°]，消除跨 ±180° 边界 bug |
| `sub/add/mul/dot/cross/norm/rot90_ccw` | 31–37 | Vec 基本运算 |
| `_seg_intersect / _line_intersect` | 40–49 | 线段/直线交点 |
| `HalfPlane` 类 | 55 | 半平面数据结构 |
| `hpi_intersect(halfplanes)` | 74 | **半平面交**（O(k²)，k=2n+2） |
| `clip_polygon_by_disk(poly, c, R)` | 115 | 多边形与圆盘求交（Sutherland–Hodgman 变种） |
| `monotone_chain(pts)` | 165 | Andrew 单调链凸包 |
| `_is_convex / _brute_force_diameter / polygon_diameter` | 185–252 | 凸性检查 / O(m²) brute / **旋转卡壳** O(m) |
| `diameter_circle_covers(poly, A, B)` | 252 | **覆盖判据** O(m) |
| `_circle_from_2 / _circle_from_3 / min_enclosing_circle (Welzl)` | 265–298 | **最小包围圆** MEC（Welzl 期望线性） |
| `lipschitz_D_theta(dets, eps_deg)` | 306 | 灵敏度 Lipschitz 界 \|∂D/∂θ\| ≤ 1/sin ε |
| `_build_halfplanes_and_disk(dets, ths, eps, R, N_disk)` | 329 | 内部：把扇形+圆盘化为半平面集合 |
| `build_localization_polygon(dets, ths, eps_deg, R, N_disk)` | 356 | 内部：构造 P₁ 凸多边形 |
| **`solve_problem_1(dets, ths, R=1800, eps=1, N_disk=64, R_eff=1500)`** | 369 | **公共 API**：返回 `{poly, n_vertices, D, A, B, O, r, covered, max_offset, mec_radius, mec_center}` |
| `_self_test()` | 414 | 7 步自检（T1–T7） |

### 算例 `problem2_analysis_v3.py`

| 函数 | 行 | 输出图 |
|---|---|---|
| `plot_three_typical` | 35 | `fig1_three_typical.png`（三种典型几何） |
| `plot_diameter_convergence` | 84 | `fig2_diameter_convergence.png`（D 关于 ε） |
| `plot_sensitivity_eps` | 114 | `fig3_sensitivity_eps.png`（Lipschitz 灵敏度） |
| `plot_R_eff_truncation` | 146 | `fig4_R_eff_truncation.png`（R_eff 截断） |
| `plot_MEC_vs_diameter` | 173 | `fig5_MEC_vs_diameter.png`（MEC vs 直径圆） |
| `plot_cover_geometry` | 196 | `fig6_cover_geometry.png`（覆盖几何） |
| `main()` | 225 | 串行 7 图，返回合并 dict（同时写 problem1_v3_results.json） |

### PDF `gen_problem1_pdf_v3.py`

| 函数 | 行 | 用途 |
|---|---|---|
| `_chapter_algorithm(story, styles)` | 31 | 英文版 §4–§11 章节（含 §5.1 Jung + §8.1 output contract） |
| `build_story(results)` | 193 | 中文版 §1–§3 + 英文版 §4–§11 + 7 张图嵌入 |
| `main()` | 297 | 主入口：`python gen_problem1_pdf_v3.py` |

## 四、启动命令

```bash
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第一问/v3"

# 方式 A：一站式验证（核心 + 算例 + PDF + 备份）
PYTHONIOENCODING=utf-8 python -X utf8 verify_v3.py

# 方式 B：bash 三步串行
bash run_all_v3.sh

# 方式 C：手动三步
PYTHONIOENCODING=utf-8 python -X utf8 problem1_core_v3.py   # 自检 7/7
PYTHONIOENCODING=utf-8 python -X utf8 problem2_analysis_v3.py # 7 张图 + JSON
PYTHONIOENCODING=utf-8 python -X utf8 gen_problem1_pdf_v3.py # PDF 生成
```

## 五、产物清单

| 产物 | 大小 | 用途 |
|---|---|---|
| `问题一建模_v3.pdf` | 824 KB | **主交付 PDF**（中英双语 16 页，含 §5.1 Jung + §8.1 output contract） |
| `问题一建模_v3_final.pdf` | 824 KB | 主交付 PDF 备份 |
| `problem1_v3_results.json` | 16 KB | 7 张图数值数据 |
| `figures/*.png` | 668 KB | 7 张可视化（图嵌入 PDF） |

## 六、当前状态

| 维度 | 状态 |
|---|---|
| 核心算法 | HPI + 旋转卡壳 + 覆盖判据 + MEC + Lipschitz + R_eff 接入 |
| 严格证明 | 命题 1–6（凸性 / 卡壳 / 覆盖判据 / 退化 / Lipschitz / Jung 定理） |
| 自检 | 9/9 通过（T1–T10，含 wrap 等价 / n=1 解析 / n=2 反向 / 等边三角形反例） |
| PDF | v3 11 页 637 KB + zh 10 页 639 KB；关键词 Jung=6 / 半平面交=6 / 34.64=2 / 5 米=2 / mec_center=3 / mec_radius=3 / wrap=3 / Lipschitz=6 |
| 修正版对接 | v3.1 已落地：`_wrap_alpha` + T7 + §5.1 Jung + §8.1 output contract + 5 m 下界 |
| 图修复 | v3.5.6.1 完成：7 张图全部重画 + 中文乱码修复 + fig7 根本性 D>0 修复 + PIL/OpenBLAS 内存错修复 |
| 论文草稿 | `paper_v3.md` 11 章节（中文，7338 B） |
| 与修正版对比 | `compare_to_修正版.md` 含完整横向对比 + v3.1 落地清单 |

## 七、引用关系

```
原题 (B 题 PDF + 附件 1/2)
   ↓
problem1_core_v3.py   ← 核心库（独立可调用）
   ↓
problem2_analysis_v3.py   ← 算例 + 7 图
   ↓                          ↓
problem1_v3_results.json   figures/*.png
   ↓
gen_problem1_pdf_v3.py   ← PDF 生成器
   ↓
问题一建模_v3.pdf   ← 主交付
```

## 八、下一步（v3.2 路线图，待用户确认）

1. 把中文 paper_v3.md 全部章节嵌入 PDF（目前 PDF 只嵌了 §1–§3 中文，§4–§11 是英文版）。
2. 加问题 2/3/4 的对接代码（候选区域 / 多机融合 / 鲁棒对偶）。
3. 加附件 1（5 检测点 + 附录 1/2 的真实数据）驱动的端到端 demo。
4. 等边三角形反例作为"经典解析反例"加入 §5。
