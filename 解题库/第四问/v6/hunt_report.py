"""Build the P4 Hunt round report from saved evidence; never run a simulator.

Run only after the intended experiment reports have been written. Missing or
incomplete confirmation/boundary evidence produces a pending selection, not a
success claim. This script does not modify a launcher or strategy.
"""
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics


HERE=Path(__file__).resolve().parent
COST_KEYS=('move_time_s','switch_time_s','measure_time_s','clear_time_s')
# strategy.py loads this geometry implementation with spec_from_file_location,
# so it is a real runtime dependency that ordinary import AST traversal misses.
DYNAMIC_DEPENDENCIES=('problem1_v4_inline.py',)
DEVELOPMENT=(
    ('dev01','25站三角网与有限局部定位'),
    ('dev02_defer','延后局部定位，先推进发现'),
    ('dev03_rings','25站双环路线'),
    ('dev04_adapt','按真实覆盖证据调整发现过程'),
    ('dev05_insertion','局部任务插入扫描路线'),
    ('dev06_reroute','缩短剩余扫描路线'),
    ('dev07_stop_ready','定位区已有覆盖方案时停止重复检测'),
    ('dev08_compact','21站固定点集与连续发现证书'),
)
EXPECTED_LABELS=[label for label,_ in DEVELOPMENT]+['confirmation01','boundary01']


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scenario_key(scenario):
    return (scenario['seed'],scenario['N'],scenario['dir_frac'],scenario['error_mode'],tuple(scenario['reception_range']))


def _expected_specs(stage):
    if stage=='development':
        return [dict(seed=951000+i,N=10+i%7,dir_frac=(.25,.5,.75,1.)[i%4],
                     error_mode=('random','fixed','edge')[i%3],reception_range=[1000,1500]) for i in range(14)]
    grid=list(itertools.product(range(10,17),(.25,.5,.75,1.),('fixed','edge')))
    if stage=='confirmation':
        return [dict(seed=952000+i,N=n,dir_frac=f,error_mode=m,reception_range=[1000,1500])
                for i,(n,f,m) in enumerate(grid)]
    return [dict(seed=953000+100*j+i,N=n,dir_frac=f,error_mode=m,reception_range=[radius,radius])
            for j,radius in enumerate((1000,1500)) for i,(n,f,m) in enumerate(grid)]


