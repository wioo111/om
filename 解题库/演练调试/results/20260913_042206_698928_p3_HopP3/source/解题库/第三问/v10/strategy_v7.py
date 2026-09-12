# -*- coding: utf-8 -*-
"""第三问 v7：在 v5 Hybrid 上做小步迭代。

v7 的改动保持 v5 的状态机接口不变：
  - 跳跃/补测距离改为 300 m；
  - no_signal 不再立即永久跳过，而是在后续扫描站位重测；
  - 清除失败一次后放弃该频道，避免重复浪费时间；
  - 使用明确的虚拟时间上限。
"""

import math

from strategy import (
    Action,
    CHANNELS,
    CH_CLEARED,
    CH_NEW,
    CH_READY,
    CH_SKIP,
    Hybrid,
    State,
    STATIC_POS,
    Vec,
    second_pos_from_bearing,
)


HOP_DIST_V7 = 300.0
EXTRA_DIST_V7 = 300.0
TIME_BUDGET_V7 = 1150.0


class HybridV7(Hybrid):
    """v5 Hybrid 的可运行 v7 版本。"""

    name = "HybridV7"

    def __init__(self):
        super().__init__()
        self.scan_sites = [
            (0.0, 0.0),
            (1000.0, 0.0),
            (0.0, 1000.0),
            (-1000.0, 0.0),
            (0.0, -1000.0),
        ]
        self.scan_site_idx = 0
        self.no_signal = set()

    def first_pos(self, ch: int, state: State) -> Vec:
        # 对曾经 no_signal 的频道换扫描站位重测；其余频道沿用 Hybrid 的走法。
        if ch in self.no_signal:
            return self.scan_sites[self.scan_site_idx % len(self.scan_sites)]
        return super().first_pos(ch, state)

    def second_pos(self, ch: int, state: State,
                   first_record):
        S, theta = first_record
        if self._phase == 'hop':
            return second_pos_from_bearing(S, theta, HOP_DIST_V7)
        rad = math.radians(theta)
        return (STATIC_POS[0] - HOP_DIST_V7 * math.cos(rad),
                STATIC_POS[1] - HOP_DIST_V7 * math.sin(rad))

    def _extra_pos(self, ch: int, recs):
        cx = sum(r[0][0] for r in recs) / len(recs)
        cy = sum(r[0][1] for r in recs) / len(recs)
        theta_mean = sum(r[1] for r in recs) / len(recs)
        a = math.radians(theta_mean + 90.0)
        return (cx + EXTRA_DIST_V7 * math.cos(a),
                cy + EXTRA_DIST_V7 * math.sin(a))

    def step(self, state: State) -> Action:
        if state.virtual_time >= TIME_BUDGET_V7:
            self.done = True
            return Action('done')

        old_pass = self.cursor // len(CHANNELS)
        action = super().step(state)
        new_pass = self.cursor // len(CHANNELS)
        if new_pass > old_pass:
            self.scan_site_idx = min(
                self.scan_site_idx + new_pass - old_pass,
                len(self.scan_sites) - 1,
            )
        return action

    def on_measure(self, state: State, ch: int, result: str, svd):
        if result == 'no_signal':
            # 重置当前频道的几何记录，下一轮从新的扫描站位重新开始。
            self.no_signal.add(ch)
            if self.ch_state[ch] not in (CH_CLEARED, CH_SKIP):
                self.ch_state[ch] = CH_NEW
                self.bearings[ch].clear()
            return

        if result in ('direction', 'near'):
            self.no_signal.discard(ch)
        super().on_measure(state, ch, result, svd)

    def on_clear(self, state: State, ch: int, success: bool):
        if success:
            super().on_clear(state, ch, True)
            return
        # v7：一次清除失败即跳过，避免在同一位置反复消耗时间。
        self.clear_fails[ch] += 1
        if self.clear_fails[ch] >= 1:
            self.ch_state[ch] = CH_SKIP
            state.skipped.add(ch)


def make_strategy(name: str = 'HybridV7'):
    if name in ('HybridV7', 'Hybrid', 'v7'):
        return HybridV7()
    raise ValueError(f'未知 v7 策略：{name}')

