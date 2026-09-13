# 第四问路线改进第2轮收尾报告

推荐 `RouteProbeP4`；最终新确认56场＋边界112场合计，平均T/N为 **508.16秒/源**，相对HuntP4整体改善 **2.85%**。

**本轮按用户要求收尾，未达到300–400秒/源。报告生成器不部署、不启动演练或正式模拟器。**

统计口径：全清与正常停止同时满足才验收；step_limit不验收。成本均值包括所有有成本记录的失败场景；缺失成本明确计为未记录，不补零。T/N按场均值，N使用评测场景的实际源数；该信息只供事后评测，不提供给策略。P95采用上取整最近秩。最差退步按同场总T相对HuntP4计算。

开发轮仅用于修错和固定参数，逐轮保留全部失败与退步；不混入最终168场均值。确认与边界冻结的策略及依赖哈希必须一致，不能看确认结果后调参再称独立验证。

## 最终168场配对比较

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 168/168 | 168/168 | 168/168 | 168/168 | 523.08 | 6639.04 | 24977.52 | 261.04 | 4.94 | 689.98 | 7724.60 | 0.00% |
| RouteAwareP4 | 168/168 | 168/168 | 168/168 | 168/168 | 508.79 | 6459.72 | 24028.39 | 266.04 | 4.68 | 687.38 | 8016.15 | 17.69% |
| RouteProbeP4 | 168/168 | 168/168 | 168/168 | 168/168 | 508.16 | 6450.15 | 23900.49 | 267.29 | 4.86 | 690.35 | 7783.88 | 18.26% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 660.28 | 603.15 | 553.95 | 510.13 | 469.23 | 449.09 | 415.70 |
| RouteAwareP4 | 639.48 | 584.30 | 540.45 | 490.62 | 468.01 | 438.30 | 400.36 |
| RouteProbeP4 | 640.81 | 579.94 | 540.50 | 490.87 | 472.29 | 438.65 | 394.02 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 4995.50 | 258.51 | 1305.21 | 79.82 |
| RouteAwareP4 | 4805.68 | 244.81 | 1330.18 | 79.05 |
| RouteProbeP4 | 4780.10 | 254.02 | 1336.46 | 79.57 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3083.58 | 257.83 | 1295.03 | 0.00 | 4636.43 |
| HuntP4 | early_clear | 896.80 | 0.00 | 0.00 | 61.39 | 958.19 |
| HuntP4 | localization | 1015.13 | 0.68 | 10.18 | 18.43 | 1044.41 |
| RouteAwareP4 | discovery | 3165.13 | 244.12 | 1320.21 | 0.00 | 4729.45 |
| RouteAwareP4 | joint_optical_clear | 1319.00 | 0.00 | 0.00 | 79.05 | 1398.05 |
| RouteAwareP4 | localization | 321.55 | 0.69 | 9.97 | 0.00 | 332.21 |
| RouteProbeP4 | discovery | 2245.14 | 245.22 | 1287.20 | 0.00 | 3777.56 |
| RouteProbeP4 | joint_optical_clear | 1354.03 | 0.00 | 0.00 | 79.57 | 1433.60 |
| RouteProbeP4 | localization | 266.30 | 0.54 | 7.95 | 0.00 | 274.79 |
| RouteProbeP4 | route_probe | 914.62 | 8.26 | 41.31 | 0.00 | 964.19 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 830 |
| HuntP4 | early_clear_success | 2184 |
| HuntP4 | early_plan_started | 2184 |
| HuntP4 | local_planner.safe_convex_probe | 1 |
| HuntP4 | local_planner.speculative_first_pair | 341 |
| HuntP4 | mesh_coverage_completed | 168 |
| HuntP4 | remaining_scan_route_shortened | 77 |
| RouteAwareP4 | early_clear_miss_advance | 787 |
| RouteAwareP4 | early_clear_success | 2184 |
| RouteAwareP4 | early_plan_started | 2184 |
| RouteAwareP4 | joint_clear_before_scan | 1945 |
| RouteAwareP4 | joint_discovery_completed | 168 |
| RouteAwareP4 | joint_route_planned | 5447 |
| RouteAwareP4 | local_planner.safe_convex_probe | 1 |
| RouteAwareP4 | local_planner.speculative_first_pair | 334 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 10 |
| RouteProbeP4 | early_clear_miss_advance | 816 |
| RouteProbeP4 | early_clear_success | 2184 |
| RouteProbeP4 | early_plan_started | 2184 |
| RouteProbeP4 | joint_clear_before_scan | 1955 |
| RouteProbeP4 | joint_discovery_completed | 168 |
| RouteProbeP4 | joint_route_planned | 5449 |
| RouteProbeP4 | local_planner.safe_convex_probe | 1 |
| RouteProbeP4 | local_planner.speculative_first_pair | 266 |
| RouteProbeP4 | route_probe.held_scan_resumed | 1388 |
| RouteProbeP4 | route_probe.probe_direction | 809 |
| RouteProbeP4 | route_probe.probe_no_signal | 579 |
| RouteProbeP4 | route_probe.zero_detour_probe_issued | 1388 |
| RouteProbeP4 | route_probe_held_scan_resumed | 1388 |
| RouteProbeP4 | route_probe_probe_direction | 809 |
| RouteProbeP4 | route_probe_probe_no_signal | 579 |
| RouteProbeP4 | route_probe_zero_detour_probe_issued | 1388 |
| RouteProbeP4 | sixteen_sources_retire_remaining_stations | 12 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 962004 | 10 | [1000, 1500] | 8.03% | 480.70 | True | True |
| RouteAwareP4 | 962007 | 10 | [1000, 1500] | 3.04% | 192.75 | True | True |
| RouteAwareP4 | 962009 | 11 | [1000, 1500] | 0.89% | 50.89 | True | True |
| RouteAwareP4 | 962011 | 11 | [1000, 1500] | 3.33% | 193.53 | True | True |
| RouteAwareP4 | 962018 | 12 | [1000, 1500] | 0.91% | 61.46 | True | True |
| RouteAwareP4 | 962020 | 12 | [1000, 1500] | 4.00% | 266.30 | True | True |
| RouteAwareP4 | 962028 | 13 | [1000, 1500] | 0.03% | 1.93 | True | True |
| RouteAwareP4 | 962032 | 14 | [1000, 1500] | 9.72% | 539.53 | True | True |
| RouteAwareP4 | 962039 | 14 | [1000, 1500] | 3.07% | 205.83 | True | True |
| RouteAwareP4 | 962041 | 15 | [1000, 1500] | 1.90% | 121.70 | True | True |
| RouteAwareP4 | 962043 | 15 | [1000, 1500] | 11.78% | 645.90 | True | True |
| RouteAwareP4 | 962045 | 15 | [1000, 1500] | 5.00% | 344.85 | True | True |
| RouteAwareP4 | 962047 | 15 | [1000, 1500] | 5.02% | 362.88 | True | True |
| RouteAwareP4 | 962052 | 16 | [1000, 1500] | 0.56% | 40.95 | True | True |
| RouteAwareP4 | 962053 | 16 | [1000, 1500] | 17.69% | 983.28 | True | True |
| RouteAwareP4 | 962054 | 16 | [1000, 1500] | 2.96% | 203.86 | True | True |
| RouteAwareP4 | 963004 | 10 | [1000, 1000] | 0.51% | 36.94 | True | True |
| RouteAwareP4 | 963005 | 10 | [1000, 1000] | 2.88% | 193.87 | True | True |
| RouteAwareP4 | 963010 | 11 | [1000, 1000] | 5.76% | 419.17 | True | True |
| RouteAwareP4 | 963011 | 11 | [1000, 1000] | 5.11% | 359.68 | True | True |
| RouteAwareP4 | 963012 | 11 | [1000, 1000] | 2.53% | 197.86 | True | True |
| RouteAwareP4 | 963013 | 11 | [1000, 1000] | 4.62% | 309.15 | True | True |
| RouteAwareP4 | 963014 | 11 | [1000, 1000] | 3.21% | 231.29 | True | True |
| RouteAwareP4 | 963016 | 12 | [1000, 1000] | 7.15% | 449.39 | True | True |
| RouteAwareP4 | 963019 | 12 | [1000, 1000] | 0.43% | 29.45 | True | True |
| RouteAwareP4 | 963020 | 12 | [1000, 1000] | 4.05% | 314.04 | True | True |
| RouteAwareP4 | 963022 | 12 | [1000, 1000] | 10.05% | 680.08 | True | True |
| RouteAwareP4 | 963023 | 12 | [1000, 1000] | 0.68% | 55.69 | True | True |
| RouteAwareP4 | 963028 | 13 | [1000, 1000] | 0.60% | 46.28 | True | True |
| RouteAwareP4 | 963029 | 13 | [1000, 1000] | 0.19% | 12.73 | True | True |
| RouteAwareP4 | 963030 | 13 | [1000, 1000] | 9.39% | 752.39 | True | True |
| RouteAwareP4 | 963034 | 14 | [1000, 1000] | 3.52% | 251.60 | True | True |
| RouteAwareP4 | 963035 | 14 | [1000, 1000] | 4.11% | 259.99 | True | True |
| RouteAwareP4 | 963036 | 14 | [1000, 1000] | 9.12% | 682.59 | True | True |
| RouteAwareP4 | 963037 | 14 | [1000, 1000] | 0.03% | 2.08 | True | True |
| RouteAwareP4 | 963038 | 14 | [1000, 1000] | 9.94% | 764.07 | True | True |
| RouteAwareP4 | 963039 | 14 | [1000, 1000] | 3.77% | 279.23 | True | True |
| RouteAwareP4 | 963041 | 15 | [1000, 1000] | 7.53% | 462.19 | True | True |
| RouteAwareP4 | 963042 | 15 | [1000, 1000] | 1.62% | 105.95 | True | True |
| RouteAwareP4 | 963043 | 15 | [1000, 1000] | 1.85% | 128.56 | True | True |
| RouteAwareP4 | 963044 | 15 | [1000, 1000] | 8.17% | 581.80 | True | True |
| RouteAwareP4 | 963046 | 15 | [1000, 1000] | 0.67% | 58.91 | True | True |
| RouteAwareP4 | 963053 | 16 | [1000, 1000] | 5.64% | 396.93 | True | True |
| RouteAwareP4 | 963054 | 16 | [1000, 1000] | 3.22% | 284.83 | True | True |
| RouteAwareP4 | 963055 | 16 | [1000, 1000] | 1.57% | 126.15 | True | True |
| RouteAwareP4 | 963113 | 11 | [1500, 1500] | 6.02% | 372.16 | True | True |
| RouteAwareP4 | 963121 | 12 | [1500, 1500] | 2.27% | 140.77 | True | True |
| RouteAwareP4 | 963124 | 13 | [1500, 1500] | 6.99% | 395.83 | True | True |
| RouteAwareP4 | 963138 | 14 | [1500, 1500] | 4.08% | 289.96 | True | True |
| RouteAwareP4 | 963139 | 14 | [1500, 1500] | 1.37% | 95.86 | True | True |
| RouteAwareP4 | 963146 | 15 | [1500, 1500] | 5.39% | 349.51 | True | True |
| RouteProbeP4 | 962004 | 10 | [1000, 1500] | 8.34% | 499.33 | True | True |
| RouteProbeP4 | 962006 | 10 | [1000, 1500] | 0.48% | 35.80 | True | True |
| RouteProbeP4 | 962007 | 10 | [1000, 1500] | 1.34% | 85.14 | True | True |
| RouteProbeP4 | 962009 | 11 | [1000, 1500] | 1.18% | 67.70 | True | True |
| RouteProbeP4 | 962018 | 12 | [1000, 1500] | 1.33% | 90.27 | True | True |
| RouteProbeP4 | 962020 | 12 | [1000, 1500] | 4.85% | 323.17 | True | True |
| RouteProbeP4 | 962021 | 12 | [1000, 1500] | 0.01% | 0.51 | True | True |
| RouteProbeP4 | 962025 | 13 | [1000, 1500] | 0.09% | 5.04 | True | True |
| RouteProbeP4 | 962028 | 13 | [1000, 1500] | 0.66% | 47.39 | True | True |
| RouteProbeP4 | 962032 | 14 | [1000, 1500] | 10.31% | 572.52 | True | True |
| RouteProbeP4 | 962034 | 14 | [1000, 1500] | 0.41% | 24.83 | True | True |
| RouteProbeP4 | 962035 | 14 | [1000, 1500] | 0.15% | 8.43 | True | True |
| RouteProbeP4 | 962038 | 14 | [1000, 1500] | 0.37% | 25.35 | True | True |
| RouteProbeP4 | 962039 | 14 | [1000, 1500] | 10.80% | 723.93 | True | True |
| RouteProbeP4 | 962041 | 15 | [1000, 1500] | 1.84% | 117.90 | True | True |
| RouteProbeP4 | 962043 | 15 | [1000, 1500] | 11.59% | 635.62 | True | True |
| RouteProbeP4 | 962045 | 15 | [1000, 1500] | 5.65% | 389.60 | True | True |
| RouteProbeP4 | 962047 | 15 | [1000, 1500] | 6.02% | 435.20 | True | True |
| RouteProbeP4 | 962053 | 16 | [1000, 1500] | 18.26% | 1014.76 | True | True |
| RouteProbeP4 | 963004 | 10 | [1000, 1000] | 1.12% | 81.74 | True | True |
| RouteProbeP4 | 963005 | 10 | [1000, 1000] | 3.42% | 229.83 | True | True |
| RouteProbeP4 | 963010 | 11 | [1000, 1000] | 6.26% | 454.92 | True | True |
| RouteProbeP4 | 963011 | 11 | [1000, 1000] | 1.28% | 89.76 | True | True |
| RouteProbeP4 | 963013 | 11 | [1000, 1000] | 5.36% | 358.97 | True | True |
| RouteProbeP4 | 963014 | 11 | [1000, 1000] | 1.79% | 129.11 | True | True |
| RouteProbeP4 | 963016 | 12 | [1000, 1000] | 1.53% | 96.26 | True | True |
| RouteProbeP4 | 963020 | 12 | [1000, 1000] | 5.30% | 411.04 | True | True |
| RouteProbeP4 | 963022 | 12 | [1000, 1000] | 11.14% | 753.98 | True | True |
| RouteProbeP4 | 963028 | 13 | [1000, 1000] | 1.41% | 107.97 | True | True |
| RouteProbeP4 | 963029 | 13 | [1000, 1000] | 0.89% | 59.03 | True | True |
| RouteProbeP4 | 963030 | 13 | [1000, 1000] | 8.04% | 644.18 | True | True |
| RouteProbeP4 | 963034 | 14 | [1000, 1000] | 1.52% | 108.33 | True | True |
| RouteProbeP4 | 963035 | 14 | [1000, 1000] | 4.40% | 278.47 | True | True |
| RouteProbeP4 | 963036 | 14 | [1000, 1000] | 9.70% | 726.56 | True | True |
| RouteProbeP4 | 963037 | 14 | [1000, 1000] | 0.91% | 63.34 | True | True |
| RouteProbeP4 | 963038 | 14 | [1000, 1000] | 10.55% | 810.57 | True | True |
| RouteProbeP4 | 963039 | 14 | [1000, 1000] | 4.76% | 352.77 | True | True |
| RouteProbeP4 | 963041 | 15 | [1000, 1000] | 8.04% | 493.57 | True | True |
| RouteProbeP4 | 963042 | 15 | [1000, 1000] | 2.25% | 147.62 | True | True |
| RouteProbeP4 | 963043 | 15 | [1000, 1000] | 2.55% | 177.48 | True | True |
| RouteProbeP4 | 963044 | 15 | [1000, 1000] | 8.42% | 599.22 | True | True |
| RouteProbeP4 | 963046 | 15 | [1000, 1000] | 1.63% | 143.53 | True | True |
| RouteProbeP4 | 963053 | 16 | [1000, 1000] | 7.88% | 554.58 | True | True |
| RouteProbeP4 | 963055 | 16 | [1000, 1000] | 4.20% | 336.61 | True | True |
| RouteProbeP4 | 963113 | 11 | [1500, 1500] | 6.95% | 429.08 | True | True |
| RouteProbeP4 | 963121 | 12 | [1500, 1500] | 2.97% | 184.19 | True | True |
| RouteProbeP4 | 963124 | 13 | [1500, 1500] | 7.53% | 426.30 | True | True |
| RouteProbeP4 | 963136 | 14 | [1500, 1500] | 3.49% | 232.23 | True | True |
| RouteProbeP4 | 963138 | 14 | [1500, 1500] | 4.69% | 333.20 | True | True |
| RouteProbeP4 | 963139 | 14 | [1500, 1500] | 1.84% | 128.79 | True | True |
| RouteProbeP4 | 963146 | 15 | [1500, 1500] | 6.03% | 391.09 | True | True |

