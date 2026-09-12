> ⚠️ **本报告已废弃（v4）**。其中的 Jung 定理不等号方向写错、圆约束逼近描述错误、
> 正式统计使用了低精度 N=32、检测点未限制在 Ω 内、第二问选点策略存在真实源信息泄漏。
> 请使用 `第一问/v5/第一问完整报告.md` 与 `第二问/v5/第二问完整报告.md`。
> 详见 `解题库/README_v5.md`。

# 第一问 v4 fix 后的重跑指令

## 关键变更
- `make_sector_halfplanes` 中 `n_lo` 符号由 `(u_lo_y, −u_lo_x)` 修正为 `(−u_lo_y, u_lo_x)`（与文档推导一致）
- `_point_in_convex_poly` 注释改为标准 CCW 凸判定
- 新增 T0 单扇形几何验证（θ=0°），失败立刻停

## 重跑命令

```bash
cd "C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第一问\v4"
python -X utf8 problem1_v4.py
```

期望 T0 通过后 T1 8/8 通过 → T2 协调算例 → T3 反向 D=0 → T4 等边三角 off>0 → T5 单扇形 D≈1500 → T6 统计。

如果 T0 仍失败（800,0 不在内 或 -800,0 在内 或 0,800 在内），把 T0 那 3 行输出贴出来——还需再调一次 n_lo / n_hi 符号。

## 第二问 v4（修了导入路径）

```bash
cd "C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第二问\v4"
set PYTHONPATH=C:\Users\LENOVO\Desktop\CUMCM2026Problems\解题库\第一问\v4
python -X utf8 problem2_v4.py
python -X utf8 plot_problem2.py
```

第二问原导入是 `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '第一问', 'v4'))`，文件路径含中文可能在某些 Python 编码设置下失败，临时把 PYTHONPATH 指过去是稳的。

如果第一问修正后第二问 D 不再都 = 3003.6，而是 Thales 圆 ≈ 50、其他 ≈ 1000+，说明算法真正生效。