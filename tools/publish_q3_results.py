"""Export allowlisted P3 result fields; read local evidence, never run a simulator."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
PRACTICE = ROOT / "解题库/演练调试/results"
FORMAL = ROOT / "解题库/正式运行/results"
OUT = ROOT / "解题库/结果汇总"
NORMAL = {"all_channels_cleared_or_covered", "cleared_maximum_16"}
COSTS = ("move_time_s", "switch_time_s", "measure_time_s", "clear_time_s")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def strategy_hash(metadata):
    for key, value in metadata.get("code_sha256", {}).items():
        if key.replace("\\", "/").endswith("第三问/v10/strategy_task.py"):
            return value
    return None


def metric_row(data, *, run_id, strategy, known_n=None, exit_code=None):
    total, cleared = number(data.get("virtual_time_s")), number(data.get("cleared"))
    costs = {k: number(data.get("time_breakdown", {}).get(k)) for k in COSTS}
    normal = data.get("stop_reason") in NORMAL and data.get("coverage_complete") is True
    normal = normal and not data.get("error") and exit_code in (0, None)
    if not data:
        normal = False if exit_code is not None else None
    return {
        "run_id": run_id, "strategy_or_variant": strategy,
        "known_target_count": known_n, "cleared": cleared,
        "full_clear": cleared == known_n if known_n is not None and cleared is not None else None,
        "normal_stop": normal, "stop_reason": data.get("stop_reason"),
        "coverage_complete_claim": data.get("coverage_complete"),
        "exit_code": exit_code, "has_result": bool(data),
        "has_error": bool(data.get("error")) or (exit_code not in (0, None)),
        "virtual_time_s": total,
        "time_per_target_s": total / known_n if total is not None and known_n else None,
        "time_per_cleared_s": total / cleared if total is not None and cleared else None,
        "measure_count": number(data.get("measure_count")),
        "clear_count": number(data.get("clear_count")),
        "clear_fail_count": number(data.get("clear_fail_count")),
        "distance_m": number(data.get("distance_m")),
        "time_breakdown": costs,
        "program_runtime_s": number(data.get("runtime_s")),
    }


def average(rows, key):
    values = [r[key] for r in rows if r.get(key) is not None]
    return mean(values) if values else None


def percentile(values, q=.95):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * q
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def summarize(rows):
    totals = [r["virtual_time_s"] for r in rows if r["virtual_time_s"] is not None]
    known = [r for r in rows if r["full_clear"] is not None]
    result = {
        "attempts": len(rows), "recorded_results": sum(r["has_result"] for r in rows),
        "full_clear": sum(r["full_clear"] is True for r in rows) if known else None,
        "full_clear_assessable": len(known),
        "normal_stops": sum(r["normal_stop"] is True for r in rows),
        "errors_or_non_normal": sum(r["normal_stop"] is False for r in rows),
        "time_available": len(totals),
        "mean_virtual_time_s": mean(totals) if totals else None,
        "mean_time_per_target_s": average(rows, "time_per_target_s"),
        "mean_time_per_cleared_s": average(rows, "time_per_cleared_s"),
        "mean_measure_count": average(rows, "measure_count"),
        "clear_failures": sum(r["clear_fail_count"] or 0 for r in rows),
        "mean_distance_m": average(rows, "distance_m"),
        "p95_virtual_time_s": percentile(totals),
        "max_virtual_time_s": max(totals) if totals else None,
        "mean_cost_s": {},
        "mean_time_per_target_by_N": {},
    }
    for key in COSTS:
        values = [r["time_breakdown"][key] for r in rows if r["time_breakdown"][key] is not None]
        result["mean_cost_s"][key] = mean(values) if values else None
    for n in sorted({r["known_target_count"] for r in rows if r["known_target_count"] is not None}):
        result["mean_time_per_target_by_N"][str(n)] = average(
            [r for r in rows if r["known_target_count"] == n], "time_per_target_s")
    complete_times = [r for r in rows if r["virtual_time_s"] is not None and r["cleared"]]
    result["sum_time_over_sum_cleared_s"] = (
        sum(r["virtual_time_s"] for r in complete_times) / sum(r["cleared"] for r in complete_times)
        if complete_times else None)
    return result


def offline_stages():
    stages = []
    for report in sorted(PRACTICE.glob("p3_*/report.json")):
        data = read(report)
        records = data.get("records", [])
        if not records or not any(number(r.get("N")) is not None for r in records):
            continue
        if not all(r.get("evaluation") == "offline_practice_not_official_simulator" for r in records):
            continue
        execution = read(report.parent / "execution.json")
        metadata = data if data.get("code_sha256") else execution
        rows = []
        groups = defaultdict(list)
        for i, record in enumerate(records, 1):
            row = metric_row(record, run_id=f"{report.parent.name}-{i:04d}",
                             strategy=record.get("variant", "unrecorded"), known_n=number(record.get("N")))
            row.update({"seed": number(record.get("seed")), "model": record.get("evaluation_model", "uniform"),
                        "error_mode": record.get("error_mode"), "post_last_clear_s": number(record.get("post_last_clear_s"))})
            if row["distance_m"] is None and row["time_breakdown"]["move_time_s"] is not None:
                row["distance_m"] = row["time_breakdown"]["move_time_s"] * 5
                row["distance_basis"] = "move_time_s * simulator_speed_5_m_per_s"
            rows.append(row)
            groups[(row["model"], row["strategy_or_variant"])].append(row)
        summaries = []
        for (model, variant), grouped in sorted(groups.items()):
            summary = {"model": model, "variant": variant, **summarize(grouped)}
            baselines = {r["seed"]: r for r in groups.get((model, "probe_plan"), [])}
            pairs = [(r, baselines[r["seed"]]) for r in grouped if r["seed"] in baselines]
            deltas = [(r["virtual_time_s"] / b["virtual_time_s"] - 1) * 100 for r, b in pairs
                      if r["virtual_time_s"] is not None and b["virtual_time_s"]]
            summary["paired_against_probe_plan"] = {
                "count": len(deltas), "slower_scenarios": sum(x > 1e-8 for x in deltas),
                "worst_time_increase_percent": max(deltas) if deltas else None,
            }
            summaries.append(summary)
        stage = {"stage": report.parent.name, "source_report_sha256": sha(report),
                 "strategy_task_snapshot_sha256": strategy_hash(metadata), "summaries": summaries, "runs": rows}
        command = data.get("command", [])
        for arg in ("--range-min", "--range-max", "--reception-min", "--reception-max"):
            if arg in command:
                stage[arg.lstrip("-").replace("-", "_")] = number(float(command[command.index(arg) + 1]))
        stages.append(stage)
    return stages


def live_runs(base, mode):
    result = []
    for index, directory in enumerate(sorted(base.glob("*_p3_*")), 1):
        data, version, execution = (read(directory / name) for name in ("result.json", "version.json", "execution.json"))
        row = metric_row(data, run_id=f"p3-{mode}-{index:03d}",
                         strategy=data.get("strategy", version.get("strategy", execution.get("strategy", "unrecorded"))),
                         exit_code=execution.get("exit_code"))
        row["strategy_task_snapshot_sha256"] = strategy_hash(version) or strategy_hash(execution)
        row["evidence"] = {"result_sha256": sha(directory / "result.json") if data else None,
                           "execution_sha256": sha(directory / "execution.json") if execution else None}
        row["result_unavailable_reason"] = None if data else "connection_interrupted_before_result"
        signals = Counter()
        exit_accepted = None
        exit_reason = None
        action_file = directory / "actions.jsonl"
        if action_file.exists():
            for line in action_file.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                try:
                    action = json.loads(line)
                except json.JSONDecodeError:
                    continue
                response = action.get("response") or {}
                if action.get("path") == "/measure":
                    signal = response.get("measure_result")
                    signals[signal if signal in ("no_signal", "direction", "near") else "missing_or_other"] += 1
                if action.get("path") == "/exit":
                    exit_accepted = response.get("accepted")
                    exit_reason = response.get("exit_reason")
        row.update({"measure_response_counts": dict(signals), "simulator_exit_accepted": exit_accepted,
                    "simulator_exit_reason": exit_reason})
        row["normal_stop"] = bool(row["normal_stop"] and row["exit_code"] == 0 and exit_accepted is True)
        result.append(row)
    return result


def f(value):
    return "未提供" if value is None else f"{value:.2f}" if isinstance(value, float) else str(value)


def render(payload):
    lines = ["# 第三问结果整理", "", "本页将本地离线模拟、真实模拟器演练、正式运行分开。所有耗时均为虚拟秒，程序运行秒单列于 JSON。", "",
             "当前演练与正式策略：`OpticalTaskP3`；源码：`解题库/第三问/v10/strategy_task.py`。",
             f"源码 SHA-256：`{payload['current_strategy_sha256']}`。历史相同变体名称须同时核对阶段源码哈希，不能当作当前版本。", "",
             "脱敏逐场数据、全部阶段成本和逐 N 均值见 [第三问.json](第三问.json)。原始日志继续留在本机，本整理未重跑模拟器或改动策略。", "",
             "## 统计口径", "",
             "离线模拟已知真实 N，报告 T/N 与全清数。真实演练、正式输出不公开目标总数，报告 T/已清除数；全清数标记未提供，不把程序覆盖完成判断当作官方全清确认。",
             "正常停止要求策略正常结束；真实运行还要求脚本退出码 0、模拟器接受 /exit。正式上传确认表示收到并通过外层校验，不等于最终评分。",
             "均值使用本组所有已记录耗时，包括失败记录；缺失耗时不填零，结果缺失次数单列。阶段之间可能复用场景，禁止把执行次数相加当作独立样本数。均匀模型与历史参考敏感性模型分别统计。", "",
             "## 最新离线迭代", "",
             "下表保留开发、验证、确认和边界各阶段及全部比较变体。开发阶段复用同一组 14 场景；确认名称是历史标签，原计划明确不称最终盲测。", "",
             "| 阶段 | 模型 | 变体 | 全清/记录 | 正常停止 | 平均 T/N | 平均 T | 检测均值 | 清除失败总数 | P95 T | 最差配对增加% |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for stage in payload["offline"]:
        if not stage["stage"].startswith("p3_task_"):
            continue
        for s in stage["summaries"]:
            lines.append(f"| {stage['stage']} | {s['model']} | {s['variant']} | {f(s['full_clear'])}/{s['attempts']} | {s['normal_stops']} | {f(s['mean_time_per_target_s'])} | {f(s['mean_virtual_time_s'])} | {f(s['mean_measure_count'])} | {s['clear_failures']} | {f(s['p95_virtual_time_s'])} | {f(s['paired_against_probe_plan']['worst_time_increase_percent'])} |")
    lines += ["", "最差配对增加按同阶段、同模型、同种子与 probe_plan 比较；正数表示退步，失败清除均已计费。没有配对时填未提供。", "",
              "## 真实模拟器演练", "", "各策略在不同案例运行，以下横向均值仅描述记录，不能据此宣称因果提速。", "",
              "| 版本 | 场数 | 正常停止 | 官方全清 | 平均 T | 平均 T/已清除数 | 清除失败总数 |", "|---|---:|---:|---|---:|---:|---:|"]
    for strategy, s in payload["practice_summaries"].items():
        lines.append(f"| {strategy} | {s['attempts']} | {s['normal_stops']} | 未提供 | {f(s['mean_virtual_time_s'])} | {f(s['mean_time_per_cleared_s'])} | {s['clear_failures']} |")
    for title, rows in (("演练逐场记录（含历史版本）", payload["practice"]), ("正式逐场记录（含失败接入）", payload["formal"])):
        lines += ["", f"## {title}", "", "| 匿名记录 | 策略 | 清除数 | T | T/已清除数 | 检测 | 失败 clear | 移动/换频/检测/清除成本 | 正常停止 |", "|---|---|---:|---:|---:|---:|---:|---|---|"]
        for r in rows:
            cost = "/".join(f(r["time_breakdown"][k]) for k in COSTS)
            lines.append(f"| {r['run_id']} | {r['strategy_or_variant']} | {f(r['cleared'])} | {f(r['virtual_time_s'])} | {f(r['time_per_cleared_s'])} | {f(r['measure_count'])} | {f(r['clear_fail_count'])} | {cost} | {'是' if r['normal_stop'] else '否/无结果'} |")
    formal = payload["formal_summary"]
    lines += ["", f"正式：{formal['recorded_results']} 份完成结果、{formal['attempts'] - formal['recorded_results']} 次失败接入。失败接入没有完整耗时与清除结果，已保留，不能按零耗时计入均值。",
              f"三份完成结果合计清除 {sum(r['cleared'] or 0 for r in payload['formal'])} 个源；逐场 T/已清除数均值 {f(formal['mean_time_per_cleared_s'])} 秒，加权总 T/总清除数 {f(formal['sum_time_over_sum_cleared_s'])} 秒。",
              "三次正式完成记录与原发布的模拟器统计相符，上传状态 confirmed / outer_verified；官方目标总数与最终分数未提供。原说明见 [正式结果说明](../正式运行/P3_FORMAL_RESULTS.md)。", "",
              "## 历史离线阶段索引", "", "历史失败、退步和未入选变体均随逐场 JSON 保留；不把旧版离线结果合并为当前版本成绩。", "",
              "| 阶段 | 记录数 | 模型与变体分组数 | 全清记录数 | 正常停止记录数 |", "|---|---:|---:|---:|---:|"]
    for stage in payload["offline"]:
        lines.append(f"| {stage['stage']} | {len(stage['runs'])} | {len(stage['summaries'])} | {sum(r['full_clear'] is True for r in stage['runs'])} | {sum(r['normal_stop'] is True for r in stage['runs'])} |")
    return "\n".join(lines) + "\n"


def main():
    practices, formal = live_runs(PRACTICE, "practice"), live_runs(FORMAL, "formal")
    published = read(ROOT / "解题库/正式运行/evidence/p3_formal_summary.json")
    completed = [r for r in formal if r["has_result"]]
    for row, official in zip(completed, published.get("runs", [])):
        program = official["program_result"]
        for key in ("cleared", "virtual_time_s", "measure_count", "clear_fail_count"):
            if row[key] != program[key]:
                raise ValueError(f"Formal evidence mismatch: {key}")
        stats = official["simulator_statistics"]
        row["published_simulator_statistics"] = {key: stats.get(key) for key in (
            "upload_state", "formal_upload_state", "end_reason", "cleared_jammer_count", "measure_accepted_count",
            "virtual_time_s", "clear_failure_count", "statistics_state")}
    grouped = defaultdict(list)
    for row in practices:
        grouped[row["strategy_or_variant"]].append(row)
    payload = {
        "schema_version": 1, "problem": 3, "current_strategy": "OpticalTaskP3",
        "current_strategy_source": "解题库/第三问/v10/strategy_task.py",
        "current_strategy_sha256": sha(ROOT / "解题库/第三问/v10/strategy_task.py"),
        "scope": "Existing local P3 offline report records plus all saved live practice and formal attempts; no rerun",
        "privacy": "Allowlisted metrics only; no team identifiers, case codes, requests, raw or encrypted logs, or user paths",
        "official_score": None, "live_official_target_count_available": False,
        "aggregation": "Per-stage and per-model; means include every recorded time, missing times counted separately; stages may reuse seeds",
        "offline": offline_stages(), "practice": practices,
        "practice_summaries": {key: summarize(rows) for key, rows in grouped.items()},
        "formal": formal, "formal_summary": summarize(formal),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "第三问.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "第三问.md").write_text(render(payload), encoding="utf-8")
    print(json.dumps({"offline_stages": len(payload["offline"]), "offline_records": sum(len(x["runs"]) for x in payload["offline"]),
                      "practice_attempts": len(practices), "formal_attempts": len(formal), "formal_results": len(completed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
