"""Bounded joint FUTURE clear-anchor replacement of discovery stations.

Inputs are observations and already certified finite optical plans only.
`actual_points` must be the intersection of locations REALLY measured for all
currently unknown channels. A proposed clear anchor is never actual evidence.
The returned mandatory scan stops survive both clear success and clear failure;
the caller must measure the returned channel snapshot there, or replace that
obligation only with another continuous proof. Actual completion is not assessed.

At most four new anchors and six cumulative deletion trials are considered.
The sufficient certificate proves the entire continuous outer target enclosure.
Cost ranking compares the SAME finite clear tasks on both routes, charging all
scan detections/switches, movement, and worst-case finite optical clear outcomes.
No third-question policy, scene truth, or no_signal spatial exclusion is used.
"""
import math

from discovery_compact import build_coverage_certifier


MAX_NEW_ANCHORS=4
MAX_DELETION_TRIALS=6
MAX_CELLS=2400
MAX_DEPTH=48
SAME_POINT_TOLERANCE=1e-6


def _point(value):
    point=tuple(map(float,value))
    if len(point)!=2 or not all(math.isfinite(x) for x in point):
        raise ValueError('points must be finite (x,y) pairs')
    return point


def _same(a,b):
    return math.dist(a,b)<=SAME_POINT_TOLERANCE


def _unique(points):
    answer=[]
    for point in points:
        point=_point(point)
        if not any(_same(point,old) for old in answer):answer.append(point)
    return answer


def _tasks(ready_tasks):
    answer=[];channels=set()
    for channel,cover_points in ready_tasks:
        if channel in channels:raise ValueError('clear tasks must have unique channel IDs')
        channels.add(channel)
        points=tuple(_point(point) for point in cover_points)
        if not 1<=len(points)<=6:raise ValueError('each supplied certified cover must have 1..6 points')
        answer.append((channel,points))
    return answer


def cost_plan(scan_points,ready_tasks,start,unknown_channels,current_channel=1):
    """Finite deterministic route with identical clear bundles in each comparison.

A scan at a first clear point is attached before that clear. Other scans and
clear bundles are ordered by nearest next stop; a bundle visits all of its cover
points in supplied order, charging k-1 failed clears then one success. This is a
conservative ranking model, not a prediction that every first clear will fail.
"""
    # Planned obligations use exact coordinates. Near-equal mandatory stops
    # cannot be silently merged: a continuous proof may depend on both points.
    scans=list(dict.fromkeys(_point(point) for point in scan_points))
    channels=tuple(sorted(set(unknown_channels)))
    jobs=[]
    for channel,points in _tasks(ready_tasks):
        same=next((point for point in scans if point==points[0]),None)
        if same is not None:scans.remove(same)
        jobs.append(dict(kind='clear_bundle',channel=channel,points=points,scan_first=same is not None))
    jobs += [dict(kind='scan',points=(point,),scan_first=True) for point in scans]
    position=_point(start);receiver=current_channel;route=[]
    cost=dict(move_time_s=0.,measure_time_s=0.,switch_time_s=0.,clear_success_time_s=0.,clear_failure_time_s=0.)
    while jobs:
        index=min(range(len(jobs)),key=lambda i:(math.dist(position,jobs[i]['points'][0]),
                                                jobs[i]['kind'],str(jobs[i].get('channel','')),i))
        job=jobs.pop(index)
        for i,point in enumerate(job['points']):
            cost['move_time_s']+=math.dist(position,point)/5.
            position=point
            if i==0 and job['scan_first']:
                order=list(channels)
                if receiver in order:order.remove(receiver);order.insert(0,receiver)
                for channel in order:
                    cost['switch_time_s']+=float(channel!=receiver)
                    cost['measure_time_s']+=5.
                    receiver=channel
                route.append(dict(kind='mandatory_scan',point=point,channels=order))
            if job['kind']=='clear_bundle':
                outcome='success' if i==len(job['points'])-1 else 'failure'
                cost['clear_success_time_s' if outcome=='success' else 'clear_failure_time_s']+=5. if outcome=='success' else 3.
                route.append(dict(kind='clear',point=point,channel=job['channel'],cost_model_outcome=outcome))
    cost['total_s']=sum(cost.values())
    cost['distance_m']=cost['move_time_s']*5.
    return dict(cost=cost,route=route,terminal_position=position,terminal_receiver_channel=receiver,
                clear_outcome_model='same full finite cover: k-1 failures then success, for ranking only')


