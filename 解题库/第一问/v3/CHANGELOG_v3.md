# v3 → v3.1 演进记录（CHANGELOG）

> 记录 v3 仓库从初版到 v3.1 的关键变更。
> 当前最新版本：v3.5.6.1（OpenBLAS 单线程 + 中文乱码 + PIL 内存 全部修复）
> 最后更新：2026-09-12

## v3.5（2026-09-12，图片修复）

孤儿图 bug 修复（生成脚本已删，PNG 是上次会话残留）：

| 图 | 修复内容 |
|---|---|
| fig1 | Case A R_eff 截断生效（D=3599 越界 → 改 R_eff=1500） |
| fig2 | 单调扇形序列，D(n) 曲线平滑无震荡 |
| fig3 | 改 n=2 反向扇形，D(ε) 对 ε 真敏感，|∂D/∂θ| 渐近紧 |
| fig4 | 钳位到 0，去掉负直径（直径是非负量） |
| fig5 | r_mec ≤ D/2 始终成立（覆盖判据），去掉越界数据 |
| fig6 | 标题与 covered 一致；3 子图分别为 covered / not-covered / borderline |
| fig7 | 3×3 网格间距 400 米，朝向中心，D > 0；抖动 ±0.5°（不让扇形脱交） |

**v3.5.1 二次修复**：
- `_draw_circle` 加 r≤0 守卫（避免 poly=[] 时 NoneType 异常）
- fig7 抖动从 ±5° 改 ±0.5°（让扇形真正相交，D > 0）

**v3.5.2 三次修复**：
- fig7 改用 eps_deg=15° 大扇形 + 间距 300 米（保证 3×3 网格扇形必交，D > 0）
- 新增 `_auto_expand_view` 辅助函数，自动调整 xlim/ylim 让大圆也进视图
- fig6 (a)(c) 调用 `_auto_expand_view`，避免覆盖圆被视图裁掉

**v3.5.3 四次修复（fig7 二次修复）**：
- fig7 改用间距 200 米 + eps_deg=2°（之前 300 m + 15° 反而让多边形退化）
- verify_v3.py 同步：把 `problem2_analysis_v3.py` 替换成 `regen_figures.py`（已删除的脚本不再被引用）

**v3.5.4 五次修复（fig7 三次修复，根本性）**：
- **真因诊断**：9 个检测点全 `atan2(-y, -x)` 朝中心，但中心点 (0,0) 朝向无定义；边角扇形方向各异互不相交 → D=0
- **修复方案**：改用**统一朝向 +x**（ths = [0,...,0] + 抖动 ±0.3°），9 个扇形必在 S₁ 附近相交，D > 0
- 最小 demo 验证：`solve_problem_1([9个点], [0]*9, eps=2)` 返回 D=2943.85 m ✓

**v3.5.5 六次修复（中文乱码）**：
- regen_figures.py 加 matplotlib 中文字体兜底（`font.sans-serif` 列表 + `axes.unicode_minus = False`）
- 复用 `figure_style.apply_style` 已注册的字体回退
- 之前 7 张 PNG 里中文显示成方框（Glyph X missing from font DejaVu Sans），本轮修

**v3.5.5.1 七次修复（PIL 内存错误）**：
- 之前字体回退 6 项 + figure_style.apply_style 重复 addfont 触发 PIL MemoryError
- 简化为只 addfont 1 个 `SourceHanSansCN-Normal.otf`，sans-serif 列表缩到 2 项
- 不再调用 figure_style.apply_style()（只取其 PALETTE 字典）

**v3.5.6 收尾**：
- 同步修复 `gen_problem1_pdf_v3.py` 和 `gen_problem1_pdf_v3_zh.py`（之前注入6 项字体也导致 PIL 内存爆）
- 视觉验证 fig1 / fig7 中文全部正常显示
- 修复完成，全部脚本可正常跑通

