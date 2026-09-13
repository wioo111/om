"""Post-hoc route diagnosis from existing Hunt action logs; never a simulator run.

The reduced routing problem deliberately knows later successful-clear points.
Its heuristic routes are NOT executable-policy acceptance or a physical lower
bound. Only the MST value is a lower bound for the stated fixed node set.
"""
import ast
from collections import Counter
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import statistics
import time

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'p4_route_diagnosis_round2_results.json'
ORIGIN = (0.0, 0.0)
OPTICAL_R = 19.99999


def path_distance(points, start=ORIGIN):
    return sum(math.dist(a, b) for a, b in zip([start] + list(points), points))


def load_frozen_geometry():
    source = HERE / 'hunt_round' / 'confirmation01' / 'source'
    spec = importlib.util.spec_from_file_location('p4_diagnosis_frozen_geometry', source / 'problem1_v4_inline.py')
    p1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p1)
    # Load only the frozen pure coverage function, without any strategy chain.
    tree = ast.parse((source / 'strategy_cost.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'optical_cover')
    namespace = dict(math=math, itertools=itertools, Point=Point, unary_union=unary_union,
                     OPTICAL_R=OPTICAL_R, distance=math.dist)
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'frozen_optical_cover', 'exec'), namespace)
    return p1, namespace['optical_cover']


def node_set(scan, success):
    return list(dict.fromkeys([ORIGIN] + scan + success))


def improve_open(route, matrix, max_passes=40):
    """Fixed origin 0; deterministic 2-opt plus relocation, bounded iterations."""
    route = list(route)
    n = len(route)
    for _ in range(max_passes):
        best, operation = 1e-7, None
        for i in range(n - 1):
            previous = route[i - 1] if i else 0
            for j in range(i + 1, n):
                gain = matrix[previous][route[i]] - matrix[previous][route[j]]
                if j + 1 < n:
                    gain += matrix[route[j]][route[j + 1]] - matrix[route[i]][route[j + 1]]
                if gain > best:
                    best, operation = gain, ('reverse', i, j)
        for i, node in enumerate(route):
            previous = route[i - 1] if i else 0
            nxt = route[i + 1] if i + 1 < n else None
            saving = matrix[previous][node]
            if nxt is not None:
                saving += matrix[node][nxt] - matrix[previous][nxt]
            reduced = route[:i] + route[i + 1:]
            for gap in range(n):
                if gap == i:
                    continue
                a = reduced[gap - 1] if gap else 0
                b = reduced[gap] if gap < n - 1 else None
                added = matrix[a][node]
                if b is not None:
                    added += matrix[node][b] - matrix[a][b]
                if saving - added > best:
                    best, operation = saving - added, ('relocate', i, gap)
        if operation is None:
            break
        kind, i, j = operation
        if kind == 'reverse':
            route[i:j + 1] = reversed(route[i:j + 1])
        else:
            route.insert(j, route.pop(i))
    return route


def fixed_scan_insert(scan, success):
    route = list(dict.fromkeys(scan))
    if route and route[0] == ORIGIN:
        route.pop(0)
    remaining = [p for p in dict.fromkeys(success) if p not in route and p != ORIGIN]
    while remaining:
        choices = []
        for node in remaining:
            for gap in range(len(route) + 1):
                a = route[gap - 1] if gap else ORIGIN
                b = route[gap] if gap < len(route) else None
                cost = math.dist(a, node)
                if b is not None:
                    cost += math.dist(node, b) - math.dist(a, b)
                choices.append((cost, node, gap))
        _, node, gap = min(choices)
        route.insert(gap, node)
        remaining.remove(node)
    return route


def relaxed_routes(scan, success, chronological):
    points = node_set(scan, success)
    ids = {p: i for i, p in enumerate(points)}
    matrix = [[math.dist(a, b) for b in points] for a in points]
    insertion = fixed_scan_insert(scan, success)
    starts = [list(dict.fromkeys(ids[p] for p in chronological if p != ORIGIN)),
              [ids[p] for p in insertion]]
    for first in sorted(range(1, len(points)), key=lambda i: (matrix[0][i], i))[:4]:
        route, remaining = [first], set(range(1, len(points))) - {first}
        while remaining:
            node = min(remaining, key=lambda i: (matrix[route[-1]][i], i))
            route.append(node)
            remaining.remove(node)
        starts.append(route)
    candidates = [improve_open(route, matrix) for route in starts]
    best = min(candidates, key=lambda route: sum(matrix[a][b] for a, b in zip([0] + route, route)))
    # Prim MST is a valid lower bound for any open tour through these nodes.
    unused, visited, mst = set(range(1, len(points))), {0}, 0.0
    while unused:
        length, node = min((matrix[a][b], b) for a in visited for b in unused)
        mst += length
        unused.remove(node)
        visited.add(node)
    return dict(required_nodes=len(points), scan_nodes=len(set(scan)),
                clear_success_nodes=len(set(success)),
                fixed_scan_cheapest_insertion_m=path_distance(insertion),
                hindsight_nn_2opt_relocate_m=path_distance([points[i] for i in best]),
                fixed_nodes_mst_lower_bound_m=mst,
                hindsight_route=[points[i] for i in best])


