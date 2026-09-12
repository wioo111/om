"""开发对照：获得多次测向后，允许在长距离接近目标前重新选路。"""
from strategy_v8 import CLEAR_R, distance
from strategy_v10 import RouteV10


class ReactiveRouteV10(RouteV10):
    name = 'ReactiveRouteV10'

    def step(self, state):
        track = self.tracks.get(self.active_ch)
        if (not self.scan_pending and not self.scan_queue and track is not None
                and not track.probe_after_fail and track.near is None
                and len(track.records) >= 2
                and distance(state.pos, track.estimate) > 2 * CLEAR_R):
            # 只释放行程的目标锁。仍由 v8 生成测量/清除动作，失败现场优先恢复。
            self.active_ch = None
        return super().step(state)
