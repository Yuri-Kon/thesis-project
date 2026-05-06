from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from src.infra.w12_vertical_experiment import (
    DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    aggregate_group_metrics,
    compute_increment_deltas,
    load_json,
    now_iso,
    write_csv,
    write_json,
    write_jsonl,
)
from src.infra.w16_issue221_experiment_matrix import (
    DEFAULT_ISSUE221_KG_PATH,
    evaluate_issue221_run_manifest,
)

__all__ = [
    "DEFAULT_ISSUE222_KG_PATH",
    "analyze_issue222_results",
    "load_and_analyze_issue222_results",
]

DEFAULT_ISSUE222_KG_PATH = DEFAULT_ISSUE221_KG_PATH
_CORE_GROUP_ORDER = (
    "static_top1",
    "fixed_threshold_gate",
    "dynamic_no_belief_state",
    "lite_belief_state",
)
_CHART_METRICS = (
    ("success", "success_rate"),
    ("success", "first_pass_success_rate"),
    ("cost", "duration_ms_mean"),
    ("cost", "high_cost_call_mean"),
    ("cost", "high_cost_failure_mean"),
    ("recovery", "patch_events_mean"),
    ("recovery", "replan_events_mean"),
    ("recovery", "suffix_replan_events_mean"),
    ("recovery", "patch_minimality_hit_rate"),
    ("recovery", "suffix_replan_prefix_preservation_rate"),
)