def motion_decomposition(actions):
    scan_indices = [i for i, a in enumerate(actions) if a['action'] == 'measure' and a['stage'] == 'discovery']
    scan_points = [tuple(actions[i]['pos']) for i in scan_indices]
    backbone = path_distance(scan_points)
    previous_index, previous_pos = -1, ORIGIN
    gaps, excess = [], 0.0
    for scan_index in scan_indices:
        endpoint = tuple(actions[scan_index]['pos'])
        between = actions[previous_index + 1:scan_index]
        points = [tuple(a['pos']) for a in between] + [endpoint]
        actual = path_distance(points, previous_pos)
        direct = math.dist(previous_pos, endpoint)
        added = max(0.0, actual - direct)
        if between:
            gaps.append(dict(left_index=previous_index, right_index=scan_index,
                             start=previous_pos, end=endpoint, channels=sorted({a['ch'] for a in between}),
                             action_count=len(between), actual_m=actual, backbone_m=direct,
                             excess_m=added, excess_s=added / 5.0,
                             outbound_m=math.dist(previous_pos, tuple(between[0]['pos'])),
                             return_to_scan_m=math.dist(tuple(between[-1]['pos']), endpoint),
                             actions=[dict(index=previous_index + 1 + j, action=a['action'], ch=a['ch'],
                                           result=a['result'], pos=a['pos'], stage=a['stage'])
                                      for j, a in enumerate(between)]))
        excess += added
        previous_index, previous_pos = scan_index, endpoint
    tail = actions[previous_index + 1:]
    tail_m = path_distance([tuple(a['pos']) for a in tail], previous_pos)
    actual_m = sum(a['cost']['move_time_s'] * 5.0 for a in actions)
    assert abs(backbone + excess + tail_m - actual_m) < 1e-5
    # All full-station boundaries, including final open tail, for later diagnostics.
    visits = []
    for index in scan_indices:
        point = tuple(actions[index]['pos'])
        if visits and visits[-1]['pos'] == point:
            visits[-1]['index'] = index
        else:
            visits.append(dict(index=index, pos=point))
    intervals = [dict(left_index=a['index'], right_index=b['index'], start=a['pos'], end=b['pos'])
                 for a, b in zip(visits, visits[1:])]
    if visits:
        intervals.append(dict(left_index=visits[-1]['index'], right_index=len(actions),
                              start=visits[-1]['pos'], end=None))
    return dict(actual_m=actual_m, fixed_scan_backbone_m=backbone,
                scan_gap_detour_excess_m=excess, final_localization_tail_m=tail_m,
                decomposition_residual_m=actual_m - backbone - excess - tail_m,
                scan_points=list(dict.fromkeys(scan_points)), gaps=gaps,
                final_tail_actions=[dict(index=previous_index + 1 + j, **a) for j, a in enumerate(tail)],
                intervals=intervals)


def information_snapshots(actions, p1):
    records, failed, near, snapshots = {}, {}, {}, {}
    for index, action in enumerate(actions):
        ch, pos = action['ch'], tuple(action['pos'])
        updated = False
        if action['action'] == 'measure' and action['result'] == 'direction':
            rows = records.setdefault(ch, [])
            if all(math.dist(pos, p) > 1e-6 for p, _ in rows):
                rows.append((pos, action['svd_deg']))
                updated = True
        elif action['action'] == 'measure' and action['result'] == 'near':
            near[ch] = pos
            updated = True
        elif action['action'] == 'clear' and action['result'] == 'no_target_in_range':
            failed.setdefault(ch, []).append(pos)
            updated = True
        if not updated:
            continue
        region = None
        if ch in near:
            region = Point(near[ch]).buffer(5.0 / math.cos(math.pi / 128.0), quad_segs=32)
        elif len(records.get(ch, [])) >= 2:
            positions, angles = zip(*records[ch])
            poly = p1.localization_polygon(positions, angles, eps_deg=1.0050001,
                                           R_eff=1500.0, R_target=1800.0, N_disk=64)
            if poly and len(poly) >= 3:
                candidate = Polygon(poly)
                if candidate.is_valid and not candidate.is_empty:
                    region = candidate
        if region is not None:
            for miss in failed.get(ch, []):
                region = region.difference(Point(miss).buffer(OPTICAL_R, quad_segs=32))
            if region.is_empty:
                raise RuntimeError(f'Existing evidence inconsistent: ch={ch}, index={index}')
        snapshots.setdefault(ch, []).append(dict(index=index, region=region,
                                                  positive_positions=len(records.get(ch, [])),
                                                  failed_clears=len(failed.get(ch, []))))
    return snapshots


