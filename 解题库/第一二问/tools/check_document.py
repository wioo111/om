"""Structural/document checks and page renders, separate from theorem verification."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import pymupdf as fitz
from PIL import Image, ImageDraw
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--pdf',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
doc=fitz.open(a.pdf)
pages=[]
for i,page in enumerate(doc):
    text=page.get_text()
    spans=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for line in b['lines'] for s in line['spans']]
    bad=[s['text'] for s in spans if s['bbox'][0]<-1 or s['bbox'][1]<-1 or s['bbox'][2]>page.rect.width+1 or s['bbox'][3]>page.rect.height+1]
    page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(a.out/f'page-{i+1}.png')
    pages.append(dict(page=i+1,characters=len(text),outside_page=bad,replacement_glyphs=text.count('\ufffd')))
report=dict(pdf=str(a.pdf),sha256=hashlib.sha256(a.pdf.read_bytes()).hexdigest(),page_count=len(doc),pages=pages)
for start in range(0,len(doc),3):
    sheet=Image.new('RGB',(1800,880),'#dddddd')
    for col,index in enumerate(range(start,min(start+3,len(doc)))):
        page=Image.open(a.out/f'page-{index+1}.png').convert('RGB')
        page.thumbnail((595,850))
        sheet.paste(page,(col*600,25))
        ImageDraw.Draw(sheet).text((col*600+10,5),f'Page {index+1}',fill='black')
    sheet.save(a.out/f'contact-{start+1}.png')
(a.out/'structure.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
