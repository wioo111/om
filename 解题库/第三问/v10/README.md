# 第三问 v10：路线专项迭代

当前用户的一键演练入口位于仓库根目录 `第三问_一键接入演练.cmd`，已通过 `演练调试/candidates.py` 选择本目录 `strategy_task.py:OpticalTaskP3`。最新题意驱动优化与验证见 [P3_TASK_OPTIMIZATION.md](../../演练调试/P3_TASK_OPTIMIZATION.md)。下文是旧路线专项交付及 `run_v10.py` 的说明；该历史入口仍默认v8，不代表当前一键候选，也不自动调用正式测试。

本包以官方演练动作完全吻合的 v8 为基础，提供只替换路线排序的 v10 候选。它是统一入口，不再要求分机器或按角色合并。

**本轮结论：保留 v8 为默认主用版。** v10 在 114 个独立场景全部清除，但主场景改善没有达到统计确认；30 局 N=15 从 v8 的 214.97 变为 v10 的 215.71 s/个，没有取得专项提速。暂不以候选替换主用策略。

官方案例 `W3QD-ZG2B-MBCG-39XH` 的 **15/15 全清、203.11 s/个** 属于已完成的 v8 演练。本版的新表现以 `results/路线专项验证.md` 为准，不能沿用该单局官方成绩。

## 使用

在本目录安装依赖：

```powershell
python -m pip install -r requirements_collab.txt
```

先检查实际选择的策略和源码版本，此命令不连接模拟器：

```powershell
python -X utf8 run_v10.py --check
```

在官方模拟器中手动开始第三问演练后运行，默认使用保留的 v8：

```powershell
python -X utf8 run_v10.py --robot-id "你的参赛队号"
```

需要演练路线候选时，明确选择 v10：

```powershell
python -X utf8 run_v10.py --strategy v10 --robot-id "你的参赛队号"
```

每轮单独保存至 `results/official_runs/时间_实际策略名/`，包括 `version.json`、实际执行的源码副本、`actions.jsonl` 与 `result.json`。避免仅从目录名或旧的 `live_v8` 文件名前缀判断版本。

## 本次改动

- `strategy_v10.py` 继承 v8，仅替换 `_route` 方法。
- `route_search.py` 对不超过 13 个当前规划点求固定起点、自由终点的最短访问顺序；更大点集保留输入顺序作为候选，并比较多个起点的最近邻路径，再做反转和连续 1–2 点重插入。
- 所有搜索站位的覆盖约束、定位测量、清除、失败恢复及停止条件沿用 v8。
- 规划只使用已发现目标的估计位置和待补搜站位，不读取真实源位置、真实源数量、模拟器种子或未来响应。

这里的“最短”仅指不超过 13 个**当前固定规划点**的访问顺序。目标估计和搜索需求会继续变化，不能据此宣称整轮在线任务达到全局最优。

## 实验与证据

- `evidence/官方演练与路线分析.md`：官方单局成绩、逐段里程及五次失败清除的额外距离。
- `results/development_01/report.json`：21 个开发场景。路线版比 v8 平均少走 402.10 m/局、快 7.40 s/个，全部清除。
- `results/holdout_cases.json`：冻结候选后新生成的 70 个主场景、20 个额外 N=15 场景、24 个压力场景。
- `results/holdout_01/report.json`：独立对照的逐局数据、汇总及对应源码快照。
- `route_trials.py`、`route_reactive.py`、`route_guarded.py` 是未采用的开发对照，官方运行入口不导入它们。
- `results/development_02/`、`development_03/` 分别保存测准后重新选路、只调整最终访问顺序的补充开发对照；各 21 局全清，但没有超过首个路线候选的开发结果。
- `benchmark_routes.py` 可复现实验；输出目录必须是尚不存在的新目录，避免覆盖证据。

复现独立对照会重新运行 228 局完整模拟：

```powershell
python -X utf8 benchmark_routes.py --cases results\holdout_cases.json --strategies v8,route --output reproduced_holdout --workers 2
```

本地模拟与官方模拟使用同一个状态更新驱动，但随机场景和测向误差场不同。本地多案例结果用于比较改动，不代替官方演练。
