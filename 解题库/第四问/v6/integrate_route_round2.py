"""Apply the completed route-round selection to practice only, preserving rollback files."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def main():
    selection = json.loads((HERE / 'route_round2/selection.json').read_text(encoding='utf-8'))
    if not selection['evidence_complete'] or not selection['all_runs_accepted']:
        raise RuntimeError('Final evidence is not accepted')
    policies = {'RouteProbeP4': ('strategy_route_probe', 'RouteProbeP4_zero_detour'),
                'RouteAwareP4': ('strategy_route', 'RouteAwareP4_joint21'),
                'HuntP4': ('strategy_hunt', 'HuntP4_compact21')}
    chosen = selection['selected_variant']
    module, name = policies[chosen]
    checksum = hashlib.sha256((HERE / (module + '.py')).read_bytes()).hexdigest()
    if checksum != selection['selected_sha256']:
        raise RuntimeError('Selection source changed after validation')
    candidate_file = REPO / '解题库/演练调试/candidates.py'
    before = candidate_file.read_text(encoding='utf-8')
    old = '    if problem==4:\n        from strategy_hunt import HuntP4\n        return HuntP4()'
    new = f'    if problem==4:\n        from {module} import {chosen}\n        return {chosen}()'
    if old not in before:
        raise RuntimeError('Practice candidate differs from the expected preserved Hunt baseline')
    paths = [candidate_file, REPO / 'tools/p4_practice_deployment.json',
             REPO / 'README.md', REPO / '解题库/演练调试/README.md',
             REPO / '第四问_一键接入演练.cmd']
    backup = HERE / 'route_round2/integration_before_route2'
    backup.mkdir(exist_ok=False)
    inventory = {}
    for path in paths:
        relative = path.relative_to(REPO)
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        target.write_bytes(data)
        inventory[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    (backup / 'hashes.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    candidate_file.write_text(before.replace(old, new, 1), encoding='utf-8')
    prior = json.loads((REPO / 'tools/p4_practice_deployment.json').read_text(encoding='utf-8-sig'))
    record = {'updated_at': datetime.now(timezone.utc).isoformat(), 'mode': 'practice', 'problem': 4,
              'actual_class': chosen, 'name': name, 'source': f'解题库/第四问/v6/{module}.py',
              'sha256': checksum, 'previous_practice': 'HuntP4', 'previous_sha256': prior['sha256'],
              'baseline': 'FastP4', 'formal_entry': prior['formal_entry'], 'formal_run_started': False,
              'evaluation_reference': '解题库/第四问/v6/route_round2/selection.json',
              'combined_mean_T_per_N': selection['combined_mean_T_per_N'],
              'combined_reference_mean_T_per_N': selection['combined_reference_mean_T_per_N'],
              'overall_improvement_percent': selection['overall_improvement_percent'],
              'goal_300_400_s_per_source_achieved': False,
              'iteration_stopped_at_user_request': True,
              'decision': 'User requested incorporating overall improvements, then stopping this wave and updating scripts. Both fresh stages passed; no further tuning or formal run.'}
    import sys
    sys.path.insert(0, str(HERE))
    from route_round2_experiment import make
    strategy = make(chosen)
    record['parameters'] = {k: v for k, v in strategy.diagnostics().items() if isinstance(v, (bool, int, float, str))}
    payload = json.dumps(record, ensure_ascii=False, indent=2) + '\n'
    (REPO / 'tools/p4_practice_deployment.json').write_text(payload, encoding='utf-8')
    (HERE / 'INTEGRATION_ROUTE_RECORD.json').write_text(payload, encoding='utf-8')
    tn = selection['combined_mean_T_per_N']
    previous = selection['combined_reference_mean_T_per_N']
    gain = selection['overall_improvement_percent']
    note = (f'当前第四问一键演练已接入 `{chosen}()`，运行名 `{name}`。本轮新56场确认和112场半径边界场景全部全清、正常停止；'
            f'合并平均T/N由上一版HuntP4的{previous:.2f}降至{tn:.2f}秒/源，整体改善{gain:.2f}%。'
            '旧版HuntP4、FinishP4和FastP4保留，正式入口仍为FastP4，未启动正式测试。'
            '本轮到此停止，尚未整体达到300—400秒/源。证据见 `解题库/第四问/v6/ROUTE_ROUND2_REPORT.md`。')
    root_readme = REPO / 'README.md'
    lines = root_readme.read_text(encoding='utf-8').splitlines()
    lines = [('- ' + note) if line.startswith('- 当前第四问演练策略：') else line for line in lines]
    root_readme.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    practice_readme = REPO / '解题库/演练调试/README.md'
    text = practice_readme.read_text(encoding='utf-8')
    lines = text.splitlines()
    lines[2] = note + ' 下文旧策略描述为历史记录。'
    text = '\n'.join(lines) + '\n'
    text = text.replace('`第四问/v6/strategy_hunt.py:HuntP4`', f'`第四问/v6/{module}.py:{chosen}`')
    practice_readme.write_text(text, encoding='utf-8')
    wrapper = REPO / '第四问_一键接入演练.cmd'
    text = wrapper.read_text(encoding='utf-8')
    text = text.replace('chcp 65001 >nul\n', 'chcp 65001 >nul\necho 第四问演练接入：启动时将打印实际策略、来源和SHA256。\n', 1)
    wrapper.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
    # Only this new offline runner changes its default; the old Hunt runner is preserved.
    local_runner = HERE / 'run_route_local.py'
    text = local_runner.read_text(encoding='utf-8').replace("default='RouteProbeP4'", f"default='{chosen}'")
    local_runner.write_text(text, encoding='utf-8')
    print(payload)


if __name__ == '__main__':
    main()
