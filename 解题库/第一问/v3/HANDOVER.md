# 上下文移交说明（HANDOVER）

> 用途：把当前 Claude 会话的工作上下文交给下一个 AI（"cowork"）继续维护
> 日期：2026-09-12
> 移交人：Claude（fable 5.1）

---

## 一、项目背景

**CUMCM 2026 B 题**（CUMCM = 全国大学生数学建模竞赛）建模仓库。题目是"无人机/机器狗协同定位干扰源"：
- **问题 1**：已知 n 个检测点坐标 + 示向度（含 ±1° 误差 + R_eff ∈ [1000,1500] 截断），构造可定位区域 P₁，求直径 D，判断直径圆是否覆盖 P₁
- **问题 2**：在问题 1 基础上选第二检测点 S₂，使最坏情况定位误差最小（主模型 J_robust + 候选区域 C_η）
- **问题 3、4**：路径规划、资源分配（暂未实现）

附件 1 = 5 个检测点的真实数据；附件 2 = 接口文档（R_eff、5 米下界、有效接收半径等约定）。

## 二、当前状态

**问题 1 = v3.5.6.1 全部完成 + 已停止开发**

修复演进：
- v3.0：核心算法 + 命题 1–5
- v3.1：`_wrap_alpha` + Jung 定理 ρ_min ≤ D/√3 + 5 m 下界 + 输出契约 (c*, ρ*)
- v3.5.0：fig1–fig7 孤儿图 bug 修复（regen_figures.py）
- v3.5.1–v3.5.5：fig7 根本性修复 + 中文乱码修复
- v3.5.6：PIL 内存错误修复（font_manager 简化）
- **v3.5.6.1**：OpenBLAS 多线程内存错修复（`OPENBLAS_NUM_THREADS=1`）

**问题 2 = 第二问/v3/ 已落盘改进定稿（16 项改动）**

未实现功能：
- 问题 3、4（路径规划、资源分配）
- 附件 1 真实数据驱动的端到端 demo

## 三、目录结构（关键）

```
解题库/
├── 第一问/
│   └── v3/                       ← 本仓库（v3.5.6.1 已停止）
│       ├── INDEX.md              ← 总索引（先读这个）
│       ├── README.md             ← 快速上手
│       ├── STATUS.md             ← 状态声明（已停止开发）
│       ├── SUBMISSION_CHECKLIST.md ← 国奖级提交清单
│       ├── CHANGELOG_v3.md       ← v3 → v3.5.6.1 完整演进
│       ├── RELEASE_NOTES_v3.5.4.md ← v3.5.x 发布说明
│       ├── HANDOVER.md           ← 本文件
│       │
│       ├── problem1_core_v3.py   ← 核心算法库（19 KB）
│       │                            public API: solve_problem_1(dets, ths, R, eps_deg, R_eff)
│       │                            包含：HPI / 旋转卡壳 / 覆盖判据 / MEC(Welzl) / Lipschitz / _wrap_alpha
│       │
│       ├── regen_figures.py      ← 7 张图重画脚本（16 KB）
│       ├── gen_problem1_pdf_v3.py ← 正式 PDF 生成器（17 KB）
│       ├── gen_problem1_pdf_v3_zh.py ← v3.3 中文 PDF 生成器（22 KB）
│       │
│       ├── verify_v3.py          ← 一站式验证（1.3 KB）
│       ├── setup_env.bat         ← 一键环境（设 OPENBLAS_NUM_THREADS=1）
│       │
│       ├── figures/              ← 7 张 PNG（中文正常显示 / 共 500 KB）
│       ├── logs/                 ← 验证日志（verify_v3.5.6.1.log / _final.log）
│       │
│       ├── 问题一建模_v3.pdf     ← 主交付 PDF（11 页 652 KB）
│       ├── 问题一建模_v3_zh_v33.pdf ← 中文版 PDF（10 页 654 KB）
│       │
│       ├── paper_v3.md           ← 中文论文草稿（11 章节）
│       ├── paper_zh.md           ← v3.3 中文论文（16 KB）
│       ├── compare_to_修正版.md  ← 与修正版对比
│       │
│       ├── figure_style.py / fig_style.mplstyle / problem1_extra_figs.py
│       │   ← v3.3/v3.4 升级套件（用户裁决保留）
│       │
│       ├── DELIVERY.md / CHECKLIST_v3.md / GAPS.md
│       │   ← v3 原始遗留文档
│       │
│       └── requirements.txt      ← numpy/matplotlib/reportlab/pypdf
│
└── 第二问/
    └── v3/                       ← 问题 2 改进定稿
        ├── 问题二建模_v3.md       ← 中文论文（11 节）
        ├── paper_v3_diff.md       ← 12 条改进 + 示范重写
        ├── problem2_core_v3.py   ← 核心算法库（11 KB）
        ├── problem2_analysis_v3.py ← 5 张图
        ├── gen_problem2_pdf_v3.py ← PDF 生成器
        ├── verify_problem2_v3.py ← 一站式验证
        └── 问题二建模_v3.pdf      ← 主交付 PDF（16 页 642 KB）
```

## 四、公共 API（最重要）

