# -*- coding: utf-8 -*-
# mock_simulator_p4.py
# 第四问脱机 mock 模拟器（继承自第三问 + 加定向源）
#
# 用法：
#   python mock_simulator_p4.py
#   python mock_simulator_p4.py selfcheck

import math
import random
import hashlib
from typing import List, Tuple, Dict, Any, Optional


ARENA_R = 1800.0
R_EFF_MIN = 1000.0
R_EFF_MAX = 1500.0
EPS_DEG = 1.0
NEAR_THRESHOLD = 5.0
CLEAR_R = 20.0
SPEED = 5.0
DETECT_TIME = 5.0
SWITCH_TIME = 1.0
CLEAR_MISS = 3.0
CLEAR_HIT = 5.0
N_CHANNELS = 20
N_MIN = 10
N_MAX = 16


class P4MockSimulator:
    """第四问 mock：全向 + 定向混合干扰源。"""

    def __init__(self, seed: int = 42, n_sources: Optional[int] = None,
                 dir_frac: float = 0.5, error_mode: str = 'random',
                 reception_range=(R_EFF_MIN, R_EFF_MAX)):
        lo, hi = map(float, reception_range)
        if not (R_EFF_MIN <= lo <= hi <= R_EFF_MAX):
            raise ValueError("reception_range must lie within 1000..1500 metres")
        self.reception_range = (lo, hi)
        self.seed = seed
        if error_mode not in ('random','fixed','edge'):raise ValueError('Unknown error mode')
        self.error_mode=error_mode
        self.rng = random.Random(seed)
        self.N = n_sources or self.rng.randint(N_MIN, N_MAX)
        n_dir = int(round(self.N * dir_frac))
        # 随机分配哪些频道是定向
        dirs = sorted(self.rng.sample(list(range(1, N_CHANNELS + 1)), n_dir))
        omnichs = sorted(set(range(1, N_CHANNELS + 1)) - set(dirs))
        self.dir_channels = set(dirs)
        # 生成源
        used = set()
        self.sources: Dict[int, Dict[str, Any]] = {}
        # 定向源
        for ch in dirs:
            while True:
                pos = (self.rng.uniform(-ARENA_R, ARENA_R),
                       self.rng.uniform(-ARENA_R, ARENA_R))
                if math.hypot(*pos) <= ARENA_R:
                    break
            self.sources[ch] = {
                'pos': pos,
                're': self.rng.uniform(*self.reception_range),
                'direction': self.rng.uniform(0, 360),  # 定向方向 α₀
                'is_dir': True,
            }
            used.add(ch)
        # 全向源
        for ch in self.rng.sample(omnichs, self.N - len(self.sources)):
            while True:
                pos = (self.rng.uniform(-ARENA_R, ARENA_R),
                       self.rng.uniform(-ARENA_R, ARENA_R))
                if math.hypot(*pos) <= ARENA_R:
                    break
            self.sources[ch] = {
                'pos': pos,
                're': self.rng.uniform(*self.reception_range),
                'direction': None,
                'is_dir': False,
            }

        self.virtual_time_s = 0.0
        self.pos = (0.0, 0.0)
        self.ch = 1
        self.cleared: set = set()

    def _in_arena(self, p) -> bool:
        return math.hypot(*p) <= ARENA_R

    def _covered(self, src: dict, S) -> bool:
        """测向点 S 是否在源的信号覆盖范围内。
        - 全向源: 总是返回 True（只要距离 ≤ re）
        - 定向源: S 相对于源的方向与定向方向 α₀ 的夹角 ≤ 90°。"""
        if not src['is_dir']:
            return True
        dx = S[0] - src['pos'][0]
        dy = S[1] - src['pos'][1]
        if math.hypot(dx, dy) < 1e-9:
            return True  # 同一点，判为覆盖
        # dx,dy 已是 S-src，故必须直接使用源指向检测点的方位。
        bearing_src_to_S = math.degrees(math.atan2(dy, dx)) % 360
        diff = ((bearing_src_to_S - src['direction'] + 540) % 360) - 180
        return abs(diff) <= 90

    def _walk_time(self, new_pos) -> float:
        return math.hypot(new_pos[0] - self.pos[0],
                          new_pos[1] - self.pos[1]) / SPEED

    def enter(self):
        self.virtual_time_s = 0.0
        self.pos = (0.0, 0.0)
        self.ch = 1
        return {
            'accepted': True,
            'virtual_time_s': self.virtual_time_s,
            'remaining_real_duration_s': 1200.0,
            'max_virtual_duration_s': 360000.0,
        }

    def exit(self):
        return {'accepted': True,
                'virtual_time_s': self.virtual_time_s,
                'cleared': len(self.cleared)}

    def measure(self, x: float, y: float, ch: int):
        # 推断移动 + 切频道
        new_pos = (x, y)
        walk = self._walk_time(new_pos)
        switch = SWITCH_TIME if ch != self.ch else 0.0
        # 更新位置 + 频道
        self.pos = new_pos
        self.ch = ch
        self.virtual_time_s += walk + switch + DETECT_TIME

        if ch not in self.sources:
            result = 'no_signal'
            svd = None
        elif ch in self.cleared:
            # 已清除 → no_signal
            result = 'no_signal'
            svd = None
        else:
            src = self.sources[ch]
            d = math.hypot(self.pos[0] - src['pos'][0],
                           self.pos[1] - src['pos'][1])
            if d > src['re']:
                # 超出有效接收半径
                result = 'no_signal'
                svd = None
            elif d <= NEAR_THRESHOLD and self._covered(src, self.pos):
                # 近距 + 在覆盖范围
                result = 'near'
                svd = None
            elif self._covered(src, self.pos):
                # 正常 direction
                true_bearing = math.degrees(math.atan2(
                    src['pos'][1] - self.pos[1],
                    src['pos'][0] - self.pos[0])) % 360
                if self.error_mode=='random':
                    err = self.rng.uniform(-EPS_DEG, EPS_DEG)
                else:
                    key=f'{self.seed}:{ch}:{x:.8f}:{y:.8f}'.encode()
                    u=int.from_bytes(hashlib.sha256(key).digest()[:8],'big')/(2**64-1)
                    err=(2*u-1)*EPS_DEG if self.error_mode=='fixed' else (EPS_DEG if u>=0.5 else -EPS_DEG)
                result = 'direction'
                svd = round((true_bearing + err) % 360,2)%360
            else:
                # 在覆盖范围外
                result = 'no_signal'
                svd = None

        return {'accepted': True,
                'measure_result': result, 'svd_deg': svd,
                'virtual_time_s': self.virtual_time_s}

    def clear(self, x: float, y: float, ch: int):
        new_pos = (x, y)
        walk = self._walk_time(new_pos)
        self.pos = new_pos
        # /clear 不切换测向机频道
        if ch not in self.sources or ch in self.cleared:
            self.virtual_time_s += walk + CLEAR_MISS
            return {'accepted': True,
                    'clear_result': 'no_target_in_range',
                    'virtual_time_s': self.virtual_time_s}
        src = self.sources[ch]
        d = math.hypot(self.pos[0] - src['pos'][0],
                       self.pos[1] - src['pos'][1])
        if d <= CLEAR_R:
            self.cleared.add(ch)
            self.virtual_time_s += walk + CLEAR_HIT
            return {'accepted': True,
                    'clear_result': 'success',
                    'virtual_time_s': self.virtual_time_s}
        else:
            self.virtual_time_s += walk + CLEAR_MISS
            return {'accepted': True,
                    'clear_result': 'no_target_in_range',
                    'virtual_time_s': self.virtual_time_s}

    def stats(self) -> dict:
        """返回赛后统计；不向策略暴露源真值。"""
        return {
            'N': self.N,
            'directional_count': len(self.dir_channels),
            'cleared': len(self.cleared),
            'clear_ratio': len(self.cleared) / self.N if self.N else 1.0,
        }


