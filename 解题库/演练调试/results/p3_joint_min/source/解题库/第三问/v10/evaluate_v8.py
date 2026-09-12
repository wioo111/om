# -*- coding: utf-8 -*-
"""可复现的独立评估：只在一局结束后读取模拟器真值核对清除率。"""

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from mock_simulator import MockSimulator
from robot_iter import run_with_sim_strategy
from strategy_v8 import AdaptiveV8
from strategy_v7 import HybridV7

HERE = Path(__file__).resolve().parent
FACTORIES = {'v8': AdaptiveV8, 'v7': HybridV7}


def summarize(records):
    if not records:
        return {}
    times = [r['avg_time_per_cleared'] for r in records
             if r['avg_time_per_cleared'] is not None]
    ordered = sorted(times)
    n = len(times)
    mean = statistics.mean(times) if n else None
    std = statistics.stdev(times) if n > 1 else 0.0 if n else None
    margin = 1.96 * std / math.sqrt(n) if n else None
    return dict(
        rounds=len(records), zero_clear_rounds=len(records) - n,
        errors=sum(r.get('error') is not None for r in records),
        cleared_mean=statistics.mean(r['cleared'] for r in records),
        clear_rate_mean=statistics.mean(r['clear_rate'] for r in records),
        full_clear_rate=statistics.mean(r['cleared'] == r['N'] for r in records),
        avg_time_per_cleared_mean=mean,
        avg_time_per_cleared_weighted=(sum(r['virtual_time_s'] for r in records)
                                     / sum(r['cleared'] for r in records)
                                     if sum(r['cleared'] for r in records) else None),
        avg_time_median=statistics.median(times) if n else None,
        avg_time_std=std,
        mean_ci95_normal=[mean - margin, mean + margin] if n else None,
        avg_time_p90=ordered[max(0, math.ceil(n * .90) - 1)] if n else None,
        avg_time_p95=ordered[max(0, math.ceil(n * .95) - 1)] if n else None,
        avg_time_min=min(times) if n else None,
        avg_time_max=max(times) if n else None,
        fraction_180_to_220=statistics.mean(
            r['avg_time_per_cleared'] is not None
            and 180 <= r['avg_time_per_cleared'] <= 220 for r in records),
        measure_count_mean=statistics.mean(r['measure_count'] for r in records),
        clear_fail_count=sum(r.get('clear_fail_count', 0) for r in records),
        runtime_mean_s=statistics.mean(r.get('runtime_s', 0) for r in records),
    )


