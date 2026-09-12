# 解题库 · v5 权威版本说明

> 更新日期：2026-09-12
> 本文件说明当前项目中**哪些文件是权威版本**，哪些已被废弃。

## 1 权威（请只使用这些）

| 问题 | 目录 | 核心代码 | 实验脚本 | 绘图脚本 | 验收脚本 | 报告 |
|---|---|---|---|---|---|---|
| 第一问 | `第一问/v5/` | `problem1_core.py` | `run_experiments.py` | `plot_figures.py` | `verify_problem1_v5.py` | `第一问完整报告.md` |
| 第二问 | `第二问/v5/` | `problem2_core.py` | `run_experiments.py` | `plot_figures.py` | `verify_problem2_v5.py` | `第二问完整报告.md` |
| 总论文 | `完整论文/` | — | — | — | — | `论文_第一二问.md`（同步自 v5 输出） |

输出目录约定（每个版本目录下）：

```
results/   所有 JSON / CSV 结果（key_numbers.json 是报告中全部数字的唯一真源）
figures/   全部正式插图（只能由 plot_figures.py 生成，禁止手工修改）
logs/      运行日志
```

## 2 已废弃（不要引用其中的数字、公式或图片）

| 位置 | 状态 | 原因 |
|---|---|---|
| `第一问/v3/`、`第二问/v3/` | 废弃 | 早期版本；其全部 PDF/报告数字已过期 |
| `第一问/v4/`、`第二问/v4/` | **废弃** | 见下 |
| `第一问/figures` 之外的 `第一问/*.pdf`、`问题一二 (1).pdf`、`问题一建模*.pdf` | 废弃 | 由旧版本报告生成，含方向写反的 Jung 定理与错误数字 |
| `代码/`、`第一问/problem1_core.py`、`第一问/problem2_analysis.py`、`第一问/problem1_cases.png` | 废弃 | 更早的代码副本，未被任何报告引用 |

### 2.1 v4 被废弃的具体原因（第一问）

1. **Jung 定理不等号写反**：报告写成 $R^*\ge D/\sqrt3$、"$2R^*/D\ge2/\sqrt3$"，
   实际应为 $\frac D2\le R^*\le\frac D{\sqrt3}$，即 $1\le q=2R^*/D\le 2/\sqrt3$。
2. **圆约束逼近描述错误**：代码用切线（外切正多边形），报告却写成"64 条弦的内接多边形"，
   并给出错误误差 0.12 m；正确外扩量为 $r(\sec\frac\pi N-1)$，$N=64$ 时为 **1.809 m**。
3. **正式统计使用 $N=32$**：个别场景 $D$ 的相对误差可达 **13.4 %**。
4. **检测点没有限制在目标区域 $\Omega$ 内**。
5. 把"定位区域一定是凸多边形""顶点数 $\le 8$""$n\ge3$ 才可能不覆盖"当作一般结论
   （实测顶点数最大为 9）。
6. `fig1` 把普通三检测点案例标成"Jung 紧情形"；`fig6` 把实际 $q=1$ 的覆盖案例
   标成"不覆盖"；`fig8` 的 Lipschitz 曲线无严格推导。

### 2.2 v4 被废弃的具体原因（第二问）

1. **信息泄漏（oracle）**：`place_thales(G, d, ...)`、`place_optimal` 等选点函数
   直接使用真实源 $G$ 与真实距离 $d=|S_1G|$。第二次移动前这两者都不可得，
   该策略**不可实现**（v5 中仅保留为显式标注的参考上界）。
2. **仿真未加第一次测量误差**：代码 `theta1 = th`（真实值），与报告声称的
   "$\theta_1$ 加 $\pm1^\circ$ 误差"不符。
3. **失败样本被静默删除**：随机/最佳共线策略只统计"成功子样本"（$N=345,395$），
   空可行域的 `D=0` 被当作优秀结果。
4. **错误的 Thales 几何推导**："$S_2$ 在以 $G$ 为圆心、$d\tan\varepsilon$ 为半径的圆上"
   "$L^*=1.56d$" 等结论均建立在真实 $G$ 已知这一不成立前提上。

v4 的 `figures/` 目录已被清空，v4 报告已加废弃横幅。

## 3 一键复现

```bat
:: 第一问
cd "C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第一问\v5"
python -X utf8 run_experiments.py
python -X utf8 plot_figures.py
python -X utf8 verify_problem1_v5.py

:: 第二问
cd "C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第二问\v5"
python -X utf8 run_experiments.py
python -X utf8 plot_figures.py
python -X utf8 verify_problem2_v5.py
```

两个 `run_experiments.py` 均使用固定随机种子（第一问 20260912；第二问 20260912），
结果可完全复现。

## 4 第三问 / 第四问

按要求**未做任何修改**。需要注意的是：`第三问/` 下的部分历史结果文件中仍出现
"Thales" 等字样（继承自旧第二问结论）。若第三问的文档引用了旧第二问的
"$L^*\approx1.56d$""Thales 圆"等结论，应改为引用本文件第 1 节的 v5 第二问结果
（$L^*\approx1005$ m、$\alpha^*\approx\pm31^\circ$）。这一处尚未处理，属于遗留问题。
