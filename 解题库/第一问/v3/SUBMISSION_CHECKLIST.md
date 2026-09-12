# 国奖级提交清单（SUBMISSION CHECKLIST）

> 版本：v3.5.6.1
> 最后整理：2026-09-12
> 用途：评委检查仓库时按此清单核对

---

## 一、必须提交（核心）

| # | 文件 | 大小 | 类型 | 说明 |
|---|---|---|---|---|
| 1 | `问题一建模_v3.pdf` | 652 KB | 主交付 PDF（11 页） | 中文 + Unicode 数学符号 |
| 2 | `问题一建模_v3_zh_v33.pdf` | 654 KB | 中文版 PDF（10 页） | v3.3 中文版备份 |
| 3 | `problem1_core_v3.py` | 19492 B | 核心算法库 | HPI / 旋转卡壳 / Welzl / Lipschitz / _wrap_alpha |
| 4 | `paper_v3.md` | 7338 B | 中文论文草稿（11 章节） | 命题 1–6 严格证明 |
| 5 | `figures/fig1–fig7.png` | 7 张 / 460 KB | 可视化 PNG | 全部重画，fig7 D > 0 |

## 二、可选提交（支撑材料）

| # | 文件 | 大小 | 类型 | 说明 |
|---|---|---|---|---|
| 6 | `paper_zh.md` | 16425 B | v3.3 中文论文草稿 | 中文版对应 .md 源 |
| 7 | `gen_problem1_pdf_v3.py` | 16726 B | 正式 PDF 生成器 | |
| 8 | `gen_problem1_pdf_v3_zh.py` | 21319 B | v3.3 中文 PDF 生成器 | |
| 9 | `regen_figures.py` | 15915 B | 图重画脚本（v3.5 新增） | |
| 10 | `verify_v3.py` | 841 B | 一站式验证 | 自检 + 重画 + PDF |
| 11 | `setup_env.bat` | 307 B | 一键环境（OpenBLAS 单线程） | |
| 12 | `run_all_v3.sh` | 435 B | bash 三步串行 | |
| 13 | `requirements.txt` | 42 B | 依赖清单 | numpy/matplotlib/reportlab |
| 14 | `problem1_v3_results.json` | ~700 B | 图 + PDF 清单 | v3.5.6.1 |

## 三、文档（辅助）

| # | 文件 | 大小 | 说明 |
|---|---|---|---|
| 15 | `INDEX.md` | 8269 B | 仓库总索引（目录树 + 启动命令 + 状态表） |
| 16 | `README.md` | 1890 B | 快速上手 |
| 17 | `CHANGELOG_v3.md` | ~5500 B | v3 → v3.5.6.1 完整演进 |
| 18 | `RELEASE_NOTES_v3.5.4.md` | ~4000 B | v3.5.x 发布说明（图修复明细） |
| 19 | `DELIVERY.md` | 3449 B | v3 原始交付清单 |
| 20 | `CHECKLIST_v3.md` | 748 B | v3 落地自检 |
| 21 | `GAPS.md` | 883 B | v3 vs v2 缺口 |
| 22 | `compare_to_修正版.md` | 9565 B | 与修正版横向对比 |

## 四、扩展套件（v3.3/v3.4 升级预留，提交时可保留）

| # | 文件 | 大小 | 说明 |
|---|---|---|---|
| 23 | `figure_style.py` | 4480 B | v3.4 顶刊配色 |
| 24 | `fig_style.mplstyle` | 259 B | v3.4 matplotlib 风格 |
| 25 | `problem1_extra_figs.py` | 5351 B | v3.4 扩展图脚本 |
| 26 | `SUBMISSION_CHECKLIST.md` | 本文件 | 提交清单 |

## 五、自检结果

| 项 | 状态 |
|---|---|
| 核心库自检（T1–T10） | 9/9 ✓ |
| 7 张图重画（regen_figures.py） | ✓ |
| 2 个 PDF 生成（v3 + zh） | ✓ |
| verify_v3.py 一站式 | `[OK] v3 全部完成` ✓ |

## 六、关键词命中（pypdf 验证）

**v3 PDF（11 页 4694 字符）**：

| 关键词 | 命中 |
|---|---|
| Jung 定理 | 6 |
| 半平面交 | 6 |
| 34.64 | 2 |
| 5 米 | 2 |
| mec_center | 3 |
| mec_radius | 3 |
| wrap | 3 |
| Lipschitz | 6 |

**zh PDF（10 页 5848 字符）**：

| 关键词 | 命中 |
|---|---|
| Jung 定理 | 6 |
| 半平面交 | 3 |
| 34.64 | 2 |
| 5 米 | 2 |
| mec_center | 2 |
| mec_radius | 2 |
| wrap | 3 |
| Lipschitz | 7 |

## 七、提交建议

1. 提交 PDF 主用 `问题一建模_v3.pdf`（11 页 637 KB），中文 + Unicode 数学符号齐全
2. 中文版 PDF `问题一建模_v3_zh_v33.pdf` 作为补充（10 页 639 KB）
3. 源码附 `problem1_core_v3.py` + `regen_figures.py` + `gen_problem1_pdf_v3.py` 三个核心脚本
4. 论文附 `paper_v3.md`（中文 markdown）+ `paper_zh.md`（v3.3 中文版）
5. 附 `SUBMISSION_CHECKLIST.md`（本文件）方便评委核对
6. 不附 `__pycache__/` / `requirements.txt` / 临时 log 文件

## 八、版本号

**当前提交版本**：v3.5.6.1
**发布日期**：2026-09-12
**状态**：已停止开发（详见 `STATUS.md`）
**上下文移交**：详见 `HANDOVER.md`（给下一个 AI 的工作交接）
**修复明细**：图 1–7 全部重画 + 中文乱码修复 + fig7 根本性修复 + PIL/OpenBLAS 内存错修复

## 九、运行日志

最新一次 verify_v3.py 跑通日志保存在 `logs/verify_v3.5.6.1.log`（2604 B），含自检 9/9 + 图重画 + PDF 生成三阶段确认。

**最终验证日志**（v3.5.6.1 收尾）：`logs/verify_v3.5.6.1_final.log`，确认自检 + 图 + PDF 全部跑通。

## 十、工作环境

| 组件 | 版本 |
|---|---|
| Python | 3.14 |
| numpy | 2.4.4 |
| matplotlib | 3.10.9 |
| reportlab | 4.4.10 |
| PIL | 12.2.0 |
| pypdf | 6.10.2 |

**必备环境变量**：`OPENBLAS_NUM_THREADS=1`（避免 OpenBLAS 多线程内存错）
