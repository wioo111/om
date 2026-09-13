# 第四问当前版本

当前演练和正式入口均使用 `strategy_route_probe.py:RouteProbeP4`，运行名
`RouteProbeP4_zero_detour`。源码SHA256：
`16e69149d6655d5c5e770a19547ec5688d7366e571ef2e9c03424fda613f468f`。

结果按离线模拟、真实演练、正式入口记录分开整理在
[第四问结果](../../结果汇总/第四问.md)，逐场数据在
[第四问.json](../../结果汇总/第四问.json)。完整本轮算法和配对比较见
[ROUTE_ROUND2_REPORT.md](ROUTE_ROUND2_REPORT.md)。

本轮独立确认56场、固定半径边界112场全部清除并正常停止；相对上一版HuntP4，
合并平均T/N由523.08降至508.16秒/源。51个配对场景耗时退步，最差增加18.26%，
全部保留在结果中。尚未整体达到300—400秒/源，当前已停止继续调参。

## 运行

使用Python 3.13，已验证的运行依赖和测试依赖见 `requirements-route.txt`。
下列命令从仓库根目录执行：

```powershell
python -m pip install -r 解题库/第四问/v6/requirements-route.txt
python 解题库/第四问/v6/run_route_local.py --strategy RouteProbeP4 --N 10 --seed 993302 --error-mode fixed --reception-range 1000 1500 --output local_result.json
第四问_一键接入演练.cmd -Check
第四问_一键接入正式.cmd -Check
```

`-Check`仅加载策略，不联网或开启测试。实际接入前在模拟器中手动开启正确的
问题和模式，再双击对应脚本。正式说明见[正式运行](../../正式运行/README.md)。
队号由环境变量 `JAMMERS_ROBOT_ID` 或本机 `tools/practice.local.json` 提供，
第一次运行也可以交互输入。仓库只提供空白配置模板，不提供真实队号。

离线错误模式为random/fixed/edge；固定半径使用1000 1000或1500 1500。
只有全清、正常停止及成本一致才算离线验收通过，step_limit不能算成功。

## 保留的版本与实现边界

- FastP4：冻结原基线，`strategy_fast.py`；正式脚本通过 `-P4Strategy FastP4` 回退。
- FinishP4、HuntP4：可运行的上一轮版本，离线入口可显式选择。
- RouteAwareP4：联合规划扫描站和已定位清除任务。
- RouteProbeP4：在RouteAwareP4原定移动线段上增加有限补测，无额外绕路，并保存未完成扫描动作。
- CostAwareP4：历史未通过候选，不是当前默认。只复用其中独立的有限光学覆盖函数。
- `discovery_joint_prune.py`：仅完成组件测试的研究方案，未接入当前策略。

策略不读取源总数、种子、真实位置或半径；no_signal不用于第四问1000米空间排除。
发现16个不同源频道后可以停止未知频道检测，少于16源仍要完成连续覆盖证明。
失败clear推进有限计划，成功后恢复扫描队列；固定点重复测向不当作独立新信息。

全部运行模块在本目录内，`problem1_v4_inline.py`为已有内联依赖，
无需从本机第三问目录补模块。几何和历史实验脚本不会随策略导入自动执行。
本目录其他带轮次名称的报告是历史记录，其当时选型不能覆盖当前README和正式入口。

## 检查与复现

```powershell
cd 解题库/第四问/v6
python -m pytest test_route.py test_route_probe.py test_route_standalone.py test_discovery_prune.py test_hunt.py test_local_hunt.py test_discovery_compact.py test_discovery_coverage.py test_discovery_mesh.py test_discovery_rings.py test_finish.py test_cost.py -q
python route_round2_experiment.py --stage development --label my_new_development --variants HuntP4 RouteAwareP4 RouteProbeP4 --workers 3
```

确认和边界实验只会在显式指定 `--stage confirmation` 或 `--stage boundary` 时运行。
已有确认种子和结果已公开，不能再次调参后声称是新的独立验证。
GitHub发布脱敏逐场数据、源码、冻结哈希和测试；原始运行日志、整目录源码快照、
交付ZIP和本机配置保留在本地，不自动推送。