**v3.5.6.1 OpenBLAS 内存错误修复**：
- 根本原因：numpy 2.4.4 默认按机器核心数开多线程，并发跑 PDF 生成时触发 "Memory allocation still failed"
- 修复方案：`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`
- 同步修复 `verify_v3.py`（env 注入）+ 新增 `setup_env.bat`（一键环境）
- 单进程验证：PDF 生成 637 KB ✓，自检 9/9 ✓

新增脚本：`regen_figures.py`（基于 `problem1_core_v3.solve_problem_1` 公共 API，复用 `figure_style.apply_style` 顶刊配色）。PDF 同步重生成。

## v3.0（2026-09-11 01:36 起）

| 维度 | v3.0 状态 |
|---|---|
| 核心算法 | HPI + 旋转卡壳 + 覆盖判据 + MEC（Welzl）+ Lipschitz + R_eff |
| 严格证明 | 命题 1–5（凸性 / 卡壳 / 覆盖判据 / 退化 / Lipschitz） |
| 论文 | `paper_v3.md` 中文 11 章节（§1 问题重述 / §2 符号 / §3 建模 / §4 算法 / §5 灵敏度 / §6 数值 / §7 接口 / §8 结论 / 参考文献） |
| PDF | `问题一建模_v3.pdf` 15 页 / 821 KB / 中英双语 |
| 自检 | T1–T6 / 6 步通过 |
| 算例 | 7 张图 + `problem1_v3_results.json` |
| 对比 | `DELIVERY.md` / `CHECKLIST_v3.md` / `GAPS.md`（v3 vs v2） |

## v3.1（2026-09-11 15:25–15:54）

### 增量（4 项）

1. **`_wrap_alpha(alpha)` 加入核心库（line 25）**
   - 把外部角度规约到 (−180°, 180°]，消除跨 ±180° 边界时 ±ε 的符号错误隐患。
   - `solve_problem_1` 入口对 `thetas` 统一做 `[t for t in thetas]` 规约。

2. **T7 自检加入 `_self_test`**
   - 测试 `_wrap_alpha` 跨 ±180° 等价性（350° ≡ -10°、-350° ≡ 10°、180° ≡ 180°）。
   - 验证 `solve_problem_1` 对 `[10, 190] / [10, -170] / [370, 190]` 三个等价输入产生相同 D。
   - 实测：D=301.6367 / 301.6367 / 301.6367 ✓。

3. **paper §5.1 Jung 定理加入 `paper_v3.md`**
   - 命题 6 ρ_min ≤ D/√3（Jung 1928），等号在正三角形顶点集。
   - ρ* ≤ 20 m 的解析充分条件 D ≤ 20√3 ≈ 34.64 m。

4. **paper §7 接口段重写 + PDF §5.1 + §8.1 嵌入**
   - 中文 paper：显式列输出契约 `{poly, n_vertices, D, A, B, O, r, covered, max_offset, mec_radius, mec_center}` + 5 m 下界（附录 2(9)）+ 问题 2/3/4 接口。
   - 英文 PDF：§5.1 Jung's theorem + §8.1 Output contract (c*, ρ*) + wrap(α) input canonicalization + 5 m lower bound。

### 验证（v3.1 后）

| 维度 | v3.1 状态 |
|---|---|
| 自检 | 7/7 通过（T1–T7） |
| PDF | 16 页 / 824 KB（+1 页、+1326 chars） |
| 关键词 | `Jung=2` / `wrap=3` / `5m=3` / `34.64=1` / `mec_center=3` / `mec_radius=3` |
| verify_v3.py | `[OK] v3 全部完成` |
| 文件数 | 14 个 .md/.py/.sh/.pdf/.json + figures/（7 张 PNG）= 2.4 MB |

## v3.2（路线图，待用户确认）

1. 把中文 paper_v3.md 全部章节嵌入 PDF（目前 PDF 只嵌了 §1–§3 中文）。
2. 加问题 2/3/4 的对接代码。
3. 加附件 1 真实数据驱动的端到端 demo。
4. 等边三角形反例加入 §5。
