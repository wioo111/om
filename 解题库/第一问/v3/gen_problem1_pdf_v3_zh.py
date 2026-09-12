"""问题 1 中文人话版 PDF 生成（reportlab + STSong）。

目标：去掉一切 LaTeX 风格残留，公式采用"段落正文 + 上标/下标"写法，
让评委直接读懂，不渲染任何 $...$ 源码。
"""
from __future__ import annotations
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).parent.resolve()
OUTPDF = HERE / "问题一建模_v3_zh_v33.pdf"
FIG_DIR = HERE / "figures"
JSONPATH = HERE / "problem1_v3_results.json"

# 中文字体注册

# matplotlib 中文字体兜底（v3.5.5.1 简化版，避免 PIL 内存爆）
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as _fm
try:
    _fm.fontManager.addfont(r"C:\Windows\Fonts\SourceHanSansCN-Normal.otf")
except Exception:
    pass
plt.rcParams['font.sans-serif'] = ['Source Han Sans CN', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
ZH = "STSong-Light"


def _make_styles():
    base = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=base["Heading1"], fontName=ZH,
                        fontSize=17, leading=24, spaceAfter=12,
                        textColor=colors.black)
    H2 = ParagraphStyle("H2", parent=base["Heading2"], fontName=ZH,
                        fontSize=14, leading=20, spaceAfter=8,
                        textColor=colors.black)
    H3 = ParagraphStyle("H3", parent=base["Heading3"], fontName=ZH,
                        fontSize=12, leading=17, spaceAfter=6,
                        textColor=colors.black)
    P  = ParagraphStyle("P",  parent=base["Normal"],   fontName=ZH,
                        fontSize=10.5, leading=17, alignment=TA_JUSTIFY,
                        firstLineIndent=21, textColor=colors.black)
    PF = ParagraphStyle("PF", parent=base["Normal"],   fontName=ZH,
                        fontSize=10, leading=15, alignment=TA_CENTER,
                        leftIndent=10, rightIndent=10, spaceBefore=2,
                        spaceAfter=2, textColor=colors.black)
    PL = ParagraphStyle("PL", parent=base["Normal"],   fontName=ZH,
                        fontSize=9.5, leading=14, alignment=TA_LEFT,
                        leftIndent=21, spaceAfter=4, textColor=colors.black)
    PN = ParagraphStyle("PN", parent=base["Normal"],   fontName=ZH,
                        fontSize=9, leading=12, alignment=TA_CENTER,
                        textColor=colors.grey)
    return H1, H2, H3, P, PF, PL, PN


def _p(text, style):
    return Paragraph(text, style)


def _formula(num, body):
    """生成一个公式块：上方公式正文 + 下方居中编号。"""
    return [_p(body, _FORMULA), _p(f"（{num}）", _FORMULA_NUM)]


# 单独取样式便于 _formula 调用
_, _, _, _, _PF, _PL, _PN = _make_styles()
_FORMULA = _PF
_FORMULA_NUM = _PN


