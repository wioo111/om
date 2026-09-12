"""机器 B：仅优化扫描选择、测点选择及清除后的补测。

本轮改动（候选 B01）聚焦两点，均落在"交会测点 / 补测时机"职责内：
1. 缩短第二测向的位移：first_hop 300→200、lateral 150→100。移动代价 5 m/s
   远高于单次检测 5 s，因此略微牺牲角度多样性、换取更短的补测位移。
2. 收紧清除阈值 probe_radius 80→50：定位包围圆半径超过约 40 m 时清除失败率
   过半（开发集上失败半径集中 25–78 m），把"直接清/再测一次"的判定点前移，
   减少清除失败后的补测链。

保留 MeasureMixin 与 make_strategy 名称；构造函数沿 super() 链初始化，
不改变 State、Track 既有字段含义。
"""
from strategy_v8 import AdaptiveV8


class MeasureMixin:
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('first_hop', 200.0)
        kwargs.setdefault('lateral', 100.0)
        kwargs.setdefault('probe_radius', 50.0)
        super().__init__(*args, **kwargs)


class MeasureCandidate(MeasureMixin, AdaptiveV8):
    name = 'MeasureCandidate'


def make_strategy():
    return MeasureCandidate()
