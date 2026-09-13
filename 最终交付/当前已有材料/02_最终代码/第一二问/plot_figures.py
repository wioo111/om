"""All publication figures come from final result/certificate files.

Matplotlib defaults are used. Numerical curves are illustrations; they do not
supply the global proof. The integer verifier in proofs is independent.
"""
from pathlib import Path
import sys,json,math,csv
from fractions import Fraction
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Rectangle
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from q12.geometry import clip_raw,diameter_raw,njit
from q12.policy import policy_constants,safe_centers_local,reception_safe_local
FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
from matplotlib import font_manager
_font_path=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
if _font_path.exists():
    font_manager.fontManager.addfont(str(_font_path))
    plt.rcParams['font.family']=[font_manager.FontProperties(fname=str(_font_path)).get_name()]
else:
    available={f.name for f in font_manager.fontManager.ttflist}
    chosen=next((f for f in ['Microsoft YaHei','SimHei','Arial Unicode MS'] if f in available),None)
    if chosen is None:raise RuntimeError('Install a Chinese font before generating figures')
    plt.rcParams['font.family']=[chosen,'DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
plt.rcParams['svg.fonttype']='none'
plt.rcParams['pdf.fonttype']=42
MAN=[]

def new(title,x='x（米）',y='y（米）',size=(7.1,4.7)):
    fig,ax=plt.subplots(figsize=size,layout='constrained');ax.set_title(title,fontsize=13,pad=10)
    ax.set_xlabel(x);ax.set_ylabel(y);ax.tick_params(labelsize=9)
    return fig,ax

def save(fig,stem,caption,source,main=False):
    for ext in ['png','pdf','svg']:fig.savefig(FIG/f'{stem}.{ext}',dpi=300)
    plt.close(fig);MAN.append(dict(stem=stem,caption=caption,source=source,main=main,formats=['png','pdf','svg']))

def geom(ax,m):
    p=np.asarray(m['vertices']);p=np.vstack([p,p[0]]);ax.fill(p[:,0],p[:,1],alpha=.17,label='定位区域')
    ax.plot(p[:,0],p[:,1],linewidth=1.5)
    a,b=np.array(m['A']),np.array(m['B']);ax.plot([a[0],b[0]],[a[1],b[1]],'o-',label='最远顶点对')
    ax.add_patch(Circle(m['diameter_circle_center'],m['D']/2,fill=False,linestyle='--',label='直径为 D 的圆'))
    ax.add_patch(Circle(m['mec_center'],m['radius'],fill=False,linestyle=':',linewidth=1.7,label='最小包围圆'))
    ax.set_aspect('equal');ax.margins(.25)

@njit(cache=True)
def post_d(poly,s,phi,eps):
    a=phi-eps;nx=math.sin(a);ny=-math.cos(a);p=clip_raw(poly,nx,ny,nx*s[0]+ny*s[1])
    a=phi+eps;nx=-math.sin(a);ny=math.cos(a);p=clip_raw(p,nx,ny,nx*s[0]+ny*s[1])
    return diameter_raw(p)[0] if len(p)>0 else 0.

def main():
    from evidence import require_fresh
    require_fresh('experiments',('results/',))
    q1=json.loads((ROOT/'results/q1_summary.json').read_text());q2=json.loads((ROOT/'results/q2_summary.json').read_text())
    proof=json.loads((ROOT/'proofs/global_certificate.json').read_text());k=policy_constants();s=np.array([k.local_x,k.local_y]);e=math.pi/180
    for name,stem,title,caption,mainfig in [
        ('typical','q1_01_geometry','交会多边形、直径与覆盖圆','典型定位多边形的直径由最远顶点对给出；本例直径圆覆盖区域。',True),
        ('equilateral_tight','q1_02_jung_tight','等边三角形：Jung 上界达到等号','三次有效测向产生的等边三角形，D=30米，最小包围圆半径为10√3米。',True),
        ('two_station_counterexample','q1_03_two_station','两次测向也可出现直径圆不覆盖','本例 q=sec(1°)>1，证明“两次测向一定覆盖”不成立；图为局部纵向放大，横纵轴比例不等。',False)]:
        m=q1['examples'][name]['metrics'];f,a=new(title);geom(a,m)
        if name=='two_station_counterexample':a.set_aspect('auto');a.set_ylim(-.27,.27);a.set_xlim(-.4,10.4)
        if name=='two_station_counterexample':
            a.legend(loc='upper center',fontsize=8,ncol=2)
            tx,ha=.5,'center'
        else:
            a.legend(loc='upper left',bbox_to_anchor=(1.01,1),fontsize=8)
            tx,ha=.98,'right'
        a.text(tx,.04,f'D = {m["D"]:.6f} m\n2R*/D = {m["q"]:.6f}',transform=a.transAxes,ha=ha,va='bottom',fontsize=9)
        save(f,stem,caption,'q1_summary.json:examples.'+name,mainfig)
    rows=q1['summary'];n=np.array([x['n'] for x in rows]);med=np.array([x['median_D'] for x in rows])
    f,a=new('检测点增加时的定位区域直径','检测点数量 n','纯交会多边形直径（米）')
    a.plot(n,med,'o-',label='中位数');a.fill_between(n,[x['p25_D'] for x in rows],[x['p75_D'] for x in rows],alpha=.15,label='25%—75%分位区间')
    a.legend();a.set_xticks(n);a.grid(axis='y',alpha=.2)
    save(f,'q1_04_diameter_vs_n','200个共享场景、每场最多12个检测点。n=2有1个无界交会区域，图中分位数仅对应有界区域。','q1_summary.json:summary')
    f,a=new('固定观测下的角误差敏感性','允许误差半宽（度）','交会区域直径（米）')
    a.plot([r['eps_deg'] for r in q1['eps_sensitivity']],[r['D_m'] for r in q1['eps_sensitivity']],'o-');a.grid(alpha=.2)
    save(f,'q1_05_error_sensitivity','仅扩大误差区间，固定同一组零误差观测。区域包含关系保证直径不减。','q1_summary.json:eps_sensitivity')
    f,a=new('圆约束的内外逼近夹逼','多边形边数 N','相对1500米的直径差（米）')
    rr=q1['disk_brackets'];a.plot([x['n'] for x in rr],[x['upper_D']-1500 for x in rr],'o-',label='外近似 D−1500')
    a.plot([x['n'] for x in rr],[1500-x['lower_D'] for x in rr],'s--',label='1500−内近似 D');a.set_xscale('log',base=2);a.set_yscale('log');a.legend();a.grid(alpha=.2)
    save(f,'q1_06_disk_bracket','圆约束只属于辅助先验区域。内外集合包含关系给出直径夹逼，未把单圆径向误差直接当成交集直径误差。','q1_summary.json:disk_brackets')
    f,a=new('完整接收安全区与两个全局最优点')
    xx,yy=np.meshgrid(np.linspace(-50,1540,600),np.linspace(-950,950,600));pts=np.c_[xx.ravel(),yy.ravel()];mask=reception_safe_local(pts).reshape(xx.shape)
    a.contourf(xx,yy,mask.astype(float),levels=[.5,1.5],alpha=.17)
    a.contour(xx,yy,mask.astype(float),levels=[.5],linewidths=1.1)
    for i,c in enumerate(safe_centers_local()):a.add_patch(Circle(c,1000,fill=False,linestyle='--' if i<2 else ':',alpha=.55))
    pminus=1500*np.array([math.cos(e),-math.sin(e)]);pplus=1500*np.array([math.cos(e),math.sin(e)])
    a.fill([0,pminus[0],1500,pplus[0]],[0,pminus[1],0,pplus[1]],alpha=.2,label='首次源位置不确定区域')
    a.plot([s[0],s[0]],[s[1],-s[1]],'*',markersize=12,label='两个全局最优点');a.plot(0,0,'o');a.annotate(r'$S_1$',(0,0),xytext=(5,8),textcoords='offset points')
    a.set_xlim(-50,1540);a.set_ylim(-930,930);a.set_aspect('equal');a.legend(loc='upper right',fontsize=8)
    save(f,'q2_01_safe_region','四个半径1000米的圆盘交集是完整未截断扇形的必要且充分接收安全区，搜索不受Ω或移动距离1000米的错误限制。','analytic four-disk theorem; policy constants',True)
    f,a=new('可连续选取的20%近优候选区域')
    xs=np.linspace(s[0]-6,s[0]+6,300);ys=np.linspace(s[1]-6,s[1]+6,300);xx,yy=np.meshgrid(xs,ys)
    from q12.policy import good_candidate_mask
    m=good_candidate_mask(np.c_[xx.ravel(),yy.ravel()]).reshape(xx.shape)
    a.contourf(xx,yy,m.astype(float),levels=[.5,1.5],alpha=.3)
    a.add_patch(Rectangle((s[0]-4,s[1]-4),8,8,fill=False,linestyle='--',label='8米×8米候选框'))
    a.add_patch(Circle(safe_centers_local()[0],1000,fill=False,label='接收安全边界'))
    a.plot(*s,'*',markersize=12,label='精确最优点');a.set_xlim(xs[0],xs[-1]);a.set_ylim(ys[0],ys[-1]);a.set_aspect('equal');a.legend(loc='lower left',fontsize=8)
    save(f,'q2_02_candidate_region','阴影内所有点都满足接收保证和J≤1.2D*，不是离散网格点的集合。下方对称候选区由镜像获得。','global_certificate.json:candidate_region',True)
    w=q2['worst_case'];m=w['posterior']['outer_metrics'];f,a=new('达到全局最坏值的真实观测')
    p=np.array(m['vertices']);p=np.vstack([p,p[0]]);a.fill(p[:,0],p[:,1],alpha=.2,label='最终定位区域');a.plot(p[:,0],p[:,1])
    g=np.array(w['G']);q=np.array(w['q']);a.plot([g[0],q[0]],[g[1],q[1]],'o-',label='达到 D* 的不可区分源对')
    for name,pos in [('P',g),('Q',q)]:a.annotate(name,pos,xytext=(5,6),textcoords='offset points')
    a.set_aspect('equal');a.margins(.15);a.legend(loc='lower left',fontsize=8)
    a.text(.99,.02,f'D* = {k.diameter_star:.6f} m',ha='right',transform=a.transAxes)
    save(f,'q2_03_worst_case','两个候选源产生完全相同的两次示向度，给出物理可实现的全局下界；上界证明在同一观测处达到等号。','q2_summary.json:worst_case',True)
    P=np.array([[0,0],pminus,[1500,-1500*math.tan(e/2)],[1500,1500*math.tan(e/2)],pplus])
    angles=np.sort(np.r_[np.linspace(-155,-32,1600),w['bearing2']]);vals=[post_d(P,s,math.radians(x),e) for x in angles]
    f,a=new('连续示向度上界证书','第二次示向度（度；使用连续角分支）','定位区域直径（米）')
    a.plot(angles,vals,linewidth=1.4,label='数值曲线（仅用于展示）')
    bx=[];by=[]
    for c in proof['all_other_headings']['partition']:
        l,h=float(Fraction(c['lo_deg'])),float(Fraction(c['hi_deg']))
        if h<angles[0] or l>angles[-1]:continue
        bx.extend([l,h,np.nan]);by.extend([math.sqrt(float(Fraction(c['upper_squared_m'])))]*2+[np.nan])
    a.plot(bx,by,linestyle='--',linewidth=.8,label='各完整角区间的严格上界')
    a.axhline(k.diameter_star,linestyle=':',label='全局值 D*');a.set_xlim(-152,-33);a.set_ylim(0,119);a.legend(loc='lower center',fontsize=8)
    save(f,'q2_04_continuous_certificate','63个闭区间覆盖解析活动区间以外的全部示向度；活动区间内用导数符号和顶点对比较证明精确最大值。','global_certificate.json:all_other_headings',True)
    f,a=new('全局下界归结为一元方程','上边界源的径向距离 t（米）','Q(t) / 1000')
    sd,cd,sn,cn=math.sin(2*e),math.cos(2*e),math.sin(4*e),math.cos(4*e)
    tt=np.linspace(1390,1412,400);K=sd*(1000**2-5*(1500-5));H=(1500-5)*sn
    qq=-K-H*tt+1000*np.sqrt((sd*1490+tt*sn)**2+(1500*cd-tt*cn)**2)
    a.plot(tt,qq/1000);a.axhline(0,linestyle='--');a.axvline(k.t_star,linestyle=':');a.annotate(f't* = {k.t_star:.6f}',(k.t_star,0),xytext=(12,18),textcoords='offset points');a.grid(alpha=.2)
    save(f,'q2_05_quadratic_root','二次方程的小根由未平方方程的正号条件筛选；Q(t*)=0给出整个连续可行域的统一下界。','analytic coefficients; policy constants')
    with (ROOT/'results/q2_paired_samples.csv').open(encoding='utf-8-sig') as f:raw=list(csv.DictReader(f))
    labels={'minimax':'全局极小极大策略','along_750':'沿示向度前进750米','perpendicular_1000':'垂线方向1000米','random_omega':'Ω内随机点'}
    f,a=new('配对实验中的定位区域直径分布','后验区域直径上界（米）','经验累计比例（成功观测内）')
    for key,lab in labels.items():
        x=np.sort([float(r['D_upper']) for r in raw if r['strategy']==key and r['D_upper']]);a.plot(x,np.arange(1,len(x)+1)/len(x),label=lab)
    a.set_xlim(0,800);a.set_ylim(0,1);a.legend(fontsize=8);a.grid(alpha=.2)
    save(f,'q2_06_empirical_cdf','同批1500个场景。CDF仅显示有后验的观测；失败案例完整保存在原始CSV，并在下一图单独报告。','q2_paired_samples.csv')
    f,a=new('全部配对场景的接收失败率','策略','接收失败率')
    rr=[r for r in q2['summary'] if r['pose']=='all'];keys=list(labels);rates=[next(x['no_signal']/x['N'] for x in rr if x['strategy']==key) for key in keys]
    bars=a.bar([labels[x] for x in keys],rates);a.set_ylim(0,.75)
    for b,v in zip(bars,rates):a.text(b.get_x()+b.get_width()/2,v+.015,f'{v:.1%}',ha='center')
    a.tick_params(axis='x',labelsize=8);a.grid(axis='y',alpha=.2)
    save(f,'q2_07_failure_rate','所有策略均使用1500个场景，未删除无信号样本。理论接收保证与有限样本中零失败严格区分。','q2_summary.json:summary')
    (FIG/'manifest.json').write_text(json.dumps(MAN,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'生成 {len(MAN)} 张图；每张含 PNG、PDF、SVG。')
    return MAN

if __name__=='__main__':main()
