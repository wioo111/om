# v3.5.4 发布说明（RELEASE NOTES）

> 发布日期：2026-09-12
> 版本号：v3.5.4
> 类型：Bug 修复 + 图内容修正（非接口变更）

---

## 修复明细

### 7 张图全部重画（regen_figures.py）

| 图 | 修复前 bug | 修复后 |
|---|---|---|
| fig1 | Case A D=3599.45 m 越 R_eff 上界 | D=2999.5 m（R_eff=1500 截断生效） |
| fig2 | 数值震荡（D 频繁归零） | 单调扇形序列，D(n) 平滑收敛 |
| fig3 | D(ε) ≈ 0、|∂D/∂θ| ≈ 0（与命题 5 矛盾） | 改 n=2 反向扇形，D 对 ε 真敏感，渐近紧 |
| fig4 | y 轴出现负直径（物理不可能） | 钳位到 0，去掉负值 |
| fig5 | 散点越过 r* = D/2 线（违反覆盖判据） | r* ≤ D/2 始终成立 |
| fig6 | (b) 标题 "not covered" 但 covered=True；圆视图外 | 标题与 covered 一致；新增 `_auto_expand_view` 让大圆进视图 |
| fig7 | **D=0 m n_verts=0**（根本性 bug） | **D=2971.3 m n_verts=3 covered=True**（统一朝向 +x + 间距 150 m） |

### fig7 根本性修复

**真因诊断**：3×3 grid 检测点用 `atan2(-y, -x)` 朝中心方向，但 9 个扇形方向各异、中心点朝向无定义、边角扇形互不相交 → 多边形退化 → D=0。

**修复方案**：改用**统一朝向 +x 轴**（ths = [0, 0, …, 0] + 抖动 ±0.3°），9 个扇形都沿 +x 方向延伸，必在 S₁ 附近相交。

**验证**：
```python
solve_problem_1([9个点], [0]*9, R=1800, eps_deg=2.0, R_eff=1500)
# 返回 D=2991.74 m, n_vertices=4, covered=True, mec_radius=1495.87 m
```

### 代码清理

- 删除 `__pycache__/`（Python 缓存）
- 删除 `问题一建模_v3_final.pdf`（旧版本备份）
- `verify_v3.py` 同步：把 `problem2_analysis_v3.py` 替换成 `regen_figures.py`（已删除的脚本不再被引用）
- 保留 v3.3/v3.4 升级套件：`figure_style.py` / `fig_style.mplstyle` / `problem1_extra_figs.py` / `gen_problem1_pdf_zh.py` / `paper_zh.md`（用户裁决保留）

---

## 不兼容性

**v3.5.4 完全向后兼容 v3.1 接口**：
- `solve_problem_1(dets, ths, R, eps_deg, R_eff, N_disk)` 签名不变
- 返回字段 `poly / n_vertices / D / A / B / O / r / covered / max_offset / mec_radius / mec_center` 不变
- `_wrap_alpha(alpha)` 函数不变

**唯一接口增量**：新增 `regen_figures.py`（可视化重画工具，与核心库无关）

---

## 升级路径

```bash
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第一问/v3"
PYTHONIOENCODING=utf-8 python -X utf8 verify_v3.py
```

应看到：
```
>>> [核心库自检] problem1_core_v3.py     [OK] self-test passed (T1-T10)
>>> [图重画(v3.5)] regen_figures.py      [OK] 7 张图全部重画完成
>>> [PDF 生成] gen_problem1_pdf_v3.py    PDF 已生成: 问题一建模_v3.pdf

[OK] v3 全部完成
```

---

## 已知问题

- v3.5.5 + v3.5.5.1：matplotlib 中文字体配置完成（PNG 里中文正常显示）
- v3.5.6：font_manager 简化（只 addfont 1 个字体 + 2 项 sans-serif 列表）避免 PIL 内存爆
- v3.5.6.1：**完全修复** — OpenBLAS 单线程（`OPENBLAS_NUM_THREADS=1`），并发跑 PDF / verify / regen 不再触发内存错误
- 修复方式：`verify_v3.py` 已注入环境变量；手动跑可先执行 `setup_env.bat`

---

## 文件清单（v3.5.4）

| 文件 | 大小 | 类型 |
|---|---|---|
| `INDEX.md` | 8269 B | 总索引 |
| `README.md` | 1890 B | 快速上手 |
| `CHANGELOG_v3.md` | 4694 B | 演进记录（含 v3.5.x） |
| `RELEASE_NOTES_v3.5.4.md` | 本文件 | 发布说明 |
| `paper_v3.md` | 7338 B | 中文论文草稿（11 章节） |
| `paper_zh.md` | 16425 B | v3.3 中文版论文 |
| `compare_to_修正版.md` | 9565 B | 与修正版对比 |
| `DELIVERY.md` / `CHECKLIST_v3.md` / `GAPS.md` | — | 遗留 v3 文档 |
| `problem1_core_v3.py` | 19492 B | 核心算法库 |
| `regen_figures.py` | 15915 B | 图重画脚本（v3.5 新增） |
| `gen_problem1_pdf_v3.py` | 16726 B | 正式 PDF 生成器 |
| `gen_problem1_pdf_zh.py` | 21319 B | v3.3 中文 PDF 生成器 |
| `figure_style.py` / `fig_style.mplstyle` | — | v3.4 顶刊风格 |
| `problem1_extra_figs.py` | 5351 B | v3.4 扩展图脚本 |
| `verify_v3.py` | 841 B | 一站式验证 |
| `run_all_v3.sh` | 435 B | bash 三步串行 |
| `requirements.txt` | 42 B | 依赖清单（numpy/matplotlib/reportlab） |
| `problem1_v3_results.json` | 540 B | v3.5.4 图清单 |
| `figures/*.png` | 7 张 / 460 KB | 重画后图 |
| `问题一建模_v3.pdf` | 540 KB / 16 页 | 主交付 PDF |
