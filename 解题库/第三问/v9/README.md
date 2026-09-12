# 第三问 v9：统一合并候选

**独立验证：94 局全部清除，主场景均值 253.68 s/源；v8 为 253.03 s/源。未证明稳定提速，200 s 目标未达到，v8 继续保留为性能基线。**

算法已经收敛为一个入口：[strategy_v9.py](strategy_v9.py)。本目录可独立复制运行，无需外部 A/B 交付目录。v8 公共几何和驱动随包提供，原 `v5` 目录保持原样。

独立实测见 [验证报告](results/validation_v9.md) 和 [逐局结果](results/validation_v9.json)。200 s 指包含移动、切频、检测、清除和收尾的每源虚拟时间，不是程序现实运行时间。

## 运行

本机环境：Python 3.14.4、NumPy 2.4.4。

```powershell
python -m pip install -r requirements_collab.txt
```

在官方模拟器中登录并启动所需演练、接口就绪后：

```powershell
python -X utf8 run_v9.py --robot-id "你的参赛队号"
```

本次迭代没有连接官方模拟器。入口只连接已启动的测试，并将实际算法代码快照、版本与逐动作日志写入 `collab/live_results/时间戳/`。

v8 回退入口：

```powershell
python -X utf8 robot.py AdaptiveV8 "你的参赛队号"
```

## 合并后保留的改动

- 修复节点重插入不能接受真实缩短的问题；同时比较三个起始节点，对开放路线做 2-opt 和重插入优化。
- 统一接近目标的测点选择：朝估计位置移动，侧移 40 m，试清半径 80 m；失败后沿用严格补测和清除规则。
- 定位区域包围半径不超过 300 m 时，暂缓沿途远处补测，接近目标后再精测。
- 沿途对已发现频道取得的无信号信息，也用于更新该源定位区域，避免继续依据过时的位置估计规划路线。
- 保留 A 的两种覆盖权重与站点比较方式；真实清除计数、误差约束、无信号覆盖证明和所有退出条件继承经过验证的 v8。

21 个开发候选的结果见 [开发记录](results/development_summary.md)，对应源码保存在 `results/snapshots/`。开发记录用于追溯，运行入口始终只使用本目录的单一 v9 策略。

## 后续修改后的验证

修改算法后，针对改动运行必要检查；无需反复运行已通过且未变化的相同代码。

```powershell
python -X utf8 -m unittest test_v9 -v
```

本轮独立场景已经公开，之后属于可分析的回归数据。需要验证新版本时，应先固定源码，再生成新场景：

```powershell
python -X utf8 -m collab.bench make-suite --kind validation --out validation_next.json
python -X utf8 validate_v9.py --suite validation_next.json --output results/validation_next.json
```

验证器并行评估 v8 和 v9，比较同场景虚拟耗时，并记录算法与公共文件哈希；不混合不同机器、不同场景的绝对均值。整个流程不做视觉复查。