```python
# 问题 1 核心
from problem1_core_v3 import solve_problem_1
r = solve_problem_1(
    dets=[(0, 0), (100, 0), (50, 80)],   # 检测点坐标
    thetas=[10.0, -10.0, 90.0],          # 示向度（度）
    R=1800.0,                            # 全局半径上限
    eps_deg=1.0,                         # 角度误差 ±ε
    R_eff=1500.0,                        # 有效接收半径
    N_disk=64                            # 圆盘离散
)
# 返回字段：poly, n_vertices, D, A, B, O, r, covered, max_offset, mec_radius, mec_center
# (c*, ρ*) = (mec_center, mec_radius) 是问题一→问题三/四的标准交接量
# 停止判据：ρ* ≤ 20 米
```

```python
# 问题 2 核心
from problem2_core_v3 import (
    classify_G, build_P2, sample_F1,
    J_robust, J_proxy, grid_search_J_robust, candidate_region
)
Gs = sample_F1(S1=(0, 0), theta1_deg=0.0, N_d=60, N_w=21)
r = J_robust(S2=(800, 0), S1=(0, 0), theta1=0.0, G_samples=Gs)
# r = {max_rho, N0, N1, N2, J_robust}
res = grid_search_J_robust(S1=(0, 0), theta1=0.0, R_Omega=1800, R_eff=1500, L_min=992)
# res = {J_star, S2_star, results}
eta_pts = candidate_region(res["results"], res["J_star"], eta=0.2)
```

## 五、启动命令

```bash
# Windows 环境（Git Bash）
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第一问/v3"
PYTHONIOENCODING=utf-8 python -X utf8 verify_v3.py
# 应看到：[OK] self-test passed (9/9) → [OK] 7 张图全部重画完成 → [OK] v3 全部完成

# 单步
python -X utf8 problem1_core_v3.py     # 自检
python -X utf8 regen_figures.py        # 重画 7 张图
python -X utf8 gen_problem1_pdf_v3.py  # 生成主 PDF

# 第二问
cd "C:/Users/LENOVO/Desktop/CUMCM2026Problems/解题库/第二问/v3"
PYTHONIOENCODING=utf-8 python -X utf8 verify_problem2_v3.py
```

## 六、已知约束（必须遵守）

1. **OPENBLAS_NUM_THREADS=1** —— 否则会触发 "Memory allocation still failed"
2. **PYTHONIOENCODING=utf-8** —— 否则会触发 GBK 编码错（中文路径）
3. **matplotlib 中文字体** —— 只注册 1 个 SourceHanSansCN-Normal.otf，sans-serif 列表 2 项，避免 PIL 内存爆
4. **figure_style.apply_style() 不要调用** —— 只取其 PALETTE 字典，避免字体设置覆盖
5. **每次 verify 跑完记得删 `__pycache__/`** —— 否则会污染提交

## 七、修复史速查

| 版本 | 修复 |
|---|---|
| v3.5.0 | fig1–fig7 孤儿图 bug（Case A 越界、震荡、负直径、越线、标签错、D=0） |
| v3.5.1 | `_draw_circle` r≤0 守卫 + fig7 抖动 |
| v3.5.4 | fig7 根本性修复（统一朝向 +x + 间距 150 m → D=2971.3 m） |
| v3.5.5 | matplotlib 中文字体配置 |
| v3.5.6 | font_manager 简化（避免 PIL 内存爆） |
| v3.5.6.1 | OpenBLAS 单线程（避免 numpy 多线程内存错） |

## 八、用户偏好

- 用户重视**数学建模国奖级**论文质量
- 用户喜欢**多轮迭代**逐步完善（v3 → v3.1 → v3.5.x）
- 用户希望**所有图都有中文标题**，不接受乱码方框
- 用户裁决：**野脚本保留**（figure_style.py / fig_style.mplstyle / problem1_extra_figs.py / gen_problem1_pdf_v3_zh.py / paper_zh.md）
- 用户曾断言"图内容本身有误"，后通过真因诊断 + 修复 + 视觉验证确认

## 九、仓库大小

- 第一问 v3：1.89 MB（28 文件 + figures/ + logs/）
- 第二问 v3：~640 KB（10 文件 + figures/ + 1 PDF）

## 十、协作建议

1. **先读 INDEX.md** —— 总索引已经写好
2. **再读 STATUS.md** —— 了解停止声明
3. **跑 verify_v3.py 验证** —— 确认环境 OK
4. **如要修改代码** —— 看 CHANGELOG_v3.md 顶部版本号 + 这次修复的具体段落
5. **如要继续问题 3/4** —— 复用 problem1_core_v3.py 作为基础库，新建 v4/ 目录
6. **如要加新功能** —— 不要修改 v3.5.6.1（已停止），新建分支/目录

## 十一、用户已给出的关键反馈（不要忘记）

1. "这些图都是第一问的" —— 用户发现 fig8/fig9 错位，已删
2. "我怀疑图片内容本身有误，所以让你看" —— 触发了 fig1–fig7 修复
3. "这图片全是乱码啊" —— 触发了中文字体配置
4. "5 处修正"指的是 `compare_to_修正版.md` 第 7 节的 6 条可借鉴动作
5. 用户要求"评价思路"时，希望按优先级（致命/重要/锦上添花）分档输出
6. 用户希望**改进示范重写**而非泛泛建议（"全部展开 + 示范重写"）
7. 用户希望**关键内容落盘**到 README/INDEX/CHANGELOG，不要只在对话里说

## 十二、当前会话结束状态

最后一次 verify_v3.py 输出（2026-09-12）：

```
[OK] self-test passed (T1–T10)
[OK] 7 张图全部重画完成（修正 v3.3 孤儿图 bug）
[OK] v3 全部完成
产物：C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第一问\v3\问题一建模_v3.pdf
```

**所有任务已完成，仓库状态稳定。**
