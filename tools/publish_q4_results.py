"""Publish aggregate Q4 evidence without private simulator identifiers.

Reads completed local artifacts only. It never contacts a simulator or runs a policy.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V6 = ROOT / "解题库/第四问/v6"
OUT = ROOT / "解题库/结果汇总"
NORMAL = {"all_channels_cleared_or_covered", "cleared_maximum_16"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public(value):
    """Remove identifiers and machine paths even from historical failure text."""
    if isinstance(value, dict):
        blocked = {"robot_id", "team_id", "team", "case", "case_code", "request_id", "request", "response", "command", "cwd", "source", "path", "file"}
        return {k: public(v) for k, v in value.items() if k not in blocked}
    if isinstance(value, list):
        return [public(x) for x in value]
    if isinstance(value, str):
        if re.search(r"[A-Za-z]:[\\/]|[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}", value):
            return "[private text omitted]"
    return value


def compact_record(record):
    fields = ("scenario", "variant", "actual_class", "name", "N", "cleared", "full_clear", "normal_stop", "accepted_run", "metrics_available", "virtual_time_s", "T_per_N", "measure_count", "clear_count", "clear_fail_count", "stop_reason", "coverage_complete", "distance_m", "time_breakdown", "stage_costs")
    out = {k: record[k] for k in fields if k in record}
    out["has_error"] = bool(record.get("error"))
    return public(out)


def offline_stage(path):
    data = read(path)
    return {
        "source": path.relative_to(ROOT).as_posix(),
        "source_sha256": sha(path),
        "status": data.get("status", "saved_report"),
        "stage": data.get("manifest", {}).get("stage"),
        "summary": public(data.get("summary", {})),
        "records": [compact_record(x) for x in data.get("records", [])],
    }


def real_runs(base, prefix):
    runs = []
    for index, folder in enumerate(sorted(base.glob("2026*p4*")), 1):
        ep, rp, vp = folder / "execution.json", folder / "result.json", folder / "version.json"
        e = read(ep) if ep.exists() else {}
        v = read(vp) if vp.exists() else {}
        terminal = e.get("exit_code") is not None and bool(e.get("finished"))
        # A stale directory does not authorize looking at an in-progress session.
        r = read(rp) if terminal and rp.exists() else {}
        row = {"label": f"{prefix}-{index:02d}", "terminal_execution": terminal,
               "launcher_mode": "formal" if prefix == "P4-F" else "practice",
               "exit_code": e.get("exit_code"), "result_available": bool(r),
               "strategy": r.get("strategy", e.get("strategy", v.get("strategy"))),
               "actual_class": r.get("actual_class", e.get("actual_class")),
               "strategy_sha256": r.get("strategy_sha256", e.get("strategy_sha256")),
               "official_mode_verified": False,
               "result_sha256": sha(rp) if terminal and rp.exists() else None}
        for k in ("cleared", "virtual_time_s", "avg_time_per_cleared", "measure_count", "clear_count", "clear_fail_count", "stop_reason", "coverage_complete", "distance_m", "time_breakdown", "actual_problem"):
            if k in r:
                row[k] = r[k]
        row["normal_stop"] = bool(r) and r.get("stop_reason") in NORMAL
        stats = r.get("simulator_summary", {})
        row["total_sources_from_saved_summary"] = stats.get("jammer_count")
        row["full_clear_verified"] = (r.get("cleared") == stats["jammer_count"]) if "jammer_count" in stats else None
        row["problem_matches"] = r.get("actual_problem") == 4 if "actual_problem" in r else None
        row["accepted_p4_evidence"] = bool(row["normal_stop"] and e.get("exit_code") == 0 and row["full_clear_verified"] and row["problem_matches"])
        if not terminal:
            row["status"] = "no_terminal_execution_evidence_not_read"
        elif e.get("exit_code") != 0:
            row["status"] = "wrong_problem" if r.get("problem_mismatch") else "connection_failure_no_result"
        else:
            row["status"] = "normal_stop" if row["normal_stop"] else "abnormal_stop"
        ap = folder / "actions.jsonl"
        if terminal and ap.exists():
            measures = collections.Counter()
            for line in ap.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                action = json.loads(line)
                if action.get("path") == "/measure":
                    response = action.get("response", {})
                    kind = response.get("measure_result")
                    measures[kind if kind in {"direction", "near", "no_signal"} else "missing_or_other"] += 1
            row["measure_result_counts"] = dict(measures)
        runs.append(row)
    return runs


def f(value):
    return "—" if value is None else f"{value:.2f}"


def main():
    selection = read(V6 / "route_round2/selection.json")
    dependencies = dict(selection["selected_dependency_sha256"])
    manifest = read(V6 / "route_round2/confirmation01/report.json")["manifest"]
    dependencies["cost_experiment.py"] = manifest["code_sha256"]["cost_experiment.py"]
    hashes = {name: {"validation_sha256": value, "current_sha256": sha(V6 / name), "matches": sha(V6 / name) == value} for name, value in sorted(dependencies.items())}
    stages = {p.parent.name: offline_stage(p) for p in sorted((V6 / "route_round2").glob("*/report.json"))}
    for label, stage in stages.items():
        # The selection report adds paired-regression statistics to raw stage reports.
        stage["summary"] = public(selection["label_evidence"][label]["summary"])
    history = {folder: {p.parent.name: offline_stage(p) for p in sorted((V6 / folder).glob("*/report.json"))} for folder in ("cost_round", "transfer_round", "hunt_round")}
    practice = real_runs(ROOT / "解题库/演练调试/results", "P4-P")
    formal = real_runs(ROOT / "解题库/正式运行/results", "P4-F")
    current_practice = [x for x in practice if x["strategy_sha256"] == selection["selected_sha256"]]
    current = public(selection["combined_summary"])
    data = {
        "schema_version": 1, "problem": 4, "publication_date": "2026-09-13",
        "scope": "Saved offline evidence, completed practice records, and completed formal-launcher records; no new tests or live requests.",
        "privacy": "No team identifier, robot identifier, request identifier, simulator case code, machine path, raw request/response, encrypted log or true source coordinates is published.",
        "metric_policy": "Offline mean T/N is the unweighted average over all scenario ratios. Failures and regressions remain listed. Real results with unknown source totals use T/cleared, not T/N.",
        "selected": {"class": selection["selected_class"], "name": "RouteProbeP4_zero_detour", "source": "解题库/第四问/v6/strategy_route_probe.py", "sha256": selection["selected_sha256"], "baseline": "HuntP4", "all_dependency_hashes_match": all(x["matches"] for x in hashes.values()), "dependency_sha256": hashes, "dependency_note": "18 selection dependencies plus cost_experiment.py from the frozen confirmation manifest; 19 in total.", "formal_entry": "第四问_一键接入正式.cmd", "practice_entry": "第四问_一键接入演练.cmd"},
        "offline_current": {"final_labels": selection["final_labels"], "combined_summary": current, "overall_improvement_percent": selection["overall_improvement_percent"], "goal_300_400_achieved": False, "stages": stages, "verification_record": public(selection["verification_record"])},
        "offline_history_separate_not_pooled": history,
        "practice": {"runs": practice, "current_version_runs": len(current_practice), "current_version_accepted": sum(x["accepted_p4_evidence"] for x in current_practice)},
        "formal_launcher": {"runs": formal, "attempts": len(formal), "normal_stops": sum(x["normal_stop"] for x in formal), "failed_or_incomplete": sum(not x["normal_stop"] for x in formal), "official_full_clear_count": None, "qualification": "The launcher explicitly records manual selection and no protocol verification of problem/mode. Saved formal results contain no authoritative total source count. Thus normal stops and cleared counts are reported, without an official full-clear rate."},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "第四问.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# 第四问最新结果汇总", "", "整理日期：2026-09-13。只整理已有结果，未启动新测试、未调参。", "", "当前正式、演练入口使用 **RouteProbeP4_zero_detour**。独立离线确认与边界共 168 场，全部清除且正常停止；平均 T/N 为 **508.16 秒/源**，同场 HuntP4 为 523.08 秒/源，整体下降 **2.85%**。尚未达到 300–400 秒/源。", "", "相对 HuntP4，168 场中有 **51 场耗时退步**，最差 **+18.26%**；并非每场都更快。失败、退步和未完成记录均保留在 [第四问.json](第四问.json)，不按成功样本筛选均值。", "", "## 当前版本及口径", "", "- 策略：[strategy_route_probe.py](../第四问/v6/strategy_route_probe.py)，SHA-256：`" + selection["selected_sha256"] + "`。", "- 本次核对 19 项离线冻结依赖（原 selection 18 项，另加冻结评测依赖 cost_experiment.py），全部与当前文件一致：**" + str(all(x["matches"] for x in hashes.values())) + "**。完整哈希在 JSON。", "- 离线指标用各场 T/N 的算术平均，失败 clear、检测、换频道、移动均计费。P95 沿用原报告的经验分位数；全清与正常停止分别检查。", "- 开发集重复使用 14 场，只用于开发；56 场确认和 112 场固定半径边界另列。离线、真实演练、正式入口记录不混为一个均值。", "- 当前入口切换仅代表代码接入，不能证明远端模拟器会话的题号或正式模式。", "", "## 离线最终对照（确认 56 + 边界 112）", "", "|策略|全清 / 正常停止|平均 T/N 秒|平均总 T 秒|平均距离米|平均检测|平均清除失败|P95 T/N 秒|最差单场退步|", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, s in current.items():
        md.append(f"|{name}|{s['full_clear']}/168 · {s['normal_stop']}/168|{f(s['mean_T_per_N'])}|{f(s['mean_T'])}|{f(s['mean_distance_m'])}|{f(s['mean_measure_count'])}|{f(s['mean_clear_fail_count'])}|{f(s['p95_T_per_N'])}|{f(s['comparison']['worst_regression_percent'])}%|")
    md += ["", "### 逐 N 平均 T/N（秒）", "", "|N|HuntP4|RouteAwareP4|RouteProbeP4|", "|---:|---:|---:|---:|"]
    for n in range(10, 17):
        md.append("|" + str(n) + "|" + "|".join(f(current[k]["by_N"][str(n)]) for k in current) + "|")
    md += ["", "### 各阶段与被淘汰开发结果", "", "|阶段|策略|场数|全清|正常停止|平均 T/N 秒|退步场数|最差退步|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for label, stage in stages.items():
        for name, s in stage["summary"].items():
            md.append(f"|{label}|{name}|{s['runs']}|{s['full_clear']}|{s['normal_stop']}|{f(s['mean_T_per_N'])}|{len(s['comparison']['regressions'])}|{f(s['comparison']['worst_regression_percent'])}%|")
    md += ["", "dev03_reuse_stops 的额外原地扫描使整体耗时增加，因此默认关闭；该轮结果保留。dev04 固定为当前版本后，才运行确认集和边界集。旧 Cost、Finish、Hunt 的各轮开发/确认/边界报告分组存于 JSON 的 offline_history_separate_not_pooled，未加入当前 168 场主均值。", "", "### 收益来源与实际触发", "", "|策略|移动秒|换频道秒|检测秒|清除秒|", "|---|---:|---:|---:|---:|"]
    for name, s in current.items():
        md.append("|" + name + "|" + "|".join(f(s["mean_costs"][k]) for k in ("move_time_s", "switch_time_s", "measure_time_s", "clear_time_s")) + "|")
    md += ["", "RouteAware 联合安排扫描站和已知源清除顺序；RouteProbe 在原移动线段上补测并恢复原扫描队列，控制额外检测与换频道成本。下表是当前候选的平均阶段成本。route_probe 的移动项是原路线的一部分，不代表额外绕路。", "", "|阶段|移动秒|换频道秒|检测秒|清除秒|", "|---|---:|---:|---:|---:|"]
    for phase, values in current["RouteProbeP4"]["phases"].items():
        md.append("|" + phase + "|" + "|".join(f(values.get(k, 0)) for k in ("move_time_s", "switch_time_s", "measure_time_s", "clear_time_s")) + "|")
    md += ["", "实际触发（168 场合计，同一事件的嵌套/平铺字段只展示一次）：", "", "|事件|次数|", "|---|---:|"]
    for event, count in current["RouteProbeP4"]["triggers"].items():
        if not event.startswith("route_probe_"):
            md.append(f"|{event}|{count}|")
    md += ["", "## 真实模拟器演练", "", f"共保留 {len(practice)} 次第四问入口记录；当前版本 {len(current_practice)} 次，{sum(x['accepted_p4_evidence'] for x in current_practice)} 次由已有模拟器结束统计确认全清并正常停止。历史版本仅作单独记录。P4-P-16 实际接入第三问，退出码 1，排除第四问性能结论但保留这一失败。", "", "|匿名运行|策略|状态|清除 / 结束统计总源数|T 秒|T/已清除 秒|检测|清除失败|无信号 / 方向 / near|", "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for r in practice:
        counts = r.get("measure_result_counts", {})
        md.append(f"|{r['label']}|{r['strategy']}|{r['status']}|{r.get('cleared', '—')}/{r.get('total_sources_from_saved_summary', '—')}|{f(r.get('virtual_time_s'))}|{f(r.get('avg_time_per_cleared'))}|{r.get('measure_count', '—')}|{r.get('clear_fail_count', '—')}|{counts.get('no_signal', 0)} / {counts.get('direction', 0)} / {counts.get('near', 0)}|")
    md += ["", "## 正式入口记录（模式未由协议核验）", "", "保存了 5 次尝试：3 次策略正常结束，2 次在进入接口时连接被重置，没有结果文件。正式入口日志明确记载题号及模式由人工选择、协议不验证，且结束结果没有总源数，因此这里只报告已清除数与 T/已清除，不写成官方全清率或 T/N。两次失败不能从总体记录中删去，也不能把缺失耗时当作 0。", "", "|匿名运行|状态|退出码|已清除|T 秒|T/已清除 秒|检测|清除失败|无信号 / 方向 / near|", "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in formal:
        counts = r.get("measure_result_counts", {})
        md.append(f"|{r['label']}|{r['status']}|{r.get('exit_code')}|{r.get('cleared', '—')}|{f(r.get('virtual_time_s'))}|{f(r.get('avg_time_per_cleared'))}|{r.get('measure_count', '—')}|{r.get('clear_fail_count', '—')}|{counts.get('no_signal', 0)} / {counts.get('direction', 0)} / {counts.get('near', 0)}|")
    md += ["", "最后一条正式入口记录为 220 次检测，其中 192 次 no_signal、28 次 direction。no_signal 是当前位置/频道没有信号，不能按第三问规则排除 1000 米区域。旧控制台抽样输出导致有方向的测量不一定显示；原始返回计数以本汇总为准。", "", "## 可复核范围", "", "[第四问.json](第四问.json) 包含当前 6 个离线阶段的全部逐场指标、每个阶段的全部失败和退步列表、历史 3 轮独立分组、29 条真实入口记录以及 19 项冻结依赖哈希。原始日志保留本地；公开记录不含队伍编号、机器人编号、请求编号、案例码、用户绝对路径或原始加密数据。", "", "运行 `python tools/publish_q4_results.py` 可从本地既有证据重新生成；不会运行策略或连接模拟器。历史验证记录为 113 项策略/独立目录测试通过；本次仅整理及核对文件，不声称重跑验证。", ""]
    (OUT / "第四问.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"dependency_matches": all(x["matches"] for x in hashes.values()), "dependency_count": len(hashes), "offline_stages": len(stages), "practice": len(practice), "formal": len(formal), "formal_normal_stop": sum(x["normal_stop"] for x in formal)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
