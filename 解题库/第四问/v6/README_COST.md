> 历史轮次记录。当前演练和正式版本以 [README.md](README.md) 为准。

# 第四问独立代码包

## 最终接入选择

本轮继续使用 `strategy_fast.py:FastP4`。不要自动把公共入口切换到CostAwareP4。

`strategy_cost.py:CostAwareP4` 为有限实验候选。确认集旧版本未通过；交付版本仅修正无效多边形回退，尚未经过新的独立确认。建议整合负责人以 `cost_round/selection.json` 的哈希和状态为准。

```python
from strategy_fast import FastP4
strategy = FastP4()  # 本轮最终选择

# 仅供后续离线研究，未部署：
from strategy_cost import CostAwareP4
ab = CostAwareP4(enable_a=True, enable_b=True, enable_c=False)
abc = CostAwareP4(enable_a=True, enable_b=True, enable_c=True)
off = CostAwareP4(enable_a=False, enable_b=False, enable_c=False)
```

## 环境与本地运行

使用Python 3.10以上，本次实际版本见 `cost_round/environment.json`。安装固定依赖：

```powershell
python -m pip install -r requirements-cost.txt
python -m pytest test_cost.py -q
python run_p4_local.py --strategy FastP4 --seeds 941001 --dir-fracs 0.25 --n-sources 10
```

Shapely 2.x用于候选连续几何运算，pytest仅用于单测。其余算法依赖均在包内；`problem1_v4_inline.py`是第四问原有本地副本，不需要用户电脑的第一问或第三问目录。包内不导入第三问策略继承链。日志会打印实际类名、策略名和源码来源。

历史 `run_p4_local.py` 默认仍为AdaptiveP4，因此本轮必须显式写 `--strategy FastP4`。原演练candidate入口仍加载FastP4；本次仅增加第四问驱动的加载信息打印，不接入新候选。

## 实验命令

以下命令为离线mock，不连接真实模拟器。输出目录必须是新目录，已有证据不会覆盖。

```powershell
python cost_experiment.py --stage development --output new_development --workers 3
python cost_experiment.py --stage confirmation --output new_confirmation --workers 3
python cost_experiment.py --stage boundary --output new_boundary --workers 3
```

这三条是复现/后续评测入口，运行根目录的修正版并不复现旧候选哈希。准确复现本轮确认失败，应使用 `cost_round/evaluated_source/cost_experiment.py` 并指定新的输出目录。即使重新运行相同种子，也不能把已看过的确认集当作新的独立验证。

开发14场×6版本；确认56场×3版本；边界固定1000/1500米各56场×3版本。工人进程数只用于离线场景并行，真实机器人动作保持串行。

仓库共享评测入口的第四问用法：

```powershell
python 解题库/演练调试/benchmark_speed.py --problem 4 --variants fast,ab,abc --reference fast --cases 56 --error-modes fixed,edge --seed-start 945000 --label p4_new_cross --reception-min 1000 --reception-max 1500
```

共享入口的修改另附 `integration/benchmark_speed.patch`，不是独立包运行依赖。独立包中的对应共享入口参数测试会跳过1项；该项已在原仓库通过。

## 证据与文件

- `COST_ROUND_REPORT.md`：选型、逐N表、阶段成本、触发次数、失败和退步说明。
- `ALGORITHM_COST.md`：A/B/C实现、连续覆盖依据、成本下界和有限进度。
- `cost_round/selection.json`：最终类、基线哈希、实验候选与修正候选哈希、未部署状态。
- `cost_round/baseline_manifest.json`、`frozen_fast/`：旧版及依赖冻结。
- `cost_round/preregistered.json`：确认前固定的交叉场景和门槛。
- `cost_round/development*/`、`confirmation/`、`boundary/`：全部逐场与逐动作记录，包含失败。
- `cost_round/evaluated_source/`：参加确认/边界实验的原候选源码。
- `cost_round/*unit*.xml`：单测与确认后回退修正测试结果。

正式测试由原模拟器流程管理，本包不会自动启动正式测试，不读取活动目标真值。
