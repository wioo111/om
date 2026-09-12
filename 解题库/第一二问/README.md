# 第一、二问最终交付：解析策略 + 完整证明 + 可执行证书

这是合并后的第一、二问唯一正式共享模块，不依赖旧 v4/v5/v6 目录。旧 v5 已在本次冻结整理中移除，不再作为正式计算和论文结果源；第三、四问的历史依赖保持不变。本轮证据与适配说明见 MERGE_REPORT.md，原包验收记录已隔离到 provenance/。

## 先打开这些文件

- `paper/第一二问完整论文.pdf`：正文、全部证明、计算机辅助证明的构造及数值实验。
- `paper/第一二问完整论文.docx`：原生公式的可编辑 Word。
- `paper/正文模板.md`：唯一可编辑正文源；完整 Markdown、LaTeX、Word 和 PDF 均为生成物。生成脚本同时更新上一级 `完整论文/论文_第一二问.*`。
- `proofs/global_certificate.json`：整数/有理数区间证书，不是随机实验日志。
- `figures/manifest.json`：13张图的标题、数据来源、主文/补充用途。每图有 PNG/PDF/SVG。

## 最终理论结果

第一问：交会区域由半平面交给出。明确区分空集、无界、点、线段和有界多边形。直径是最远顶点对距离；以任意最远点对中点为圆心、D/2为半径，逐顶点检查即可精确判断直径圆是否覆盖。

第二问：固定“保证第二次接收或近距返回，最小化两次观测后精确源位置集合的最坏直径”的准则。未被目标边界截断的首次扇形上，连续平面的两个精确全局最优位置为 `(843.034753748736, ±545.528422439214)` 米（相对首次测向坐标）。最坏直径为 `110.969318572838...` 米。坐标由论文中的二次方程定义，不是网格拟合数字。

输入任意有效 S1、实测示向度 theta，只需平移与旋转该向量。对所有有效首次观测都保持相同最坏直径上界；中心观测给出所有策略无法突破的下界，因此该映射是“对全部首次观测取最坏情况”的全局极小极大策略。边界截断可能让某个给定观测获得更小值；本包没有把通用策略说成每个截断状态的逐点唯一最优。

证明不是把保守目标当原目标：下界来自精确物理可行的不可区分源对；上界利用外包五边形，但在同一对源处达到等号。两界相等后才推出精确全局最优。

## 运行

推荐 Python 3.10 或以上。首次安装：

```powershell
python -m pip install -r requirements-fast.txt
python run.py prove
python run.py test
python run.py experiments
python run.py figures
python run.py paper
python run.py verify
```

直接求解：

```powershell
python run.py q1 --input examples/q1_observations.json --out results/my_q1.json
python run.py q2 --s1 0 0 --bearing 0 --out results/my_q2.json
python run.py q2 --s1 2100 400 --bearing 190 --side -1 --out results/my_q2_external.json
```

第二问返回理论点、实际执行点和严格向内的数值保护位移。保护位移约0.000055米；执行点的目标值损失已由证书界定在0.0001米以内。不要将执行点误记为符号意义上的精确极小点。

重建数据、图片和文档：

```powershell
python run.py experiments
python run.py figures
python run.py paper
```

重建文档需要 Pandoc（也可安装 requirements-paper.txt）；生成 PDF 需要 XeLaTeX。Windows 文档使用本机宋体、微软雅黑、Times New Roman，Linux 使用 Noto CJK 与 Liberation Serif。图片使用已安装的中文字体。不附带字体文件。verify 检查本次各阶段的退出码、相关源文件和产物哈希，不接受旧日志替代重新执行。

## 代码结构

`geometry.py`：第一问几何内核；`posterior.py`：含近距排除的精确物理集合的内外近似；`policy.py`：常数时间解析策略；`interval.py`：向外舍入的整数区间算术；`proof.py`：全局下界代数检查、活动区间证明、全部其他示向度覆盖以及连续近优候选区证明。

`experiments.py` 生成全量配对数据，失败不丢弃。误差均匀分布只是实验假设，证明只使用有界误差。`plot_figures.py` 的数值曲线只用于展示；全局证明不依赖 Matplotlib、绘图采样或随机种子。

## 适用边界

解析常数和全局证明对应原题的 1°、5米、1000—1500米参数。不能直接修改这些参数后继续引用现有全局定理。一般参数下第一问几何函数仍可计算；第二问常数需要重新推导/验证。

不把D≤40米等同于20米光学保证，光学保证检查的是最小包围圆半径≤20米。同点重复测向不会产生新的独立误差。没有远程仓库写入，也不包含第三、四问的接口或结果。
