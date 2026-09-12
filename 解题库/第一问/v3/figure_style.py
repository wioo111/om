"""v3.4 图表样式：顶刊配图风格（白底、无边框、衬线字体、低饱和网格）。"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---- 字体：衬线 + 中文 ----
for p in (r"C:\\Windows\\Fonts\\SourceHanSerifSC-Regular.otf",
          r"C:\\Windows\\Fonts\\SourceHanSansCN-Normal.ttf",
          r"C:\\Windows\\Fonts\\msyh.ttc",
          r"C:\\Windows\\Fonts\\simhei.ttf",
          r"C:\\Windows\\Fonts\\simsun.ttc"):
    try:
        fm.fontManager.addfont(p)
    except Exception:
        pass

# 中文衬线字体名（按系统实际可用逐级回退）
for name in ("Source Han Serif SC", "Source Han Serif CN",
             "Noto Serif CJK SC", "SimSun"):
    if name in [f.name for f in fm.fontManager.ttflist]:
        ZH = name
        break
else:
    ZH = "DejaVu Sans"

# ---- 顶刊配色（Nature / Science 风格，4 色）----
PALETTE = {
    "navy":     "#264653",  # 深蓝（主色 1，文字/边框）
    "teal":     "#2A9D8F",  # 蓝绿（主色 2）
    "orange":   "#E76F51",  # 暖橙（强调/数据点）
    "yellow":   "#E9C46A",  # 黄（次强调）
    "gray":     "#8D99AE",  # 中性灰（次要线）
    "light":    "#EDF2F4",  # 浅底色（极少用）
    "ink":      "#222831",  # 主文字
    "muted":    "#6B7280",  # 次文字
    "grid":     "#E5E7EB",  # 网格线
}

COLOR_CYCLE = [PALETTE["teal"], PALETTE["orange"],
               PALETTE["yellow"], PALETTE["gray"], PALETTE["navy"]]


def apply_style():
    plt.rcParams.update({
        "font.family":     "serif",
        "font.serif":      ["Times New Roman", "DejaVu Serif", ZH],
        "font.sans-serif": ["DejaVu Sans", "Arial", ZH],
        "font.size":       11,
        "axes.titlesize":  12.5,
        "axes.labelsize":  11,
        "axes.linewidth":  0.0,           # 边框完全去掉
        "axes.edgecolor":  PALETTE["ink"],
        "axes.labelcolor": PALETTE["ink"],
        "axes.titlecolor": PALETTE["ink"],
        "axes.facecolor":  "white",       # 白底，不嵌浅灰
        "figure.facecolor":"white",
        "axes.grid":       True,
        "grid.color":      PALETTE["grid"],
        "grid.linewidth":  0.6,
        "grid.alpha":      0.7,           # 网格极淡
        "lines.linewidth": 2.0,           # 主线 2.0
        "lines.markersize": 7,
        "legend.frameon":  False,         # 图例无边框
        "legend.fontsize": 10,
        "xtick.color":     PALETTE["muted"],
        "ytick.color":     PALETTE["muted"],
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.spines.left":  False,       # 左边框也去
        "axes.spines.bottom":True,
    })


def color_cycle():
    return list(COLOR_CYCLE)


def style_axes(ax, title=None, xlabel=None, ylabel=None):
    if title is not None:
        ax.set_title(title, color=PALETTE["ink"], pad=14,
                     weight="semibold", loc="left")   # 标题左对齐
    if xlabel is not None:
        ax.set_xlabel(xlabel, color=PALETTE["ink"], labelpad=8)
    if ylabel is not None:
        ax.set_ylabel(ylabel, color=PALETTE["ink"], labelpad=8)
    ax.tick_params(colors=PALETTE["muted"], length=0, pad=4)
    ax.spines["bottom"].set_color(PALETTE["muted"])
    ax.spines["bottom"].set_linewidth(0.8)


def legend(ax, place="right", **kw):
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return None
    if place == "right":
        kw.setdefault("loc", "center left")
        kw.setdefault("bbox_to_anchor", (1.02, 0.5))
        kw.setdefault("borderaxespad", 0.0)
    elif place == "below":
        kw.setdefault("loc", "upper center")
        kw.setdefault("bbox_to_anchor", (0.5, -0.14))
        kw.setdefault("ncol", min(3, max(1, len(handles))))
        kw.setdefault("borderaxespad", 0.0)
    else:
        kw.setdefault("loc", "best")
    leg = ax.legend(frameon=False, **kw)
    if leg is not None:
        for text in leg.get_texts():
            text.set_color(PALETTE["ink"])
    return leg


def reserve_legend_room(fig, place="right", right=0.80, bottom=0.20):
    if place == "right":
        fig.subplots_adjust(right=right, left=0.10, top=0.88, bottom=0.13)
    elif place == "below":
        fig.subplots_adjust(right=0.97, left=0.10, top=0.92, bottom=bottom)
    else:
        fig.tight_layout()