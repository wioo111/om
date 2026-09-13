"""Prepare a verified submission copy without changing models or starting a simulator.

prepare: copy final source/dependencies and evidence; generate complete appendices.
finalize: block release until the paper, AI disclosure and original logs are reviewed.
archive: byte-verified external backup, then remove ONLY allowlisted tracked history.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import zipfile

LIMIT = 20_000_000
Q12 = '解题库/第一二问'
P3 = '解题库/第三问/v10'
P4 = '解题库/第四问/v6'
PAPER34 = '解题库/完整论文/第三四问'
SOURCE_EXT = {'.py', '.ps1', '.cmd', '.sh', '.m', '.r', '.R', '.c', '.cpp', '.h'}
TEXT_EXT = SOURCE_EXT | {'.md', '.txt', '.json', '.csv', '.toml', '.yaml', '.yml', '.tex', '.bib', '.svg', '.csl', '.cls', '.sty'}
KEEP_EXT = TEXT_EXT | {'.png', '.jpg', '.jpeg', '.pdf', '.docx'}
SKIP_PARTS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', 'tmp', 'temp', 'source_snapshot'}
SELECT = [
    'run.py', 'tools/*.py', 'tools/*.ps1', 'tools/*.cmd', 'tools/practice.local.example.json',
    '第三问_一键接入正式.cmd', '第三问_一键接入演练.cmd',
    '第四问_一键接入正式.cmd', '第四问_一键接入演练.cmd',
    Q12+'/*.py', Q12+'/requirements*.txt', Q12+'/pyproject.toml', Q12+'/src/**/*.py',
    Q12+'/tests/**/*.py', Q12+'/examples/**/*', Q12+'/results/*.json', Q12+'/results/*.csv',
    Q12+'/proofs/**/*', Q12+'/paper/**/*', Q12+'/figures/*.svg', Q12+'/figures/*.png',
    Q12+'/figures/manifest.json',
    *[P3+'/'+n for n in ('strategy.py','strategy_v8.py','strategy_fast.py','strategy_night.py','strategy_transit.py','strategy_joint.py','strategy_task.py','problem1_v4_inline.py','robot.py','robot_iter.py','mock_simulator.py')],
    P3+'/requirements*.txt',
    *[P4+'/'+n for n in ('strategy.py','strategy_p4.py','strategy_fast.py','strategy_cost.py','strategy_finish.py','strategy_hunt.py','strategy_route.py','strategy_route_probe.py','problem1_v4_inline.py','local_hunt.py','discovery_mesh.py','discovery_rings.py','discovery_compact.py','discovery_coverage.py','discovery_prune.py','robot.py','robot_iter.py','mock_simulator_p4.py','run_route_local.py','route_round2_experiment.py')],
    P4+'/requirements*.txt',
    '解题库/演练调试/*.py', '解题库/演练调试/*.json',
    '解题库/演练调试/datasets/**/*', '解题库/演练调试/data/**/*',
    '解题库/结果汇总/*.json', '解题库/结果汇总/*.md',
    '解题库/正式运行/evidence/*.json', '解题库/正式运行/*.md',
    PAPER34+'/*.py', PAPER34+'/*.json', PAPER34+'/*.md',
    PAPER34+'/figures/*.svg', PAPER34+'/figures/*.png',
]
ARCHIVE_CANDIDATES = [
    '.claude', '他人思路', 'CUMCM_Q1Q2_COMPLETE.zip',
    '解题库/第三问/q3_v8_collaboration.zip', '解题库/第三问/q3_v9_merged.zip',
    '解题库/第三问/q3_v10_route.zip', '解题库/第三问/v5.zip',
]
REQUIRED = [Q12+'/src/q12/geometry.py', Q12+'/src/q12/policy.py',
            Q12+'/src/q12/proof.py', Q12+'/src/q12/interval.py',
            P3+'/strategy_task.py', P3+'/robot_iter.py',
            P4+'/strategy_route_probe.py', P4+'/discovery_compact.py',
            P4+'/robot_iter.py', 'tools/formal_launch.py']
DESCRIPTIONS = {
    'geometry.py':'交会定位、区域直径与最小包围圆',
    'posterior.py':'物理可行区域及内外包络', 'policy.py':'第二检测点及接收安全域',
    'proof.py':'通用策略的计算机辅助核验', 'interval.py':'定向区间运算',
    'strategy_task.py':'第三问数量上界及有限光学清除',
    'strategy_route_probe.py':'第四问零绕路补测与调度',
    'discovery_compact.py':'第四问21站构造', 'discovery_coverage.py':'连续覆盖核验',
    'robot.py':'模拟器通信客户端', 'robot_iter.py':'动作执行、状态更新及成本统计',
    'formal_launch.py':'正式策略加载与日志记录',
}


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def safe_relative(value: str) -> Path:
    p=PurePosixPath(value.replace('\\','/'))
    if p.is_absolute() or not p.parts or '..' in p.parts or ':' in p.parts[0]:
        raise ValueError('Unsafe relative path: '+value)
    return Path(*p.parts)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git','-C',str(root),*args],text=True,encoding='utf-8').strip()


def eligible(path: Path, root: Path) -> bool:
    rel=path.relative_to(root)
    return (path.is_file() and not path.is_symlink()
            and not any(p in SKIP_PARTS or p.startswith('~$') for p in rel.parts)
            and path.suffix in KEEP_EXT
            and not path.name.endswith(('.local.json','.sqlite3','.pyc')))


def select_sources(root: Path) -> set[Path]:
    chosen={p.relative_to(root) for pattern in SELECT for p in root.glob(pattern) if eligible(p,root)}
    pool=[p for p in root.rglob('*.py') if eligible(p,root)
          and not any(x in p.parts for x in ('results','logs','他人思路'))]
    index={}
    for p in pool: index.setdefault(p.stem,[]).append(p.relative_to(root))
    pending=list(chosen); examined=set()
    while pending:
        rel=pending.pop()
        if rel in examined or rel.suffix!='.py':continue
        examined.add(rel)
        tree=ast.parse((root/rel).read_text(encoding='utf-8-sig'),filename=str(rel))
        modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):modules += [a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module: modules.append(node.module)
        for module in modules:
            parts=module.split('.')
            roots=[rel.parent,rel.parent/'src',Path(Q12)/'src',Path('tools'),Path('解题库/演练调试')]
            matches=[]
            for base in roots:
                for suffix in [Path(*parts).with_suffix('.py'),Path(*parts)/'__init__.py']:
                    candidate=base/suffix
                    if (root/candidate).is_file():matches.append(candidate)
                if matches:break
            if not matches and len(index.get(parts[-1],[]))==1:matches=index[parts[-1]]
            for item in matches:
                if item not in chosen:chosen.add(item);pending.append(item)
    return chosen


def scan_text(path: Path, private_terms: list[str]) -> list[str]:
    if path.suffix not in TEXT_EXT:return []
    text=path.read_text(encoding='utf-8-sig',errors='replace'); hits=[]
    for value in private_terms:
        if value and value in text:hits.append('private_term')
    if re.search(r'[A-Za-z]:[\\/]+Users[\\/][^\s\'\"<>]+',text):hits.append('absolute_user_path')
    if re.search(r'github\.com/wioo111|\b(?:sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,})',text):hits.append('account_or_token')
    if re.search(r'(?:[\"\']robot_id[\"\']\s*[:=]\s*[\"\']\d{12}[\"\'])',text):hits.append('literal_team_id')
    return sorted(set(hits))


def add_extra(root: Path, support: Path, inputs: dict, records: list) -> None:
    for row in inputs.get('extra_files',[]):
        src=Path(row['source']);src=src if src.is_absolute() else root/src
        dst=support/safe_relative(row['destination'])
        if not src.is_file() or src.is_symlink():raise ValueError('Missing extra input: '+str(src))
        if dst.exists():raise FileExistsError(str(dst))
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        records.append({'path':dst.relative_to(support).as_posix(),'sha256':digest(dst),
                        'bytes':dst.stat().st_size,'description':row.get('description','补充复现材料')})


def prepare(root: Path, out: Path, inputs: dict) -> None:
    if out.exists():raise FileExistsError('Use a new output directory; previous evidence is not overwritten.')
    chosen=select_sources(root)
    missing=[p for p in REQUIRED if Path(p) not in chosen]
    if missing:raise ValueError('Required final sources missing: '+', '.join(missing))
    out.mkdir(parents=True);support=out/'支撑材料工作区';code=support/'程序与复现';code.mkdir(parents=True)
    records=[]; privacy=[]
    for rel in sorted(chosen,key=lambda x:x.as_posix()):
        src=root/rel; dst=code/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        if digest(src)!=digest(dst):raise IOError('Copy verification failed: '+str(rel))
        desc=DESCRIPTIONS.get(rel.name,'完整源程序/测试' if rel.suffix in SOURCE_EXT else '结果、图表或复现输入')
        records.append({'path':dst.relative_to(support).as_posix(),'sha256':digest(dst),'bytes':dst.stat().st_size,'description':desc})
        hits=scan_text(dst,inputs.get('private_terms',[]))
        if hits:privacy.append({'path':rel.as_posix(),'flags':hits})
    add_extra(root,support,inputs,records)
    for row in records:
        if not row['path'].startswith('程序与复现/'):
            hits=scan_text(support/row['path'],inputs.get('private_terms',[]))
            if hits:privacy.append({'path':row['path'],'flags':hits})
    a=['# 附录A 支撑材料文件列表','','| 文件名 | 功能描述 |','|---|---|']
    for row in records:a.append(f"| `{row['path']}` | {row['description']} |")
    a += ['| `提交清单.json` | 文件哈希与完整性核对 |','']
    (out/'附录A_文件列表.md').write_text('\n'.join(a),encoding='utf-8')
    b=['# 附录B 完整源程序代码','','行号仅用于论文展示，不写入可执行文件。','']
    for row in records:
        p=support/row['path']
        if p.suffix not in SOURCE_EXT:continue
        text=p.read_text(encoding='utf-8-sig')
        b += ['## '+row['path'],'','```text']
        b += [f'{i:5d}  {line}' for i,line in enumerate(text.splitlines(),1)]
        b += ['```','']
    (out/'附录B_完整代码.md').write_text('\n'.join(b),encoding='utf-8')
    write_json(support/'提交清单.json',{'files':records,'manifest_does_not_hash_itself':True})
    checklist={
        'paper': '', 'paper_sha256': '', 'ai_pdf': '',
        'official_logs': [],
        'manual_checks':{
            'paper_all_four_questions':False,'abstract_one_page':False,
            'body_without_contents_and_at_most_30_pages':False,
            'appendix_A_B_complete_and_matches_support':False,
            'margins_at_least_25mm_numbering_correct':False,
            'anonymity_all_files_including_metadata':False,
            'ai_information_complete_and_reviewed':False,
            'official_exports_mapped_to_three_runs_per_problem':False,
            'code_run_in_isolated_directory_results_match_paper':False,
            'all_data_and_experiment_dependencies_present':False},
        'frozen_support_manifest_sha256':digest(support/'提交清单.json'),
        'privacy_findings':privacy,
        'note':'本清单是待核验状态，不是已完成声明。正式日志另需以本机导出原件补入；不要改名或解密。'}
    write_json(out/'提交核验.json',checklist)
    (out/'尚不可直接提交.txt').write_text('尚缺合并完整论文、完整附录、人工核验、AI最终说明及正式日志核对。\n本阶段只整理源码和现有证据；未生成最终提交ZIP。\n',encoding='utf-8')
    print(json.dumps({'stage':'prepared_not_submission_ready','files':len(records),'privacy_flags':len(privacy),'out':str(out)},ensure_ascii=False))


def final_check_and_pack(root: Path, out: Path) -> None:
    config=json.loads((out/'提交核验.json').read_text(encoding='utf-8-sig'))
    support=out/'支撑材料工作区';issues=[]
    if not all(config['manual_checks'].values()):issues.append('人工核验清单未全部完成')
    if digest(support/'提交清单.json')!=config['frozen_support_manifest_sha256']:issues.append('提交清单已变化，须重新核验论文附录')
    manifest=json.loads((support/'提交清单.json').read_text(encoding='utf-8'))
    expected=set()
    for row in manifest['files']:
        p=support/safe_relative(row['path']);expected.add(p.relative_to(support).as_posix())
        if not p.is_file() or digest(p)!=row['sha256']:issues.append('支撑文件缺失或变化: '+row['path'])
    actual={p.relative_to(support).as_posix() for p in support.rglob('*') if p.is_file()}
    if actual != expected | {'提交清单.json'}:issues.append('工作区实际文件与附录A文件清单不一致')
    paper=Path(config.get('paper') or '_missing_');ai=Path(config.get('ai_pdf') or '_missing_')
    if not paper.is_file() or paper.suffix.lower()!='.pdf':issues.append('缺少完整参赛论文PDF')
    elif digest(paper)!=config.get('paper_sha256'):issues.append('论文PDF哈希未核验')
    if not ai.is_file() or ai.suffix.lower()!='.pdf':issues.append('缺少AI工具使用详情PDF')
    if ai.is_file() and not any(r['sha256']==digest(ai) and Path(r['path']).name=='AI工具使用详情.pdf' for r in manifest['files']):issues.append('AI最终PDF未纳入附录A对应清单；重新prepare')
    counts={3:0,4:0};seen_hash=set();seen_name=set()
    for row in config.get('official_logs',[]):
        q=row.get('problem');p=support/safe_relative(row['path'])
        if q not in counts or not p.is_file() or p.suffix.lower()!='.jlog':issues.append('无效正式日志映射');continue
        if p.name.startswith('practice-'):issues.append('演练日志不能替代正式日志')
        if p.name!=row.get('original_filename'):issues.append('正式导出日志文件名不一致')
        h=digest(p)
        if h in seen_hash or p.name in seen_name:issues.append('正式日志重复')
        seen_hash.add(h);seen_name.add(p.name);counts[q]+=1
        if p.relative_to(support).as_posix() not in expected:issues.append('正式日志未列入附录A；重新prepare')
    if counts!={3:3,4:3}:issues.append('第三、四问各三次正式日志未齐')
    if paper.is_file() and paper.stat().st_size>LIMIT:issues.append('论文超过20MB')
    try:
        from pypdf import PdfReader
        if paper.is_file():
            reader=PdfReader(str(paper));first=reader.pages[0].extract_text() or ''
            if '承诺书' in first.replace(' ','') or '编号专用页' in first:issues.append('电子论文含专用封面')
            if '摘要' not in first.replace(' ',''):issues.append('电子论文第一页未识别到摘要')
    except ImportError:issues.append('未安装pypdf，无法完成PDF初步核验')
    if issues:
        write_json(out/'阻塞项.json',issues);raise RuntimeError('；'.join(issues))
    final_target=out/'正式提交'
    if final_target.exists():raise FileExistsError('Final output already exists')
    target=out/'正在校验_不可提交';target.mkdir(exist_ok=False)
    shutil.copyfile(paper,target/'参赛论文.pdf')
    zpath=target/'支撑材料.zip'
    with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(support.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(support).as_posix())
    with zipfile.ZipFile(zpath) as z:
        if z.testzip():raise RuntimeError('ZIP integrity failure')
    if zpath.stat().st_size>LIMIT:
        zpath.rename(out/'支撑材料_超过20MB_不可提交.zip')
        raise RuntimeError('支撑材料超过20MB，不得删减必要代码；需压缩重复图件并重新核验')
    target.rename(final_target);target=final_target
    write_json(out/'最终校验.json',{'files':[{ 'path':p.name,'sha256':digest(p),'bytes':p.stat().st_size} for p in target.iterdir()], 'automatic_checks_do_not_replace_manual_review':True})
    print('已生成两个提交文件：'+str(target))


def archive(root: Path, destination: Path) -> None:
    if destination==root or root in destination.parents:raise ValueError('Archive must be outside the repository')
    if destination.exists():raise FileExistsError('Archive destination already exists')
    tracked=git(root,'ls-files','-z').split('\0')
    selected=[]
    for name in tracked:
        if not name:continue
        p=root/safe_relative(name)
        if any(name==a or name.startswith(a+'/') for a in ARCHIVE_CANDIDATES):
            if p.is_symlink():raise ValueError('Refuse symlink archive')
            if p.is_file():selected.append((name,p))
    destination.mkdir(parents=True);records=[]
    (destination/'git_status_before.txt').write_text(git(root,'status','--porcelain=v1'),encoding='utf-8')
    (destination/'HEAD.txt').write_text(git(root,'rev-parse','HEAD')+'\n',encoding='utf-8')
    for name,p in selected:
        d=destination/safe_relative(name);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
        records.append({'path':name,'sha256':digest(p),'bytes':p.stat().st_size})
    for r in records:
        if digest(destination/safe_relative(r['path']))!=r['sha256']:raise IOError('Archive mismatch')
    write_json(destination/'archive_manifest.json',records)
    for r in records:
        p=root/safe_relative(r['path'])
        if digest(p)!=r['sha256']:raise RuntimeError('Source changed during archive; stop')
        p.unlink()
    print(f'已归档{len(records)}个指定历史文件；未提交Git、未删除模拟器或日志。')


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','finalize','archive'])
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--out',type=Path)
    p.add_argument('--inputs',type=Path)
    a=p.parse_args();root=a.repo.resolve()
    if not a.out:p.error('--out is required and must identify a new working or archive directory')
    out=a.out.resolve()
    inputs=json.loads(a.inputs.read_text(encoding='utf-8-sig')) if a.inputs else {}
    if a.command=='prepare':prepare(root,out,inputs)
    elif a.command=='finalize':final_check_and_pack(root,out)
    else:archive(root,out)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc),file=sys.stderr);sys.exit(1)
