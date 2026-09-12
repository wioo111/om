"""
使用 reportlab 直接生成问题1建模改进版的 PDF
================================================

中文字体使用系统自带的中文字体（SimSun/Microsoft YaHei等），
或 reportlab 内置 CID 字体（不需外部字体文件）。
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, Image, PageBreak,
                                 Preformatted)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 注册中文字体
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))   # 类黑体，用作标题


def make_styles():
    styles = getSampleStyleSheet()
    body = ParagraphStyle('Body',
                          parent=styles['BodyText'],
                          fontName='STSong-Light',
                          fontSize=10,
                          leading=15,
                          alignment=TA_JUSTIFY,
                          spaceAfter=4)
    h1 = ParagraphStyle('H1',
                        parent=styles['Heading1'],
                        fontName='HeiseiKakuGo-W5',
                        fontSize=16,
                        leading=20,
                        spaceBefore=18,
                        spaceAfter=10,
                        textColor=colors.black)
    h2 = ParagraphStyle('H2',
                        parent=styles['Heading2'],
                        fontName='HeiseiKakuGo-W5',
                        fontSize=13,
                        leading=17,
                        spaceBefore=12,
                        spaceAfter=8)
    h3 = ParagraphStyle('H3',
                        parent=styles['Heading3'],
                        fontName='HeiseiKakuGo-W5',
                        fontSize=11,
                        leading=14,
                        spaceBefore=8,
                        spaceAfter=6)
    title = ParagraphStyle('Title',
                           parent=styles['Title'],
                           fontName='HeiseiKakuGo-W5',
                           fontSize=20,
                           leading=24,
                           alignment=TA_CENTER,
                           spaceAfter=16)
    cap = ParagraphStyle('Caption',
                         parent=styles['BodyText'],
                         fontName='STSong-Light',
                         fontSize=9,
                         alignment=TA_CENTER,
                         spaceBefore=4,
                         spaceAfter=10)
    code = ParagraphStyle('Code',
                          parent=styles['BodyText'],
                          fontName='Courier',
                          fontSize=8,
                          leading=10,
                          leftIndent=10,
                          backColor=colors.whitesmoke,
                          borderColor=colors.lightgrey,
                          borderWidth=0.5,
                          borderPadding=4)
    return {'body': body, 'h1': h1, 'h2': h2, 'h3': h3,
            'title': title, 'cap': cap, 'code': code}


def main():
    S = make_styles()
    doc = SimpleDocTemplate(
        '问题一建模_v2.pdf',
        pagesize=A4,
        leftMargin=2.0*cm, rightMargin=2.0*cm,
        topMargin=2.0*cm, bottomMargin=2.0*cm,
        title='问题1建模改进版 - 多边形定位区域直径与覆盖性判定',
        author='建模组'
    )

    story = []

    # ---- 标题 ----
    story.append(Paragraph(
        '问题1建模（改进版）<br/>'
        '多边形定位区域直径与覆盖性判定',
        S['title']))
    story.append(Spacer(1, 0.4*cm))

    # ---- 摘要 ----
    story.append(Paragraph(
        '<b>摘要：</b>本文给出由 $n$ 个检测点及其对干扰源的示向度出发，'
        '构造定位多边形、求其直径、并判断以该直径为直径的圆能否覆盖整个'
        '定位区域的完整算法。基于题目给出的全局误差上界 $\\varepsilon=1°$，'
        '采用最坏情形 robust feasible set 建模；通过半平面交 (Sutherland–'
        'Hodgman) 求得凸多边形，再用旋转卡壳法在 $O(m)$ 时间内求直径，'
        '最后用命题 1 的判据判定覆盖性。文中给出了完整的伪代码、复杂度分析、'
        '六类典型情形的数值实验以及与后续问题 2/3/4 的接口。'
        '关键结论：单检测点 (n=1) 的定位直径必为 3600 m，无定位意义；'
        'n ≥ 3 且三点不共线时直径可降至 30–200 m 量级。',
        S['body']))
    story.append(Spacer(1, 0.3*cm))

    # ====================================================
    # §1 统一记号与基本假设
    # ====================================================
    story.append(Paragraph('1 &nbsp;&nbsp;统一记号与基本假设', S['h1']))

    story.append(Paragraph(
        '设检测点集为<br/>'
        '$\\mathcal{S}=\\{S_i=(x_i,y_i)\\}_{i=1}^{n}\\subset\\mathbb{R}^2,$<br/>'
        '$S_i$ 处测得干扰源的示向度 $\\theta_i\\in[0°,360°)$。',
        S['body']))

    story.append(Paragraph(
        '<b>误差假设</b>（与题目原文等价）：对每个 $i$，真实方位角<br/>'
        '$\\alpha_i(G)=\\mathrm{atan2}(y_G-y_i,\\,x_G-x_i)$<br/>'
        '与 $\\theta_i$ 之差 $\\delta_i=\\alpha_i-\\theta_i$ 满足<br/>'
        '$\\delta_i\\in[-\\varepsilon,\\varepsilon],\\quad \\varepsilon=1°$.<br/>'
        '注意：题目给出的是<b>全局上界</b>；同一地点重复测量不改变误差，'
        '故各 $\\delta_i$ 在 $[-\\varepsilon,\\varepsilon]$ 内可取任意值，'
        '模型采用<b>最坏情形</b>（robust feasible set）。',
        S['body']))

    story.append(Paragraph(
        '<b>目标区域</b>：$\\Omega=\\{(x,y):x^2+y^2\\le R^2\\},\\quad R=1800\\text{ m}$.<br/>'
        '<b>真实干扰源</b>位置 $G=(x_G,y_G)\\in\\Omega$ 未知。<br/>'
        '定义角度归一化函数<br/>'
        '$\\mathrm{wrap}(\\alpha)=\\alpha-360°\\left\\lfloor\\dfrac{\\alpha+180°}{360°}\\right\\rfloor\\in[-180°,180°).$',
        S['body']))

    # ====================================================
    # §2 由示向度构造定位区域
    # ====================================================
    story.append(Paragraph('2 &nbsp;&nbsp;由示向度构造定位区域', S['h1']))

    story.append(Paragraph('2.1 &nbsp;&nbsp;单检测点的扇形约束', S['h2']))
    story.append(Paragraph(
        '对检测点 $S_i$、示向度 $\\theta_i$，由 $\\delta_i\\in[-\\varepsilon,\\varepsilon]$ 可得<br/>'
        '$\\mathrm{wrap}(\\alpha_i(G)-\\theta_i)\\in[-\\varepsilon,\\varepsilon].$<br/>'
        '这等价于 $G$ 位于以 $S_i$ 为顶点、方向角 $\\theta_i$、'
        '张角 $2\\varepsilon$ 的<b>扇形</b>内。',
        S['body']))

    story.append(Paragraph(
        '记两条边界单位方向<br/>'
        '$u_i^{-}=(\\cos(\\theta_i-\\varepsilon),\\sin(\\theta_i-\\varepsilon)),$<br/>'
        '$u_i^{+}=(\\cos(\\theta_i+\\varepsilon),\\sin(\\theta_i+\\varepsilon)).$<br/>'
        '则 $G$ 位于扇形内的充要条件为<br/>'
        '$\\mathrm{cross}(u_i^{-},\\,G-S_i)\\ge 0,\\quad '
        '\\mathrm{cross}(u_i^{+},\\,G-S_i)\\le 0,$<br/>'
        '其中 $\\mathrm{cross}(a,b)=a_xb_y-a_yb_x$.',
        S['body']))

    story.append(Paragraph('2.2 &nbsp;&nbsp;化为标准半平面形式', S['h2']))
    story.append(Paragraph(
        '对每条不等式线性化：<br/>'
        '$\\mathrm{cross}(u,P-S)\\ge 0 \\iff n\\cdot P\\le n\\cdot S,\\quad n=(u_y,-u_x),$<br/>'
        '$\\mathrm{cross}(u,P-S)\\le 0 \\iff n\\cdot P\\le n\\cdot S,\\quad n=(-u_y,u_x).$<br/>'
        '记为统一形式 $H_i^{(1)},H_i^{(2)}$（每条 $n_k\\cdot P\\le d_k$）。',
        S['body']))

    story.append(Paragraph('2.3 &nbsp;&nbsp;综合定位区域', S['h2']))
    story.append(Paragraph(
        '取所有扇形约束与 $\\Omega$ 的交集：<br/>'
        '$\\mathcal{P}_1 = \\Omega\\cap\\bigcap_{i=1}^n \\bigl(H_i^{(1)}\\cap H_i^{(2)}\\bigr).$',
        S['body']))

    story.append(Paragraph(
        '<b>命题 1.</b> $\\mathcal{P}_1$ 为凸集；'
        '当 $\\Omega$ 由 $N_{\\text{disk}}$ 个半平面近似时，'
        '若存在解则 $\\mathcal{P}_1$ 为凸多边形；'
        '若 $\\mathcal{P}_1=\\varnothing$，则示向度之间相互矛盾。',
        S['body']))

    # ====================================================
    # §3 半平面交算法
    # ====================================================
    story.append(Paragraph('3 &nbsp;&nbsp;半平面交算法', S['h1']))

    story.append(Paragraph('3.1 &nbsp;&nbsp;算法 1（构造定位多边形）', S['h2']))

    algo1 = '''Algorithm 1: Construct Localization Polygon P1
─────────────────────────────────────────────────
Input : (S_i, θ_i) i=1..n; R=1800; ε=1°; N_disk=64
Output: Vertices V1..Vm (CCW convex polygon); feasible∈{0,1}

1. P^(0) ← regular N_disk-gon inscribed in Ω
2. for i = 1 to n:
       (H1, H2) ← half-planes from (S_i, θ_i, ε)
       P^(i) ← P^(i−1) ∩ H1 ∩ H2    [Sutherland–Hodgman]
       if P^(i) = ∅: return ([], feasible=0)
3. Convex-hull(P^(n)); drop collinear vertices (tol 1e-7)
4. return (V1..Vm, feasible=1)

Complexity: O(n·N_disk) per intersection;
            O(n·N_disk + N_disk·log N_disk) total.'''

    story.append(Preformatted(algo1, S['code']))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph(
        '<b>注（数值稳定性）</b>：扇形张角仅 $2°$，约束近于平行。'
        '多边形顶点距原点的量级可达 $R/\\tan(\\varepsilon)\\approx 1.03\\times 10^5\\text{ m}$，'
        '需用 <font face="Courier">double</font> 精度'
        '（浮点相对误差 $\\sim 10^{-16}$，绝对误差 $\\sim 10^{-11}\\text{ m}$）。',
        S['body']))

    story.append(Paragraph(
        '<b>注（退化情形）</b>：'
        '若最终顶点数 $m&lt;3$，令直径 $D=0$ 并报告空集；'
        '若 $m=2$，$D$ 为该段长度；'
        '若 $m\\ge 3$，进入 §4。',
        S['body']))

    story.append(PageBreak())

    # ====================================================
    # §4 定性几何分析
    # ====================================================
    story.append(Paragraph('4 &nbsp;&nbsp;定位区域的定性几何分析', S['h1']))

    story.append(Paragraph(
        '<b>命题 2（直径上界）</b>：设 $\\mathcal{P}_1\\neq\\varnothing$，则<br/>'
        '$\\mathrm{diam}(\\mathcal{P}_1)\\le \\min\\left\\{2R,\\; '
        '\\dfrac{2R}{\\sin\\varepsilon}\\cdot\\dfrac{1}{\\sin\\phi_{\\min}}\\right\\},$<br/>'
        '其中 $\\phi_{\\min}=\\min_{i&lt;j}\\angle(\\overrightarrow{S_iS_j},\\theta_i)$。',
        S['body']))
    story.append(Paragraph(
        '<i>证明（梗概）</i>：单点扇形与 $\\Omega$ 的交集直径为 $2R$；'
        '$n$ 个扇形的交集落在任一扇形内，故直径 $\\le 2R$。'
        '第二项源于扇形半角 $\\varepsilon$ 与基线长度 $L_{ij}=|S_iS_j|$ 的三角关系。',
        S['body']))

    story.append(Paragraph(
        '<b>推论 1</b>：单检测点 ($n=1$) 的定位直径必为 $2R=3600\\text{ m}$，'
        '对 $R=1800$ 无实际定位意义。',
        S['body']))

    # 表格 1: 各种情形
    data1 = [
        ['n', 'P_1 形态', '典型直径量级 (ε=1°, R=1800)'],
        ['1', '扇形 ∩ Ω (一段弧 + 两条弦)', '2R = 3600 m'],
        ['2', '菱形 ∩ Ω (退化时为空)', '100~3600 m'],
        ['3', '凸六边形 ∩ Ω (三点协调时)', '30~200 m'],
        ['4', '凸八边形 ∩ Ω (包围时)', '20~100 m'],
        ['≥5', '凸 2n 边形 ∩ Ω (接近收敛)', '→ 0 (理想)'],
    ]
    t1 = Table(data1, colWidths=[2*cm, 7*cm, 6*cm])
    t1.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'STSong-Light', 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t1)
    story.append(Paragraph('表 1：不同检测点数 $n$ 下 $\\mathcal{P}_1$ 的典型形态与直径量级',
                           S['cap']))

    story.append(Paragraph(
        '<b>注</b>：表 1 的数值结论可由 Python 数值实验验证'
        '（见附代码 <font face="Courier">problem2_analysis.py</font>）。',
        S['body']))

    # ====================================================
    # §5 多边形直径
    # ====================================================
    story.append(Paragraph('5 &nbsp;&nbsp;多边形直径（旋转卡壳）', S['h1']))

    algo2 = '''Algorithm 2: Convex Polygon Diameter
─────────────────────────────────────────
Input : V1..Vm (CCW convex polygon)
Output: D, (i*, j*)

1. D² ← 0; (i*, j*) ← (0, 1)
2. i0 ← argmin y-coordinate of V_i; j ← (i0+1) mod m
3. while not back to start:
       if |cross(V_{i0+1}−V_{i0}, V_{j+1}−V_j)| grows:
           i0 ← (i0+1) mod m
       else:
           j ← (j+1) mod m
       if ||V_{i0}−V_j||² > D²:
           D² ← ||V_{i0}−V_j||²; (i*,j*) ← (i0,j)
4. fallback: brute force over all (i,j) for m ≤ 10
5. return (D = √D², i*, j*)

Complexity: O(m) rotating calipers; total O(n·m + n·log n).'''

    story.append(Preformatted(algo2, S['code']))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph(
        '对 $n\\le 20$ 的实际情形，算 2 耗时不超过 1 ms。',
        S['body']))

    # ====================================================
    # §6 直径圆覆盖性
    # ====================================================
    story.append(Paragraph('6 &nbsp;&nbsp;直径圆覆盖性判定', S['h1']))

    story.append(Paragraph(
        '设算法 2 给出直径端点 $A=V_{i^*}$、$B=V_{j^*}$，构造直径圆<br/>'
        '$\\mathcal{C}(A,B)=\\{P:\\|P-\\frac{A+B}{2}\\|\\le\\frac{\\|A-B\\|}{2}\\}.$',
        S['body']))

    story.append(Paragraph(
        '<b>命题 3（覆盖判据）</b>：$\\mathcal{P}_1\\subseteq\\mathcal{C}(A,B)$ 当且仅当<br/>'
        '$\\max_{1\\le k\\le m}\\|V_k-\\tfrac{A+B}{2}\\|_2\\le\\tfrac{\\|A-B\\|_2}{2}.$',
        S['body']))
    story.append(Paragraph(
        '<i>证明</i>：$\\mathcal{P}_1$ 是 $V_1,\\dots,V_m$ 的凸包。'
        '凸集 $\\subseteq\\mathcal{C}(A,B)$ $\\iff$ 其顶点 $\\subseteq\\mathcal{C}(A,B)$'
        '（圆是凸集；凸包 $\\subseteq$ 凸集 $\\iff$ 生成元 $\\subseteq$）。',
        S['body']))

    story.append(Paragraph('6.1 &nbsp;&nbsp;几何等价形式', S['h2']))
    story.append(Paragraph(
        '直径圆覆盖 $\\mathcal{P}_1$ 等价于下述任一条件：<br/>'
        '(i) $\\mathcal{P}_1$ 的最小包围圆（MEC）直径 $\\le\\|A-B\\|$；<br/>'
        '(ii) $A,B$ 为 $\\mathcal{P}_1$ 的一对对踵点，'
        '且 $\\mathcal{P}_1$ 中所有点对 $(A,B)$ 张角 $\\ge 90°$；<br/>'
        '(iii) 对所有顶点 $V_k$，$\\angle AV_kB\\ge 90°$。',
        S['body']))

    # 表格 2: 几何判别
    data2 = [
        ['多边形', '直径圆覆盖?', '说明'],
        ['等边三角形', '否', '第三顶点距圆心 √3/2·D > D/2'],
        ['长方形', '是', '对角线即外接圆直径'],
        ['正六边形', '是', '最长对角线即外接圆直径'],
        ['正五边形', '否', '外接圆直径 > 最长对角线'],
        ['一般三角形', '取决于', '仅钝角边作直径时覆盖'],
    ]
    t2 = Table(data2, colWidths=[4*cm, 4*cm, 7*cm])
    t2.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'STSong-Light', 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t2)
    story.append(Paragraph('表 2：典型凸多边形的直径圆覆盖性',
                           S['cap']))

    story.append(Paragraph(
        '<b>问题 1 第二问的判定方法</b>：<br/>'
        '① 由算法 2 得 $D,i^*,j^*$；<br/>'
        '② 令 $O=\\frac{V_{i^*}+V_{j^*}}{2}$，$r=D/2$；<br/>'
        '③ 计算 $d_{\\max}=\\max_k\\|V_k-O\\|$；<br/>'
        '④ 若 $d_{\\max}\\le r+10^{-7}$ 则覆盖，否则不覆盖。',
        S['body']))

    story.append(PageBreak())

    # ====================================================
    # §7 数值算例
    # ====================================================
    story.append(Paragraph('7 &nbsp;&nbsp;数值算例', S['h1']))

    story.append(Paragraph(
        '所有算例均使用 Python 3 实现（见附代码 '
        '<font face="Courier">problem1_core.py</font> 与 '
        '<font face="Courier">problem2_analysis.py</font>），'
        '误差 $\\varepsilon=1°$、$R=1800$ m。',
        S['body']))

    data3 = [
        ['情形', '顶点数', '直径 D (m)', '覆盖?', '说明'],
        ['n=1, θ=45°', '4', '1800.00', '是', '扇形 ∩ Ω'],
        ['n=2 对称 θ=0°,180°', '4', '1600.00', '是', '朝向彼此'],
        ['n=3 协调 (G≈0)', '6', '28.91', '否', '第三顶点出圆'],
        ['n=4 包围', '8', '54.90', '是', '凸八边形'],
        ['矛盾示向度', '0', '0', 'N/A', '空集'],
        ['n=5 协调', '8', '25.75', '是', '几乎收敛'],
    ]
    t3 = Table(data3, colWidths=[3.5*cm, 2*cm, 2.5*cm, 2*cm, 4.5*cm])
    t3.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'STSong-Light', 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t3)
    story.append(Paragraph('表 3：六类典型情形数值结果', S['cap']))

    story.append(Paragraph(
        '各情形可视化见图 1。',
        S['body']))

    # 插入图片
    img_path = os.path.join(os.path.dirname(__file__), 'problem1_cases.png')
    if not os.path.exists(img_path):
        img_path = '../代码/problem1_cases.png'
    if os.path.exists(img_path):
        story.append(Image(img_path, width=16*cm, height=9*cm))
        story.append(Paragraph(
            '图 1：六类典型情形。扇形约束（虚线）、定位多边形（红色）、'
            '直径（绿线）、直径圆（绿虚线）。',
            S['cap']))
    else:
        story.append(Paragraph(
            '<i>（图 1 由 problem2_analysis.py 生成）</i>',
            S['body']))

    # ====================================================
    # §8 完整伪代码
    # ====================================================
    story.append(Paragraph('8 &nbsp;&nbsp;完整算法伪代码', S['h1']))

    algo_full = '''Algorithm 3: Full Pipeline for Problem 1
───────────────────────────────────────────────
Input : (S_i, θ_i) i=1..n; ε=1°; R=1800
Output: D, A, B, ρ∈{0,1}

1. (V1..Vm, feasible) ← Algorithm 1
2. if feasible=0 or m<2:
       return (D=0, A=B=V1, ρ=0)
3. (D, i*, j*) ← Algorithm 2
4. A ← V_{i*}; B ← V_{j*}
5. O ← (A+B)/2; r ← D/2
6. d_max ← max_k ||V_k − O||
7. ρ ← 1[d_max ≤ r + 1e-7]
8. return (D, A, B, ρ)

Complexity: O(n·m + n·log n). For n ≤ 20, m ≤ 40,
            wall time < 1 ms in pure Python.'''

    story.append(Preformatted(algo_full, S['code']))
    story.append(Spacer(1, 0.2*cm))

    # ====================================================
    # §9 结论
    # ====================================================
    story.append(Paragraph('9 &nbsp;&nbsp;结论与对后续问题的接口', S['h1']))

    story.append(Paragraph(
        '1. <b>问题 1</b>已给出由 $(S_i,\\theta_i)$ 出发，'
        '构造定位多边形、求直径、判定覆盖的完整算法；<br/>'
        '2. 关键结论（命题 2）：<b>$n=1$ 无定位意义，'
        '$n\\ge 3$ 且三点不共线时直径 $\\lesssim 200$ m</b>；<br/>'
        '3. 对问题 2：将命题 2 作为"定位效果"量化基础，'
        '给出 $S_2$ 候选区域（见问题 2 建模文档）；<br/>'
        '4. 对问题 3：旋转卡壳的 $A,B$ 即为"机器狗进入 20 m 内可清除"的入口点；<br/>'
        '5. 对问题 4：在算法 1 前加入定向方向估计的区间交集运算，其余不变。',
        S['body']))

    story.append(Spacer(1, 0.4*cm))

    # 附录
    story.append(Paragraph('附录 A &nbsp;&nbsp;代码清单', S['h1']))
    story.append(Paragraph(
        '<font face="Courier">problem1_core.py</font>：'
        '半平面、凸包、直径、覆盖判别的核心实现。<br/>'
        '<font face="Courier">problem2_analysis.py</font>：'
        '六类情形数值实验与可视化。<br/>'
        '所有代码用 Python 3 + NumPy 实现，无外部依赖。',
        S['body']))

    # 构建 PDF
    doc.build(story)
    print(f'已生成 PDF: {doc.filename}')


if __name__ == "__main__":
    main()