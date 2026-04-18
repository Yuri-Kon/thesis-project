from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.infra.w12_vertical_experiment import (
    DEFAULT_OFFLINE_THRESHOLDS,
    DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    aggregate_group_metrics,
    build_markdown_report,
    compute_increment_deltas,
    deep_merge,
    extract_run_metrics,
    load_json,
    load_tool_capability_map,
    normalize_high_cost_rules,
    now_iso,
    stable_hash,
    write_csv,
    write_json,
    write_jsonl,
)

__all__ = [
    "DEFAULT_ISSUE221_CONFIG_PATH",
    "DEFAULT_ISSUE221_KG_PATH",
    "build_issue221_run_manifest",
    "evaluate_issue221_run_manifest",
    "load_issue221_selection",
]

DEFAULT_ISSUE221_CONFIG_PATH = Path(
    "configs/experiments/w16_issue221_experiment_matrix.json"
)
DEFAULT_ISSUE221_KG_PATH = Path("src/kg/protein_tool_kg.json")
DEFAULT_ISSUE221_OUTPUT_ROOT = Path("output/experiment/w16-expr-1")
DEFAULT_ISSUE221_BASELINE_FREEZE_CONFIG_PATH = Path(
    "configs/experiments/w13_issue209_baseline_freeze.json"
)
_EXPECTED_GROUP_IDS = (
    "static_top1",
    "fixed_threshold_gate",
    "dynamic_no_belief_state",
    "lite_belief_state",
)


