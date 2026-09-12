# 第三问 v8 三机协作

建议当前这台电脑担任 C，总控与官方演练留在这里；另两台分别负责 A、B。三台各用独立目录，从同一个协作包开始。

## 按当前瓶颈分工

历史 90 局的平均单源时间为 252.9 s。其中移动 177.7 s、检测 58.4 s、切频 11.1 s、清除 5.7 s。程序现实运行平均约 3.04 s/局；200 s 目标指虚拟耗时，增加电脑的作用主要是同时试验不同算法。

| 机器 | 负责的问题 | 只修改的文件 | 第一轮重点 | 交回的内容 |
|---|---|---|---|---|
| A | 路线、目标顺序、补充覆盖站位 | `collab/route_candidate.py` | 优先改善 N=10–12，减少完成清除后的补查绕路、重复覆盖和长距离折返 | 最佳候选文件、成对对比 JSON、最慢/失败轨迹、简短改动说明 |
| B | 扫哪些频道、何时补测、在哪里交会 | `collab/measure_candidate.py` | 减少低收益扫描与补测，保留同点固定误差和全部清除条件 | 最佳候选文件、成对对比 JSON、最慢/失败轨迹、简短改动说明 |
| C | 统一验收、组合、发布可运行版本、官方演练 | `collab/combined_candidate.py` | 同批新场景比较基线、A、B、A+B；只选实测最好的一个 | 对比表、选中版本、官方演练真实日志 |

A 可把移动时间 177.7→约145 s/源作为方向，B 可把检测时间 58.4→约40 s/源作为方向。两项若同时兑现，再加切频与清除，约为 202 s/源。这是分解目标，不是预计一定能达到的成绩；两者会相互影响，组合必须实测。

当前 N=10 的历史均值为 307.1 s，N=16 为 192.7 s。因此只汇报一个总均值容易受场景构成影响；新筛选集按 N 分层均衡，必须与同一批场景的 v8 比较，不能直接拿新均值与 252.9 s 相减。

## 开始操作

三台解压同一个 `q3_v8_collaboration.zip`，进入其中的 `q3_v8_collaboration` 目录。统一 Python 与 NumPy 版本；本机已验证环境为 Python 3.14.4、NumPy 2.4.4，包内 `collab/frozen.json` 记录环境与公共文件版本。

依赖安装命令为 `python -m pip install -r requirements_collab.txt`。复制对应的 `START_A.md`、`START_B.md`、`START_C.md` 内容作为各机任务说明。候选模板起初与 v8 行为相同，**尚未包含新算法提升**。

机器 A 的命令：

```powershell
python -X utf8 -m collab.bench run --candidate collab.route_candidate:make_strategy --role A --label A01
```

机器 B 的命令：

```powershell
python -X utf8 -m collab.bench run --candidate collab.measure_candidate:make_strategy --role B --label B01
```

包内已带 21 局开发集的 v8 基线缓存；Python、NumPy、公共文件和场景版本相同时可直接复用。不同环境或新场景首次会跑一次 v8 并缓存，后续只跑候选。改版后用 A02、A03 / B02、B03 等新标签，旧结果不覆盖。程序显示的 `paired_delta_s` 为“候选减基线”，负值表示更快。

筛选集 `collab/screen.json` 共 21 局，N=10–16 各 3 局。这个集合可重复用于迭代，是公开开发集，不能用作最终独立成绩。单机每轮围绕一个改动比较最多 3–4 个候选；先筛选后扩大样本，避免每次都跑 90 局。

## 每轮 45–60 分钟的交接

1. 前 25–35 分钟：A、B 分别实现有明确原因的改动，用同一筛选集与缓存基线比较。
2. 到约定交接时刻：每台只交一个优胜候选，不把整个工作目录或 `results` 相互覆盖。
3. C 收到 A、B 后固定候选文件，再生成一份此前未使用的新验收集。A、B 在等待期间可以分析下个思路，但不改正在验收的副本。
4. C 对 A、B、A+B 分别运行同一份验收集。基线只跑一次并复用。若组合不如单项，选择单项版本。
5. 选中版本交给 C 做官方演练，并带回真实逐动作日志。下一轮只针对新失败或明确瓶颈继续，不反复重跑已经通过的相同代码，不做视觉复查。

