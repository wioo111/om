# 问题 1 v3 — 国奖级改进版

> 这是 `v3/` 的**快速上手入口**。完整索引见 `INDEX.md`；论文草稿见 `paper_v3.md`；与修正版对比见 `compare_to_修正版.md`；演进记录见 `CHANGELOG_v3.md`；发布说明见 `RELEASE_NOTES_v3.5.4.md`；提交清单见 `SUBMISSION_CHECKLIST.md`；状态声明见 `STATUS.md`；上下文移交见 `HANDOVER.md`。

**移交新 AI**：直接打开 `HANDOVER.md`，含公共 API / 启动命令 / 已知约束 / 修复史 / 用户偏好。

## 目标
把 v2（半平面交 + 旋转卡壳 + 覆盖判定）升到国奖级：
1. 算法正确性证明（凸性 / 直径 / 覆盖判据 充要条件）
2. MEC（最小包围圆）作为对照基准
3. Lipschitz 界 / 灵敏度分析
4. R_eff ∈ [1000, 1500] 的有效接收半径接入
5. 与问题 2/3/4 的形式化接口
6. 重做表 3 数据（修正 v2 n=1 D=1800 错值）
7. **v3.1**：`_wrap_alpha` + Jung 定理 ρ_min ≤ D/√3 + 5 m 下界 + 输出契约 (c*, ρ*)
8. **v3.5.x**：图修复（孤儿图 bug + fig7 根本性修复 + 中文乱码修复 + PIL/OpenBLAS 内存错误）

## 一键运行
```bash
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第一问/v3"
setup_env.bat
PYTHONIOENCODING=utf-8 python -X utf8 verify_v3.py
```
应看到 `[OK] v3 全部完成`。当前最新版本 **v3.5.6.1**（fig7 修复 + 中文乱码修复 + PIL 内存修复 + OpenBLAS 单线程修复）。

**重要**：verify_v3.py 内部已自动设置 `OPENBLAS_NUM_THREADS=1`；手动跑 PDF 生成时建议先跑 `setup_env.bat`。

## 使用方法（详细）

### 1. 一站式（推荐）
```bash
setup_env.bat                        # 注入 OPENBLAS_NUM_THREADS=1
python -X utf8 verify_v3.py          # 自检 + 重画 + PDF
```
看到 `[OK] v3 全部完成` 即成功。

### 2. 分步
```bash
setup_env.bat
python -X utf8 problem1_core_v3.py      # 9/9 自检
python -X utf8 regen_figures.py         # 重画 7 张图
python -X utf8 gen_problem1_pdf_v3.py   # 生成主交付 PDF
```

### 3. 单独跑 PDF 生成（手动）
```bash
setup_env.bat
OPENBLAS_NUM_THREADS=1 python -X utf8 gen_problem1_pdf_v3.py
```

### 4. 公共 API
```python
from problem1_core_v3 import solve_problem_1
r = solve_problem_1(
    dets=[(0, 0), (100, 0), (50, 80)],
    thetas=[10.0, -10.0, 90.0],
    R=1800.0, eps_deg=1.0, N_disk=64, R_eff=1500.0
)
# r = {poly, n_vertices, D, A, B, O, r, covered, max_offset,
#      mec_radius, mec_center}
```

## 图清单（7 张）

| 图 | 内容 | 关键数据 |
|---|---|---|
| fig1_three_typical | 三类典型情形（n=1 / n=3 一致 / n=3 矛盾） | D=2999.5 / 2499.5 / 0.0 m |
| fig2_diameter_convergence | D 关于检测点数 n 的收敛曲线 | 3 条 R_eff 截断对比 |
| fig3_sensitivity_eps | D(ε) 灵敏度 + Lipschitz 界 | n=2 反向扇形，渐近紧 |
| fig4_R_eff_truncation | E[D] 关于 R_eff 的曲线 | 50 次采样 ±std |
| fig5_MEC_vs_diameter | MEC 半径 vs 直径圆半径 | r_mec ≤ D/2 散点图 |
| fig6_cover_geometry | 覆盖几何三情形（covered/not-covered/borderline） | 直径圆 + MEC 圆可视化 |
| fig7_grid_overview | 3×3 检测点网格概览 | D=2971.3 m n_verts=3（统一朝向 +x） |

## 文件
- `INDEX.md` — 完整索引（目录树 / 文件用途 / API / 启动 / 产物）
- `paper_v3.md` — 中文论文草稿（11 章节）
- `paper_zh.md` — v3.3 中文版论文（备用）
- `compare_to_修正版.md` — 与修正版横向对比 + v3.1 落地清单
- `CHANGELOG_v3.md` — v3 → v3.5.6.1 演进记录
- `RELEASE_NOTES_v3.5.4.md` — v3.5.x 发布说明（图修复明细）
- `SUBMISSION_CHECKLIST.md` — 国奖级提交清单（26 项）
- `DELIVERY.md` / `CHECKLIST_v3.md` / `GAPS.md` — v3 原始版本遗留

## 产物
- `问题一建模_v3.pdf` — **主交付 PDF**（11 页 / 652 KB / 中文 + Unicode 数学符号）
- `问题一建模_v3_zh_v33.pdf` — v3.3 中文版 PDF 备份（10 页 / 654 KB）
- `figures/*.png` — 7 张可视化（中文正常显示 / 共 460 KB）
- `problem1_v3_results.json` — 图 + PDF 清单（v3.5.6.1）
- `logs/verify_v3.5.6.1.log` — 一站式验证日志
