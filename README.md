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
- 第三、四问的模型、代码、数据和正文保持原样；其中使用的内联旧几何模块和 v4 后备模块保留。现有总论文原本仅含第一、二问，没有第三、四问总章节，不新增或拼接它们的结论。

正式图片用途见 `解题库/第一二问/figures/manifest.json`；证明与整合证据见共享目录 `MERGE_REPORT.md`。