`RouteAwareP4` 相对HuntP4的每场成本变化（候选减基线）：移动 -189.83秒、换频道 -13.70秒、检测 +24.97秒、清除 -0.77秒。其平均T/N整体改善为 2.73%；这些差值与上述阶段成本及实际触发次数共同说明收益来源。

`RouteProbeP4` 相对HuntP4的每场成本变化（候选减基线）：移动 -215.41秒、换频道 -4.49秒、检测 +31.25秒、清除 -0.25秒。其平均T/N整体改善为 2.85%；这些差值与上述阶段成本及实际触发次数共同说明收益来源。

## dev01

阶段 `development`；已记录28/28场策略运行。[完整报告](route_round2/dev01/report.json) · [冻结清单](route_round2/dev01/manifest.json) · [原始动作](route_round2/dev01/runs/)

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 14/14 | 14/14 | 14/14 | 14/14 | 507.21 | 6434.67 | 24037.65 | 258.43 | 4.43 | 662.39 | 7654.46 | 0.00% |
| RouteAwareP4 | 14/14 | 14/14 | 14/14 | 14/14 | 499.03 | 6299.44 | 23269.68 | 261.07 | 5.43 | 701.84 | 7498.27 | 6.80% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 646.59 | 528.82 | 576.84 | 512.19 | 487.65 | 421.89 | 376.49 |
| RouteAwareP4 | 681.07 | 549.33 | 527.62 | 493.38 | 481.87 | 407.50 | 352.41 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 4807.53 | 256.71 | 1292.14 | 78.29 |
| RouteAwareP4 | 4653.94 | 258.86 | 1305.36 | 81.29 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3002.96 | 256.21 | 1286.79 | 0.00 | 4545.96 |
| HuntP4 | early_clear | 1003.15 | 0.00 | 0.00 | 63.71 | 1066.87 |
| HuntP4 | localization | 801.42 | 0.50 | 5.36 | 14.57 | 821.85 |
| RouteAwareP4 | discovery | 3102.42 | 258.43 | 1299.64 | 0.00 | 4660.49 |
| RouteAwareP4 | joint_optical_clear | 1292.12 | 0.00 | 0.00 | 81.29 | 1373.40 |
| RouteAwareP4 | localization | 259.39 | 0.43 | 5.71 | 0.00 | 265.54 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 62 |
| HuntP4 | early_clear_success | 182 |
| HuntP4 | early_plan_started | 182 |
| HuntP4 | local_planner.speculative_first_pair | 15 |
| HuntP4 | mesh_coverage_completed | 14 |
| HuntP4 | remaining_scan_route_shortened | 12 |
| RouteAwareP4 | early_clear_miss_advance | 76 |
| RouteAwareP4 | early_clear_success | 182 |
| RouteAwareP4 | early_plan_started | 182 |
| RouteAwareP4 | joint_clear_before_scan | 161 |
| RouteAwareP4 | joint_discovery_completed | 14 |
| RouteAwareP4 | joint_route_planned | 451 |
| RouteAwareP4 | local_planner.speculative_first_pair | 16 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 2 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 961000 | 10 | [1000, 1500] | 4.68% | 295.22 | True | True |
| RouteAwareP4 | 961001 | 11 | [1000, 1500] | 6.80% | 387.37 | True | True |
| RouteAwareP4 | 961005 | 15 | [1000, 1500] | 0.23% | 15.12 | True | True |
| RouteAwareP4 | 961007 | 10 | [1000, 1500] | 5.96% | 394.46 | True | True |
| RouteAwareP4 | 961008 | 11 | [1000, 1500] | 1.07% | 63.77 | True | True |
| RouteAwareP4 | 961010 | 13 | [1000, 1500] | 3.31% | 211.17 | True | True |

