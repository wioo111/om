# -*- coding: utf-8 -*-
# robot.py
# 第三问：真模拟器 HTTP 客户端 + 策略调度
#
# 用法：
#   from robot import run
#   run(strategy_name='Hybrid', robot_id='<参赛队号>', base_url='http://127.0.0.1:2026')
#
# 严格按附件 1 实现：
#   - HTTP POST + JSON
#   - Content-Type: application/json
#   - 每个新动作使用新 request_id；重试复用
#   - 同时检查 HTTP 状态和 accepted
#   - 字段：arena_id, robot_id, request_id, position{x,y}, channel

import json
import uuid
import time
from http.client import HTTPException
from typing import Optional
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

from strategy import make_strategy, State, Action, Vec

BASE_URL = "http://127.0.0.1:2026"
ARENA_ID = "default"


class HTTPError_(Exception):
    pass


def _post(base_url: str, path: str, payload: dict,
          timeout: float = 10.0, deadline=None, before_attempt=None) -> dict:
    """发送 POST，解析 JSON。同时检查 HTTP 状态和 accepted。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        if before_attempt is not None:
            before_attempt()
        remaining = timeout if deadline is None else min(timeout, deadline - time.monotonic())
        if remaining <= 0:
            raise HTTPError_('现实运行时间已到，未发送新请求')
        try:
            with urlrequest.urlopen(req, timeout=remaining) as r:
                status = r.status
                text = r.read().decode("utf-8")
            break
        except HTTPError as e:
            status = e.code
            text = e.read().decode("utf-8", errors="replace")
            break
        except (URLError, TimeoutError, ConnectionError, HTTPException) as e:
            if attempt == 2:
                raise HTTPError_(f'同一请求重试失败，执行状态不确定: {e}') from e
            # req/body/request_id 始终复用，避免重复移动和计时。
            pause = 0.2 * (attempt + 1)
            if deadline is not None:
                pause = min(pause, max(0, deadline - time.monotonic()))
            time.sleep(pause)
    if status != 200:
        raise HTTPError_(f"HTTP {status}: {text}")
    resp = json.loads(text)
    if not resp.get("accepted", False):
        raise HTTPError_(f"accepted=false: {resp}")
    return resp


class SimulatorClient:
    """对真模拟器的薄封装。"""

    def __init__(self, base_url: str, robot_id: str, log_path=None):
        self.base_url = base_url
        self.robot_id = robot_id
        self._seq = 0
        self.deadline = None
        self.log_path = log_path

    def set_deadline(self, deadline):
        self.deadline = deadline

    def _send(self, path, payload):
        record = {'path': path, 'request': payload}
        try:
            response = _post(self.base_url, path, payload, deadline=self.deadline)
            record['response'] = response
            return response
        except Exception as exc:
            record['error'] = str(exc)
            raise
        finally:
            if self.log_path:
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')

    def _req_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}-{uuid.uuid4().hex[:6]}"

    def enter(self) -> dict:
        payload = {
            "arena_id": ARENA_ID,
            "robot_id": self.robot_id,
            "request_id": self._req_id("enter"),
        }
        return self._send('/enter', payload)

    def measure(self, x: float, y: float, channel: int) -> dict:
        payload = {
            "arena_id": ARENA_ID,
            "robot_id": self.robot_id,
            "request_id": self._req_id("m"),
            "position": {"x": float(x), "y": float(y)},
            "channel": int(channel),
        }
        return self._send('/measure', payload)

    def clear(self, x: float, y: float, channel: int) -> dict:
        payload = {
            "arena_id": ARENA_ID,
            "robot_id": self.robot_id,
            "request_id": self._req_id("c"),
            "position": {"x": float(x), "y": float(y)},
            "channel": int(channel),
        }
        return self._send('/clear', payload)

    def exit(self) -> dict:
        payload = {
            "arena_id": ARENA_ID,
            "robot_id": self.robot_id,
            "request_id": self._req_id("exit"),
        }
        return self._send('/exit', payload)


# ============================================================
# 通用驱动器：策略 + 任意 Simulator-like 对象
# ============================================================
def run_with_sim(strategy_name: str, sim, max_steps: int = 5000) -> dict:
    """在任意 Simulator-like 对象上跑完一局。"""
    from robot_iter import run_with_sim_strategy
    if strategy_name in ('AdaptiveP4', 'p4'):
        from strategy_p4 import AdaptiveP4
        return run_with_sim_strategy(AdaptiveP4(), sim, max_steps)
    if strategy_name in ('AdaptiveV8', 'v8'):
        from strategy_v8 import AdaptiveV8
        return run_with_sim_strategy(AdaptiveV8(), sim, max_steps)
    if strategy_name in ('HybridV7', 'v7'):
        from strategy_v7 import HybridV7
        return run_with_sim_strategy(HybridV7(), sim, max_steps)
    strategy = make_strategy(strategy_name)
    return run_with_sim_strategy(strategy, sim, max_steps)


# 薄包装：跑真模拟器
def run(strategy_name: str, robot_id: str,
        base_url: str = BASE_URL, max_steps: int = 5000, log_path=None) -> dict:
    cli = SimulatorClient(base_url, robot_id, log_path=log_path)
    return run_with_sim(strategy_name, cli, max_steps=max_steps)


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    from datetime import datetime
    parser = argparse.ArgumentParser(description='在已手动启动的模拟器测试中运行策略')
    parser.add_argument('strategy', nargs='?', default='AdaptiveV8')
    parser.add_argument('robot_id', help='模拟器当前登录参赛队号')
    parser.add_argument('--base-url', default=BASE_URL)
    parser.add_argument('--log')
    args = parser.parse_args()
    path = Path(args.log) if args.log else Path(__file__).parent / 'results' / (
        'live_v8_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    out = run(args.strategy, args.robot_id, args.base_url, log_path=str(path))
    out.pop('log', None)
    print(json.dumps(out, indent=2, ensure_ascii=False, allow_nan=False))
    print(f'逐动作记录: {path.resolve()}')
