"""Offline checks for stratification, censored calibration and scene isolation."""
import copy
import json
import math
from pathlib import Path
import random
import subprocess
import sys

import pytest

from p3_metrics import paired, quantile, stratified
from p3_reference import (assign_historical_split, fit_histogram, fit_profile,
                          interval_weights, normalize_actions, source_intervals,
                          trajectory_features, validation_scores, write_json)

ROOT=Path(__file__).resolve().parent


def row(n,variant,seed,t,full=True):
    return dict(N=n,variant=variant,seed=seed,error_mode='fixed',full_clear=full,
                virtual_time_s=t,clear_fail_count=0,time_breakdown={'move_time_s':t/2})


def test_n_regression_cannot_hide_in_overall_gain():
    rows=[row(n,v,n,100+(10 if n==10 else -10) if v=='new' else 100)
          for n in range(10,17) for v in ('old','new')]
    report=stratified(rows,'old')
    assert report['groups']['N=10']['vs_reference']['new']['mean_saved_s']==-10
    assert report['groups']['overall']['vs_reference']['new']['mean_saved_s']>0
    assert report['groups']['N=10-15']['variants']['new']['cases']==6
    assert report['groups']['N=16']['variants']['new']['cases']==1


def test_failure_is_not_rewarded_as_speedup():
    report=paired([row(10,'old',1,100)], [row(10,'new',1,2,False)])
    assert report['mean_saved_s'] is None
    assert report['new_failures']==1 and report['omitted_speed_pairs']==1


def test_missing_or_duplicate_pair_rejected():
    a=row(10,'old',1,100); b=row(10,'new',2,100)
    with pytest.raises(ValueError,match='Unmatched'):paired([a],[b])
    with pytest.raises(ValueError,match='Duplicate'):paired([a,a],[b,b])


def test_models_are_part_of_pair_identity():
    a=row(10,'old',1,100);b=row(10,'new',1,90);b['evaluation_model']='reference'
    with pytest.raises(ValueError,match='Unmatched'):paired([a],[b])


def test_case_mean_per_source_not_ratio_of_pooled_means():
    rows=[row(10,'old',1,100),row(16,'old',2,320)]
    s=stratified(rows,'old')['groups']['overall']['variants']['old']
    assert s['mean_completed_per_source_s']==15.
    assert quantile([0,100],.95)==95.


def test_bootstrap_reproducible():
    old=[row(10,'old',i,100) for i in range(10)]
    new=[row(10,'new',i,100-i) for i in range(10)]
    assert paired(old,new)==paired(old,new)


def action(kind,pos=None,ch=None,result=None,t=0.):
    return dict(action=kind,pos=pos,ch=ch,result=result,virtual_time_s=t,svd_deg=None)


def test_clear_does_not_switch_measurement_channel():
    actions=[action('enter'),action('measure',[0,0],2,'no_signal',6),
             action('clear',[0,0],3,'no_target_in_range',9),
             action('measure',[0,0],2,'no_signal',14),action('exit',t=14)]
    features=trajectory_features(actions)
    assert features['max_action_clock_error_s']==0
    assert features['switch_count']==1
    assert features['post_last_clear_s'] is None


def test_tail_after_last_clear_and_timing_mismatch():
    actions=[action('enter'),action('clear',[0,0],1,'success',5),
             action('measure',[0,0],2,'no_signal',11),action('exit',t=11)]
    features=trajectory_features(actions)
    assert features['post_last_clear_s']==6 and features['max_action_clock_error_s']==0
    actions[-1]['virtual_time_s']=12
    assert trajectory_features(actions)['max_action_clock_error_s']==1


@pytest.mark.parametrize('seed',range(8))
def test_conservative_intervals_contain_actual_source(seed):
    rng=random.Random(seed);angle=rng.uniform(0,2*math.pi)
    radius=rng.uniform(0,1800);z=[radius*math.cos(angle),radius*math.sin(angle)]
    reception=rng.uniform(1000,1500)
    offset=rng.uniform(0,20);q=[z[0]+offset,z[1]]
    received=[z[0]+reception-1,z[1]];negative=[z[0]+reception+1,z[1]]
    actions=[action('measure',received,1,'direction'),action('measure',negative,1,'no_signal'),
             action('clear',q,1,'success'),action('measure',q,1,'no_signal')]
    interval=source_intervals(actions)[0]
    assert interval['radial_squared_fraction'][0] <= (radius/1800)**2 <= interval['radial_squared_fraction'][1]
    assert interval['reception_radius_m'][0] <= reception <= interval['reception_radius_m'][1]


def test_impossible_intervals_rejected():
    with pytest.raises(ValueError,match='Inconsistent'):
        source_intervals([action('measure',[3000,0],1,'direction'),action('clear',[0,0],1,'success')])


