"""Build the final offline route-round report; never deploy or run a simulator.

The final population is confirmation01 (56) plus boundary01 (112), paired by
the complete scenario specification.  Development labels remain separate and
all failures/regressions are retained.  The default command refuses to publish
a final recommendation until both final stages are complete.
"""

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = HERE / "route_round2"
REFERENCE = "HuntP4"
FINAL_VARIANTS = ("HuntP4", "RouteAwareP4", "RouteProbeP4")
COST_KEYS = ("move_time_s", "switch_time_s", "measure_time_s", "clear_time_s")
SOURCE_NAMES = {"HuntP4": "strategy_hunt.py", "RouteAwareP4": "strategy_route.py",
                "RouteProbeP4": "strategy_route_probe.py"}
VERIFICATION_RECORD = {
    "source": "integration thread's completed validation record",
    "passed": 113,
    "seconds": 17.62,
    "command": "python -m pytest test_route.py test_route_probe.py test_route_standalone.py test_discovery_prune.py test_hunt.py test_local_hunt.py test_discovery_compact.py test_discovery_coverage.py test_discovery_mesh.py test_discovery_rings.py test_finish.py test_cost.py -q",
    "research_only_helper": "discovery_joint_prune.py",
    "research_only_test": "test_discovery_joint_prune.py",
    "research_only_passed": 9,
    "research_helper_integrated": False,
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scenario_key(row):
    return json.dumps(row["scenario"], sort_keys=True, separators=(",", ":"))


def row_key(row):
    return row["variant"], scenario_key(row)


def measured(row):
    fields = ("T_per_N", "virtual_time_s", "distance_m", "measure_count", "clear_fail_count")
    return (row.get("metrics_available", True)
            and all(isinstance(row.get(key), (int, float)) and math.isfinite(row[key]) for key in fields)
            and all(isinstance(row.get("time_breakdown", {}).get(key), (int, float))
                    and math.isfinite(row["time_breakdown"][key]) for key in COST_KEYS))


def full_clear(row):
    return bool(row.get("full_clear")) and row.get("cleared") == row["scenario"]["N"]


def normal_stop(row):
    return bool(row.get("normal_stop")) and row.get("stop_reason") != "step_limit"


def accepted(row):
    return bool(row.get("accepted_run")) and full_clear(row) and normal_stop(row) and not row.get("error")


def p95(values):
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def trigger_counts(diagnostic, prefix=""):
    result = Counter()
    for name, value in diagnostic.items():
        if not isinstance(value, dict):
            continue
        if name == "triggers":
            for key, count in value.items():
                if isinstance(count, (int, float)):
                    result[prefix + key] += count
        else:
            result.update(trigger_counts(value, prefix + name + "."))
    return result


def paired(group, reference):
    pairs = [(r, reference[scenario_key(r)]) for r in group
             if scenario_key(r) in reference and measured(r) and measured(reference[scenario_key(r)])]
    if not pairs:
        return {"paired_runs": 0, "status": "no_measured_pairs", "regressions": []}
    changes = []
    for row, baseline in pairs:
        fraction = row["virtual_time_s"] / baseline["virtual_time_s"] - 1
        changes.append(dict(scenario=row["scenario"], regression_fraction=fraction,
                            delta_T_s=row["virtual_time_s"] - baseline["virtual_time_s"],
                            candidate_accepted=accepted(row), reference_accepted=accepted(baseline)))
    mean_candidate = statistics.mean(row["T_per_N"] for row, _ in pairs)
    mean_reference = statistics.mean(row["T_per_N"] for _, row in pairs)
    worst = max(changes, key=lambda item: item["regression_fraction"])
    return dict(paired_runs=len(pairs), status="complete" if len(pairs) == len(group) else "partial_missing_metrics",
                mean_T_per_N=mean_candidate, reference_mean_T_per_N=mean_reference,
                improvement_percent=100 * (1 - mean_candidate / mean_reference),
                p95_regression_percent=100 * p95([item["regression_fraction"] for item in changes]),
                worst_regression_percent=100 * worst["regression_fraction"], worst_case=worst,
                regressions=[item for item in changes if item["regression_fraction"] > 1e-9],
                all_pairs_accepted=all(accepted(row) and accepted(base) for row, base in pairs))


def summarize(rows):
    reference = {scenario_key(row): row for row in rows if row["variant"] == REFERENCE}
    result = {}
    for variant in sorted({row["variant"] for row in rows}):
        group = [row for row in rows if row["variant"] == variant]
        costs = [row for row in group if measured(row)]
        item = dict(runs=len(group), full_clear=sum(full_clear(row) for row in group),
                    normal_stop=sum(normal_stop(row) for row in group), accepted=sum(accepted(row) for row in group),
                    metric_runs=len(costs), unavailable_metric_runs=len(group) - len(costs),
                    identities=sorted({(row.get("actual_class", "未记录"), row.get("name", "未记录"),
                                        row.get("source", "未记录")) for row in group}),
                    failures=[dict(scenario=row["scenario"], stop_reason=row.get("stop_reason", "未记录"),
                                   error=row.get("error") or "acceptance_failed", metrics_available=measured(row))
                              for row in group if not accepted(row)],
                    comparison=paired(group, reference))
        if costs:
            phases = sorted({name for row in costs for name in row.get("stage_costs", {})})
            triggers = Counter()
            for row in costs:
                triggers.update(trigger_counts(row.get("diagnostics", {})))
            item.update(mean_T_per_N=statistics.mean(row["T_per_N"] for row in costs),
                        mean_T=statistics.mean(row["virtual_time_s"] for row in costs),
                        weighted_T_per_N=sum(row["virtual_time_s"] for row in costs) / sum(row["scenario"]["N"] for row in costs),
                        p95_T_per_N=p95([row["T_per_N"] for row in costs]),
                        p95_T=p95([row["virtual_time_s"] for row in costs]),
                        worst_T_per_N=max(row["T_per_N"] for row in costs),
                        by_N={str(n):statistics.mean(row["T_per_N"] for row in costs if row["scenario"]["N"] == n)
                              for n in sorted({row["scenario"]["N"] for row in costs})},
                        mean_distance_m=statistics.mean(row["distance_m"] for row in costs),
                        mean_measure_count=statistics.mean(row["measure_count"] for row in costs),
                        mean_clear_fail_count=statistics.mean(row["clear_fail_count"] for row in costs),
                        mean_costs={key:statistics.mean(row["time_breakdown"][key] for row in costs) for key in COST_KEYS},
                        phases={phase:{key:sum(row.get("stage_costs", {}).get(phase, {}).get(key, 0) for row in costs) / len(costs)
                                       for key in COST_KEYS} for phase in phases},
                        triggers=dict(sorted(triggers.items())))
        result[variant] = item
    return result


def load_label(directory):
    report_path, manifest_path = directory / "report.json", directory / "manifest.json"
    if not report_path.exists() or not manifest_path.exists():
        return dict(label=directory.name, complete=False, reason="completed_report_not_present")
    report, manifest = read_json(report_path), read_json(manifest_path)
    expected = {(variant, json.dumps(scenario, sort_keys=True, separators=(",", ":")))
                for variant in manifest["variants"] for scenario in manifest["scenarios"]}
    records = report["records"]
    if len(records) != len({row_key(row) for row in records}):
        raise ValueError(f"Duplicate scenario/variant rows in {directory.name}")
    complete = (report.get("status") == "complete" and {row_key(row) for row in records} == expected
                and report.get("expected_runs") == len(expected) and report.get("observed_runs") == len(expected))
    if report.get("manifest", {}).get("code_sha256") != manifest.get("code_sha256"):
        raise ValueError(f"Manifest mismatch in {directory.name}")
    # progress.jsonl is the raw completed-row stream, independent of the final
    # summary cache.  Compare authoritative scalar outcomes, then recompute all
    # report statistics from these raw rows, including failed observations.
    progress = directory / "progress.jsonl"
    if progress.exists():
        raw = [json.loads(line) for line in progress.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(raw) != len({row_key(row) for row in raw}) or {row_key(row) for row in raw} != {row_key(row) for row in records}:
            raise ValueError(f"Raw-row population mismatch in {directory.name}")
        indexed = {row_key(row): row for row in raw}
        for row in records:
            other = indexed[row_key(row)]
            for key in ("full_clear", "normal_stop", "accepted_run", "virtual_time_s", "T_per_N",
                        "time_breakdown", "distance_m", "measure_count", "clear_fail_count", "actual_class", "source"):
                if row.get(key) != other.get(key):
                    raise ValueError(f"Raw-row {key} mismatch in {directory.name}")
        records = raw
    return dict(label=directory.name, stage=manifest["stage"], complete=complete,
                manifest=manifest, rows=records, summary=summarize(records),
                report_path=str(report_path), report_sha256=digest(report_path),
                manifest_sha256=digest(manifest_path), expected_runs=len(expected), observed_runs=len(records))


def source_fingerprint(label, variant):
    manifest = label["manifest"]
    source = Path(label["report_path"]).parent / "source"
    source_name = SOURCE_NAMES[variant]
    pending = [source_name, "robot_iter.py", "mock_simulator_p4.py", "route_round2_experiment.py"]
    pending.extend(manifest.get("dynamic_dependency_sha256", {}))
    hashes = manifest["code_sha256"]
    result = {}
    while pending:
        name = pending.pop()
        if name in result:
            continue
        path = source / name
        if name not in hashes or not path.exists() or digest(path) != hashes[name]:
            raise ValueError(f"Frozen source/hash missing or changed: {label['label']}/{name}")
        result[name] = hashes[name]
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
            for module in modules:
                if module:
                    local = module.split(".")[0] + ".py"
                    if local in hashes:
                        pending.append(local)
    return dict(sorted(result.items()))


def deployment_record(selection):
    path = ROOT / "tools" / "p4_practice_deployment.json"
    if not path.exists():
        return {"status": "not_present", "file": str(path)}
    record = read_json(path)
    source = Path(record.get("source", ""))
    source = source if source.is_absolute() else ROOT / source
    expected = record.get("sha256")
    actual = digest(source) if source.is_file() else None
    matched = bool(expected and actual == expected)
    return dict(status="hash_matches_current_source" if matched else "hash_mismatch_or_source_missing",
                file=str(path), updated_at=record.get("updated_at"), actual_class=record.get("actual_class"),
                name=record.get("name"), source=str(source), recorded_sha256=expected, current_sha256=actual,
                source_hash_matches=matched,
                matches_recommendation=matched and record.get("actual_class") == selection["selected_class"]
                                       and actual == selection["selected_sha256"],
                formal_entry=record.get("formal_entry", "未记录"),
                interpretation="verified metadata only; this report does not start a simulator or deploy code")


def choose(labels, confirmation_label, boundary_label):
    final = [labels.get(confirmation_label), labels.get(boundary_label)]
    ready = all(label and label.get("complete") for label in final)
    if ready:
        ready = (final[0]["stage"] == "confirmation" and len(final[0]["manifest"]["scenarios"]) == 56
                 and final[1]["stage"] == "boundary" and len(final[1]["manifest"]["scenarios"]) == 112
                 and all(set(FINAL_VARIANTS) <= set(label["manifest"]["variants"]) for label in final))
    if not ready:
        raise RuntimeError("Final confirmation01/boundary01 evidence is not complete; final outputs were not written")
    rows = [row for label in final for row in label["rows"]]
    combined = summarize(rows)
    eligibility = {}
    fingerprints = {}
    for variant in FINAL_VARIANTS:
        prints = [source_fingerprint(label, variant) for label in final]
        fingerprints[variant] = prints[0]
        equal = prints[0] == prints[1]
        local_match = all((HERE / name).is_file() and digest(HERE / name) == sha for name, sha in prints[0].items())
        stats = combined[variant]
        eligibility[variant] = dict(all_runs_accepted=stats["accepted"] == 168,
                                    all_metrics_available=stats["metric_runs"] == 168,
                                    frozen_code_equal_across_final_stages=equal,
                                    current_dependency_hashes_match=local_match)
        eligibility[variant]["eligible"] = all(eligibility[variant].values())
    eligible = [name for name in FINAL_VARIANTS if eligibility[name]["eligible"]]
    reference_mean = combined[REFERENCE].get("mean_T_per_N")
    selected = min(eligible, key=lambda name: combined[name]["mean_T_per_N"]) if eligible else REFERENCE
    if reference_mean is not None and combined[selected].get("mean_T_per_N", math.inf) >= reference_mean - 1e-9:
        selected = REFERENCE
    stats = combined[selected]
    source_name = SOURCE_NAMES[selected]
    source_hash = fingerprints[selected][source_name]
    complete = ready and all(eligibility[v]["all_metrics_available"] for v in FINAL_VARIANTS)
    selection = dict(selected_variant=selected, selected_class=selected,
                     selected_source=str(HERE / source_name), selected_sha256=source_hash,
                     evidence_complete=complete,
                     combined_mean_T_per_N=stats.get("mean_T_per_N"),
                     combined_reference_mean_T_per_N=reference_mean,
                     overall_improvement_percent=stats["comparison"].get("improvement_percent"),
                     all_runs_accepted=eligibility[selected]["all_runs_accepted"],
                     generated_at=datetime.now(timezone.utc).isoformat(),
                     comparison_reference=REFERENCE, final_labels=[confirmation_label, boundary_label],
                     final_scenarios_per_variant=168, development_excluded_from_combined=True,
                     selection_rule="All 168 final scenarios must fully clear and stop normally; among eligible unchanged candidates choose lowest all-run mean T/N; retain HuntP4 if no overall improvement",
                     deployment_action="none; integration is a separate recorded action",
                     goal_300_400_s_per_source_achieved=False,
                     goal_status="This round is closed at the user's request; 300-400 s/source was not achieved",
                     eligibility=eligibility, selected_dependency_sha256=fingerprints[selected],
                     validation_source_fingerprints=fingerprints, combined_summary=combined,
                     verification_record=VERIFICATION_RECORD,
                     label_evidence={name:dict(stage=value.get("stage"), complete=value["complete"],
                                              report_sha256=value.get("report_sha256"),
                                              manifest_sha256=value.get("manifest_sha256"),
                                              summary=value.get("summary", {})) for name, value in labels.items()})
    selection["integration_record"] = deployment_record(selection)
    return selection


def fmt(value, digits=2):
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) and math.isfinite(value) else "未记录"


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(output)


def summary_tables(summary):
    lines = [table(["策略", "全清", "正常停止", "验收", "成本样本", "均值T/N", "均值T", "移动米", "检测", "失败清除", "P95 T/N", "P95 T", "最差配对退步"],
                   [[name, f"{item['full_clear']}/{item['runs']}", f"{item['normal_stop']}/{item['runs']}",
                     f"{item['accepted']}/{item['runs']}", f"{item['metric_runs']}/{item['runs']}",
                     fmt(item.get("mean_T_per_N")), fmt(item.get("mean_T")), fmt(item.get("mean_distance_m")),
                     fmt(item.get("mean_measure_count")), fmt(item.get("mean_clear_fail_count")),
                     fmt(item.get("p95_T_per_N")), fmt(item.get("p95_T")),
                     fmt(item["comparison"].get("worst_regression_percent")) + "%"] for name, item in summary.items()]),
             "", "逐N平均T/N（秒/源）：", "",
             table(["策略"] + [str(n) for n in range(10, 17)],
                   [[name] + [fmt(item.get("by_N", {}).get(str(n))) for n in range(10, 17)] for name, item in summary.items()]),
             "", "四项成本均值（秒/场）：", "",
             table(["策略", "移动", "换频道", "检测", "清除（含成功与失败）"],
                   [[name] + [fmt(item.get("mean_costs", {}).get(key)) for key in COST_KEYS] for name, item in summary.items()])]
    return "\n".join(lines)


def detailed_tables(summary):
    phases = [[name, phase] + [fmt(costs[key]) for key in COST_KEYS] + [fmt(sum(costs.values()))]
              for name, item in summary.items() for phase, costs in item.get("phases", {}).items()]
    triggers = [[name, trigger, fmt(count, 0)] for name, item in summary.items() for trigger, count in item.get("triggers", {}).items()]
    lines = ["阶段成本均值（秒/场；未触发阶段对该场计0）：", "",
             table(["策略", "阶段", "移动", "换频道", "检测", "清除", "合计"], phases),
             "", "实际触发次数（该集合累计；嵌套规划器保留独立前缀）：", "",
             table(["策略", "触发项", "次数"], triggers) if triggers else "无已记录触发项。"]
    return "\n".join(lines)


def adverse_tables(summary):
    failures, regressions = [], []
    for name, item in summary.items():
        for failure in item["failures"]:
            scenario = failure["scenario"]
            failures.append([name, scenario["seed"], scenario["N"], scenario["dir_frac"], scenario["error_mode"],
                             scenario["reception_range"], failure["stop_reason"], failure["error"]])
        for regression in item["comparison"]["regressions"]:
            scenario = regression["scenario"]
            regressions.append([name, scenario["seed"], scenario["N"], scenario["reception_range"],
                                fmt(100 * regression["regression_fraction"]) + "%", fmt(regression["delta_T_s"]),
                                regression["candidate_accepted"], regression["reference_accepted"]])
    return "\n".join(["验收失败（全部保留）：", "",
                      table(["策略", "seed", "N", "定向比例", "误差", "半径", "停止原因", "错误"], failures) if failures else "本集合无验收失败。",
                      "", "相对HuntP4的全部耗时退步场景：", "",
                      table(["策略", "seed", "N", "半径", "退步", "增加秒", "候选验收", "Hunt验收"], regressions) if regressions else "无已测配对退步。"])


def render(labels, selection):
    lines = ["# 第四问路线改进第2轮收尾报告", "",
             f"推荐 `{selection['selected_variant']}`；最终新确认56场＋边界112场合计，平均T/N为 **{fmt(selection['combined_mean_T_per_N'])}秒/源**，"
             f"相对HuntP4整体改善 **{fmt(selection['overall_improvement_percent'])}%**。", "",
             "**本轮按用户要求收尾，未达到300–400秒/源。报告生成器不部署、不启动演练或正式模拟器。**", "",
             "统计口径：全清与正常停止同时满足才验收；step_limit不验收。成本均值包括所有有成本记录的失败场景；缺失成本明确计为未记录，不补零。"
             "T/N按场均值，N使用评测场景的实际源数；该信息只供事后评测，不提供给策略。P95采用上取整最近秩。最差退步按同场总T相对HuntP4计算。", "",
             "开发轮仅用于修错和固定参数，逐轮保留全部失败与退步；不混入最终168场均值。确认与边界冻结的策略及依赖哈希必须一致，不能看确认结果后调参再称独立验证。", "",
             "## 最终168场配对比较", "", summary_tables(selection["combined_summary"]), "",
             detailed_tables(selection["combined_summary"]), "", adverse_tables(selection["combined_summary"]), ""]
    reference_cost = selection["combined_summary"][REFERENCE].get("mean_costs", {})
    for variant, item in selection["combined_summary"].items():
        if variant == REFERENCE or not item.get("mean_costs") or not reference_cost:
            continue
        changes = [item["mean_costs"][key] - reference_cost[key] for key in COST_KEYS]
        lines.extend([f"`{variant}` 相对HuntP4的每场成本变化（候选减基线）：移动 {changes[0]:+.2f}秒、"
                      f"换频道 {changes[1]:+.2f}秒、检测 {changes[2]:+.2f}秒、清除 {changes[3]:+.2f}秒。"
                      f"其平均T/N整体改善为 {fmt(item['comparison'].get('improvement_percent'))}%；这些差值与上述阶段成本及实际触发次数共同说明收益来源。", ""])
    stage_order = {"development": 0, "confirmation": 1, "boundary": 2}
    for name, label in sorted(labels.items(), key=lambda pair:(stage_order.get(pair[1].get("stage"), 3), pair[0])):
        lines.extend([f"## {name}", ""])
        if not label["complete"]:
            lines.extend(["该标签未完成，未进入统计和选型。原有证据保持不动。", ""])
            continue
        lines.extend([f"阶段 `{label['stage']}`；已记录{label['observed_runs']}/{label['expected_runs']}场策略运行。"
                      f"[完整报告](route_round2/{name}/report.json) · [冻结清单](route_round2/{name}/manifest.json) · [原始动作](route_round2/{name}/runs/)", "",
                      summary_tables(label["summary"]), "", detailed_tables(label["summary"]), "", adverse_tables(label["summary"]), "",
                      "实际加载身份：", "",
                      table(["variant", "实际类", "运行名", "源码", "该轮源码SHA256"],
                            [[variant, actual, run_name, source, label["manifest"]["code_sha256"].get(Path(source).name, "未记录")]
                             for variant, item in label["summary"].items() for actual, run_name, source in item["identities"]]), ""])
    lines.extend(["## 单测与研究保留", "",
                  "整合线程提供的本轮综合验证记录：113项通过，用时17.62秒。该测试结论独立于下列离线模拟统计，报告生成没有重新运行测试。", "",
                  "```powershell", VERIFICATION_RECORD["command"], "```", "",
                  "`discovery_joint_prune.py` / `test_discovery_joint_prune.py` 单独9项通过，尚未接入生产策略，仅作研究保留；不把未接入helper的单测当成当前策略的收益证据。", ""])
    research_rows = []
    for filename in ("geometry_search_extra_results.json", "discovery_design_round2_results.json", "discovery_star_round2_results.json"):
        path = HERE / filename
        if path.exists():
            data = read_json(path)
            counts = Counter(row["status"] for row in data["rows"])
            research_rows.append([filename, len(data["rows"]), counts["continuously_certified"],
                                  counts["rejected_by_strict_counterexample"], counts["unproved_within_finite_budget"]])
    if research_rows:
        lines.extend(["固定几何研究的失败与未证结果全部保留，不接入无连续证明的构造：", "",
                      table(["证据文件", "构造数", "连续通过", "严格盲区反例", "有限预算未证"], research_rows), ""])
    lines.extend(["## 选型与接入记录", "",
                  f"选择 `{selection['selected_class']}`，源码 `{Path(selection['selected_source']).name}`，SHA256 `{selection['selected_sha256']}`。", "",
                  "选型仅依照本轮最终168场的完整验收、可用成本及整体平均T/N；不引入事后单场门槛。若候选没有整体改善，则保留HuntP4。", "",
                  table(["策略", "168场全验收", "全部成本可用", "最终两阶段同代码", "当前依赖匹配", "可选"],
                        [[name] + [item[key] for key in ("all_runs_accepted", "all_metrics_available", "frozen_code_equal_across_final_stages",
                                                         "current_dependency_hashes_match", "eligible")] for name, item in selection["eligibility"].items()]), ""])
    deployment = selection["integration_record"]
    if deployment.get("source_hash_matches"):
        lines.append(f"单独读取的 `tools/p4_practice_deployment.json` 记录 `{deployment.get('name')}` / `{deployment.get('actual_class')}`，"
                     f"其SHA256与当前源码匹配；是否与本报告推荐一致：`{deployment['matches_recommendation']}`。正式入口记录为 `{deployment.get('formal_entry')}`。")
    else:
        lines.append(f"接入记录状态 `{deployment['status']}`；未将该记录当作当前已接入的证明。")
    lines.extend(["", "接入记录是带源码哈希的元数据，本报告没有因此宣称新一局模拟器已经运行。"
                  "基线和所有开发/确认/边界原始结果均保留；策略替换由独立接入步骤完成。", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmation-label", default="confirmation01")
    parser.add_argument("--boundary-label", default="boundary01")
    args = parser.parse_args()
    labels = {directory.name:load_label(directory) for directory in sorted(EXPERIMENT.iterdir()) if directory.is_dir()}
    selection = choose(labels, args.confirmation_label, args.boundary_label)
    report = render(labels, selection)
    report_path, selection_path = HERE / "ROUTE_ROUND2_REPORT.md", EXPERIMENT / "selection.json"
    for path, data in ((report_path, report), (selection_path, json.dumps(selection, ensure_ascii=False, indent=2, allow_nan=False))):
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(data, encoding="utf-8")
        temporary.replace(path)
    print(json.dumps({key:selection[key] for key in ("selected_variant", "selected_class", "selected_source", "selected_sha256",
                                                     "evidence_complete", "combined_mean_T_per_N", "combined_reference_mean_T_per_N",
                                                     "overall_improvement_percent", "all_runs_accepted")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
