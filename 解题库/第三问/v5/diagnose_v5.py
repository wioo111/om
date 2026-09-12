# -*- coding: utf-8 -*-
# diagnose_v5.py
# v5 速度诊断：单局逐 action 分解，找出耗时大头
#
# 输出：results/diagnose_<seed>.json
#       + 控制台打印每个 action 的耗时

import json
import os
from mock_simulator import MockSimulator
from robot import run_with_sim
from strategy import make_strategy

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

SEED = 42
MAX_STEPS = 8000

print("=" * 60)
print(f"诊断 v5 Hybrid 单局耗时分解（seed={SEED}）")
print("=" * 60)

# 跑一局并收集 actions
from mock_simulator import MockSimulator

class ActionLogger:
    def __init__(self):
        self.actions = []

def run_with_log(strategy_name, sim, max_steps):
    """robot.run_with_sim 的扩展版：把每个 action 的耗时都记下来。"""
    from strategy import State
    from robot import _dispatch_action

    s = make_strategy(strategy_name)
    state = State(pos=(0.0, 0.0), ch=1)
    log = []
    prev_t = 0.0
    for step in range(max_steps):
        a = s.step(state)
        if a.kind == 'done':
            log.append({'step': step, 'kind': 'done',
                       'virt': sim.virtual_time_s,
                       'delta': 0})
            break
        # 执行 action
        prev_t = sim.virtual_time_s
        if a.kind == 'measure':
            r = sim.measure(a.pos[0], a.pos[1], a.ch)
            state.pos = a.pos
            state.ch = a.ch
            # 更新 state 的 bearing 记录
            if r.measure_result == 'direction':
                # 找这个频道的 state
                if hasattr(s, 'bearings') and a.ch in s.bearings:
                    s.bearings[a.ch].append((a.pos, r.svd_deg))
                    # 切换 ch state
                    if hasattr(s, 'ch_state'):
                        if s.ch_state[a.ch] == 'new':
                            s.ch_state[a.ch] = 'disc'
            elif r.measure_result == 'near':
                if hasattr(s, 'bearings') and a.ch in s.bearings:
                    s.bearings[a.ch].append((a.pos, 0.0))  # near 也记
                    if hasattr(s, 'ch_state') and s.ch_state[a.ch] == 'new':
                        s.ch_state[a.ch] = 'disc'
            elif r.measure_result == 'no_signal':
                if hasattr(s, 'ch_state') and s.ch_state[a.ch] == 'new':
                    s.ch_state[a.ch] = 'skip'
            log.append({'step': step, 'kind': 'measure',
                       'ch': a.ch, 'pos': a.pos,
                       'result': r.measure_result,
                       'svd': getattr(r, 'svd_deg', None),
                       'virt': sim.virtual_time_s,
                       'delta': sim.virtual_time_s - prev_t})
        elif a.kind == 'clear':
            r = sim.clear(a.pos[0], a.pos[1], a.ch)
            state.pos = a.pos
            if hasattr(s, 'cleared') and r.clear_result == 'success':
                s.cleared.add(a.ch)
                if hasattr(s, 'ch_state'):
                    s.ch_state[a.ch] = 'cleared'
            log.append({'step': step, 'kind': 'clear',
                       'ch': a.ch, 'pos': a.pos,
                       'result': r.clear_result,
                       'virt': sim.virtual_time_s,
                       'delta': sim.virtual_time_s - prev_t})
        else:
            log.append({'step': step, 'kind': a.kind,
                       'virt': sim.virtual_time_s,
                       'delta': 0})
            break
    return log


# 跑 5 局
sim = MockSimulator(seed=SEED)
log = run_with_log('Hybrid', sim, MAX_STEPS)

# 统计
total_delta = sum(a['delta'] for a in log if 'delta' in a)
moves = [a for a in log if a['kind'] == 'measure' and a.get('delta', 0) > 6]
switches = [a for a in log if a['kind'] == 'measure' and 6 < a.get('delta', 0) <= 7]
stationary = [a for a in log if a['kind'] == 'measure' and a.get('delta', 0) <= 6]
clears = [a for a in log if a['kind'] == 'clear']

print(f"\n总虚拟时间：{total_delta:.1f}s")
print(f"测量次数：{len([a for a in log if a['kind']=='measure'])}")
print(f"清除次数：{len(clears)}")
print(f"\n耗时分解：")
move_time = sum(a.get('delta', 0) for a in moves)
switch_time = sum(a.get('delta', 0) for a in switches)
stationary_time = sum(a.get('delta', 0) for a in stationary)
clear_time = sum(a.get('delta', 0) for a in clears)
print(f"  移动+检测：{move_time:.1f}s ({100*move_time/total_delta:.1f}%)")
print(f"  仅切换频道：{switch_time:.1f}s ({100*switch_time/total_delta:.1f}%)")
print(f"  原位检测：{stationary_time:.1f}s ({100*stationary_time/total_delta:.1f}%)")
print(f"  清除：{clear_time:.1f}s ({100*clear_time/total_delta:.1f}%)")

# 检查每个 measure 的 channel 是不是来回切
prev_ch = None
switch_count = 0
for a in log:
    if a['kind'] == 'measure' and prev_ch is not None and a['ch'] != prev_ch:
        switch_count += 1
    if a['kind'] == 'measure':
        prev_ch = a['ch']
print(f"\n频道切换次数：{switch_count}")
print(f"频道切换占总耗时：{switch_time:.1f}s / {total_delta:.1f}s = "
      f"{100*switch_time/total_delta:.1f}%")

# 失败的 clear 占比
fail_clears = [a for a in clears if a.get('result') == 'no_target_in_range']
print(f"\n失败的 clear：{len(fail_clears)} / {len(clears)} = "
      f"{100*len(fail_clears)/max(1,len(clears)):.1f}%")
print(f"失败 clear 总耗时：{sum(a.get('delta',0) for a in fail_clears):.1f}s")

# 保存
out_file = os.path.join(OUT_DIR, f'diagnose_seed{SEED}.json')
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump({
        'seed': SEED,
        'N': sim.N,
        'cleared': len(sim.cleared),
        'total_virtual_time': total_delta,
        'n_measures': len([a for a in log if a['kind']=='measure']),
        'n_clears': len(clears),
        'n_fail_clears': len(fail_clears),
        'n_channel_switches': switch_count,
        'move_time': move_time,
        'switch_time': switch_time,
        'stationary_time': stationary_time,
        'clear_time': clear_time,
        'log': log,
    }, f, indent=2, ensure_ascii=False, default=str)
print(f"\n详细日志写入 {out_file}")