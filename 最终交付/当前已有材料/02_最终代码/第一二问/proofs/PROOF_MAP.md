# 完整证明索引

证明—代码—结果对应表

| 结论 | 数学依据 | 实现及证据 |
|:---|:---|:---|
| 半平面模型与退化状态 | 命题1、式(1) | `geometry.py`；`pure_bearing_region` |
| 连续直径 | 命题2 | 全点对与旋转卡壳独立测试 |
| 直径圆覆盖 | 命题3 | `Region.metrics` 与反例数据 |
| Jung界 | 命题4 | 等边三角形及穷举支持圆测试 |
| 精确物理集合夹逼 | 式(5)—(6) | `posterior.py` |
| 完整未截断接收域 | 命题5 | `safe_centers_local`、四圆约束 |
| 原目标的全域下界 | 式(12)—(21) | `proof.py:lower_checks` |
| 精确全局上界 | 附录A | `active_checks`、`heading_certificate` |
| 全部首次观测的策略保证 | 命题6 | `policy.py` 平移、旋转与镜像 |
| 连续20%候选区 | 式(28) | `candidate_certificate` |
| 执行点数值保护 | 第5节 | `operational_certificate` |
| 图文与数据一致 | 第6节 | 单一JSON/CSV源与交付检查脚本 |

`global_certificate.json` 保留根和坐标的严格区间、所有活动分支的检查值，以及全部角度叶区间。代码不是替代未给出的证明，而是执行本文已经明确列出的有限有理数不等式检查。相反，单元测试和数值实验只说明实现通过了列明的测试，它们不承担上述定理的逻辑证明责任。测试数以本轮 `logs/pytest.xml` 为准；原包的153项之外已增加5项入口适配测试。