实际加载身份：

| variant | 实际类 | 运行名 | 源码 | 该轮源码SHA256 |
| --- | --- | --- | --- | --- |
| HuntP4 | HuntP4 | HuntP4_compact21 | strategy_hunt.py | 33e3de0328b9087c33dd49f037d2c8b86be88aabc2b97e7a229564f9cfdbc25c |
| RouteAwareP4 | RouteAwareP4 | RouteAwareP4_joint21 | strategy_route.py | 0394a5e274780deaa0e07ac9964e42891cbb7f1ef65a03bc20d0807e76355e1b |

## dev02_prune

阶段 `development`；已记录28/28场策略运行。[完整报告](route_round2/dev02_prune/report.json) · [冻结清单](route_round2/dev02_prune/manifest.json) · [原始动作](route_round2/dev02_prune/runs/)

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 14/14 | 14/14 | 14/14 | 14/14 | 507.21 | 6434.67 | 24037.65 | 258.43 | 4.43 | 662.39 | 7654.46 | 0.00% |
| RouteAwareP4 | 14/14 | 14/14 | 14/14 | 14/14 | 497.51 | 6280.36 | 23272.16 | 260.86 | 5.43 | 699.84 | 7479.27 | 6.45% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 646.59 | 528.82 | 576.84 | 512.19 | 487.65 | 421.89 | 376.49 |
| RouteAwareP4 | 679.12 | 547.51 | 526.00 | 491.77 | 480.52 | 406.08 | 351.58 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 4807.53 | 256.71 | 1292.14 | 78.29 |
| RouteAwareP4 | 4654.43 | 240.36 | 1304.29 | 81.29 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3002.96 | 256.21 | 1286.79 | 0.00 | 4545.96 |
| HuntP4 | early_clear | 1003.15 | 0.00 | 0.00 | 63.71 | 1066.87 |
| HuntP4 | localization | 801.42 | 0.50 | 5.36 | 14.57 | 821.85 |
| RouteAwareP4 | discovery | 3102.14 | 239.93 | 1298.57 | 0.00 | 4640.64 |
| RouteAwareP4 | joint_optical_clear | 1292.82 | 0.00 | 0.00 | 81.29 | 1374.11 |
| RouteAwareP4 | localization | 259.47 | 0.43 | 5.71 | 0.00 | 265.61 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 62 |
| HuntP4 | early_clear_success | 182 |
| HuntP4 | early_plan_started | 182 |
| HuntP4 | local_planner.speculative_first_pair | 15 |
| HuntP4 | mesh_coverage_completed | 14 |
| HuntP4 | remaining_scan_route_shortened | 12 |
| RouteAwareP4 | early_clear_miss_advance | 76 |
| RouteAwareP4 | early_clear_success | 182 |
| RouteAwareP4 | early_plan_started | 182 |
| RouteAwareP4 | joint_clear_before_scan | 161 |
| RouteAwareP4 | joint_discovery_completed | 14 |
| RouteAwareP4 | joint_route_planned | 451 |
| RouteAwareP4 | local_planner.speculative_first_pair | 16 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 2 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 961000 | 10 | [1000, 1500] | 4.38% | 276.22 | True | True |
| RouteAwareP4 | 961001 | 11 | [1000, 1500] | 6.45% | 367.37 | True | True |
| RouteAwareP4 | 961007 | 10 | [1000, 1500] | 5.65% | 374.46 | True | True |
| RouteAwareP4 | 961008 | 11 | [1000, 1500] | 0.74% | 43.77 | True | True |
| RouteAwareP4 | 961010 | 13 | [1000, 1500] | 3.02% | 192.17 | True | True |

