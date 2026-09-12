"""机器 A：仅优化目标路线、补充覆盖站位和站位移动。

起始模板与 v8 完全相同，不代表已经有性能改进。
请保留 RouteMixin 和 make_strategy 名称，便于机器 C 组合。
"""
from strategy_v8 import AdaptiveV8


class RouteMixin:
    # 在这里重写路线方法；新增状态使用 route_ 前缀。
    # _next_destination / _cover_route / _build_cover_route /
    # _route / _refine_station / _explore_action
    pass


class RouteCandidate(RouteMixin, AdaptiveV8):
    name = 'RouteCandidate'


def make_strategy():
    return RouteCandidate()
