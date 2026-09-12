# -*- coding: utf-8 -*-
# strategy_v6.py
# 第三问 v6：吸收新方案的 6 个改造点
#
# 改造点（相对 v5）：
#   1) 目标改为 max|R| s.t. T ≤ 1200（16 源全清不可达）
#   2) 原点起步扫描：先扫全部 20 频道，发现约 11 源
#   3) 三点小基线精定位：第2点沿 θ 走 200m，第3点垂直 200m，第4点备用
#   4) 阶段穿插：每扫5个频道立即精定位已发现源
#   5) 4 主轴补充扫：沿 E/N/W/S 各走 L_axis 米重扫 no_signal 频道
#   6) 时间检查 + 失败1次换方向：T>1100 放弃该源；clear失败1次换补点方向
#
# 与 v5 共用：problem1_v4_inline.py（已内联 Q1 v4）+ mock_simulator.py

import math
import os
import importlib.util as _ilu
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set

# 加载 Q1 v4（自包含）
_HERE = os.path.dirname(os.path.abspath(__file__))
_INLINE = os.path.join(_HERE, 'problem1_v4_inline.py')
_spec = _ilu.spec_from_file_location('problem1_v4', _INLINE)
p1 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(p1)

# ============================================================
# 常量（按新方案校准）
# ============================================================
Vec = Tuple[float, float]
CHANNELS = list(range(1, 21))
ARENA_R = 1800.0
EPS_DEG = 1.0
CLEAR_R = 20.0
SPEED = 5.0
HOP_DIST = 200.0           # 改造点 #3：200m 小基线（v5 是 800m）
VERT_DIST = 200.0          # 改造点 #3：垂直方向 200m
L_AXIS = 600.0             # 改造点 #5：主轴扫描长度
BATCH_SIZE = 5             # 改造点 #4：每扫5个频道立即穿插精定位
TIME_BUDGET = 1150.0       # 改造点 #6：剩余时间 < 50s 时退出
TIME_ABORT_SRC = 1100.0    # 改造点 #6：单源精定位前检查剩余时间

# 阶段
PHASE_COARSE = 'coarse'    # 原点扫频道
PHASE_REFINE = 'refine'    # 精定位已发现源（穿插）
PHASE_AXIS = 'axis'        # 4 主轴扫残源
PHASE_DONE = 'done'


# ============================================================
# 工具
# ============================================================
def localize(records: List[Tuple[Vec, float]],
             eps: float = EPS_DEG) -> Optional[Tuple[Vec, float]]:
    if len(records) < 2:
        return None
    dets = [r[0] for r in records]
    thetas = [r[1] for r in records]
    res = p1.solve_problem_1(dets, thetas, eps_deg=eps,
                             R_eff=1500.0, R_target=ARENA_R, N_disk=32)
    if res['n_vertices'] < 3 or res['D'] < 1e-3:
        return None
    return res['mec_center'], res['mec_radius']


def add_offset(p: Vec, theta_deg: float, dist: float) -> Vec:
    rad = math.radians(theta_deg)
    return (p[0] + dist * math.cos(rad),
            p[1] + dist * math.sin(rad))


def perp(theta_deg: float) -> float:
    """垂直方向（逆时针 90°）。"""
    return (theta_deg + 90.0) % 360.0


# ============================================================
# per-channel 状态机
# ============================================================
CH_NEW = 'new'           # 还没扫过该频道
CH_DISCOVERED = 'disc'   # 收到 direction 还没定位收敛
CH_READY = 'ready'       # ≥2 bearing + MEC ≤ 20m，可清除
CH_CLEARED = 'cleared'   # 已清除
CH_SKIP = 'skip'         # 放弃（多次失败或剩余时间不够）