def covered(region, disks):
    return region is not None and not region.is_empty and region.difference(disks).is_empty


def insertion_cost(points, interval):
    best = None
    for route in itertools.permutations(points):
        length = path_distance(route, interval['start'])
        if interval['end'] is not None:
            length += math.dist(route[-1], interval['end']) - math.dist(interval['start'], interval['end'])
        cost = length / 5.0 + 3.0 * (len(route) - 1) + 5.0
        if best is None or cost < best['worst_case_s']:
            best = dict(worst_case_s=cost, points=list(route), scan_gap_left_index=interval['left_index'],
                        scan_gap_right_index=interval['right_index'])
    return best


def clear_readiness(actions, intervals, p1, optical_cover):
    snapshots = information_snapshots(actions, p1)
    batches, per_action = [], []
    index = 0
    while index < len(actions):
        if actions[index]['action'] != 'clear':
            index += 1
            continue
        ch, first = actions[index]['ch'], index
        while index < len(actions) and actions[index]['action'] == 'clear' and actions[index]['ch'] == ch:
            index += 1
        last = index - 1
        attempts = actions[first:index]
        history = [s for s in snapshots.get(ch, []) if s['index'] < first]
        region = history[-1]['region'] if history else None
        before = tuple(actions[first - 1]['pos']) if first else ORIGIN
        actual_points = [tuple(a['pos']) for a in attempts]
        union = unary_union([Point(p).buffer(OPTICAL_R, quad_segs=32) for p in actual_points])
        if covered(region, union):
            plan = dict(points=actual_points)
            origin = 'actual_executed_points_cover_complete_region'
        else:
            plan = optical_cover(region, before, limit=6) if region is not None else None
            origin = 'reconstructed_complete_plan_from_preclear_observations' if plan else 'no_complete_plan_reconstructed'
        points = [tuple(p) for p in plan['points']] if plan else []
        all_disks = unary_union([Point(p).buffer(OPTICAL_R, quad_segs=32) for p in points]) if points else None
        ready = next((s['index'] for s in history if all_disks is not None and covered(s['region'], all_disks)), None)
        earlier, later = [], []
        if ready is not None:
            for interval in intervals:
                if interval['left_index'] < ready:
                    continue
                choice = insertion_cost(points, interval)
                if interval['right_index'] <= first:
                    earlier.append(choice)
                if interval['left_index'] >= last:
                    later.append(choice)
        after = tuple(actions[index]['pos']) if index < len(actions) else None
        actual_marginal_m = path_distance(actual_points, before)
        if after is not None:
            actual_marginal_m += math.dist(actual_points[-1], after) - math.dist(before, after)
        clear_cost = sum(a['cost']['clear_time_s'] for a in attempts)
        batch = dict(ch=ch, first_action_index=first, last_action_index=last,
                     executed_attempts=len(attempts), full_plan_points=len(points),
                     reconstructed_plan_origin=origin, first_information_ready_index=ready,
                     actual_marginal_move_m=max(0.0, actual_marginal_m), actual_clear_cost_s=clear_cost,
                     actual_marginal_total_s=actual_marginal_m / 5.0 + clear_cost,
                     best_earlier_gap=min(earlier, key=lambda row: row['worst_case_s']) if earlier else None,
                     best_later_gap=min(later, key=lambda row: row['worst_case_s']) if later else None,
                     full_plan=points)
        for action_index in range(first, index):
            action = actions[action_index]
            disk = Point(action['pos']).buffer(OPTICAL_R, quad_segs=32)
            available = [s for s in snapshots.get(ch, []) if s['index'] < action_index]
            guaranteed = next((s['index'] for s in available if covered(s['region'], disk)), None)
            per_action.append(dict(ch=ch, action_index=action_index, result=action['result'],
                                   single_clear_certified_before_action=guaranteed is not None,
                                   earliest_single_clear_certificate_index=guaranteed,
                                   complete_plan_ready_index=ready,
                                   belongs_to_complete_plan=bool(points),
                                   earlier_scan_gap_available=bool(earlier), later_scan_gap_available=bool(later)))
        batches.append(batch)
    return batches, per_action


