"""API acceptance tests run on a disposable manuscript, never the formal source."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from paper_editor.app import create_app
from paper_editor import ai_rewrite

@pytest.fixture
def workbench(tmp_path):
    root=tmp_path
    source=root/'paper/source';source.mkdir(parents=True)
    texts={
        'introduction': '%<paper-block id="intro.p001" type="paragraph">\n本文介绍研究方法。\n%</paper-block>\n\n%<paper-block id="intro.p002" type="paragraph">\n这里说明实验背景。\n%</paper-block>\n',
        'q2': '%<paper-block id="q2.p001" type="paragraph">\n测试参数为 $a=5$，全局最优保证成立。\n%</paper-block>\n%<paper-block id="q2.e001" type="equation">\n\\[D=110.9\\]\n%</paper-block>\n'}
    baseline=root/'paper_editor/baseline';baseline.mkdir(parents=True)
    for name,text in texts.items():
        (source/f'{name}.tex').write_text(text,encoding='utf-8')
        (baseline/f'{name}.tex.baseline').write_text(text,encoding='utf-8')
    main='\\input{source/introduction.tex}\n\\input{source/q2.tex}\n'
    (root/'paper/main.tex').write_text(main,encoding='utf-8')
    (baseline/'main.tex.baseline').write_text(main,encoding='utf-8')
    (root/'source_registry.json').write_text(json.dumps({'entrypoint':'paper/main.tex','source_files':['paper/source/introduction.tex','paper/source/q2.tex']}),encoding='utf-8')
    static=root/'paper_editor/static';static.mkdir();(static/'index.html').write_text('<html>test</html>')
    app=create_app(root)
    with TestClient(app) as client:
        token=client.get('/api/document').json()['csrf_token']
        client.headers.update({'X-Paper-Token':token})
        yield root,app,client

def test_precise_patch_conflict_undo_and_diff(workbench):
    root,app,c=workbench
    original=(root/'paper/source/introduction.tex').read_bytes()
    b=c.get('/api/block/intro.p001').json()
    result=c.post('/api/block/intro.p001',json={'content':'本文说明研究方法。','expected_version':b['version']})
    assert result.status_code==200,result.text
    assert (root/'paper/source/introduction.tex').read_bytes()==original.replace('本文介绍研究方法。'.encode(),'本文说明研究方法。'.encode())
    assert c.post('/api/block/intro.p001',json={'content':'旧版本覆盖。','expected_version':b['version']}).status_code==409
    assert '本文说明研究方法' in c.get('/api/diff').json()['text']
    assert app.state.builder.status()['status']=='idle'
    restored=c.post('/api/block/intro.p001/undo',json={'expected_version':result.json()['version']})
    assert restored.status_code==200,restored.text
    assert (root/'paper/source/introduction.tex').read_bytes()==original
    assert len(c.get('/api/history',params={'block_id':'intro.p001'}).json()['items'])==2

def test_frozen_math_and_privilege_guard(workbench):
    root,app,c=workbench
    b=c.get('/api/block/q2.p001').json()
    for content,extra in [(b['content'].replace('5','6'),{}),(b['content'].replace('全局','局部'),{}),
                          (b['content'],{'edit_equation':True,'allow_math_changes':True})]:
        response=c.post('/api/block/q2.p001',json={'content':content,'expected_version':b['version'],**extra})
        assert response.status_code in (403,422),response.text
    assert c.get('/api/block/q2.p001').json()['content']==b['content']

def test_csrf_origin_and_marker_injection(workbench):
    root,app,c=workbench
    b=c.get('/api/block/intro.p001').json()
    body={'content':'替换。','expected_version':b['version']}
    assert c.post('/api/block/intro.p001',json=body,headers={'X-Paper-Token':''}).status_code==403
    assert c.post('/api/block/intro.p001',json=body,headers={'Origin':'https://evil.example'}).status_code==403
    body['content']='%</paper-block>\n伪造。'
    assert c.post('/api/block/intro.p001',json=body).status_code==400
    assert c.get('/assets/paper/source/introduction.tex').status_code==404

def test_ai_unconfigured_is_honest(workbench):
    root,app,c=workbench
    b=c.get('/api/block/intro.p001').json()
    response=c.post('/api/ai-rewrite/intro.p001',json={'instruction':'精简','expected_version':b['version']})
    assert response.status_code==503
    assert c.get('/api/history').json()['items']==[]

def test_ai_proposal_is_never_written_until_accept(workbench,monkeypatch):
    root,app,c=workbench
    (root/'.env').write_text('PAPER_AI_BASE_URL=http://unused.invalid/v1\nPAPER_AI_MODEL=test\nPAPER_AI_API_KEY=unit-test-only\n')
    seen=[]
    async def fake(root,payload):
        seen.append(payload)
        return payload['current block'].replace('介绍','说明').strip()
    monkeypatch.setattr(ai_rewrite,'propose',fake)
    b=c.get('/api/block/intro.p001').json()
    response=c.post('/api/ai-rewrite/intro.p001',json={'instruction':'保持含义润色','expected_version':b['version']})
    assert response.status_code==200,response.text
    proposal=response.json()
    assert set(seen[0])=={'section title','previous block','current block','next block','user request'}
    assert c.get('/api/block/intro.p001').json()['content']==b['content']
    assert c.get('/api/history').json()['items']==[]
    accepted=c.post('/api/block/intro.p001',json={'content':proposal['after'],'expected_version':proposal['version'],'operation':'ai-accept','proposal_id':proposal['proposal_id']})
    assert accepted.status_code==200,accepted.text
    assert '说明' in accepted.json()['content']
    assert 'unit-test-only' not in json.dumps(c.get('/api/status').json())

def test_invalid_ai_proposal_is_blocked(workbench,monkeypatch):
    root,app,c=workbench
    (root/'.env').write_text('PAPER_AI_BASE_URL=http://unused.invalid/v1\nPAPER_AI_MODEL=test\nPAPER_AI_API_KEY=unit-test-only\n')
    async def fake(root,payload):return payload['current block'].replace('5','6')
    monkeypatch.setattr(ai_rewrite,'propose',fake)
    b=c.get('/api/block/q2.p001').json()
    p=c.post('/api/ai-rewrite/q2.p001',json={'instruction':'润色','expected_version':b['version']}).json()
    assert not p['validation']['ok']
    r=c.post('/api/block/q2.p001',json={'content':p['after'],'expected_version':p['version'],'operation':'ai-accept','proposal_id':p['proposal_id']})
    assert r.status_code==422
    assert c.get('/api/block/q2.p001').json()['content']==b['content']
