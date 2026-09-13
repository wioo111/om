"""Package a completed route round. No simulator access or entry-point mutation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

from test_route_standalone import RUNTIME_FILES


HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE.parent / '交付' / 'P4_route_round2_20260913.zip')
    args = parser.parse_args()
    selection = json.loads((HERE / 'route_round2/selection.json').read_text(encoding='utf-8'))
    if not selection['evidence_complete'] or not selection['all_runs_accepted']:
        raise RuntimeError('Selected strategy lacks complete accepted evidence')
    selected = selection['selected_variant']
    source_name = Path(selection['selected_source']).name
    if digest((HERE / source_name).read_bytes()) != selection['selected_sha256']:
        raise RuntimeError('Selected source differs from the frozen evidence')
    integration_path = HERE / 'INTEGRATION_ROUTE_RECORD.json'
    integration = json.loads(integration_path.read_text(encoding='utf-8'))
    if integration['actual_class'] != selection['selected_class'] or integration['sha256'] != selection['selected_sha256']:
        raise RuntimeError('Integration identity does not match selected evidence')
    output = args.output.resolve()
    for path in (output, output.with_suffix('.manifest.json'), output.with_suffix('.sha256')):
        if path.exists():
            raise FileExistsError('Preserve the existing delivery: ' + str(path))
    source_files = set(RUNTIME_FILES) | {
        'run_hunt_local.py', 'make_route_delivery.py', 'route_round2_experiment.py',
        'route_round2_report.py', 'hunt_experiment.py', 'cost_experiment.py',
        'test_route.py', 'test_route_probe.py', 'test_route_standalone.py',
        'test_discovery_prune.py', 'test_hunt.py', 'test_local_hunt.py',
        'test_discovery_compact.py', 'test_discovery_coverage.py',
        'test_discovery_mesh.py', 'test_discovery_rings.py', 'test_cost.py',
        'test_finish.py', 'ROUTE_ROUND2_REPORT.md', 'INTEGRATION_ROUTE_RECORD.json',
        'discovery_design_round2.py', 'discovery_design_round2_results.json',
        'discovery_star_round2.py', 'discovery_star_round2_results.json',
        'p4_route_diagnosis_round2.py', 'p4_route_diagnosis_round2_results.json',
    }
    entries = {name: (HERE / name).read_bytes() for name in source_files}
    for name in ('discovery_joint_prune.py', 'test_discovery_joint_prune.py'):
        if (HERE / name).is_file():
            entries[name] = (HERE / name).read_bytes()
    entries['requirements-route.txt'] = b'numpy==2.5.3\nshapely==2.1.2\npytest==9.1.1\n'
    labels = []
    root = HERE / 'route_round2'
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (folder / 'manifest.json').is_file():
            continue
        if not (folder / 'report.json').is_file():
            raise RuntimeError('Unfinished experiment: ' + folder.name)
        labels.append(folder.name)
        index = {}
        for path in sorted((folder / 'source').rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            data = path.read_bytes()
            checksum = digest(data)
            blob = 'frozen_sources/blobs/' + checksum
            entries.setdefault(blob, data)
            index[path.relative_to(folder / 'source').as_posix()] = {'sha256': checksum, 'blob': blob}
        entries[f'route_round2/{folder.name}/SOURCE_INDEX.json'] = json.dumps(index, indent=2).encode()
        for path in sorted(folder.rglob('*')):
            if path.is_file() and 'source' not in path.relative_to(folder).parts and '__pycache__' not in path.parts:
                entries['route_round2/' + path.relative_to(root).as_posix()] = path.read_bytes()
    for path in root.iterdir():
        if path.is_file():
            entries['route_round2/' + path.name] = path.read_bytes()
    for path in (root / 'integration_before_route2').rglob('*'):
        if path.is_file():
            entries['route_round2/' + path.relative_to(root).as_posix()] = path.read_bytes()
    entries['restore_route_source.py'] = b'''import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parent
index_path=(r/'route_round2'/a.label/'SOURCE_INDEX.json').resolve();index_path.relative_to(r/'route_round2')
index=json.loads(index_path.read_text());a.output.mkdir(parents=True,exist_ok=False)
for name,item in index.items():
    dest=(a.output/name).resolve();dest.relative_to(a.output.resolve())
    blob=(r/item['blob']).resolve();blob.relative_to(r/'frozen_sources')
    data=blob.read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256']
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
print(a.output.resolve())
'''
    entries['README_ROUTE.md'] = f'''# 第四问本轮交付

最终选用 `{selected}`，实际哈希与全部结果见 `ROUTE_ROUND2_REPORT.md` 和
`INTEGRATION_ROUTE_RECORD.json`。旧版 HuntP4、FinishP4、FastP4 均保留。
本轮完成后按用户要求停止继续迭代，尚未整体达到300—400秒/源。

## 独立离线运行

```powershell
python -m pip install -r requirements-route.txt
python run_route_local.py --strategy {selected} --N 10 --seed 993302 --error-mode fixed --reception-range 1000 1500 --output my_result.json
python run_route_local.py --strategy HuntP4 --N 10 --seed 993302 --error-mode fixed
python -m pytest test_route.py test_route_probe.py test_route_standalone.py test_discovery_prune.py test_hunt.py test_local_hunt.py test_cost.py test_finish.py -q
```

正常停止、全清且四项成本核对通过才返回0；step_limit不算通过。错误模式仅
random/fixed/edge。半径边界使用1000 1000或1500 1500。输出必须是新文件。
离线入口只使用本地mock，不启动或连接正式模拟器。公共演练一键脚本已在
原仓库更新；本独立包用于离线运行和代码交付，正式入口仍保留FastP4。

策略只使用测量反馈，不读取源数、真值、种子或真实半径。共同规划扫描与清除，
沿原定扫描路段进行有限补测；no_signal不裁剪定位区，补测位置和固定误差
不会被当作独立重复证据。连续覆盖与有限光学清除保证来自本包几何函数，
不依赖用户电脑上的第三问目录；problem1_v4_inline.py已内置。

所有开发尝试、退步场景、确认和边界逐动作记录在route_round2。历史源码通过
SHA256去重保存，可恢复到新目录：

```powershell
python restore_route_source.py --label dev04_transit_probe --output restored_dev04
```

几何搜索结果和未接入helper仅为研究证据，不在当前运行链中。
包装器只读取文件，绝不启动测试或改写公共入口。包内路径记录属于历史证据，
不是对原电脑绝对路径的运行依赖。
'''.encode('utf-8')
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'selected_variant': selected,
                'selected_sha256': selection['selected_sha256'], 'frozen_labels': labels,
                'formal_run_started': False, 'files': {}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            manifest['files'][name] = {'bytes': len(data), 'sha256': digest(data)}
            archive.writestr(name, data)
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    checksum = digest(output.read_bytes())
    manifest['archive'] = {'sha256': checksum, 'bytes': output.stat().st_size}
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    output.with_suffix('.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps({'archive': str(output), 'sha256': checksum, 'bytes': output.stat().st_size,
                      'files': len(entries) + 1}, ensure_ascii=False))


if __name__ == '__main__':
    main()
