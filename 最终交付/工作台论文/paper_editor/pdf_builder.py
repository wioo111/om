"""Explicit, isolated XeLaTeX build jobs; text edits never invoke this module."""
from __future__ import annotations
from pathlib import Path
import json, os, shutil, subprocess, tempfile, threading, uuid
from datetime import datetime, timezone

class PDFBuilder:
    def __init__(self, root, mapper):
        self.root=Path(root);self.mapper=mapper;self.lock=threading.Lock()
        self.state={'status':'idle','log_summary':'尚未构建工作台 PDF','pdf_path':None,'pdf_url':None}
        self.destination=self.root/'paper/build'
        self.destination.mkdir(parents=True,exist_ok=True)
        status=self.destination/'build_status.json'
        if status.exists():
            previous=json.loads(status.read_text(encoding='utf-8'))
            if previous.get('status') in ('success','failed'):self.state=previous

    def status(self):
        with self.lock:return dict(self.state)

    def start(self):
        with self.lock:
            if self.state['status']=='running':return dict(self.state)
            self.state={'status':'running','job_id':uuid.uuid4().hex,'log_summary':'正在从正式 LaTeX 源码构建…',
                        'pdf_path':None,'pdf_url':None,'started':datetime.now(timezone.utc).isoformat()}
        threading.Thread(target=self._run,daemon=True,name='paper-pdf-builder').start()
        return self.status()

    def _run(self):
        logs=[]
        try:
            exe=shutil.which('xelatex')
            if not exe:
                p=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/MiKTeX/miktex/bin/x64/xelatex.exe'
                if p.exists():exe=str(p)
            if not exe:raise RuntimeError('未找到 XeLaTeX。请安装 MiKTeX/TeX Live 或将 xelatex 加入 PATH。')
            revision=self.mapper.document()['revision']
            with tempfile.TemporaryDirectory(prefix='paper-build-') as td:
                stage=Path(td)
                paper=self.root/'paper'
                for name in ('main.tex','source','figures','paper_figures.pdf'):
                    p=paper/name
                    if p.is_dir():shutil.copytree(p,stage/name)
                    elif p.exists():shutil.copy2(p,stage/name)
                if self.mapper.document()['revision']!=revision:
                    raise RuntimeError('复制构建快照时源码发生变化，请重新点击构建。')
                output=stage/'output';output.mkdir()
                stable=False
                for i in range(4):
                    aux=output/'main.aux'
                    before=aux.read_bytes() if aux.exists() else None
                    command=[exe,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error','-file-line-error',
                             '-output-directory='+str(output),'main.tex']
                    completed=subprocess.run(command,cwd=stage,capture_output=True,text=True,
                                             encoding='utf-8',errors='replace',timeout=180)
                    text=completed.stdout+'\n'+completed.stderr
                    logs.append(f'PASS {i+1}; exit_code={completed.returncode}\n'+text)
                    if completed.returncode:raise RuntimeError('LaTeX 编译失败，见日志摘要。')
                    after=aux.read_bytes() if aux.exists() else None
                    stable=before is not None and before==after
                    if i>=1 and (stable or 'Rerun to get cross-references right' not in text):break
                result=output/'main.pdf'
                if not result.exists():raise RuntimeError('编译没有生成 PDF。')
                target=self.destination/'main.pdf'
                tmp=self.destination/'main.pdf.tmp';shutil.copy2(result,tmp);os.replace(tmp,target)
                warnings=[line for line in text.splitlines() if any(x in line for x in ('Warning','Overfull','Missing character'))]
                current=self.mapper.document()['revision']
                self._set(status='success',pdf_path=str(target),pdf_url='/api/pdf',source_revision=revision,
                          stale=current!=revision,reference_records_stable=stable,
                          log_summary='PDF 构建成功。'+('构建期间源码有新修改，此 PDF 对应点击构建时的版本。' if current!=revision else '')+
                          ('\n'+'\n'.join(warnings[-12:]) if warnings else ''),error=None)
        except Exception as e:
            lines='\n'.join(logs).splitlines()
            errors=[line for line in lines if line.startswith('!') or ': error' in line.lower() or 'Error' in line]
            self._set(status='failed',error=str(e),log_summary=str(e)+'\n'+'\n'.join((errors or lines[-24:])[-24:]),pdf_path=None,pdf_url=None)
        finally:
            (self.destination/'build.log').write_text('\n\n'.join(logs),encoding='utf-8')
            (self.destination/'build_status.json').write_text(json.dumps(self.status(),ensure_ascii=False,indent=2),encoding='utf-8')

    def _set(self,**values):
        with self.lock:self.state.update(values,finished=datetime.now(timezone.utc).isoformat())
