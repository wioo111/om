"""C 机器在用户手动启动的官方演练中运行选定候选，不修改公共 robot.py。"""
import argparse
import hashlib
import importlib
import json
from datetime import datetime
from pathlib import Path

from collab.bench import ROOT, foundation
from robot import SimulatorClient
from robot_iter import run_with_sim_strategy


def main():
    parser = argparse.ArgumentParser(description='连接已由用户启动的本地模拟器测试')
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--robot-id', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:2026')
    args = parser.parse_args()
    expected = json.loads((ROOT / 'collab/frozen.json').read_text(encoding='utf-8'))['files']
    if foundation() != expected:
        raise SystemExit('公共版本与冻结基线不一致，请先由 C 统一版本')
    module, entry = args.candidate.split(':', 1)
    if not module.startswith('collab.'):
        raise SystemExit('候选应位于 collab 目录')
    strategy = getattr(importlib.import_module(module), entry)()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = ROOT / 'collab/live_results' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    paths = sorted((ROOT / 'collab').glob('*candidate.py'))
    metadata = dict(candidate=args.candidate, foundation=foundation(),
                    candidate_files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (folder / 'version.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    for path in paths:
        (folder / path.name).write_bytes(path.read_bytes())
    client = SimulatorClient(args.base_url, args.robot_id, str(folder / 'actions.jsonl'))
    try:
        result = run_with_sim_strategy(strategy, client)
        result.pop('log', None)
        (folder / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False,
                                                      allow_nan=False), encoding='utf-8')
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    except Exception as exc:
        (folder / 'error.txt').write_text(f'{type(exc).__name__}: {exc}', encoding='utf-8')
        raise
    finally:
        print(f'本次代码快照与逐动作日志: {folder}')


if __name__ == '__main__':
    main()
