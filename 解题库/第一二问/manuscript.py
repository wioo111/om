"""One editable manuscript; generated chapters and repository paper share data."""
from pathlib import Path
import json
import re
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
P=ROOT/'paper'

def test_counts():
    root=ET.parse(ROOT/'logs/pytest.xml').getroot()
    suites=list(root.iter('testsuite'))
    counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    if not counts['tests'] or counts['failures'] or counts['errors'] or counts['skipped']:
        raise RuntimeError(f'Incomplete test execution: {counts}')
    return counts

def render_manuscript(text,q1,q2):
    from evidence import require_fresh
    require_fresh('prove',('proofs/',))
    require_fresh('test',('logs/pytest.xml',))
    require_fresh('experiments',('results/',))
    proof=json.loads((ROOT/'proofs/global_certificate.json').read_text(encoding='utf-8'))
    primary=next(x for x in q2['summary'] if x['pose']=='all' and x['strategy']=='minimax')
    worst=q2['worst_case']['posterior']
    values={
        'TEST_COUNT':str(test_counts()['tests']),
        'Q2_MEAN':f"{primary['mean_D_among_valid']:.6f}",
        'Q2_P95':f"{primary['p95_D_among_valid']:.6f}",
        'OPTICAL_RATE':f"{100*primary['optical_guarantee_rate']:.4f}",
        'WORST_LO':f"{worst['lower_m']:.6f}", 'WORST_HI':f"{worst['upper_m']:.6f}",
        'HEADING_LEAVES':str(proof['all_other_headings']['leaf_count']),
        'CANDIDATE_LEAVES':str(proof['candidate_region']['leaf_count']),
    }
    for key,value in values.items():text=text.replace('{{'+key+'}}',value)
    if '{{' in text:raise RuntimeError('Unfilled manuscript variable')
    # Preserve six selected argument figures, place the other seven in appendix C.
    manifest=json.loads((ROOT/'figures/manifest.json').read_text(encoding='utf-8'))
    supplement=['## 附录C 补充实验图', '', '下列图片与正文使用同一组正式结果文件。图中的采样曲线不承担全局证明。', '']
    for i,item in enumerate((x for x in manifest if not x['main']),1):
        supplement += [f"![图C{i} {item['caption']}](../figures/{item['stem']}.png){{width=11cm}}",'',f"数据来源：`{item['source']}`。",'']
    return text.replace('## 参考文献','\n'.join(supplement)+'\n## 参考文献')

def split_chapters(text):
    sections=re.split(r'(?=^## )',text,flags=re.M)
    groups={'第一问正文.md':[], '第二问正文.md':[], '实验与实现.md':[],
            '证明附录.md':[], '参考文献.md':[], '摘要与符号.md':[], '结论.md':[]}
    for s in sections:
        if s.startswith('## 2 '):key='第一问正文.md'
        elif s.startswith(('## 3 ','## 4 ')):key='第二问正文.md'
        elif s.startswith(('## 5 ','## 6 ')):key='实验与实现.md'
        elif s.startswith('## 附录'):key='证明附录.md'
        elif s.startswith('## 参考文献'):key='参考文献.md'
        elif s.startswith('## 7 '):key='结论.md'
        else:key='摘要与符号.md'
        groups[key].append(s)
    for name,parts in groups.items():(P/name).write_text(''.join(parts),encoding='utf-8')

def publish_repository_paper():
    dest=ROOT.parent/'完整论文';dest.mkdir(exist_ok=True)
    source=P/'第一二问完整论文'
    target=dest/'论文_第一二问'
    for ext in ('.md','.tex'):
        text=source.with_suffix(ext).read_text(encoding='utf-8')
        text=text.replace('../figures/','../第一二问/figures/')
        target.with_suffix(ext).write_text(text,encoding='utf-8')
    for ext in ('.pdf','.docx'):shutil.copyfile(source.with_suffix(ext),target.with_suffix(ext))
