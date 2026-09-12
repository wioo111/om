"""机器 B：仅优化扫描选择、测点选择及清除后的补测。

起始模板与 v8 完全相同，不代表已经有性能改进。
请保留 MeasureMixin 和 make_strategy 名称，便于机器 C 组合。
"""
from strategy_v8 import AdaptiveV8


class MeasureMixin:
    # 在这里重写测量方法；新增状态使用 measure_ 前缀。
    # _start_scan / _local_action / on_measure / on_clear
    # 如需 __init__，必须通过 super() 调用基类，保留既有状态含义。
    pass


class MeasureCandidate(MeasureMixin, AdaptiveV8):
    name = 'MeasureCandidate'


def make_strategy():
    return MeasureCandidate()
