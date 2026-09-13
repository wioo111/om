> 历史轮次记录。当前演练和正式版本以 [README.md](README.md) 为准。

# 第四问 FinishP4 独立实验包

本包是本轮新候选及其证据，当前一键入口仍为FastP4。主门槛通过、附加门槛未过，详见FINISH_ROUND_REPORT.md与transfer_round/selection.json。没有实机新候选测试结果。

## 安装与测试

使用Python 3.10以上，本机测试环境沿用上一轮独立环境。安装依赖和单测：

```powershell
python -m pip install -r requirements-cost.txt
python -m pytest test_finish.py -q
```

包内含独立几何实现、FastP4基线、第四问mock及驱动，不需要第三问目录。strategy_cost.py只提供optical_cover纯函数；CostAwareP4类未启用。

## 正确构造候选

```python
from strategy_finish import FinishP4
from strategy_fast import FastP4

baseline = FastP4()
combined = FinishP4(enabled=True, trim_corners=True)  # 本轮联合候选
only_grid = FinishP4(enabled=False, trim_corners=True)
only_tail = FinishP4(enabled=True, trim_corners=False)
```

只写FinishP4()默认只启用尾段，不能把它当成表中的联合候选。驱动会打印实际类、运行名和来源路径。

## 离线复现

```powershell
python transfer_experiment.py --stage development --label replay_dev --workers 3
python transfer_experiment.py --stage confirmation --label replay_confirm --workers 3
python transfer_experiment.py --stage boundary --label replay_boundary --workers 3
```

已有目录拒绝覆盖。复现旧种子不算新独立验证。各阶段全部动作和失败/退步场景均保存，不只保留成功样本。上述命令不连接模拟器。

证据目录transfer_round/包含实际演练分解、620动作前缀见证、开发/确认/边界报告、代码冻结及选型清单；正式试验门槛不因确认结果修改。当前程序和一键演练默认没有自动切换。
