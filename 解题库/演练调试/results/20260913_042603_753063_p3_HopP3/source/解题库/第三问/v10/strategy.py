# -*- coding: utf-8 -*-
# strategy.py  (v2 重写版)
# 第三问：4 套定位清除策略（统一接口）
#
# 设计原则：
#   - 每个频道 ch 有状态：NEW / M1 / READY / CLEARED / SKIP
#   - 策略 step() 在外层 cursor 上推进，对当前 ch 调用 _next_action_for_ch(ch)
#   - 状态机不会回退：M1 → 一定要补第 2 个 bearing，然后切到 READY（再试定位）
#   - 失败的 clear 不会无限重试：超过 N 次失败 → SKIP
#
# 4 套策略的区别 = 第二个测向点的位置选取 + 清除前是否再移动补测：
#   1) StaticScan：固定在 (1000, 0)，第 2 点 = 沿 θ 走 800 m
#   2) Patrol：4 个站点轮换
#   3) BlinkHop：第 1 点随机在 (0,0) 起步，每测到 direction 沿 θ 跳 800 m
#   4) Hybrid：早期闪烁跳跃广撒网，后期 StaticScan 精定位
#
# 复用 Q1 v4 的 solve_problem_1 / localization_polygon。

import math
import os
import importlib.util as _ilu
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set

# 复用 Q1 v4 算法 —— 优先用内联版本 problem1_v4_inline.py（自包含），
# 没有内联文件时再用外部多级 fallback 找 problem1_v4.py。
# 这样 v5 文件夹可以单独复制到任何机器，不需要 Q1 v4 源码。
def _locate_problem1_v4():
    """优先内联；找不到再 fallback 找外部 problem1_v4.py。
    返回 (module, source_label)。"""
    here = os.path.dirname(os.path.abspath(__file__))
    # 1) 内联版本（v5 自带）
    inline = os.path.join(here, 'problem1_v4_inline.py')
    if os.path.isfile(inline):
        return inline, 'inline'

    # 2) 外部多级 fallback
    fname = 'problem1_v4.py'
    candidates = []
    # 2a) 与本文件相对
    candidates.append(os.path.normpath(os.path.join(
        here, '..', '..', '第一问', 'v4', fname)))
    # 2b) 从 cwd 向上找
    cwd = os.getcwd()
    cur = cwd
    for _ in range(8):
        cand = os.path.join(cur, '第一问', 'v4', fname)
        if os.path.isfile(cand):
            candidates.append(os.path.abspath(cand))
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # 2c) 环境变量
    env = os.environ.get('CUMCM2026_ROOT')
    if env:
        candidates.append(os.path.normpath(os.path.join(env, '第一问', 'v4', fname)))
    # 2d) 常见路径
    common = [
        r'C:\Users\LENOVO\Desktop\CUMCM2026Problems',
        r'D:\CUMCM2026Problems',
        r'/mnt/c/Users/LENOVO/Desktop/CUMCM2026Problems',
        os.path.expanduser('~/Desktop/CUMCM2026Problems'),
        os.path.expanduser('~/CUMCM2026Problems'),
    ]
    for c in common:
        candidates.append(os.path.join(c, '第一问', 'v4', fname))

    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c), 'external'

    raise FileNotFoundError(
        '找不到 Q1 v4 算法源。请确认 v5 文件夹里有 problem1_v4_inline.py，'
        '或设置 CUMCM2026_ROOT 指向 CUMCM2026Problems 根目录。\n'
        '尝试过的路径：\n  ' + '\n  '.join(candidates))


_FIRST_FILE, _SOURCE = _locate_problem1_v4()
_spec = _ilu.spec_from_file_location('problem1_v4', _FIRST_FILE)
p1 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(p1)
print(f'[strategy] Q1 v4 算法源 = {_SOURCE}: {os.path.basename(_FIRST_FILE)}')

Vec = Tuple[float, float]
CHANNELS = list(range(1, 21))
ARENA_R = 1800.0
EPS_DEG = 1.0
CLEAR_R = 20.0
SPEED = 5.0
HOP_DIST = 800.0           # 闪烁跳跃：沿 direction 走多远
STATIC_POS: Vec = (1000.0, 0.0)
PATROL_POS: List[Vec] = [
    (1000.0, 0.0), (0.0, 1000.0), (-1000.0, 0.0), (0.0, -1000.0)
]
MAX_CLEAR_FAILS = 3        # 同一频道清除失败 ≥ N 次 → SKIP

# 每个频道的内部状态
CH_NEW = 'new'
CH_M1 = 'm1'
CH_READY = 'ready'
CH_CLEARED = 'cleared'
CH_SKIP = 'skip'


# ============================================================
# Action
# ============================================================
@dataclass
class Action:
    kind: str            # 'measure' | 'clear' | 'done'
    pos: Vec = (0.0, 0.0)
    ch: int = 1

    def __repr__(self):
        if self.kind == 'done':
            return "Action(done)"
        return f"Action({self.kind}, pos={self.pos}, ch={self.ch})"


