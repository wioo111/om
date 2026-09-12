"""在用户已经启动的本地演练中运行 v9，并保存实际代码与动作日志。"""
import sys
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='运行第三问 v9；连接已启动的本地演练')
    parser.add_argument('--robot-id', required=True, help='参赛队号')
    parser.add_argument('--base-url', default='http://127.0.0.1:2026', help='本地模拟器地址')
    args = parser.parse_args()
    from collab.live import main
    sys.argv = [sys.argv[0], '--candidate', 'collab.merged_candidate:make_strategy',
                '--robot-id', args.robot_id, '--base-url', args.base_url]
    main()