def operational_diagnostics(case, actions):
    """Explain null observations and distinguish tail transit from local probing."""
    n = case['scenario']['N']
    observed = {a['ch'] for a in actions if a['result'] in ('direction', 'near')}
    never_observed = set(range(1, 21)) - observed
    absent_measurements = [a for a in actions if a['action'] == 'measure' and a['ch'] in never_observed]
    absent_nonmove = sum(a['cost']['measure_time_s'] + a['cost']['switch_time_s'] for a in absent_measurements)
    per_channel = {}
    last_scan = case['movement_decomposition']['intervals'][-1]['left_index']
    batches = {b['ch']: b for b in case['clear_batches']}
    previous_ch = None
    for action in case['movement_decomposition']['final_tail_actions']:
        ch = action['ch']
        row = per_channel.setdefault(ch, dict(move_s=0.0, approach_s=0.0, within_task_move_s=0.0,
                                              local_measurements=0, local_no_signal=0,
                                              clear_attempts=0, full_plan_ready_before_final_scan=False))
        move = action['cost']['move_time_s']
        row['move_s'] += move
        row['approach_s' if previous_ch != ch else 'within_task_move_s'] += move
        row['local_measurements'] += action['action'] == 'measure'
        row['local_no_signal'] += action['action'] == 'measure' and action['result'] == 'no_signal'
        row['clear_attempts'] += action['action'] == 'clear'
        ready = batches[ch]['first_information_ready_index']
        row['full_plan_ready_before_final_scan'] = ready is not None and ready <= last_scan
        previous_ch = ch
    return dict(never_observed_channels=sorted(never_observed),
                no_signal_count=sum(a['result'] == 'no_signal' for a in actions),
                no_signal_on_never_observed_channel=len(absent_measurements),
                no_signal_on_later_observed_channel=sum(a['result'] == 'no_signal' and a['ch'] in observed for a in actions),
                absence_detection_and_switch_s_per_N=absent_nonmove / n,
                fixed_scan_and_absence_only_floor_s_per_N=case['scan_backbone_s_per_N'] + absent_nonmove / n,
                unchanged_scan_and_all_nonmovement_floor_s_per_N=case['actual_T_per_N'] - case['scan_detour_s_per_N'] - case['final_tail_s_per_N'],
                tail_task_approach_s_per_N=sum(v['approach_s'] for v in per_channel.values()) / n,
                tail_within_task_move_s_per_N=sum(v['within_task_move_s'] for v in per_channel.values()) / n,
                tail_move_for_already_certifiable_tasks_s_per_N=sum(v['move_s'] for v in per_channel.values() if v['full_plan_ready_before_final_scan']) / n,
                tail_move_for_tasks_needing_late_information_s_per_N=sum(v['move_s'] for v in per_channel.values() if not v['full_plan_ready_before_final_scan']) / n,
                tail_channels=per_channel)


