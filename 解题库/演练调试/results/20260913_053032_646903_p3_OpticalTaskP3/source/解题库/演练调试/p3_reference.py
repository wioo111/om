"""Read completed own practice logs; fit weak interval-censored reference profiles.

No network, SQLite, encrypted-log decoding or live session access. A fitted histogram
is a sensitivity model, NOT an identification of the official generator.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RADIAL_EDGES = [0., 1/3, 2/3, 1.]
RECEPTION_EDGES = [1000., 1100., 1200., 1300., 1400., 1500.]


def digest(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def read_json(file):
    return json.loads(Path(file).read_text(encoding='utf-8'))


def write_json(file, value):
    Path(file).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def normalize_actions(raw):
    actions, seen = [], {}
    for row in raw:
        req, res = row.get('request', {}), row.get('response', {})
        key = req.get('request_id')
        if key and key in seen:
            if row != seen[key]:
                raise ValueError('Conflicting retry contents')
            continue
        if key:
            seen[key] = row
        if res.get('accepted') is not True:
            raise ValueError('Incomplete or rejected action: not a completed reference trajectory')
        action = row['path'].lstrip('/')
        if action not in ('enter', 'measure', 'clear', 'exit'):
            raise ValueError('Unknown action')
        pos = req.get('position', {})
        actions.append(dict(action=action, pos=[pos['x'], pos['y']] if pos else None,
                            ch=req.get('channel'), result=res.get('measure_result', res.get('clear_result')),
                            svd_deg=res.get('svd_deg'), virtual_time_s=res['virtual_time_s']))
    if not actions or actions[0]['action'] != 'enter' or actions[-1]['action'] != 'exit':
        raise ValueError('Requires successful enter and exit')
    return actions


def trajectory_features(actions):
    prev = (0., 0.); ch = 1; last_t = 0.; last_clear = None; cleared = set()
    counts = Counter(); errors = []; moves = 0.; switches = 0
    for a in actions:
        expected = 0.
        if a['action'] in ('measure', 'clear'):
            distance = math.dist(prev, a['pos']); moves += distance; expected += distance/5
            prev = a['pos']
            if a['action'] == 'measure':
                switched = int(ch != a['ch']); ch = a['ch']; switches += switched
                expected += 5 + switched
                counts[a['result']] += 1
            else:
                expected += 5 if a['result'] == 'success' else 3
                counts['clear_'+a['result']] += 1
                if a['result'] == 'success':
                    if a['ch'] in cleared:
                        raise ValueError('Same channel cleared twice')
                    cleared.add(a['ch']); last_clear = a['virtual_time_s']
        errors.append(abs(a['virtual_time_s']-last_t-expected)); last_t = a['virtual_time_s']
    return dict(counts=dict(counts), move_m=moves, switch_count=switches, cleared=len(cleared),
                virtual_time_s=last_t, post_last_clear_s=last_t-last_clear if last_clear is not None else None,
                max_action_clock_error_s=max(errors))


def source_intervals(actions):
    """Conservative marginal bounds from successful clear disks, never point truth.

    If q is a successful clear and z the unknown source, |z-q|<=20.
    A received point p implies R>=|p-q|-20; no_signal before clearing implies
    R<|p-q|+20. These are necessary bounds, not sufficient scene reconstruction.
    """
    observations = {}; intervals = []
    for a in actions:
        ch = a['ch']
        if a['action'] == 'measure':
            observations.setdefault(ch, []).append(a)
        if a['action'] != 'clear' or a['result'] != 'success':
            continue
        q = a['pos']; r = math.hypot(*q)
        radius = [max(0., r-20.), min(1800., r+20.)]
        low, high = 1000., 1500.
        for obs in observations.get(ch, []):
            d = math.dist(q, obs['pos'])
            if obs['result'] in ('direction', 'near'):
                low = max(low, d-20.)
            elif obs['result'] == 'no_signal':
                high = min(high, d+20.)
        if radius[0] > radius[1] or low > high:
            raise ValueError('Inconsistent clear/reception constraints')
        intervals.append(dict(ch=ch, radial_squared_fraction=[(v/1800.)**2 for v in radius],
                              reception_radius_m=[low, high]))
        observations[ch] = []  # post-clear no_signal must not tighten the old source radius
    return intervals


def collect_completed(results):
    cases, rejected, duplicates, seen = [], [], [], {}
    exports = REPO/'Jammers-simulator-win64/Jammers-simulator/JammersSimulatorData/behavior-logs'
    # Completed public practice summaries only, never formal or active journals.
    export_index = {}
    for file in exports.glob('practice-p3-*.result.json'):
        data = read_json(file)
        if data.get('problem_no') == 3:
            export_index.setdefault(data.get('case_code'), []).append((file, data))
    for folder in sorted(Path(results).glob('20??????_*_p3_*')):
        files = [folder/name for name in ('result.json', 'actions.jsonl', 'version.json', 'execution.json')]
        if not all(f.exists() for f in files):
            rejected.append(dict(folder=folder.name, reason='incomplete files')); continue
        try:
            result, version, execution = read_json(files[0]), read_json(files[2]), read_json(files[3])
            official = result.get('simulator_summary', {})
            if (result.get('mode') != 'practice' or result.get('problem') != 3
                    or official.get('problem_no') != 3 or version.get('guard_event') != 'practice_authorized'
                    or execution.get('exit_code') != 0 or result.get('problem_mismatch') or result.get('case_mismatch')):
                raise ValueError('Not a verified completed P3 practice run')
            if result.get('case') != official.get('case_code'):
                raise ValueError('Case association mismatch')
            n = official['jammer_count']
            if n not in range(10, 17):
                raise ValueError('Invalid N')
            matches = export_index.get(result['case'], [])
            if len(matches) > 1:
                raise ValueError('Ambiguous completed export')
            package = None
            if matches:
                f, ex = matches[0]; files.append(f)
                if ex['jammer_count'] != n or ex.get('directional_jammer_count') != 0:
                    raise ValueError('Completed export contradicts P3 summary')
                package = ex.get('package_sha256')
            identity = package or 'case:'+result['case']
            case_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
            if case_id in seen:
                duplicates.append(dict(folder=folder.name, same_scene_as=seen[case_id])); continue
            raw = [json.loads(s) for s in files[1].read_text(encoding='utf-8').splitlines() if s.strip()]
            actions = normalize_actions(raw); features = trajectory_features(actions)
            if features['max_action_clock_error_s'] > .0001:
                raise ValueError('Action clock inconsistent with documented rules')
            if (features['cleared'] != result['cleared'] or features['cleared'] != official['cleared_jammer_count']
                    or abs(features['virtual_time_s']-official['virtual_time_us']/1e6) > .0001):
                raise ValueError('Actions and completed summary disagree')
            intervals = source_intervals(actions)
            case = dict(case_id=case_id, case_code=result['case'], N=n, strategy=result['strategy'],
                        full_clear=features['cleared'] == n, features=features, intervals=intervals,
                        actions=actions, source_folder=str(folder.relative_to(REPO)),
                        source_sha256={str(f.relative_to(REPO)): digest(f) for f in files},
                        policy_sha256=version['code_sha256'], started=version['started'])
            cases.append(case); seen[case_id] = folder.name
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append(dict(folder=folder.name, reason=str(exc)))
    return cases, rejected, duplicates


def assign_historical_split(cases):
    """Freeze by whole scene, stratified by N. Neither part is a fresh blind test."""
    for n in range(10, 17):
        group = sorted((c for c in cases if c['N'] == n),
                       key=lambda c: hashlib.sha256(('p3-reference-v1:'+c['case_id']).encode()).hexdigest())
        n_validation = max(1, round(len(group)*.25)) if len(group) >= 2 else 0
        for i, case in enumerate(group):
            case['split'] = 'historical_validation' if i < n_validation else 'historical_calibration'
    return cases


def interval_weights(interval, edges):
    lo, hi = interval
    if lo > hi or lo < edges[0] or hi > edges[-1]:
        raise ValueError('Interval outside declared support')
    weights = [max(0., min(hi,b)-max(lo,a))/(b-a) for a,b in zip(edges,edges[1:])]
    if not any(weights):
        weights[min(len(weights)-1, next((i for i,b in enumerate(edges[1:]) if lo < b), len(weights)-1))] = 1.
    return weights


def fit_histogram(intervals, edges):
    # Regularized EM under a working interval-censoring model. Adaptive observation
    # positions violate an identifiable independent-censoring model; report this limitation.
    k = len(edges)-1; probabilities = [1/k]*k
    evidence = [interval_weights(x, edges) for x in intervals]
    for _ in range(300):
        counts = [1.]*k  # one prior pseudo-observation/bin, fixed before validation
        for weights in evidence:
            likelihood = sum(p*w for p,w in zip(probabilities,weights))
            for i in range(k):
                counts[i] += probabilities[i]*weights[i]/likelihood
        updated = [v/sum(counts) for v in counts]
        if max(abs(a-b) for a,b in zip(updated,probabilities)) < 1e-10:
            probabilities = updated; break
        probabilities = updated
    return dict(edges=edges, probabilities=probabilities, interval_count=len(intervals),
                wholly_uninformative=sum(all(abs(w-1)<1e-12 for w in row) for row in evidence),
                pseudo_count_per_bin=1.)


def fit_profile(cases):
    training = [c for c in cases if c['split'] == 'historical_calibration' and c['full_clear']]
    if not training:
        raise ValueError('No eligible calibration scenes')
    profile = dict(schema=1, status='experimental_reference_sensitivity_model',
                   fitted_case_ids=[c['case_id'] for c in training],
                   noise_fitted=False, angle_distribution='uniform_assumption',
                   channel_distribution='uniform_without_replacement_assumption',
                   N_distribution='not_fitted; evaluate all N equally; never passed to policy',
                   limitations=['Successful clear gives a 20m disk, not a true position.',
                                'Intervals are necessary marginal bounds, not a reconstructed joint scene.',
                                'Reception censoring depends on historical policies; fit is not an identified official law.',
                                'Radial distance and reception radius sampled independently as a working assumption.',
                                'Historical validation has been seen before; fresh official holdout is still empty.'])
    for key, edges in [('radial_squared_fraction', RADIAL_EDGES), ('reception_radius_m', RECEPTION_EDGES)]:
        profile[key] = fit_histogram([i[key] for c in training for i in c['intervals']], edges)
    return profile


def validation_scores(cases, profile):
    scores = {}
    for split in ('historical_calibration', 'historical_validation'):
        selected = [c for c in cases if c['split'] == split and c['full_clear']]
        scores[split] = {}
        for key in ('radial_squared_fraction', 'reception_radius_m'):
            model = profile[key]; k = len(model['probabilities']); improvements = []
            for case in selected:
                logs = []
                for item in case['intervals']:
                    weights = interval_weights(item[key], model['edges'])
                    fitted = sum(p*w for p,w in zip(model['probabilities'], weights))
                    uniform = sum(weights)/k
                    logs.append(math.log(fitted/uniform))
                improvements.append(st.mean(logs))
            scores[split][key] = dict(scenes=len(improvements),
                mean_scene_log_likelihood_gain_vs_uniform=st.mean(improvements) if improvements else None,
                interpretation='Positive favors fitted interval compatibility; not task-speed improvement or true-density accuracy.')
    return scores


def sample_histogram(rng, profile):
    u = rng.random(); acc = 0.
    for i, p in enumerate(profile['probabilities']):
        acc += p
        if u <= acc or i == len(profile['probabilities'])-1:
            return rng.uniform(profile['edges'][i], profile['edges'][i+1])


def reference_simulator(seed, n, mode, profile):
    # Lazy import: keep the data pipeline usable without importing legacy P3/P4 modules.
    from mock_simulator import MockSimulator, Source

    class ReferenceSimulator(MockSimulator):
        def _gen_sources(self):
            sources = {}
            for ch in self.rng.sample(list(range(1, 21)), self.N):
                radius = 1800*math.sqrt(sample_histogram(self.rng, profile['radial_squared_fraction']))
                angle = self.rng.uniform(0., 2*math.pi)
                reception = sample_histogram(self.rng, profile['reception_radius_m'])
                sources[ch] = Source(ch, (radius*math.cos(angle), radius*math.sin(angle)), reception)
            return sources
    return ReferenceSimulator(seed=seed, N=n, error_mode=mode)
