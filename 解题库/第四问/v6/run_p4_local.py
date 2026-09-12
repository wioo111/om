# -*- coding: utf-8 -*-
"""问题4 v6 本地批量入口。

直接运行：
    python run_p4_local.py

默认对 dir_frac=0.25/0.5/0.75/1.0 各运行 3 个 seed，并打印每局要求的
核心字段，同时将完整结果保存到 results/p4_local_*.json。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from mock_simulator_p4 import P4MockSimulator
from robot_iter import run_with_sim_strategy
from strategy_p4 import AdaptiveP4


DEFAULT_SEEDS = (41001, 41007, 41013)
DEFAULT_DIR_FRACS = (0.25, 0.5, 0.75, 1.0)


def run_one(seed: int, dir_frac: float, n_sources=None,
            max_steps: int = 30000) -> dict:
    sim = P4MockSimulator(seed=seed, n_sources=n_sources, dir_frac=dir_frac)
    result = run_with_sim_strategy(AdaptiveP4(), sim, max_steps=max_steps)
    result['seed'] = seed
    result['dir_frac'] = dir_frac
    result['N'] = sim.N
    result['directional_count'] = len(sim.dir_channels)
    result['clear_ratio'] = result['cleared'] / sim.N if sim.N else 1.0
    return result


def _compact(row: dict) -> dict:
    keys = (
        'seed', 'N', 'directional_count', 'cleared', 'clear_ratio',
        'virtual_time_s', 'avg_time_per_cleared', 'measure_count',
        'clear_fail_count', 'stop_reason',
    )
    return {key: row.get(key) for key in keys}


def main() -> int:
    parser = argparse.ArgumentParser(description='问题4 v6 本地批量验证')
    parser.add_argument('--seeds', default=','.join(map(str, DEFAULT_SEEDS)),
                        help='逗号分隔的 seed，默认每档 3 个')
    parser.add_argument('--dir-fracs', default=','.join(map(str, DEFAULT_DIR_FRACS)),
                        help='逗号分隔的定向源比例')
    parser.add_argument('--n-sources', type=int, default=None,
                        help='固定源数量；默认按 mock 的 10..16 随机')
    parser.add_argument('--max-steps', type=int, default=30000)
    parser.add_argument('--output', default=None,
                        help='结果 JSON 路径；默认写入 results/')
    args = parser.parse_args()

    try:
        seeds = [int(item.strip()) for item in args.seeds.split(',') if item.strip()]
        dir_fracs = [float(item.strip()) for item in args.dir_fracs.split(',')
                     if item.strip()]
    except ValueError as exc:
        parser.error(f'种子或 dir_frac 参数非法: {exc}')
        return 2
    if not seeds or not dir_fracs:
        parser.error('seeds 和 dir-fracs 不能为空')
        return 2
    if any(not 0.0 <= frac <= 1.0 for frac in dir_fracs):
        parser.error('dir_frac 必须在 0 和 1 之间')
        return 2

    rows = []
    errors = []
    for dir_frac in dir_fracs:
        print(f'=== dir_frac={dir_frac:g} ===', flush=True)
        for seed in seeds:
            try:
                row = run_one(seed, dir_frac, args.n_sources, args.max_steps)
            except Exception as exc:  # 批量验证保留失败局，继续跑其它 seed
                row = {
                    'seed': seed,
                    'N': None,
                    'directional_count': None,
                    'cleared': 0,
                    'clear_ratio': 0.0,
                    'virtual_time_s': None,
                    'avg_time_per_cleared': None,
                    'measure_count': None,
                    'clear_fail_count': None,
                    'stop_reason': 'error',
                    'dir_frac': dir_frac,
                    'error': f'{type(exc).__name__}: {exc}',
                }
                errors.append(row)
            rows.append(row)
            print(json.dumps({**_compact(row), 'dir_frac': dir_frac,
                              **({'error': row['error']} if row.get('error') else {})},
                             ensure_ascii=False, allow_nan=False), flush=True)

    if args.output:
        output = Path(args.output)
    else:
        output_dir = Path(__file__).parent / 'results'
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output = output_dir / f'p4_local_{stamp}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'strategy': 'AdaptiveP4',
        'evaluation': 'offline_mock',
        'seeds': seeds,
        'dir_fracs': dir_fracs,
        'records': rows,
        'compact_records': [_compact(row) for row in rows],
        'all_full_clear': bool(rows) and all(
            row.get('clear_ratio') == 1.0 and row.get('stop_reason')
            == 'all_channels_cleared_or_covered' for row in rows
        ) and not errors,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                                 allow_nan=False), encoding='utf-8')
    print(f'结果文件: {output.resolve()}', flush=True)
    print(json.dumps({'all_full_clear': payload['all_full_clear'],
                      'rounds': len(rows), 'errors': len(errors)},
                     ensure_ascii=False), flush=True)
    return 0 if payload['all_full_clear'] else 1


if __name__ == '__main__':
    sys.exit(main())
