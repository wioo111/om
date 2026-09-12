"""只读提取官方证据并逐动作核对 v8；不为改变后的路线编造响应。"""
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from robot_iter import run_with_sim_strategy
from strategy_v8 import AdaptiveV8, distance

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
CASE = 'W3QD-ZG2B-MBCG-39XH'


class ObservedRun:
    def __init__(self, records, count):
        self.records, self.index, self.count = records, 0, count

    def call(self, path, pos=None, ch=None):
        row = self.records[self.index]
        if path != row['path']:
            raise ValueError(f'第 {self.index} 条动作类型不一致: {path} / {row["path"]}')
        if pos is not None:
            request = row['request']
            old = request['position']
            if distance(pos, (old['x'], old['y'])) > 1e-6 or ch != request['channel']:
                raise ValueError(f'第 {self.index} 条动作发生分歧，不能使用原日志作为新路线响应')
        self.index += 1
        return row['response']

    def enter(self):
        return self.call('/enter')

    def exit(self):
        return self.call('/exit')

    def measure(self, x, y, ch):
        return self.call('/measure', (x, y), ch)

    def clear(self, x, y, ch):
        return self.call('/clear', (x, y), ch)

    def stats(self):
        return {'N': self.count}


class RecordedV8(AdaptiveV8):
    def __init__(self):
        super().__init__()
        self.context = []
        self.current_plan = None

    def _cover_route(self, state, known, remaining, n_unknown):
        routes = [self._build_cover_route(state, known, remaining, n_unknown, power)
                  for power in (0.6, 1.0, 1.6)]
        def cost(route):
            previous, value = state.pos, 0.0
            for ch, pos in route:
                value += distance(previous, pos)/5
                if ch < 0:
                    value += 6*n_unknown
                previous = pos
            return value
        route = min(routes, key=cost)
        self.current_plan = {'nodes': [(int(ch), tuple(map(float, pos))) for ch,pos in route],
                             'estimated_cost_s': cost(route)}
        return route[0] if route else None

    def step(self, state):
        self.current_plan = None
        active = self.active_ch
        known = {str(ch): {'estimate': tuple(map(float,t.estimate)), 'radius':float(t.radius),
                          'observations':len(t.records)}
                 for ch,t in self.tracks.items() if ch not in self.cleared}
        action = super().step(state)
        if action.kind != 'done':
            self.context.append({'active_before':active, 'active_after':self.active_ch,
                                 'cleared_before':len(self.cleared), 'known_before':known,
                                 'plan':self.current_plan})
        return action