实际加载身份：

| variant | 实际类 | 运行名 | 源码 | 该轮源码SHA256 |
| --- | --- | --- | --- | --- |
| HuntP4 | HuntP4 | HuntP4_compact21 | strategy_hunt.py | 33e3de0328b9087c33dd49f037d2c8b86be88aabc2b97e7a229564f9cfdbc25c |
| RouteAwareP4 | RouteAwareP4 | RouteAwareP4_joint21 | strategy_route.py | ebeb00f3f46e649777ef5c1346d5322bd7fe750d80c7ac056618b1626e993721 |

## dev03_reuse_stops

阶段 `development`；已记录28/28场策略运行。[完整报告](route_round2/dev03_reuse_stops/report.json) · [冻结清单](route_round2/dev03_reuse_stops/manifest.json) · [原始动作](route_round2/dev03_reuse_stops/runs/)

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 14/14 | 14/14 | 14/14 | 14/14 | 507.21 | 6434.67 | 24037.65 | 258.43 | 4.43 | 662.39 | 7654.46 | 0.00% |
| RouteAwareP4 | 14/14 | 14/14 | 14/14 | 14/14 | 510.81 | 6454.24 | 23106.53 | 295.79 | 5.50 | 696.88 | 7781.27 | 11.55% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 646.59 | 528.82 | 576.84 | 512.19 | 487.65 | 421.89 | 376.49 |
| RouteAwareP4 | 688.57 | 570.35 | 538.64 | 489.70 | 496.61 | 431.35 | 360.48 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 4807.53 | 256.71 | 1292.14 | 78.29 |
| RouteAwareP4 | 4621.31 | 272.50 | 1478.93 | 81.50 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3002.96 | 256.21 | 1286.79 | 0.00 | 4545.96 |
| HuntP4 | early_clear | 1003.15 | 0.00 | 0.00 | 63.71 | 1066.87 |
| HuntP4 | localization | 801.42 | 0.50 | 5.36 | 14.57 | 821.85 |
| RouteAwareP4 | discovery | 3105.09 | 272.14 | 1473.57 | 0.00 | 4850.80 |
| RouteAwareP4 | joint_optical_clear | 1284.45 | 0.00 | 0.00 | 81.50 | 1365.95 |
| RouteAwareP4 | localization | 231.77 | 0.36 | 5.36 | 0.00 | 237.48 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 62 |
| HuntP4 | early_clear_success | 182 |
| HuntP4 | early_plan_started | 182 |
| HuntP4 | local_planner.speculative_first_pair | 15 |
| HuntP4 | mesh_coverage_completed | 14 |
| HuntP4 | remaining_scan_route_shortened | 12 |
| RouteAwareP4 | bounded_additional_scan_at_clear_stop | 43 |
| RouteAwareP4 | early_clear_miss_advance | 77 |
| RouteAwareP4 | early_clear_success | 182 |
| RouteAwareP4 | early_plan_started | 182 |
| RouteAwareP4 | joint_clear_before_scan | 162 |
| RouteAwareP4 | joint_discovery_completed | 14 |
| RouteAwareP4 | joint_route_planned | 452 |
| RouteAwareP4 | local_planner.speculative_first_pair | 15 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 2 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 961000 | 10 | [1000, 1500] | 7.84% | 494.72 | True | True |
| RouteAwareP4 | 961001 | 11 | [1000, 1500] | 11.55% | 658.07 | True | True |
| RouteAwareP4 | 961004 | 14 | [1000, 1500] | 2.07% | 123.96 | True | True |
| RouteAwareP4 | 961005 | 15 | [1000, 1500] | 7.81% | 506.52 | True | True |
| RouteAwareP4 | 961007 | 10 | [1000, 1500] | 5.21% | 344.89 | True | True |
| RouteAwareP4 | 961008 | 11 | [1000, 1500] | 4.30% | 255.53 | True | True |
| RouteAwareP4 | 961010 | 13 | [1000, 1500] | 6.53% | 415.86 | True | True |
| RouteAwareP4 | 961011 | 14 | [1000, 1500] | 1.66% | 126.81 | True | True |

实际加载身份：

| variant | 实际类 | 运行名 | 源码 | 该轮源码SHA256 |
| --- | --- | --- | --- | --- |
| HuntP4 | HuntP4 | HuntP4_compact21 | strategy_hunt.py | 33e3de0328b9087c33dd49f037d2c8b86be88aabc2b97e7a229564f9cfdbc25c |
| RouteAwareP4 | RouteAwareP4 | RouteAwareP4_joint21 | strategy_route.py | 944b4b120d4530f27bb4724215d5d491a0ebba2cbf697946cbfe5ea121fea25c |

## dev04_transit_probe

