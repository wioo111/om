# -*- coding: utf-8 -*-
"""共用驱动：本地模拟与官方 HTTP 响应采用同一条状态更新路径。"""

import math
import inspect
import time
from strategy import State


def response_dict(response):
    if isinstance(response, dict):
        return response
    return {**vars(response), **getattr(response, 'extra', {})}


def accepted_response(response):
    data = response_dict(response)
    if data.get('accepted') is not True:
        raise RuntimeError(f'动作未被接受，未更新状态: {data}')
    value = data.get('virtual_time_s')
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RuntimeError('响应中缺少有效的 virtual_time_s')
    return data


def run_with_sim_strategy(strategy, sim, max_steps=8000):
    print(f"[P4 strategy] class={type(strategy).__name__} name={strategy.name} source={inspect.getfile(type(strategy))}", flush=True)
    state = State(pos=(0.0, 0.0), ch=1)
    started = time.monotonic()
    entered = accepted_response(sim.enter())
    remaining_real = entered.get('remaining_real_duration_s', 1200.0)
    maximum_virtual = entered.get('max_virtual_duration_s', 360000.0)
    deadline = started + max(0.0, remaining_real - min(2.0, remaining_real / 10))
    if hasattr(sim, 'set_deadline'):
        sim.set_deadline(deadline)
    state.virtual_time = entered['virtual_time_s']
    log = []
    totals = dict(move_time_s=0.0, switch_time_s=0.0,
                  measure_time_s=0.0, clear_time_s=0.0)
    stop_reason = 'step_limit'

    for _ in range(max_steps):
        if time.monotonic() >= deadline:
            stop_reason = 'real_deadline'
            break
        action = strategy.step(state)
        if action is None or action.kind == 'done':
            stop_reason = getattr(strategy, 'completion_reason', None) or 'strategy_done'
            break
        if action.kind not in ('measure', 'clear'):
            raise ValueError(f'未知动作: {action.kind}')
        if (len(action.pos) != 2 or not all(math.isfinite(v) and abs(v) <= 2000000
                                          for v in action.pos)
                or not isinstance(action.ch, int) or not 1 <= action.ch <= 20):
            raise ValueError(f'动作参数非法: {action}')
        movement = math.dist(state.pos, action.pos) / 5
        switching = float(action.kind == 'measure' and action.ch != state.ch)
        if state.virtual_time + movement + switching + 5 > maximum_virtual:
            stop_reason = 'virtual_deadline'
            break
        if time.monotonic() >= deadline:
            stop_reason = 'real_deadline'
            break
        previous_time = state.virtual_time
        response = accepted_response(getattr(sim, action.kind)(*action.pos, action.ch))
        if response['virtual_time_s'] + 1e-8 < previous_time:
            raise RuntimeError('接受的响应出现虚拟时间倒退')
        state.pos = action.pos
        state.virtual_time = response['virtual_time_s']
        if action.kind == 'measure':
            result = response.get('measure_result')
            if result not in ('near', 'direction', 'no_signal'):
                raise RuntimeError(f'非法检测结果: {result}')
            state.ch = action.ch
            strategy.on_measure(state, action.ch, result, response.get('svd_deg'))
            totals['measure_time_s'] += 5
        else:
            result = response.get('clear_result')
            if result not in ('success', 'no_target_in_range'):
                raise RuntimeError(f'非法清除结果: {result}')
            # /clear 仅指定目标，不改变测向机当前频道。
            strategy.on_clear(state, action.ch, result == 'success')
            totals['clear_time_s'] += 5 if result == 'success' else 3
        totals['move_time_s'] += movement
        totals['switch_time_s'] += switching
        log.append(dict(action=action.kind, ch=action.ch, pos=action.pos,
                        result=result, svd_deg=response.get('svd_deg'),
                        virtual_time_s=state.virtual_time,
                        delta_time_s=state.virtual_time - previous_time))

    # 提前预留时间主动退出；超过官方现实期限后不再向关闭接口发请求。
    if time.monotonic() < started + remaining_real:
        if hasattr(sim, 'set_deadline'):
            sim.set_deadline(started + remaining_real)
        exited = accepted_response(sim.exit())
        state.virtual_time = exited['virtual_time_s']
    result = sim.stats() if hasattr(sim, 'stats') else {}
    cleared = len(state.cleared)
    result.update(cleared=cleared, virtual_time_s=state.virtual_time,
                  avg_time_per_cleared=state.virtual_time / cleared if cleared else None,
                  measure_count=sum(row['action'] == 'measure' for row in log),
                  clear_count=sum(row['action'] == 'clear' for row in log),
                  clear_fail_count=sum(row['result'] == 'no_target_in_range' for row in log),
                  stop_reason=stop_reason,
                  coverage_complete=stop_reason in ('all_channels_cleared_or_covered',
                                                     'cleared_maximum_16'),
                  cleared_channels=sorted(state.cleared),
                  absent_channels=sorted(getattr(strategy, 'absent', [])),
                  runtime_s=time.monotonic() - started,
                  time_breakdown=totals, log=log)
    return result


run_with_sim_v2 = run_with_sim_strategy
