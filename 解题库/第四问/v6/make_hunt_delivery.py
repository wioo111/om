"""Build the self-contained P4 Hunt delivery only after evidence is complete.

No simulation, network request, strategy mutation or public-entry change occurs.
Historical frozen sources use a content-addressed store with restore indexes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile


HERE = Path(__file__).resolve().parent
ARCHIVE_NAME = 'P4_hunt_round_20260913.zip'
SOURCE_FILES = (
    'strategy.py', 'problem1_v4_inline.py', 'strategy_p4.py', 'strategy_fast.py',
    'strategy_finish.py', 'strategy_cost.py', 'strategy_hunt.py', 'local_hunt.py',
    'discovery_mesh.py', 'discovery_rings.py', 'discovery_coverage.py', 'discovery_compact.py',
    'mock_simulator_p4.py', 'robot_iter.py', 'hunt_experiment.py', 'cost_experiment.py', 'hunt_report.py',
    'geometry_search.py', 'geometry_search_results.json',
    'geometry_search_extra.py', 'geometry_search_extra_results.json',
    'geometry_route_opt.py', 'geometry_route_opt_results.json',
    'run_hunt_local.py', 'make_hunt_delivery.py', 'test_hunt.py', 'test_local_hunt.py',
    'test_discovery_mesh.py', 'test_discovery_rings.py', 'test_discovery_coverage.py',
    'test_discovery_compact.py', 'test_cost.py', 'test_finish.py', 'requirements-cost.txt',
    'HUNT_ROUND_REPORT.md',
)

README = '''# 第四问 Hunt 独立交付包

实际选择、性能和限制以 `HUNT_ROUND_REPORT.md` 为准。默认离线入口是
`run_hunt_local.py`，显式加载 `strategy_hunt.HuntP4`，打印实际类名、来源、
源文件 SHA256、诊断、四项成本和停止原因。FastP4 和 FinishP4 原版均保留。
整合负责人已将公共演练入口接入HuntP4，集成事实及实际源码哈希见
`INTEGRATION_RECORD.json`。正式入口仍为FastP4，未启动正式测试。
本打包脚本本身不修改任何公共入口。

## 安装与单场离线运行

建议 Python 3.13，已验证的依赖见 `requirements-hunt.txt`。

```powershell
python -m pip install -r requirements-hunt.txt
python run_hunt_local.py --strategy HuntP4 --N 10 --seed 993201 --dir-frac 0.5 --error-mode fixed --reception-range 1000 1500 --output local_hunt_result.json
python run_hunt_local.py --strategy FastP4 --N 10 --seed 993201 --dir-frac 0.5 --error-mode fixed
python run_hunt_local.py --strategy FinishP4 --N 10 --seed 993201 --dir-frac 0.5 --error-mode fixed
```

`--error-mode` 仅接受 random/fixed/edge。固定半径写为
`--reception-range 1000 1000` 或 `--reception-range 1500 1500`。
只有全清、正常停止且成本核对正确时退出码才为0。step_limit不是通过。
输出路径必须是新文件。该入口只创建本地mock，不访问正式模拟器。

## 测试与实验

```powershell
python -m pytest test_hunt.py test_local_hunt.py test_discovery_compact.py test_discovery_coverage.py test_discovery_mesh.py test_discovery_rings.py test_finish.py test_cost.py -q
python hunt_experiment.py --stage development --label new_development --variants FastP4 FinishP4 HuntP4 --workers 3
```

实验标签必须是新目录。确认集和边界集仅在明确调用时运行：分别使用
`--stage confirmation` 或 `--stage boundary`。已看过的确认场景不能调参后再次
称独立确认。完整历史结果、失败记录和逐动作成本在 `hunt_round/`。
独立包的 `test_cost.py` 可能跳过原仓库共享入口测试；其余模块均在本包中。

## 算法与依赖边界

21站连续发现证明、每频道实际测量证据、最多16源计数、安全光学覆盖、
有限局部补测与有证明的扫描站替换详见主报告与源文件说明。
no_signal不作为第四问的1000米空间排除。策略不读源数、种子、真实位置或半径。
零额外移动near清除保留扫描进度；失败的有限光学计划推进，耗尽报矛盾。

`problem1_v4_inline.py` 已内置。第三问纯光学思想通过本地 `strategy_cost.py`
中的函数实现；不导入第三问目录或第三问策略继承链。NumPy用于连续覆盖证书，
Shapely用于连续光学覆盖，pytest仅用于测试。包内没有第三问目录补齐依赖。

`geometry_search.py`、`geometry_search_extra.py`、`geometry_route_opt.py`及对应
`*_results.json`属于附加几何构造和最短路线证明证据，不会随策略导入重新运行。
这些几何实验不读取模拟场景。需要复现路线MILP求解时再安装
`requirements-geometry.txt`中的SciPy；普通策略运行不需要SciPy。
`hunt_report.py`为主报告生成器，原始场景证据保留在`hunt_round/`。

## 冻结源码与清单

`PACKAGE_MANIFEST.json` 保存每个文件的长度与SHA256。
历史各轮 `source/` 采用去重存储：索引位于
`hunt_round/<label>/SOURCE_INDEX.json`，内容位于 `frozen_sources/blobs/<SHA256>`。
恢复某一轮的完整源码到新目录：

```powershell
python restore_hunt_source.py --label dev08_compact --output restored_dev08
```

恢复后的源码对应历史清单。不要把当前根目录的新版本冒充历史失败版本。
原始结果中的本机来源路径是历史证据字段，不是运行依赖。
'''

RESTORE = '''"""Restore a saved P4 source snapshot into a new directory."""
import argparse,hashlib,json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if Path(args.label).name != args.label or args.label in ('.','..') or '/' in args.label or '\\\\' in args.label:
        parser.error('--label must be one directory name')
    root=Path(__file__).resolve().parent
    index=json.loads((root/'hunt_round'/args.label/'SOURCE_INDEX.json').read_text(encoding='utf-8'))
    args.output.mkdir(parents=True,exist_ok=False)
    for relative,entry in index['files'].items():
        target=args.output/relative
        target.resolve().relative_to(args.output.resolve())
        data=(root/entry['blob']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:
            raise RuntimeError('source blob hash mismatch: '+relative)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
    print(str(args.output.resolve()))

if __name__=='__main__':
    main()
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assemble_entries():
    """Return logical ZIP names and bytes/paths; never copies or modifies source."""
    missing = [name for name in SOURCE_FILES if not (HERE / name).is_file()]
    if missing:
        raise RuntimeError('Delivery inputs are not ready: ' + ', '.join(missing))
    entries = {name: HERE / name for name in SOURCE_FILES}
    entries['README_HUNT.md'] = README.encode('utf-8')
    entries['requirements-hunt.txt'] = b'numpy==2.5.3\nshapely==2.1.2\npytest==9.1.1\n'
    entries['requirements-geometry.txt'] = b'-r requirements-hunt.txt\nscipy==1.18.1\n'
    entries['restore_hunt_source.py'] = RESTORE.encode('utf-8')
    integration = HERE / 'INTEGRATION_RECORD.json'
    if not integration.is_file():
        integration = HERE.parents[2] / 'tools' / 'p4_practice_deployment.json'
    if not integration.is_file():
        raise RuntimeError('Practice integration record is missing')
    deployed = json.loads(integration.read_text(encoding='utf-8-sig'))
    if deployed.get('sha256') != digest((HERE / 'strategy_hunt.py').read_bytes()):
        raise RuntimeError('Practice integration record does not match the packaged Hunt source')
    entries['INTEGRATION_RECORD.json'] = integration
    root = HERE / 'hunt_round'
    if not root.is_dir():
        raise RuntimeError('hunt_round evidence directory is missing')
    snapshots = {}
    for label in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = label / 'manifest.json'
        if manifest.is_file() and not (label / 'report.json').is_file():
            raise RuntimeError('Experiment is unfinished: ' + label.name)
        source = label / 'source'
        if source.is_dir():
            index = {}
            for path in sorted(source.rglob('*')):
                if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                    continue
                relative = path.relative_to(source).as_posix()
                data = path.read_bytes()
                checksum = digest(data)
                blob = 'frozen_sources/blobs/' + checksum
                entries.setdefault(blob, data)
                index[relative] = dict(sha256=checksum, bytes=len(data), blob=blob)
            snapshots[label.name] = index
            entries[f'hunt_round/{label.name}/SOURCE_INDEX.json'] = json.dumps(
                dict(label=label.name, storage='sha256_deduplicated', files=index),
                ensure_ascii=False, indent=2).encode('utf-8')
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if 'source' in relative.parts or '__pycache__' in relative.parts or path.suffix == '.pyc':
            continue
        entries['hunt_round/' + relative.as_posix()] = path
    # Optional human-readable evidence added by the integration owner.
    for pattern in ('HUNT_*.md', 'ALGORITHM_HUNT*.md', 'requirements-hunt.txt'):
        for path in HERE.glob(pattern):
            if path.is_file():
                entries[path.name] = path
    return entries, snapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE.parent / '交付' / ARCHIVE_NAME)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    inventory_path = output.with_suffix('.manifest.json')
    checksum_path = output.with_suffix('.sha256')
    if any(path.exists() for path in (output, inventory_path, checksum_path)):
        parser.error('Delivery output already exists; use a new --output path')
    entries, snapshots = assemble_entries()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                    runtime_default='strategy_hunt.HuntP4', official_entry_modified=False,
                    includes_all_recorded_runs=True, frozen_labels=sorted(snapshots), files={})
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in sorted(entries.items()):
            data = source.read_bytes() if isinstance(source, Path) else source
            manifest['files'][name] = dict(bytes=len(data), sha256=digest(data))
            archive.writestr(name, data)
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
    checksum = digest(output.read_bytes())
    manifest['archive'] = dict(filename=output.name, bytes=output.stat().st_size, sha256=checksum)
    inventory_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    checksum_path.write_text(checksum + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps(dict(archive=str(output), sha256=checksum, bytes=output.stat().st_size,
                          files=len(entries) + 1, manifest=str(inventory_path),
                          checksum_file=str(checksum_path), frozen_labels=sorted(snapshots)),
                     ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