def diagnose(path, p1, optical_cover):
    raw = path.read_bytes()
    data = json.loads(raw)
    summary, actions = data['summary'], data['actions']
    n = summary['scenario']['N']
    motion = motion_decomposition(actions)
    success = [tuple(a['pos']) for a in actions if a['action'] == 'clear' and a['result'] == 'success']
    chronological = [tuple(a['pos']) for a in actions if (a['action'] == 'measure' and a['stage'] == 'discovery')
                     or (a['action'] == 'clear' and a['result'] == 'success')]
    routing = relaxed_routes(motion['scan_points'], success, chronological)
    nonmove = summary['virtual_time_s'] - motion['actual_m'] / 5.0
    routing.update(hindsight_nonmoving_costs_held_fixed_s=nonmove,
                   hindsight_T_per_N=(nonmove + routing['hindsight_nn_2opt_relocate_m'] / 5.0) / n,
                   hindsight_saving_s_per_N=(motion['actual_m'] - routing['hindsight_nn_2opt_relocate_m']) / (5.0 * n),
                   fixed_scan_insertion_saving_s_per_N=(motion['actual_m'] - routing['fixed_scan_cheapest_insertion_m']) / (5.0 * n),
                   conditional_mst_maximum_saving_s_per_N=(motion['actual_m'] - routing['fixed_nodes_mst_lower_bound_m']) / (5.0 * n))
    batches, per_clear = clear_readiness(actions, motion['intervals'], p1, optical_cover)
    readiness = Counter()
    for row in per_clear:
        readiness['actions'] += 1
        readiness['individually_certified'] += row['single_clear_certified_before_action']
        readiness['in_complete_plan'] += row['belongs_to_complete_plan']
        readiness['earlier_gap_available'] += row['earlier_scan_gap_available']
        readiness['later_gap_available'] += row['later_scan_gap_available']
    earlier_savings, later_savings = [], []
    for batch in batches:
        for field, collection in (('best_earlier_gap', earlier_savings), ('best_later_gap', later_savings)):
            if batch[field] is not None:
                collection.append(max(0.0, batch['actual_marginal_total_s'] - batch[field]['worst_case_s']))
    result = dict(input_file=path.relative_to(HERE).as_posix(), input_sha256=hashlib.sha256(raw).hexdigest(),
                  scenario=summary['scenario'], accepted_run=summary['accepted_run'],
                  actual_T=summary['virtual_time_s'], actual_T_per_N=summary['T_per_N'],
                  measure_count=summary['measure_count'], clear_fail_count=summary['clear_fail_count'],
                  cost=summary['time_breakdown'], recorded_stage_costs=summary['stage_costs'],
                  scan_backbone_s_per_N=motion['fixed_scan_backbone_m'] / (5.0 * n),
                  scan_detour_s_per_N=motion['scan_gap_detour_excess_m'] / (5.0 * n),
                  final_tail_s_per_N=motion['final_localization_tail_m'] / (5.0 * n),
                  movement_decomposition=motion, relaxed_routing=routing,
                  clear_information_summary=dict(readiness), clear_batches=batches, clear_actions=per_clear,
                  nonadditive_independent_earlier_gap_saving_sum_s_per_N=sum(earlier_savings) / n,
                  nonadditive_independent_later_gap_saving_sum_s_per_N=sum(later_savings) / n)
    result['operational_diagnostics'] = operational_diagnostics(result, actions)
    return result


def aggregate(rows):
    keys = ('actual_T_per_N', 'scan_backbone_s_per_N', 'scan_detour_s_per_N', 'final_tail_s_per_N',
            'nonadditive_independent_earlier_gap_saving_sum_s_per_N',
            'nonadditive_independent_later_gap_saving_sum_s_per_N')
    output = dict(cases=len(rows), actual_all_accepted=all(row['accepted_run'] for row in rows),
                  means={key: statistics.mean(row[key] for row in rows) for key in keys})
    for key in ('hindsight_T_per_N', 'hindsight_saving_s_per_N', 'fixed_scan_insertion_saving_s_per_N',
                'conditional_mst_maximum_saving_s_per_N'):
        output['means'][key] = statistics.mean(row['relaxed_routing'][key] for row in rows)
    output['clear_information'] = dict(sum((Counter(row['clear_information_summary']) for row in rows), Counter()))
    for key in ('absence_detection_and_switch_s_per_N', 'fixed_scan_and_absence_only_floor_s_per_N',
                'unchanged_scan_and_all_nonmovement_floor_s_per_N', 'tail_task_approach_s_per_N',
                'tail_within_task_move_s_per_N', 'tail_move_for_already_certifiable_tasks_s_per_N',
                'tail_move_for_tasks_needing_late_information_s_per_N'):
        output['means'][key] = statistics.mean(row['operational_diagnostics'][key] for row in rows)
    return output


