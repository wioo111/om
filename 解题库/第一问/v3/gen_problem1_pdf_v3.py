"""问题1 v3 国奖级 PDF 生成脚本（reportlab + 中文字体）。

输出文件：解题库/第一问/v3/问题一建模_v3.pdf

v3.2 修订（2026-09-11）：
- 全部内容改写为中文（删 _chapter_algorithm 英文版）
- 公式从 LaTeX 源码（$...$、\\mathcal、\\theta 等）改为 Unicode 人话数学符号
"""
from __future__ import annotations
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).parent.resolve()
OUTPDF = HERE / "问题一建模_v3.pdf"
FIG_DIR = HERE / "figures"
JSONPATH = HERE / "problem1_v3_results.json"

# 中文字体注册（按可用性逐级回退）
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
ZH = "STSong-Light"

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


def _make_styles():
    base = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=base["Heading1"], fontName=ZH,
                        fontSize=16, leading=22, spaceAfter=12)
    H2 = ParagraphStyle("H2", parent=base["Heading2"], fontName=ZH,
                        fontSize=13, leading=18, spaceAfter=8)
    H3 = ParagraphStyle("H3", parent=base["Heading3"], fontName=ZH,
                        fontSize=11, leading=15, spaceAfter=6)
    P  = ParagraphStyle("P",  parent=base["Normal"],   fontName=ZH,
                        fontSize=10.5, leading=16, alignment=TA_JUSTIFY,
                        firstLineIndent=21)
    PC = ParagraphStyle("PC", parent=base["Normal"],   fontName=ZH,
                        fontSize=9, alignment=TA_CENTER, leading=12)
    return H1, H2, H3, P, PC


