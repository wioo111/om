# CUMCM 2026 B 题

第一、二问的唯一正式计算实现是 `解题库/第一二问/src/q12/`，根目录 `run.py` 和分问目录 `run.py` 都调用它。

当前冻结状态：Q1/Q2：FROZEN；Q3/Q4：继续开发。

## 环境与使用

建议 Python 3.13，在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r 解题库/第一二问/requirements-fast.txt
python run.py q1 --input 解题库/第一二问/examples/q1_observations.json
python run.py q2 --s1 0 0 --bearing 0
python run.py q2 --s1 2100 400 --bearing 190 --side -1
python run.py prove
python run.py test
python run.py experiments
python run.py figures
python run.py paper
python run.py verify
```

论文编译另需 Pandoc 和 XeLaTeX；Windows 使用本机宋体、微软雅黑和 Times New Roman，不随仓库分发字体。也支持安装 `pypandoc_binary` 提供 Pandoc。每条命令自动保存时间、退出码、输出和源文件/产物哈希到共享目录 `logs/runs/`，失败记录不会被覆盖。

## 正式论文与历史资料

- 唯一可编辑正文源：`解题库/第一二问/paper/正文模板.md`。表格、统计数字由 `results/`、本轮证明和测试证据生成。
- 总论文：`解题库/完整论文/论文_第一二问.md`、`.tex`、`.docx`、`.pdf`。运行 `python 解题库/完整论文/build_paper.py` 同步重建。
- 分问正文、实验与实现、证明附录、参考文献由同一模板分章生成，禁止直接修改生成文件。
- 第一、二问旧 v3/v4/v5 和根部历史代码、报告、图片均**不再作为正式计算和论文结果源**。旧 v5 目录已随本次冻结整理移除；第三、四问所需的独立内联/后备兼容模块仍保留。
- 第一、二问合并时未改动第三、四问；其中使用的内联旧几何模块和 v4 后备模块保留。后续第三、四问演练候选与离线证据单独管理，见下节。现有总论文原本仅含第一、二问，没有第三、四问总章节，不新增或拼接它们的结论。

正式图片用途见 `解题库/第一二问/figures/manifest.json`；证明与整合证据见共享目录 `MERGE_REPORT.md`。

## 第三、四问：仅演练迭代

在模拟器里开始对应问题的演练后，双击根目录的 [第三问_一键接入演练.cmd](第三问_一键接入演练.cmd) 或 [第四问_一键接入演练.cmd](第四问_一键接入演练.cmd)。自动等待倒计时、进入、执行候选算法、退出并保存结果；本机队号已配置且不提交 Git。两个文件必须与实际演练问题号对应。

命令行入口和模拟器操作规则见 [演练调试说明](解题库/演练调试/README.md)，本轮真实演练与离线对照分别见 [速度迭代记录](解题库/演练调试/SPEED_REPORT.md)。该入口不启动、切换或复位模拟器测试；只有已确认开放的演练会话可使用，不调用正式测试。原默认策略保留，候选须显式指定。

问题三的逐N评测、历史演练参考集及校准对照入口见 [分层评测与数据校准](解题库/演练调试/P3_EVALUATION.md)。均匀模型与参考模型分别汇报，算法不使用事后获知的真实N；历史数据与未来演练留出数据隔离。所有这些评测命令均为本地离线运行，不启动真实或正式测试。

当前第三问一键候选已更新为 `OpticalTaskP3`：实际加入源数量上界推理及以20米光学清除成本为目标的末段搜索。新代码、连续覆盖构造和本轮对照结果见 [第三问题意驱动优化](解题库/演练调试/P3_TASK_OPTIMIZATION.md)。第四问入口不变。

2026-09-13 05:30 最新8场真实问题三演练使用 `OpticalTaskP3`，全部清除成功（98/98个源）；逐N统计、每局耗时及未解决的尾段搜索问题见 [最新实机结果](解题库/演练调试/P3_PRACTICE_0530.md)。这不是新旧算法的同案例配对提速证明。模拟器本地数据目录、队号配置和临时文件不随源码发布，脱敏动作与源码快照保存在演练调试的 `results/` 中。
