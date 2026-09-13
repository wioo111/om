# 论文 HTML 可视化微调工作台

本工作台把正式 LaTeX 源码投影为浏览器阅读视图。点击一处正文、标题、图注、表注或列表项，会通过稳定 block ID 定位到唯一源码块；保存只替换该块的内容。最终论文仍由 LaTeX 构建，HTML 不承担最终分页与排版的权威角色。

## 获取与一键运行

仓库为 [https://github.com/wioo111/om](https://github.com/wioo111/om)，使用 `main` 分支。Windows 需预先安装 **Git、Python ≥ 3.10**。首次启动需要联网，启动入口会准备工作台专用虚拟环境、安装 Python 依赖并准备 MathJax；**无需 Node.js**。

在 PowerShell 中首次获取并启动：

```powershell
git clone --branch main https://github.com/wioo111/om.git
Set-Location -LiteralPath .\om
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1
```

后续从仓库根目录直接运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1
```

浏览器打开 **[http://localhost:8765](http://localhost:8765)**。启动器在后台运行服务，完成启动后退出；关闭浏览器或启动器不会停止后台服务，`Ctrl+C` 也不用于结束已启动的后台服务。服务只监听本机，GitHub 用来分发源码，不能使用 GitHub Pages 直接编辑电脑上的正式论文。

可指定端口或禁止自动打开浏览器：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1 -Port 8766 -NoBrowser
```

后台服务记录位于工作台目录 `paper_editor/runtime/server-8765.json`，包含对应进程信息；端口改变时记录文件名相应改变。对同一工作台已启动的服务，启动器会复用它。

需要同步仓库更新时，在仓库根目录运行：

```powershell
git pull --ff-only origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-paper-editor.ps1
```

先保存自己的修改并查看源码 diff。若 Git 提示本地修改冲突或分支分歧，应先处理改稿与合并，再重新启动；不要为更新工具而覆盖论文修改。

阅读和修改 HTML 不依赖 LaTeX。只有“构建 PDF”需要 **XeLaTeX**，可使用 MiKTeX 或 TeX Live，并安装论文所需的中文、数学、图表等宏包。MiKTeX 首次编译还可能下载缺失宏包；缺少工具或宏包时，工作台会报告构建失败和日志，而不会宣称已生成新 PDF。

## 目录结构

以下路径均相对于 `最终交付/工作台论文/`：

```text
工作台论文/
├─ README.md
├─ 启动工作台.ps1
├─ .env.example                  # 可选 AI 配置样例
├─ .env                          # 本地配置，不提交
├─ .venv/                        # 启动时准备的 Python 环境
├─ source_registry.json          # 唯一源、稳定 ID 与冻结范围登记
├─ archive/
│  └─ main_图文补全.tex.import    # 迁移前原稿，只用于追溯
├─ paper/
│  ├─ main.tex                   # 唯一正式 LaTeX 构建入口
│  ├─ source/
│  │  ├─ preamble.tex            # 导言与论文题名
│  │  ├─ abstract.tex
│  │  ├─ introduction.tex
│  │  ├─ q1.tex
│  │  ├─ q2.tex
│  │  ├─ q3.tex
│  │  ├─ q4.tex
│  │  ├─ conclusion.tex
│  │  ├─ appendix.tex
│  │  └─ ending.tex
│  ├─ paper_figures.pdf          # 正式图册
│  ├─ figures/                  # 有原始分图时优先读取，可选
│  └─ build/                     # 本地 PDF 和编译日志
└─ paper_editor/
   ├─ app.py                     # 本地 FastAPI 服务
   ├─ source_mapper.py           # ID 映射、验证、原子写入和撤销
   ├─ renderer.py                # HTML 阅读视图
   ├─ ai_rewrite.py              # 单块 AI 提案，不自动落盘
   ├─ pdf_builder.py             # 显式 XeLaTeX 构建
   ├─ run.py
   ├─ requirements.txt
   ├─ static/                    # 双栏界面
   ├─ baseline/                  # 导入基线，只用于比较
   ├─ cache/                     # 浏览器图片等派生缓存
   ├─ history.jsonl              # 本机逐块修改历史
   ├─ tests/
   │  ├─ test_source_mapper.py
   │  └─ test_api.py
   └─ test_renderer.py
```

仓库根目录的 `start-paper-editor.ps1` 是对外统一启动入口；用户无需切换到中文子目录，也无需手动安装前端构建工具。`figures/`、`.env`、虚拟环境、缓存和构建产物可以在首次启动或使用对应功能后出现。

## 正式源与稳定映射

当前进入最终 LaTeX 阶段：**`paper/main.tex` 与其引用的 `paper/source/*.tex` 是唯一正式源**。`main.tex` 通过 `\input` 组合各文件；可编辑块及文件范围由 `source_registry.json` 登记。生成的 HTML、PDF、历史副本、基线副本和 `archive/*.import` 都不是另一份可独立编辑的正文。旧生成链不得覆盖这一正式源目录。

每个语义块使用不影响 LaTeX 编译的注释标记：

```latex
%<paper-block id="q2.p001" type="paragraph">
对应的原始 LaTeX 内容
%</paper-block>
```

ID 不依赖行号。修改内容不会触发其他块重新编号；重复 ID 会报错。当前导入共有 **463 个稳定块，190 个冻结块**；其中包含 17 幅图、13 个表格和 29 个只读程序块。迁移登记保留导入稿与去标记后重建内容的摘要，便于确认拆分没有改动数学内容。

## 点击和手动编辑

1. 在左侧“HTML 阅读”中点击正文、标题、列表项、图注或表注。选中块高亮，右侧显示章节路径、block ID、源码路径与当前源码。
2. 在“手动编辑”的替换框中修改当前块。保留 `\section{...}`、`\caption{...}`、`\item` 等原有 LaTeX 结构；只改需要调整的文字。
3. 展开“本次修改 diff”核对当前块，然后点击“保存此块”；也可使用 `Ctrl+Enter`。
4. 保存成功后更新 HTML，保持阅读位置。普通文字修改不会自动完整编译 PDF。

点击图片定位整个只读 figure 块；点击图注定位单独的 caption 块。图片本体不使用 `contenteditable`。程序附录默认折叠，展开可阅读完整代码，不能在工作台中修改策略。

写入前检查 ID 唯一性、文件版本、LaTeX 基本括号平衡、marker 完整性及保护规则；写入采用临时文件与原子替换。若同一文件已被其他操作更新，会拒绝过期版本，需重新读取当前源码后处理自己的修改，不能覆盖竞争更新。

## Q1/Q2 冻结与公式模式

普通润色不得改变 Q1/Q2 的公式、数学常数、最优点、最优直径、引用及定理结论。保护涉及问题一、二正文及登记的相关摘要、分析和附录块。检测到受保护差异时，保存会被阻止并显示原因；部分定理或结论段整体冻结，不能借“润色”改变限定条件。

公式默认只读。只有选中**独立公式块**并显式勾选“编辑公式”，才可申请手动修改公式；这不是 AI 润色的绕过入口。普通正文中的行内公式仍受保护，不可通过改写整段放行。本工具建设与使用不自动改变 Q1/Q2 数学模型，也不重写 Q3/Q4 策略。

## AI 微调：先提案，再接受

AI 是可选功能，当前没有配置时会明确显示“AI 未配置”，手动编辑、历史和 PDF 功能仍可用。准备好模型服务后，在工作台目录复制配置样例：

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
notepad .env
```

按自己的服务填写：

```dotenv
PAPER_AI_PROVIDER=openai-compatible
PAPER_AI_BASE_URL=
PAPER_AI_MODEL=
PAPER_AI_API_KEY=
```

兼容 OpenAI 格式的服务地址通常需要包含其 `/v1` 路径；本地 Ollama 使用 `PAPER_AI_PROVIDER=ollama`，填写其服务地址与已安装模型名，密钥可以为空。配置文件只在本机保存；不要把真实 `.env` 或密钥提交到 GitHub。模型调用使用自己选择的服务及其费用规则。

操作步骤：

1. 选中一个可润色块，切换到“AI 微调”。
2. 选择“精简”“学术化”“去 AI 味”“拆长句”“增强逻辑”“保持含义润色”或“自定义”，按需补充要求。
3. 点击“生成修改建议”。每次只把章节标题、前一块、当前块、后一块和本次要求交给配置的模型。
4. 阅读 Before / After 及 diff。AI 只能返回当前块的替换 LaTeX，不应修改公式、符号、数值、引用、定理条件或结论。
5. 合适时点击“接受并保存此块”；不合适则“丢弃建议”。生成建议本身不写源码；违反冻结保护或版本已过期的建议不能接受。

未配置真实模型服务时，不把接口测试当作真实 AI 改写验收，也不会提供伪造的模型输出。

## 历史、撤销与 diff

在右侧“修改历史”中查看当前块的时间、操作类型及修改内容；点击“撤销最近修改”可撤销该块最近一次可撤销操作。历史记录写入本地 `paper_editor/history.jsonl`，包含 block ID、时间、before、after 与操作类型。撤销同样检查当前版本，并留下记录。

右上角“源码 diff”包含两种视图：

- **本轮源码修改**：正式源相对导入基线的差异；不会因刷新浏览器而清空。
- **Git diff**：源码的实际 Git 工作区差异。若正式源尚未被 Git 跟踪，界面会说明使用相对导入基线的 `git diff --no-index` 比较。工具不会替你暂存、提交或推送。

也可在仓库根目录查看：

```powershell
git diff -- "最终交付/工作台论文/paper/main.tex" "最终交付/工作台论文/paper/source"
```

## 构建正式 PDF

安装 XeLaTeX 后点击右上角“构建 PDF”。服务从点击时的正式源快照编译，关闭 shell escape，并按需要处理交叉引用。界面显示成功或失败、日志摘要与最终文件路径；成功后可切换到“PDF 预览”或打开生成文件。

输出位置：

- `paper/build/main.pdf`：最近一次成功构建的正式 PDF。
- `paper/build/build.log`：本次完整编译输出。
- `paper/build/build_status.json`：构建状态和对应源码版本。

如果编译期间又保存了文字，界面会提示 PDF 对应较早的构建快照，需再次构建才能纳入新修改。失败时先依据日志解决缺少的宏包、字体或 LaTeX 错误；HTML 能显示不代表 LaTeX 必然通过编译。

## 依赖与接口

Python 依赖以 `paper_editor/requirements.txt` 为准：FastAPI、Uvicorn、HTTPX、PyMuPDF 和 Pytest。MathJax 在首次准备后从本机提供，日常浏览不依赖外部公式 CDN。浏览器图片来自正式分图或图册页的 PNG 缓存，缓存转换不修改原图。

供本地界面使用的接口包括：

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/document` | HTML、块信息和源码版本 |
| `GET /api/block/{id}` | 当前块及其正式源码位置 |
| `POST /api/block/{id}` | 校验后写入当前块 |
| `POST /api/ai-rewrite/{id}` | 生成当前块建议，不落盘 |
| `POST /api/block/{id}/undo` | 撤销当前块最近修改 |
| `GET /api/history` | 修改历史 |
| `GET /api/diff` | 基线差异与实际 Git diff |
| `POST /api/build-pdf` | 开始正式 LaTeX 构建 |
| `GET /api/build-pdf/status` | 构建状态 |
| `GET /api/build-pdf/log` | 编译日志 |
| `GET /api/pdf` | 最近成功构建的 PDF |
| `GET /api/events` | 源码变化通知，刷新 HTML |

接口只为本机工作台提供服务，不是可直接部署在 GitHub Pages 上的在线协作系统。

## 当前验收依据与边界

本轮 48 项非视觉自动化测试全部通过，用时 10.42 秒：

- 32 项源码映射测试：块定位、稳定 ID、修改范围、版本竞争、保护与撤销等。
- 6 项 API 测试：本地接口、逐块写入、AI 提案流程和权限边界等。
- 10 项渲染测试：数学、引用、图注父子映射、表格、列表、代码保留、路径限制和 HTML 转义等。

真实论文的渲染检查覆盖 463 个 ID、17 幅图、13 个表格及 29 个代码块，未发现缺失或重复的 HTML 块映射。

实际浏览器操作已验收：选中 `abstract.p001`，临时修改文字并保存，确认 HTML 更新及相对基线的实际 diff；再通过历史撤销，源码 diff 恢复为空。点击图片定位只读 `q1.f001`，点击图注独立定位 `q1.c001`。[操作截图](acceptance/workbench-operation.png)已保存。

正式 PDF 已用 XeLaTeX 连续两轮构建成功：101 页、3,278,548 字节，交叉引用稳定，0 条 Overfull 警告。两轮日志合计仍有原模板的 80 行 Missing character 警告；本任务未为消除这些警告修改论文内容。后续改稿需要重新构建，不能沿用本次构建状态作为验证结果。真实外部 AI 服务尚未联调。

需要按改动范围重跑逻辑测试时，在工作台目录、已准备环境后执行：

```powershell
.\.venv\Scripts\python.exe -m pytest paper_editor/tests -q
.\.venv\Scripts\python.exe -m unittest paper_editor.test_renderer -v
```

上述浏览器操作、截图和 PDF 结果对应本轮验收；不代表其他电脑已完成首次安装，也不代表后续改稿已验证。遵守当前任务要求，不进行反复视觉检查。
