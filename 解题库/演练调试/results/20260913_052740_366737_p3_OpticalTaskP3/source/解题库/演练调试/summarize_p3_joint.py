"""Aggregate frozen paired offline evidence; never contacts the simulator."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent / 'results'
LABELS = ('p3_joint_dev01', 'p3_joint_dev02', 'p3_joint_holdout01',
          'p3_joint_probe_holdout', 'p3_joint_min', 'p3_joint_max', 'p3_probe_confirmation')


def stats(rows):
    return dict(n=len(rows), full_clear=sum(r['full_clear'] for r in rows),
                mean_virtual_s=statistics.mean(r['virtual_time_s'] for r in rows),
                mean_wall_s=statistics.mean(r['wall_s'] for r in rows),
                max_virtual_s=max(r['virtual_time_s'] for r in rows),
                total_measures=sum(r['measure_count'] for r in rows),
                total_clear_failures=sum(r['clear_fail_count'] for r in rows),
                mean_move_m=5*statistics.mean(r['time_breakdown']['move_time_s'] for r in rows))


def compare(old, new):
    a = {(r['seed'], r['N'], r['error_mode']): r for r in old}
    b = {(r['seed'], r['N'], r['error_mode']): r for r in new}
    assert len(a) == len(old) and len(b) == len(new) and a.keys() == b.keys()
    savings = [a[k]['virtual_time_s']-b[k]['virtual_time_s'] for k in sorted(a)]
    before, after = stats(old), stats(new)
    return dict(old=before, new=after, mean_saved_s=statistics.mean(savings),
                percent_saved=100*(1-after['mean_virtual_s']/before['mean_virtual_s']),
                standard_error_s=statistics.stdev(savings)/len(savings)**.5,
                better=sum(x>.001 for x in savings), worse=sum(x<-.001 for x in savings),
                same=sum(abs(x)<=.001 for x in savings),
                maximum_saved_s=max(savings), maximum_regression_s=-min(savings))


def main():
    reports, inputs = {}, {}
    for label in LABELS:
        file = ROOT / label / 'report.json'
        report = json.loads(file.read_text(encoding='utf-8'))
        assert report['exit_code'] == 0 and report['sources_unchanged']
        reports[label] = report
        inputs[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    code_key = next(k for k in reports['p3_joint_holdout01']['code_sha256'] if k.endswith('strategy_joint.py'))
    # Dev01 predates the probe planner. Its older code remains part of the ablation evidence.
    frozen_labels = [label for label in LABELS if label not in ('p3_joint_dev01',)]
    assert len({reports[label]['code_sha256'][code_key] for label in frozen_labels}) == 1
    main_rows = reports['p3_joint_holdout01']['records'] + reports['p3_joint_probe_holdout']['records']
    confirmation = reports['p3_probe_confirmation']['records']
    common = main_rows + confirmation
    select = lambda rows, variant: [r for r in rows if r['variant'] == variant]
    stress = reports['p3_joint_min']['records'] + reports['p3_joint_max']['records']
    selected_all = select(common+stress, 'probe_plan')
    previous_all = select(common+stress, 'residual')
    result = dict(created=datetime.now(timezone.utc).isoformat(), input_sha256=inputs,
                  policy_code_history={label: reports[label]['code_sha256'][code_key] for label in LABELS},
                  policy_code_sha256=reports['p3_joint_holdout01']['code_sha256'][code_key],
                  evaluation='offline_only_not_official_simulator',
                  total_executions=sum(len(r['records']) for r in reports.values()),
                  current_vs_first_one_click=compare(select(common, 'scan'), select(common, 'probe_plan')),
                  current_vs_previous=compare(select(common, 'residual'), select(common, 'probe_plan')),
                  current_vs_initial_baseline_56=compare(select(main_rows, 'baseline'), select(main_rows, 'probe_plan')),
                  selected_all_independent=compare(previous_all, selected_all),
                  confirmation=compare(select(confirmation, 'residual'), select(confirmation, 'probe_plan')),
                  rejected_joint=compare(select(main_rows, 'residual'), select(main_rows, 'joint')),
                  rejected_plan_joint=compare(select(main_rows, 'residual'), select(main_rows, 'plan_joint')))
    folder = ROOT / 'p3_joint_comparison'
    folder.mkdir(exist_ok=False)
    (folder / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