def _self_test():
    sim = P4MockSimulator(seed=42)
    print(f"P4 mock: N={sim.N}, dir_channels={sorted(sim.dir_channels)}")
    entered = sim.enter()
    assert entered['accepted'] is True
    assert entered['virtual_time_s'] == 0.0
    assert entered['remaining_real_duration_s'] == 1200.0
    assert entered['max_virtual_duration_s'] == 360000.0
    measured = sim.measure(0, 0, 1)
    print("测向点 (0,0) 测频道 1：", measured)
    assert measured['accepted'] is True
    assert isinstance(measured['virtual_time_s'], (int, float))
    cleared = sim.clear(0, 0, 1)
    assert cleared['accepted'] is True
    exited = sim.exit()
    assert exited['accepted'] is True
    assert isinstance(exited['virtual_time_s'], (int, float))
    assert sim.N >= 10 and sim.N <= 16
    assert any(s['is_dir'] for s in sim.sources.values())
    assert any(not s['is_dir'] for s in sim.sources.values())
    print("P4 mock selfcheck passed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'selfcheck':
        _self_test()
    else:
        sim = P4MockSimulator(seed=42)
        print(f"N = {sim.N}, dir_channels = {sorted(sim.dir_channels)}")
        for ch in sorted(sim.sources.keys())[:5]:
            s = sim.sources[ch]
            kind = "DIR" if s['is_dir'] else "OMNI"
            print(f"  ch={ch} {kind} pos=({s['pos'][0]:.0f},{s['pos'][1]:.0f}) "
                  f"re={s['re']:.0f}"
                  + (f" α₀={s['direction']:.1f}°" if s['is_dir'] else ""))