def build_issue221_run_manifest(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    output_root: Path | None = None,
    run_id: str | None = None,
    repeats_override: int | None = None,
    max_runs: int | None = None,
    dry_run: bool = False,
    selection: set[tuple[str, str, int]] | None = None,
) -> tuple[dict[str, Any], Path]:
    """构建并可选执行 issue221 的四组统一实验矩阵。

    Args:
        config: issue221 实验配置。
        config_path: 配置文件路径，用于回链。
        output_root: 可选输出根目录覆盖。
        run_id: 可选运行批次 ID。
        repeats_override: 可选重复次数覆盖。
        max_runs: 可选最大运行数上限。
        dry_run: 是否只生成矩阵与清单而不真正执行。
        selection: 可选子集过滤，仅执行指定 `(group_id, task_key, replicate)`。

    Returns:
        二元组，分别为写出的 run manifest 与对应输出目录。
    """

    issue_id = int(config.get("issue_id") or 221)
    matrix = _resolve_issue221_matrix(config=config)
    resolved_output_root = (
        output_root
        or _path_from_value(config.get("output_root"))
        or DEFAULT_ISSUE221_OUTPUT_ROOT
    )
    resolved_output_root.mkdir(parents=True, exist_ok=True)
    resolved_run_id = run_id or f"w16e1-{datetime_now_tag()}-{_git_short_sha()}"
    run_dir = resolved_output_root / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_constraints = _dict_value(config.get("base_constraints"))
    base_metadata = _dict_value(config.get("base_metadata"))
    repeat_policy = _dict_value(config.get("repeat_policy"))
    offline_thresholds = _resolve_thresholds(config.get("offline_thresholds"))
    requirement2_capability_map = _resolve_requirement2_capability_map(
        config.get("requirement2_capability_map")
    )

    run_entries: list[dict[str, Any]] = []
    counter = 0
    for group in matrix["groups"]:
        group_id = group["id"]
        group_constraints = _dict_value(group.get("constraint_overrides"))
        group_runtime_policy = str(group.get("runtime_policy") or "lite_belief_state")
        for task in matrix["tasks"]:
            task_key = task["task_key"]
            repeat_count = (
                repeats_override
                if isinstance(repeats_override, int) and repeats_override > 0
                else _resolve_task_repeat_count(
                    task=task,
                    default_repeats=int(config.get("repeats") or 1),
                    repeat_policy=repeat_policy,
                )
            )
            for replicate in range(1, repeat_count + 1):
                if selection is not None and (group_id, task_key, replicate) not in selection:
                    continue
                if max_runs is not None and counter >= max_runs:
                    break

                merged_constraints = deep_merge(base_constraints, group_constraints)
                merged_constraints = deep_merge(
                    merged_constraints,
                    _dict_value(task.get("constraints")),
                )
                merged_constraints["runtime_policy"] = group_runtime_policy

                merged_metadata = deep_merge(base_metadata, _dict_value(task.get("metadata")))
                merged_metadata = deep_merge(
                    merged_metadata,
                    {
                        "issue_id": issue_id,
                        "experiment": "w16_issue221_matrix",
                        "group_id": group_id,
                        "group_label": group.get("label"),
                        "task_key": task_key,
                        "replicate": replicate,
                        "freeze_id": matrix["freeze_id"],
                        "task_set_version": matrix["task_set_version"],
                        "difficulty": task.get("difficulty"),
                        "budget_tier": task.get("budget_tier"),
                    },
                )

                logical_run_id = f"{resolved_run_id}_{group_id}_{task_key}_r{replicate:02d}"
                task_id = _sanitize_task_id(logical_run_id)
                run_config_path = run_dir / "run_configs" / f"{logical_run_id}.json"
                run_config_payload = {
                    "issue_id": issue_id,
                    "generated_at": now_iso(),
                    "run_id": logical_run_id,
                    "task_id": task_id,
                    "group": group,
                    "task": task,
                    "constraints": merged_constraints,
                    "metadata": merged_metadata,
                    "lineage": {
                        "freeze_id": matrix["freeze_id"],
                        "task_set_version": matrix["task_set_version"],
                        "difficulty_scheme_version": matrix["difficulty_scheme_version"],
                        "baseline_freeze_config_path": matrix["baseline_freeze"][
                            "config_path"
                        ],
                        "baseline_freeze_config_hash": matrix["baseline_freeze"][
                            "config_hash"
                        ],
                        "baseline_freeze_manifest_path": matrix["baseline_freeze"][
                            "manifest_path"
                        ],
                        "high_cost_rules_hash": stable_hash(matrix["high_cost_rules"]),
                    },
                }
                write_json(run_config_path, run_config_payload)

                started_at = now_iso()
                status_external = "DRY_RUN"
                status_internal = "DRY_RUN"
                report_path = ""
                pending_action_type = None
                execution_error = None

                if not dry_run:
                    status_external, status_internal, report_path, pending_action_type, execution_error = (
                        _execute_matrix_run(
                            task_id=task_id,
                            goal=str(task.get("goal") or "de_novo_design"),
                            constraints=merged_constraints,
                            metadata=merged_metadata,
                        )
                    )

                finished_at = now_iso()
                event_log_path = Path("data/logs") / f"{task_id}.jsonl"
                snapshot_path = Path("data/snapshots") / f"{task_id}.jsonl"

                run_entries.append(
                    {
                        "run_id": logical_run_id,
                        "task_id": task_id,
                        "task_key": task_key,
                        "group_id": group_id,
                        "group_label": group.get("label"),
                        "comparison_order": group.get("comparison_order"),
                        "replicate": replicate,
                        "attempt_number": 1,
                        "issue_id": issue_id,
                        "freeze_id": matrix["freeze_id"],
                        "task_set_version": matrix["task_set_version"],
                        "difficulty_scheme_version": matrix["difficulty_scheme_version"],
                        "difficulty": task.get("difficulty"),
                        "budget_tier": task.get("budget_tier"),
                        "runtime_policy": group_runtime_policy,
                        "goal": task.get("goal"),
                        "constraints_hash": stable_hash(merged_constraints),
                        "metadata_hash": stable_hash(merged_metadata),
                        "run_spec_hash": stable_hash(
                            {
                                "group_id": group_id,
                                "task_key": task_key,
                                "replicate": replicate,
                                "constraints": merged_constraints,
                            }
                        ),
                        "run_config_path": str(run_config_path),
                        "status_external": status_external,
                        "status_internal": status_internal,
                        "pending_action_type": pending_action_type,
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "event_log_path": str(event_log_path),
                        "snapshot_path": str(snapshot_path),
                        "report_path": report_path,
                        "execution_error": execution_error,
                        "high_cost_rules_hash": stable_hash(matrix["high_cost_rules"]),
                        "baseline_freeze_config_path": matrix["baseline_freeze"][
                            "config_path"
                        ],
                        "baseline_freeze_config_hash": matrix["baseline_freeze"][
                            "config_hash"
                        ],
                    }
                )
                counter += 1

            if max_runs is not None and counter >= max_runs:
                break
        if max_runs is not None and counter >= max_runs:
            break

    run_manifest_path = run_dir / "runs_manifest.json"
    manifest = {
        "issue_id": issue_id,
        "generated_at": now_iso(),
        "run_id": resolved_run_id,
        "config_path": str(config_path),
        "run_manifest_path": str(run_manifest_path),
        "config_hash": stable_hash(dict(config)),
        "description": config.get("description"),
        "freeze_id": matrix["freeze_id"],
        "task_set_version": matrix["task_set_version"],
        "difficulty_scheme_version": matrix["difficulty_scheme_version"],
        "baseline_freeze": matrix["baseline_freeze"],
        "metrics_contract": matrix["metrics_contract"],
        "high_cost_rules": matrix["high_cost_rules"],
        "dry_run": dry_run,
        "groups": matrix["groups"],
        "tasks": matrix["tasks"],
        "offline_thresholds": offline_thresholds,
        "requirement2_capability_map": requirement2_capability_map,
        "artifact_policy": _resolve_artifact_policy(config.get("artifact_policy")),
        "rerun_policy": _resolve_rerun_policy(config.get("rerun_policy")),
        "repeat_policy": repeat_policy,
        "selection_filter_applied": selection is not None,
        "runs": run_entries,
    }

    write_json(run_manifest_path, manifest)
    write_json(
        run_dir / "resolved_config_snapshot.json",
        {
            "config": dict(config),
            "resolved_matrix": matrix,
            "args": {
                "config_path": str(config_path),
                "output_root": str(resolved_output_root),
                "run_id": run_id,
                "repeats_override": repeats_override,
                "max_runs": max_runs,
                "dry_run": dry_run,
                "selection_applied": selection is not None,
            },
        },
    )
    write_jsonl(run_dir / "runs.jsonl", run_entries)
    write_csv(
        run_dir / "run_log_index.csv",
        run_entries,
        [
            "run_id",
            "task_id",
            "group_id",
            "replicate",
            "task_key",
            "difficulty",
            "budget_tier",
            "runtime_policy",
            "status_external",
            "status_internal",
            "started_at",
            "finished_at",
            "run_config_path",
            "event_log_path",
            "snapshot_path",
            "report_path",
            "freeze_id",
            "pending_action_type",
            "execution_error",
        ],
    )

    return manifest, run_dir


