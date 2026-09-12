"""连接用户已经启动的官方演练；每轮保存实际策略、源码和动作日志。"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parent
RUNTIME_FILES = ('run_v10.py', 'strategy_v10.py', 'route_search.py',
                 'strategy_v8.py', 'strategy.py', 'problem1_v4_inline.py',
                 'robot.py', 'robot_iter.py')


def main():
    parser = argparse.ArgumentParser(description='第三问路线专项版，连接已启动的官方演练')
    parser.add_argument('--robot-id', help='模拟器当前登录的参赛队号')
    parser.add_argument('--base-url', default='http://127.0.0.1:2026')
    parser.add_argument('--strategy', choices=('v10', 'v8'), default='v8',
                        help='默认保留已通过官方单局验证的 v8；v10 为路线候选')
    parser.add_argument('--check', action='store_true', help='显示策略和版本，不连接模拟器')
    args = parser.parse_args()
    from strategy_v10 import make_strategy
    from strategy_v8 import AdaptiveV8
    strategy = make_strategy() if args.strategy == 'v10' else AdaptiveV8()
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in RUNTIME_FILES}
    metadata = dict(strategy=strategy.name, entry='run_v10.py',
                    python=platform.python_version(), code_sha256=hashes)
    print(json.dumps(metadata, indent=2, ensure_ascii=False), flush=True)
    if args.check:
        return
    if not args.robot_id:
        parser.error('连接演练需要 --robot-id；检查版本可使用 --check')
    from robot import SimulatorClient
    from robot_iter import run_with_sim_strategy
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = ROOT / 'results' / 'official_runs' / f'{stamp}_{strategy.name}'
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'version.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    snapshots = folder / 'source'
    snapshots.mkdir()
    for name in RUNTIME_FILES:
        (snapshots / name).write_bytes((ROOT / name).read_bytes())
    client = SimulatorClient(args.base_url, args.robot_id, str(folder / 'actions.jsonl'))
    try:
        result = run_with_sim_strategy(strategy, client)
        result.pop('log', None)
        result['strategy'] = strategy.name
        result['distance_m'] = result['time_breakdown']['move_time_s'] * 5
        (folder / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False,
                                                      allow_nan=False), encoding='utf-8')
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    except Exception as exc:
        (folder / 'error.txt').write_text(f'{type(exc).__name__}: {exc}', encoding='utf-8')
        raise
    finally:
        print(f'本轮实际代码与逐动作记录：{folder}', flush=True)


if __name__ == '__main__':
    main()
