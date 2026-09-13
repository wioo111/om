"""One-click practice only: no desktop automation, no simulator start/reset APIs."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
MODULE=REPO/'解题库/演练调试'
sys.path.insert(0,str(MODULE))
from run_practice import (PracticeGuard, PracticeNotReady, DEFAULT_DATA, main as run_robot,
                          p4_strategy_metadata, print_p4_strategy)

@contextmanager
def one_robot(lock_path):
    """OS-held lock is automatically released even if the console is closed."""
    import msvcrt
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as exc:raise RuntimeError('已有一个接入程序在运行，请勿重复点击。') from exc
        try:yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

def robot_id(config_path):
    value=os.environ.get('JAMMERS_ROBOT_ID')
    if not value and config_path.exists():
        value=json.loads(config_path.read_text(encoding='utf-8-sig')).get('robot_id')
    if not value:
        value=input('首次使用，请输入模拟器当前登录队号（只保存到本机）：').strip()
        if not re.fullmatch(r'[0-9]{12}',value):raise ValueError('队号须为12位数字。')
        config_path.write_text(json.dumps({'robot_id':value},indent=2),encoding='utf-8')
    value=str(value).strip()
    if not re.fullmatch(r'[0-9]{12}',value):raise ValueError('本机队号设置无效，请检查 tools/practice.local.json。')
    return value

def wait_for_practice(data,timeout=30.,clock=time.monotonic,sleep=time.sleep):
    deadline=clock()+timeout
    pinned=None
    while True:
        try:
            guard=PracticeGuard(data,allow_waiting=True)
        except PracticeNotReady:
            if pinned is not None:raise RuntimeError('等待期间会话消失，已停止；请对新局重新点击。')
        else:
            identity=(guard.journal,guard.header)
            if pinned is None:pinned=identity
            elif identity!=pinned:raise RuntimeError('等待期间会话已切换，已停止接入。')
            if guard.ready:return guard
        if clock()>=deadline:raise RuntimeError('30秒内未发现开放的演练。请先在模拟器开始对应演练，再双击接入文件。')
        sleep(.25)

class Tee:
    def __init__(self,console,log,secret):self.console=console;self.log=log;self.secret=secret
    def write(self,text):
        text=text.replace(self.secret,'<redacted>') if self.secret else text
        self.console.write(text);self.log.write(text);self.flush()
        return len(text)
    def flush(self):self.console.flush();self.log.flush()

def execute(problem,config_path=ROOT/'practice.local.json',data=DEFAULT_DATA,
            output_root=MODULE/'results/one_click',timeout=30.,runner=run_robot):
    if problem not in (3,4):raise ValueError('只支持问题3或4演练。')
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder=output_root/(stamp+f'_p{problem}')
    folder.mkdir(parents=True,exist_ok=False)
    record=dict(problem=problem,mode='practice',started=datetime.now(timezone.utc).isoformat(),
                command=['practice_launch.py','--problem',str(problem)],exit_code=1)
    secret=''
    try:
        with one_robot(ROOT/'.practice.lock'):
            secret=robot_id(config_path)
            with (folder/'console.log').open('w',encoding='utf-8') as log:
                with redirect_stdout(Tee(sys.stdout,log,secret)),redirect_stderr(Tee(sys.stderr,log,secret)):
                    print(f'问题{problem}演练：等待接口开放（最长30秒）；请勿切换会话。',flush=True)
                    guard=wait_for_practice(data,timeout)
                    record['journal_name']=guard.journal.parent.name
                    print('已确认演练，机器狗开始自动执行。',flush=True)
                    result_folder,result=runner(['--problem',str(problem),'--strategy','candidate',
                        '--robot-id',secret,'--data',str(data),'--journal',str(guard.journal)])
                    record['result_folder']=str(result_folder)
                    print(f"\n本局结束：清除{result['cleared']}个；虚拟耗时{result['virtual_time_s']:.2f}秒。")
                    official=result.get('simulator_summary')
                    if official:print(f"模拟器确认：{official['cleared_jammer_count']}/{official['jammer_count']}。")
                    print('完整结果：'+str(result_folder))
            record['exit_code']=0
    except KeyboardInterrupt:
        record.update(exit_code=130,error='用户中断；本局执行状态请以模拟器为准，不自动重复进入。')
        print(record['error'],file=sys.stderr)
    except Exception as exc:
        record['error']=f'{type(exc).__name__}: {exc}'.replace(secret,'<redacted>') if secret else f'{type(exc).__name__}: {exc}'
        (folder/'error.txt').write_text(traceback.format_exc().replace(secret,'<redacted>') if secret else traceback.format_exc(),encoding='utf-8')
        print('未继续执行：'+record['error'],file=sys.stderr)
    finally:
        record['finished']=datetime.now(timezone.utc).isoformat()
        (folder/'execution.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return record['exit_code']

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem',required=True,type=int,choices=(3,4))
    parser.add_argument('--check',action='store_true',help='Check local dependencies only; never connect')
    args=parser.parse_args(argv)
    if args.check:
        import numpy,scipy,shapely
        if args.problem == 4:
            sys.path.insert(0, str(REPO / '解题库/第四问/v6'))
            from candidates import make_candidate
            strategy = make_candidate(4)
            print_p4_strategy(p4_strategy_metadata(strategy))
        print(f'问题{args.problem}启动器可用；本次仅检查本机依赖，没有发送任何模拟器请求。')
        return 0
    return execute(args.problem)

if __name__=='__main__':sys.exit(main())