def evaluate_issue221_run_manifest(
    *,
    manifest: Mapping[str, Any],
    output_dir: Path,
    kg_path: Path = DEFAULT_ISSUE221_KG_PATH,
    bootstrap_iterations: int = 10000,
    seed: int = 20260416,
) -> dict[str, Any]:
    """评估 issue221 的 run manifest 并生成可追溯产物。

    Args:
        manifest: 由运行脚本写出的 run manifest。
        output_dir: 评估产物目录。
        kg_path: Tool KG 路径。
        bootstrap_iterations: bootstrap 轮数。
        seed: 随机种子。

    Returns:
        包含 run-level、group-level 与 rerun 计划的汇总字典。
    """

    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise ValueError("run manifest missing `runs` list")

    group_order = [
        str(group.get("id"))
        for group in manifest.get("groups", [])
        if isinstance(group, dict) and isinstance(group.get("id"), str)
    ]
    requirement2_capability_map = _resolve_requirement2_capability_map(
        manifest.get("requirement2_capability_map")
    )
    thresholds = _resolve_thresholds(manifest.get("offline_thresholds"))
    artifact_policy = _resolve_artifact_policy(manifest.get("artifact_policy"))
    rerun_policy = _resolve_rerun_policy(manifest.get("rerun_policy"))
    tool_capability_map = load_tool_capability_map(kg_path)

    run_level_results: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        metrics = extract_run_metrics(
            run,
            tool_capability_map=tool_capability_map,
            requirement2_capability_map=requirement2_capability_map,
            high_cost_rules=manifest.get("high_cost_rules"),
        )
        artifact_status = _evaluate_run_artifacts(
            run=run,
            metrics=metrics,
            artifact_policy=artifact_policy,
        )
        row = dict(run)
        row.update(metrics)
        row.update(artifact_status)
        row["summary_row_id"] = stable_hash(
            {
                "run_id": row.get("run_id"),
                "final_status": row.get("final_status"),
                "artifact_complete": row.get("artifact_complete"),
                "abnormal_reasons": row.get("abnormal_reasons"),
            }
        )
        run_level_results.append(row)

    aggregated = aggregate_group_metrics(
        run_level_results,
        group_order=group_order or list(_EXPECTED_GROUP_IDS),
        iterations=max(100, bootstrap_iterations),
        seed=seed,
        thresholds=thresholds,
        requirement2_capability_map=requirement2_capability_map,
    )

    delta_metrics = [
        "success",
        "first_pass_success",
        "schema_valid",
        "executable_plan",
        "patch_event_count",
        "replan_event_count",
        "duration_ms",
        "high_cost_call_count",
        "action_continue_count",
        "action_patch_local_count",
        "action_suffix_replan_count",
        "action_stop_count",
    ]
    delta_rows: list[dict[str, Any]] = []
    for metric in delta_metrics:
        delta_rows.extend(
            compute_increment_deltas(
                run_level_results,
                group_order=group_order or list(_EXPECTED_GROUP_IDS),
                metric_key=metric,
                iterations=max(100, bootstrap_iterations),
                seed=seed + len(delta_rows) + 1,
            )
        )

    rerun_candidates = _build_rerun_candidates(
        run_level_results=run_level_results,
        rerun_policy=rerun_policy,
    )
    rerun_selection = {
        "generated_at": now_iso(),
        "runs": [
            {
                "group_id": item["group_id"],
                "task_key": item["task_key"],
                "replicate": item["replicate"],
            }
            for item in rerun_candidates
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "run_level_results.jsonl", run_level_results)
    write_json(output_dir / "run_level_results.json", run_level_results)

    summary_rows = aggregated["summary_rows"]
    patch_rows = aggregated["patch_rows"]
    high_cost_rows = aggregated["high_cost_rows"]
    action_rows = aggregated["action_rows"]
    requirement2_rows = aggregated["requirement2_rows"]
    abnormal_rows = aggregated["abnormal_rows"]
    gate_rows = aggregated["gate_rows"]

    write_csv(
        output_dir / "matrix_metrics_summary.csv",
        summary_rows,
        [
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
            "runtime_state_observable_rate",
            "shadow_output_observable_rate",
            "patch_events_mean",
            "replan_events_mean",
            "suffix_replan_events_mean",
            "duration_ms_mean",
            "high_cost_call_mean",
            "high_cost_failure_mean",
            "action_continue_mean",
            "action_patch_local_mean",
            "action_suffix_replan_mean",
            "action_stop_mean",
            "shadow_action_agreement_rate",
            "patch_minimality_hit_rate",
            "suffix_replan_prefix_preservation_rate",
        ],
    )
    write_json(output_dir / "matrix_metrics_summary.json", summary_rows)
    write_csv(
        output_dir / "action_distribution.csv",
        action_rows,
        [
            "group_id",
            "action_continue_total",
            "action_patch_local_total",
            "action_suffix_replan_total",
            "action_stop_total",
            "shadow_action_observation_total",
            "shadow_action_agreement_total",
            "shadow_action_agreement_rate",
        ],
    )
    write_csv(
        output_dir / "patch_replan_breakdown.csv",
        patch_rows,
        [
            "group_id",
            "patch_events_total",
            "replan_events_total",
            "suffix_replan_events_total",
            "patch_parameter_level",
            "patch_tool_level",
            "patch_structure_level",
            "patch_minimality_hit_rate",
            "suffix_prefix_sample_size",
            "suffix_prefix_preservation_rate",
        ],
    )
    write_csv(
        output_dir / "high_cost_breakdown.csv",
        high_cost_rows,
        [
            "group_id",
            "high_cost_calls_total",
            "high_cost_failures_total",
            "high_cost_rule_hits",
        ],
    )
    write_csv(
        output_dir / "requirement2_tool_capability_slices.csv",
        requirement2_rows,
        ["group_id", "slice_type", "name", "covered", "usage_count"],
    )
    write_csv(
        output_dir / "mechanism_increment_deltas.csv",
        delta_rows,
        [
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
    write_csv(
        output_dir / "abnormal_samples.csv",
        abnormal_rows,
        [
            "run_id",
            "task_id",
            "group_id",
            "replicate",
            "reason",
            "final_status",
            "event_log_path",
        ],
    )
    write_jsonl(output_dir / "abnormal_samples.jsonl", abnormal_rows)

    evidence_index = [
        {
            "run_id": row.get("run_id"),
            "group_id": row.get("group_id"),
            "task_key": row.get("task_key"),
            "replicate": row.get("replicate"),
            "freeze_id": row.get("freeze_id"),
            "task_set_version": row.get("task_set_version"),
            "run_config_path": row.get("run_config_path"),
            "event_log_path": row.get("event_log_path"),
            "snapshot_path": row.get("snapshot_path"),
            "report_path": row.get("report_path"),
            "summary_row_id": row.get("summary_row_id"),
            "artifact_complete": row.get("artifact_complete"),
        }
        for row in run_level_results
    ]
    write_json(output_dir / "evidence_index.json", evidence_index)

    write_csv(
        output_dir / "run_traceability_index.csv",
        run_level_results,
        [
            "run_id",
            "group_id",
            "replicate",
            "task_key",
            "difficulty",
            "budget_tier",
            "runtime_policy",
            "final_status",
            "success",
            "artifact_complete",
            "lineage_linked",
            "run_config_linked",
            "event_log_linked",
            "snapshot_linked",
            "report_linked",
            "missing_required_artifacts",
            "run_config_path",
            "event_log_path",
            "snapshot_path",
            "report_path",
            "summary_row_id",
        ],
    )

    write_json(
        output_dir / "offline_gate_assessment.json",
        {
            "generated_at": now_iso(),
            "thresholds": thresholds,
            "groups": gate_rows,
        },
    )
    write_json(output_dir / "rerun_candidates.json", rerun_candidates)
    write_json(output_dir / "rerun_selection.json", rerun_selection)

    validation_summary = {
        "generated_at": now_iso(),
        "run_count": len(run_level_results),
        "success_count": sum(1 for row in run_level_results if row.get("success")),
        "artifact_complete_count": sum(
            1 for row in run_level_results if row.get("artifact_complete")
        ),
        "rerun_candidate_count": len(rerun_candidates),
        "groups": summary_rows,
    }
    write_json(output_dir / "validation_summary.json", validation_summary)

    markdown = _build_issue221_markdown_report(
        issue_id=int(manifest.get("issue_id") or 221),
        run_manifest_path=_resolve_issue221_manifest_path(
            manifest=manifest,
            output_dir=output_dir,
        ),
        config_path=Path(str(manifest.get("config_path") or "UNKNOWN")),
        freeze_id=str(manifest.get("freeze_id") or "UNKNOWN"),
        summary_rows=summary_rows,
        delta_rows=delta_rows,
        gate_rows=gate_rows,
        generated_at=now_iso(),
    )
    (output_dir / "matrix_report.md").write_text(markdown, encoding="utf-8")

    return {
        "run_level_results": run_level_results,
        "summary_rows": summary_rows,
        "action_rows": action_rows,
        "rerun_candidates": rerun_candidates,
        "validation_summary": validation_summary,
    }


def load_issue221_selection(path: Path) -> set[tuple[str, str, int]]:
    """读取 rerun/子集选择清单。"""

    payload = load_json(path)
    raw_runs = payload.get("runs")
    if not isinstance(raw_runs, list):
        raise ValueError("selection payload missing `runs` list")

    selection: set[tuple[str, str, int]] = set()
    for item in raw_runs:
        if not isinstance(item, dict):
            continue
        group_id = item.get("group_id")
        task_key = item.get("task_key")
        replicate = item.get("replicate")
        if not (
            isinstance(group_id, str)
            and group_id
            and isinstance(task_key, str)
            and task_key
            and isinstance(replicate, int)
            and replicate > 0
        ):
            continue
        selection.add((group_id, task_key, replicate))
    return selection


def datetime_now_tag() -> str:
    return now_iso().replace(":", "").replace("-", "").replace("+", "z")


def _build_rerun_candidates(
    *,
    run_level_results: Iterable[dict[str, Any]],
    rerun_policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    max_attempts = int(rerun_policy.get("max_attempts") or 2)
    rows: list[dict[str, Any]] = []
    for row in run_level_results:
        reasons: list[str] = []
        final_status = str(row.get("final_status") or "UNKNOWN")
        if final_status != "DONE":
            reasons.append(f"status:{final_status}")
        for name in row.get("missing_required_artifacts") or []:
            reasons.append(f"missing_artifact:{name}")
        if not row.get("lineage_linked"):
            reasons.append("lineage_unlinked")
        for name in row.get("abnormal_reasons") or []:
            reasons.append(f"abnormal:{name}")

        attempt_number = int(row.get("attempt_number") or 1)
        if not reasons or attempt_number >= max_attempts:
            continue

        rows.append(
            {
                "run_id": row.get("run_id"),
                "group_id": row.get("group_id"),
                "task_key": row.get("task_key"),
                "replicate": row.get("replicate"),
                "attempt_number": attempt_number,
                "next_attempt_number": attempt_number + 1,
                "reasons": reasons,
                "rerun_strategy": "retry_same_config",
                "run_config_path": row.get("run_config_path"),
            }
        )
    return rows


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _resolve_issue221_manifest_path(*, manifest: Mapping[str, Any], output_dir: Path) -> Path:
    raw_path = manifest.get("run_manifest_path")
    if isinstance(raw_path, str) and raw_path:
        return Path(raw_path)
    return output_dir / "runs_manifest.json"


def _build_issue221_markdown_report(
    *,
    issue_id: int,
    run_manifest_path: Path,
    config_path: Path,
    freeze_id: str,
    summary_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    generated_at: str,
) -> str:
    """生成 issue221 专用矩阵报告，避免复用旧 A0-A6 文案。"""

    base_report = build_markdown_report(
        issue_id=issue_id,
        run_manifest_path=run_manifest_path,
        freeze_id=freeze_id,
        summary_rows=summary_rows,
        delta_rows=delta_rows,
        gate_rows=gate_rows,
        generated_at=generated_at,
    )
    legacy_header = f"# Issue #{issue_id} Vertical Experiment Report (A0-A6)"
    issue221_header = f"# Issue #{issue_id} Four-Group Experiment Matrix Report"
    lines = base_report.splitlines()
    if lines and lines[0] == legacy_header:
        lines[0] = issue221_header

    lines_to_insert = [
        "",
        "## Matrix Context",
        "",
        f"- config_path: `{config_path}`",
        "- comparison_scope: `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`",
        "- report_contract: `issue221_run_level_matrix`",
        "",
    ]
    insert_at = 5 if len(lines) >= 5 else len(lines)
    lines[insert_at:insert_at] = lines_to_insert
    return "\n".join(lines) + "\n"


def _evaluate_run_artifacts(
    *,
    run: Mapping[str, Any],
    metrics: Mapping[str, Any],
    artifact_policy: Mapping[str, Any],
) -> dict[str, Any]:
    final_status = str(metrics.get("final_status") or "UNKNOWN")
    required = list(artifact_policy.get("all_runs_required") or [])
    if final_status == "DONE":
        required.extend(artifact_policy.get("success_runs_required") or [])
    elif final_status.startswith("WAITING"):
        required.extend(artifact_policy.get("waiting_runs_required") or [])
    elif final_status in {"FAILED", "CANCELLED"}:
        required.extend(artifact_policy.get("failed_runs_required") or [])

    status_map = {
        "run_config_path": _path_exists(run.get("run_config_path")),
        "event_log_path": bool(metrics.get("event_log_path"))
        and _path_exists(metrics.get("event_log_path")),
        "snapshot_path": bool(metrics.get("snapshot_linked")),
        "report_path": bool(metrics.get("report_linked")),
    }
    missing = sorted(name for name in required if not status_map.get(name, False))
    lineage_linked = bool(run.get("freeze_id")) and bool(run.get("task_set_version"))
    return {
        "run_config_linked": status_map["run_config_path"],
        "event_log_linked": status_map["event_log_path"],
        "snapshot_linked": status_map["snapshot_path"],
        "report_linked": status_map["report_path"],
        "lineage_linked": lineage_linked,
        "missing_required_artifacts": missing,
        "artifact_complete": not missing and lineage_linked,
    }


def _execute_matrix_run(
    *,
    task_id: str,
    goal: str,
    constraints: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str, str, str, str | None, str | None]:
    from src.adapters.builtins import ensure_builtin_adapters
    from src.agents.executor import ExecutorAgent
    from src.agents.planner import PlannerAgent
    from src.agents.summarizer import SummarizerAgent
    from src.models.contracts import (
        Decision,
        DecisionChoice,
        PendingActionType,
        ProteinDesignTask,
        now_iso as contracts_now_iso,
    )
    from src.models.db import (
        ExternalStatus,
        InternalStatus,
        TERMINAL_INTERNAL_STATUSES,
        TaskRecord,
        to_external_status,
    )
    from src.storage.snapshot_store import append_snapshot
    from src.workflow.context import WorkflowContext
    from src.workflow.decision_apply import (
        apply_patch_confirm_decision,
        apply_plan_confirm_decision,
        apply_replan_confirm_decision,
    )
    from src.workflow.snapshots import build_task_snapshot
    from src.workflow.status import transition_task_status

    try:
        task = ProteinDesignTask(
            task_id=task_id,
            goal=goal,
            constraints=constraints,
            metadata=metadata,
        )
        ensure_builtin_adapters()
        planner = PlannerAgent()
        executor = ExecutorAgent()
        summarizer = SummarizerAgent()

        record = TaskRecord(
            id=task.task_id,
            status=ExternalStatus.CREATED,
            internal_status=InternalStatus.CREATED,
            created_at=contracts_now_iso(),
            updated_at=contracts_now_iso(),
            goal=task.goal,
            constraints=task.constraints,
            metadata=task.metadata,
            plan=None,
            design_result=None,
            safety_events=[],
        )
        context = WorkflowContext(
            task=task,
            plan=None,
            step_results={},
            safety_events=[],
            design_result=None,
            status=InternalStatus.CREATED,
        )

        plan = planner.plan_with_status(task, context, record=record)
        plan = _apply_experiment_plan_overrides(
            plan=plan,
            task_constraints=constraints,
        )
        context.plan = plan
        record.plan = plan
        loop_budget = 12
        resume_from_existing = False
        while loop_budget > 0:
            if context.status in TERMINAL_INTERNAL_STATUSES:
                break
            if context.status == InternalStatus.WAITING_PLAN_CONFIRM:
                _auto_apply_waiting_decision(
                    task=task,
                    context=context,
                    record=record,
                )
                resume_from_existing = False
            elif context.status == InternalStatus.WAITING_PATCH:
                _auto_apply_waiting_decision(
                    task=task,
                    context=context,
                    record=record,
                )
                resume_from_existing = True
            elif context.status == InternalStatus.WAITING_REPLAN:
                _auto_apply_waiting_decision(
                    task=task,
                    context=context,
                    record=record,
                )
                if context.status == InternalStatus.PLANNING and context.plan is not None:
                    transition_task_status(
                        context,
                        record,
                        InternalStatus.PLANNED,
                        reason="auto_accept_replan_candidate",
                    )
                resume_from_existing = True
            elif context.status in {InternalStatus.PLANNED, InternalStatus.RUNNING, InternalStatus.PLANNING}:
                active_plan = context.plan or plan
                if active_plan is None:
                    raise ValueError("active plan is required before execution")
                active_plan = _apply_experiment_plan_overrides(
                    plan=active_plan,
                    task_constraints=constraints,
                )
                context.plan = active_plan
                record.plan = active_plan
                plan = active_plan
                plan = executor.run_plan(
                    active_plan,
                    context,
                    record=record,
                    finalize_status=False,
                    resume_from_existing=resume_from_existing,
                )
                if context.status in TERMINAL_INTERNAL_STATUSES:
                    break
                if context.status not in {
                    InternalStatus.WAITING_PLAN_CONFIRM,
                    InternalStatus.WAITING_PATCH,
                    InternalStatus.WAITING_REPLAN,
                }:
                    executor.summarize_and_finalize(context, record, summarizer)
                    break
                resume_from_existing = True
            else:
                break
            loop_budget -= 1

        if loop_budget <= 0 and context.status not in TERMINAL_INTERNAL_STATUSES:
            raise RuntimeError("auto decision loop exhausted before task reached terminal state")

        if context.status == InternalStatus.DONE:
            append_snapshot(
                build_task_snapshot(
                    context,
                    state_override=to_external_status(context.status),
                    require_runtime_state=False,
                )
            )

        status_external = str(getattr(record.status, "value", record.status))
        status_internal = str(
            getattr(record.internal_status, "value", record.internal_status)
        )
        report_path = (
            str(record.design_result.report_path)
            if record.design_result is not None
            else ""
        )
        pending_action_type = (
            str(record.pending_action.action_type.value)
            if record.pending_action is not None
            else None
        )
        return (
            status_external,
            status_internal,
            report_path,
            pending_action_type,
            None,
        )
    except Exception as exc:  # pragma: no cover - runtime resilience path
        return ("FAILED", "FAILED", "", None, f"{type(exc).__name__}: {exc}")


def _apply_experiment_plan_overrides(
    *,
    plan,
    task_constraints: Mapping[str, Any],
):
    """按实验约束重写计划中的特定工具选择。

    Args:
        plan: 当前待执行计划。
        task_constraints: 任务约束，允许 issue221 在实验层声明工具覆写。

    Returns:
        可能被重写后的计划；若无需调整则返回原计划。
    """

    override_tool = str(
        task_constraints.get("structure_prediction_tool_override") or ""
    ).strip()
    override_mode = str(
        task_constraints.get("structure_prediction_execution_mode") or ""
    ).strip()
    secondary_structure_tool_override = str(
        task_constraints.get("secondary_structure_annotation_tool_override") or ""
    ).strip()
    if not override_tool and not secondary_structure_tool_override:
        return plan

    changed = False
    rewritten_steps = []
    for step in plan.steps:
        rewritten_step = step
        if _is_structure_prediction_step(step):
            step_changed = False
            rewritten_inputs = dict(step.inputs or {})
            rewritten_metadata = dict(step.metadata or {})
            if step.tool != override_tool:
                rewritten_metadata.update(
                    {
                        "issue221_structure_override_applied": True,
                        "issue221_structure_tool_original": step.tool,
                        "issue221_structure_tool_override": override_tool,
                    }
                )
                step_changed = True
            if override_mode and override_tool == "openfold":
                if rewritten_inputs.get("execution_mode") != override_mode:
                    rewritten_inputs["execution_mode"] = override_mode
                    step_changed = True
            if step_changed:
                rewritten_step = step.model_copy(
                    update={
                        "tool": override_tool,
                        "inputs": rewritten_inputs,
                        "metadata": rewritten_metadata,
                    },
                    deep=True,
                )
                changed = True
        elif _is_secondary_structure_annotation_step(step) and secondary_structure_tool_override:
            rewritten_inputs = dict(step.inputs or {})
            rewritten_metadata = dict(step.metadata or {})
            rewritten_metadata.update(
                {
                    "issue221_secondary_structure_override_applied": True,
                    "issue221_secondary_structure_tool_original": step.tool,
                    "issue221_secondary_structure_tool_override": secondary_structure_tool_override,
                }
            )
            rewritten_step = step.model_copy(
                update={
                    "tool": secondary_structure_tool_override,
                    "inputs": rewritten_inputs,
                    "metadata": rewritten_metadata,
                },
                deep=True,
            )
            changed = True
        rewritten_steps.append(rewritten_step)

    if not changed:
        return plan
    return plan.model_copy(update={"steps": rewritten_steps}, deep=True)


def _is_structure_prediction_step(step) -> bool:
    """判断步骤是否属于结构预测能力。"""

    if str(getattr(step, "tool", "") or "") in {
        "esmfold",
        "nim_esmfold",
        "alphafold",
        "openfold",
    }:
        return True
    metadata = getattr(step, "metadata", None) or {}
    capability = metadata.get("capability")
    if capability == "structure_prediction":
        return True
    capabilities = metadata.get("capabilities")
    if isinstance(capabilities, list):
        return "structure_prediction" in capabilities
    return False


def _is_secondary_structure_annotation_step(step) -> bool:
    """判断步骤是否属于二级结构注释能力。"""

    if str(getattr(step, "tool", "") or "") == "dssp":
        return True
    metadata = getattr(step, "metadata", None) or {}
    capability = metadata.get("capability")
    if capability == "secondary_structure_annotation":
        return True
    capabilities = metadata.get("capabilities")
    if isinstance(capabilities, list):
        return "secondary_structure_annotation" in capabilities
    return False


def _auto_apply_waiting_decision(
    *,
    task,
    context,
    record,
) -> None:
    from src.models.contracts import (
        Decision,
        DecisionChoice,
        PendingActionType,
    )
    from src.workflow.decision_apply import (
        apply_patch_confirm_decision,
        apply_plan_confirm_decision,
        apply_replan_confirm_decision,
    )

    pending_action = context.pending_action or record.pending_action
    if pending_action is None:
        raise ValueError("pending_action is required when auto-applying waiting decision")

    candidate_id = pending_action.default_recommendation or pending_action.default_suggestion
    if candidate_id is None and pending_action.candidates:
        candidate_id = pending_action.candidates[0].candidate_id

    if pending_action.action_type == PendingActionType.REPLAN_CONFIRM and candidate_id is None:
        choice = DecisionChoice.CONTINUE
    else:
        choice = DecisionChoice.ACCEPT

    decision = Decision(
        decision_id=f"auto_decision_{stable_hash([task.task_id, pending_action.pending_action_id, now_iso()])}",
        task_id=task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=choice,
        selected_candidate_id=candidate_id if choice == DecisionChoice.ACCEPT else None,
        decided_by="issue221_auto_runner",
        comment="auto-accept default recommendation for offline matrix execution",
    )

    if pending_action.action_type == PendingActionType.PLAN_CONFIRM:
        apply_plan_confirm_decision(context, record, decision)
        return
    if pending_action.action_type == PendingActionType.PATCH_CONFIRM:
        apply_patch_confirm_decision(context, record, decision)
        return
    if pending_action.action_type == PendingActionType.REPLAN_CONFIRM:
        apply_replan_confirm_decision(context, record, decision)
        return
    raise ValueError(f"unsupported pending action type: {pending_action.action_type.value}")


def _git_short_sha() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip()
        return output or "nogit"
    except Exception:
        return "nogit"


def _normalize_groups(
    *,
    baselines: Any,
    group_overrides: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(baselines, list) or len(baselines) != 4:
        raise ValueError("baseline freeze must provide exactly four baselines")

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in baselines:
        if not isinstance(raw, dict):
            continue
        group_id = raw.get("id")
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("baseline row missing id")
        merged = deep_merge(dict(raw), _dict_value(group_overrides.get(group_id)))
        merged["supports_current_repo"] = bool(
            merged.get("supports_current_repo", True)
        )
        if not merged["supports_current_repo"]:
            raise ValueError(f"group {group_id} is not enabled for current repo")
        merged["comparison_order"] = int(merged.get("comparison_order") or 0)
        rows.append(merged)
        seen_ids.add(group_id)

    if tuple(sorted(seen_ids)) != tuple(sorted(_EXPECTED_GROUP_IDS)):
        raise ValueError(f"baseline ids mismatch: {sorted(seen_ids)}")
    return sorted(rows, key=lambda item: int(item.get("comparison_order") or 0))


def _normalize_tasks(
    *,
    freeze_tasks: Any,
    task_overrides: Mapping[str, Any],
    default_goal: str,
) -> list[dict[str, Any]]:
    if not isinstance(freeze_tasks, list) or not freeze_tasks:
        raise ValueError("baseline freeze must provide tasks")

    rows: list[dict[str, Any]] = []
    for raw in freeze_tasks:
        if not isinstance(raw, dict):
            continue
        task_key = raw.get("task_key")
        if not isinstance(task_key, str) or not task_key:
            raise ValueError("task row missing task_key")
        override = _dict_value(task_overrides.get(task_key))
        constraints: dict[str, Any] = {}
        if raw.get("prompt") is not None:
            constraints["prompt"] = raw.get("prompt")
        if isinstance(raw.get("length_range"), list):
            constraints["length_range"] = list(raw.get("length_range"))
        constraints = deep_merge(constraints, _dict_value(override.get("constraints")))
        rows.append(
            {
                "task_key": task_key,
                "goal": str(override.get("goal") or default_goal),
                "display_name": str(raw.get("display_name") or task_key),
                "difficulty": str(raw.get("difficulty") or "unknown"),
                "budget_tier": str(raw.get("budget_tier") or "standard"),
                "rationale": str(raw.get("rationale") or ""),
                "constraints": constraints,
                "metadata": _dict_value(override.get("metadata")),
            }
        )
    return rows


def _path_exists(value: Any) -> bool:
    path = _path_from_value(value)
    return bool(path and path.exists())


def _path_from_value(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def _resolve_artifact_policy(raw_policy: Any) -> dict[str, list[str]]:
    policy = _dict_value(raw_policy)
    return {
        "all_runs_required": _string_list(
            policy.get("all_runs_required"),
            default=["run_config_path", "event_log_path"],
        ),
        "success_runs_required": _string_list(
            policy.get("success_runs_required"),
            default=["snapshot_path", "report_path"],
        ),
        "waiting_runs_required": _string_list(
            policy.get("waiting_runs_required"),
            default=["snapshot_path"],
        ),
        "failed_runs_required": _string_list(
            policy.get("failed_runs_required"),
            default=[],
        ),
    }


def _resolve_issue221_matrix(*, config: Mapping[str, Any]) -> dict[str, Any]:
    freeze_config_path = (
        _path_from_value(config.get("baseline_freeze_config_path"))
        or DEFAULT_ISSUE221_BASELINE_FREEZE_CONFIG_PATH
    )
    freeze_config = load_json(freeze_config_path)
    group_overrides = _dict_value(config.get("group_overrides"))
    task_overrides = _dict_value(config.get("task_overrides"))
    groups = _normalize_groups(
        baselines=freeze_config.get("baselines"),
        group_overrides=group_overrides,
    )
    tasks = _normalize_tasks(
        freeze_tasks=freeze_config.get("tasks"),
        task_overrides=task_overrides,
        default_goal=str(config.get("default_goal") or "de_novo_design"),
    )

    manifest_path = _path_from_value(config.get("baseline_freeze_manifest_path"))
    manifest_exists = bool(manifest_path and manifest_path.exists())
    return {
        "freeze_id": str(freeze_config.get("freeze_id") or "issue209-baseline-freeze"),
        "task_set_version": str(
            freeze_config.get("task_set_version") or "issue209-taskset-v1"
        ),
        "difficulty_scheme_version": str(
            freeze_config.get("difficulty_scheme_version")
            or "issue209-difficulty-v1"
        ),
        "metrics_contract": _dict_value(freeze_config.get("metrics_contract")),
        "high_cost_rules": normalize_high_cost_rules(
            freeze_config.get("high_cost_rules")
        ),
        "groups": groups,
        "tasks": tasks,
        "baseline_freeze": {
            "config_path": str(freeze_config_path),
            "config_hash": stable_hash(freeze_config),
            "manifest_path": str(manifest_path) if manifest_path else None,
            "manifest_exists": manifest_exists,
        },
    }


def _resolve_requirement2_capability_map(raw_value: Any) -> dict[str, list[str]]:
    if not isinstance(raw_value, dict):
        return dict(DEFAULT_REQUIREMENT2_CAPABILITY_MAP)
    resolved: dict[str, list[str]] = {}
    for key, value in raw_value.items():
        if isinstance(key, str) and isinstance(value, list):
            resolved[key] = [str(item) for item in value if isinstance(item, str)]
    return resolved or dict(DEFAULT_REQUIREMENT2_CAPABILITY_MAP)


def _resolve_rerun_policy(raw_value: Any) -> dict[str, Any]:
    policy = _dict_value(raw_value)
    return {
        "max_attempts": int(policy.get("max_attempts") or 2),
    }


def _resolve_task_repeat_count(
    *,
    task: Mapping[str, Any],
    default_repeats: int,
    repeat_policy: Mapping[str, Any],
) -> int:
    if default_repeats <= 0:
        raise ValueError("default repeats must be positive")
    by_budget = _dict_value(repeat_policy.get("by_budget_tier"))
    budget_tier = task.get("budget_tier")
    if isinstance(budget_tier, str):
        value = by_budget.get(budget_tier)
        if isinstance(value, int) and value > 0:
            return value
    return default_repeats


def _resolve_thresholds(raw_value: Any) -> dict[str, float]:
    thresholds = dict(DEFAULT_OFFLINE_THRESHOLDS)
    if isinstance(raw_value, dict):
        for key, value in raw_value.items():
            if isinstance(key, str) and isinstance(value, (int, float)):
                thresholds[key] = float(value)
    return thresholds


def _sanitize_task_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return cleaned[:96]


def _string_list(value: Any, *, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    return [str(item) for item in value if isinstance(item, str) and item]
