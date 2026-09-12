# -*- coding: utf-8 -*-
# selfcheck_v6.py
# v6 自检：仿 selfcheck.py 但只验证 v6 路径
#
# 用法：python selfcheck_v6.py

import sys
import os

print("=" * 60)
print("v6 自检")
print("=" * 60)

# 1) Q1 v4 内联
print("\n[1/4] 验证 problem1_v4_inline.py…")
if not os.path.isfile(os.path.join(os.path.dirname(__file__),
                                    'problem1_v4_inline.py')):
    print("  ✗ 找不到 problem1_v4_inline.py")
    sys.exit(1)
import strategy_v6 as v6
print(f"  ✓ Q1 v4 已通过内联加载")

# 2) 4 阶段状态机可实例化
print("\n[2/4] 验证 4 阶段状态机…")
s = v6.V6Strategy()
state = v6.State(pos=(0.0, 0.0), ch=1)
print(f"  ✓ 初始 phase = {s.phase}, coarse_idx = {s.coarse_idx}")

# 跑几步看动作变化
for i in range(8):
    a = s.step(state)
    print(f"  step {i}: {a}")
    if a.kind in ('measure', 'clear'):
        state.pos = a.pos
        state.ch = a.ch
    if a.kind == 'done':
        break

# 3) 模拟一个 direction 测点，看状态机反应
print("\n[3/4] 模拟 direction 反馈…")
s2 = v6.V6Strategy()
state2 = v6.State(pos=(0.0, 0.0), ch=1)
# 第 1 步：measure(0,0, ch=5)
a = s2.step(state2)
print(f"  action 1: {a}")
state2.pos = a.pos; state2.ch = a.ch
# 模拟方向 = 45°
s2.on_measure(state2, a.ch, 'direction', 45.0)
print(f"  ✓ on_measure(direction, θ=45°)：ch_state = {s2.ch_state[a.ch]}, "
      f"bearings = {len(s2.bearings[a.ch])} 个")
print(f"  refine_queue = {s2.refine_queue}")

# 4) 端到端跑一局
print("\n[4/4] 端到端跑一局 V6 (seed=42)…")
from mock_simulator import MockSimulator
sim = MockSimulator(seed=42)
s3 = v6.V6Strategy()
state3 = v6.State(pos=(0.0, 0.0), ch=1)
sim.enter()
state3.virtual_time = 0.0
n = 0
while n < 12000:
    a = s3.step(state3)
    if a.kind == 'done':
        break
    if a.kind in ('measure', 'clear'):
        state3.pos = a.pos
        state3.ch = a.ch
    if a.kind == 'measure':
        resp = sim.measure(a.pos[0], a.pos[1], a.ch)
        s3.on_measure(state3, a.ch, resp.measure_result, resp.svd_deg)
    elif a.kind == 'clear':
        resp = sim.clear(a.pos[0], a.pos[1], a.ch)
        s3.on_clear(state3, a.ch, resp.clear_result == 'success')
    state3.virtual_time = resp.virtual_time_s
    n += 1
sim.exit()
st = sim.stats()
print(f"  ✓ N={st['N']}, cleared={st['cleared']}, "
      f"virt={st['virtual_time_s']:.1f}s, "
      f"m={st['measure_count']}, c={st['clear_count']}")

print("\n" + "=" * 60)
print("v6 自检通过。跑：python run_eval_v6.py")
print("=" * 60)