def _local_dependencies(source,roots):
    """Resolve imports against the frozen folder, without importing strategy code."""
    pending=list(roots);found=set()
    while pending:
        name=pending.pop()
        if name in found:continue
        path=source/name
        if not path.is_file():continue
        found.add(name)
        tree=ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import):names=[alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module:names=[node.module.split('.')[0]]
            for module in names:
                dependency=module+'.py'
                if (source/dependency).is_file() and dependency not in found:pending.append(dependency)
    return sorted(found)


def _hash_evidence(folder,manifest,rows):
    recorded=manifest.get('code_sha256',{})
    source=folder/'source'
    sources=sorted({row.get('source','') for row in rows if row.get('source')})
    dependencies=sorted(set(_local_dependencies(source,sources+['mock_simulator_p4.py','robot_iter.py','cost_experiment.py']+list(DYNAMIC_DEPENDENCIES)))
                        |set(DYNAMIC_DEPENDENCIES))
    details={}
    for name in sorted(set(dependencies)|set(sources)):
        expected=recorded.get(name)
        snapshot=source/name
        current=HERE/name
        item=dict(manifest_sha256=expected or 'not_recorded',
                  frozen_sha256=_sha(snapshot) if snapshot.is_file() else 'missing',
                  current_sha256=_sha(current) if current.is_file() else 'missing')
        item['frozen_matches_manifest']=bool(expected and item['frozen_sha256']==expected)
        item['current_matches_manifest']=bool(expected and item['current_sha256']==expected)
        details[name]=item
    return dict(files=details,dependency_files=dependencies,
                frozen_verified=bool(details) and all(item['frozen_matches_manifest'] for item in details.values()),
                current_matches=bool(details) and all(item['current_matches_manifest'] for item in details.values()),
                actual_strategies={variant:sorted({(row.get('actual_class','unreported'),row.get('name','unreported'),row.get('source','unreported'))
                                                  for row in rows if row['variant']==variant})
                                   for variant in sorted({row['variant'] for row in rows})})


def _measured(row):
    return row.get('metrics_available',True) and all(
        isinstance(row.get(key),(int,float)) and math.isfinite(row[key])
        for key in ('T_per_N','virtual_time_s','distance_m','measure_count','clear_fail_count'))


def _p95(values):
    return sorted(values)[math.ceil(.95*len(values))-1]


def _metrics(rows):
    measured=[row for row in rows if _measured(row)]
    result=dict(rounds=len(rows),full_clear=sum(bool(row.get('full_clear')) for row in rows),
                normal_stop=sum(bool(row.get('normal_stop')) for row in rows),
                accepted=sum(bool(row.get('full_clear')) and bool(row.get('normal_stop')) for row in rows),
                metric_rounds=len(measured),missing_cost_rounds=len(rows)-len(measured),
                metric_population='all measured runs including failures; never successful runs only')
    if not measured:return result
    result.update(mean_T_per_N=statistics.mean(row['T_per_N'] for row in measured),
                  weighted_T_per_N=sum(row['virtual_time_s'] for row in measured)/sum(row['scenario']['N'] for row in measured),
                  mean_T=statistics.mean(row['virtual_time_s'] for row in measured),
                  total_T=sum(row['virtual_time_s'] for row in measured),
                  mean_distance_m=statistics.mean(row['distance_m'] for row in measured),
                  mean_measure=statistics.mean(row['measure_count'] for row in measured),
                  mean_clear_failures=statistics.mean(row['clear_fail_count'] for row in measured),
                  total_clear_failures=sum(row['clear_fail_count'] for row in measured),
                  p95_T_per_N=_p95([row['T_per_N'] for row in measured]),
                  p95_T=_p95([row['virtual_time_s'] for row in measured]),
                  worst_T_per_N=max(row['T_per_N'] for row in measured),
                  worst_T=max(row['virtual_time_s'] for row in measured),
                  mean_cost={key:sum(row['time_breakdown'][key] for row in measured)/len(measured) for key in COST_KEYS},
                  phases={phase:{key:sum(row.get('stage_costs',{}).get(phase,{}).get(key,0) for row in measured)/len(measured)
                                 for key in COST_KEYS}
                          for phase in sorted({phase for row in measured for phase in row.get('stage_costs',{})})},
                  triggers={key:sum(row.get('diagnostics',{}).get('triggers',{}).get(key,0) for row in measured)
                            for key in sorted({key for row in measured for key in row.get('diagnostics',{}).get('triggers',{})})},
                  by_N={str(n):dict(rounds=sum(row['scenario']['N']==n for row in measured),
                                    mean_T_per_N=statistics.mean(row['T_per_N'] for row in measured if row['scenario']['N']==n),
                                    worst_T_per_N=max(row['T_per_N'] for row in measured if row['scenario']['N']==n))
                        for n in sorted({row['scenario']['N'] for row in measured})})
    return result


def _compare(rows,variant,reference):
    candidate=[row for row in rows if row['variant']==variant]
    baseline={_scenario_key(row['scenario']):row for row in rows if row['variant']==reference}
    if not baseline:return dict(status='reference_not_run',reference=reference,paired_rounds=0)
    pairs=[(row,baseline[_scenario_key(row['scenario'])]) for row in candidate
           if _scenario_key(row['scenario']) in baseline and _measured(row) and _measured(baseline[_scenario_key(row['scenario'])])]
    if not pairs:return dict(status='no_measured_pairs',reference=reference,paired_rounds=0)
    changes=[dict(seed=row['scenario']['seed'],scenario=row['scenario'],
                  fraction=row['virtual_time_s']/base['virtual_time_s']-1,
                  delta_T=row['virtual_time_s']-base['virtual_time_s'],
                  candidate_accepted=bool(row.get('full_clear')) and bool(row.get('normal_stop')),
                  reference_accepted=bool(base.get('full_clear')) and bool(base.get('normal_stop')))
             for row,base in pairs]
    worst=max(changes,key=lambda row:row['fraction'])
    return dict(status='complete' if len(pairs)==len(candidate) else 'partial',reference=reference,paired_rounds=len(pairs),
                improvement=1-statistics.mean(row['T_per_N'] for row,_ in pairs)/statistics.mean(base['T_per_N'] for _,base in pairs),
                worst_regression_fraction=worst['fraction'],worst_seed=worst['seed'],
                p95_regression_fraction=_p95([row['fraction'] for row in changes]),
                by_N_worst={str(n):max(row['fraction'] for row in changes if row['scenario']['N']==n)
                            for n in sorted({row['scenario']['N'] for row in changes})},
                regressions=[row for row in changes if row['fraction']>1e-9])


def _load(folder):
    report_path=folder/'report.json'
    if not report_path.is_file():return dict(label=folder.name,status='report_missing',records=[])
    report=json.loads(report_path.read_text(encoding='utf-8'))
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    rows=report['records'];stage=manifest['stage']
    variants=manifest['variants'];scenarios=manifest['scenarios']
    expected={(_scenario_key(scenario),variant) for scenario in scenarios for variant in variants}
    actual=[(_scenario_key(row['scenario']),row['variant']) for row in rows]
    issues=[]
    if len(actual)!=len(set(actual)):issues.append('duplicate_run_records')
    if set(actual)!=expected:issues.append('incomplete_or_extra_records')
    if {_scenario_key(s) for s in scenarios}!={_scenario_key(s) for s in _expected_specs(stage)}:
        issues.append('scenario_grid_differs_from_preregistered_stage')
    if report.get('manifest')!=manifest:issues.append('report_manifest_differs_from_saved_manifest')
    metrics={variant:_metrics([row for row in rows if row['variant']==variant]) for variant in variants}
    comparisons={variant:{reference:_compare(rows,variant,reference) for reference in ('FastP4','FinishP4')}
                 for variant in variants}
    hashes=_hash_evidence(folder,manifest,rows)
    if not hashes['frozen_verified']:issues.append('frozen_source_hash_mismatch_or_missing')
    return dict(label=folder.name,stage=stage,status='complete' if not issues else 'invalid_evidence',issues=issues,
                manifest=manifest,records=rows,metrics=metrics,comparisons=comparisons,hash_evidence=hashes)


def _selection(stages):
    lookup={stage['label']:stage for stage in stages}
    required=[lookup.get(label,dict(label=label,status='report_missing')) for label in ('confirmation01','boundary01')]
    reasons=[]
    for stage in required:
        if stage['status']!='complete':reasons.append(stage['label']+':'+stage['status'])
        elif not stage['hash_evidence']['current_matches']:reasons.append(stage['label']+':current_code_differs_from_frozen_evidence')
    if reasons:return dict(status='pending_evidence',selected_variant='FinishP4',candidate='HuntP4',reasons=reasons,
                           report_generator_changed_deployment=False,target_status='not_proven',performance_rule='all clear and normal stop; overall improvement versus FinishP4; no additional 5% threshold')
    rows=[row for stage in required for row in stage['records']]
    candidate=[row for row in rows if row['variant']=='HuntP4']
    baseline=[row for row in rows if row['variant']=='FinishP4']
    expected_rounds=56+112
    metrics=_metrics(candidate);reference=_metrics(baseline);comparison=_compare(rows,'HuntP4','FinishP4')
    complete=len(candidate)==len(baseline)==expected_rounds and metrics['metric_rounds']==reference['metric_rounds']==expected_rounds
    correct=complete and metrics['accepted']==reference['accepted']==expected_rounds
    better=comparison.get('status')=='complete' and comparison.get('improvement',0)>0
    selected=correct and better
    mean=metrics.get('mean_T_per_N')
    target_met=correct and mean is not None and mean<=400
    result=dict(status='selected' if selected else 'retain_baseline',selected_variant='HuntP4' if selected else 'FinishP4',
                candidate='HuntP4',baseline='FinishP4',candidate_metrics=metrics,baseline_metrics=reference,
                comparison_vs_FinishP4=comparison,complete_evidence=complete,all_clear_and_normal=correct,
                overall_improvement=better,target_status='achieved' if target_met else 'not_achieved',
                target_definition='mean of scenario total virtual time divided by scenario N, across all 168 validation runs; upper target 400 s/source',
                target_range_s=[300,400],report_generator_changed_deployment=False,
                performance_rule='all clear and normal stop; overall improvement versus FinishP4; no additional 5% threshold',
                evidence_labels=['confirmation01','boundary01'])
    if metrics.get('by_N'):
        result['all_N_means_at_most_400']=all(value['mean_T_per_N']<=400 for value in metrics['by_N'].values())
    result['candidate_sha256']=required[0]['manifest']['code_sha256'].get('strategy_hunt.py','not_recorded')
    result['candidate_dependency_sha256']={name:item['manifest_sha256'] for name,item in required[0]['hash_evidence']['files'].items()}
    return result


def _practice_integration(selection):
    """Read the integration record without dispatching or importing a robot."""
    repo=HERE.parents[2]
    path=repo/'tools/p4_practice_deployment.json'
    if not path.is_file():return dict(status='integration_record_missing',live_practice_rerun='not_performed_after_integration')
    record=json.loads(path.read_text(encoding='utf-8-sig'))
    result={key:record[key] for key in ('mode','problem','actual_class','name','source','sha256','parameters','updated_at') if key in record}
    result.update(status='integration_record_read',record_source=str(path.relative_to(repo)),
                  live_practice_rerun='not_performed_after_integration',
                  evidence_scope='integration metadata plus current file hash; no claim of a post-integration simulator run')
    source=repo/record.get('source','')
    if source.is_file():
        result['current_source_sha256']=_sha(source)
        result['matches_current_source']=result['current_source_sha256']==record.get('sha256')
    else:result['matches_current_source']=False
    result['matches_verified_candidate']=bool(selection.get('candidate_sha256') and record.get('sha256')==selection['candidate_sha256'])
    return result


def _number(value,digits=2):
    return f'{value:.{digits}f}' if isinstance(value,(int,float)) else '未提供'


def _percent(value):
    return f'{value:+.2%}' if isinstance(value,(int,float)) else '未配对'


def _table(lines,headers,rows):
    lines.append('| '+' | '.join(headers)+' |')
    lines.append('| '+' | '.join('---' for _ in headers)+' |')
    lines.extend('| '+' | '.join(str(value).replace('|','\\|').replace('\n',' ') for value in row)+' |' for row in rows)
    lines.append('')


def _run_link(label,row):
    extension='.json' if _measured(row) else '.error.json'
    return f"[动作及成本](hunt_round/{label}/runs/{row['scenario']['seed']}_{row['variant']}{extension})"


def render(stages,selection):
    lines=['# 第四问 Hunt 有限迭代报告','',
           '本报告只读取冻结实验记录，不启动模拟器、不切换公共入口。FastP4 与此前已接入演练的 FinishP4 均保留。','']
    if selection['status']=='pending_evidence':
        lines+=['证据尚未齐全或当前代码与验证快照不一致，不能据此宣称完成验证、切换候选或达到速度目标。',
                '缺项：'+', '.join(selection['reasons'])+'。','']
    else:
        chosen=selection['selected_variant'];metrics=selection['candidate_metrics']
        lines+=[f"证据选型：**{chosen}**。确认集与边界集合计 HuntP4 {metrics['accepted']}/{metrics['rounds']} 场全清且正常停止，平均 T/N 为 **{_number(metrics.get('mean_T_per_N'))} 秒/源**。",'']
        if selection['target_status']=='achieved':
            wording='进入 300–400 秒/源目标区间' if metrics['mean_T_per_N']>=300 else '低于 300 秒/源，优于目标区间'
            lines+=[f'独立验证汇总均值已{wording}。这是全验证集均值，不表示每一场或每个 N 分组均达到该水平。','']
        else:lines+=['**300–400 秒/源目标尚未达到。** 整体改善和速度目标分别判断，不能以改善比例替代达标。','']
    lines+=['## 实验口径与独立性','',
            '开发阶段 dev01–dev08 反复使用同一组 14 场（seed 951000–951013）修错和固定方案，不能合并成 112 个独立场景。',
            'confirmation01 是本轮一次性使用的新 56 场：N=10…16、定向比例 0.25/0.5/0.75/1 与 fixed/edge 的笛卡尔积，半径范围 1000–1500 米。开发集另外包含 random。',
            'boundary01 使用另一组新种子，分别固定半径 1000 米和 1500 米，共 112 场。固定/边缘误差按同位置、频道复现，不因多测一次改变后续随机序列。',
            '通过必须同时全清且正常停止；step_limit 不算通过。成本均值纳入所有有实测成本的运行，包括失败和退步；缺少成本的外围异常单列，绝不补零，也不只平均成功样本。',
            '平均 T/N 指逐场 T/N 的算术均值；同时保留累计 T÷累计 N 的加权值。P95 使用排序后的 nearest-rank 第 ceil(0.95×场数) 项。最差退步为同场候选 T÷参照 T−1，负值表示最差配对仍然更快。',
            '选型遵循已授权的“正确性和正常停止优先，整体收益即可加入”；本轮不另设 5% 门槛。报告不会自动修改接入脚本。','',
            '## 从第三问借鉴了什么','',
            '只借鉴局部候选区的有限光学覆盖、把移动/检测/换频道/成功与失败清除全部计费的比较，以及延后有限局部定位以保留扫描进度的思路。第四问维持自己的发现证书和半平面物理规则；no_signal 不产生 1000 米空间排除，也不读取隐藏源数或真实半径。',
            '固定点集优化与连续几何证书独立于模拟场景。有限清除覆盖的是整个已证明外包的候选区，采样不承担覆盖保证；失败推进计划并保留排除信息。','',
            '## null 展示问题','',
            '原演练控制台把所有动作都读取为 clear_result，所以 enter/measure 显示 null。08:31 两局原始记录实际上有 direction+svd_deg 或 no_signal；这属于展示字段错误，不是检测数据丢失。',
            '现按端点显示真实 measure_result/clear_result，enter/exit 显示明确状态；no_signal/near 没有方位时省略 svd_deg，缺失必填字段明确提示。原始动作记录和第三问行为未改。真实 no_signal 仍然计入检测成本，不能通过修日志消除。','',
            '## 各开发阶段与验证阶段','']
    probe_counts=[f"{stage['label']} {stage['metrics']['HuntP4'].get('total_clear_failures','未提供')} 次"
                  for stage in stages if stage['label'] in ('confirmation01','boundary01')
                  and 'HuntP4' in stage.get('metrics',{})]
    if probe_counts:
        lines += ['HuntP4 的失败 clear：'+ '；'.join(probe_counts)+'。这些是有成本的有限光学试探未命中，每次失败清除的 3 秒及到达该点的移动均已计费；不等于整场失败。整场是否失败仍以最终全清和正常停止判定。','']
    notes=dict(DEVELOPMENT)
    for stage in stages:
        label=stage['label'];lines+=[f'### {label}'+('：'+notes[label] if label in notes else ''),'']
        if stage['status']=='report_missing':lines+=['报告尚未生成；本阶段不纳入完成或速度结论。',''];continue
        lines += [f"证据状态：{stage['status']}。完整原始汇总：[report.json](hunt_round/{label}/report.json)；冻结配置：[manifest.json](hunt_round/{label}/manifest.json)。",'']
        if stage['issues']:lines+=['证据问题：'+', '.join(stage['issues'])+'。','']
        _table(lines,['策略','场数','全清','正常停止','两项通过','平均T/N','平均总T','累计T','P95 T/N','P95 T','最差T/N'],
               [(variant,value['rounds'],value['full_clear'],value['normal_stop'],value['accepted'],_number(value.get('mean_T_per_N')),
                 _number(value.get('mean_T')),_number(value.get('total_T')),_number(value.get('p95_T_per_N')),
                 _number(value.get('p95_T')),_number(value.get('worst_T_per_N'))) for variant,value in stage['metrics'].items()])
        _table(lines,['策略','均移动距离m','均检测次数','均失败清除','失败清除总数','加权T/N','成本样本/全部','相对Fast改善','相对Finish改善','最差相对Finish耗时变化'],
               [(variant,_number(value.get('mean_distance_m')),_number(value.get('mean_measure')),_number(value.get('mean_clear_failures')),
                 value.get('total_clear_failures','未提供'),_number(value.get('weighted_T_per_N')),f"{value['metric_rounds']}/{value['rounds']}",
                 _percent(stage['comparisons'][variant]['FastP4'].get('improvement')),
                 _percent(stage['comparisons'][variant]['FinishP4'].get('improvement')),
                 _percent(stage['comparisons'][variant]['FinishP4'].get('worst_regression_fraction'))) for variant,value in stage['metrics'].items()])
        _table(lines,['策略','N','场数','平均T/N','最差单场T/N','最差相对Finish耗时变化'],
               [(variant,n,values['rounds'],_number(values['mean_T_per_N']),_number(values['worst_T_per_N']),
                 _percent(stage['comparisons'][variant]['FinishP4'].get('by_N_worst',{}).get(n)))
                for variant,value in stage['metrics'].items() for n,values in value.get('by_N',{}).items()])
        _table(lines,['策略/动作阶段','移动秒/场','换频道秒/场','检测秒/场','清除秒/场','合计秒/场'],
               [(variant+'/'+phase,*[_number(cost[key]) for key in COST_KEYS],_number(sum(cost.values())))
                for variant,value in stage['metrics'].items()
                for phase,cost in [('全部',value.get('mean_cost',{}))]+list(value.get('phases',{}).items()) if cost])
        _table(lines,['策略','实际事件','触发总次数'],[(variant,key,count) for variant,value in stage['metrics'].items() for key,count in value.get('triggers',{}).items()])
        source_rows=[]
        for variant,identities in stage['hash_evidence']['actual_strategies'].items():
            for actual_class,name,source in identities:
                item=stage['hash_evidence']['files'].get(source,{})
                source_rows.append((variant,actual_class,name,source,item.get('manifest_sha256','未记录'),
                                    '一致' if item.get('frozen_matches_manifest') else '不一致/缺失',
                                    '一致' if item.get('current_matches_manifest') else '历史版本/已变化'))
        _table(lines,['变体','实际类','实际名称','来源','冻结SHA256','副本校验','与当前核对'],source_rows)
        lines += [f"运行依赖整体：冻结副本{'一致' if stage['hash_evidence']['frozen_verified'] else '不一致或缺失'}；与当前{'一致' if stage['hash_evidence']['current_matches'] else '存在变化（开发历史允许，当前候选验收须一致）'}。逐文件哈希保存在 selection.json。",'']
    lines+=['## 全部失败与退步场景','',
            '以下列出所有已保存阶段的失败，以及分别相对 FastP4/FinishP4 的正向耗时退步；相同场景出现在不同开发版本中会分别保留。','']
    failures=[];regressions=[]
    for stage in stages:
        if stage['status']=='report_missing':continue
        for row in stage['records']:
            if not(row.get('full_clear') and row.get('normal_stop')):
                failures.append((stage['label'],row['variant'],row['scenario']['seed'],row.get('stop_reason','未提供'),row.get('error') or '全清/正常停止条件未满足',_run_link(stage['label'],row)))
        for variant,comparisons in stage['comparisons'].items():
            for reference,comparison in comparisons.items():
                if variant==reference:continue
                for regression in comparison.get('regressions',[]):
                    row=next(row for row in stage['records'] if row['variant']==variant and _scenario_key(row['scenario'])==_scenario_key(regression['scenario']))
                    regressions.append((stage['label'],variant,reference,regression['seed'],regression['scenario']['N'],
                                        _percent(regression['fraction']),_number(regression['delta_T']),_run_link(stage['label'],row)))
    if failures:_table(lines,['阶段','候选','seed','停止原因','错误','证据'],failures)
    else:lines+=['已读取报告中无失败场景；缺失阶段仍不视为通过。','']
    if regressions:_table(lines,['阶段','候选','参照','seed','N','耗时增加','增加秒数','证据'],regressions)
    else:lines+=['已读取的配对记录中无正向耗时退步；未配对的变体不包含在这一判断中。','']
    lines+=['## 选择与剩余目标','',
            '完整选型、每阶段指标和全部依赖哈希：[selection.json](hunt_round/selection.json)。',
            '报告生成器没有修改部署；这与整合负责人已经完成的演练入口接入分别记录。没有自动启动正式测试，没有修改第一二问、第三问结论或模拟器物理规则。','']
    integration=selection.get('practice_integration',{})
    if integration.get('status')=='integration_record_read':
        lines += [f"只读接入记录：实际类 `{integration.get('actual_class','未提供')}`，名称 `{integration.get('name','未提供')}`，源码 `{integration.get('source','未提供')}`，SHA256 `{integration.get('sha256','未提供')}`。",
                  f"接入记录与当前源码{'一致' if integration.get('matches_current_source') else '不一致/缺失'}，与本轮验证候选{'一致' if integration.get('matches_verified_candidate') else '不一致/尚缺验证'}。**已接入演练入口，接入后的实机尚未复跑。** 离线验收不等于实机复跑结果。",'']
    else:lines+=['缺少演练接入元信息；不能从报告选择本身推断已经接入。','']
    if selection.get('candidate_metrics'):
        metrics=selection['candidate_metrics']
        lines+=[f"最终验证集合计 {metrics['rounds']} 场，平均 T/N {_number(metrics.get('mean_T_per_N'))} 秒/源，加权 {_number(metrics.get('weighted_T_per_N'))} 秒/源；相对当前 FinishP4 改善 {_percent(selection['comparison_vs_FinishP4'].get('improvement'))}。",'']
        _table(lines,['N','验证场数','平均T/N','最差单场T/N'],
               [(n,value['rounds'],_number(value['mean_T_per_N']),_number(value['worst_T_per_N'])) for n,value in metrics.get('by_N',{}).items()])
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=HERE/'hunt_round')
    parser.add_argument('--output',type=Path,default=HERE/'HUNT_ROUND_REPORT.md')
    args=parser.parse_args(argv)
    stages=[_load(args.root/label) for label in EXPECTED_LABELS]
    selection=_selection(stages)
    selection['practice_integration']=_practice_integration(selection)
    selection['generated']=datetime.now(timezone.utc).isoformat()
    selection['development_uses_same_14_scenarios']=True
    selection['stages']={stage['label']:{key:value for key,value in stage.items() if key not in ('records','manifest')} for stage in stages}
    selection['report_generator_sha256']=_sha(Path(__file__))
    args.output.write_text(render(stages,selection),encoding='utf-8')
    (args.root/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({key:selection[key] for key in ('status','selected_variant','target_status')},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