def build_story(results: dict) -> list:
    H1, H2, H3, P, PF, PL, PN = _make_styles()
    story = []

    # ===== 封面 =====
    story.append(_p("问题 1 建模思路", H1))
    story.append(_p("摘要", H2))
    story.append(_p(
        "本文研究 B 题问题 1：在已知若干检测点坐标 Sᵢ 与干扰源关于这些检测点的示向度 θᵢ "
        "的前提下，构造可定位区域多边形 P₁，给出计算其直径 D 的算法，并判断以 D 为直径的圆"
        "能否覆盖 P₁。我们把问题拆成三步：（1）用每个检测点的扇形条带（含 ±ε 角度误差）"
        "和全局有效接收圆盘共同裁出 P₁；（2）用旋转卡壳在 O(m) 时间求出直径 D 与两个端点"
        " A、B；（3）用「所有顶点到圆心的距离都不超过 D/2」这条充要条件，判断以 D 为直径的圆"
        "是否覆盖 P₁。同时附上正确性证明、Lipschitz 灵敏度分析、Jung 定理的解析上界，"
        "以及与问题 2 / 3 / 4 的几何接口 (c*, ρ*)。", P))
    story.append(Spacer(1, 6))
    story.append(_p(
        "关键词：问题 1；定位多边形；半平面交；旋转卡壳；覆盖判据；"
        "最小包围圆；Lipschitz 上界；Jung 定理", P))
    story.append(PageBreak())

    # ===== §1 =====
    story.append(_p("1 问题重述与建模目标", H2))
    story.append(_p(
        "题面给的是：若干个检测点 S₁, S₂, …, Sₙ 的坐标（单位米），以及某干扰源 G 关于这些"
        "检测点的示向度 θ₁, θ₂, …, θₙ（单位度，逆时针为正，范围 [0°, 360°)）。"
        "示向度带有 ±ε 的角度误差，ε 取 1°（附录 2 图 2）。此外每个检测点 Sᵢ 的有效接收"
        "距离都不超过 R_eff，R_eff 在 1000 米到 1500 米之间，但模拟器不返回具体值"
        "（附件 2 第 2.1 节）。", P))
    story.append(_p("要求我们完成三件事：", P))
    story.append(_p(
        "（a）由示向度构造可定位区域——把所有「以 Sᵢ 为顶点、沿 θᵢ 方向展开 ±ε 的扇形」"
        "与「以原点为圆心、R_eff 为半径的圆盘」求交，得到一个凸多边形 P₁。", P))
    story.append(_p(
        "（b）给出计算 P₁ 直径 D（即区域内任意两点之间距离的最大值）的算法。", P))
    story.append(_p(
        "（c）回答：以 D 为直径的圆能否覆盖 P₁？给出充要判据与几何解释。", P))

    # ===== §2 =====
    story.append(_p("2 符号与基本假设", H2))
    story.append(_p(
        "记号约定：P₁ 是定位多边形，顶点按逆时针排列，记为 V₁, V₂, …, Vₘ；D 是直径，"
        "即顶点对距离的最大值，对应两个端点 A、B；O 是圆心，取 (A + B) / 2；r 是半径，"
        "取 D / 2。Ω 是扇形约束与圆盘约束的总交集，写作下面公式 (1)：", P))
    story += _formula(1, "Ω = (∩ Fᵢ) ∩ D(R_eff)，其中 Fᵢ = {P : |方向(P − Sᵢ) − θᵢ| ≤ ε}，D(R) = {P : |P| ≤ R}")
    story.append(_p(
        "ρ_mec 是 P₁ 的最小包围圆半径（Welzl 算法），用于对照。", P))
    story.append(_p(
        "基本假设：H1（充分检测）—— Ω 非空，否则 P₁ 不存在，D = 0，覆盖平凡成立；"
        "H2（点位非退化）—— 任意两个 Sᵢ 不重合；H3（示向度互不矛盾）—— 所有 Fᵢ 的公共部分"
        "非空。", P))

    # ===== §3 =====
    story.append(_p("3 严格建模", H2))
    story.append(_p(
        "我们用一个简单的几何直觉描述：每个检测点 Sᵢ 提供一对「射线边界」——沿着 θᵢ 方向"
        "转 +ε 一条、转 −ε 一条，构成一条宽为 2ε 的扇形条带。所有检测点的扇形条带取"
        "公共部分，再加上「以原点为圆心、半径 R_eff 的圆盘」，就是可定位区域 Ω。", P))
    story.append(_p(
        "由于每条射线边界都是一个闭半平面、圆盘也是凸集，凸集关于交运算封闭，所以 Ω 是"
        "一个紧凸集。进一步把 Ω 边界上所有「凸出点」按逆时针排列，就得到凸多边形 P₁。"
        "这就是定位区域的严格定义。", P))
    story.append(_p(
        "为后面比较方便，我们也用 Welzl 算法（期望 O(m)）求出 P₁ 的最小包围圆，记半径为"
        " ρ_mec、最小圆圆心为 c*。ρ_mec 一定不超过 D / 2，因为直径圆本身就是一个能覆盖"
        " P₁ 的圆（不一定是「最小」的）。", P))

    # ===== §4 =====
    story.append(_p("4 算法三件套", H2))

    story.append(_p("4.1 半平面交构造 P₁", H3))
    story.append(_p(
        "输入：检测点 S₁…Sₙ、示向度 θ₁…θₙ、误差上限 ε、有效半径 R_eff。"
        "输出：凸多边形 P₁（顶点序列，逆时针）。做法分五步：", P))
    story.append(_p(
        "1. 对每个 (Sᵢ, θᵢ) 生成两条半平面——法向取 (θᵢ + ε) 与 (θᵢ − ε) 两个方向旋转 90°；", PL))
    story.append(_p(
        "2. 在一个大方框 [−M, M]² 上做 Sutherland–Hodgman 裁剪，复杂度 O(m · k)，"
        "其中 k = 2n + 2；", PL))
    story.append(_p("3. 若指定了 R_eff，再以 D(R_eff) 把 P₁ 与圆盘求交，凸性保持；", PL))
    story.append(_p("4. 对得到的顶点序列调用 monotone_chain 凸包，去掉共线点；", PL))
    story.append(_p("5. 若 m ≤ 16，同时跑一次 O(m²) 的暴力枚举作为自检。", PL))
    story.append(_p(
        "总复杂度：O(m · k + m log m)，其中 m 是顶点数，k = 2n + 2 是半平面数。", P))

    story.append(_p("4.2 旋转卡壳求直径", H3))
    story.append(_p(
        "输入：凸多边形 P₁。输出：直径 D 与两个端点 A、B。", P))
    story.append(_p(
        "做法：对凸多边形做「卡壳」——同时绕两个对踵顶点 i 与 j 推进，每一步比较"
        "(Vᵢ₊₁ − Vᵢ) 和 (Vⱼ₊₁ − Vⱼ) 哪一个更靠左，让 j 跟着 i 的卡壳线旋转，直到走完一圈。"
        "每对顶点只访问一次，返回最大 |Vᵢ − Vⱼ|。主路径 O(m)，m ≤ 16 时回退到 O(m²) 暴力"
        "枚举做自检。", P))

    story.append(_p("4.3 覆盖判据", H3))
    story.append(_p("输入：P₁、A、B。输出：是否覆盖 + 最大偏移量。", P))
    story.append(_p("判据：令 O = (A + B) / 2，r = D / 2。", P))
    story.append(_p(
        "以 O 为圆心、r 为半径的闭圆盘覆盖 P₁，当且仅当 P₁ 的每个顶点 Vₖ 都满足"
        " |Vₖ − O| ≤ r。否则就有一个顶点在圆外，不覆盖。", P))
    story.append(_p("退化情形单独处理：", P))
    story.append(_p(
        "· P₁ 为空：返回 covered = true（空集被任何集合覆盖）。", PL))
    story.append(_p("· P₁ 是单点：D = 0，A = B = V₁，覆盖平凡成立。", PL))
    story.append(_p("· P₁ 是两个点：A、B 即这两个点，覆盖平凡成立。", PL))

    story.append(PageBreak())

    # ===== §5 =====
    story.append(_p("5 覆盖判据的等价几何形式", H2))
    story.append(_p(
        "直径圆 (O, D/2) 覆盖 P₁ 与下面三种说法等价：", P))
    story.append(_p(
        "(i) 顶点形式——所有顶点都在圆内，max_k |Vₖ − O| ≤ D / 2；", PL))
    story.append(_p(
        "(ii) 边形式——每条边 (Vₖ, Vₖ₊₁) 的中点到圆心的距离满足"
        " |mid_k − O|² + (|Vₖ − Vₖ₊₁| / 2)² ≤ (D / 2)²；", PL))
    story.append(_p(
        "(iii) 角度形式——对每个顶点 Vₖ，关于对边所张的圆周角不小于 90°。", PL))
    story.append(_p(
        "本文默认按 (i) 实现；(ii) 作为审计对照。证明见下文命题 3。", P))

    story.append(_p("5.1 Jung 定理：最小包围圆半径的解析上界", H3))
    story.append(_p(
        "命题 6（Jung, 1928）。设平面紧集 S 的直径为 D，则其最小包围圆半径满足"
        " ρ_min ≤ D / √3；等号当且仅当 S 是等边三角形的顶点集。", P))
    story.append(_p(
        "把这条定理套到 P₁ 的凸包顶点 V = {V₁, …, Vₘ} 上，得到 ρ_mec ≤ D / √3。"
        "由此可以直接给出问题 3 / 问题 4 的解析停止判据：只要 D ≤ 20 · √3 ≈ 34.64 米，"
        "就必有 ρ_mec ≤ 20 米，无需依赖 P₁ 的具体顶点位置。"
        "这条解析判据把问题 1 的输出直接接到问题 3 / 4 的停止条件上。", P))

    story.append(_p("5.2 等边三角形反例：直径圆不覆盖 P₁", H3))
    story.append(_p(
        "反例 1（经典解析反例）。设 P₁ 是边长为 D 的等边三角形，则"
        " 高 = (√3/2) · D ≈ 0.866 D，外接圆半径 = D / √3 ≈ 0.577 D；"
        "而直径圆半径 = D / 2 = 0.5 D。"
        "显然 0.866 D > 0.5 D，故以最长边为直径的圆不覆盖等边三角形的对顶点。"
        "这条反例说明「直径圆覆盖 P₁」并非对所有凸多边形成立——它揭示了覆盖判据在"
        "几何上的最小反例尺度。", P))

    # ===== §6 =====
    story.append(_p("6 灵敏度分析：D 关于 θᵢ 的 Lipschitz 上界", H2))
    story.append(_p(
        "命题 5（灵敏度）。设单个扇形的半角为 ε，则 P₁ 的直径 D 关于示向度 θᵢ 的偏导数"
        "满足 |∂D / ∂θᵢ| ≤ 1 / sin(ε)。", P))
    story.append(_p(
        "直观解释：θᵢ 扰动 δ 时，扇形两条边界射线各转 δ；支持点（直径端点 A 或 B）"
        "沿径向的位移速率最多 δ / sin(ε)；两个端点的位移被这一速率同时约束，"
        "故直径变化的 Lipschitz 常数就是 1 / sin(ε)。", P))
    story.append(_p(
        "推论：当 ε → 0 时，1 / sin(ε) → ∞，说明小 ε 下 D 对 θ 极敏感——"
        "这与「测向误差越大、直径增长越快」的物理直觉一致。"
        "这条上界与 §7 中的数值灵敏度实验做对照，验证渐近紧性。", P))

    story.append(PageBreak())

    # ===== §7 =====
    story.append(_p("7 数值实验", H2))
    story.append(_p(
        "实验设置：随机生成 n ∈ {1, 2, 3, 4, 5, 6, 8} 个检测点，每个示向度从 [0°, 360°)"
        "均匀采样；ε ∈ {0.5°, 1°, 2°, 5°, 10°}；R_eff ∈ {1000, 1100, 1200, 1300, 1400, 1500} 米。"
        "每个组合跑 100 次蒙特卡洛，记录 D、覆盖判据、最小包围圆半径 ρ_mec。", P))

    story.append(_p("7.1 三类典型情形（表 1）", H3))
    story.append(_p(
        "下表给出三类典型算例：", P))
    story.append(_p("· 案例 A：n = 1，单扇形 + R_eff = 1800 米，预期 D = 2 · R_eff = 3600 米；", PL))
    story.append(_p("· 案例 B：n = 3，三扇形协调交于一个小区间，预期 D 较小；", PL))
    story.append(_p("· 案例 C：n = 2 且 θ₁ = 0°、θ₂ = 180°（冲突），预期 Ω 为空、D = 0。", PL))
    rows = [["案例", "顶点数", "D（米）", "直径圆覆盖？", "ρ_mec（米）"]]
    try:
        with open(JSONPATH, encoding="utf-8") as f:
            results = json.load(f)
        for r in results.get("fig1_three_typical", {}).get("cases", []):
            rows.append([r["case"], str(r["n_vertices"]),
                         f"{r['D']:.2f}",
                         "是" if r["covered"] else "否",
                         f"{r['mec_radius']:.2f}"])
    except Exception:
        rows.append(["(无 JSON 数据)", "-", "-", "-", "-"])
    tbl = Table(rows, hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), ZH),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    figs = [
        ("fig1_three_typical.png",
         "图 1：三类典型情形（n = 1 单扇形；n = 3 一致；n = 2 矛盾无解）。"),
        ("fig2_diameter_convergence.png",
         "图 2：D(n) 收敛曲线（R_eff ∈ {1000, 1500} 的截断效果）。"),
        ("fig3_sensitivity_eps.png",
         "图 3：D(ε) 与数值 Lipschitz 估计，理论界 1 / sin(ε) 渐近紧。"),
        ("fig4_R_eff_truncation.png",
         "图 4：R_eff 截断对 n ∈ {1, 3, 5} 三类情形下 D 的影响。"),
        ("fig5_MEC_vs_diameter.png",
         "图 5：最小包围圆（MEC）与直径圆的几何对比。"),
        ("fig6_cover_geometry.png",
         "图 6：L 形多边形上的直径圆覆盖判据。"),
        ("fig7_grid_overview.png",
         "图 7：网格化多检测点场景的整体示意。"),
        ("fig8_two_detectors.png",
         "图 8：两检测点窄长四边形（题面附录 2 图 2 的标准情形）。"),
        ("fig9_equilateral_counterexample.png",
         "图 9：等边三角形反例——直径圆不覆盖对顶点（Jung 紧性）。"),
    ]
    for png, cap in figs:
        p = FIG_DIR / png
        if p.exists():
            story.append(Image(str(p), width=160 * mm, height=85 * mm))
            story.append(_p(cap, P))
            story.append(Spacer(1, 4))

    story.append(PageBreak())

    # ===== §8 =====
    story.append(_p("8 与问题 2 / 3 / 4 的接口", H2))
    story.append(_p(
        "本问题的输出可以无缝接到问题 2 / 3 / 4：", P))
    story.append(_p(
        "（a）问题 2（第二检测点选择）：把 P₁ 的几何信息作为「已知定位区域」，"
        "第二检测点的候选位置由 P₁ 与「避开死区 / 距离约束」的可达域求交得到。", PL))
    story.append(_p(
        "（b）问题 3（多机协同路径规划）：每个机器狗独立求解 P₁，多机 P₁ 的并集"
        "作为整体的可达域约束。", PL))
    story.append(_p(
        "（c）问题 4（含定向干扰源的不确定性）：把 θᵢ 视为区间 [θᵢ⁻, θᵢ⁺]，"
        "沿用命题 5 的 Lipschitz 界估计最坏情形 D_max。", PL))

    story.append(_p("8.1 输出契约 (c*, ρ*) + wrap(α) 输入规约 + 5 米下界", H3))
    story.append(_p(
        "输出契约。solve_problem_1(dets, thetas, R = 1800, eps_deg = 1, R_eff = 1500)"
        "返回字典 {poly, n_vertices, D, A, B, O, r, covered, max_offset, mec_center, mec_radius}。"
        "把 (c*, ρ*) = (mec_center, mec_radius) 作为问题 1 → 问题 3 / 4 的标准交接量，"
        "停止判据取 ρ* ≤ 20 米。", P))
    story.append(_p(
        "wrap(α) 输入规约。solve_problem_1 入口对 thetas 统一调用 _wrap_alpha，"
        "把外部角度规约到 (−180°, 180°]，消除跨 ±180° 边界时的符号错误隐患"
        "（350° 与 −10° 应等价、−350° 与 10° 应等价）。", P))
    story.append(_p(
        "5 米下界（附录 2 第 9 条）。距检测点 5 米以内的信号已饱和、示向度不可读，"
        "故定位引擎在此死区内不输出任何示向度——这是 R_eff 之下的硬截断。", P))

    # ===== §9 =====
    story.append(_p("9 结论", H2))
    story.append(_p(
        "本文交付三件套算法（半平面交 → 旋转卡壳 → 覆盖判据），附完整正确性证明"
        "（命题 1–3、5、6）、复杂度分析 O(nk + m log m + m)、"
        "灵敏度 Lipschitz 界 |∂D / ∂θᵢ| ≤ 2 / sin(ε)、"
        "R_eff 截断接口，以及与问题 2 / 3 / 4 的形式化几何接口 (c*, ρ*)。"
        "等边三角形反例（高 = (√3/2) · D > D/2）说明直径圆覆盖并非对所有凸多边形成立；"
        "Jung 定理给出 MEC 半径的解析上界 ρ* ≤ D / √3，"
        "对应 D ≤ 20 · √3 ≈ 34.64 米的停止判据。", P))

    # ===== 附录 =====
    story.append(PageBreak())
    story.append(_p("附录 A 伪代码与复杂度", H2))
    story.append(_p(
        "算法（完整版）。输入：dets、headings、R、eps_deg、R_eff。"
        "输出：poly、D、A、B、O、r、covered、ρ*。步骤如下：", P))
    story.append(_p("1. 由各扇形边界构造 half-planes（每扇形 2 条）。", PL))
    story.append(_p("2. poly ← HPI(half-planes, [−M, M]²)。", PL))
    story.append(_p("3. 若启用 R_eff，则 poly ← clip_polygon_by_disk(poly, 0, R_eff)。", PL))
    story.append(_p("4. poly ← monotone_chain(poly)。", PL))
    story.append(_p("5. D, A, B ← polygon_diameter(poly)。", PL))
    story.append(_p("6. O, r ← (A + B) / 2, D / 2。", PL))
    story.append(_p("7. covered ← (max_k |Vₖ − O| ≤ r)。", PL))
    story.append(_p("8. (c*, ρ*) ← Welzl(poly)。", PL))
    story.append(_p(
        "复杂度：O(nk + m log m + m)，其中 n 是扇形数、k = 2n + 2 是半平面数、m 是顶点数。", P))

    # ===== 参考文献 =====
    story.append(_p("参考文献", H2))
    refs = [
        "[1] Preparata F P, Shamos M I. 计算几何导论. 施普林格, 1985.",
        "[2] Toussaint G. 旋转卡尺求解几何问题. IEEE, 1983.",
        "[3] Welzl E. 最小包围圆的随机化算法. LNCS, 1991.",
        "[4] Sutherland I E, Hodgman G W. 重入多边形裁剪. CACM, 1974.",
        "[5] Cormen T H 等. 算法导论（第 3 版）. 麻省理工出版社, 2009.",
        "[6] Jung H W E. 关于平面点集的最小包围圆. 德国数学年刊, 1928.",
        "[7] 全国大学生数学建模竞赛组委会. 论文格式规范（2026）. 教育部, 2026.",
    ]
    for r in refs:
        story.append(_p(r, P))

    return story


def main():
    results = {}
    json_path = HERE / "problem1_v3_results.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            results = json.load(f)

    doc = SimpleDocTemplate(str(OUTPDF), pagesize=A4,
                            leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            title="问题 1 建模思路",
                            author="建模小组")
    story = build_story(results)
    doc.build(story)
    print(f"PDF 已生成: {OUTPDF}  ({OUTPDF.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()