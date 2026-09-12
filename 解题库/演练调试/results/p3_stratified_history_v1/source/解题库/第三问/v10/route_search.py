"""开放路径排序。起点固定，终点自由；输入只有当前已知的规划点。"""
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=13)
def _layers(n):
    groups = [[] for _ in range(n + 1)]
    for mask in range(1, 1 << n):
        groups[mask.bit_count()].append(mask)
    return tuple(np.asarray(group, dtype=np.int32) for group in groups)


def exact_order(matrix):
    """Held–Karp 动态规划；matrix[0] 是起点，其余行列是待访问点。"""
    n = len(matrix) - 1
    if n <= 1:
        return list(range(1, n + 1))
    costs = np.full((1 << n, n), np.inf)
    parent = np.full((1 << n, n), -1, dtype=np.int8)
    for j in range(n):
        costs[1 << j, j] = matrix[0, j + 1]
    for masks in _layers(n)[2:]:
        for j in range(n):
            selected = masks[(masks & (1 << j)) != 0]
            previous = selected ^ (1 << j)
            incoming = costs[previous] + matrix[1:, j + 1]
            best = np.argmin(incoming, axis=1)
            costs[selected, j] = incoming[np.arange(len(selected)), best]
            parent[selected, j] = best
    mask = (1 << n) - 1
    j = int(np.argmin(costs[mask]))
    order = []
    while mask:
        order.append(j + 1)
        before = int(parent[mask, j])
        mask ^= 1 << j
        j = before
    return order[::-1]


def _polish(order, matrix):
    """较大点集用 2-opt 和连续 1–2 点重插入；保留自由终点。"""
    order = list(order)
    n = len(order)
    d = matrix.tolist()
    for _ in range(30):
        best_gain, operation = 1e-7, None
        for i in range(n - 1):
            previous = order[i - 1] if i else 0
            for j in range(i + 1, n):
                gain = d[previous][order[i]] - d[previous][order[j]]
                if j + 1 < n:
                    nxt = order[j + 1]
                    gain += d[order[j]][nxt] - d[order[i]][nxt]
                if gain > best_gain:
                    best_gain, operation = gain, ('reverse', i, j, 0)
        for width in (1, 2):
            for i in range(n - width + 1):
                first, last = order[i], order[i + width - 1]
                previous = order[i - 1] if i else 0
                nxt = order[i + width] if i + width < n else None
                saving = d[previous][first]
                if nxt is not None:
                    saving += d[last][nxt] - d[previous][nxt]
                reduced = order[:i] + order[i + width:]
                for gap in range(len(reduced) + 1):
                    if gap == i:
                        continue
                    a = reduced[gap - 1] if gap else 0
                    b = reduced[gap] if gap < len(reduced) else None
                    added = d[a][first]
                    if b is not None:
                        added += d[last][b] - d[a][b]
                    gain = saving - added
                    if gain > best_gain:
                        best_gain, operation = gain, ('insert', i, gap, width)
        if operation is None:
            break
        kind, i, j, width = operation
        if kind == 'reverse':
            order[i:j + 1] = reversed(order[i:j + 1])
        else:
            segment = order[i:i + width]
            del order[i:i + width]
            order[j:j] = segment
    return order


@lru_cache(maxsize=256)
def route_order(start, positions):
    """缓存仅含规划点坐标，既不保存观测响应，也不引入模拟器真值。"""
    n = len(positions)
    points = np.asarray((start,) + positions, dtype=float)
    delta = points[:, None, :] - points[None, :, :]
    matrix = np.sqrt(np.sum(delta * delta, axis=2))
    if n <= 13:
        return tuple(i - 1 for i in exact_order(matrix))
    candidates = [list(range(1, n + 1))]
    for first in np.argsort(matrix[0, 1:], kind='stable')[:4] + 1:
        remaining = list(range(1, n + 1))
        order = [int(first)]
        remaining.remove(first)
        while remaining:
            nxt = min(remaining, key=lambda i: matrix[order[-1], i])
            remaining.remove(nxt)
            order.append(nxt)
        candidates.append(order)
    polished = [_polish(order, matrix) for order in candidates]
    def cost(order):
        return sum(matrix[a, b] for a, b in zip([0] + order, order))
    return tuple(i - 1 for i in min(polished, key=cost))
