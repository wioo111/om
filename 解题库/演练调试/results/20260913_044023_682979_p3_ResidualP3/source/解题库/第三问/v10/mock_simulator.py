# -*- coding: utf-8 -*-
# mock_simulator.py
# 第三问本地 mock 模拟器（脱机评估用）
#
# 严格按附件 1 / 附件 2 的物理规则实现：
#   - 10–16 个全向干扰源（N 在范围内随机，频道互不相同）
#   - /measure：返回 no_signal / near / direction（direction 含 ±1° 误差的示向度）
#   - /clear：返回 success / no_target_in_range
#   - 移动 = 距离/5 m/s；切换频道 = 1 s；检测 = 5 s；清除 = 3/5 s
#   - 近距阈值 5 m（直接 near）；清除半径 20 m
#   - 有效接收半径 1000–1500 m

import math
import random
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Vec = Tuple[float, float]

# ============================================================
# 题目常量
# ============================================================
ARENA_RADIUS = 1800.0          # 目标区域半径
CHANNELS = list(range(1, 21))  # 频道集
SPEED = 5.0                    # 移动速度 m/s
T_MEASURE = 5.0                # 单次检测耗时
T_SWITCH = 1.0                 # 切换频道耗时
T_CLEAR_FAIL = 3.0             # 清除未发现耗时
T_CLEAR_OK = 5.0               # 清除成功耗时
NEAR_RADIUS = 5.0              # 近距阈值
CLEAR_RADIUS = 20.0            # 清除半径
EPS_DEG = 1.0                  # 示向度误差范围