阶段 `development`；已记录42/42场策略运行。[完整报告](route_round2/dev04_transit_probe/report.json) · [冻结清单](route_round2/dev04_transit_probe/manifest.json) · [原始动作](route_round2/dev04_transit_probe/runs/)

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 14/14 | 14/14 | 14/14 | 14/14 | 507.21 | 6434.67 | 24037.65 | 258.43 | 4.43 | 662.39 | 7654.46 | 0.00% |
| RouteAwareP4 | 14/14 | 14/14 | 14/14 | 14/14 | 497.51 | 6280.36 | 23272.16 | 260.86 | 5.43 | 699.84 | 7479.27 | 6.45% |
| RouteProbeP4 | 14/14 | 14/14 | 14/14 | 14/14 | 494.23 | 6245.01 | 22994.68 | 262.86 | 5.50 | 706.75 | 7308.86 | 6.70% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 646.59 | 528.82 | 576.84 | 512.19 | 487.65 | 421.89 | 376.49 |
| RouteAwareP4 | 679.12 | 547.51 | 526.00 | 491.77 | 480.52 | 406.08 | 351.58 |
| RouteProbeP4 | 673.46 | 535.56 | 518.51 | 495.86 | 475.45 | 407.69 | 353.09 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 4807.53 | 256.71 | 1292.14 | 78.29 |
| RouteAwareP4 | 4654.43 | 240.36 | 1304.29 | 81.29 |
| RouteProbeP4 | 4598.94 | 250.29 | 1314.29 | 81.50 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3002.96 | 256.21 | 1286.79 | 0.00 | 4545.96 |
| HuntP4 | early_clear | 1003.15 | 0.00 | 0.00 | 63.71 | 1066.87 |
| HuntP4 | localization | 801.42 | 0.50 | 5.36 | 14.57 | 821.85 |
| RouteAwareP4 | discovery | 3102.14 | 239.93 | 1298.57 | 0.00 | 4640.64 |
| RouteAwareP4 | joint_optical_clear | 1292.82 | 0.00 | 0.00 | 81.29 | 1374.11 |
| RouteAwareP4 | localization | 259.47 | 0.43 | 5.71 | 0.00 | 265.61 |
| RouteProbeP4 | discovery | 2180.40 | 241.64 | 1268.93 | 0.00 | 3690.97 |
| RouteProbeP4 | joint_optical_clear | 1314.47 | 0.00 | 0.00 | 81.50 | 1395.97 |
| RouteProbeP4 | localization | 203.03 | 0.36 | 3.93 | 0.00 | 207.32 |
| RouteProbeP4 | route_probe | 901.03 | 8.29 | 41.43 | 0.00 | 950.75 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 62 |
| HuntP4 | early_clear_success | 182 |
| HuntP4 | early_plan_started | 182 |
| HuntP4 | local_planner.speculative_first_pair | 15 |
| HuntP4 | mesh_coverage_completed | 14 |
| HuntP4 | remaining_scan_route_shortened | 12 |
| RouteAwareP4 | early_clear_miss_advance | 76 |
| RouteAwareP4 | early_clear_success | 182 |
| RouteAwareP4 | early_plan_started | 182 |
| RouteAwareP4 | joint_clear_before_scan | 161 |
| RouteAwareP4 | joint_discovery_completed | 14 |
| RouteAwareP4 | joint_route_planned | 451 |
| RouteAwareP4 | local_planner.speculative_first_pair | 16 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 2 |
| RouteProbeP4 | early_clear_miss_advance | 77 |
| RouteProbeP4 | early_clear_success | 182 |
| RouteProbeP4 | early_plan_started | 182 |
| RouteProbeP4 | joint_clear_before_scan | 162 |
| RouteProbeP4 | joint_discovery_completed | 14 |
| RouteProbeP4 | joint_route_planned | 452 |
| RouteProbeP4 | local_planner.speculative_first_pair | 11 |
| RouteProbeP4 | route_probe.held_scan_resumed | 116 |
| RouteProbeP4 | route_probe.probe_direction | 72 |
| RouteProbeP4 | route_probe.probe_no_signal | 44 |
| RouteProbeP4 | route_probe.zero_detour_probe_issued | 116 |
| RouteProbeP4 | route_probe_held_scan_resumed | 116 |
| RouteProbeP4 | route_probe_probe_direction | 72 |
| RouteProbeP4 | route_probe_probe_no_signal | 44 |
| RouteProbeP4 | route_probe_zero_detour_probe_issued | 116 |
| RouteProbeP4 | sixteen_sources_retire_remaining_stations | 2 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 961000 | 10 | [1000, 1500] | 4.38% | 276.22 | True | True |
| RouteAwareP4 | 961001 | 11 | [1000, 1500] | 6.45% | 367.37 | True | True |
| RouteAwareP4 | 961007 | 10 | [1000, 1500] | 5.65% | 374.46 | True | True |
| RouteAwareP4 | 961008 | 11 | [1000, 1500] | 0.74% | 43.77 | True | True |
| RouteAwareP4 | 961010 | 13 | [1000, 1500] | 3.02% | 192.17 | True | True |
| RouteProbeP4 | 961000 | 10 | [1000, 1500] | 1.49% | 93.86 | True | True |
| RouteProbeP4 | 961001 | 11 | [1000, 1500] | 4.34% | 247.37 | True | True |
| RouteProbeP4 | 961004 | 14 | [1000, 1500] | 0.07% | 4.12 | True | True |
| RouteProbeP4 | 961005 | 15 | [1000, 1500] | 0.26% | 16.82 | True | True |
| RouteProbeP4 | 961007 | 10 | [1000, 1500] | 6.70% | 443.55 | True | True |
| RouteProbeP4 | 961010 | 13 | [1000, 1500] | 4.33% | 275.70 | True | True |

实际加载身份：

| variant | 实际类 | 运行名 | 源码 | 该轮源码SHA256 |
| --- | --- | --- | --- | --- |
| HuntP4 | HuntP4 | HuntP4_compact21 | strategy_hunt.py | 33e3de0328b9087c33dd49f037d2c8b86be88aabc2b97e7a229564f9cfdbc25c |
| RouteAwareP4 | RouteAwareP4 | RouteAwareP4_joint21 | strategy_route.py | bb30e9d446b886670277036d5485729ff8d4263c3c2457e016c8b51c06639608 |
| RouteProbeP4 | RouteProbeP4 | RouteProbeP4_zero_detour | strategy_route_probe.py | 16e69149d6655d5c5e770a19547ec5688d7366e571ef2e9c03424fda613f468f |

## confirmation01

