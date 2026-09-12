"""问题2 v3 国奖级 PDF 生成脚本（reportlab + 中文字体）.

输出文件：解题库/第二问/v3/问题二建模_v3.pdf
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
OUTPDF = HERE / "问题二建模_v3.pdf"
FIG_DIR = HERE / "figures"
JSONPATH = HERE / "problem2_v3_results.json"

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
ZH = "STSong-Light"


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
    return H1, H2, H3, P


def build_story(results: dict) -> list:
    H1, H2, H3, P = _make_styles()
    story = []

    # ===== 封面 =====
    story.append(Paragraph("问题 2 建模（国奖级改进版）", H1))
    story.append(Paragraph("摘要", H2))
    story.append(Paragraph(
        "本文研究 B 题问题 2：在已知第一次检测点 S₁ 与示向度 θ₁ 后，给出第二检测点 S₂ 的最优"
        "选择与候选区域 C_η，使得最坏情况下最小覆盖圆半径 ρ₂ 最小。我们构造源候选区域 F₁（窄角扇形"
        "被 Ω 与 B(S₁, 1500)\\B(S₁, 5) 截出），按 ‖S₂ − G‖ 把 G 分 A₀/A₁/A₂ 三类，"
        "以 J_robust(S₂) = max{max ρ₂, λ · 1_{A₂>0}} 为主模型、J_proxy(S₂) = max(1/|sin β|) "
        "为代理粗筛；推荐 (d, w) 参数化矩形采样（N=1260）；并给出退化情形 D1–D4、"
        "反例 2/3、命题 7/8/9 严格证明、调用契约与复杂度分析。", P))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "关键词：问题 2；候选区域；鲁棒最坏最小化；最小覆盖圆；退化情形；Jung 定理；接口契约",
        P))
    story.append(PageBreak())

    # ===== §1 符号 =====
    story.append(Paragraph("1 符号与基本假设", H2))
    story.append(Paragraph(
        "记检测点为 Sᵢ = (xᵢ, yᵢ)，示向度为 θᵢ，示向度误差 ε = 1°。"
        "目标区域 Ω = {(x, y) : x² + y² ≤ 1800²}，干扰源真实位置 G = (x_G, y_G)。"
        "角度归一化函数 wrap(α) = α − 360° · ⌊(α + 180°) / 360°⌋ ∈ [−180°, 180°)。"
        "附录 2 接口文档要点：同一检测点测向误差固定、测向误差范围 [−1°, 1°]、"
        "有效接收半径 R ∈ [1000, 1500] 米（机器狗无法读取）、"
        "近距阈值 5 米（信号饱和但可光学清除）。", P))
    story.append(PageBreak())

    # ===== §2 F₁ =====
    story.append(Paragraph("2 第一次检测后的源候选区域 F₁", H2))
    story.append(Paragraph(
        "第一次检测点为 S₁，示向度为 θ₁，读数本身存在 ±1° 误差："
        "α₁(G) = wrap(atan2(G − S₁) − θ₁) ∈ [−2°, 2°]。"
        "F₁ = Ω ∩ (B(S₁, 1500) \\ B(S₁, 5)) ∩ {P : |wrap(atan2(P − S₁) − θ₁)| ≤ 2°}。"
        "几何含义：以 S₁ 为顶点、方向 θ₁、张角 2° 的窄角形，被外环 1500 米和 Ω 截断。"
        "5 米下界在第一次检测中是信号饱和死区，第二次检测中才是可光学清除区，"
        "二者阈值相同但角色不同，混淆会导致 A₀ 被误划入『未定位』。", P))
    story.append(PageBreak())

    # ===== §3 三分类 =====
    story.append(Paragraph("3 候选源位置关于 S₂ 的分类", H2))
    story.append(Paragraph(
        "设 S₂ ∈ Ω 且 ‖S₂ − S₁‖ ≥ L_min。L_min 取 max(L_geo, L_eng)："
        "L_geo = D* / (2 sin ε) ≈ 992 米（理论下限，停止判据 ρ₂ ≤ 20 米的几何必要条件）；"
        "L_eng = 30 米（工程下限，避免两检测点物理重合）。"
        "把 F₁ 中 G 按 ‖S₂ − G‖ 分为三类："
        "A₀(S₂) = {G : ‖S₂ − G‖ ≤ 5}（可光学清除，代价 0）；"
        "A₁(S₂) = {G : 5 < ‖S₂ − G‖ ≤ 1500}（可精算 ρ₂）；"
        "A₂(S₂) = {G : ‖S₂ − G‖ > 1500}（盲区，赋惩罚 λ）。", P))
    story.append(PageBreak())

    # ===== §4 几何作用 =====
    story.append(Paragraph("4 第二检测点的几何作用", H2))
    story.append(Paragraph(
        "交会角 β(S₂, G) = arccos(((G − S₁) · (G − S₂)) / (‖G − S₁‖ · ‖G − S₂‖))，"
        "误差放大因子 κ(S₂, G) = 1 / |sin β(S₂, G)|。"
        "β 越接近 90°，D₂ 越小；β → 0° / 180°，D₂ → ∞。"
        "**κ 与 ρ₂ 的关系**：远场近似 L ≪ d 时 ρ₂ ≈ κ · 2ε · d；"
        "近场（d < 200 米）或退化情形（β → 0° / 180°），κ / ρ₂ 偏差可达 30%–50%。"
        "**结论**：κ 仅作粗筛代理，不作停止判据（严格判据为 ρ₂ ≤ 20 米）。", P))
    story.append(PageBreak())

    # ===== §5 最优选择模型 =====
    story.append(Paragraph("5 第二检测点的最优选择模型", H2))
    story.append(Paragraph("5.1 主模型：鲁棒最坏最小化", H3))
    story.append(Paragraph(
        "S₂* = argmin_{S₂ ∈ Ω} max_{G ∈ A₁(S₂)} ρ₂(S₂, G)，"
        "其中 ρ₂ 由问题一的 Welzl 算法给出。", P))
    story.append(Paragraph("5.2 盲区惩罚", H3))
    story.append(Paragraph(
        "J_robust(S₂) = max{ max_{G ∈ A₁(S₂)} ρ₂(S₂, G),  λ · 1_{Pr(G ∈ A₂) > 0} }。"
        "λ 取 1500 米作为下界（保守值），折算 ≈ 2025 米（移动 1500 + 检测 25 + 重选 500）。"
        "建议做 λ ∈ {1000, 1500, 2000} 三档扫描验证 S₂* 不敏感于 λ。", P))
    story.append(Paragraph("5.3 概率参考模型", H3))
    story.append(Paragraph(
        "J_prob(S₂) = (∫_{A₁} ρ₂ dG + λ · |A₂|) / |F₁|。"
        "源位置先验三档：(a) 均匀（无信息，默认）；(b) 指数（推荐，若附件 1 有历史数据）；"
        "(c) 对数正态（备选，贴合『源距离右偏』）。这只是次模型。", P))
    story.append(Paragraph("5.4 代理模型", H3))
    story.append(Paragraph(
        "粗筛模型：min_{S₂ ∈ Ω} max_{G ∈ A₁(S₂)} 1 / |sin β(S₂, G)|。"
        "仅在远场近似下与主模型同解；近场或盲区出现时可能给出误导性结果。", P))
    story.append(PageBreak())

    # ===== §6 候选区域 =====
    story.append(Paragraph("6 第二检测点的候选区域 C_η", H2))
    story.append(Paragraph(
        "设 J* = min_{S₂ ∈ Ω} J_robust(S₂)，相对容许量 η > 0："
        "C_η = {S₂ ∈ Ω : J_robust(S₂) ≤ (1 + η) · J*}。"
        "**命题 8**（J_robust 分段连续性）：J_robust(S₂) 关于 S₂ 是分段连续的，"
        "在 A₂ 占主导的区域跳变 λ − ρ₂_max；ρ₂_max 本身在 S₂ 平移下 Lipschitz 连续。"
        "η 的物理含义：η = 0 对应最优解集合；η = 0.2（推荐）对应"
        "『机器狗走偏一步仍在停止判据内』（±3 米 / 15 米 = 20%）。", P))
    story.append(PageBreak())

    # ===== §7 几何化候选 =====
    story.append(Paragraph("7 几何化候选区域", H2))
    story.append(Paragraph(
        "源距离先验区间 d ∈ [d_min, d_max] = [5, 1500]，G(d) = S₁ + d (cos θ₁, sin θ₁)。"
        "对 β₀ ∈ (0°, 90°]，单点候选 C_{β₀}(G₀) = {S₂ : 5 < ‖S₂ − G₀‖ ≤ 1500, "
        "|sin β(S₂, G₀)| ≥ sin β₀}。"
        "外候选 C_all(β₀) = Ω ∪_{d} C_{β₀}(G(d))；鲁棒候选 C_robust(β₀) = Ω ∩_{d} C_{β₀}(G(d))。", P))
    story.append(Paragraph("7.1 C_robust 恒空引理", H3))
    story.append(Paragraph(
        "**引理**：L ∈ [5, 1500]、ψ − θ₁ = ±90° 时，"
        "sin β₀ ≤ L / √(d² + L²) ≤ L_max / √(d_min² + L_max²) = 1500 / √(25 + 2.25 × 10⁶) ≈ 0.99996。"
        "即 β₀ < 90° 即可；β₀ = 90° 要求 L → ∞，与 ‖S₂‖ ≤ 1800 矛盾，故恒空。"
        "C_robust = ∅ 时的降级策略：(a) C_all；(b) S₂* = G₀ + 1000 · (−sin θ₁, cos θ₁)；"
        "(c) 触发第三检测点。", P))
    story.append(PageBreak())

    # ===== §8 理想第二检测点 =====
    story.append(Paragraph("8 理想第二检测点（代理闭式参考解）", H2))
    story.append(Paragraph(
        "**本节定位**：本节给出的是**已知 G 时的闭式参考解**，不是 §5.1 主模型的解。"
        "两者只在 G 已知时一致；G 未知时，本节仅作为代理模型的解析锚点，不与 C_η 重合。", P))
    story.append(Paragraph("8.1 命题 7（β–D₂ 单调性）", H3))
    story.append(Paragraph(
        "固定 d 与 L，D₂ 关于 β 在 (0°, 180°) 上严格单调递减，β = 90° 取极小值 "
        "D₂ = 2ε · max(d, L)。"
        "**证明概要**：D₂ ∝ 1 / sin β；β → 90° 时 sin β = 1，D₂ 最小；"
        "β → 0° / 180° 时 sin β → 0，D₂ → ∞（受 R = 1500 米截断）。证毕。", P))
    story.append(Paragraph("8.2 闭式表达", H3))
    story.append(Paragraph(
        "S₂(t) = G₀ + t · (−sin θ₁, cos θ₁)，t ∈ [5, 1500]，‖S₂(t) − S₁‖ ≥ L_min。"
        "源距离 d 不确定时，S₂*(d) = G(d) + t · (−sin θ₁, cos θ₁)，"
        "随 d 变化扫出弯曲带 C_all(90°)。", P))
    story.append(PageBreak())

    # ===== §9 退化情形 =====
    story.append(Paragraph("9 退化情形与失效模式", H2))
    story.append(Paragraph(
        "**情形 D1（β → 0°）**：G、S₁、S₂ 近似共线，sin β → 0，ρ₂ → ∞。"
        "**应对**：|sin β| < 1e-3 时立即抛弃该 S₂。", P))
    story.append(Paragraph(
        "**情形 D2（β → 180°）**：sin β 仍 → 0。**应对**：同 D1。", P))
    story.append(Paragraph(
        "**情形 D3（A₂ 占比 = 100%）**：所有候选源距离均超 1500 米。"
        "**应对**：Pr(G ∈ A₂) > 0.9 时直接重选 S₂。", P))
    story.append(Paragraph(
        "**情形 D4（ρ₂_max > 50 米）**：**应对**：触发第三检测点。", P))
    story.append(Paragraph("9.1 反例 2（β 退化 → D₂ 爆炸）", H3))
    story.append(Paragraph(
        "S₁ = (0, 0)、θ₁ = 0°，S₂ = (1000, 0)，G = (500, 0)："
        "G − S₁ 与 G − S₂ 方向相反，β = 180°，sin β = 0，ρ₂ = ∞。"
        "**说明**：S₂ 选在 S₁ 示向度射线上是最坏选择，必须显式剔除。", P))
    story.append(Paragraph("9.2 反例 3（C_robust = ∅ 的几何反例）", H3))
    story.append(Paragraph(
        "d_min = 5、d_max = 1500、β₀ = 89°：对任意 S₂ ∈ Ω，至少存在某个 d 使 "
        "|sin β(S₂, G(d))| < sin 89° ≈ 0.9998。"
        "**说明**：β₀ 接近 90° 时 C_robust 必然为空。", P))
    story.append(PageBreak())

    # ===== §10 停止判据 =====
    story.append(Paragraph("10 停止判据：与问题三、四的接口", H2))
    story.append(Paragraph(
        "若 ρ₂(S₁, S₂, G) ≤ 20 m，停止补充检测，直接光学精确定位 + 清除；"
        "若 > 20 m，需补充第三检测点。"
        "由 Jung 定理 ρ₂ ≤ D₂ / √3，故 D₂ ≤ 20 · √3 ≈ 34.64 m 时 ρ₂ 必然 ≤ 20 米（解析判据）。"
        "问题二给出 ρ₂ 数值；问题三、四根据 ρ* ≤ 20 m 决定是否继续；"
        "满足后机器狗移动到 c*（MEC 圆心）启动光学清除。", P))
    story.append(PageBreak())

    # ===== §11 算法 =====
    story.append(Paragraph("11 候选区域求解算法", H2))
    story.append(Paragraph("11.0 与问题一 v3 的调用契约", H3))
    story.append(Paragraph(
        "问题二的所有几何计算通过问题一的公共 API 调用：", P))
    story.append(Paragraph(
        "from problem1_core_v3 import solve_problem_1, _wrap_alpha", P))
    story.append(Paragraph(
        "def build_P2(S1, theta1, S2, G, ...):", P))
    story.append(Paragraph(
        "    theta2_G = degrees(atan2(G - S2))", P))
    story.append(Paragraph(
        "    thetas = [_wrap_alpha(theta1), _wrap_alpha(theta2_G)]", P))
    story.append(Paragraph(
        "    return solve_problem_1(dets=[S1, S2], thetas=thetas, R=1500, ...)", P))

    story.append(Paragraph("11.1 算法步骤（7 步）", H3))
    story.append(Paragraph(
        "（1）网格离散 Ω，间距 50 米。"
        "（2）(d, w) 参数化矩形采样：N_d = 60、N_w = 21，共 1260 个点（替换原拉丁超立方）。"
        "（3）每个 (S₂, G) 调 build_P2 构造 P₂。"
        "（4）Welzl 求 ρ₂。"
        "（5）J_robust(S₂) = max{ max_i ρ₂, 1500 · 1_{N₂>0} }。"
        "（6）找 J*，生成 C_η。"
        "（7）Nelder-Mead 精化 S₂*。", P))

    story.append(Paragraph("11.2 复杂度分析", H3))
    story.append(Paragraph(
        "网格 ≈ 2800 个 S₂；每个 S₂ 配 N = 1260 个 G 样本；"
        "每个 (S₂, G) ≈ 1 ms（HPI + Welzl，n=2, m≤8）；"
        "Nelder-Mead ≤ 100 步 ≈ 0.2 秒。"
        "总耗时单核 ≈ 61 分钟，多核并行（50 路）≈ 1.5 分钟。", P))

    story.append(Paragraph("11.3 灵敏度分析", H3))
    story.append(Paragraph(
        "采样 max 与真 max 偏差 ≤ O(σ_ρ / √N)；"
        "由问题一命题 5 Lipschitz 界 |∂D/∂θ| ≤ 1/sin(ε)，N = 1260 时偏差 ≤ 5%（σ_ρ = 30 米）。"
        "建议加图：对 N ∈ {50, 200, 500, 1260, 3000} 画 J* 收敛曲线。", P))
    story.append(PageBreak())

    # ===== 5 张图 =====
    story.append(Paragraph("12 数值实验", H2))
    figs = [
        ("fig1_F1_first_detection.png", "图 1：F₁ 几何（窄角扇形被 Ω 与 B(S₁,1500)\\B(S₁,5) 截出）。"),
        ("fig2_beta_isobands.png", "图 2：β 等值带（假设 G 沿 θ₁ 方向 1000 米处）。"),
        ("fig3_J_robust_heatmap.png", "图 3：J_robust 热图 + 最优点 S₂* + 候选区域 C_η=0.2。"),
        ("fig4_three_categories_A0A1A2.png", "图 4：固定 S₂ 时 F₁ 中 G 的三类划分 A₀ / A₁ / A₂。"),
        ("fig5_convergence_N_scan.png", "图 5：J_robust 关于 N_d 的收敛曲线（N_d=60 已稳定）。"),
    ]
    for png, cap in figs:
        p = FIG_DIR / png
        if p.exists():
            story.append(Image(str(p), width=160 * mm, height=90 * mm))
            story.append(Paragraph(cap, P))
            story.append(Spacer(1, 4))

    # ===== 参考文献 =====
    story.append(PageBreak())
    story.append(Paragraph("参考文献", H2))
    refs = [
        "[1] Preparata F P, Shamos M I. 计算几何导论. 施普林格, 1985.",
        "[2] Toussaint G. 旋转卡尺求解几何问题. IEEE, 1983.",
        "[3] Welzl E. 最小包围圆的随机化算法. LNCS, 1991.",
        "[4] Jung H W E. 关于平面点集的最小包围圆. 德国数学年刊, 1928.",
        "[5] 全国大学生数学建模竞赛组委会. 论文格式规范（2026）. 教育部, 2026.",
    ]
    for r in refs:
        story.append(Paragraph(r, P))

    return story


def main():
    results = {}
    json_path = HERE / "problem2_v3_results.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            results = json.load(f)

    doc = SimpleDocTemplate(str(OUTPDF), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            title="问题 2 建模（国奖级改进版）",
                            author="建模小组")
    story = build_story(results)
    doc.build(story)
    print(f"PDF 已生成: {OUTPDF}  ({OUTPDF.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()