def test_em_uninformative_intervals_do_not_invent_distribution():
    profile=fit_histogram([[1000,1500]]*50,[1000,1100,1200,1300,1400,1500])
    assert profile['probabilities']==pytest.approx([.2]*5)
    assert profile['wholly_uninformative']==50


def test_em_fit_responds_to_informative_bounds_and_keeps_support():
    profile=fit_histogram([[1001,1099]]*20,[1000,1100,1200,1300,1400,1500])
    assert profile['probabilities'][0]>.8
    assert min(profile['probabilities'])>0
    assert sum(profile['probabilities'])==pytest.approx(1.)
    with pytest.raises(ValueError):interval_weights([900,1100],profile['edges'])


def fake_cases():
    return [dict(case_id=f'{n}-{i}',N=n,full_clear=True,
                 intervals=[dict(radial_squared_fraction=[.1,.2],reception_radius_m=[1000,1200])])
            for n in range(10,17) for i in range(4)]


def test_split_stable_when_input_order_changes():
    cases=fake_cases()
    one=assign_historical_split(copy.deepcopy(cases));two=assign_historical_split(copy.deepcopy(cases[::-1]))
    assert {c['case_id']:c['split'] for c in one}=={c['case_id']:c['split'] for c in two}
    assert sum(c['split']=='historical_validation' for c in one)==7
    assert all(c['split']!='final_holdout' for c in one)


def test_validation_data_cannot_change_fit():
    cases=assign_historical_split(fake_cases());first=fit_profile(cases)
    for c in cases:
        if c['split']=='historical_validation':
            c['intervals']=[dict(radial_squared_fraction=[.9,1.],reception_radius_m=[1400,1500])]
    assert fit_profile(cases)==first
    score=validation_scores(cases,first)
    assert score['historical_validation']['radial_squared_fraction']['mean_scene_log_likelihood_gain_vs_uniform']<0
    assert not set(first['fitted_case_ids']) & {c['case_id'] for c in cases if c['split']=='historical_validation'}


def test_incomplete_scene_excluded_from_fit_not_erased():
    cases=assign_historical_split(fake_cases());bad=next(c for c in cases if c['split']=='historical_calibration')
    bad['full_clear']=False
    assert bad['case_id'] not in fit_profile(cases)['fitted_case_ids']
    assert len(cases)==28


def test_normalization_deduplicates_exact_retry_and_redacts():
    enter=dict(path='/enter',request={'request_id':'1','robot_id':'SECRET'},
               response={'accepted':True,'virtual_time_s':0})
    end=dict(path='/exit',request={'request_id':'2'},response={'accepted':True,'virtual_time_s':0})
    assert len(normalize_actions([enter,enter,end]))==2
    assert 'SECRET' not in json.dumps(normalize_actions([enter,end]))
    conflict=copy.deepcopy(enter);conflict['response']['virtual_time_s']=1
    with pytest.raises(ValueError,match='Conflicting'):normalize_actions([enter,conflict,end])


@pytest.mark.parametrize('outside',[False,True])
def test_reference_simulator_offline_entry_and_no_n_in_response(tmp_path,outside):
    profile=fit_profile(assign_historical_split(fake_cases()));file=tmp_path/'profile.json';write_json(file,profile)
    code=f'''
import sys, json, math
sys.path[:0]={list(map(str,[ROOT,ROOT.parent/'第三问/v10']))!r}
from p3_reference import reference_simulator
from strategy_transit import ResidualP3
from robot_iter import run_with_sim_strategy
p=json.load(open({str(file)!r},encoding='utf-8'))
a=reference_simulator(1089991,10,'fixed',p)
b=reference_simulator(1089991,10,'fixed',p)
assert [(s.pos,s.R_eff) for s in a.sources.values()]==[(s.pos,s.R_eff) for s in b.sources.values()]
assert all(math.hypot(*s.pos)<=1800 and 1000<=s.R_eff<=1500 for s in a.sources.values())
assert 'N' not in a.enter().extra and 'jammer_count' not in a.enter().extra
result=run_with_sim_strategy(ResidualP3(),b)
assert result['cleared']==10 and result['coverage_complete']
print('REFERENCE_OFFLINE_PASS')
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=tmp_path if outside else ROOT.parents[1],
                          capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert result.returncode==0,result.stdout+result.stderr


def test_frozen_dataset_tamper_rejected(tmp_path):
    from p3_evaluation import load_profile
    write_json(tmp_path/'profile.json',{'fitted_case_ids':[]})
    write_json(tmp_path/'manifest.json',{'artifact_sha256':{'profile.json':'wrong'},'validation_case_ids':[]})
    with pytest.raises(ValueError,match='changed'):load_profile(str(tmp_path))