def choose_joint_replacement(actual_points,pending,ready_tasks,start,unknown_channels,
                             current_channel=1,mandatory_scan_stops=(),checker=None):
    """Return a cost-improving proved plan, or the unchanged pending obligations.

ready_tasks is [(known_channel, certified_cover_points), ...]. The caller must
retain existing mandatory_scan_stops across replans even after the originating
clear task disappears. Only measurements update actual per-channel evidence.
"""
    actual=_unique(actual_points);original=[_point(point) for point in pending]
    existing=list(dict.fromkeys(_point(point) for point in mandatory_scan_stops))
    tasks=_tasks(ready_tasks);start=_point(start)
    channels=tuple(sorted(set(unknown_channels)))
    baseline=cost_plan(original+existing,tasks,start,channels,current_channel)
    stats=dict(kind='joint_continuous_future_anchor_replacement',future_plan_only=True,
               actual_completion='not_assessed',coverage_uses_sampling=False,
               max_new_anchors=MAX_NEW_ANCHORS,max_deletion_trials=MAX_DELETION_TRIALS,
               max_cells_per_certificate=MAX_CELLS,attempts=[],future_plan_proved=False,
               actual_common_unique_points=len(actual),baseline_cost=baseline['cost'],
               cost_saving_s=0.,reason='not_started')
    fallback=dict(accepted=False,removed=[],remaining=original[:],mandatory_scan_stops=existing[:],
                  mandatory_scan_channels=channels,new_anchors=[],baseline_plan=baseline,
                  proposed_plan=baseline,diagnostics=stats)
    if not original or not channels:
        stats['reason']='no_pending_or_no_unknown_channels'
        return fallback
    candidates=[]
    for channel,points in tasks:
        anchor=points[0]
        if any(_same(anchor,point) for point in actual+existing+[entry[1] for entry in candidates]):continue
        candidates.append((channel,anchor))
    candidates.sort(key=lambda entry:(min(math.dist(entry[1],point) for point in original),
                                      math.dist(start,entry[1]),str(entry[0])))
    # Existing unfulfilled anchors consume the same four-anchor budget. They
    # cannot be discarded merely to make room for another promising clear stop.
    anchor_capacity=max(0,MAX_NEW_ANCHORS-len(existing))
    anchors=[point for _,point in candidates[:anchor_capacity]]
    obligations=existing+anchors
    hypothetical=actual+obligations
    stats['proposed_new_anchors']=anchors
    if checker is None:
        try:checker=build_coverage_certifier(max_cells=MAX_CELLS,max_depth=MAX_DEPTH)
        except (ArithmeticError,ValueError,RuntimeError) as exc:
            stats.update(reason='certificate_construction_error',error=str(exc))
            return fallback

    def prove(points):
        try:
            passed=bool(checker.certified_complete(points,max_cells=MAX_CELLS))
            return passed,dict(checker.last_diagnostics)
        except (ArithmeticError,ValueError,RuntimeError) as exc:
            return False,dict(reason='certificate_error',error=str(exc))

    passed,diagnostic=prove(hypothetical+original)
    stats['initial_certificate']=diagnostic
    if not passed:
        stats['reason']='initial_future_plan_not_proved'
        return fallback
    entries=list(enumerate(original));attempted=set();removed=[];best=None
    while entries and len(attempted)<MAX_DELETION_TRIALS:
        available=[i for i,(identity,_) in enumerate(entries) if identity not in attempted]
        if not available:break
        reference_points=anchors or existing or actual or [start]
        index=min(available,key=lambda i:(min(math.dist(entries[i][1],point) for point in reference_points),entries[i][0]))
        identity,point=entries[index];attempted.add(identity)
        tentative=[entry[1] for j,entry in enumerate(entries) if j!=index]
        passed,diagnostic=prove(hypothetical+tentative)
        trial=dict(original_pending_index=identity,point=point,continuous_proof=passed,certificate=diagnostic)
        stats['attempts'].append(trial)
        if not passed:continue
        entries.pop(index);removed.append(point)
        candidate=cost_plan(tentative+obligations,tasks,start,channels,current_channel)
        saving=baseline['cost']['total_s']-candidate['cost']['total_s']
        trial.update(cost_saving_s=saving,candidate_cost=candidate['cost'])
        if saving>1e-7 and (best is None or saving>best['saving']):
            best=dict(remaining=tentative[:],removed=removed[:],plan=candidate,saving=saving)
    if best is None:
        stats['reason']='no_cost_improving_certified_deletion'
        return fallback
    stats.update(reason='cost_improving_joint_future_replacement',future_plan_proved=True,
                 cost_saving_s=best['saving'],proposed_cost=best['plan']['cost'],
                 clear_outcome_cannot_cancel_scan_obligation=True)
    return dict(accepted=True,removed=best['removed'],remaining=best['remaining'],
                mandatory_scan_stops=obligations,mandatory_scan_channels=channels,new_anchors=anchors,
                baseline_plan=baseline,proposed_plan=best['plan'],diagnostics=stats)
