# 问题 2 v3 — 国奖级改进版

> 这是 `v3/` 的**快速上手入口**。完整索引见 `INDEX.md`；论文定稿见 `问题二建模_v3.md`；改进溯源见 `问题二建模_v3.md` 附录 B；与原稿的对比 diff 见 `paper_v3_diff.md`。

## 目标

把原稿（LaTeX）升到国奖级：
1. 把所有 LaTeX 公式换成 Unicode 人话数学符号（中文论文体例）
2. 融合 12 条改进 + 4 处用户评审硬伤修复 = 16 项改动
3. 与问题一 v3 库的 `_wrap_alpha` + `solve_problem_1` 闭环
4. 重做主模型 J_robust + 代理 J_proxy + (d, w) 矩形采样
5. 补退化情形 D1–D4 + 反例 2/3 + 命题 7/8/9 严格证明
6. 补调用契约 §11.0 + 复杂度分析 §11.2 + 灵敏度 §11.3

## 一键运行

```bash
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第二问/v3"
PYTHONIOENCODING=utf-8 python -X utf8 verify_problem2_v3.py
```
应看到 `[OK] 7/7 自检通过`。

## 文件

- `INDEX.md` — 完整索引
- `问题二建模_v3.md` — **改进定稿（中文 Markdown，含 16 项改动溯源）**
- `paper_v3_diff.md` — 12 条改进清单 + 示范重写
- `问题二.txt` — 原稿（LaTeX）

## 公共 API

```python
from problem2_core_v3 import (
    classify_G, build_P2, sample_F1,
    J_robust, J_proxy, grid_search_J_robust, candidate_region
)

# 1) 采样 F₁
Gs = sample_F1(S1=(0, 0), theta1_deg=0.0, N_d=60, N_w=21)

# 2) 单点 J_robust
r = J_robust(S2=(800, 0), S1=(0, 0), theta1=0.0, G_samples=Gs)
# r = {max_rho, N0, N1, N2, J_robust}

# 3) 网格搜索
res = grid_search_J_robust(S1=(0, 0), theta1=0.0,
                           R_Omega=1800, R_eff=1500,
                           L_min=992, grid_step=50)
# res = {J_star, S2_star, results}

# 4) 候选区域 C_η
eta_pts = candidate_region(res["results"], res["J_star"], eta=0.2)
```