def main():
    data = WORKSPACE/'Jammers-simulator-win64/Jammers-simulator/JammersSimulatorData'
    db = data/'practice-statistics-queue.sqlite3'
    con = sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory = sqlite3.Row
    columns = ('problem_no,practice_run_no,case_code,end_reason,cleared_jammer_count,'
               'measure_accepted_count,virtual_time_us,program_run_duration_ms,'
               'channel_switch_count,clear_failure_count,jammer_count,state')
    stats = dict(con.execute('SELECT '+columns+' FROM practice_statistics_tasks '
                             'WHERE case_code=? ORDER BY id DESC LIMIT 1',(CASE,)).fetchone())
    con.close()
    metadata_path = data/'behavior-logs'/f'practice-p3-{stats["practice_run_no"]}-{CASE}.result.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    path = ROOT.parent/'v9/results/live_v8_20260912_224809.jsonl'
    original = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    simulator, strategy = ObservedRun(original,stats['jammer_count']), RecordedV8()
    replay = run_with_sim_strategy(strategy,simulator)
    assert simulator.index == len(original)
    assert replay['cleared'] == stats['cleared_jammer_count']
    events, previous, channel = [], (0.0,0.0), 1
    switches = 0
    for row,context in zip([r for r in original if r['path'] in ('/measure','/clear')],strategy.context):
        req, response = row['request'], row['response']
        pos = (req['position']['x'],req['position']['y'])
        leg = distance(previous,pos)
        kind = row['path'][1:]
        if kind == 'measure':
            switches += channel != req['channel']
            channel = req['channel']
        plan = context['plan']
        if kind == 'clear':
            category = 'approach_clear'
        elif plan and plan['nodes'] and plan['nodes'][0][0] < 0:
            category = 'supplementary_search'
        elif context['active_after'] is not None:
            category = 'localization_measure'
        else:
            category = 'station_scan'
        events.append({'index':len(events)+1,'action':kind,'channel':req['channel'],
                       'from':previous,'to':pos,'distance_m':leg,
                       'result':response.get('measure_result',response.get('clear_result')),
                       'bearing_deg':response.get('svd_deg'),'virtual_time_s':response['virtual_time_s'],
                       'category':category,**context})
        previous = pos
    total_distance = sum(e['distance_m'] for e in events)
    non_movement = stats['measure_accepted_count']*5 + switches + stats['cleared_jammer_count']*5 + stats['clear_failure_count']*3
    assert switches == stats['channel_switch_count']
    assert abs(total_distance/5+non_movement-stats['virtual_time_us']/1e6) < 1e-5
    failures, episodes = [], []
    for i,e in enumerate(events):
        if e['result'] != 'no_target_in_range':
            continue
        end = next(j for j in range(i+1,len(events)) if events[j]['channel']==e['channel'] and events[j]['result']=='success')
        recovery = sum(v['distance_m'] for v in events[i+1:end+1])
        failures.append({'index':e['index'],'channel':e['channel'],'approach_m':e['distance_m'],
                         'recovery_m':recovery,'success_index':events[end]['index'],
                         'excess_over_direct_to_success_m':e['distance_m']+recovery-distance(e['from'],events[end]['to'])})
        if not episodes or episodes[-1]['success_index'] < e['index']:
            episodes.append(failures[-1])
    clear_nodes = [(e['channel'],e['to']) for e in events if e['result']=='success']
    clear_order_length = distance((0,0),clear_nodes[0][1])+sum(distance(a[1],b[1]) for a,b in zip(clear_nodes,clear_nodes[1:]))
    route = AdaptiveV8._route((0,0),clear_nodes)
    offline_clear_length = distance((0,0),route[0][1])+sum(distance(a[1],b[1]) for a,b in zip(route,route[1:]))
    summary = {'case_code':CASE,'official_statistics':stats,'official_metadata':metadata,
               'original_strategy_behavior':'AdaptiveV8','matched_requests':len(original),
               'algorithm_stop_reason':replay['stop_reason'],
               'source_sha256':hashlib.sha256((ROOT/'strategy_v8.py').read_bytes()).hexdigest(),
               'http_log_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
               'distance_m':total_distance,'movement_s':total_distance/5,'non_movement_s':non_movement,
               'mean_s':stats['virtual_time_us']/1e6/stats['jammer_count'],
               'movement_fraction':total_distance/5/(stats['virtual_time_us']/1e6),
               'distance_by_category':{k:sum(e['distance_m'] for e in events if e['category']==k) for k in sorted({e['category'] for e in events})},
               'longest_legs':sorted([{k:e[k] for k in ('index','action','channel','distance_m','result','category','from','to')} for e in events],key=lambda e:e['distance_m'],reverse=True)[:12],
               'failures':failures,'nonoverlapping_failure_excess_m':sum(e['excess_over_direct_to_success_m'] for e in episodes),
               'recorded_clear_order_length_m':clear_order_length,'posthoc_reordered_clear_positions_length_m':offline_clear_length,
               'posthoc_clear_order_gain_m':clear_order_length-offline_clear_length,
               'measurement_search_distance_above_clear_polyline_m':total_distance-clear_order_length,
               'posthoc_caveat':'仅对已记录成功清除位置的事后几何分析，未计探测与信息约束，不能作为新策略成绩。',
               'conditional_10km_mean_s':(10000/5+non_movement)/stats['jammer_count']}
    (ROOT/'evidence/official_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'evidence/official_actions.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