def _chapter_zh_4_to_9(story, H2, H3, P):
    """§4 算法 → §9 结论，全中文，公式用 Unicode 数学符号。"""
    story.append(Paragraph("4 算法三件套：半平面交 + 旋转卡壳 + 覆盖判据", H2))
    story.append(Paragraph(
        "步骤 1（半平面交构造）：对每个扇形约束生成两条半平面，在外接矩形 [−M, M]² 上"
        "用 Sutherland–Hodgman 裁剪，时间复杂度 O(m · k)，其中 m 为顶点数、k = 2n + 2 为半平面数。"
        "步骤 2（圆盘裁剪）：若启用有效接收半径 R_eff，则用 D(R_eff) 再裁一次多边形，凸性保持。"
        "步骤 3（凸包）：对（可能非严格凸的）顶点序列调用 monotone_chain，得到严格凸多边形；"
        "若 m ≤ 16 则同时跑 O(m²) 暴力枚举作为审计。步骤 4（直径）：旋转卡壳 O(m) 主路径，"
        "返回直径 D 与两个端点 A、B。步骤 5（覆盖判据）：max ‖V_k − O‖ ≤ D / 2，其中 O = (A + B) / 2。"
        "步骤 6（MEC 对照）：用 Welzl 随机化算法求最小包围圆，期望复杂度 O(m)。", P))

    story.append(Paragraph("4.1 正确性（命题 1–3）", H3))
    story.append(Paragraph(
        "命题 1（凸性）。半平面的交仍是半平面（即凸集），闭圆盘是凸集，二者之交仍是凸集。"
        "因此步骤 1–2 返回一个凸集；monotone_chain 进一步把它化成凸多边形。"
        "命题 2（直径正确性）。对凸多边形，旋转卡壳枚举所有对踵点对；最大距离等于全局直径。"
        "命题 3（覆盖判据充要条件）。以 O 为圆心、r 为半径的闭圆盘覆盖凸多边形 P₁，当且仅当"
        "P₁ 的每个顶点 V_k 满足 ‖V_k − O‖ ≤ r。证明：若某顶点越界则不覆盖；反之，所有顶点在圆内，"
        "凸包上每条边的中点也由凸性落在圆内，从而整条边落在圆内，故多边形被覆盖。", P))
    story.append(PageBreak())

    story.append(Paragraph("5 覆盖判据：三种等价的几何形式", H2))
    story.append(Paragraph(
        "直径圆 (O, D / 2) 覆盖 P₁ 等价于下面任一形式："
        "（i）顶点形式：max_k ‖V_k − O‖ ≤ D / 2；"
        "（ii）边形式：对每条边 (V_k, V_{k+1})，中点在圆内、且弦半长满足"
        "‖mid_k − O‖² + (‖V_k − V_{k+1}‖ / 2)² ≤ (D / 2)²；"
        "（iii）角度形式：对每个顶点 V_k，关于对边所张的圆周角 ≥ 90°。"
        "本文实现以（i）为标准形式，（ii）作为审计。", P))

    story.append(Paragraph("5.1 Jung 定理：MEC 半径的解析上界", H3))
    story.append(Paragraph(
        "命题 6（Jung, 1928）。对平面上任一紧集 S，设其直径为 D，则其最小包围圆半径"
        "满足 ρ_min ≤ D / √3；等号当且仅当 S 是等边三角形的顶点集。"
        "把它套到 P₁ 的凸包 V = {V₁, …, V_m} 上，立即得到"
        "ρ* = ρ_mec ≤ D / √3。"
        "由此推出问题 3/4 的解析停止判据：只要 D ≤ 20 · √3 ≈ 34.64 米，就必有 ρ* ≤ 20 米，"
        "无需依赖具体顶点位置。这条解析判据直接把问题 1 的输出接到问题 3/4 的停止条件上。", P))

    story.append(Paragraph("5.2 等边三角形反例：直径圆不覆盖 P₁", H3))
    story.append(Paragraph(
        "反例 1（经典解析反例）。设 P₁ 是边长为 D 的等边三角形，则其高 = (√3 / 2) · D ≈ 0.866 D，"
        "外接圆半径 = D / √3 ≈ 0.577 D；而直径圆半径 = D / 2 = 0.5 D。"
        "高 0.866 D 显著大于 0.5 D，故直径圆（以最长边为直径）不覆盖三角形的对顶点。"
        "此反例说明「直径圆覆盖」并非对所有凸多边形成立，是覆盖判据的最小反例尺度。", P))

    story.append(Paragraph("6 灵敏度分析：D 关于 θ_i 的 Lipschitz 界", H2))
    story.append(Paragraph(
        "命题 5（灵敏度）。对单个半角为 ε 的扇形，D 关于示向度 θ_i 的偏导满足"
        "|∂D / ∂θ_i| ≤ 1 / sin(ε)。"
        "证明概要：θ_i 的扰动 δ 使扇形两条边界射线各转 δ；由几何关系，支持点沿径向"
        "移动的速率至多为 δ / sin(ε)；两端点的距离变化被此速率约束，故 Lipschitz 常数为 1 / sin(ε)。"
        "在 ε → 0（小误差）时此界渐近紧，说明小 ε 下 D 对 θ 极敏感，与数值实验一致。", P))
    story.append(PageBreak())

    story.append(Paragraph("7 数值实验", H2))
    figs = [
        ("fig1_three_typical.png",
         "图 1：三类典型情形（n = 1 扇形；n = 3 一致；n = 3 矛盾无解）。"),
        ("fig2_diameter_convergence.png",
         "图 2：D(n) 收敛曲线（R_eff ∈ {1000, 1500} 的截断效果）。"),
        ("fig3_sensitivity_eps.png",
         "图 3：D(ε) 与数值 Lipschitz 估计，理论界 1/sin(ε) 渐近紧。"),
        ("fig4_R_eff_truncation.png",
         "图 4：R_eff 截断对 n ∈ {1, 3, 5} 三类情形下 D 的影响。"),
        ("fig5_MEC_vs_diameter.png",
         "图 5：最小包围圆（MEC）与直径圆的几何对比。"),
        ("fig6_cover_geometry.png",
         "图 6：L 形多边形上的直径圆覆盖判据。"),
        ("fig7_grid_overview.png",
         "图 7：网格化多检测点场景的整体示意。"),
    ]
    for png, cap in figs:
        p = FIG_DIR / png
        if p.exists():
            story.append(Image(str(p), width=160*mm, height=80*mm))
            story.append(Paragraph(cap, P))
            story.append(Spacer(1, 4))

    story.append(Paragraph("7.1 六类典型案例（表 1）", H3))
    rows = [["案例", "顶点数", "D (米)", "覆盖？", "MEC 半径 (米)"]]
    try:
        with open(JSONPATH, encoding="utf-8") as f:
            results = json.load(f)
        for r in results.get("three_typical", {}).get("cases", []):
            rows.append([r["case"], str(r["n_vertices"]),
                         f"{r['D']:.2f}", "是" if r["covered"] else "否",
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
    story.append(PageBreak())

    story.append(Paragraph("8 与问题 2 / 3 / 4 的接口", H2))
    story.append(Paragraph(
        "对给定的检测点集合与示向度，本问题输出的定位多边形 P₁ = (V₁, …, V_m) 直接作为："
        "（a）问题 2 的输入——第二检测点的候选部署区域；"
        "（b）问题 3 的输入——多机协同路径规划的几何基底；"
        "（c）问题 4 的输入——资源分配的可达域。"
        "直径 D 刻画最坏情形下的部署区域大小；MEC 半径 ρ_mec 给出覆盖 P₁ 的最小圆半径，"
        "作为第二检测点可放置范围的下界。", P))

    story.append(Paragraph("8.1 输出契约 (c*, ρ*) + wrap(α) 输入规约 + 5 米下界", H3))
    story.append(Paragraph(
        "输出契约：solve_problem_1(dets, thetas, R = 1800, eps_deg = 1, R_eff = 1500)"
        "返回字典 {poly, n_vertices, D, A, B, O, r, covered, max_offset, mec_center, mec_radius}。"
        "把 (c*, ρ*) = (mec_center, mec_radius) 作为问题 1 → 问题 3/4 的标准交接量，"
        "停止判据取 ρ* ≤ 20 米。"
        "wrap(α) 输入规约：solve_problem_1 入口对 thetas 统一调用 _wrap_alpha，把外部角度"
        "规约到 (−180°, 180°]，消除跨 ±180° 边界时的符号错误隐患"
        "（例如 350° 与 −10° 应等价）。"
        "5 米下界（附录 2 第 9 条）：距检测点 5 米以内的信号已饱和、示向度不可读，"
        "故定位引擎在此死区内不输出任何示向度——这是 R_eff 之下的硬截断。", P))

    story.append(Paragraph("9 结论", H2))
    story.append(Paragraph(
        "本文交付三件套算法（半平面交 → 旋转卡壳 → 覆盖判据），附完整正确性证明"
        "（命题 1–3、命题 5、命题 6 Jung 定理）、复杂度分析"
        "O(nk + m log m + m)、灵敏度 Lipschitz 界 |∂D / ∂θ_i| ≤ 1 / sin(ε)、"
        "R_eff 截断接口，以及与问题 2 / 3 / 4 的形式化几何接口。"
        "等边三角形反例（高 = (√3/2) · D > D/2）说明直径圆覆盖并非对所有凸多边形成立，"
        "Jung 定理给出 MEC 半径的解析上界 ρ* ≤ D / √3，对应 D ≤ 20 · √3 ≈ 34.64 米的停止判据。", P))
    story.append(PageBreak())

    story.append(Paragraph("附录 A 伪代码与复杂度", H2))
    story.append(Paragraph(
        "算法 1（求解）。输入：dets、headings、R、eps_deg、R_eff。"
        "输出：poly、D、A、B、O、r、covered、MEC。"
        "（1）由各扇形边界构造 half-planes；"
        "（2）poly ← HPI(half-planes, [−M, M]²)；"
        "（3）若启用 R_eff，则 poly ← clip_polygon_by_disk(poly, 0, R_eff)；"
        "（4）poly ← monotone_chain(poly)；"
        "（5）D, A, B ← polygon_diameter(poly)；"
        "（6）O, r ← (A + B) / 2, D / 2；"
        "（7）covered ← (max_k ‖V_k − O‖ ≤ r)；"
        "（8）mec_center, mec_radius ← Welzl(poly)。"
        "复杂度：O(nk + m log m + m)，其中 n 为扇形数、k = 2n + 2 为半平面数、m 为顶点数。", P))

    story.append(Paragraph("参考文献", H2))
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
        story.append(Paragraph(r, P))


def build_story(results: dict) -> list:
    """组装 PDF 故事，全中文，公式用 Unicode 数学符号。"""
    H1, H2, H3, P, PC = _make_styles()
    story = []

    # ===== 封面 =====
    story.append(Paragraph("问题 1 建模（国奖级改进版）", H1))
    story.append(Paragraph("摘要", H2))
    story.append(Paragraph(
        "本文研究 B 题问题 1：在已知若干检测点坐标 Sᵢ 及示向度 θᵢ 的前提下，"
        "构造可定位区域 P₁，给出计算其直径 D 的算法，并判断以 D 为直径的圆能否覆盖 P₁。"
        "我们给出三件套算法（半平面交构造 → 旋转卡壳求直径 → 覆盖判据），"
        "附完整正确性证明（命题 1–3、5、6）、复杂度分析、Lipschitz 灵敏度分析、"
        "R_eff 接入，以及与问题 2/3/4 的形式化几何接口 (c*, ρ*)。", P))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "关键词：问题 1；定位多边形；半平面交；旋转卡壳；覆盖判据；MEC；Lipschitz 界；Jung 定理",
        P))
    story.append(PageBreak())

    # ===== §1 问题重述 =====
    story.append(Paragraph("1 问题重述与建模目标", H2))
    story.append(Paragraph(
        "在 B 题问题 1 中，给定 n 个检测点 Sᵢ ∈ ℝ²（i = 1, …, n）及其对应的示向度 θᵢ，"
        "每个示向度允许 ±ε 的误差；每个检测点的可接收半径受全局常数 R 与全局有效接收半径"
        "R_eff ∈ [1000, 1500] 双重约束（依附件 2 接口文档）。"
        "要求：（i）构造由 n 个扇形约束与有效接收圆盘约束的交集——定位多边形 P₁；"
        "（ii）给出计算 P₁ 直径 D 的算法；（iii）判断以 D 为直径的圆能否覆盖 P₁。", P))
    story.append(Spacer(1, 4))

    # ===== §2 符号与基本假设 =====
    story.append(Paragraph("2 符号与基本假设", H2))
    story.append(Paragraph(
        "记 V = {V₁, …, V_m} 为 P₁ 的顶点（按逆时针 CCW 排列），"
        "A、B 为直径端点，O = (A + B) / 2 为圆心，r = D / 2 为半径。"
        "设 Ω = (∩ᵢ₌₁ⁿ Fᵢ) ∩ D(R_eff)，"
        "其中 Fᵢ = {P : ∠(SᵢP 方向, θᵢ) ≤ ε} 为扇形约束、"
        "D(R_eff) = {P : ‖P‖ ≤ R_eff} 为全局圆盘。"
        "假设 H1（充分检测）：Ω ≠ ∅；"
        "假设 H2（无退化点）：任意两个 Sᵢ 不重合；"
        "假设 H3（示向度互不矛盾）：所有扇形约束有公共非空解。", P))
    story.append(PageBreak())

    # ===== §3 严格建模 =====
    story.append(Paragraph("3 严格建模：半平面 + 凸集 + MEC 对照", H2))
    story.append(Paragraph(
        "（i）扇形 Fᵢ 等价于两条半平面的交（直线方向取 θᵢ ± ε），"
        "半平面的法向取单位方向旋转 90° 后归一化；"
        "（ii）Ω 是有限个闭半平面与闭圆盘的交集，由凸集关于交运算的封闭性，Ω 为紧凸集；"
        "（iii）把 Ω 多边形化即得凸多边形 P₁，其顶点恰是半平面交与圆盘裁剪的所有极角极值点；"
        "（iv）MEC 半径 ρ_mec 由 Welzl 算法（期望 O(m)）给出，作为以 D / 2 为半径"
        "的圆覆盖性判别的对照基线。", P))
    story.append(PageBreak())

    # ===== §4 → §9 + 附录 + 参考文献（全中文）=====
    _chapter_zh_4_to_9(story, H2, H3, P)

    return story


def main():
    results = {}
    json_path = HERE / "problem1_v3_results.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            results = json.load(f)

    doc = SimpleDocTemplate(str(OUTPDF), pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm,
                            title="问题 1 建模（国奖级改进版）",
                            author="建模小组")
    story = build_story(results)
    doc.build(story)
    print(f"PDF 已生成: {OUTPDF}  ({OUTPDF.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
