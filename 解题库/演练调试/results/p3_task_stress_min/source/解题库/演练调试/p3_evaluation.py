"""Frozen P3 reference data and stratified offline comparisons. No simulator connection."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

from p3_metrics import stratified, markdown_table
from p3_reference import (ROOT, REPO, digest, read_json, write_json, collect_completed,
                          assign_historical_split, fit_profile, validation_scores)

RESULTS = ROOT/'results'
HISTORY = ('p3_joint_holdout01', 'p3_joint_probe_holdout', 'p3_probe_confirmation')
VARIANTS = ('scan', 'residual', 'probe_plan')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def dataset_file(value):
    candidate = Path(value)
    return candidate.resolve() if candidate.exists() else RESULTS/value


def freeze(folder):
    cases, rejected, duplicates = collect_completed(RESULTS)
    if not cases:
        raise ValueError('No completed P3 reference cases')
    assign_historical_split(cases)
    profile = fit_profile(cases)
    validation = validation_scores(cases, profile)
    counts = {split: {str(n): sum(c['split']==split and c['N']==n for c in cases)
                      for n in range(10,17)}
              for split in ('historical_calibration', 'historical_validation')}
    manifest = dict(schema=1, frozen_at=utc_now(), reference_scope='own completed P3 practice only',
                    cases=len(cases), split_counts=counts, rejected=rejected, duplicates=duplicates,
                    known_run_folders=sorted(p.name for p in RESULTS.glob('20??????_*_p3_*')),
                    future_official_holdout=[],
                    blind_test_status='NOT_AVAILABLE: all existing records are historical, already inspected.',
                    split_unit='whole unique scenario; completed package hash when available, otherwise case code',
                    split_algorithm='within N sort SHA256(p3-reference-v1:case_id), reserve round(25%) for retrospective validation',
                    calibration_case_ids=profile['fitted_case_ids'],
                    validation_case_ids=[c['case_id'] for c in cases if c['split']=='historical_validation'],
                    case_source_sha256={c['case_id']:c['source_sha256'] for c in cases})
    write_json(folder/'cases.json', cases)
    write_json(folder/'profile.json', profile)
    write_json(folder/'validation.json', validation)
    manifest['artifact_sha256']={name:digest(folder/name) for name in ('cases.json','profile.json','validation.json')}
    write_json(folder/'manifest.json', manifest)
    lines = ['# 问题三：冻结历史演练参考集', '',
             f'纳入 {len(cases)} 个唯一场景；拒收 {len(rejected)} 个；重复场景 {len(duplicates)} 个。',
             '仅读取已结束的自有问题三演练，不读取活动日志、加密载荷或正式测试数据库。', '',
             '| N | 历史校准 | 历史验证 |', '|---|---:|---:|']
    for n in range(10,17):
        lines.append(f"| {n} | {counts['historical_calibration'][str(n)]} | {counts['historical_validation'][str(n)]} |")
    lines += ['', '## 信息边界', '',
              '这些记录以前已被查看和用于算法诊断。历史验证只是不参与本次拟合，绝非全新盲测。未来官方演练留出集目前为空。',
              '按整场唯一场景划分，不能把动作行或同一场景的不同副本拆到两边。未全清记录仍保留，但不用于估计源分布，避免漏检偏差。',
              'N 只属于评测元数据。生成器内部按 N 构造场景，策略仅接收常规动作响应。', '',
              '## 校准构造', '',
              '清除成功点 q 不是目标真值 z，只能推出 ||z-q||≤20米。由三角不等式，',
              '目标径向距离属于 [max(0,||q||−20), min(1800,||q||+20)]。',
              '清除前在 p 收到信号给出 R≥||p-q||−20；未收到信号给出 R<||p-q||+20。',
              '再与 [1000,1500] 相交。这里只形成保守的边际区间，不能据此精确重放官方场景。',
              '使用等面积三档径向区间、五档接收半径，以固定每档一个伪计数的区间加权 EM 拟合；不根据验证结果改变分箱或正则。',
              '区间似然权重是区间与分档的重叠长度/档宽。此工作模型未消除自适应测点导致的删失偏差，不是官方分布识别。',
              '方位、频道及径向与半径独立性仍为假设；误差分布未拟合，继续分别评测四种噪声。', '',
              '## 验证：区间相容性，不等于提速', '',
              '| 分割 | 变量 | 每场平均对数似然相对均匀模型增益 |', '|---|---|---:|']
    for split, entries in validation.items():
        for key, value in entries.items():
            gain=value['mean_scene_log_likelihood_gain_vs_uniform']
            lines.append(f'| {split} | {key} | {gain:.6f} |')
    lines += ['', '正值只表示对这些观测区间更相容，负值表示更差。任何一种结果均不能证明官方分布真实性。',
              '新参考模型仅作为独立敏感性模型；不覆盖旧模拟器，不切换一键策略，不把历史响应用于新动作。',
              'manifest.json 保存输入与输出哈希；profile.json 只由历史校准集拟合。']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(dict(cases=len(cases), splits=counts, validation=validation, rejected=rejected), ensure_ascii=False))
    return 0


def history(folder):
    rows=[]; inputs={}
    for label in HISTORY:
        path=RESULTS/label/'report.json'; report=read_json(path)
        if report['exit_code'] != 0 or not report['sources_unchanged']:
            raise ValueError('Invalid historical execution evidence')
        inputs[str(path.relative_to(REPO))]=digest(path)
        for original in report['records']:
            if original['variant'] not in VARIANTS:
                continue
            row=dict(original)
            trace_file=path.parent/'runs'/f"{row['seed']}_{row['variant']}.json"
            trace=read_json(trace_file)['actions']
            inputs[str(trace_file.relative_to(REPO))]=digest(trace_file)
            last=next((r['virtual_time_s'] for r in reversed(trace)
                       if r['action']=='clear' and r['result']=='success'),None)
            row['post_last_clear_s']=row['virtual_time_s']-last if last is not None else None
            rows.append(row)
    evaluation=stratified(rows,'residual')
    report=dict(scope='historical offline regression set; already used for model selection, not fresh holdout',
                input_sha256=inputs, records=rows, stratified=evaluation)
    write_json(folder/'report.json',report)
    (folder/'REPORT.md').write_text('# 历史112场景分层对照\n\n'
        '每种算法112场景，每个N为16场。均为已有离线结果重算统计，不是新官方演练。\n\n'
        '先比较全清率；正节省表示快于ResidualP3。置信区间为整场配对自助法描述区间，未作多重比较修正。\n\n'
        +markdown_table(evaluation)+'\n\n'
        '历史场景已参与算法选择，此后只作为开发/回归集。整体均值不能替代分N结果。\n',encoding='utf-8')
    print('Historical paired scenes:',evaluation['groups']['overall']['variants']['probe_plan']['cases'])
    return 0


def load_profile(dataset):
    dataset=dataset_file(dataset); manifest=read_json(dataset/'manifest.json')
    for name,expected in manifest['artifact_sha256'].items():
        if digest(dataset/name) != expected:
            raise ValueError('Frozen reference artifact changed: '+name)
    profile=read_json(dataset/'profile.json')
    if set(profile['fitted_case_ids']) & set(manifest['validation_case_ids']):
        raise ValueError('Calibration/validation scene leakage')
    return dataset,manifest,profile


def benchmark(folder,args):
    from benchmark_speed import run_case
    dataset,manifest,profile=load_profile(args.dataset)
    specs=[]; scenes=[]
    variants=tuple(args.variants.split(','))
    models=('uniform','reference'); modes=('fixed','edge','bias','smooth')
    for model in models:
        traces=folder/'runs'/model; traces.mkdir(parents=True)
        for n in range(10,17):
            for i in range(args.cases_per_n):
                seed=args.seed_start+(n-10)*args.cases_per_n+i
                scene=dict(model=model,seed=seed,N=n,error_mode=modes[i%4])
                scenes.append(scene)
                for variant in variants:
                    specs.append((3,variant,seed,n,modes[i%4],0.,str(traces),(1000.,1500.),
                                  profile if model=='reference' else None))
    plan=dict(created=utc_now(), stages='frozen offline validation, not official practice or a final blind test',
              dataset=str(dataset.relative_to(REPO)), manifest_sha256=digest(dataset/'manifest.json'),
              profile_sha256=digest(dataset/'profile.json'), variants=variants, reference=args.reference,
              parameter_changes_after_plan='none', scenes=scenes,
              future_official_holdout_status=manifest['blind_test_status'])
    write_json(folder/'plan.json',plan)  # fixed before any policy execution
    rows=[]
    with (folder/'progress.jsonl').open('w',encoding='utf-8') as progress:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(run_case,spec) for spec in specs]
            for future in as_completed(futures):
                row=future.result(); rows.append(row)
                entry={k:row.get(k) for k in ('evaluation_model','variant','seed','N','full_clear','virtual_time_s','error')}
                line=json.dumps(entry,ensure_ascii=False); progress.write(line+'\n');progress.flush();print(line,flush=True)
    evaluation={model:stratified([r for r in rows if r['evaluation_model']==model],args.reference) for model in models}
    report=dict(plan_sha256=digest(folder/'plan.json'),executions=len(rows),records=rows,models=evaluation,
                model_interpretation='Do not pool model families. A sensitivity fit is not official distribution truth.')
    write_json(folder/'report.json',report)
    lines=['# 冻结参数：分N、分生成模型的多基线离线对照','',
           '均匀模型与历史参考敏感性模型分别汇报，不合并平均。每个N等量、四种误差等量；同场景配对。',
           '各版算法在本批执行期间均冻结；不按真实N路由算法，不自动切换一键候选。',
           '速度统计只涵盖完成场景，失败数显式保留。整场自助法区间仅为描述性估计，非多重比较后的显著性结论。']
    for model, ev in evaluation.items():
        lines += ['', '## '+model, '', markdown_table(ev)]
    lines += ['', '真实新演练留出验证未执行。结果只能证明这两类离线模型中的表现，不能代替实机提速证据。']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return 0 if all(r['full_clear'] for r in rows) else 1


def queue_holdout(folder,args):
    dataset,manifest,_=load_profile(args.dataset)
    known=set(manifest['known_run_folders']); pending=[]
    for run in sorted(RESULTS.glob('20??????_*_p3_*')):
        if run.name in known:
            continue
        required=[run/name for name in ('version.json','execution.json','result.json','actions.jsonl')]
        if not all(f.exists() for f in required):
            continue
        version,execution=read_json(required[0]),read_json(required[1])
        if (version.get('mode')!='practice' or version.get('problem')!=3
                or version.get('guard_event')!='practice_authorized' or execution.get('exit_code')!=0):
            continue
        # Only hash result/action bytes; do not parse N, rewards or outcomes for tuning.
        pending.append(dict(folder=run.name, source_sha256={str(f.relative_to(REPO)):digest(f) for f in required}))
    write_json(folder/'holdout_queue.json',dict(reference_manifest_sha256=digest(dataset/'manifest.json'),
        pending=pending, status='sealed outcomes; not evaluated; no automatic fitting or policy selection'))
    print('New completed practice folders queued without outcome inspection:',len(pending))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','history','benchmark','queue-holdout'))
    parser.add_argument('--label',required=True,help='New immutable output directory name')
    parser.add_argument('--dataset',help='Frozen reference label or directory')
    parser.add_argument('--cases-per-n',type=int,default=8)
    parser.add_argument('--seed-start',type=int,default=1080001)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--variants',default=','.join(VARIANTS))
    parser.add_argument('--reference',default='residual')
    args=parser.parse_args()
    if Path(args.label).name!=args.label or args.label in ('.','..'):
        parser.error('label must be a new directory name')
    if args.command in ('benchmark','queue-holdout') and not args.dataset:
        parser.error('--dataset required')
    if args.cases_per_n<4 or args.cases_per_n%4 or args.workers<1:
        parser.error('cases-per-n must be a positive multiple of 4; workers must be positive')
    variants=args.variants.split(',')
    allowed=set(VARIANTS)|{'cardinality','optical_task','optical_probe','shared_bearing','shared_optical','bounded_optical'}
    if args.reference not in variants or len(set(variants))!=len(variants) or set(variants)-allowed:
        parser.error('Unknown/duplicate variant or reference not included')
    folder=RESULTS/args.label;folder.mkdir(parents=True,exist_ok=False)
    sources=list(ROOT.glob('*.py'))+list((ROOT.parent/'第三问/v10').glob('*.py'))
    hashes={str(f.relative_to(REPO)):digest(f) for f in sources}
    for f in sources:
        dest=folder/'source'/f.relative_to(REPO);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(f.read_bytes())
    record=dict(started=utc_now(),command=[sys.executable,*sys.argv],cwd=str(Path.cwd()),code_sha256=hashes,
                scope='offline only; no real simulator requests, no formal tests',exit_code=1)
    write_json(folder/'execution.json',record)
    # Preserve exact output and exception evidence, including failures.
    original=sys.stdout
    class Tee:
        def __init__(self,log):self.log=log
        def write(self,text):self.log.write(text);return original.write(text)
        def flush(self):self.log.flush();original.flush()
    with (folder/'console.txt').open('w',encoding='utf-8') as console:
        sys.stdout=Tee(console)
        try:
            if args.command=='freeze':code=freeze(folder)
            elif args.command=='history':code=history(folder)
            elif args.command=='benchmark':code=benchmark(folder,args)
            else:code=queue_holdout(folder,args)
            unchanged=all(digest(REPO/path)==value for path,value in hashes.items())
            record['sources_unchanged']=unchanged
            record['exit_code']=code if unchanged else 1
        except Exception:
            traceback.print_exc(file=sys.stdout)
        finally:
            sys.stdout=original;record['finished']=utc_now();write_json(folder/'execution.json',record)
    print('OUTPUT',folder,'EXIT',record['exit_code'])
    return record['exit_code']


if __name__=='__main__':
    sys.exit(main())
