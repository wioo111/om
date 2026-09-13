"""Run the current P3/P4 strategy in a manually opened simulator test."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

from practice_launch import REPO, ROOT, Tee, one_robot, robot_id, p4_strategy_metadata
from run_practice import p4_action_summary


def load_strategy(problem, p4_strategy='RouteProbeP4'):
    module = REPO / '解题库' / ('第三问/v10' if problem == 3 else '第四问/v6')
    sys.path.insert(0, str(module))
    if problem == 3:
        from strategy_task import OpticalTaskP3
        strategy = OpticalTaskP3()
    elif p4_strategy == 'FastP4':
        from strategy_fast import FastP4
        strategy = FastP4()
    elif p4_strategy == 'RouteProbeP4':
        from strategy_route_probe import RouteProbeP4
        strategy = RouteProbeP4()
    else:
        raise ValueError('Unsupported P4 formal strategy: ' + p4_strategy)
    from robot import SimulatorClient, _post
    from robot_iter import run_with_sim_strategy
    return module, strategy, SimulatorClient, _post, run_with_sim_strategy


def print_p4_formal_strategy(metadata):
    print(f"[P4 formal] class={metadata['actual_class']} name={metadata['strategy']}", flush=True)
    print('来源：' + metadata['strategy_source'], flush=True)
    print('SHA256：' + metadata['strategy_sha256'], flush=True)
    print('配置：' + json.dumps(metadata['feature_config'], ensure_ascii=False), flush=True)


def execute(problem, p4_strategy='RouteProbeP4'):
    module, strategy, client_type, post, run = load_strategy(problem, p4_strategy)
    metadata = p4_strategy_metadata(strategy) if problem == 4 else {}
    folder = REPO / '解题库/正式运行/results' / (
        datetime.now().strftime('%Y%m%d_%H%M%S_%f') + f'_p{problem}_{strategy.name}')
    folder.mkdir(parents=True, exist_ok=False)
    record = dict(mode='formal', problem=problem, strategy=strategy.name,
                  started=datetime.now(timezone.utc).isoformat(), exit_code=1,
                  session_selection='manual; protocol does not verify problem or mode')
    record.update(metadata)
    secret = ''
    try:
        # Share the lock with the practice launcher to prevent concurrent clients.
        with one_robot(ROOT / '.practice.lock'):
            secret = robot_id(ROOT / 'practice.local.json')
            with (folder / 'console.log').open('w', encoding='utf-8') as log:
                with redirect_stdout(Tee(sys.stdout, log, secret)), redirect_stderr(Tee(sys.stderr, log, secret)):
                    if problem == 4:
                        print_p4_formal_strategy(metadata)
                    hashes = {}
                    for source in list(module.glob('*.py')) + list(ROOT.glob('*launch.*')):
                        relative = source.relative_to(REPO)
                        target = folder / 'source' / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        data = source.read_bytes()
                        target.write_bytes(data)
                        hashes[str(relative)] = hashlib.sha256(data).hexdigest()
                    record['code_sha256'] = hashes
                    (folder / 'version.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')

                    class LoggedClient(client_type):
                        def _send(self, path, payload):
                            if path not in ('/enter', '/measure', '/clear', '/exit'):
                                raise RuntimeError('Unsupported simulator action')
                            row = dict(path=path, request={
                                k: '<redacted>' if k == 'robot_id' else v
                                for k, v in payload.items()})
                            try:
                                response = post(self.base_url, path, payload, deadline=self.deadline)
                                row['response'] = response
                                if path in ('/enter', '/clear', '/exit') or self._seq % 100 == 0:
                                    if problem == 4:
                                        summary = p4_action_summary(self._seq, path, payload, response)
                                    else:
                                        summary = dict(action=self._seq, path=path,
                                            virtual_time_s=response.get('virtual_time_s'),
                                            result=response.get('clear_result'))
                                    print(json.dumps(summary, ensure_ascii=False), flush=True)
                                return response
                            except Exception as exc:
                                row['error'] = str(exc).replace(secret, '<redacted>')
                                raise
                            finally:
                                with (folder / 'actions.jsonl').open('a', encoding='utf-8') as actions:
                                    actions.write(json.dumps(row, ensure_ascii=False).replace(secret, '<redacted>') + '\n')

                    print(f'接入问题{problem}正式测试，策略：{strategy.name}。运行中请勿切换或中止会话。', flush=True)
                    result = run(strategy, LoggedClient('http://127.0.0.1:2026', secret), max_steps=8000)
                    result.pop('log', None)
                    result.update(mode='formal', problem=problem, strategy=strategy.name)
                    result.update(metadata)
                    (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                    print(f"执行结束：清除{result['cleared']}个，虚拟耗时{result['virtual_time_s']:.2f}秒，停止原因：{result['stop_reason']}。")
                    print('清除数来自接口和策略记录；正式成绩、加密日志及上传状态请以模拟器为准。')
                    if problem == 4:
                        record['normal_stop'] = result['stop_reason'] in (
                            'all_channels_cleared_or_covered', 'cleared_maximum_16')
                        record['exit_code'] = 0 if record['normal_stop'] else 1
                    else:
                        record['exit_code'] = 0
    except (Exception, KeyboardInterrupt) as exc:
        record['exit_code'] = 130 if isinstance(exc, KeyboardInterrupt) else 1
        error = traceback.format_exc()
        if secret:
            error = error.replace(secret, '<redacted>')
        (folder / 'error.txt').write_text(error, encoding='utf-8')
        print('执行已停止：' + (str(exc).replace(secret, '<redacted>') if secret else str(exc)), file=sys.stderr)
        print('不自动重新进入或退出；请在模拟器查看本局状态，勿直接重复运行。', file=sys.stderr)
    finally:
        record['finished'] = datetime.now(timezone.utc).isoformat()
        (folder / 'execution.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print('运行记录：' + str(folder))
    return record['exit_code']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem', type=int, choices=(3, 4), required=True)
    parser.add_argument('--p4-strategy', choices=('RouteProbeP4', 'FastP4'), default='RouteProbeP4',
                        help='P4 only: validated default or preserved FastP4 rollback')
    parser.add_argument('--check', action='store_true', help='Import the actual strategy without network requests')
    args = parser.parse_args(argv)
    if args.check:
        _, strategy, *_ = load_strategy(args.problem, args.p4_strategy)
        if args.problem == 4:
            print_p4_formal_strategy(p4_strategy_metadata(strategy))
        print(f'问题{args.problem}正式入口离线检查通过，策略：{strategy.name}；未发送模拟器请求。')
        return 0
    return execute(args.problem, args.p4_strategy)


if __name__ == '__main__':
    sys.exit(main())