@dataclass
class Source:
    """一个全向干扰源（mock 内部用）。"""
    ch: int
    pos: Vec
    R_eff: float                 # 有效接收半径 1000–1500
    cleared: bool = False

    def can_receive(self, P: Vec) -> bool:
        """判断 P 是否在该源的有效接收距离内（全向）。"""
        dx = P[0] - self.pos[0]
        dy = P[1] - self.pos[1]
        return dx * dx + dy * dy <= self.R_eff * self.R_eff

    def bearing_deg(self, P: Vec) -> float:
        """从 P 看该源的真实方位角（0°=东，逆时针为正，[0,360)）。"""
        dx = self.pos[0] - P[0]
        dy = self.pos[1] - P[1]
        return (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0


@dataclass
class MockResponse:
    """统一响应结构（与真模拟器字段名一致）。"""
    accepted: bool
    measure_result: Optional[str] = None   # no_signal / near / direction
    svd_deg: Optional[float] = None
    clear_result: Optional[str] = None     # success / no_target_in_range
    virtual_time_s: float = 0.0
    extra: Dict = field(default_factory=dict)


class MockSimulator:
    """完全脱机的模拟器实现，与真模拟器调用接口一致。"""

    def __init__(self, seed: int = 42, N: Optional[int] = None,
                 R_eff_range: Tuple[float, float] = (1000.0, 1500.0),
                 verbose: bool = False, error_mode: str = 'fixed'):
        self.seed = seed
        self.rng = random.Random(seed)
        self.N = N if N is not None else self.rng.randint(10, 16)
        self.R_eff_range = R_eff_range
        self.verbose = verbose
        if error_mode not in ('fixed', 'bias', 'smooth', 'edge'):
            raise ValueError('unknown error_mode')
        self.error_mode = error_mode

        # 机器狗状态
        self.pos: Vec = (0.0, 0.0)
        self.cur_ch: int = 1
        self.entered: bool = False
        self.virtual_time: float = 0.0

        # 干扰源
        self.sources: Dict[int, Source] = self._gen_sources()

        # 评估用
        self.measure_count: int = 0
        self.clear_count: int = 0
        self.log: List[dict] = []

    # --------------------------------------------------------
    # 场景生成
    # --------------------------------------------------------
    def _gen_sources(self) -> Dict[int, Source]:
        """在目标区域内随机生成 N 个频道互不相同的全向干扰源。"""
        chs = self.rng.sample(CHANNELS, self.N)
        srcs: Dict[int, Source] = {}
        for ch in chs:
            # 在圆内均匀采样
            while True:
                x = self.rng.uniform(-ARENA_RADIUS, ARENA_RADIUS)
                y = self.rng.uniform(-ARENA_RADIUS, ARENA_RADIUS)
                if x * x + y * y <= ARENA_RADIUS * ARENA_RADIUS:
                    break
            R_eff = self.rng.uniform(*self.R_eff_range)
            srcs[ch] = Source(ch=ch, pos=(x, y), R_eff=R_eff)
        return srcs

    # --------------------------------------------------------
    # 内部工具
    # --------------------------------------------------------
    def _add_time(self, dt: float):
        self.virtual_time += dt

    def _move_cost(self, new_pos: Vec) -> float:
        dx = new_pos[0] - self.pos[0]
        dy = new_pos[1] - self.pos[1]
        return math.hypot(dx, dy) / SPEED

    def _log(self, action: str, req: dict, resp: MockResponse):
        self.log.append({
            'action': action,
            'req': {k: v for k, v in req.items() if k != 'arena_id'},
            'resp': {
                'accepted': resp.accepted,
                'measure_result': resp.measure_result,
                'svd_deg': resp.svd_deg,
                'clear_result': resp.clear_result,
                'virtual_time_s': resp.virtual_time_s,
            },
        })

    # --------------------------------------------------------
    # 公开 API（与真模拟器一致）
    # --------------------------------------------------------
    def enter(self, robot_id: str = "MOCK", request_id: str = "enter-1"
              ) -> MockResponse:
        self.pos = (0.0, 0.0)
        self.cur_ch = 1
        self.entered = True
        self.virtual_time = 0.0
        resp = MockResponse(accepted=True, virtual_time_s=0.0,
                            extra={'remaining_real_duration_s': 1200,
                                   'max_virtual_duration_s': 360000})
        self._log('/enter', {'robot_id': robot_id, 'request_id': request_id}, resp)
        return resp

    def measure(self, x: float, y: float, channel: int,
                request_id: str = "m") -> MockResponse:
        """按附件 1 规则返回 measure_result。"""
        if not self.entered:
            return MockResponse(accepted=False, virtual_time_s=0.0)

        new_pos = (float(x), float(y))
        # 1) 移动
        t_move = self._move_cost(new_pos)
        # 2) 切频道
        t_switch = T_SWITCH if channel != self.cur_ch else 0.0
        # 3) 检测
        t_act = T_MEASURE
        self._add_time(t_move + t_switch + t_act)
        self.pos = new_pos
        self.cur_ch = channel
        self.measure_count += 1

        # 找该频道的源
        src = self.sources.get(channel)
        if src is None or src.cleared:
            res = MockResponse(
                accepted=True, measure_result='no_signal',
                virtual_time_s=self.virtual_time,
            )
            self._log('/measure',
                      {'position': new_pos, 'channel': channel,
                       'request_id': request_id}, res)
            return res

        # 距离判定
        dx = new_pos[0] - src.pos[0]
        dy = new_pos[1] - src.pos[1]
        dist = math.hypot(dx, dy)
        if dist <= NEAR_RADIUS:
            res = MockResponse(
                accepted=True, measure_result='near',
                virtual_time_s=self.virtual_time,
            )
            self._log('/measure',
                      {'position': new_pos, 'channel': channel,
                       'request_id': request_id}, res)
            return res

        if not src.can_receive(new_pos):
            res = MockResponse(
                accepted=True, measure_result='no_signal',
                virtual_time_s=self.virtual_time,
            )
            self._log('/measure',
                      {'position': new_pos, 'channel': channel,
                       'request_id': request_id}, res)
            return res

        # 同一频道、同一位置的误差固定；按官方接口将示向度保留两位小数。
        true_b = src.bearing_deg(new_pos)
        px, py = (0.0 if v == 0.0 else v for v in new_pos)
        key = f'{self.seed}:{channel}:{px.hex()}:{py.hex()}'
        code = int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), 'big')
        noise = 2 * (code / (2**64 - 1)) - 1
        if self.error_mode == 'bias':
            noise = math.sin(self.seed * 0.123 + channel * 12.34)
        elif self.error_mode == 'smooth':
            noise = math.sin(new_pos[0] / 180 + new_pos[1] / 240
                             + self.seed * 0.123 + channel)
        elif self.error_mode == 'edge':
            noise = 1.0 if code % 2 else -1.0
        svd = round((true_b + noise * EPS_DEG) % 360.0, 2) % 360.0
        res = MockResponse(
            accepted=True, measure_result='direction', svd_deg=svd,
            virtual_time_s=self.virtual_time,
        )
        self._log('/measure',
                  {'position': new_pos, 'channel': channel,
                   'request_id': request_id}, res)
        return res

    def clear(self, x: float, y: float, channel: int,
              request_id: str = "c") -> MockResponse:
        if not self.entered:
            return MockResponse(accepted=False, virtual_time_s=0.0)

        new_pos = (float(x), float(y))
        t_move = self._move_cost(new_pos)
        self._add_time(t_move)
        self.pos = new_pos
        self.clear_count += 1

        src = self.sources.get(channel)
        if src is None or src.cleared:
            self._add_time(T_CLEAR_FAIL)
            res = MockResponse(
                accepted=True, clear_result='no_target_in_range',
                virtual_time_s=self.virtual_time,
            )
            self._log('/clear',
                      {'position': new_pos, 'channel': channel,
                       'request_id': request_id}, res)
            return res

        dx = new_pos[0] - src.pos[0]
        dy = new_pos[1] - src.pos[1]
        if math.hypot(dx, dy) <= CLEAR_RADIUS:
            src.cleared = True
            self._add_time(T_CLEAR_OK)
            res = MockResponse(
                accepted=True, clear_result='success',
                virtual_time_s=self.virtual_time,
            )
            self._log('/clear',
                      {'position': new_pos, 'channel': channel,
                       'request_id': request_id}, res)
            return res

        self._add_time(T_CLEAR_FAIL)
        res = MockResponse(
            accepted=True, clear_result='no_target_in_range',
            virtual_time_s=self.virtual_time,
        )
        self._log('/clear',
                  {'position': new_pos, 'channel': channel,
                   'request_id': request_id}, res)
        return res

    def exit(self, request_id: str = "exit-1") -> MockResponse:
        res = MockResponse(
            accepted=True, virtual_time_s=self.virtual_time,
            extra={'exit_reason': 'user_exit'},
        )
        self._log('/exit', {'request_id': request_id}, res)
        return res

    # --------------------------------------------------------
    # 评估用辅助
    # --------------------------------------------------------
    def stats(self) -> dict:
        cleared = sum(1 for s in self.sources.values() if s.cleared)
        return {
            'N': self.N,
            'cleared': cleared,
            'clear_rate': cleared / self.N,
            'virtual_time_s': self.virtual_time,
            'avg_time_per_cleared': (self.virtual_time / cleared
                                     if cleared > 0 else float('inf')),
            'measure_count': self.measure_count,
            'clear_count': self.clear_count,
            'sources_truth': {ch: (s.pos, s.R_eff, s.cleared)
                              for ch, s in self.sources.items()},
        }


if __name__ == "__main__":
    # 快速自检：随机跑几个动作
    import json
    sim = MockSimulator(seed=42, verbose=True)
    sim.enter()
    print("N =", sim.N, "channels:", sorted(sim.sources.keys()))
    # 摸一个频道
    sim.measure(0, 0, 1)
    sim.measure(0, 0, 2)
    sim.exit()
    print(json.dumps(sim.stats(), indent=2, default=str))