阶段 `confirmation`；已记录168/168场策略运行。[完整报告](route_round2/confirmation01/report.json) · [冻结清单](route_round2/confirmation01/manifest.json) · [原始动作](route_round2/confirmation01/runs/)

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 56/56 | 56/56 | 56/56 | 56/56 | 512.25 | 6505.84 | 24560.63 | 252.70 | 4.88 | 676.85 | 7317.25 | 0.00% |
| RouteAwareP4 | 56/56 | 56/56 | 56/56 | 56/56 | 499.32 | 6341.78 | 23615.94 | 259.88 | 5.02 | 653.94 | 7358.20 | 17.69% |
| RouteProbeP4 | 56/56 | 56/56 | 56/56 | 56/56 | 498.60 | 6325.94 | 23438.01 | 261.82 | 5.18 | 648.87 | 7418.86 | 18.26% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 637.66 | 585.01 | 558.46 | 502.21 | 452.23 | 435.24 | 414.95 |
| RouteAwareP4 | 634.18 | 562.08 | 541.58 | 476.91 | 445.65 | 427.35 | 407.48 |
| RouteProbeP4 | 634.26 | 560.65 | 544.07 | 480.38 | 452.39 | 430.20 | 388.23 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 4912.13 | 250.61 | 1263.48 | 79.62 |
| RouteAwareP4 | 4723.19 | 239.16 | 1299.38 | 80.05 |
| RouteProbeP4 | 4687.60 | 248.70 | 1309.11 | 80.54 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3080.57 | 250.36 | 1258.39 | 0.00 | 4589.32 |
| HuntP4 | early_clear | 970.04 | 0.00 | 0.00 | 63.91 | 1033.95 |
| HuntP4 | localization | 861.52 | 0.25 | 5.09 | 15.71 | 882.57 |
| RouteAwareP4 | discovery | 3159.04 | 238.88 | 1294.29 | 0.00 | 4692.20 |
| RouteAwareP4 | joint_optical_clear | 1371.57 | 0.00 | 0.00 | 80.05 | 1451.62 |
| RouteAwareP4 | localization | 192.58 | 0.29 | 5.09 | 0.00 | 197.96 |
| RouteProbeP4 | discovery | 2252.82 | 240.45 | 1264.91 | 0.00 | 3758.18 |
| RouteProbeP4 | joint_optical_clear | 1398.44 | 0.00 | 0.00 | 80.54 | 1478.97 |
| RouteProbeP4 | localization | 153.28 | 0.23 | 4.11 | 0.00 | 157.61 |
| RouteProbeP4 | route_probe | 883.07 | 8.02 | 40.09 | 0.00 | 931.18 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 273 |
| HuntP4 | early_clear_success | 728 |
| HuntP4 | early_plan_started | 728 |
| HuntP4 | local_planner.speculative_first_pair | 57 |
| HuntP4 | mesh_coverage_completed | 56 |
| HuntP4 | remaining_scan_route_shortened | 28 |
| RouteAwareP4 | early_clear_miss_advance | 281 |
| RouteAwareP4 | early_clear_success | 728 |
| RouteAwareP4 | early_plan_started | 728 |
| RouteAwareP4 | joint_clear_before_scan | 664 |
| RouteAwareP4 | joint_discovery_completed | 56 |
| RouteAwareP4 | joint_route_planned | 1836 |
| RouteAwareP4 | local_planner.speculative_first_pair | 57 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 3 |
| RouteProbeP4 | early_clear_miss_advance | 290 |
| RouteProbeP4 | early_clear_success | 728 |
| RouteProbeP4 | early_plan_started | 728 |
| RouteProbeP4 | joint_clear_before_scan | 660 |
| RouteProbeP4 | joint_discovery_completed | 56 |
| RouteProbeP4 | joint_route_planned | 1824 |
| RouteProbeP4 | local_planner.speculative_first_pair | 46 |
| RouteProbeP4 | route_probe.held_scan_resumed | 449 |
| RouteProbeP4 | route_probe.probe_direction | 266 |
| RouteProbeP4 | route_probe.probe_no_signal | 183 |
| RouteProbeP4 | route_probe.zero_detour_probe_issued | 449 |
| RouteProbeP4 | route_probe_held_scan_resumed | 449 |
| RouteProbeP4 | route_probe_probe_direction | 266 |
| RouteProbeP4 | route_probe_probe_no_signal | 183 |
| RouteProbeP4 | route_probe_zero_detour_probe_issued | 449 |
| RouteProbeP4 | sixteen_sources_retire_remaining_stations | 5 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 962004 | 10 | [1000, 1500] | 8.03% | 480.70 | True | True |
| RouteAwareP4 | 962007 | 10 | [1000, 1500] | 3.04% | 192.75 | True | True |
| RouteAwareP4 | 962009 | 11 | [1000, 1500] | 0.89% | 50.89 | True | True |
| RouteAwareP4 | 962011 | 11 | [1000, 1500] | 3.33% | 193.53 | True | True |
| RouteAwareP4 | 962018 | 12 | [1000, 1500] | 0.91% | 61.46 | True | True |
| RouteAwareP4 | 962020 | 12 | [1000, 1500] | 4.00% | 266.30 | True | True |
| RouteAwareP4 | 962028 | 13 | [1000, 1500] | 0.03% | 1.93 | True | True |
| RouteAwareP4 | 962032 | 14 | [1000, 1500] | 9.72% | 539.53 | True | True |
| RouteAwareP4 | 962039 | 14 | [1000, 1500] | 3.07% | 205.83 | True | True |
| RouteAwareP4 | 962041 | 15 | [1000, 1500] | 1.90% | 121.70 | True | True |
| RouteAwareP4 | 962043 | 15 | [1000, 1500] | 11.78% | 645.90 | True | True |
| RouteAwareP4 | 962045 | 15 | [1000, 1500] | 5.00% | 344.85 | True | True |
| RouteAwareP4 | 962047 | 15 | [1000, 1500] | 5.02% | 362.88 | True | True |
| RouteAwareP4 | 962052 | 16 | [1000, 1500] | 0.56% | 40.95 | True | True |
| RouteAwareP4 | 962053 | 16 | [1000, 1500] | 17.69% | 983.28 | True | True |
| RouteAwareP4 | 962054 | 16 | [1000, 1500] | 2.96% | 203.86 | True | True |
| RouteProbeP4 | 962004 | 10 | [1000, 1500] | 8.34% | 499.33 | True | True |
| RouteProbeP4 | 962006 | 10 | [1000, 1500] | 0.48% | 35.80 | True | True |
| RouteProbeP4 | 962007 | 10 | [1000, 1500] | 1.34% | 85.14 | True | True |
| RouteProbeP4 | 962009 | 11 | [1000, 1500] | 1.18% | 67.70 | True | True |
| RouteProbeP4 | 962018 | 12 | [1000, 1500] | 1.33% | 90.27 | True | True |
| RouteProbeP4 | 962020 | 12 | [1000, 1500] | 4.85% | 323.17 | True | True |
| RouteProbeP4 | 962021 | 12 | [1000, 1500] | 0.01% | 0.51 | True | True |
| RouteProbeP4 | 962025 | 13 | [1000, 1500] | 0.09% | 5.04 | True | True |
| RouteProbeP4 | 962028 | 13 | [1000, 1500] | 0.66% | 47.39 | True | True |
| RouteProbeP4 | 962032 | 14 | [1000, 1500] | 10.31% | 572.52 | True | True |
| RouteProbeP4 | 962034 | 14 | [1000, 1500] | 0.41% | 24.83 | True | True |
| RouteProbeP4 | 962035 | 14 | [1000, 1500] | 0.15% | 8.43 | True | True |
| RouteProbeP4 | 962038 | 14 | [1000, 1500] | 0.37% | 25.35 | True | True |
| RouteProbeP4 | 962039 | 14 | [1000, 1500] | 10.80% | 723.93 | True | True |
| RouteProbeP4 | 962041 | 15 | [1000, 1500] | 1.84% | 117.90 | True | True |
| RouteProbeP4 | 962043 | 15 | [1000, 1500] | 11.59% | 635.62 | True | True |
| RouteProbeP4 | 962045 | 15 | [1000, 1500] | 5.65% | 389.60 | True | True |
| RouteProbeP4 | 962047 | 15 | [1000, 1500] | 6.02% | 435.20 | True | True |
| RouteProbeP4 | 962053 | 16 | [1000, 1500] | 18.26% | 1014.76 | True | True |

实际加载身份：

| variant | 实际类 | 运行名 | 源码 | 该轮源码SHA256 |
| --- | --- | --- | --- | --- |
| HuntP4 | HuntP4 | HuntP4_compact21 | strategy_hunt.py | 33e3de0328b9087c33dd49f037d2c8b86be88aabc2b97e7a229564f9cfdbc25c |
| RouteAwareP4 | RouteAwareP4 | RouteAwareP4_joint21 | strategy_route.py | bb30e9d446b886670277036d5485729ff8d4263c3c2457e016c8b51c06639608 |
| RouteProbeP4 | RouteProbeP4 | RouteProbeP4_zero_detour | strategy_route_probe.py | 16e69149d6655d5c5e770a19547ec5688d7366e571ef2e9c03424fda613f468f |

## boundary01

阶段 `boundary`；已记录336/336场策略运行。[完整报告](route_round2/boundary01/report.json) · [冻结清单](route_round2/boundary01/manifest.json) · [原始动作](route_round2/boundary01/runs/)

| 策略 | 全清 | 正常停止 | 验收 | 成本样本 | 均值T/N | 均值T | 移动米 | 检测 | 失败清除 | P95 T/N | P95 T | 最差配对退步 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 112/112 | 112/112 | 112/112 | 112/112 | 528.49 | 6705.64 | 25185.97 | 265.21 | 4.97 | 710.75 | 7884.76 | 0.00% |
| RouteAwareP4 | 112/112 | 112/112 | 112/112 | 112/112 | 513.53 | 6518.69 | 24234.62 | 269.12 | 4.52 | 691.73 | 8170.69 | 10.05% |
| RouteProbeP4 | 112/112 | 112/112 | 112/112 | 112/112 | 512.94 | 6512.25 | 24131.73 | 270.03 | 4.70 | 695.32 | 8214.66 | 11.14% |

逐N平均T/N（秒/源）：

