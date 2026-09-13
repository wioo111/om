# 本地论文 HTML 微调工作台

在浏览器阅读论文，点击段落、标题或图表注，精确修改对应的正式 LaTeX 源码块。普通保存即时更新 HTML；最终 PDF 仍由 XeLaTeX 构建。

项目仓库：[wioo111/om](https://github.com/wioo111/om)，分支 `main`。工作台位于 [`最终交付/工作台论文`](最终交付/工作台论文/README.md)。GitHub 用于分享源码与同步修改；编辑服务运行在自己的电脑上，不能把 GitHub Pages 当作可写入本地论文的后端。

## Windows 一键启动

预先安装 Git 和 Python 3.10 或更高版本，并让终端能找到 Python。首次运行需要联网下载 Python 依赖和 MathJax；不需要安装 Node.js。阅读、编辑 HTML 不需要 LaTeX。

首次获取：

```powershell
git clone --branch main https://github.com/wioo111/om.git
Set-Location -LiteralPath .\om
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1
```

以后从仓库根目录运行同一个入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1
```

启动入口准备工作台专用虚拟环境、安装所需依赖、准备本地 MathJax，然后在后台启动服务。浏览器地址为 **[http://localhost:8765](http://localhost:8765)**。服务仅监听本机回环地址；关闭浏览器或启动器不会停止后台服务，`Ctrl+C` 也不用于结束已启动的后台服务。

可用 `-Port 8766` 更换端口，或用 `-NoBrowser` 只启动服务而不打开浏览器。启动器记录位于工作台目录 `paper_editor/runtime/server-8765.json`；端口改变时文件名相应改变。

获取仓库更新后打开：

```powershell
git pull --ff-only origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1
```

已有本地改稿时，先查看并保存自己的源码 diff。若 Git 因本地修改或分支分歧停止更新，处理完成后再启动；不要用覆盖工作区的方式丢弃改稿。

## 基本操作

1. 点击左侧正文、标题、列表项或图表注，右侧显示稳定 block ID、章节路径、源码路径与当前源码。
2. 在“手动编辑”中修改当前块，查看 diff，再点击“保存此块”。保存只替换该块 marker 之间的内容。
3. AI 暂未配置时照常手动编辑。稍后在工作台目录的本地 `.env` 配置模型服务，再使用“AI 微调”；建议必须经“接受并保存此块”才会写回。
4. 在“修改历史”中点击“撤销最近修改”，撤销当前块最近一次可撤销操作。
5. 点击“源码 diff”，查看相对导入基线的本轮修改及实际 Git diff。
6. 需要正式 PDF 时，安装含 `xelatex` 的 MiKTeX 或 TeX Live，再点击“构建 PDF”；界面显示结果、日志摘要及 PDF 路径。

图片整体和附录程序代码只读；点击图注可单独改图注。公式默认只读，独立公式块需显式开启“编辑公式”。Q1/Q2 普通润色受到数学冻结保护，不能改公式、数值、引用或定理结论。

## 唯一正式源与详细说明

唯一构建入口为 `最终交付/工作台论文/paper/main.tex`，正文来自它引用的 `paper/source/*.tex`。HTML、缓存和 PDF 均为派生产物；`archive/` 保存迁移前原稿，不能作为另一份正文继续修改，也不能让旧生成链覆盖正式源。

当前导入包含 **463 个稳定块，其中 190 个块受到冻结保护**。本轮 48 项自动化测试通过（10.42 秒）。实际浏览器已完成段落保存、HTML 更新、diff 查看与撤销，撤销后源码 diff 为空；图片与图注独立定位通过。[操作截图](最终交付/工作台论文/acceptance/workbench-operation.png)已保存。

正式 PDF 经两轮 XeLaTeX 构建成功，101 页、3,278,548 字节，交叉引用稳定，0 条 Overfull 警告；两轮日志合计保留原模板的 80 行 Missing character 警告，未为消除警告改动论文内容。

完整目录、AI 配置、接口、修改保护、测试命令和验收边界见 [工作台使用说明](最终交付/工作台论文/README.md)。
