"""Loopback-only paper workbench. All source writes go through SourceMapper."""
from __future__ import annotations
import asyncio, difflib, json, secrets, time
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .source_mapper import SourceMapper, MapperError
from .renderer import Renderer
from .pdf_builder import PDFBuilder
from . import ai_rewrite

ROOT=Path(__file__).resolve().parent.parent

class PatchRequest(BaseModel):
    content:str=Field(max_length=200000)
    expected_version:str
    operation:str='manual'
    edit_equation:bool=False
    allow_math_changes:bool=False
    proposal_id:str|None=None

class RewriteRequest(BaseModel):
    instruction:str=Field(min_length=1,max_length=3000)
    mode:str='polish'
    expected_version:str

class VersionRequest(BaseModel):
    expected_version:str

def create_app(root:Path=ROOT):
    root=Path(root).resolve()
    mapper=SourceMapper(root)
    renderer=Renderer(root,mapper)
    builder=PDFBuilder(root,mapper)
    token=secrets.token_urlsafe(32)
    proposals={}
    app=FastAPI(title='本地论文微调工作台',docs_url=None,redoc_url=None)
    app.state.mapper=mapper;app.state.renderer=renderer;app.state.builder=builder
    app.state.csrf_token=token;app.state.proposals=proposals

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        host=request.url.hostname
        if host not in ('127.0.0.1','localhost','::1','testserver'):
            return JSONResponse({'error':'工作台仅允许本机访问。'},status_code=403)
        origin=request.headers.get('origin')
        if origin and urlsplit(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'error':'拒绝跨站请求。'},status_code=403)
        if request.method in ('POST','PUT','PATCH','DELETE') and not secrets.compare_digest(request.headers.get('x-paper-token',''),token):
            return JSONResponse({'error':'页面会话已失效，请刷新后重试。'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
        return response

    @app.exception_handler(MapperError)
    async def mapper_error(request,exc):
        return JSONResponse({'error':str(exc),'detail':str(exc),'code':getattr(exc,'code','source_error')},status_code=getattr(exc,'status',400))

    @app.get('/',response_class=HTMLResponse)
    def index():return (root/'paper_editor/static/index.html').read_text(encoding='utf-8')

    @app.get('/api/status')
    def status():
        return {'ai':ai_rewrite.public_settings(root),'source_root':str(root/'paper/source'),
                'entry':str(root/'paper/main.tex'),'build':builder.status(),'csrf_token':token}

    @app.get('/api/document')
    async def document():
        result=await asyncio.to_thread(renderer.render_document)
        result.update(csrf_token=token,ai=ai_rewrite.public_settings(root))
        return result

    @app.get('/api/block/{block_id}')
    def block(block_id:str):return mapper.get_block(block_id)

    @app.post('/api/block/{block_id}')
    async def patch(block_id:str,body:PatchRequest):
        current=mapper.get_block(block_id)
        if (body.allow_math_changes or body.edit_equation) and current['type']!='equation':
            return JSONResponse({'error':'数学编辑模式只适用于独立公式块，普通正文不能绕过冻结保护。'},status_code=422)
        if body.operation not in ('manual','ai-accept'):
            return JSONResponse({'error':'不支持的修改操作。'},status_code=400)
        if body.operation=='ai-accept':
            proposal=proposals.get(body.proposal_id)
            if not proposal or proposal['id']!=block_id or proposal['version']!=body.expected_version or proposal['after']!=body.content:
                return JSONResponse({'error':'AI 提案已失效或内容不匹配，请重新生成。'},status_code=409)
            if not proposal['validation']['ok']:
                return JSONResponse({'error':'该提案未通过冻结保护，不能接受。'},status_code=422)
            if body.edit_equation or body.allow_math_changes:
                return JSONResponse({'error':'AI 润色提案不能通过接受操作提升数学修改权限。'},status_code=422)
        result=await asyncio.to_thread(mapper.patch_block,block_id,body.content,body.expected_version,
                    operation=body.operation,edit_equation=body.edit_equation,allow_math_changes=body.allow_math_changes)
        if body.proposal_id:proposals.pop(body.proposal_id,None)
        return result

    @app.post('/api/ai-rewrite/{block_id}')
    async def rewrite(block_id:str,body:RewriteRequest):
        current=mapper.get_block(block_id)
        if current['version']!=body.expected_version:
            return JSONResponse({'error':'源码已发生变化，请重新选择当前块。'},status_code=409)
        if current.get('readonly') or current['type'] in ('equation','figure','table','code'):
            return JSONResponse({'error':'请选中可润色的正文、标题、图注或表注。'},status_code=422)
        if not ai_rewrite.public_settings(root)['configured']:
            return JSONResponse({'error':'AI 未配置。可先手动编辑，稍后填写本地 .env。'},status_code=503)
        try:
            payload=ai_rewrite.context_for(mapper,block_id,body.instruction)
            after=await ai_rewrite.propose(root,payload)
        except Exception as e:
            # Provider response bodies and authorization headers are never relayed.
            return JSONResponse({'error':str(e) if isinstance(e,(ValueError,RuntimeError)) else 'AI 请求失败，请检查本地服务配置。'},status_code=502)
        try:
            mapper.validate_patch(block_id,after,body.expected_version,operation='ai-accept')
            validation={'ok':True,'message':'差异通过保护检查；尚未写入。'}
        except MapperError as e:
            validation={'ok':False,'message':str(e)}
        proposal_id=secrets.token_urlsafe(24)
        proposal={'id':block_id,'before':current['content'],'after':after,'version':body.expected_version,
                  'validation':validation,'created':time.time()}
        # Bounded, process-local proposals: a restart invalidates pending accepts.
        for key,value in list(proposals.items()):
            if value['created']<time.time()-3600:proposals.pop(key,None)
        if len(proposals)>=100:proposals.pop(next(iter(proposals)))
        proposals[proposal_id]=proposal
        return {**proposal,'proposal_id':proposal_id,
                'diff':'\n'.join(difflib.unified_diff(current['content'].splitlines(),after.splitlines(),fromfile='before',tofile='after',lineterm=''))}

    @app.post('/api/block/{block_id}/undo')
    async def undo(block_id:str,body:VersionRequest):
        return await asyncio.to_thread(mapper.undo,block_id,body.expected_version)

    @app.get('/api/history')
    def history(block_id:str|None=None):return {'items':mapper.history(block_id)}

    @app.get('/api/diff')
    def diff():return mapper.diff()

    @app.post('/api/build-pdf')
    def build():return builder.start()

    @app.get('/api/build-pdf/status')
    def build_status():return builder.status()

    @app.get('/api/build-pdf/log')
    def build_log():
        path=root/'paper/build/build.log'
        return {'text':path.read_text(encoding='utf-8') if path.exists() else '尚无构建日志。'}

    @app.get('/api/pdf')
    def pdf():
        path=root/'paper/build/main.pdf'
        if not path.exists():return JSONResponse({'error':'尚未生成 PDF。'},status_code=404)
        return FileResponse(path,media_type='application/pdf')

    @app.get('/assets/{asset_path:path}')
    def asset(asset_path:str):
        path=(root/asset_path).resolve()
        allowed=[(root/'paper/figures').resolve(),(root/'paper_editor/cache').resolve()]
        permitted=any(path.is_relative_to(p) for p in allowed) or path==(root/'paper/paper_figures.pdf').resolve()
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.svg','.webp','.pdf') or not permitted or not path.is_file():
            return JSONResponse({'error':'图片不存在或路径不可访问。'},status_code=404)
        return FileResponse(path)

    @app.get('/api/events')
    async def events(request:Request):
        async def stream():
            last='';tick=0
            while not await request.is_disconnected():
                try:
                    doc=await asyncio.to_thread(mapper.document)
                    revision=doc['revision']
                    if revision!=last:
                        last=revision
                        yield 'event: document_changed\ndata: '+json.dumps({'revision':revision})+'\n\n'
                except MapperError as e:
                    yield 'event: source_error\ndata: '+json.dumps({'error':str(e)},ensure_ascii=False)+'\n\n'
                tick+=1
                if tick%20==0:yield ': keepalive\n\n'
                await asyncio.sleep(1)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

    app.mount('/static',StaticFiles(directory=root/'paper_editor/static'),name='static')
    vendor=root/'paper_editor/vendor/mathjax'
    if not vendor.exists():vendor=root/'node_modules/mathjax/es5'
    if vendor.exists():app.mount('/vendor/mathjax',StaticFiles(directory=vendor),name='mathjax')
    return app
