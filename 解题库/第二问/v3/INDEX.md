# v3 仓库总览（INDEX）

> 这是 `解题库/第二问/v3/` 的**总索引**。读完这一份就能知道仓库里有什么、怎么跑、产物在哪、当前状态如何。
> 最后整理：2026-09-11（v3.1 落地后）。

## 一、目录树

```
v3/
├── INDEX.md                 ← 本文件（总索引）
├── README.md                ← 快速上手
├── 问题二.txt               ← 原稿（LaTeX，11253 B）
├── 问题二建模_v3.md         ← 改进定稿（中文 Markdown，16 项改动已融合）
├── paper_v3_diff.md         ← 12 条改进 + 示范重写
├──
├── problem2_core_v3.py      ← 核心算法库
├── problem2_analysis_v3.py  ← 算例与可视化
├── gen_problem2_pdf_v3.py   ← PDF 生成器（待写）
├── verify_problem2_v3.py    ← 一站式验证（待写）
├──
├── problem2_v3_results.json ← 5 张图数值数据
├──
└── figures/                 ← 5 张可视化 PNG
    ├── fig1_F1_first_detection.png
    ├── fig2_beta_isobands.png
    ├── fig3_J_robust_heatmap.png
    ├── fig4_three_categories_A0A1A2.png
    └── fig5_convergence_N_scan.png
```

## 二、文件用途

| 文件 | 用途 |
|---|---|
| `问题二.txt` | 原稿 LaTeX 草稿 |
| `问题二建模_v3.md` | 改进定稿（融合 16 项改动） |
| `paper_v3_diff.md` | 12 条改进清单 + 示范重写 |
| `problem2_core_v3.py` | 核心算法库（classify_G / build_P2 / J_robust / grid_search / _self_test） |
| `problem2_analysis_v3.py` | 5 张图算例 |
| `gen_problem2_pdf_v3.py` | PDF 生成器（待写） |
| `verify_problem2_v3.py` | 一站式验证（待写） |

## 三、关键 API

| 函数 | 用途 |
|---|---|
| `classify_G(S2, G, R_eff=1500)` | 把 G 分 A₀/A₁/A₂ |
| `build_P2(S1, θ₁, S2, G, ...)` | 调 `solve_problem_1` 构造 P₂ |
| `sample_F1(S1, θ₁, N_d=60, N_w=21)` | (d, w) 参数化矩形采样 |
| `J_robust(S2, S1, θ₁, G_samples, lam=1500)` | 主模型 |
| `J_proxy(S2, S1, θ₁, G_samples)` | κ 代理粗筛 |
| `grid_search_J_robust(S1, θ₁, ...)` | 网格搜索（带代理粗筛） |
| `candidate_region(results, J_star, eta=0.2)` | C_η 候选区域 |
| `_self_test()` | 7 步自检（T1–T7） |

## 四、启动命令

```bash
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第二问/v3"

# 方式 A：一站式
PYTHONIOENCODING=utf-8 python -X utf8 verify_problem2_v3.py

# 方式 B：手动三步
PYTHONIOENCODING=utf-8 python -X utf8 problem2_core_v3.py      # 自检 7/7
PYTHONIOENCODING=utf-8 python -X utf8 problem2_analysis_v3.py  # 5 张图 + JSON
PYTHONIOENCODING=utf-8 python -X utf8 gen_problem2_pdf_v3.py   # PDF 生成
```

## 五、产物清单

| 产物 | 用途 |
|---|---|
| `figures/*.png` | 5 张可视化 |
| `problem2_v3_results.json` | 5 张图数值数据 |
| `问题二建模_v3.pdf`（待生成） | 主交付 PDF |

## 六、当前状态

| 维度 | 状态 |
|---|---|
| 改进定稿 | `问题二建模_v3.md` 已落地 16 项改动 |
| 核心库 | 已写（classify/build_P2/J_robust/J_proxy/grid_search/_self_test） |
| 算例与图 | 已写（5 张图算例） |
| PDF 生成 | 待写 |
| 自检 | 待跑（应 7/7） |
| 与问题一 v3 衔接 | `_wrap_alpha` + `solve_problem_1` 复用 |

## 七、引用关系

```
原题（B 题 PDF + 附件 2）
   ↓
问题一 v3: problem1_core_v3.py  ← 核心库（HPI + Welzl + _wrap_alpha）
   ↓
问题二 v3: problem2_core_v3.py  ← 复用 + 扩展（classify_G / J_robust / grid_search）
   ↓
problem2_analysis_v3.py  ← 5 张图算例
   ↓
figures/*.png + problem2_v3_results.json
   ↓
gen_problem2_pdf_v3.py  ← PDF 生成器（待写）
   ↓
问题二建模_v3.pdf  ← 主交付（待生成）
```