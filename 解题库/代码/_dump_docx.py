import zipfile, re
from xml.etree import ElementTree as ET

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def docx_text(path):
    z = zipfile.ZipFile(path)
    xml = z.read('word/document.xml').decode('utf-8')
    root = ET.fromstring(xml)
    out = []
    for p in root.iter('{%s}p' % NS['w']):
        line = ''.join(t.text or '' for t in p.iter('{%s}t' % NS['w']))
        out.append(line)
    return '\n'.join(out)

a1 = docx_text(r'C:\Users\LENOVO\Desktop\CUMCM2026Problems\原题\附件\附件1.docx')
a2 = docx_text(r'C:\Users\LENOVO\Desktop\CUMCM2026Problems\原题\附件\附件2.docx')
open(r'C:\Users\LENOVO\Desktop\CUMCM2026Problems\原题\附件\_a1.txt', 'w', encoding='utf-8').write(a1)
open(r'C:\Users\LENOVO\Desktop\CUMCM2026Problems\原题\附件\_a2.txt', 'w', encoding='utf-8').write(a2)
print('a1:', len(a1), 'a2:', len(a2))