def recommendations(rows):
    means = aggregate(rows)['means']
    return [
        dict(priority=1, direction='Jointly route all currently certified clears with remaining real scan stations',
             implementable_without_future_truth=True,
             change='Use complete finite optical plans as tasks with entry and exit costs. Compare the entire remaining route, including the eventual tail, rather than requiring each immediate insertion to stay below 160 seconds.',
             measured_tail_already_certifiable_budget_s_per_N=means['tail_move_for_already_certifiable_tasks_s_per_N'],
             potential_kind='Budget currently spent; not guaranteed recoverable savings',
             example=dict(seed=953131, ch=14, first_proof_action=238, executed_clear_action=294,
                          earlier_gap=[252, 264], earlier_worst_cost_s=142.813590559686,
                          actual_tail_task_marginal_s=538.994567537901, isolated_retrospective_saving_s_per_N=30.475459767554995)),
        dict(priority=2, direction='Bring the second positive observation forward for unresolved one-bearing sources',
             implementable_without_future_truth=True,
             change='Add bounded positive-only local tasks to the same route planner while passing nearby; preserve actual scan obligations and use no_signal only as a failed attempt, never a spatial exclusion.',
             measured_tail_not_yet_certifiable_budget_s_per_N=means['tail_move_for_tasks_needing_late_information_s_per_N'],
             measured_tail_intra_task_move_s_per_N=means['tail_within_task_move_s_per_N'],
             potential_kind='Existing late-task motion budget; requires development validation, may increase cost',
             example=dict(seed=953006, N=10, final_tail_s_per_N=257.66141559583434,
                          comment='Most tail channels still need an additional positive observation, so changing the clear threshold alone cannot remove this tail.')),
        dict(priority=3, direction='Reduce actually required discovery/absence work to reach low-N targets',
             implementable_without_future_truth=True,
             change='Use new continuous coverage certificates for shorter actual routes or valid per-channel station omission. Reordering the unchanged mandatory points cannot remove the low-N discovery burden.',
             all_case_hindsight_route_T_per_N=means['hindsight_T_per_N'],
             all_case_conditional_fixed_node_MST_floor_T_per_N=means['actual_T_per_N']-means['conditional_mst_maximum_saving_s_per_N'],
             all_case_fixed_scan_and_absence_only_floor_s_per_N=means['fixed_scan_and_absence_only_floor_s_per_N'],
             potential_kind='Conditional diagnosis under unchanged station/clear-point and cost assumptions; not a global impossibility theorem'),
    ]


def main():
    if OUTPUT.exists():
        raise SystemExit('Existing diagnosis retained; do not overwrite result evidence')
    started = time.monotonic()
    p1, optical_cover = load_frozen_geometry()
    paths = sorted((HERE / 'hunt_round' / 'confirmation01' / 'runs').glob('*_HuntP4.json'))
    paths += sorted((HERE / 'hunt_round' / 'boundary01' / 'runs').glob('*_HuntP4.json'))
    assert len(paths) == 168
    rows = []
    for index, path in enumerate(paths, 1):
        row = diagnose(path, p1, optical_cover)
        rows.append(row)
        if index % 28 == 0:
            print(f'{index}/{len(paths)} existing logs diagnosed', flush=True)
    selected = {}
    low = [row for row in rows if row['scenario']['N'] == 10]
    for label, group in [('confirmation_lowN_worst', [r for r in low if '/confirmation01/' in r['input_file']]),
                         ('boundary1000_lowN_worst', [r for r in low if r['scenario']['reception_range'] == [1000, 1000]]),
                         ('boundary1500_lowN_worst', [r for r in low if r['scenario']['reception_range'] == [1500, 1500]])]:
        selected[label] = max(group, key=lambda row: row['actual_T_per_N'])['scenario']['seed']
    for n in (10, 13, 16):
        group = sorted((r for r in rows if r['scenario']['N'] == n), key=lambda row: row['actual_T_per_N'])
        selected[f'N{n}_median_typical'] = group[len(group) // 2]['scenario']['seed']
    output = dict(kind='posthoc_existing_log_diagnosis_only', simulator_runs=0,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  limitations=[
                      'Successful-clear points are retrospective mandatory nodes; their future locations cannot be fed to an online strategy.',
                      'The heuristic TSP value is a feasible route for a relaxed fixed-node problem, not a proven lower bound or deployable performance.',
                      'MST gives only a conditional fixed-node route lower bound; real strategies may use different clear locations and must retain observation prerequisites.',
                      'Local measurement sites and failed-clear sites are omitted from the relaxed node set; current nonmovement charges are held fixed only for accounting.',
                      'Same-plan earlier certificates prove information sufficiency for those retrospective points, not that the earlier planner would choose those points.',
                      'Independent best-gap savings overlap and are explicitly not additive or acceptance evidence.',
                      'Later scheduling preserves current logged scan points hypothetically; altered measurement replies and queues require actual offline development validation.',
                  ],
                  summary=aggregate(rows), by_N={str(n): aggregate([r for r in rows if r['scenario']['N'] == n]) for n in range(10, 17)},
                  recommendations=recommendations(rows), selected_cases=selected, cases=rows, runtime_s=time.monotonic() - started)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(output=str(OUTPUT), summary=output['summary'], selected_cases=selected,
                          runtime_s=output['runtime_s']), ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
