"""机器 C：组合两个候选；组合成绩必须重新测量，不能相加单项收益。"""
from strategy_v8 import AdaptiveV8
from collab.route_candidate import RouteMixin
from collab.measure_candidate import MeasureMixin


class CombinedCandidate(RouteMixin, MeasureMixin, AdaptiveV8):
    name = 'CombinedCandidate'


def make_strategy():
    return CombinedCandidate()
