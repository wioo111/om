> ⚠️ **本报告已废弃（v4）**。其中的 Jung 定理不等号方向写错、圆约束逼近描述错误、
> 正式统计使用了低精度 N=32、检测点未限制在 Ω 内、第二问选点策略存在真实源信息泄漏。
> 请使用 `第一问/v5/第一问完整报告.md` 与 `第二问/v5/第二问完整报告.md`。
> 详见 `解题库/README_v5.md`。

# 任务：重画第一问 / 第二问 v4 图

## 背景
- 上一轮 PNG 信息密度极低：4 个算例多边形几乎看不见，n=2/3/6 D=0.0，中文字体乱码
- 已重写 `plot_problem1.py`（4 个有几何意义的算例，固定源 G=(500,400)）+ `plot_problem2.py`（3 张清晰图）
- 中文字体已用 fallback 链：SimHei / Microsoft YaHei / Source Han Sans CN / Noto Sans CJK SC

#.../problem1_v4.py` → `figures/fig_examples.png` 等 4 张
2. `python -X utf8 plot_problem2.py` → `figures/fig_strategies.png` 等 3 张

## 期望输出（关键判定）

第一问 fig_examples.png（4 子图）：
- (a) n=2：两个扇形从 (0,0) 和 (1100,0) 出发，垂直相交，定位多边形是个**小菱形/小四边形**（D 应 ~30-80 m）
- (b) n=3：三扇形包围源，多边形是**小三角**（D 应 ~20-50 m）
- (c) n=4：四扇形围绕，多边形接近**正方形**（D 应 ~20-40 m）
- (d) n=5：包含 (550, -100) 远点扇形，多边形仍小（D 应 ~20-40 m）

第二问 fig_thales_geometry.png（6 子图）：
- (a) Thales 圆子图：D 应 ~30 m，多边形小
- (b) 最佳共线：D 应 ~80 m
- (c) 平行共线：D 应 ~1400 m，多边形大
- (d) 反平行：D 应 ~1400 m
- (e) 随机：D 应 ~80 m
- (f) 策略说明表（中文）

fig_strategies.png：5 策略箱线图（D 对数坐标）+ 覆盖率柱状图
fig_heatmap_L.png：D 关于 (d, L) 的热图 + 等高线

## 必须汇报
1. **逐图描述你看到的内容**（不是 Traceback——是图本身）：
   - fig_examples.png：哪个子图能看到清晰多边形？D 数字？直径圆 vs MEC 是否能区分？覆盖判断文本？
   - fig_2R_over_D.png：8 个 n 的箱线图能否区分？Jung 上界线可见？
   - fig_cover_rate.png：覆盖率随 n 是否单调下降？8 个柱体清晰？
   - fig_D_sensitivity.png：D 关于 θ 误差 / R_eff 的敏感度是否清晰？
   - fig_strategies.png：5 策略箱线图（中位数差异是否直观）+ 50% 警戒线
   - fig_thales_geometry.png：5 策略子图的几何直观有区别吗？
   - fig_heatmap_L.png：D 在 (d, L) 平面上有等高线纹理吗？
2. 中文字体是否正常显示（标题"定位多边形"、"覆盖"、坐标轴标签等是否中文）
3. 文件大小 + 修改时间
4. 任何 Traceback

## 不要做
- 不要改代码再跑——失败就失败贴给我
- 不要装新包

## 若中文字体仍乱码

在两个 plot 脚本顶部把字体列表第一项换成你系统已有的中文字体：
```python
for cand in ['Microsoft YaHei', 'SimHei', 'Source Han Sans CN', ...]:
    ...
```
告诉我你系统装了什么中文字体（看 `C:\Windows\Fonts\`），我据...