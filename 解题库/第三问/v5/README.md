# 第三问 v5 · 机器狗自动定位清除策略

最新迭代为 **v8**，使用说明见 [README_v8.md](README_v8.md)，默认评估入口为 `python run_iter.py`。本页以下内容保留为 v5 历史说明。

## 文件清单

- `mock_simulator.py` — 脱机 mock 模拟器（按附件 1 物理规则自洽生成测试场景）
- `strategy.py` — 4 套策略主体（BlinkHop / StaticScan / Patrol / Hybrid）
- `robot.py` — 真模拟器 HTTP 客户端 + 通用驱动器
- `run_eval.py` — baseline 评估 driver
- `plot_results.py` — 画 4 张对比图

## 工作流

### 1. 脱机评估（不需要模拟器）

```bash
cd 解题库/第三问/v5
python run_eval.py        # 跑 30 局/策略，输出 results/summary.{json,md}
python plot_results.py    # 画 4 张图到 results/figures/
```

### 2. 接真模拟器

```bash
# 启动模拟器，登录，进入"问题 3 演练测试"
python -c "from robot import run; import json; \
  print(json.dumps(run('Hybrid', '<你的参赛队号>'), indent=2, ensure_ascii=False))"
```

## 策略要点

| 策略 | 第 1 测点 | 第 2 测点 | 适合场景 |
|---|---|---|---|
| BlinkHop | 当前位置 | 沿 direction 跳 800 m | 频道多、距离远 |
| StaticScan | (1000, 0) | 沿 direction 走 800 m | 频道分散、定位精度优先 |
| Patrol | 4 站位轮换 | 沿 direction 走 800 m | 干扰源分布广 |
| Hybrid | 早期跳、后期固定 (1000, 0) | 同上 | 综合：先广后精 |

定位子算法全部复用 Q1 v4 的 `solve_problem_1`：楔形交集 + MEC 圆。
停止判据：MEC 半径 ≤ 20 m（对应 Jung 直径 ≤ 20√3 ≈ 34.64 m）。

## 关键设计

- **per-channel 状态机**：`NEW → M1 → READY → CLEARED/SKIP`，不会死循环
- **失败计数**：同一频道 clear 失败 ≥ 3 次 → SKIP，避免无谓重试
- **混合策略阶段切换**：已清除 < 5 用闪烁跳跃，≥ 5 切到 StaticScan 精定位
- **robot.py 状态同步**：每次动作前更新 `state.pos` 和 `state.ch`，让策略看到真实当前位置

## 待优化

- 第 3+ 个 bearing 的位置选择可以更智能（用不确定性最大的方向）
- Hybrid 切换阈值 5/10 是经验值，可以从脱机评估结果调
- 真模拟器上要观察：1) 重复 clear 的"幂等性"会浪费 3s 失败耗时；
  2) 测向误差累积下，MEC 半径经常 > 20m，需要重定位机制
