"""P3 scene-paired, N-stratified evaluation. Failure rates precede speed."""
import math
import random
import statistics as st


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    x = (len(values) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    return values[lo] + (values[hi] - values[lo]) * (x - lo)


def average(values):
    values = [v for v in values if v is not None]
    return st.mean(values) if values else None


def scene_key(row):
    return (row.get('evaluation_model', 'uniform'), row.get('scene_id', row.get('seed')),
            row['N'], row.get('error_mode'))


def stats(rows):
    good = [r for r in rows if r['full_clear']]
    times = [r['virtual_time_s'] for r in good]
    return dict(cases=len(rows), full_clear=len(good), failed=len(rows)-len(good),
                full_clear_rate=len(good)/len(rows) if rows else None,
                mean_completed_virtual_s=average(times),
                mean_completed_per_source_s=average(r['virtual_time_s']/r['N'] for r in good),
                p95_completed_virtual_s=quantile(times, .95),
                worst_completed_virtual_s=max(times) if times else None,
                mean_wall_s=average(r.get('wall_s', r.get('runtime_s')) for r in rows),
                mean_measure_count=average(r.get('measure_count') for r in rows),
                clear_failures=sum(r.get('clear_fail_count', 0) for r in rows),
                mean_post_last_clear_s=average(r.get('post_last_clear_s') for r in good),
                mean_move_m=average(r.get('time_breakdown', {}).get('move_time_s', 0)*5 for r in good))


def paired(old, new):
    def index(rows):
        result = {scene_key(r): r for r in rows}
        if len(result) != len(rows):
            raise ValueError('Duplicate scene within a variant')
        return result
    a, b = index(old), index(new)
    if a.keys() != b.keys():
        raise ValueError('Unmatched scenes: refusing unpaired speed comparison')
    keys = sorted(a, key=str)
    complete = [k for k in keys if a[k]['full_clear'] and b[k]['full_clear']]
    savings = [a[k]['virtual_time_s']-b[k]['virtual_time_s'] for k in complete]
    rng = random.Random(20260913)
    boot = [st.mean(rng.choices(savings, k=len(savings))) for _ in range(1200)] if savings else []
    old_mean = average(a[k]['virtual_time_s'] for k in complete)
    saved = average(savings)
    return dict(paired_scenes=len(keys), paired_full_clear=len(complete),
                omitted_speed_pairs=len(keys)-len(complete),
                old_failures=sum(not r['full_clear'] for r in old),
                new_failures=sum(not r['full_clear'] for r in new),
                mean_saved_s=saved, saved_percent=100*saved/old_mean if old_mean else None,
                bootstrap_mean_saved_95_interval_s=[quantile(boot, .025), quantile(boot, .975)],
                interval_note='Scene bootstrap, descriptive; small N groups and multiple comparisons remain uncertain.',
                better=sum(v > .001 for v in savings), worse=sum(v < -.001 for v in savings),
                same=sum(abs(v) <= .001 for v in savings))


def stratified(rows, reference):
    variants = sorted({r['variant'] for r in rows})
    if reference not in variants:
        raise ValueError('Reference variant missing')
    if any(r['N'] not in range(10, 17) for r in rows):
        raise ValueError('P3 N must be 10..16')
    groups = {f'N={n}': {n} for n in range(10, 17)}
    groups.update({'N=10-15': set(range(10, 16)), 'overall': set(range(10, 17))})
    output = {}
    for name, ns in groups.items():
        selected = {v: [r for r in rows if r['variant'] == v and r['N'] in ns] for v in variants}
        output[name] = dict(variants={v: stats(rr) for v, rr in selected.items()},
                            vs_reference={v: paired(selected[reference], rr)
                                          for v, rr in selected.items() if v != reference})
    macro = {v: average(output[f'N={n}']['variants'][v]['mean_completed_virtual_s']
                        for n in range(10, 17)) for v in variants}
    return dict(reference=reference, groups=output, equal_N_macro_completed_virtual_s=macro,
                interpretation='Full-clear rate first. Speed conditional on completion, not a reward for early exit. '
                               'N is evaluation metadata, never a policy input. Overall is case-weighted; macro is equal-N.')


def markdown_table(report):
    variants = list(report['groups']['overall']['variants'])
    lines = ['| 分组 | 算法 | 全清/场数 | 完成总耗时均值/秒 | 单源均值/秒 | P95/秒 | 相对基线节省/秒（95%区间） |',
             '|---|---|---:|---:|---:|---:|---|']
    fmt = lambda x: '—' if x is None else f'{x:.2f}'
    for group, value in report['groups'].items():
        for variant in variants:
            s = value['variants'][variant]
            p = value['vs_reference'].get(variant)
            delta = '基线' if p is None else (fmt(p['mean_saved_s']) + ' [' + ', '.join(
                fmt(x) for x in p['bootstrap_mean_saved_95_interval_s']) + ']')
            lines.append(f"| {group} | {variant} | {s['full_clear']}/{s['cases']} | "
                         f"{fmt(s['mean_completed_virtual_s'])} | {fmt(s['mean_completed_per_source_s'])} | "
                         f"{fmt(s['p95_completed_virtual_s'])} | {delta} |")
    return '\n'.join(lines)