def run_one(seed, name='v8', error_mode='fixed', receive_radius=None, N=None):
    kwargs = {'seed': seed, 'error_mode': error_mode, 'N': N}
    if receive_radius is not None:
        kwargs['R_eff_range'] = (receive_radius, receive_radius)
    sim = MockSimulator(**kwargs)
    strategy = FACTORIES[name]()
    error = None
    try:
        result = run_with_sim_strategy(strategy, sim)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        result = sim.stats()
        result['log'] = sim.log
        result['stop_reason'] = 'error'
        result['coverage_complete'] = False
    # 真值只用于赛后计分，策略没有 sim 参数。
    result.pop('sources_truth', None)
    if result.get('avg_time_per_cleared') is not None:
        if not math.isfinite(result['avg_time_per_cleared']):
            result['avg_time_per_cleared'] = None
    if not error and result.get('time_breakdown'):
        if abs(sum(result['time_breakdown'].values()) - result['virtual_time_s']) > 1e-6:
            error = '计时分解与模拟器总时间不一致'
    if result.get('coverage_complete') and result['cleared'] != result['N']:
        error = '策略宣告搜索覆盖完成，但真值仍有未清除源'
    result.update(seed=seed, strategy=name, error_mode=error_mode, error=error)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=30)
    # 与开发阶段使用的 42/2024/12345、90000..90023 不重叠。
    parser.add_argument('--seeds', default='1410001,1510007,1610011')
    parser.add_argument('--strategy', choices=FACTORIES, default='v8')
    parser.add_argument('--compare-v7', action='store_true')
    parser.add_argument('--stress', action='store_true')
    parser.add_argument('--output', default='iter_v8')
    args = parser.parse_args()
    bases = [int(v.strip()) for v in args.seeds.split(',') if v.strip()]
    seeds = [base + 7 * k for base in bases for k in range(args.rounds)]
    if args.rounds < 1 or not bases or len(set(seeds)) != len(seeds):
        parser.error('局数必须为正，各组种子不能重叠')
    if Path(args.output).name != args.output:
        parser.error('--output 只接受文件名，不接受目录')
    out_dir = HERE / 'results'
    out_dir.mkdir(exist_ok=True)
    records, comparison, stress = [], [], []
    worst = None
    for i, seed in enumerate(seeds):
        row = run_one(seed, args.strategy)
        trace = row.pop('log', [])
        row['seed_base'] = bases[i // args.rounds]
        records.append(row)
        t = row['avg_time_per_cleared']
        if t is not None and (worst is None or t > worst['avg_time_per_cleared']):
            worst = {**row, 'log': trace}
        if args.compare_v7:
            baseline = run_one(seed, 'v7')
            baseline.pop('log', None)
            comparison.append(baseline)
        if (i + 1) % args.rounds == 0:
            group = summarize(records[-args.rounds:])
            print(json.dumps({'seed_base': row['seed_base'], **group},
                             ensure_ascii=False, allow_nan=False), flush=True)
    if args.stress:
        for mode in ('fixed', 'bias', 'smooth', 'edge'):
            for count in (10, 13, 16):
                for radius in (1000., 1500.):
                    seed = 1200000 + len(stress) * 17
                    row = run_one(seed, args.strategy, mode, radius, count)
                    row.pop('log', None)
                    row['receive_radius'] = radius
                    stress.append(row)
        print('stress', json.dumps(summarize(stress), ensure_ascii=False), flush=True)
    hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
              for name in ('strategy_v8.py', 'mock_simulator.py', 'robot_iter.py',
                           'robot.py', 'evaluate_v8.py', 'problem1_v4_inline.py')}
    summary = summarize(records)
    groups = {str(base): summarize([r for r in records if r['seed_base'] == base])
              for base in bases}
    mean = summary['avg_time_per_cleared_mean']
    # “左右”显式采用 ±10%；单局尾部另行报告，不能只用均值声称稳定。
    goal_met = (mean is not None and 180 <= mean <= 220
                and summary['full_clear_rate'] == 1 and not summary['errors']
                and all(180 <= s['avg_time_per_cleared_mean'] <= 220 for s in groups.values()))
    report = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                  evaluation='offline_mock_not_official_simulator',
                  source_distribution='uniform_disk_1800m; N uniform_integer_10_to_16; R uniform_1000_to_1500',
                  timing='virtual_time_s / successful_clear_count; mean over all rounds; zero-clear counted separately',
                  goal_mean_s=200, goal_band_s=[180, 220], goal_met=goal_met,
                  rounds_per_seed=args.rounds, seed_bases=bases, code_sha256=hashes,
                  summary=summary, by_seed_base=groups,
                  by_N={str(n): summarize([r for r in records if r['N'] == n])
                        for n in range(10, 17)},
                  v7_summary=summarize(comparison), stress_summary=summarize(stress),
                  records=records, v7_records=comparison, stress_records=stress)
    path = out_dir / f'{args.output}.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    if worst:
        (out_dir / f'{args.output}_worst_trace.json').write_text(
            json.dumps(worst, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    def fmt(v):
        return f'{v:.1f}' if v is not None else '无有效值'
    lines = ['# 第三问 v8 独立脱机验证', '',
             f'目标：200 s/源，约定范围 180–220 s/源；本次目标达成：{goal_met}。',
             '全部时间包含搜索、移动、检测、切频、清除失败及收尾，不按已知真值提前退出。', '',
             f'总局数：{len(records)}；全清率：{summary["full_clear_rate"]:.1%}；异常：{summary["errors"]}；零清除局：{summary["zero_clear_rounds"]}。',
             f'每局单源时间的平均值：{fmt(mean)} s；标准差：{fmt(summary["avg_time_std"])} s；P95：{fmt(summary["avg_time_p95"])} s。',
             f'范围：{fmt(summary["avg_time_min"])}–{fmt(summary["avg_time_max"])} s；落在 180–220 s 的局数占比：{summary["fraction_180_to_220"]:.1%}。', '',
             '| 种子组 | 局数 | 全清率 | 平均单源时间/s | P95/s |',
             '|---|---:|---:|---:|---:|']
    for base, s in groups.items():
        lines.append(f'| {base} | {s["rounds"]} | {s["full_clear_rate"]:.1%} | {fmt(s["avg_time_per_cleared_mean"])} | {fmt(s["avg_time_p95"])} |')
    lines.extend(['', '这些结果来自本地模型，不能代替官方模拟器演练或正式测试。',
                  '同点误差固定且响应保留两位小数；压力场景包括最小/最大接收半径、固定偏差、连续空间偏差及误差端点。',
                  f'原始逐局数据与源文件哈希：`{path.name}`；最慢场景动作记录：`{args.output}_worst_trace.json`。'])
    if stress:
        s = summarize(stress)
        lines.extend(['', f'压力场景 {len(stress)} 局：全清率 {s["full_clear_rate"]:.1%}，异常 {s["errors"]}，平均单源时间 {fmt(s["avg_time_per_cleared_mean"])} s。'])
    path.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'summary': summary, 'goal_met': goal_met, 'output': str(path)},
                     ensure_ascii=False, allow_nan=False), flush=True)
    if (summary['errors'] or summary['full_clear_rate'] < 1
            or any(r['error'] or r['cleared'] != r['N'] for r in stress)):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