@dataclass
class State:
    pos: Vec
    ch: int
    cleared: Set[int] = field(default_factory=set)
    skipped: Set[int] = field(default_factory=set)
    bearing_records: Dict[int, List[Tuple[Vec, float]]] = field(default_factory=dict)
    virtual_time: float = 0.0


# ============================================================
# 工具：定位 + 清除
# ============================================================
def localize(records: List[Tuple[Vec, float]],
             eps: float = EPS_DEG) -> Optional[Tuple[Vec, float]]:
    """对一组 (S, θ) 用 Q1 算法定位，返回 MEC 圆心和半径。"""
    if len(records) < 2:
        return None
    dets = [r[0] for r in records]
    thetas = [r[1] for r in records]
    res = p1.solve_problem_1(dets, thetas, eps_deg=eps,
                             R_eff=1500.0, R_target=ARENA_R, N_disk=32)
    if res['n_vertices'] < 3 or res['D'] < 1e-3:
        return None
    return res['mec_center'], res['mec_radius']


def second_pos_from_bearing(S: Vec, theta: float, dist: float = HOP_DIST) -> Vec:
    """从 S 沿 θ 方向走 dist 米。"""
    rad = math.radians(theta)
    return (S[0] + dist * math.cos(rad),
            S[1] + dist * math.sin(rad))


# ============================================================
# 基类
# ============================================================
class BaseStrategy:
    name: str = "base"

    def __init__(self):
        self.ch_state: Dict[int, str] = {ch: CH_NEW for ch in CHANNELS}
        self.bearings: Dict[int, List[Tuple[Vec, float]]] = {ch: [] for ch in CHANNELS}
        self.clear_fails: Dict[int, int] = {ch: 0 for ch in CHANNELS}
        self.cursor = 0
        self.done = False
        self._attempts = 0  # 总步数上限

    # 子类重写：返回某个频道的第 1 / 第 2 个 measure 位置
    def first_pos(self, ch: int, state: State) -> Vec:
        return STATIC_POS

    def second_pos(self, ch: int, state: State,
                   first_record: Tuple[Vec, float]) -> Vec:
        S, theta = first_record
        return second_pos_from_bearing(S, theta, HOP_DIST)

    def next_action_for_ch(self, ch: int, state: State) -> Optional[Action]:
        """对某个频道返回下一个动作；None 表示切到下个频道。"""
        st = self.ch_state[ch]
        if st == CH_CLEARED or st == CH_SKIP:
            return None
        recs = self.bearings[ch]
        if st == CH_NEW:
            return Action('measure', self.first_pos(ch, state), ch)
        if st == CH_M1:
            assert len(recs) == 1
            return Action('measure',
                          self.second_pos(ch, state, recs[0]), ch)
        if st == CH_READY:
            # 已经有 ≥ 2 个 bearing；尝试定位清除
            loc = localize(recs)
            if loc is None:
                # 几何退化（两扇形反向等），跳过
                self.ch_state[ch] = CH_SKIP
                state.skipped.add(ch)
                return None
            c, r = loc
            if r <= CLEAR_R:
                return Action('clear', c, ch)
            # 定位还不够准，再补一个 bearing
            # 简单策略：在上次某个 bearing 附近 + 沿另一方向 600m
            extra = self._extra_pos(ch, recs)
            return Action('measure', extra, ch)
        return None

    def _extra_pos(self, ch: int, recs: List[Tuple[Vec, float]]) -> Vec:
        """第 3+ 个 bearing 的位置：取已有 bearing 中心 + 沿某方向 600m。"""
        cx = sum(r[0][0] for r in recs) / len(recs)
        cy = sum(r[0][1] for r in recs) / len(recs)
        # 沿"已收 bearing 角度差最大"的方向
        thetas = [r[1] for r in recs]
        a = math.radians(sum(thetas) / len(thetas) + 90)  # 垂直方向
        return (cx + 600 * math.cos(a), cy + 600 * math.sin(a))

    def step(self, state: State) -> Action:
        if self.done:
            return Action('done')
        self._attempts += 1
        if self._attempts > 8000:
            self.done = True
            return Action('done')

        # 扫一圈找下一个需要处理的频道
        for _ in range(len(CHANNELS)):
            ch = CHANNELS[self.cursor % len(CHANNELS)]
            self.cursor += 1
            if ch in state.cleared or ch in state.skipped:
                continue
            a = self.next_action_for_ch(ch, state)
            if a is not None:
                return a
        # 全部清完或无新动作
        self.done = True
        return Action('done')

    # --------- 事件回调 ---------
    def on_measure(self, state: State, ch: int, result: str,
                   svd: Optional[float]):
        if result == 'direction' and svd is not None:
            recs = self.bearings[ch]
            # 避免重复（同一 pos 的 bearing 只记一次）
            pos = state.pos
            if not any((abs(S[0] - pos[0]) < 1e-3 and
                        abs(S[1] - pos[1]) < 1e-3) for S, _ in recs):
                recs.append((pos, svd))
            # 更新状态
            if self.ch_state[ch] == CH_NEW:
                self.ch_state[ch] = CH_M1
            elif self.ch_state[ch] in (CH_M1, CH_READY):
                # M1 → READY（如果 ≥ 2 个）；READY 再多收也无所谓
                if len(recs) >= 2:
                    self.ch_state[ch] = CH_READY
        elif result == 'no_signal':
            self.ch_state[ch] = CH_SKIP
            state.skipped.add(ch)
        elif result == 'near':
            # 已经在源附近 5m：直接进入"尝试清除"状态（用当前位置）
            self.ch_state[ch] = CH_READY
            # 不需要再测，把 state.pos 作为一个"假 bearing"也加入
            self.bearings[ch].append((state.pos, 0.0))
            self.bearings[ch].append((state.pos, 90.0))

    def on_clear(self, state: State, ch: int, success: bool):
        if success:
            self.ch_state[ch] = CH_CLEARED
            state.cleared.add(ch)
        else:
            self.clear_fails[ch] += 1
            if self.clear_fails[ch] >= MAX_CLEAR_FAILS:
                self.ch_state[ch] = CH_SKIP
                state.skipped.add(ch)


