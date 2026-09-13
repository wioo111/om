"""Generate the seven paper figures from frozen, published data. No network or simulator.

Requirements: Python 3.10+, matplotlib, numpy. Install an available CJK font locally.
SVG text remains editable; no font file is packaged. Values/precision: figure_data.json.
"""
from pathlib import Path
import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Rectangle, Polygon

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT/'figure_data.json').read_text(encoding='utf-8'))

def configure():
    installed = {f.name for f in font_manager.fontManager.ttflist}
    choices = ['Noto Sans CJK SC','Noto Sans CJK JP','Microsoft YaHei','SimHei','WenQuanYi Zen Hei']
    selected = next((name for name in choices if name in installed), None)
    if not selected:
        raise RuntimeError('Install a CJK font; do not publish figures with missing glyphs.')
    plt.rcParams.update({'font.family': selected, 'font.size':11, 'axes.titlesize':14,
                         'axes.labelsize':11, 'svg.fonttype':'none', 'axes.unicode_minus':False,
                         'svg.hashsalt':'cumcm-p3p4-paper-71a22c1', 'savefig.dpi':180})

def base(title, figsize=(8.8,5.4)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, loc='left', pad=15, fontweight='bold')
    ax.spines[['top','right']].set_visible(False)
    return fig, ax

def compact_svg(path):
    """Compact SVG structure; round only drawing coordinates to 0.001 pt."""
    text=path.read_text(encoding='utf-8')
    ns='http://www.w3.org/2000/svg'
    ET.register_namespace('',ns)
    ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
    root=ET.fromstring(text)
    used=set(re.findall(r'url\(#([^)]*)\)',text)) | set(re.findall(r'href="#([^"]+)"',text))
    for parent in root.iter():
        for child in list(parent):
            if child.tag==f'{{{ns}}}metadata': parent.remove(child)
    counts=Counter(el.get('style') for el in root.iter() if el.get('style'))
    shared={style:f's{i}' for i,(style,count) in enumerate(counts.items()) if count>1}
    for el in root.iter():
        if 'id' in el.attrib and el.attrib['id'] not in used: del el.attrib['id']
        style=el.get('style')
        if style in shared:
            el.set('class',shared[style]); del el.attrib['style']
        for key in ('d','points','transform','x','y','width','height','viewBox'):
            if key in el.attrib:
                el.set(key,re.sub(r'-?\d+\.\d+(?:e[+-]?\d+)?',lambda m:format(float(m.group()),'.3f').rstrip('0').rstrip('.'),el.attrib[key]).replace('\n',' '))
    style=ET.Element(f'{{{ns}}}style')
    style.text=''.join('.'+name+'{'+value+'}' for value,name in shared.items())
    root.insert(0,style)
    def flatten(parent):
        for child in list(parent):
            flatten(child)
            if child.tag==f'{{{ns}}}g' and not child.attrib:
                i=list(parent).index(child)
                for offset,item in enumerate(list(child)): parent.insert(i+offset,item)
                parent.remove(child)
    flatten(root)
    out=ET.tostring(root,encoding='unicode')
    out=re.sub(r'>\s+<','><',out)
    path.write_text(out+'\n',encoding='utf-8')

def save(fig, name, output, preview):
    fig.tight_layout(pad=1.5)
    path = output/(name+'.svg')
    fig.savefig(path, format='svg', metadata={'Date':None,'Creator':'P3/P4 paper figure generator'})
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview/(name+'.png'), dpi=160)
    plt.close(fig)
    # Remove cosmetic whitespace only; leave all paths and text unchanged.
    svg=path.read_text(encoding='utf-8')
    svg=re.sub(r'>\s+<','><',svg)
    path.write_text(svg,encoding='utf-8')
    compact_svg(path)
    return path

