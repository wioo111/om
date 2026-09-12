"""Recheck theorem certificate, full experiment accounting and deliverable files.

Uses only local artifacts; never infers correctness from file names or test counts.
"""
from __future__ import annotations
from pathlib import Path
import csv,hashlib,json,math,re,sys,zipfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from q12.proof import verify_all
from q12.policy import choose_second_point
from evidence import require_fresh
from manuscript import test_counts

def need(ok:bool,message:str)->None:
    if not ok:raise RuntimeError(message)

def rows(name):
    with (ROOT/'results'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    for command,prefix in [('prove',('proofs/',)),('test',('logs/pytest.xml',)),
                           ('experiments',('results/',)),('figures',('figures/',)),('paper',('paper/',))]:
        require_fresh(command,prefix)
    certificate=verify_all()
    saved=json.loads((ROOT/'proofs/global_certificate.json').read_text(encoding='utf-8'))
    for name in ['t_star_m','diameter_star_m','station_original_coordinates_m']:
        need(certificate[name]==saved[name],f'Stale proof constant: {name}')
    q1=json.loads((ROOT/'results/q1_summary.json').read_text())
    q2=json.loads((ROOT/'results/q2_summary.json').read_text())
    r1,r2=rows('q1_samples.csv'),rows('q2_paired_samples.csv')
    need(len(r1)==1000,'Q1 accounting mismatch')
    need(len(r2)==6000,'Q2 accounting mismatch')
    summaries=[x for x in q2['summary'] if x['pose']=='all']
    need(len(summaries)==4 and all(x['N']==1500 for x in summaries),'Unequal strategy denominators')
    primary=next(x for x in summaries if x['strategy']=='minimax')
    need(primary['no_signal']==0,'Minimax policy had a reception failure')
    primary_rows=[r for r in r2 if r['strategy']=='minimax']
    need(len(primary_rows)==1500,'Missing primary-strategy evaluations')
    need(all(not r['D_upper'] or float(r['D_upper'])<110.970 for r in primary_rows),'Posterior exceeded guarded bound plus polygon error budget')
    manifest=json.loads((ROOT/'figures/manifest.json').read_text(encoding='utf-8'))
    need(len(manifest)==13,'Expected 13 figures')
    for item in manifest:
        for ext in ['png','pdf','svg']:
            f=ROOT/'figures'/f'{item["stem"]}.{ext}'
            need(f.is_file() and f.stat().st_size>1000,f'Missing/empty figure: {f.name}')
    base=ROOT/'paper/第一二问完整论文'
    for ext in ['.pdf','.docx','.md','.tex']:
        need(base.with_suffix(ext).is_file(),f'Missing paper {ext}')
    text=base.with_suffix('.md').read_text(encoding='utf-8')
    need('{{' not in text,'Unfilled manuscript template')
    need('附录A' in text and '附录B' in text,'Missing full proof appendices')
    need('110.969318572838179' in text,'Paper optimum mismatch')
    for s in summaries:
        need(f'{s["mean_D_among_valid"]:.3f}' in text,'Paper/experiment mean mismatch')
    with zipfile.ZipFile(base.with_suffix('.docx')) as z:
        xml=z.read('word/document.xml');tree=ET.fromstring(xml)
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math',
        'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    equations=len(tree.findall('.//m:oMath',ns));need(equations>300,'Missing native Word equations')
    raw=''.join(n.text or '' for n in tree.findall('.//w:t',ns))
    need('$$' not in raw and r'\tag' not in raw,'Unconverted Word equation source')
    tests=test_counts()
    repository=ROOT.parent/'完整论文/论文_第一二问'
    need(repository.with_suffix('.md').read_text(encoding='utf-8')==text.replace('../figures/','../第一二问/figures/'),'Repository manuscript is stale')
    for ext in ['.docx','.pdf']:
        need(repository.with_suffix(ext).read_bytes()==base.with_suffix(ext).read_bytes(),'Repository document is stale: '+ext)
    referenced=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text)
    need(len(referenced)==len(manifest),'Figure references do not match manifest')
    need(all((base.parent/p).is_file() for p in referenced),'Broken manuscript image link')
    q2chapter=(ROOT/'paper/第二问正文.md').read_text(encoding='utf-8')
    need('## 参考文献' not in q2chapter and '## 附录' not in q2chapter,'Q2 chapter contains appended back matter')
    from q12.geometry import Observation,pure_bearing_region
    data=json.loads((ROOT/'examples/q1_observations.json').read_text())
    smoke=pure_bearing_region([Observation(**x) for x in data['observations']]).metrics()
    need(smoke['D'] is not None,'Q1 CLI example is not bounded')
    choose_second_point((2100,400),190,side=-1)
    result={'pass':True,'theorem_certificate_reexecuted':True,'tests_recorded':tests['tests'],
            'q1_regions':len(r1),'q2_scenarios':1500,'q2_strategy_evaluations':len(r2),
            'primary_no_signal':0,'figures':len(manifest),'figure_formats':['png','svg','pdf'],
            'word_native_equations':equations,'proof_nonactive_heading_intervals':certificate['all_other_headings']['leaf_count'],
            'continuous_candidate_intervals':certificate['candidate_region']['leaf_count'],
            'diameter_star_interval_m':certificate['diameter_star_m'],
            'scope':'exact continuous minimax at untruncated first observations; exact policy-level minimax over all valid first observations',
            'not_claimed':'pointwise optimality at every individually truncated boundary state'}
    (ROOT/'audit').mkdir(exist_ok=True)
    (ROOT/'audit/ACCEPTANCE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