# ============================================================
# 具体策略
# ============================================================
class StaticScan(BaseStrategy):
    """固定在 (1000, 0)，对每个频道：
       1) measure(ch) @ (1000, 0)
       2) 若 direction：沿 θ 走 800m，再 measure(ch)
       3) 定位 → clear
    """
    name = "StaticScan"

    def first_pos(self, ch: int, state: State) -> Vec:
        return STATIC_POS


class Patrol(BaseStrategy):
    """在 4 个站位之间轮换：每站位扫所有频道。"""
    name = "Patrol"

    def __init__(self):
        super().__init__()
        self.site_idx = 0

    def first_pos(self, ch: int, state: State) -> Vec:
        return PATROL_POS[self.site_idx]

    def step(self, state: State) -> Action:
        # 在每站位扫一轮（len(CHANNELS) 个动作）
        a = super().step(state)
        # 当 cursor 回到 0，说明本轮结束 → 换站位
        if self.cursor % len(CHANNELS) == 0:
            self.site_idx = (self.site_idx + 1) % len(PATROL_POS)
        return a


class BlinkHop(BaseStrategy):
    """在初始 (0,0) 起步，每收 1 个 direction 就沿 θ 跳 800m 当作下个测点。"""
    name = "BlinkHop"

    def first_pos(self, ch: int, state: State) -> Vec:
        return state.pos  # 沿用当前位置

    def second_pos(self, ch: int, state: State,
                   first_record: Tuple[Vec, float]) -> Vec:
        S, theta = first_record
        return second_pos_from_bearing(S, theta, HOP_DIST)


class Hybrid(BaseStrategy):
    """早期：闪烁跳跃（pos 跟着 direction 走）；后期：固定到 STATIC_POS 精定位。"""
    name = "Hybrid"

    def __init__(self):
        super().__init__()
        self._phase = 'hop'   # 'hop' | 'static'
        self._switch_at = 5   # 已清除 ≥ 5 切换到 static

    def first_pos(self, ch: int, state: State) -> Vec:
        if self._phase == 'hop':
            return state.pos
        return STATIC_POS

    def second_pos(self, ch: int, state: State,
                   first_record: Tuple[Vec, float]) -> Vec:
        if self._phase == 'hop':
            S, theta = first_record
            return second_pos_from_bearing(S, theta, HOP_DIST)
        # static：固定基线，沿 θ 反方向 800m 作第 2 点
        S, theta = first_record
        rad = math.radians(theta)
        # 取与 first_pos 反向 + 800m
        return (STATIC_POS[0] - 800 * math.cos(rad),
                STATIC_POS[1] - 800 * math.sin(rad))

    def step(self, state: State) -> Action:
        # 阶段切换
        if self._phase == 'hop' and len(state.cleared) >= self._switch_at:
            self._phase = 'static'
        return super().step(state)


# ============================================================
# 工厂
# ============================================================
def make_strategy(name: str) -> BaseStrategy:
    return {
        'BlinkHop': BlinkHop,
        'StaticScan': StaticScan,
        'Patrol': Patrol,
        'Hybrid': Hybrid,
    }[name]()


if __name__ == "__main__":
    s = make_strategy('Hybrid')
    st = State(pos=(0.0, 0.0), ch=1)
    for i in range(8):
        a = s.step(st)
        print(i, a)
        if a.kind == 'done':
            break