| 策略 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | 671.59 | 612.22 | 551.70 | 514.10 | 477.74 | 456.01 | 416.07 |
| RouteAwareP4 | 642.14 | 595.42 | 539.88 | 497.47 | 479.20 | 443.77 | 396.80 |
| RouteProbeP4 | 644.09 | 589.59 | 538.71 | 496.11 | 482.25 | 442.88 | 396.92 |

四项成本均值（秒/场）：

| 策略 | 移动 | 换频道 | 检测 | 清除（含成功与失败） |
| --- | --- | --- | --- | --- |
| HuntP4 | 5037.19 | 262.46 | 1326.07 | 79.92 |
| RouteAwareP4 | 4846.92 | 247.63 | 1345.58 | 78.55 |
| RouteProbeP4 | 4826.35 | 256.68 | 1350.13 | 79.09 |

阶段成本均值（秒/场；未触发阶段对该场计0）：

| 策略 | 阶段 | 移动 | 换频道 | 检测 | 清除 | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| HuntP4 | discovery | 3085.08 | 261.56 | 1313.35 | 0.00 | 4659.99 |
| HuntP4 | early_clear | 860.18 | 0.00 | 0.00 | 60.13 | 920.31 |
| HuntP4 | localization | 1091.93 | 0.89 | 12.72 | 19.79 | 1125.33 |
| RouteAwareP4 | discovery | 3168.17 | 246.74 | 1333.17 | 0.00 | 4748.08 |
| RouteAwareP4 | joint_optical_clear | 1292.72 | 0.00 | 0.00 | 78.55 | 1371.27 |
| RouteAwareP4 | localization | 386.04 | 0.89 | 12.41 | 0.00 | 399.34 |
| RouteProbeP4 | discovery | 2241.30 | 247.61 | 1298.35 | 0.00 | 3787.26 |
| RouteProbeP4 | joint_optical_clear | 1331.83 | 0.00 | 0.00 | 79.09 | 1410.92 |
| RouteProbeP4 | localization | 322.82 | 0.69 | 9.87 | 0.00 | 333.37 |
| RouteProbeP4 | route_probe | 930.40 | 8.38 | 41.92 | 0.00 | 980.70 |

实际触发次数（该集合累计；嵌套规划器保留独立前缀）：

| 策略 | 触发项 | 次数 |
| --- | --- | --- |
| HuntP4 | early_clear_miss_advance | 557 |
| HuntP4 | early_clear_success | 1456 |
| HuntP4 | early_plan_started | 1456 |
| HuntP4 | local_planner.safe_convex_probe | 1 |
| HuntP4 | local_planner.speculative_first_pair | 284 |
| HuntP4 | mesh_coverage_completed | 112 |
| HuntP4 | remaining_scan_route_shortened | 49 |
| RouteAwareP4 | early_clear_miss_advance | 506 |
| RouteAwareP4 | early_clear_success | 1456 |
| RouteAwareP4 | early_plan_started | 1456 |
| RouteAwareP4 | joint_clear_before_scan | 1281 |
| RouteAwareP4 | joint_discovery_completed | 112 |
| RouteAwareP4 | joint_route_planned | 3611 |
| RouteAwareP4 | local_planner.safe_convex_probe | 1 |
| RouteAwareP4 | local_planner.speculative_first_pair | 277 |
| RouteAwareP4 | sixteen_sources_retire_remaining_stations | 7 |
| RouteProbeP4 | early_clear_miss_advance | 526 |
| RouteProbeP4 | early_clear_success | 1456 |
| RouteProbeP4 | early_plan_started | 1456 |
| RouteProbeP4 | joint_clear_before_scan | 1295 |
| RouteProbeP4 | joint_discovery_completed | 112 |
| RouteProbeP4 | joint_route_planned | 3625 |
| RouteProbeP4 | local_planner.safe_convex_probe | 1 |
| RouteProbeP4 | local_planner.speculative_first_pair | 220 |
| RouteProbeP4 | route_probe.held_scan_resumed | 939 |
| RouteProbeP4 | route_probe.probe_direction | 543 |
| RouteProbeP4 | route_probe.probe_no_signal | 396 |
| RouteProbeP4 | route_probe.zero_detour_probe_issued | 939 |
| RouteProbeP4 | route_probe_held_scan_resumed | 939 |
| RouteProbeP4 | route_probe_probe_direction | 543 |
| RouteProbeP4 | route_probe_probe_no_signal | 396 |
| RouteProbeP4 | route_probe_zero_detour_probe_issued | 939 |
| RouteProbeP4 | sixteen_sources_retire_remaining_stations | 7 |

验收失败（全部保留）：

本集合无验收失败。

相对HuntP4的全部耗时退步场景：

