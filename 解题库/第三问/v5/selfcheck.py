# -*- coding: utf-8 -*-
# selfcheck.py
# 3 行自检：验证 import 路径 + mock 物理规则 + 策略主循环
# 用法：python selfcheck.py

import sys
import os

print("=" * 60)
print("第三问 v5 自检")
print("=" * 60)

# 1) 验证 problem1_v4 路径
print("\n[1/4] 验证 Q1 v4 路径解析…")
try:
    import strategy
    print(f"  ✓ Q1 v4 已加载：{strategy._FIRST_FILE}")
except Exception as e:
    print(f"  ✗ Q1 v4 加载失败：{e}")
    print("    设置环境变量 CUMCM2026_ROOT 指向 CUMCM2026Problems 根目录")
    print("    Windows: set CUMCM2026_ROOT=C:\\path\\to\\CUMCM2026Problems")
    print("    Linux:   export CUMCM2026_ROOT=/path/to/CUMCM2026Problems")
    sys.exit(1)

# 2) 验证 mock 物理规则
print("\n[2/4] 验证 mock 物理规则…")
from mock_simulator import MockSimulator, CHANNELS
sim = MockSimulator(seed=42)
print(f"  ✓ 生成了 N={sim.N} 个频道：{sorted(sim.sources.keys())[:5]}…")
sim.enter()
r1 = sim.measure(0, 0, 1)
print(f"  ✓ measure(0,0,1) @ t=0: {r1.measure_result} "
      f"virt={r1.virtual_time_s:.1f}s")
assert r1.virtual_time_s == 5.0, f"期望 5s，实测 {r1.virtual_time_s}"
r2 = sim.measure(0, 0, 2)
delta2 = r2.virtual_time_s - r1.virtual_time_s
print(f"  ✓ measure(0,0,2) 切频道: virt={r2.virtual_time_s:.1f}s，"
      f"本动作增量={delta2:.1f}s（累计应为 11.0，增量应为 6.0：1+5）")
assert abs(delta2 - 6.0) < 1e-9, f"期望本动作增量 6s，实测 {delta2}s"
r3 = sim.measure(1000, 0, 3)
delta3 = r3.virtual_time_s - r2.virtual_time_s
print(f"  ✓ measure(1000,0,3) 移动200s+切1s+检测5s: "
      f"virt={r3.virtual_time_s:.1f}s，本动作增量={delta3:.1f}s（应为 206.0）")
assert abs(delta3 - 206.0) < 1e-9, f"期望本动作增量 206s，实测 {delta3}s"
sim.exit()

# 3) 验证 4 套策略可实例化
print("\n[3/4] 验证 4 套策略…")
import strategy
for name in ['BlinkHop', 'StaticScan', 'Patrol', 'Hybrid']:
    s = strategy.make_strategy(name)
    st = strategy.State(pos=(0.0, 0.0), ch=1)
    a = s.step(st)
    assert a.kind in ('measure', 'clear', 'done'), \
        f"{name} 第一个动作类型异常：{a}"
    print(f"  ✓ {name:12s}  first action = {a}")

# 4) 端到端跑一局
print("\n[4/4] 端到端跑一局（Hybrid, seed=42）…")
from robot import run_with_sim
sim2 = MockSimulator(seed=42)
stats = run_with_sim('Hybrid', sim2, max_steps=8000)
print(f"  ✓ N={stats['N']}, cleared={stats['cleared']}, "
      f"virt={stats['virtual_time_s']:.1f}s, "
      f"m={stats['measure_count']}, c={stats['clear_count']}")
print(f"  ✓ 平均定位清除时间 = {stats['avg_time_per_cleared']:.1f}s"
      if stats['cleared'] > 0 else "  (未清除任何频道)")

print("\n" + "=" * 60)
print("全部自检通过。可以跑：")
print("  python run_eval.py        # 机器 A：基线")
print("  python sweep_hybrid.py    # 机器 B：超参扫描")
print("  python reproduce.py       # 机器 C：复现 + 极端 case")
print("=" * 60)
