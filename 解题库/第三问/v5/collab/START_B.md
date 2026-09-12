# 机器 B 开工指令

继续优化第三问，基于冻结的 v8，职责只限扫描选择、补测时机、交会测点及清除失败后的补测。当前历史检测耗时约 58.4 s/源，占总耗时 23%；重点减少无信息增益的扫描与补测。

先读 `collab/README.md` 和 `strategy_v8.py`。只修改 `collab/measure_candidate.py`，保留 MeasureMixin 和 make_strategy 接口；可以重写 _start_scan、_local_action、on_measure、on_clear。新增状态使用 measure_ 前缀，构造函数必须调用 super()。不改变 State、Track 既有字段含义。

每次验证一个明确假设，例如在覆盖进度与目标不确定性之间分配检测，或在已有几何约束下选择更短的补测位移。单纯在同一点重复测量不能降低固定误差。每轮最多比较 3–4 个有明确差异的方案。使用：

```powershell
python -X utf8 -m collab.bench run --candidate collab.measure_candidate:make_strategy --role B --label B01
```

换版本用新 label。工具自动缓存公共基线。不要修改模拟器、速度、误差、接收半径、计时、几何核心、路线方法或全清停止条件；不读取源真值、种子，不丢弃失败场景。禁止视觉复查、反复审计。

到交接时只交最佳候选文件、配对结果 JSON、最慢/失败轨迹，以及五行改动与结果说明；若没有改善，如实报告并保留 v8。C 负责新场景验收及组合。