| 策略 | seed | N | 半径 | 退步 | 增加秒 | 候选验收 | Hunt验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RouteAwareP4 | 963004 | 10 | [1000, 1000] | 0.51% | 36.94 | True | True |
| RouteAwareP4 | 963005 | 10 | [1000, 1000] | 2.88% | 193.87 | True | True |
| RouteAwareP4 | 963010 | 11 | [1000, 1000] | 5.76% | 419.17 | True | True |
| RouteAwareP4 | 963011 | 11 | [1000, 1000] | 5.11% | 359.68 | True | True |
| RouteAwareP4 | 963012 | 11 | [1000, 1000] | 2.53% | 197.86 | True | True |
| RouteAwareP4 | 963013 | 11 | [1000, 1000] | 4.62% | 309.15 | True | True |
| RouteAwareP4 | 963014 | 11 | [1000, 1000] | 3.21% | 231.29 | True | True |
| RouteAwareP4 | 963016 | 12 | [1000, 1000] | 7.15% | 449.39 | True | True |
| RouteAwareP4 | 963019 | 12 | [1000, 1000] | 0.43% | 29.45 | True | True |
| RouteAwareP4 | 963020 | 12 | [1000, 1000] | 4.05% | 314.04 | True | True |
| RouteAwareP4 | 963022 | 12 | [1000, 1000] | 10.05% | 680.08 | True | True |
| RouteAwareP4 | 963023 | 12 | [1000, 1000] | 0.68% | 55.69 | True | True |
| RouteAwareP4 | 963028 | 13 | [1000, 1000] | 0.60% | 46.28 | True | True |
| RouteAwareP4 | 963029 | 13 | [1000, 1000] | 0.19% | 12.73 | True | True |
| RouteAwareP4 | 963030 | 13 | [1000, 1000] | 9.39% | 752.39 | True | True |
| RouteAwareP4 | 963034 | 14 | [1000, 1000] | 3.52% | 251.60 | True | True |
| RouteAwareP4 | 963035 | 14 | [1000, 1000] | 4.11% | 259.99 | True | True |
| RouteAwareP4 | 963036 | 14 | [1000, 1000] | 9.12% | 682.59 | True | True |
| RouteAwareP4 | 963037 | 14 | [1000, 1000] | 0.03% | 2.08 | True | True |
| RouteAwareP4 | 963038 | 14 | [1000, 1000] | 9.94% | 764.07 | True | True |
| RouteAwareP4 | 963039 | 14 | [1000, 1000] | 3.77% | 279.23 | True | True |
| RouteAwareP4 | 963041 | 15 | [1000, 1000] | 7.53% | 462.19 | True | True |
| RouteAwareP4 | 963042 | 15 | [1000, 1000] | 1.62% | 105.95 | True | True |
| RouteAwareP4 | 963043 | 15 | [1000, 1000] | 1.85% | 128.56 | True | True |
| RouteAwareP4 | 963044 | 15 | [1000, 1000] | 8.17% | 581.80 | True | True |
| RouteAwareP4 | 963046 | 15 | [1000, 1000] | 0.67% | 58.91 | True | True |
| RouteAwareP4 | 963053 | 16 | [1000, 1000] | 5.64% | 396.93 | True | True |
| RouteAwareP4 | 963054 | 16 | [1000, 1000] | 3.22% | 284.83 | True | True |
| RouteAwareP4 | 963055 | 16 | [1000, 1000] | 1.57% | 126.15 | True | True |
| RouteAwareP4 | 963113 | 11 | [1500, 1500] | 6.02% | 372.16 | True | True |
| RouteAwareP4 | 963121 | 12 | [1500, 1500] | 2.27% | 140.77 | True | True |
| RouteAwareP4 | 963124 | 13 | [1500, 1500] | 6.99% | 395.83 | True | True |
| RouteAwareP4 | 963138 | 14 | [1500, 1500] | 4.08% | 289.96 | True | True |
| RouteAwareP4 | 963139 | 14 | [1500, 1500] | 1.37% | 95.86 | True | True |
| RouteAwareP4 | 963146 | 15 | [1500, 1500] | 5.39% | 349.51 | True | True |
| RouteProbeP4 | 963004 | 10 | [1000, 1000] | 1.12% | 81.74 | True | True |
| RouteProbeP4 | 963005 | 10 | [1000, 1000] | 3.42% | 229.83 | True | True |
| RouteProbeP4 | 963010 | 11 | [1000, 1000] | 6.26% | 454.92 | True | True |
| RouteProbeP4 | 963011 | 11 | [1000, 1000] | 1.28% | 89.76 | True | True |
| RouteProbeP4 | 963013 | 11 | [1000, 1000] | 5.36% | 358.97 | True | True |
| RouteProbeP4 | 963014 | 11 | [1000, 1000] | 1.79% | 129.11 | True | True |
| RouteProbeP4 | 963016 | 12 | [1000, 1000] | 1.53% | 96.26 | True | True |
| RouteProbeP4 | 963020 | 12 | [1000, 1000] | 5.30% | 411.04 | True | True |
| RouteProbeP4 | 963022 | 12 | [1000, 1000] | 11.14% | 753.98 | True | True |
| RouteProbeP4 | 963028 | 13 | [1000, 1000] | 1.41% | 107.97 | True | True |
| RouteProbeP4 | 963029 | 13 | [1000, 1000] | 0.89% | 59.03 | True | True |
| RouteProbeP4 | 963030 | 13 | [1000, 1000] | 8.04% | 644.18 | True | True |
| RouteProbeP4 | 963034 | 14 | [1000, 1000] | 1.52% | 108.33 | True | True |
| RouteProbeP4 | 963035 | 14 | [1000, 1000] | 4.40% | 278.47 | True | True |
| RouteProbeP4 | 963036 | 14 | [1000, 1000] | 9.70% | 726.56 | True | True |
| RouteProbeP4 | 963037 | 14 | [1000, 1000] | 0.91% | 63.34 | True | True |
| RouteProbeP4 | 963038 | 14 | [1000, 1000] | 10.55% | 810.57 | True | True |
| RouteProbeP4 | 963039 | 14 | [1000, 1000] | 4.76% | 352.77 | True | True |
| RouteProbeP4 | 963041 | 15 | [1000, 1000] | 8.04% | 493.57 | True | True |
| RouteProbeP4 | 963042 | 15 | [1000, 1000] | 2.25% | 147.62 | True | True |
| RouteProbeP4 | 963043 | 15 | [1000, 1000] | 2.55% | 177.48 | True | True |
| RouteProbeP4 | 963044 | 15 | [1000, 1000] | 8.42% | 599.22 | True | True |
| RouteProbeP4 | 963046 | 15 | [1000, 1000] | 1.63% | 143.53 | True | True |
| RouteProbeP4 | 963053 | 16 | [1000, 1000] | 7.88% | 554.58 | True | True |
| RouteProbeP4 | 963055 | 16 | [1000, 1000] | 4.20% | 336.61 | True | True |
| RouteProbeP4 | 963113 | 11 | [1500, 1500] | 6.95% | 429.08 | True | True |
| RouteProbeP4 | 963121 | 12 | [1500, 1500] | 2.97% | 184.19 | True | True |
| RouteProbeP4 | 963124 | 13 | [1500, 1500] | 7.53% | 426.30 | True | True |
| RouteProbeP4 | 963136 | 14 | [1500, 1500] | 3.49% | 232.23 | True | True |
| RouteProbeP4 | 963138 | 14 | [1500, 1500] | 4.69% | 333.20 | True | True |
| RouteProbeP4 | 963139 | 14 | [1500, 1500] | 1.84% | 128.79 | True | True |
| RouteProbeP4 | 963146 | 15 | [1500, 1500] | 6.03% | 391.09 | True | True |

实际加载身份：

| variant | 实际类 | 运行名 | 源码 | 该轮源码SHA256 |
| --- | --- | --- | --- | --- |
| HuntP4 | HuntP4 | HuntP4_compact21 | strategy_hunt.py | 33e3de0328b9087c33dd49f037d2c8b86be88aabc2b97e7a229564f9cfdbc25c |
| RouteAwareP4 | RouteAwareP4 | RouteAwareP4_joint21 | strategy_route.py | bb30e9d446b886670277036d5485729ff8d4263c3c2457e016c8b51c06639608 |
| RouteProbeP4 | RouteProbeP4 | RouteProbeP4_zero_detour | strategy_route_probe.py | 16e69149d6655d5c5e770a19547ec5688d7366e571ef2e9c03424fda613f468f |

## integration_before_route2

该标签未完成，未进入统计和选型。原有证据保持不动。

## 单测与研究保留

整合线程提供的本轮综合验证记录：113项通过，用时17.62秒。该测试结论独立于下列离线模拟统计，报告生成没有重新运行测试。

```powershell
python -m pytest test_route.py test_route_probe.py test_route_standalone.py test_discovery_prune.py test_hunt.py test_local_hunt.py test_discovery_compact.py test_discovery_coverage.py test_discovery_mesh.py test_discovery_rings.py test_finish.py test_cost.py -q
```

`discovery_joint_prune.py` / `test_discovery_joint_prune.py` 单独9项通过，尚未接入生产策略，仅作研究保留；不把未接入helper的单测当成当前策略的收益证据。

固定几何研究的失败与未证结果全部保留，不接入无连续证明的构造：

| 证据文件 | 构造数 | 连续通过 | 严格盲区反例 | 有限预算未证 |
| --- | --- | --- | --- | --- |
| geometry_search_extra_results.json | 16 | 0 | 14 | 2 |
| discovery_design_round2_results.json | 80 | 0 | 79 | 1 |
| discovery_star_round2_results.json | 72 | 0 | 72 | 0 |

## 选型与接入记录

选择 `RouteProbeP4`，源码 `strategy_route_probe.py`，SHA256 `16e69149d6655d5c5e770a19547ec5688d7366e571ef2e9c03424fda613f468f`。

选型仅依照本轮最终168场的完整验收、可用成本及整体平均T/N；不引入事后单场门槛。若候选没有整体改善，则保留HuntP4。

| 策略 | 168场全验收 | 全部成本可用 | 最终两阶段同代码 | 当前依赖匹配 | 可选 |
| --- | --- | --- | --- | --- | --- |
| HuntP4 | True | True | True | True | True |
| RouteAwareP4 | True | True | True | True | True |
| RouteProbeP4 | True | True | True | True | True |

单独读取的 `tools/p4_practice_deployment.json` 记录 `RouteProbeP4_zero_detour` / `RouteProbeP4`，其SHA256与当前源码匹配；是否与本报告推荐一致：`True`。正式入口记录为 `FastP4`。

接入记录是带源码哈希的元数据，本报告没有因此宣称新一局模拟器已经运行。基线和所有开发/确认/边界原始结果均保留；策略替换由独立接入步骤完成。