def generate(output=None, preview=None):
    configure()
    output=Path(output or ROOT/'figures'); output.mkdir(parents=True,exist_ok=True)
    preview=Path(preview) if preview else None
    paths=[]

    # Q3-1: continuous optical cover; purely illustrative geometry.
    fig,ax=base('连续光学覆盖：先覆盖区域，再比较行动成本',(8.8,4.8))
    radius=19.99; halfwidth=6; length=90
    h=math.sqrt(radius**2-halfwidth**2)
    centers=np.linspace(-length/2+h,length/2-h,3)
    poly=np.array([[-43,-4],[-30,-6],[30,-4],[43,1],[38,6],[-26,5]])
    ax.add_patch(Rectangle((-45,-6),90,12,fill=False,linestyle='--',linewidth=1.2))
    ax.add_patch(Polygon(poly,alpha=.22,linewidth=1.2))
    for i,x in enumerate(centers,1):
        ax.add_patch(Circle((x,0),radius,fill=False,linewidth=1.5))
        ax.plot(x,0,marker='o',markersize=4)
        ax.text(x,-23,f'q{i}',ha='center')
    ax.text(0,9,'候选区域及其外包矩形',ha='center')
    ax.text(0,28,'w = 6 m；r = 19.99 m；h = √(r² − w²)；3 个清除位置',ha='center',fontsize=10)
    ax.set(xlim=(-60,60),ylim=(-29,33),xlabel='示意坐标 x / m',ylabel='示意坐标 y / m')
    ax.set_aspect('equal'); paths.append(save(fig,'q3_01_optical_cover',output,preview))

    # Q3-3: exact formal-run action cost decomposition.
    rows=DATA['q3_formal']; fig,ax=base('第三问正式测试：虚拟时间成本构成')
    bottom=np.zeros(3)
    for key,label,hatch in [('move_s','移动',''),('measure_s','检测','//'),('switch_s','切频道','xx'),('clear_s','光学与清除','--')]:
        values=np.array([r[key] for r in rows]); ax.bar(range(3),values,bottom=bottom,width=.55,label=label,hatch=hatch)
        if key=='move_s':
            for i,v in enumerate(values): ax.text(i,v/2,f'{v:.1f}',ha='center',va='center',fontsize=11)
        bottom+=values
    for i,r in enumerate(rows): ax.text(i,r['total']+45,f"{r['total']:.2f} s",ha='center',fontsize=11)
    ax.set_xticks(range(3),[f"正式 {r['run']}\n已清除 {r['cleared']} 个" for r in rows])
    ax.set(ylabel='虚拟时间 / s',ylim=(0,3800),yticks=[0,1000,2000,3000])
    ax.legend(ncol=4,loc='upper center',frameon=False,fontsize=10)
    paths.append(save(fig,'q3_03_formal_cost',output,preview))

    # Q3-2: practice data; actual known N, not formal hidden N.
    fig,ax=base('第三问同版本演练：源数与平均清除耗时')
    rows=DATA['q3_practice']
    ax.scatter([r['N'] for r in rows],[r['total']/r['N'] for r in rows],s=55)
    offsets=[(8,-8),(8,5),(-24,7),(8,5),(8,6),(8,5),(8,4),(8,-13)]
    for r,off in zip(rows,offsets):
        ax.annotate(r['id'],(r['N'],r['total']/r['N']),xytext=off,textcoords='offset points',fontsize=10)
    ax.set(xlabel='演练结束后公开的源总数 N',ylabel='平均定位清除时间（秒/源）',xlim=(9.6,16.4),ylim=(165,345),xticks=list(range(10,17)))
    ax.text(.98,.98,'8/8 场全清；98/98 个源\n不同案例不构成配对提速证据',transform=ax.transAxes,ha='right',va='top',fontsize=10)
    paths.append(save(fig,'q3_02_practice',output,preview))

    # Q4-1: actual 21-station construction; not a runtime robot trajectory.
    fig,ax=base('第四问：中心＋8 个内环站＋12 个外环站',(7.8,7.1))
    g=DATA['q4_geometry']; ro=g['outer_apothem']/math.cos(math.pi/g['outer_count'])
    ai=np.arange(8)*2*math.pi/8; ao=np.arange(12)*2*math.pi/12
    inner=g['inner_radius']*np.c_[np.cos(ai),np.sin(ai)]; outer=ro*np.c_[np.cos(ao),np.sin(ao)]
    ax.add_patch(Circle((0,0),1800,fill=False,linewidth=1.6))
    ax.add_patch(Polygon(outer,fill=False,linestyle='--',linewidth=1))
    ax.add_patch(Circle((0,0),999.999,fill=False,linestyle=':',linewidth=.8))
    ax.scatter([0],[0],marker='*',s=90,label='中心站')
    ax.scatter(inner[:,0],inner[:,1],marker='o',s=35,label='内环站（999.999 m）')
    ax.scatter(outer[:,0],outer[:,1],marker='^',s=42,label='外环站（约 1863.50 m）')
    for i,(x,y) in enumerate(outer,1):ax.text(x*1.09,y*1.09,f'O{i}',ha='center',va='center',fontsize=9)
    for i,(x,y) in enumerate(inner,1):ax.text(x*1.1,y*1.1,f'I{i}',ha='center',va='center',fontsize=9)
    ax.set(xlabel='x / m',ylabel='y / m',xlim=(-2250,2250),ylim=(-2250,2500),xticks=[-2000,-1000,0,1000,2000],yticks=[-2000,-1000,0,1000,2000])
    ax.set_aspect('equal');ax.legend(loc='upper right',fontsize=9,frameon=False,ncol=1)
    paths.append(save(fig,'q4_01_compact_stations',output,preview))

    # Q4-2: zero-detour probe geometry; hypotheses are explicitly not source truth.
    fig,ax=base('沿既有移动线段补测：不额外绕路，但检测仍计费',(8.8,4.6))
    ax.plot([0,5,10],[0,0,0],marker='o',linewidth=2)
    ax.plot([-1,5],[1.5,4],linestyle='--',linewidth=1)
    ax.plot([5,5],[0,4],linestyle=':',linewidth=1.4)
    ax.plot(5,4,marker='x',markersize=9);ax.plot(-1,1.5,marker='s',markersize=5)
    ax.text(0,-.55,'A：当前点',ha='center');ax.text(5,-.55,'P：插入补测点',ha='center');ax.text(10,-.55,'B：原扫描站',ha='center')
    ax.text(-1,1.8,'已有正向测点',ha='left',fontsize=10)
    ax.text(5.2,4.1,'假设位置（仅用于价值排序）',fontsize=10)
    ax.text(5,-1.6,'|AP| + |PB| = |AB|；新增动作成本 = 5 s + 增量换频道成本',ha='center',fontsize=10)
    ax.annotate('',xy=(9.3,.3),xytext=(5.7,.3),arrowprops={'arrowstyle':'->'})
    ax.text(7.5,.55,'补测后恢复原动作',ha='center',fontsize=10)
    ax.set(xlim=(-2,12),ylim=(-2.1,5.3));ax.set_aspect('equal');ax.set_axis_off()
    paths.append(save(fig,'q4_02_zero_detour',output,preview))

    # Q4-3: equal-N diagnostic over the explicitly mixed 168-scene suite.
    fig,ax=base('第四问离线分层：确认 56 场＋边界 112 场')
    d=DATA['q4_offline']
    for key,marker in [('HuntP4','o'),('RouteAwareP4','s'),('RouteProbeP4','^')]:
        ax.plot(d['N'],d[key],marker=marker,markersize=5,linewidth=1.5,label=key)
    ax.set(xlabel='模拟场景源数 N（不向策略提供）',ylabel='逐 N 平均清除时间（秒/源）',xticks=d['N'],ylim=(350,730))
    ax.legend(frameon=False,fontsize=10)
    paths.append(save(fig,'q4_03_offline_by_n',output,preview))

    # Q4-4: all successful formal-entry records; two failed connections have no T.
    fig,ax=base('第四问正式入口：3 次正常结束记录')
    rows=[r for r in DATA['q4_formal_entry'] if r['status']=='normal_stop']
    ax.bar(range(3),[r['per_cleared'] for r in rows],width=.55)
    for i,r in enumerate(rows):
        ax.text(i,r['per_cleared']+10,f"{r['per_cleared']:.2f}\nT = {r['total']:.2f} s",ha='center',fontsize=10)
    ax.set_xticks(range(3),[f"{r['id']}\n已清除 {r['cleared']} 个" for r in rows])
    ax.set(ylabel='T/已清除数（秒/源）',ylim=(0,700),yticks=[0,200,400,600])
    ax.text(.98,.98,'另有 2 次连接失败，无有效耗时\n模式未由协议核验；总源数未公开',transform=ax.transAxes,ha='right',va='top',fontsize=9)
    paths.append(save(fig,'q4_04_formal_entry',output,preview))
    return paths

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'figures')
    parser.add_argument('--preview',type=Path)
    args=parser.parse_args()
    for path in generate(args.output,args.preview):print(path)
