"""从已经完成的结果生成路线专项报告，不再运行策略或调用模拟器。"""
import json
from pathlib import Path
import statistics

from benchmark_routes import paired
from evaluate_v8 import summarize

ROOT = Path(__file__).resolve().parent


def mean(rows, key):
    return statistics.mean(r[key] for r in rows)


def main():
    report = json.loads((ROOT / 'results/holdout_01/report.json').read_text(encoding='utf-8'))
    development = json.loads((ROOT / 'results/development_01/report.json').read_text(encoding='utf-8'))
    rows = report['records']
    sources15 = [{**r, 'group': 'N15_all'} for r in rows if r['N'] == 15 and r['group'] != 'stress']
    n15 = {name: summarize([r for r in sources15 if r['strategy'] == name]) for name in ('v8', 'route')}
    n15_paired = paired(sources15, 'route', 'N15_all')
    main_pair = report['paired']['route']['main']
    candidate = [r for r in rows if r['strategy'] == 'route']
    complete = all(r['cleared'] == r['N'] and not r['error'] and r['coverage_complete'] for r in candidate)
    supported = complete and main_pair['mean_delta_ci95_normal'][1] < 0
    main_new = report['summary']['route']['main']
    goal = complete and 180 <= main_new['avg_time_per_cleared_mean'] <= 220
    decision = dict(candidate='RouteV10', full_clear_all=complete,
                    promotion='not_promoted_keep_v8', default_strategy='AdaptiveV8',
                    main_improvement_supported_by_paired_normal_ci95=supported,
                    main_goal_180_220_mean_met=goal,
                    mean_goal_s=200, n15=n15, n15_paired=n15_paired,
                    official_v10_retested=False,
                    previous_official_score=dict(strategy='AdaptiveV8',case='W3QD-ZG2B-MBCG-39XH',mean_s=203.10944306666667),
                    code_sha256=report['code_sha256'])
    (ROOT / 'results/decision.json').write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding='utf-8')
    def f(value):
        return f'{value:.2f}'
    main_old = report['summary']['v8']['main']
    pct = -main_pair['mean_delta_s'] / main_old['avg_time_per_cleared_mean'] * 100
    conclusion = ('独立主场景支持路线改动带来平均时间改善。' if supported else
                  '独立主场景尚不足以确认平均时间改善，不宣称本版稳定优于 v8。')
    lines = ['# 第三问 v10 路线专项验证', '', conclusion,
             '**交付决定：v8 继续作为统一入口的默认策略，v10 仅作为显式可选的路线候选。未达到稳定 200 s/个的目标。**',
             f'两版各完成 114 局新场景；v10 全部清除且无异常：{complete}。',
             f'主场景平均达到 180–220 s/个：{goal}。本版未重新运行官方演练。', '',
             '## 统一对照结果', '',
             '每个场景使用同一组源位置、频道、接收半径与固定空间误差设置，比较整轮结束后的总虚拟时间。统计量是各局“总时间/成功清除数”的平均，失败或未完成场景不静默丢弃。', '',
             '| 场景组 | 每版局数 | v8 均值/s | v10 均值/s | v8 P95/s | v10 P95/s | v10 全清 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    pairs = [('均衡主场景 N=10–16', report['summary']['v8']['main'], main_new),
             ('N=15 专项（含主场景中 10 局）', n15['v8'], n15['route']),
             ('边界压力场景', report['summary']['v8']['stress'], report['summary']['route']['stress'])]
    for label, old, new in pairs:
        lines.append(f'| {label} | {new["rounds"]} | {f(old["avg_time_per_cleared_mean"])} | {f(new["avg_time_per_cleared_mean"])} | {f(old["avg_time_p95"])} | {f(new["avg_time_p95"])} | {new["full_clear_rate"]:.0%} |')
    lines += ['', 'N=15 专项由均衡主场景中的 10 局加预先指定的额外 20 局组成，与第一行存在 10 局重叠；不能把三行局数直接相加。独立场景共 70+20+24=114 局，两版共 228 次完整运行。', '',
              f'主场景每个源平均变化为 {main_pair["mean_delta_s"]:+.2f} s，相对 v8 改善 {pct:.2f}%；成对差值的近似 95% 正态置信区间为 [{f(main_pair["mean_delta_ci95_normal"][0])}, {f(main_pair["mean_delta_ci95_normal"][1])}] s。',
              f'其中 {main_pair["improved_rounds"]} 局改善，{main_pair["worse_rounds"]} 局变慢；最大单局退步为 {f(main_pair["worst_regression_s"])} s/个。',
              f'N=15 的成对平均变化为 {n15_paired["mean_delta_s"]:+.2f} s/个，近似 95% 区间 [{f(n15_paired["mean_delta_ci95_normal"][0])}, {f(n15_paired["mean_delta_ci95_normal"][1])}] s。', '',
              '上述区间描述本地随机场景下的平均差值，不是下一轮官方案例的预测区间，也不表示每一局都会加快。', '',
              '## 路程和操作成本', '',
              '| 主场景每局平均 | v8 | v10 | v10 − v8 |',
              '|---|---:|---:|---:|']
    groups = {name: [r for r in rows if r['strategy'] == name and r['group'] == 'main'] for name in ('v8', 'route')}
    for title, key in [('移动距离/m', 'distance_m'), ('检测次数', 'measure_count'), ('清除失败次数', 'clear_fail_count')]:
        old, new = mean(groups['v8'], key), mean(groups['route'], key)
        lines.append(f'| {title} | {f(old)} | {f(new)} | {new-old:+.2f} |')
    for title, key in [('移动时间/s', 'move_time_s'), ('检测时间/s', 'measure_time_s'), ('切频时间/s', 'switch_time_s'), ('清除时间/s', 'clear_time_s')]:
        old, new = (statistics.mean(r['time_breakdown'][key] for r in groups[name]) for name in ('v8', 'route'))
        lines.append(f'| {title} | {f(old)} | {f(new)} | {new-old:+.2f} |')
    lines += ['', '路线改变会同时改变观测位置和检测次数，所以验收使用完整虚拟总时间，不只比较规划折线。', '',
              '## 开发筛选与冻结', '',
              '首轮筛选两项路线改动，定位、清除和搜索完成判断均保持 v8。21 局旧开发集只用于选择候选，未混入独立成绩。首个候选的独立验证不足以确认改善后，又做了两个有明确机制的补充开发对照；均未超过首候选的开发表现，未追加独立测试或更改已报告的独立成绩。', '',
              '| 开发候选 | 21 局均值/s | 相对 v8 距离变化/m·局⁻¹ | 处理 |',
              '|---|---:|---:|---|']
    for name, label, action in [('route', '改善访问顺序', '冻结后进入独立测试'), ('cautious', '访问顺序 + 位置不确定性折减预测覆盖', '不采用')]:
        lines.append(f'| {label} | {f(development["summary"][name]["main"]["avg_time_per_cleared_mean"])} | {f(development["paired"][name]["main"]["distance_delta_m"])} | {action} |')
    for folder, name, label in [('development_02', 'reactive', '测准后允许重新选择行程目标'),
                                 ('development_03', 'guarded', '保留搜索站位，仅调整最终访问顺序')]:
        trial = json.loads((ROOT / f'results/{folder}/report.json').read_text(encoding='utf-8'))
        for filename in ('strategy_v8.py', 'mock_simulator.py', 'robot_iter.py', 'strategy.py', 'problem1_v4_inline.py'):
            assert trial['code_sha256'][filename] == development['code_sha256'][filename]
        base_rows = [r for r in development['records'] if r['strategy'] == 'v8']
        comparison = paired(base_rows + trial['records'], name, 'main')
        trial_mean = trial['summary'][name]['main']['avg_time_per_cleared_mean']
        lines.append(f'| {label} | {f(trial_mean)} | {f(comparison["distance_delta_m"])} | 不采用 |')
    lines += ['', '独立测试期间没有修改候选源码；结果保存运行前快照并在完成时核对哈希。压力场景覆盖固定点误差、整场偏差、连续空间偏差及误差端点，源数 10/13/16，接收半径固定在 1000/1500 m。', '',
              '## 实现与范围', '',
              'v10 仅覆盖 v8 的 `_route`。对不超过 13 个固定规划点用动态规划求最短开放路径；较大点集保留已有顺序并进行多起点与连续点重插入搜索。起点固定，终点不要求返回原点。规划点仍由 v8 生成，覆盖证明仍只来自实际检测。', '',
              '最短路径求解已在 2–7 点共 6 组实例上与穷举结果逐一比对；13/16/20 点检查完整访问与计算耗时。检查了候选 RouteV10 的定位、测量、清除、失败恢复、停止及兜底搜索仍继承 v8。运行入口已用 `--check` 验证，只检查版本，不访问官方接口。', '',
              '## 官方结果的归属与限制', '',
              '已完成的官方案例 W3QD-ZG2B-MBCG-39XH 为 v8 行为：15/15 全清，203.11 s/个，移动 11743.21 m。124 个 HTTP 请求与 v8 完整回放一致。不能将该成绩算作 v10，也不能把事后重排清除点的 9806.39 m 写成新策略已实现的官方路线。', '',
              '详细官方数据和五次失败清除分析见 `../evidence/官方演练与路线分析.md`。本地测试结果与官方单案例来自不同场景，不作直接胜负比较。', '',
              '## 可复现文件', '',
              '- `holdout_cases.json`：独立场景清单和生成种子。',
              '- `holdout_01/report.json`：完整逐局数据、分组统计和源码哈希。',
              '- `holdout_01/source/`：本次实际执行的冻结源码。',
              '- `holdout_01/worst_v8.json`、`worst_route.json`：最慢场景动作记录。',
              '- `decision.json`：是否全清、是否支持平均改善、是否达到 180–220 s 的机器可读结论。',
              '- `development_01/report.json`：开发筛选数据。', '']
    (ROOT / 'results/路线专项验证.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(full_clear=complete, improvement_supported=supported, goal_met=goal,
                          main=main_new, paired=main_pair, n15=n15, n15_paired=n15_paired), ensure_ascii=False))


if __name__ == '__main__':
    main()