# ============================================================
# 策略主体
# ============================================================
class V6Strategy:
    """v6 主策略：4 阶段状态机 + per-channel 状态机。"""

    name = "V6"

    def __init__(self):
        self.phase = PHASE_COARSE
        # coarse 阶段：扫频道的进度
        self.coarse_idx = 0              # 下一个要扫的频道（CHANNELS 索引）
        self.batch_progress = 0          # 当前 batch 内已扫的频道数
        # refine 阶段：精定位待处理的频道
        self.refine_queue: List[int] = []  # 待精定位的频道（FIFO）
        # axis 阶段：4 主轴扫描进度
        self.axis_idx = 0                # 0=东,1=北,2=西,3=南
        self.axis_ch_idx = 0             # 主轴端点上扫的频道进度
        # per-channel 状态
        self.ch_state: Dict[int, str] = {ch: CH_NEW for ch in CHANNELS}
        self.bearings: Dict[int, List[Tuple[Vec, float]]] = {ch: [] for ch in CHANNELS}
        self.supplement_dir: Dict[int, int] = {ch: 0 for ch in CHANNELS}  # 第4点换向计数
        self.no_signal_channels: Set[int] = set()  # 在原点扫到 no_signal 的频道（后面要重扫）
        # 全局
        self.cleared: Set[int] = set()
        self.skipped: Set[int] = set()
        self._steps = 0

    def step(self, state: State) -> Action:
        if self.phase == PHASE_DONE:
            return Action('done')
        self._steps += 1
        if self._steps > 12000:
            self.phase = PHASE_DONE
            return Action('done')
        # 改造点 #6：剩余时间检查
        if state.virtual_time > TIME_BUDGET:
            self.phase = PHASE_DONE
            return Action('done')

        if self.phase == PHASE_COARSE:
            return self._step_coarse(state)
        elif self.phase == PHASE_REFINE:
            return self._step_refine(state)
        elif self.phase == PHASE_AXIS:
            return self._step_axis(state)
        return Action('done')

    # --------------------------------------------------------
    # 阶段 1：原点扫频道 + 穿插精定位
    # --------------------------------------------------------
    def _step_coarse(self, state: State) -> Action:
        # 先看看 refine 队列
        a = self._try_refine(state)
        if a is not None:
            return a

        # 当前 batch 内扫下一个频道
        if self.coarse_idx >= len(CHANNELS):
            # 原点扫完所有频道（不论是否扫到）
            self.phase = PHASE_AXIS
            return self._step_axis(state)

        if self.batch_progress >= BATCH_SIZE:
            # 当前 batch 完成 → 强制精定位
            self.batch_progress = 0
            a = self._refine_one(state)
            if a is not None:
                return a
            # 没有待精定位频道时，直接继续扫描下一个频道。

        ch = CHANNELS[self.coarse_idx]
        self.coarse_idx += 1
        self.batch_progress += 1
        # 在原点 (0,0) 扫
        return Action('measure', (0.0, 0.0), ch)

    def _try_refine(self, state: State) -> Optional[Action]:
        if not self.refine_queue:
            return None
        ch = self.refine_queue[0]
        if self.ch_state[ch] in (CH_CLEARED, CH_SKIP):
            self.refine_queue.pop(0)
            return None
        return self._refine_one(state)

    def _refine_one(self, state: State) -> Action:
        """精定位下一个频道；如果没东西要精定位则返回 None（让外层继续扫频道）。"""
        # 从 refine_queue 找一个还能处理的
        while self.refine_queue:
            ch = self.refine_queue[0]
            if self.ch_state[ch] in (CH_CLEARED, CH_SKIP):
                self.refine_queue.pop(0)
                continue
            # 改造点 #6：单源时间检查
            if state.virtual_time > TIME_ABORT_SRC:
                self.ch_state[ch] = CH_SKIP
                self.skipped.add(ch)
                self.refine_queue.pop(0)
                continue
            return self._do_refine(ch, state)
        return None

    def _do_refine(self, ch: int, state: State) -> Action:
        """实际执行一个精定位动作。"""
        recs = self.bearings[ch]
        st = self.ch_state[ch]

        if st == CH_DISCOVERED and len(recs) == 1:
            # 第一步：从当前位置走到 S2（沿 θ1 走 200m）
            S1, theta1 = recs[0]
            S2 = add_offset(S1, theta1, HOP_DIST)
            return Action('measure', S2, ch)

        if st == CH_DISCOVERED and len(recs) == 2:
            # 第二步：垂直方向走 200m 到 S3
            S1, theta1 = recs[0]
            S2, theta2 = recs[1]
            # 沿 S2 的 θ2 垂直方向走 VERT_DIST
            S3 = add_offset(S2, perp(theta2), VERT_DIST)
            return Action('measure', S3, ch)

        if st == CH_READY:
            # 尝试清除
            loc = localize(recs)
            if loc is None:
                # 几何退化（反向扇形），放弃
                self.ch_state[ch] = CH_SKIP
                self.skipped.add(ch)
                if self.refine_queue and self.refine_queue[0] == ch:
                    self.refine_queue.pop(0)
                return Action('measure', state.pos, ch)  # 占位，让外层再 step
            c, r = loc
            if r <= CLEAR_R:
                return Action('clear', c, ch)
            # 改造点 #6：失败 → 换补点方向（最多 2 次换向）
            sup = self.supplement_dir[ch]
            if sup >= 2:
                self.ch_state[ch] = CH_SKIP
                self.skipped.add(ch)
                if self.refine_queue and self.refine_queue[0] == ch:
                    self.refine_queue.pop(0)
                return Action('measure', state.pos, ch)
            # 补第 4 点：沿 θ 方向再走 200m
            S1, theta1 = recs[0]
            extra = add_offset(S1, theta1, HOP_DIST * (2 + sup))
            self.supplement_dir[ch] = sup + 1
            return Action('measure', extra, ch)

        # 默认
        return Action('measure', state.pos, ch)

    # --------------------------------------------------------
    # 阶段 3：4 主轴扫残源
    # --------------------------------------------------------
    def _step_axis(self, state: State) -> Action:
        # 先看 refine 队列
        a = self._try_refine(state)
        if a is not None:
            return a
        a = self._refine_one(state)
        if a is not None:
            return a

        # 4 主轴：东、北、西、南
        axis_dirs = [0.0, 90.0, 180.0, 270.0]
        if self.axis_idx >= len(axis_dirs):
            self.phase = PHASE_DONE
            return Action('done')

        # 还没到端点？走
        if state.virtual_time > TIME_BUDGET:
            self.phase = PHASE_DONE
            return Action('done')

        # 在端点扫：只扫那些在原点 no_signal 的频道
        candidates = [ch for ch in self.no_signal_channels
                      if ch not in self.cleared and ch not in self.skipped]
        if not candidates:
            # 没有可扫的频道，换下一个主轴
            self.axis_idx += 1
            self.axis_ch_idx = 0
            if self.axis_idx >= len(axis_dirs):
                self.phase = PHASE_DONE
                return Action('done')
            # 走到下一主轴端点
            d = axis_dirs[self.axis_idx]
            target = add_offset(state.pos, d, L_AXIS)
            return Action('measure', target, 1)  # 占位（先移动）
        if self.axis_ch_idx >= len(candidates):
            self.axis_idx += 1
            self.axis_ch_idx = 0
            d = axis_dirs[self.axis_idx]
            target = add_offset(state.pos, d, L_AXIS)
            return Action('measure', target, 1)  # 占位

        # 在当前主轴端点测一个频道
        ch = candidates[self.axis_ch_idx]
        self.axis_ch_idx += 1
        d = axis_dirs[self.axis_idx]
        target = add_offset(state.pos, d, L_AXIS)
        return Action('measure', target, ch)

    # --------------------------------------------------------
    # 回调
    # --------------------------------------------------------
    def on_measure(self, state: State, ch: int, result: str,
                   svd: Optional[float]):
        if result == 'direction' and svd is not None:
            recs = self.bearings[ch]
            pos = state.pos
            # 同一位置不重复
            if not any((abs(S[0] - pos[0]) < 1e-3 and
                        abs(S[1] - pos[1]) < 1e-3) for S, _ in recs):
                recs.append((pos, svd))
            if self.ch_state[ch] == CH_NEW:
                self.ch_state[ch] = CH_DISCOVERED
                # 加入精定位队列
                if ch not in self.refine_queue:
                    self.refine_queue.append(ch)
            elif self.ch_state[ch] == CH_DISCOVERED and len(recs) >= 2:
                # 检查定位是否收敛
                loc = localize(recs)
                if loc is not None and loc[1] <= CLEAR_R:
                    self.ch_state[ch] = CH_READY
            elif self.ch_state[ch] == CH_READY:
                # 补点后重算
                loc = localize(recs)
                if loc is not None and loc[1] <= CLEAR_R:
                    self.ch_state[ch] = CH_READY
                else:
                    self.ch_state[ch] = CH_DISCOVERED  # 回退
        elif result == 'no_signal':
            if self.phase == PHASE_COARSE:
                # 原点扫到 no_signal，记下来后面主轴重扫
                self.no_signal_channels.add(ch)
        elif result == 'near':
            # 已经非常接近源，直接尝试清除
            self.bearings[ch].append((state.pos, 0.0))
            self.bearings[ch].append((state.pos, 90.0))
            self.ch_state[ch] = CH_READY
            if ch not in self.refine_queue:
                self.refine_queue.append(ch)

    def on_clear(self, state: State, ch: int, success: bool):
        if success:
            self.ch_state[ch] = CH_CLEARED
            self.cleared.add(ch)
            if ch in self.refine_queue:
                self.refine_queue.remove(ch)
        else:
            # 改造点 #6：失败1次换方向（不是重试同一位置）
            # _do_refine 会处理；这里只更新状态
            # 失败但有可能再补点成功，所以不回退状态
            pass


# ============================================================
# Action / State（与 v5 兼容）
# ============================================================
@dataclass
class Action:
    kind: str
    pos: Vec = (0.0, 0.0)
    ch: int = 1


@dataclass
class State:
    pos: Vec
    ch: int
    cleared: Set[int] = field(default_factory=set)
    skipped: Set[int] = field(default_factory=set)
    bearing_records: Dict[int, List[Tuple[Vec, float]]] = field(default_factory=dict)
    virtual_time: float = 0.0


def make_strategy(name: str = "V6"):
    if name == "V6":
        return V6Strategy()
    raise ValueError(f"未知策略 {name}；v6 只支持 V6")