筛选的建议门槛：全部清除、无异常、平均比同场景基线改善至少 3%，P95 恶化不超过 5%。工具给出 `screening_pass` 供筛选使用；它不代表达到 200 s 或具有正式成绩。N=10–12 和压力场景也必须看，不能用跳过难例、丢弃失败局或提前退出降低均值。

## C 的独立验收与合并

收到并固定两份候选后，由 C 生成新清单，清单留在 C，开发机本轮不据此调参。共 70 个均衡主场景和 24 个压力场景。

```powershell
python -X utf8 -m collab.bench make-suite --kind validation --out collab/acceptance_round01.json

python -X utf8 -m collab.bench run --candidate collab.route_candidate:make_strategy --suite collab/acceptance_round01.json --role C --label C_A01
python -X utf8 -m collab.bench run --candidate collab.measure_candidate:make_strategy --suite collab/acceptance_round01.json --role C --label C_B01
python -X utf8 -m collab.bench run --candidate collab.combined_candidate:make_strategy --suite collab/acceptance_round01.json --role C --label C_AB01

python -X utf8 -m collab.bench table collab/results/C_A01.json collab/results/C_B01.json collab/results/C_AB01.json
```

换下一轮时生成新文件 `acceptance_round02.json`；不要对同一验收集反复调参后继续称为独立验证。上一轮失败场景可以纳入开发回归集。

每份 JSON 都包含公共基线版本、环境版本、场景指纹、候选文件版本、同场景逐局结果、N 分组统计、P95、成对改善量及其近似置信区间。`table` 会拒绝不同场景、不同公共版本或不同环境的混合排名。置信区间是描述性近似；最终还要看全清、尾部和官方演练。

两个候选类分别将 `RouteMixin`、`MeasureMixin` 与 v8 组合继承，C 的组合类同时加载两个 mixin。不要改变 `State`、`Track` 既有字段含义。新增状态分别用 `route_`、`measure_` 前缀；若增加构造函数，必须沿 `super()` 链初始化。A 不改测量回调，B 不改路线方法，两边都不改全清停止条件。

公共物理规则、模拟器、Q1 几何函数、HTTP 驱动和评测器属于冻结基线；不能各机自行修改后混比。如果发现公共缺陷，交给 C 统一修复、发布新的公共版本，并为该版本生成新基线。策略只能用接口响应，不能读取源真值、场景种子或按测试种子特判。

## 官方演练

原题附件明确同一账号不能同时在两台设备使用，所以官方模拟器由 C 独占，A/B 使用脱机模拟。只进行当前用户已经选择的演练，正式测试由用户安排。

验收后，C 可用下面的候选入口连接已手动启动的模拟器，无需修改公共 `robot.py`。把 candidate 替换为实测选中的 A、B 或组合；代码快照、版本信息、逐动作日志保存在 `collab/live_results/时间戳/`。

```powershell
python -X utf8 -m collab.live --candidate collab.combined_candidate:make_strategy --robot-id "你的参赛队号"
```

这个命令会实际连接已经启动的测试。它不会启动模拟器、登录、选择模式或自动安排正式测试。先确认当前启动的是要进行的演练。

既有 v8 演练命令：

```powershell
python -X utf8 robot.py AdaptiveV8 "你的参赛队号"
```

## 交付格式

每个开发机只需交：

- 一个候选 `.py` 文件；首轮辅助函数也放入各自候选文件，保持完整记录和直接组合。
- 对应 `collab/results/A01.json` 或 `B01.json`。
- 对应 `A01_worst_trace.json` / `B01_worst_trace.json`。
- 五行说明：改了什么、为何预计有效、平均改善、P95与全清率、已知问题。

本包只完成本地协作工具接入与小样本通路检查；尚未替用户在另外两台机器启动任务，也没有新增官方演练成绩。