def analyze_issue222_results(
    *,
    manifest: Mapping[str, Any],
    output_dir: Path,
    kg_path: Path = DEFAULT_ISSUE222_KG_PATH,
    bootstrap_iterations: int = 10000,
    seed: int = 20260417,
) -> dict[str, Any]:
    """生成 issue222 的总体与难度分层聚合分析。

    Args:
        manifest: issue221 运行清单。
        output_dir: issue222 分析产物目录。
        kg_path: Tool KG 路径。
        bootstrap_iterations: bootstrap 轮数。
        seed: 随机种子。

    Returns:
        包含 run-level、总体、分层、恢复复杂度和图表行的分析结果。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    source_eval_dir = output_dir / "source_issue221_evaluation"
    source_result = evaluate_issue221_run_manifest(
        manifest=manifest,
        output_dir=source_eval_dir,
        kg_path=kg_path,
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
    )
    run_level_results = list(source_result["run_level_results"])
    group_order = _resolve_group_order(manifest)
    requirement2_map = _resolve_requirement2_map(manifest)
    thresholds = _numeric_thresholds(manifest.get("offline_thresholds"))

    overall = aggregate_group_metrics(
        run_level_results,
        group_order=group_order,
        iterations=max(100, bootstrap_iterations),
        seed=seed + 101,
        thresholds=thresholds,
        requirement2_capability_map=requirement2_map,
    )
    overall_rows = [
        _summary_projection(row, slice_type="overall", slice_value="all")
        for row in overall["summary_rows"]
    ]

    stratified_rows: list[dict[str, Any]] = []
    for offset, difficulty in enumerate(_ordered_values(run_level_results, "difficulty")):
        slice_runs = [
            row for row in run_level_results if str(row.get("difficulty") or "unknown") == difficulty
        ]
        aggregated = aggregate_group_metrics(
            slice_runs,
            group_order=group_order,
            iterations=max(100, bootstrap_iterations),
            seed=seed + 201 + offset,
            thresholds=thresholds,
            requirement2_capability_map=requirement2_map,
        )
        stratified_rows.extend(
            _summary_projection(row, slice_type="difficulty", slice_value=difficulty)
            for row in aggregated["summary_rows"]
        )

    recovery_rows = _build_recovery_complexity_rows(
        overall_rows=overall_rows,
        stratified_rows=stratified_rows,
    )
    chart_rows = _build_chart_summary_rows(overall_rows + stratified_rows)
    delta_rows = _build_issue222_delta_rows(
        run_level_results=run_level_results,
        group_order=group_order,
        iterations=max(100, bootstrap_iterations),
        seed=seed + 401,
    )
    metric_definitions = _metric_definitions()
    statistical_summary = {
        "generated_at": now_iso(),
        "issue_id": 222,
        "source_issue_id": int(manifest.get("issue_id") or 221),
        "run_count": len(run_level_results),
        "group_order": group_order,
        "difficulty_values": _ordered_values(run_level_results, "difficulty"),
        "source_run_manifest_path": manifest.get("run_manifest_path"),
        "source_evaluation_dir": str(source_eval_dir),
        "metric_dimensions": ["success", "cost", "recovery"],
        "delta_metrics": sorted({row["metric"] for row in delta_rows}),
    }

    write_jsonl(output_dir / "run_level_results.jsonl", run_level_results)
    write_json(output_dir / "run_level_results.json", run_level_results)
    write_csv(output_dir / "overall_metrics.csv", overall_rows, _analysis_fieldnames())
    write_json(output_dir / "overall_metrics.json", overall_rows)
    write_csv(
        output_dir / "difficulty_stratified_metrics.csv",
        stratified_rows,
        _analysis_fieldnames(),
    )
    write_json(output_dir / "difficulty_stratified_metrics.json", stratified_rows)
    write_csv(
        output_dir / "recovery_complexity_high_cost.csv",
        recovery_rows,
        [
            "slice_type",
            "slice_value",
            "group_id",
            "runs",
            "patch_events_mean",
            "replan_events_mean",
            "suffix_replan_events_mean",
            "recovery_event_mean",
            "patch_minimality_hit_rate",
            "suffix_replan_prefix_preservation_rate",
            "high_cost_call_mean",
            "high_cost_failure_mean",
        ],
    )
    write_csv(
        output_dir / "chart_summary_rows.csv",
        chart_rows,
        ["slice_type", "slice_value", "group_id", "metric_dimension", "metric", "value"],
    )
    write_json(output_dir / "chart_summary_rows.json", chart_rows)
    write_csv(
        output_dir / "statistical_deltas.csv",
        delta_rows,
        [
            "slice_type",
            "slice_value",
            "from_group",
            "to_group",
            "metric",
            "delta",
            "ci_low",
            "ci_high",
            "sample_size",
            "pairing",
        ],
    )
    write_json(output_dir / "metric_definitions.json", metric_definitions)
    write_csv(
        output_dir / "metric_definitions.csv",
        metric_definitions,
        ["metric", "dimension", "definition", "source", "table"],
    )
    write_json(output_dir / "statistical_summary.json", statistical_summary)
    (output_dir / "issue222_analysis_report.md").write_text(
        _build_markdown_report(
            generated_at=statistical_summary["generated_at"],
            manifest=manifest,
            overall_rows=overall_rows,
            stratified_rows=stratified_rows,
            recovery_rows=recovery_rows,
            delta_rows=delta_rows,
        ),
        encoding="utf-8",
    )

    return {
        "run_level_results": run_level_results,
        "overall_rows": overall_rows,
        "stratified_rows": stratified_rows,
        "recovery_rows": recovery_rows,
        "chart_rows": chart_rows,
        "delta_rows": delta_rows,
        "metric_definitions": metric_definitions,
        "statistical_summary": statistical_summary,
    }


def _resolve_group_order(manifest: Mapping[str, Any]) -> list[str]:
    groups = [
        str(group.get("id"))
        for group in manifest.get("groups", [])
        if isinstance(group, dict) and isinstance(group.get("id"), str)
    ]
    if groups:
        return groups
    return list(_CORE_GROUP_ORDER)


def _resolve_requirement2_map(manifest: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = manifest.get("requirement2_capability_map")
    if not isinstance(raw, dict):
        return dict(DEFAULT_REQUIREMENT2_CAPABILITY_MAP)
    return {
        str(key): [str(item) for item in value if isinstance(item, str)]
        for key, value in raw.items()
        if isinstance(value, list)
    }


def _numeric_thresholds(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(raw)
        for key, raw in value.items()
        if isinstance(raw, (int, float)) and not isinstance(raw, bool)
    }


def _ordered_values(rows: Iterable[Mapping[str, Any]], field: str) -> list[str]:
    preferred = ["easy", "medium", "hard", "unknown"]
    values = {str(row.get(field) or "unknown") for row in rows}
    ordered = [value for value in preferred if value in values]
    ordered.extend(sorted(values - set(ordered)))
    return ordered


def _summary_projection(
    row: Mapping[str, Any],
    *,
    slice_type: str,
    slice_value: str,
) -> dict[str, Any]:
    projected = {
        "slice_type": slice_type,
        "slice_value": slice_value,
        "group_id": row.get("group_id"),
        "runs": row.get("runs"),
        "success_rate": row.get("success_rate"),
        "success_ci_low": row.get("success_ci_low"),
        "success_ci_high": row.get("success_ci_high"),
        "first_pass_success_rate": row.get("first_pass_success_rate"),
        "schema_valid_rate": row.get("schema_valid_rate"),
        "executable_plan_rate": row.get("executable_plan_rate"),
        "waiting_chain_complete_rate": row.get("waiting_chain_complete_rate"),
        "failure_traceable_rate": row.get("failure_traceable_rate"),
        "duration_ms_mean": row.get("duration_ms_mean"),
        "duration_ms_ci_low": row.get("duration_ms_ci_low"),
        "duration_ms_ci_high": row.get("duration_ms_ci_high"),
        "high_cost_call_mean": row.get("high_cost_call_mean"),
        "high_cost_call_ci_low": row.get("high_cost_call_ci_low"),
        "high_cost_call_ci_high": row.get("high_cost_call_ci_high"),
        "high_cost_failure_mean": row.get("high_cost_failure_mean"),
        "patch_events_mean": row.get("patch_events_mean"),
        "replan_events_mean": row.get("replan_events_mean"),
        "suffix_replan_events_mean": row.get("suffix_replan_events_mean"),
        "patch_minimality_hit_rate": row.get("patch_minimality_hit_rate"),
        "suffix_replan_prefix_preservation_rate": row.get(
            "suffix_replan_prefix_preservation_rate"
        ),
        "action_continue_mean": row.get("action_continue_mean"),
        "action_patch_local_mean": row.get("action_patch_local_mean"),
        "action_suffix_replan_mean": row.get("action_suffix_replan_mean"),
        "action_stop_mean": row.get("action_stop_mean"),
        "shadow_action_agreement_rate": row.get("shadow_action_agreement_rate"),
    }
    projected["recovery_event_mean"] = _sum_numeric(
        projected.get("patch_events_mean"),
        projected.get("replan_events_mean"),
        projected.get("suffix_replan_events_mean"),
    )
    return projected


def _sum_numeric(*values: Any) -> float | None:
    total = 0.0
    observed = False
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += float(value)
            observed = True
    return total if observed else None


def _build_recovery_complexity_rows(
    *,
    overall_rows: list[dict[str, Any]],
    stratified_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "slice_type": row["slice_type"],
            "slice_value": row["slice_value"],
            "group_id": row["group_id"],
            "runs": row["runs"],
            "patch_events_mean": row["patch_events_mean"],
            "replan_events_mean": row["replan_events_mean"],
            "suffix_replan_events_mean": row["suffix_replan_events_mean"],
            "recovery_event_mean": row["recovery_event_mean"],
            "patch_minimality_hit_rate": row["patch_minimality_hit_rate"],
            "suffix_replan_prefix_preservation_rate": row[
                "suffix_replan_prefix_preservation_rate"
            ],
            "high_cost_call_mean": row["high_cost_call_mean"],
            "high_cost_failure_mean": row["high_cost_failure_mean"],
        }
        for row in [*overall_rows, *stratified_rows]
    ]


def _build_chart_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        for dimension, metric in _CHART_METRICS:
            chart_rows.append(
                {
                    "slice_type": row["slice_type"],
                    "slice_value": row["slice_value"],
                    "group_id": row["group_id"],
                    "metric_dimension": dimension,
                    "metric": metric,
                    "value": row.get(metric),
                }
            )
    return chart_rows


def _build_issue222_delta_rows(
    *,
    run_level_results: list[dict[str, Any]],
    group_order: list[str],
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    metric_keys = [
        "success",
        "first_pass_success",
        "duration_ms",
        "high_cost_call_count",
        "patch_event_count",
        "replan_event_count",
        "suffix_replan_event_count",
    ]
    rows: list[dict[str, Any]] = []
    slices = [("overall", "all", run_level_results)]
    for difficulty in _ordered_values(run_level_results, "difficulty"):
        slices.append(
            (
                "difficulty",
                difficulty,
                [
                    row
                    for row in run_level_results
                    if str(row.get("difficulty") or "unknown") == difficulty
                ],
            )
        )

    counter = 0
    for slice_type, slice_value, slice_runs in slices:
        for metric in metric_keys:
            for delta in compute_increment_deltas(
                slice_runs,
                group_order=group_order,
                metric_key=metric,
                iterations=iterations,
                seed=seed + counter,
            ):
                enriched = dict(delta)
                enriched["slice_type"] = slice_type
                enriched["slice_value"] = slice_value
                rows.append(enriched)
            counter += 1
    return rows


def _analysis_fieldnames() -> list[str]:
    return [
        "slice_type",
        "slice_value",
        "group_id",
        "runs",
        "success_rate",
        "success_ci_low",
        "success_ci_high",
        "first_pass_success_rate",
        "schema_valid_rate",
        "executable_plan_rate",
        "waiting_chain_complete_rate",
        "failure_traceable_rate",
        "duration_ms_mean",
        "duration_ms_ci_low",
        "duration_ms_ci_high",
        "high_cost_call_mean",
        "high_cost_call_ci_low",
        "high_cost_call_ci_high",
        "high_cost_failure_mean",
        "patch_events_mean",
        "replan_events_mean",
        "suffix_replan_events_mean",
        "recovery_event_mean",
        "patch_minimality_hit_rate",
        "suffix_replan_prefix_preservation_rate",
        "action_continue_mean",
        "action_patch_local_mean",
        "action_suffix_replan_mean",
        "action_stop_mean",
        "shadow_action_agreement_rate",
    ]


def _metric_definitions() -> list[dict[str, str]]:
    return [
        {
            "metric": "success_rate",
            "dimension": "success",
            "definition": "DONE runs divided by all runs in the slice.",
            "source": "extract_run_metrics.final_status from event log or manifest status_external",
            "table": "overall_metrics.csv, difficulty_stratified_metrics.csv",
        },
        {
            "metric": "first_pass_success_rate",
            "dimension": "success",
            "definition": "DONE runs without patch, replan, or waiting entry.",
            "source": "extract_run_metrics patch/replan/waiting counters",
            "table": "overall_metrics.csv, difficulty_stratified_metrics.csv",
        },
        {
            "metric": "duration_ms_mean",
            "dimension": "cost",
            "definition": "Mean end-to-end run duration in milliseconds.",
            "source": "manifest duration_ms or started_at/finished_at/event timestamps",
            "table": "overall_metrics.csv, difficulty_stratified_metrics.csv",
        },
        {
            "metric": "high_cost_call_mean",
            "dimension": "cost",
            "definition": "Mean matched high-cost tool calls per run.",
            "source": "STEP_FINISHED/STEP_FAILED rows matched against high_cost_rules",
            "table": "overall_metrics.csv, recovery_complexity_high_cost.csv",
        },
        {
            "metric": "patch_events_mean",
            "dimension": "recovery",
            "definition": "Mean parameter/tool/structure patch events per run.",
            "source": "PARAM_TWEAK, REPLACE_TOOL, STRUCTURE_PATCH event rows",
            "table": "overall_metrics.csv, recovery_complexity_high_cost.csv",
        },
        {
            "metric": "replan_events_mean",
            "dimension": "recovery",
            "definition": "Mean replanning transitions per run.",
            "source": "TASK_STATUS_CHANGED rows whose to_status is REPLANNING",
            "table": "overall_metrics.csv, recovery_complexity_high_cost.csv",
        },
        {
            "metric": "suffix_replan_prefix_preservation_rate",
            "dimension": "recovery",
            "definition": "Share of suffix replan samples that preserve the successful prefix.",
            "source": "data.recovery.prefix_preserved samples",
            "table": "overall_metrics.csv, recovery_complexity_high_cost.csv",
        },
    ]


def _build_markdown_report(
    *,
    generated_at: str,
    manifest: Mapping[str, Any],
    overall_rows: list[dict[str, Any]],
    stratified_rows: list[dict[str, Any]],
    recovery_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Issue #222 Integration Analysis",
        "",
        f"- generated_at: `{generated_at}`",
        f"- source_issue: `#{int(manifest.get('issue_id') or 221)}`",
        f"- source_run_manifest: `{manifest.get('run_manifest_path') or 'UNKNOWN'}`",
        "- comparison_scope: `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`",
        "",
        "## Overall Metrics",
        "",
        "| group | runs | success | first_pass | high_cost_mean | patch_mean | replan_mean | recovery_mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall_rows:
        lines.append(
            "| {group_id} | {runs} | {success:.4f} | {first_pass:.4f} | {high_cost:.4f} | {patch:.4f} | {replan:.4f} | {recovery:.4f} |".format(
                group_id=row.get("group_id"),
                runs=int(row.get("runs") or 0),
                success=float(row.get("success_rate") or 0.0),
                first_pass=float(row.get("first_pass_success_rate") or 0.0),
                high_cost=float(row.get("high_cost_call_mean") or 0.0),
                patch=float(row.get("patch_events_mean") or 0.0),
                replan=float(row.get("replan_events_mean") or 0.0),
                recovery=float(row.get("recovery_event_mean") or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Difficulty Stratification",
            "",
            "| difficulty | group | runs | success | high_cost_mean | recovery_mean |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in stratified_rows:
        lines.append(
            "| {difficulty} | {group_id} | {runs} | {success:.4f} | {high_cost:.4f} | {recovery:.4f} |".format(
                difficulty=row.get("slice_value"),
                group_id=row.get("group_id"),
                runs=int(row.get("runs") or 0),
                success=float(row.get("success_rate") or 0.0),
                high_cost=float(row.get("high_cost_call_mean") or 0.0),
                recovery=float(row.get("recovery_event_mean") or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Output Contract",
            "",
            "- `overall_metrics.csv`: overall success/cost/recovery summary rows.",
            "- `difficulty_stratified_metrics.csv`: difficulty x group stratified summary rows.",
            "- `recovery_complexity_high_cost.csv`: patch/replan/prefix/high-cost focused rows.",
            "- `chart_summary_rows.csv`: long-form chart/table rows.",
            "- `metric_definitions.json`: metric definitions and source mappings.",
            "- `statistical_deltas.csv`: paired or unpaired bootstrap deltas for core metrics.",
            "",
            f"- recovery_rows: `{len(recovery_rows)}`",
            f"- delta_rows: `{len(delta_rows)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def load_and_analyze_issue222_results(
    *,
    run_manifest_path: Path,
    output_dir: Path,
    kg_path: Path = DEFAULT_ISSUE222_KG_PATH,
    bootstrap_iterations: int = 10000,
    seed: int = 20260417,
) -> dict[str, Any]:
    """从 run manifest 路径加载并执行 issue222 分析。"""

    return analyze_issue222_results(
        manifest=load_json(run_manifest_path),
        output_dir=output_dir,
        kg_path=kg_path,
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
    )
