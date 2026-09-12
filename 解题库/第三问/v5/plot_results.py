# -*- coding: utf-8 -*-
# plot_results.py
# 读取 results/summary.json 画 4 张图：
#   fig1: 各策略清除率柱状图
#   fig2: 各策略平均定位清除时间柱状图
#   fig3: 按 N 分组的时间曲线
#   fig4: 平均测量次数 vs 清除次数散点
#
# 用法：python plot_results.py

import json
import os
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
import matplotlib.pyplot as plt

# 优先使用系统中文字体，避免默认 DejaVu Sans 缺少中文字形。
_font_candidates = [
    os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts',
                 'Noto Sans SC (TrueType).otf'),
    os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts',
                 'NotoSansSC-VF.ttf'),
    os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts',
                 'simhei.ttf'),
]
for _font_path in _font_candidates:
    if os.path.exists(_font_path):
        font_manager.fontManager.addfont(_font_path)
        matplotlib.rcParams['font.family'] = \
            font_manager.FontProperties(fname=_font_path).get_name()
        break
matplotlib.rcParams['axes.unicode_minus'] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'figures')
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(HERE, 'results', 'summary.json'), 'r') as f:
    summary = json.load(f)

strategies = list(summary['by_strategy'].keys())
by = summary['by_strategy']

# ---- fig1: 清除率 ----
fig, ax = plt.subplots(figsize=(7, 4))
rates = [by[s]['overall']['clear_rate_mean'] * 100 for s in strategies]
ax.bar(strategies, rates, color=['#4e79a7', '#f28e2b', '#e15759', '#76b7b2'])
ax.set_ylabel('清除率 (%)')
ax.set_title('各策略清除率（mock 模拟器，{}局/策略）'.format(
    summary['N_ROUNDS']))
ax.set_ylim(0, 105)
for i, v in enumerate(rates):
    ax.text(i, v + 1, f'{v:.1f}%', ha='center', fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig1_clear_rate.png'), dpi=150)
plt.close()

# ---- fig2: 平均定位清除时间 ----
fig, ax = plt.subplots(figsize=(7, 4))
times = [by[s]['overall']['avg_time_mean'] for s in strategies]
ax.bar(strategies, times, color=['#4e79a7', '#f28e2b', '#e15759', '#76b7b2'])
ax.set_ylabel('平均定位清除时间 (s)')
ax.set_title('各策略平均定位清除时间（已清除频道）')
for i, v in enumerate(times):
    ax.text(i, v + 1, f'{v:.0f}', ha='center', fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig2_avg_time.png'), dpi=150)
plt.close()

# ---- fig3: 按 N 分组的时间曲线 ----
fig, ax = plt.subplots(figsize=(7, 4))
Ns = list(range(10, 17))
for s in strategies:
    byN = by[s]['by_N']
    ts = [byN.get(str(N), {}).get('avg_time_mean', None) for N in Ns]
    ts_clean = [t if t is not None else float('nan') for t in ts]
    ax.plot(Ns, ts_clean, marker='o', label=s)
ax.set_xlabel('干扰源数 N')
ax.set_ylabel('平均定位清除时间 (s)')
ax.set_title('不同 N 下的平均定位清除时间')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig3_by_N.png'), dpi=150)
plt.close()

# ---- fig4: 测量次数 vs 清除次数 ----
fig, ax = plt.subplots(figsize=(7, 4))
m_counts = [by[s]['overall']['measures_mean'] for s in strategies]
c_counts = [by[s]['overall']['clears_mean'] for s in strategies]
ax.scatter(m_counts, c_counts, s=120, alpha=0.7)
for s, m, c in zip(strategies, m_counts, c_counts):
    ax.annotate(s, (m, c), xytext=(7, 7), textcoords='offset points')
ax.set_xlabel('平均测量次数')
ax.set_ylabel('平均清除次数')
ax.set_title('策略效率：测量 vs 清除')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'fig4_efficiency.png'), dpi=150)
plt.close()

print('4 张图已写入', OUT)
