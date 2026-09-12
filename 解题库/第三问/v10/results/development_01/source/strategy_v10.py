"""第三问路线专项候选：继承官方演练行为吻合的 v8 定位与清除逻辑。"""
from strategy_v8 import AdaptiveV8
from route_search import route_order


class RouteV10(AdaptiveV8):
    name = 'RouteV10'

    @staticmethod
    def _route(start, nodes):
        nodes = list(nodes)
        if len(nodes) < 2:
            return nodes
        order = route_order(tuple(start), tuple(tuple(node[1]) for node in nodes))
        return [nodes[i] for i in order]


def make_strategy():
    return RouteV10()
