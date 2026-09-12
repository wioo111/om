# 机器 A 开工指令

继续优化第三问，基于冻结的 v8，职责只限路线、目标顺序、补充覆盖站位及站位移动。当前历史移动耗时约 177.7 s/源，占总耗时 70%，优先改善 N=10–12 的稀疏场景。

先读 `collab/README.md` 和 `strategy_v8.py`。只修改 `collab/route_candidate.py`，保留 RouteMixin 和 make_strategy 接口；可以重写 _next_destination、_cover_route、_build_cover_route、_route、_refine_station、_explore_action。新增状态使用 route_ 前缀。

先提出一个明确的路径改进假设，再实现并与同场景 v8 配对验证。每轮最多比较 3–4 个有明确差异的方案，避免大范围无目的参数扫描。使用：

```powershell
python -X utf8 -m collab.bench run --candidate collab.route_candidate:make_strategy --role A --label A01
```

换版本用新 label。工具自动缓存公共基线。不要修改模拟器、速度、角误差、接收半径、计时、几何核心或全清停止条件；不读取源真值、种子，不丢弃失败场景。禁止视觉复查、反复审计。

到交接时只交最佳候选文件、配对结果 JSON、最慢/失败轨迹，以及五行改动与结果说明；若没有改善，如实报告并保留 v8。不要把整个工作目录覆盖到其他机器。C 负责新场景验收及组合。
