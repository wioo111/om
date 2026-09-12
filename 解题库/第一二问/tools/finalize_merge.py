"""Produce the merge report from recorded executions, without staging or committing."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
AUDIT=ROOT/'audit'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def command(args):
    p=subprocess.run(args,cwd=REPO,capture_output=True,text=True,encoding='utf-8')
    return dict(argv=args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)

stages=[read(AUDIT/f'latest_{name}.json') for name in ('prove','test','experiments','figures','paper','verify')]
assert all(s['exit_code']==0 and s['sources_unchanged'] for s in stages)
accept=read(AUDIT/'ACCEPTANCE.json')
protected=read(AUDIT/'protected_questions.json')
current={str(p.relative_to(REPO)):sha(p) for name in ('第三问','第四问') for p in (REPO/'解题库'/name).rglob('*') if p.is_file()}
assert current==protected['files_before']
temp=Path.home()/'AppData/Local/Temp'
reviews={name:read(temp/f'cumcm-q12-final-{name}/structure.json') for name in ('pdf','word')}
assert reviews['pdf']['sha256']==sha(REPO/'解题库/完整论文/论文_第一二问.pdf')
for r in reviews.values():
    assert all(not p['outside_page'] and not p['replacement_glyphs'] for p in r['pages'])
visual=dict(reviewed_at=datetime.now(timezone.utc).isoformat(),
    method='All 13 plot PNGs inspected; 4 layout issues corrected and those figures inspected again. All final PDF and native Word-export pages viewed in numbered contact sheets.',
    findings='Chinese labels rendered, no visible missing glyphs, overlap or page clipping. Two-station unequal axis scale explicitly captioned. Word proof-map table spans pages with repeated header.',
    corrected=['q1_01_geometry: legend outside plot','q1_02_jung_tight: legend outside plot',
               'q1_03_two_station: legend and metric separated from geometry','q2_04_continuous_certificate: legend away from proof curve'],
    plots={p.name:sha(p) for p in (ROOT/'figures').glob('*.png')},
    docx_sha256=sha(REPO/'解题库/完整论文/论文_第一二问.docx'),documents=reviews)
(AUDIT/'document_review.json').write_text(json.dumps(visual,ensure_ascii=False,indent=2),encoding='utf-8')
# uv environments intentionally need not contain pip. Query installed versions directly.
from importlib.metadata import version
environment=dict(python=sys.version,executable=sys.executable,
    packages={n:version(n) for n in ('numpy','scipy','shapely','matplotlib','pytest','mpmath','python-docx','numba','pypandoc_binary','pymupdf')},
    virtual_environment_outside_repository=True,
    fonts=['SimSun','Microsoft YaHei','Times New Roman'],
    tex='MiKTeX user installation; xelatex, installed via winget; ctex/xecjk and required packages installed',
    word_review='Native Word COM ExportAsFixedFormat (hidden new application), exit 0; LibreOffice renderer unavailable',
    install_commands=['uv venv --python 3.13 C:/Users/LENOVO/.cache/cumcm-q12-venv',
    'uv pip install --python C:/Users/LENOVO/.cache/cumcm-q12-venv/Scripts/python.exe -r 解题库/第一二问/requirements-fast.txt pypandoc_binary pymupdf',
    'winget install --id MiKTeX.MiKTeX --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity'])
(AUDIT/'ENVIRONMENT.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
manifest=read(ROOT/'figures/manifest.json')
rows=[]
for r in stages:
    elapsed=(datetime.fromisoformat(r['finished'])-datetime.fromisoformat(r['started'])).total_seconds()
    rows.append(f"| `python run.py {r['command']}` | {r['exit_code']} | {elapsed:.2f}s | [{r['run_id']}]({r['log']}) |")
figure_rows=[]
main_num=0;supplement_num=0
for f in manifest:
    if f['main']:
        main_num+=1;place=f'正文图{main_num}' if main_num<6 else '证明附录A，图6'
    else:
        supplement_num+=1;place=f'补充附录C，图C{supplement_num}'
    figure_rows.append(f"| `{f['stem']}` | {place} | `{f['source']}` |")
runs=[read(p) for p in sorted((ROOT/'logs/runs').glob('*/record.json'))]
failures=[r for r in runs if r['exit_code'] or not r['sources_unchanged']]
failure_lines=[f"- `{r['run_id']}`：{r['command']}，退出码 {r['exit_code']}，源文件执行期间未变化={r['sources_unchanged']}；[原始输出]({r['log']})。" for r in failures]
smokes=[r for r in runs if r['command'] in ('q1','q2') and r['cwd']==str(REPO) and r['exit_code']==0]
smoke_lines=[f"- `{' '.join(r['argv'][4:])}`：退出0，[输出]({r['log']})。" for r in smokes]
report=f'''# 第一、二问正式合并报告

生成时间：{datetime.now().astimezone().isoformat()}。本报告来自实际日志和文件检查，不沿用交付包的 PASS。

## 1. 仓库事实与范围

开始分支 `main`，基线 `1698697667831dc028cad6114111d2f1ebd51615`。原仓库 README_v5 指向 v5；原总稿实际引用 v4 结论，未存在统一的总论文生成脚本，不能按版本号判断正式来源。

开始已有的两个未跟踪文件：根目录 `CUMCM_Q1Q2_COMPLETE.zip`，以及 `解题库/第四问/v6/results/p4_local_20260913_005453.json`，均原样保留。输入 ZIP SHA256：`{sha(REPO/'CUMCM_Q1Q2_COMPLETE.zip')}`。

原总稿仅含第一、二问，没有第三、四问总章节。本次真正替换并重建该总稿的摘要、符号、假设、问题分析、第一问、第二問、算法、实验、结论、参考文献和证明附录；没有自创第三、四问章节，也没有重写第三、四问正文。本次未执行 commit、push、reset、clean 或删除历史代码。

## 2. 唯一正式实现和根目录入口

共享目录 `解题库/第一二问/`，内部直接保留 `src/q12/`、`proofs/`、`tests/`、`results/`、`figures/`、`paper/`，没有再套交付包目录。geometry、policy、interval、proof、posterior 均只有这一份正式实现；没有对官方模拟器或旧 v4/v5/v6 的新增依赖。

根目录 `run.py`、`解题库/第一问/run.py`、`解题库/第二问/run.py` 为薄适配。原 v5 的实验、绘图和验收共六个脚本曾直接执行并转接共享模块；冻结整理后 Q1/Q2 的 v5 目录已移除，与正式结果源隔离。根 README 和分问 README 明确正式入口与论文源。

在仓库根目录使用本轮环境：

```powershell
$py = 'C:/Users/LENOVO/.cache/cumcm-q12-venv/Scripts/python.exe'
& $py run.py q1 --input 解题库/第一二问/examples/q1_observations.json
& $py run.py q2 --s1 0 0 --bearing 0
& $py run.py q2 --s1 2100 400 --bearing 190 --side -1
& $py run.py prove
```

也可按根 README 新建自己的虚拟环境。q1、q2、prove、test、experiments、figures、paper、verify、all 均保留。输入路径相对调用者工作目录，内部资源和产物相对正式模块目录，不依赖作者电脑绝对路径。

## 3. 论文源与生成关系

唯一可编辑正文源：`paper/正文模板.md`。`build_paper.py` 与 `manuscript.py` 读取这一个源及正式 JSON/CSV、JUnit 和证明证书，生成完整 Markdown、LaTeX、DOCX、PDF，再同步到 `解题库/完整论文/论文_第一二问.*`。总稿构建入口是根目录执行 `python 解题库/完整论文/build_paper.py`；本轮最终构建实际由此入口执行成功。

- 第一问章节：第2节 → `paper/第一问正文.md`。
- 第二问主体与全域证明：第3、4节 → `paper/第二问正文.md`。
- 算法及实验：第5、6节 → `paper/实验与实现.md`。
- 摘要与符号、结论、参考文献分别独立生成。
- 附录A 完整几何分支、连续示向度区间覆盖、舍入安全构造；附录B 证明—代码—结果对应；附录C 七张补充图 → `paper/证明附录.md`。
- 没有把包内含后续内容的“第二问正文”机械追加。没有重复参考文献、附录嵌入第二问主体；所有 Markdown/TeX 图片路径已同步。

保留区域判别、连续直径、覆盖充要条件、Jung 界及反例；完整接收信息集、四圆安全域、连续全域下界、活动区间与非活动区间上界、上下界相等、通用策略保证、连续候选区域保证均保留具体证明与必要条件。主文公式(1)—(28)，附录(A1)—(A7)，图1—6及C1—C7。

精确结论针对未截断首次扇形的全局最优，以及对全部有效首次观测取最坏情况的策略级极小极大；不宣称每个边界截断状态逐状态最优。理论点约 `(843.034753748736, ±545.528422439214)` 米，严格最坏直径区间：

`{accept['diameter_star_interval_m'][0]}` 至 `{accept['diameter_star_interval_m'][1]}` 米。

执行点使用向内保护位移约 `0.00005534046665` 米，中心情形约 `(843.034744445260,545.528367886373)` 米，与理论点分列。没有为匹配目标数值手改输出。

## 4. 图片和显示

全部13图重新生成，保留 PNG/SVG/PDF。正文5张，证明附录1张，补充附录7张。每张用途和数据来源如下；具体图注以 manifest 为准。

| 图片 | 归位 | 数据源 |
|---|---|---|
{chr(10).join(figure_rows)}

实际检查13张PNG；修正典型多边形、等边三角形、双站反例、区间证书图的图例/标注遮挡。双站反例的非等比例坐标明确写入图注，其他几何图保持等比例。最终 XeLaTeX PDF 19页、Word 原生渲染17页逐页查看，未见方框乱码、图像裁切或重叠，Word 跨页证明映射表保留重复表头。结构检查无文本越界、无替代字符。图像及文档哈希和页级检查见 `audit/document_review.json`；临时页面渲染均在仓库外。

## 5. 本轮执行证据

Python 3.13 独立环境位于仓库外。安装依赖和本机 XeLaTeX/Pandoc 后执行全部要求流程。每次记录完整实际命令、cwd、开始结束时间、退出码、源文件及产物哈希，成功和失败日志均保留。下表是各阶段最终有效执行记录；此前完整模块目录的执行也保留在 logs/runs。

| 命令 | 退出码 | 耗时 | 完整输出 |
|---|---:|---:|---|
{chr(10).join(rows)}

- prove 从头有理数区间重算；63个非活动示向度叶区间、56个连续候选区域叶区间。
- test：158项通过，0失败、0错误、0跳过。原153项完整保留，新增5项真实子进程入口测试（包括非仓库工作目录）。不再依赖旧 pytest.txt 或硬编码测试数。
- experiments：第一问1000区域；第二问1500相同场景×4策略=6000评估，失败样本不删除，主策略无信号数0。
- figures：13×3格式；paper：本轮DOCX/PDF真正编译成功，341个原生Word公式。
- verify：重新执行数学证书，校验阶段源依赖、产物哈希、统计、分章、全部图片引用及总稿同步，全部通过。

根目录冒烟运行（其完整命令、输入、输出由各记录文件保存）：

{chr(10).join(smoke_lines)}

第一问例直径约36.339273549米，直径圆覆盖；第二问中心与区域外(2100,400)、190°、下侧分支均成功。日志中的理论点与执行点分别输出。

## 6. 问题定位和保留的失败记录

初次 Word 构建发现 Pandoc 未转换附录(A7)带 tag 的公式，原生显示公式数量不一致而主动失败。修复方法是仅在临时转换输入中移除 tag，由原有原生公式编号逻辑恢复编号；未放宽公式完整性断言。重新生成后341个原生公式、全部显示公式一致。

一次排版过程中图片源码调整使该轮源文件快照不一致，该记录未作为验收证据；后续已稳定重建。原始记录如下：

{chr(10).join(failure_lines)}

原包的 logs 和 ACCEPTANCE 等旧审计移至 `provenance/`，明确是历史证据，不参与本轮通过判断。首次 TeX 环境缺失已通过安装解决；标准 LibreOffice 渲染器因本机缺少 soffice 不可用，改用真实 Microsoft Word 隐藏实例导出进行显示检查，不以包内PDF替代。最终未通过项目：无；未执行第三、四问全量仿真，见下一节。剩余非致命警告：MiKTeX宏包请求的LaTeX版本较新、宋体没有原生粗体而使用常规字体；最终文字可读，不影响公式、证明或编译，编译日志原样保留。

## 7. 第三、四问保护和限制

第三、四问{len(current)}个文件的哈希在依赖检查前后及最终交付时相同；相对于 HEAD 的受保护目录差异为空。第三问v10的strategy_v10、第四问v6的strategy_p4及实际strategy依赖均成功导入，确认继续使用各自内联几何模块；第一问v4后备模块未删除或修改。具体命令、退出码、哈希见 `audit/protected_questions.json`。

没有重跑第三、四问耗时全量仿真，因此不声称其所有场景重新通过；本次没有改动其模型、代码、数据、结论或正文。已有第四问未跟踪结果文件原样保留。

## 8. 交付和 Git 状态

新增共享模块、适配入口、总稿生成脚本和总稿DOCX/PDF/TeX均为本次交付。`audit/untracked_files.txt`列出包括新增文件在内的完整未跟踪清单；其中输入ZIP和第四问原有结果不是本次新生成文件。`audit/git_diff_stat.txt`是实际 git diff --stat，仅包含已跟踪文件变化，不能代表全部新文件。

虚拟环境、临时解压、页面渲染、字体文件在仓库外；Python/pytest/Numba缓存由.gitignore排除，没有将它们纳入交付。未暂存、未提交、未推送。最终状态及检查退出码保存在 `audit/git_state.json`。
'''
(ROOT/'MERGE_REPORT.md').write_text(report.replace(chr(92),'/'),encoding='utf-8')
# Create the inventory before querying Git so it includes its own evidence filenames.
for name in ('untracked_files.txt','git_diff_stat.txt','git_state.json'):
    (AUDIT/name).touch(exist_ok=True)
git={name:command(args) for name,args in {
    'branch':['git','branch','--show-current'],
    'status':['git','-c','core.quotepath=false','status','--short'],
    'diff_stat':['git','-c','core.quotepath=false','diff','--stat'],
    'diff_check':['git','diff','--check'],
    'protected_diff':['git','diff','--exit-code','HEAD','--','解题库/第三问','解题库/第四问'],
    'untracked':['git','-c','core.quotepath=false','ls-files','--others','--exclude-standard'],
    'staged':['git','diff','--cached','--stat'],
}.items()}
assert all(git[k]['exit_code']==0 for k in git)
assert not git['staged']['stdout']
(AUDIT/'git_diff_stat.txt').write_text(git['diff_stat']['stdout'],encoding='utf-8')
(AUDIT/'untracked_files.txt').write_text(git['untracked']['stdout'],encoding='utf-8')
(AUDIT/'git_state.json').write_text(json.dumps(git,ensure_ascii=False,indent=2),encoding='utf-8')
print(git['diff_stat']['stdout'])
print('UNTRACKED_FILES',len(git['untracked']['stdout'].splitlines()))
print('MERGE_REPORT_OK',ROOT/'MERGE_REPORT.md')
