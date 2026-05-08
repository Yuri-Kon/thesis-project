from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.agents.planner import (
    PlannerAgent,
    ToolSpec,
    _load_default_tool_registry,
)
from src.infra.benchmark_platform_adapters import (
    normalize_issue199_platform_adapter_config,
)
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
from src.llm.baseline_provider import BaselineProvider
from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.provider_registry import create_provider, load_provider_catalog

__all__ = [
    "DEFAULT_ISSUE172_CONFIG_PATH",
    "DEFAULT_ISSUE172_INTERNAL_SUMMARY_PATH",
    "DEFAULT_ISSUE172_KG_PATH",
    "build_issue172_run_manifest",
    "evaluate_issue172_run_manifest",
]


DEFAULT_ISSUE172_CONFIG_PATH = Path(
    "configs/experiments/external_baseline_experiment.json"
)
DEFAULT_ISSUE172_OUTPUT_ROOT = Path("output/experiment/external-baseline-comparison")
DEFAULT_ISSUE172_KG_PATH = Path("src/kg/protein_tool_kg.json")
DEFAULT_ISSUE172_PLATFORM_FREEZE_CONFIG_PATH = Path(
    "configs/experiments/benchmark_platform_adapters.json"
)
DEFAULT_ISSUE172_TASK_FREEZE_CONFIG_PATH = Path(
    "configs/experiments/baseline_experiment_contract.json"
)
DEFAULT_ISSUE172_INTERNAL_SUMMARY_PATH = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv"
)
_EXPECTED_GROUP_IDS = ("E0", "E1", "E2")


def build_issue172_run_manifest(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    output_root: Path | None = None,
    run_id: str | None = None,
    repeats_override: int | None = None,
    max_runs: int | None = None,
    dry_run: bool = False,
    provider_alias: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """构建并可选执行外部基线实验清单。"""

    issue_id = int(config.get("issue_id") or 172)
    matrix = _resolve_issue172_matrix(config=config)
    resolved_output_root = (
        output_root
        or _path_from_value(config.get("output_root"))
        or DEFAULT_ISSUE172_OUTPUT_ROOT
    )
    resolved_output_root.mkdir(parents=True, exist_ok=True)
    resolved_run_id = run_id or f"w12e3-{_datetime_now_tag()}-{_git_short_sha()}"
    run_dir = resolved_output_root / resolved_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_constraints = _dict_value(config.get("base_constraints"))
    base_metadata = _dict_value(config.get("base_metadata"))
    repeat_policy = _dict_value(config.get("repeat_policy"))
    offline_thresholds = _resolve_thresholds(config.get("offline_thresholds"))
    requirement2_capability_map = _resolve_requirement2_capability_map(
        config.get("requirement2_capability_map")
    )
    artifact_policy = _resolve_artifact_policy(config.get("artifact_policy"))
    rerun_policy = _resolve_rerun_policy(config.get("rerun_policy"))
    internal_reference_summary_path = (
        _path_from_value(config.get("internal_reference_summary_path"))
        or DEFAULT_ISSUE172_INTERNAL_SUMMARY_PATH
    )

    run_entries: list[dict[str, Any]] = []
    counter = 0
    for group in matrix["groups"]:
        group_id = str(group["id"])
        group_constraints = _dict_value(group.get("constraint_overrides"))
        decision_policy = _dict_value(group.get("decision_policy"))
        for task in matrix["tasks"]:
            task_key = str(task["task_key"])
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
                if max_runs is not None and counter >= max_runs:
                    break

                merged_constraints = deep_merge(base_constraints, group_constraints)
                merged_constraints = deep_merge(
                    merged_constraints,
                    _dict_value(task.get("constraints")),
                )
                merged_constraints = deep_merge(
                    merged_constraints,
                    {
                        "runtime_fallback": {
                            "enable_dual_route": False,
                            "force_external_only": True,
                            "fallback_capability": "external_horizontal_baseline",
                        },
                        "plan_top_k": int(merged_constraints.get("plan_top_k") or 1),
                        "patch_top_k": int(merged_constraints.get("patch_top_k") or 1),
                        "replan_top_k": int(merged_constraints.get("replan_top_k") or 1),
                    },
                )

                goal = _compose_horizontal_goal(
                    base_prompt=str(task.get("prompt") or task.get("goal") or "de_novo_design"),
                    group=group,
                    constraints=merged_constraints,
                )
                merged_metadata = deep_merge(base_metadata, _dict_value(task.get("metadata")))
                merged_metadata = deep_merge(
                    merged_metadata,
                    {
                        "issue_id": issue_id,
                        "experiment": "external_baseline_comparison",
                        "group_id": group_id,
                        "group_label": group.get("label"),
                        "canonical_label": group.get("canonical_label"),
                        "baseline_family": group.get("baseline_family"),
                        "agent_style": group.get("agent_style"),
                        "task_key": task_key,
                        "replicate": replicate,
                        "freeze_id": matrix["freeze_id"],
                        "dataset_version": matrix["dataset_version"],
                        "task_set_version": matrix["task_set_version"],
                        "difficulty": task.get("difficulty"),
                        "budget_tier": task.get("budget_tier"),
                        "tool_whitelist_version": matrix["tool_whitelist"]["tool_whitelist_version"],
                        "budget_version": matrix["budget_contract"]["budget_version"],
                        "decision_policy": decision_policy,
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
                    "goal": goal,
                    "constraints": merged_constraints,
                    "metadata": merged_metadata,
                    "lineage": {
                        "freeze_id": matrix["freeze_id"],
                        "dataset_version": matrix["dataset_version"],
                        "task_set_version": matrix["task_set_version"],
                        "difficulty_scheme_version": matrix["difficulty_scheme_version"],
                        "platform_freeze_config_path": matrix["platform_freeze"]["config_path"],
                        "platform_freeze_config_hash": matrix["platform_freeze"]["config_hash"],
                        "task_freeze_config_path": matrix["task_freeze"]["config_path"],
                        "task_freeze_config_hash": matrix["task_freeze"]["config_hash"],
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
                    (
                        status_external,
                        status_internal,
                        report_path,
                        pending_action_type,
                        execution_error,
                    ) = _execute_horizontal_run(
                        task_id=task_id,
                        goal=goal,
                        constraints=merged_constraints,
                        metadata=merged_metadata,
                        group_policy=group,
                        allowed_tool_ids=matrix["tool_whitelist"]["allowed_tool_ids"],
                        provider_allowlist=matrix["provider_allowlist"],
                        provider_alias=provider_alias,
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
                        "canonical_label": group.get("canonical_label"),
                        "comparison_order": group.get("comparison_order"),
                        "replicate": replicate,
                        "attempt_number": 1,
                        "issue_id": issue_id,
                        "freeze_id": matrix["freeze_id"],
                        "dataset_version": matrix["dataset_version"],
                        "task_set_version": matrix["task_set_version"],
                        "difficulty_scheme_version": matrix["difficulty_scheme_version"],
                        "difficulty": task.get("difficulty"),
                        "budget_tier": task.get("budget_tier"),
                        "baseline_family": group.get("baseline_family"),
                        "agent_style": group.get("agent_style"),
                        "goal": goal,
                        "constraints_hash": stable_hash(merged_constraints),
                        "metadata_hash": stable_hash(merged_metadata),
                        "run_spec_hash": stable_hash(
                            {
                                "group_id": group_id,
                                "task_key": task_key,
                                "replicate": replicate,
                                "constraints": merged_constraints,
                                "decision_policy": decision_policy,
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
                        "tool_whitelist_version": matrix["tool_whitelist"]["tool_whitelist_version"],
                        "budget_version": matrix["budget_contract"]["budget_version"],
                        "planner_provider_alias": provider_alias,
                        "high_cost_rules_hash": stable_hash(matrix["high_cost_rules"]),
                        "platform_freeze_config_path": matrix["platform_freeze"]["config_path"],
                        "platform_freeze_config_hash": matrix["platform_freeze"]["config_hash"],
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
        "dataset_version": matrix["dataset_version"],
        "task_set_version": matrix["task_set_version"],
        "difficulty_scheme_version": matrix["difficulty_scheme_version"],
        "tool_whitelist": matrix["tool_whitelist"],
        "budget_contract": matrix["budget_contract"],
        "provider_allowlist": matrix["provider_allowlist"],
        "metrics_contract": matrix["metrics_contract"],
        "high_cost_rules": matrix["high_cost_rules"],
        "platforms": matrix["platforms"],
        "platform_freeze": matrix["platform_freeze"],
        "task_freeze": matrix["task_freeze"],
        "dry_run": dry_run,
        "groups": matrix["groups"],
        "tasks": matrix["tasks"],
        "offline_thresholds": offline_thresholds,
        "requirement2_capability_map": requirement2_capability_map,
        "artifact_policy": artifact_policy,
        "rerun_policy": rerun_policy,
        "repeat_policy": repeat_policy,
        "internal_reference_summary_path": str(internal_reference_summary_path),
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
                "provider_alias": provider_alias,
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
            "agent_style",
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


def evaluate_issue172_run_manifest(
    *,
    manifest: Mapping[str, Any],
    output_dir: Path,
    kg_path: Path = DEFAULT_ISSUE172_KG_PATH,
    bootstrap_iterations: int = 10000,
    seed: int = 20260420,
    internal_summary_path: Path | None = None,
) -> dict[str, Any]:
    """评估外部基线实验并生成对比产物。"""

    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise ValueError("run manifest missing `runs` list")

    group_order = [
        str(group.get("id"))
        for group in manifest.get("groups", [])
        if isinstance(group, dict) and isinstance(group.get("id"), str)
    ]
    thresholds = _resolve_thresholds(manifest.get("offline_thresholds"))
    artifact_policy = _resolve_artifact_policy(manifest.get("artifact_policy"))
    rerun_policy = _resolve_rerun_policy(manifest.get("rerun_policy"))
    requirement2_capability_map = _resolve_requirement2_capability_map(
        manifest.get("requirement2_capability_map")
    )
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

    summary_rows = aggregated["summary_rows"]
    patch_rows = aggregated["patch_rows"]
    high_cost_rows = aggregated["high_cost_rows"]
    action_rows = aggregated["action_rows"]
    requirement2_rows = aggregated["requirement2_rows"]
    abnormal_rows = aggregated["abnormal_rows"]
    gate_rows = aggregated["gate_rows"]
    rerun_candidates = _build_rerun_candidates(
        run_level_results=run_level_results,
        rerun_policy=rerun_policy,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "run_level_results.jsonl", run_level_results)
    write_json(output_dir / "run_level_results.json", run_level_results)
    write_csv(
        output_dir / "horizontal_metrics_summary.csv",
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
            "patch_minimality_hit_rate",
            "suffix_replan_prefix_preservation_rate",
        ],
    )
    write_json(output_dir / "horizontal_metrics_summary.json", summary_rows)
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
    write_json(
        output_dir / "offline_gate_assessment.json",
        {
            "generated_at": now_iso(),
            "thresholds": thresholds,
            "groups": gate_rows,
        },
    )
    write_json(output_dir / "rerun_candidates.json", rerun_candidates)
    write_json(
        output_dir / "evidence_index.json",
        [
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
        ],
    )
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
            "agent_style",
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

    reference_path = (
        internal_summary_path
        or _path_from_value(manifest.get("internal_reference_summary_path"))
        or DEFAULT_ISSUE172_INTERNAL_SUMMARY_PATH
    )
    merged_rows, reference_group_id = _build_internal_reference_comparison(
        summary_rows=summary_rows,
        internal_summary_path=reference_path,
    )
    write_csv(
        output_dir / "lite_belief_state_vs_e0_e2.csv",
        merged_rows,
        [
            "group_id",
            "label",
            "scope",
            "success_rate",
            "first_pass_success_rate",
            "duration_ms_mean",
            "high_cost_call_mean",
            "waiting_chain_complete_rate",
            "failure_traceable_rate",
            "patch_events_mean",
            "replan_events_mean",
        ],
    )
    write_json(output_dir / "lite_belief_state_vs_e0_e2.json", merged_rows)

    report_markdown = _build_issue172_markdown_report(
        issue_id=int(manifest.get("issue_id") or 172),
        run_manifest_path=_resolve_manifest_path(manifest=manifest, output_dir=output_dir),
        config_path=Path(str(manifest.get("config_path") or "UNKNOWN")),
        freeze_id=str(manifest.get("freeze_id") or "UNKNOWN"),
        dataset_version=str(manifest.get("dataset_version") or "UNKNOWN"),
        summary_rows=summary_rows,
        delta_rows=delta_rows,
        gate_rows=gate_rows,
        merged_rows=merged_rows,
        internal_reference_group_id=reference_group_id,
        generated_at=now_iso(),
    )
    (output_dir / "horizontal_report.md").write_text(report_markdown, encoding="utf-8")

    validation_summary = {
        "generated_at": now_iso(),
        "run_count": len(run_level_results),
        "success_count": sum(1 for row in run_level_results if row.get("success")),
        "artifact_complete_count": sum(
            1 for row in run_level_results if row.get("artifact_complete")
        ),
        "rerun_candidate_count": len(rerun_candidates),
        "reference_group_id": reference_group_id,
        "groups": summary_rows,
    }
    write_json(output_dir / "validation_summary.json", validation_summary)
    return {
        "run_level_results": run_level_results,
        "summary_rows": summary_rows,
        "merged_rows": merged_rows,
        "rerun_candidates": rerun_candidates,
        "validation_summary": validation_summary,
    }


def _execute_horizontal_run(
    *,
    task_id: str,
    goal: str,
    constraints: dict[str, Any],
    metadata: dict[str, Any],
    group_policy: Mapping[str, Any],
    allowed_tool_ids: list[str],
    provider_allowlist: Mapping[str, Any],
    provider_alias: str | None,
) -> tuple[str, str, str, str | None, str | None]:
    from src.adapters.builtins import ensure_builtin_adapters
    from src.agents.executor import ExecutorAgent
    from src.agents.summarizer import SummarizerAgent
    from src.models.contracts import now_iso as contracts_now_iso
    from src.models.db import (
        ExternalStatus,
        InternalStatus,
        TERMINAL_INTERNAL_STATUSES,
        TaskRecord,
        to_external_status,
    )
    from src.models.contracts import ProteinDesignTask
    from src.storage.snapshot_store import append_snapshot
    from src.workflow.context import WorkflowContext
    from src.workflow.errors import PlanRunError
    from src.workflow.snapshots import build_task_snapshot
    from src.workflow.status import transition_task_status

    filtered_registry = _filter_tool_registry(allowed_tool_ids)
    fallback_provider = _load_issue172_provider(
        provider_allowlist=provider_allowlist,
        requested_alias=provider_alias,
    )
    planner = PlannerAgent(
        tool_registry=filtered_registry,
        llm_provider=None,
        fallback_llm_provider=fallback_provider,
    )
    executor = ExecutorAgent()
    summarizer = SummarizerAgent()

    try:
        task = ProteinDesignTask(
            task_id=task_id,
            goal=goal,
            constraints=constraints,
            metadata=metadata,
        )
        ensure_builtin_adapters()
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
        plan = _apply_horizontal_plan_overrides(
            plan=plan,
            task_constraints=constraints,
        )
        context.plan = plan
        record.plan = plan
        loop_budget = int(group_policy.get("max_loop_budget") or 12)
        resume_from_existing = False
        decision_history: dict[str, int] = {}

        while loop_budget > 0:
            if context.status in TERMINAL_INTERNAL_STATUSES:
                break
            if context.status in {
                InternalStatus.WAITING_PLAN_CONFIRM,
                InternalStatus.WAITING_PATCH,
                InternalStatus.WAITING_REPLAN,
            }:
                _auto_apply_horizontal_decision(
                    task=task,
                    context=context,
                    record=record,
                    group_policy=group_policy,
                    decision_history=decision_history,
                )
                if context.status in TERMINAL_INTERNAL_STATUSES:
                    break
                resume_from_existing = context.status in {
                    InternalStatus.RUNNING,
                    InternalStatus.PLANNING,
                }
            elif context.status in {
                InternalStatus.PLANNED,
                InternalStatus.RUNNING,
                InternalStatus.PLANNING,
            }:
                active_plan = context.plan or plan
                if active_plan is None:
                    raise ValueError("active plan is required before execution")
                active_plan = _apply_horizontal_plan_overrides(
                    plan=active_plan,
                    task_constraints=constraints,
                )
                context.plan = active_plan
                record.plan = active_plan
                plan = active_plan
                try:
                    plan = executor.run_plan(
                        active_plan,
                        context,
                        record=record,
                        finalize_status=False,
                        resume_from_existing=resume_from_existing,
                    )
                except PlanRunError:
                    if context.status not in {
                        InternalStatus.WAITING_PATCH,
                        InternalStatus.WAITING_REPLAN,
                    }:
                        raise
                    resume_from_existing = True
                else:
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
            transition_task_status(
                context,
                record,
                InternalStatus.FAILED,
                reason="external_baseline_loop_budget_exhausted",
            )

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


def _auto_apply_horizontal_decision(
    *,
    task,
    context,
    record,
    group_policy: Mapping[str, Any],
    decision_history: dict[str, int] | None = None,
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

    decision_policy = _dict_value(group_policy.get("decision_policy"))
    patch_round_limit = int(decision_policy.get("max_patch_accepts") or 0)
    replan_round_limit = int(decision_policy.get("max_replan_accepts") or 0)

    fingerprint = stable_hash(
        [
            pending_action.action_type.value,
            candidate_id or "",
            str(pending_action.metadata.get("workflow_action") or ""),
            str(pending_action.metadata.get("workflow_action_reason") or ""),
        ]
    )
    repeated_count = (
        int(decision_history.get(fingerprint, 0))
        if decision_history is not None
        else 0
    )

    if pending_action.action_type == PendingActionType.PLAN_CONFIRM:
        choice = DecisionChoice.ACCEPT
        comment = (
            f"{group_policy.get('canonical_label') or group_policy.get('label')} "
            "accepts the selected external baseline plan candidate."
        )
    elif pending_action.action_type == PendingActionType.PATCH_CONFIRM:
        if patch_round_limit > repeated_count and candidate_id is not None:
            choice = DecisionChoice.ACCEPT
            comment = "Reflexion baseline accepts one patch round for textual recovery."
        else:
            choice = DecisionChoice.CANCEL
            comment = (
                "This external baseline does not continue patch recovery after the configured limit."
            )
            candidate_id = None
    elif pending_action.action_type == PendingActionType.REPLAN_CONFIRM:
        if replan_round_limit > repeated_count and candidate_id is not None:
            choice = DecisionChoice.ACCEPT
            comment = "Reflexion baseline accepts one replan round after failure feedback."
        else:
            choice = DecisionChoice.CANCEL
            comment = (
                "This external baseline stops after exhausting configured replan/reflection rounds."
            )
            candidate_id = None
    else:
        raise ValueError(f"Unsupported pending action type: {pending_action.action_type}")

    if decision_history is not None:
        decision_history[fingerprint] = repeated_count + 1

    decision = Decision(
        decision_id=f"{task.task_id}_{pending_action.pending_action_id}_external_baseline",
        task_id=task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=choice,
        selected_candidate_id=candidate_id,
        decided_by="external_baseline_runner",
        comment=comment,
    )
    if pending_action.action_type == PendingActionType.PLAN_CONFIRM:
        apply_plan_confirm_decision(context, record, decision)
    elif pending_action.action_type == PendingActionType.PATCH_CONFIRM:
        apply_patch_confirm_decision(context, record, decision)
    else:
        apply_replan_confirm_decision(context, record, decision)


def _resolve_issue172_matrix(*, config: Mapping[str, Any]) -> dict[str, Any]:
    platform_freeze_path = (
        _path_from_value(config.get("platform_freeze_config_path"))
        or DEFAULT_ISSUE172_PLATFORM_FREEZE_CONFIG_PATH
    )
    task_freeze_path = (
        _path_from_value(config.get("task_freeze_config_path"))
        or DEFAULT_ISSUE172_TASK_FREEZE_CONFIG_PATH
    )
    platform_freeze = normalize_issue199_platform_adapter_config(load_json(platform_freeze_path))
    task_freeze = load_json(task_freeze_path)
    groups = _normalize_issue172_groups(config.get("groups"))
    tasks = _normalize_issue172_tasks(
        freeze_tasks=task_freeze.get("tasks"),
        task_overrides=_dict_value(config.get("task_overrides")),
    )
    return {
        "freeze_id": str(platform_freeze.get("freeze_id") or "issue199-platform-freeze"),
        "dataset_version": str(platform_freeze.get("dataset_version") or "unknown"),
        "task_set_version": str(platform_freeze.get("task_set_version") or "issue209-taskset-v1"),
        "difficulty_scheme_version": str(
            task_freeze.get("difficulty_scheme_version") or "issue209-difficulty-v1"
        ),
        "tool_whitelist": _dict_value(platform_freeze.get("tool_whitelist")),
        "budget_contract": _dict_value(platform_freeze.get("budget_contract")),
        "provider_allowlist": _dict_value(platform_freeze.get("provider_allowlist")),
        "platforms": _dict_value(platform_freeze.get("platforms")),
        "metrics_contract": _dict_value(task_freeze.get("metrics_contract")),
        "high_cost_rules": normalize_high_cost_rules(task_freeze.get("high_cost_rules")),
        "groups": groups,
        "tasks": tasks,
        "platform_freeze": {
            "config_path": str(platform_freeze_path),
            "config_hash": stable_hash(platform_freeze),
        },
        "task_freeze": {
            "config_path": str(task_freeze_path),
            "config_hash": stable_hash(task_freeze),
        },
    }


def _normalize_issue172_groups(raw_groups: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_groups, list) or len(raw_groups) != len(_EXPECTED_GROUP_IDS):
        raise ValueError("issue172 config must define exactly three groups (E0/E1/E2)")
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_groups:
        if not isinstance(raw, dict):
            continue
        group_id = raw.get("id")
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("issue172 group row missing id")
        merged = {
            **dict(raw),
            "comparison_order": int(raw.get("comparison_order") or 0),
            "constraint_overrides": _dict_value(raw.get("constraint_overrides")),
            "decision_policy": _dict_value(raw.get("decision_policy")),
            "canonical_label": str(raw.get("canonical_label") or raw.get("label") or group_id),
            "label": str(raw.get("label") or group_id),
            "baseline_family": str(raw.get("baseline_family") or group_id),
            "agent_style": str(raw.get("agent_style") or group_id),
            "supports_current_repo": bool(raw.get("supports_current_repo", True)),
        }
        if not merged["supports_current_repo"]:
            raise ValueError(f"group {group_id} is not enabled for current repo")
        rows.append(merged)
        seen_ids.add(group_id)

    if tuple(sorted(seen_ids)) != tuple(sorted(_EXPECTED_GROUP_IDS)):
        raise ValueError(f"issue172 group ids mismatch: {sorted(seen_ids)}")
    return sorted(rows, key=lambda item: int(item.get("comparison_order") or 0))


def _normalize_issue172_tasks(
    *,
    freeze_tasks: Any,
    task_overrides: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(freeze_tasks, list) or not freeze_tasks:
        raise ValueError("task freeze must provide tasks")

    rows: list[dict[str, Any]] = []
    for raw in freeze_tasks:
        if not isinstance(raw, dict):
            continue
        task_key = raw.get("task_key")
        if not isinstance(task_key, str) or not task_key:
            raise ValueError("task row missing task_key")
        override = _dict_value(task_overrides.get(task_key))
        prompt = str(override.get("prompt") or raw.get("prompt") or task_key)
        constraints: dict[str, Any] = {
            "prompt": prompt,
        }
        if isinstance(raw.get("length_range"), list):
            constraints["length_range"] = list(raw.get("length_range"))
        constraints = deep_merge(constraints, _dict_value(override.get("constraints")))
        rows.append(
            {
                "task_key": task_key,
                "prompt": prompt,
                "display_name": str(raw.get("display_name") or task_key),
                "difficulty": str(raw.get("difficulty") or "unknown"),
                "budget_tier": str(raw.get("budget_tier") or "standard"),
                "rationale": str(raw.get("rationale") or ""),
                "constraints": constraints,
                "metadata": _dict_value(override.get("metadata")),
            }
        )
    return rows


def _compose_horizontal_goal(
    *,
    base_prompt: str,
    group: Mapping[str, Any],
    constraints: Mapping[str, Any],
) -> str:
    group_id = str(group.get("id") or "E0")
    top_k = int(constraints.get("plan_top_k") or 1)
    if group_id == "E0":
        style_hint = (
            "Use a ReAct-style single trajectory baseline. Keep one concise tool path and "
            "avoid branch search or verbal reflection."
        )
    elif group_id == "E1":
        style_hint = (
            f"Use a ToT-style multi-branch baseline. Explore up to {top_k} candidate branches "
            "before selecting the most promising plan."
        )
    else:
        style_hint = (
            "Use a Reflexion-style recovery baseline. Prefer a simple initial plan but allow one "
            "text-based recovery cycle after failure feedback."
        )
    return f"{base_prompt}\n\nExternal baseline style hint: {style_hint}"


def _load_issue172_provider(
    *,
    provider_allowlist: Mapping[str, Any],
    requested_alias: str | None,
) -> BaseProvider:
    catalog_path = (
        _path_from_value(provider_allowlist.get("catalog_path"))
        or Path("configs/llm_providers.json")
    )
    if not catalog_path.exists():
        return BaselineProvider(ProviderConfig(model_name="baseline"))
    catalog = load_provider_catalog(catalog_path)
    allowed_aliases = [
        str(item)
        for item in provider_allowlist.get("allowed_aliases") or []
        if isinstance(item, str) and item
    ]
    preferred_aliases: list[str] = []
    if isinstance(requested_alias, str) and requested_alias.strip():
        preferred_aliases.append(requested_alias.strip())
    preferred_aliases.extend(alias for alias in allowed_aliases if alias != "baseline")
    preferred_aliases.append("baseline")

    for alias in preferred_aliases:
        settings = catalog.providers.get(alias)
        if settings is None:
            continue
        try:
            return create_provider(settings)
        except Exception:
            continue
    return BaselineProvider(ProviderConfig(model_name="baseline"))


def _filter_tool_registry(allowed_tool_ids: Iterable[str]) -> list[ToolSpec]:
    allowed = {tool_id for tool_id in allowed_tool_ids if tool_id}
    registry = list(_load_default_tool_registry())
    if not allowed:
        return registry
    filtered = [spec for spec in registry if spec.id in allowed]
    if not filtered:
        raise ValueError("allowed tool whitelist produced an empty planner registry")
    return filtered


def _apply_horizontal_plan_overrides(
    *,
    plan,
    task_constraints: Mapping[str, Any],
):
    override_tool = str(
        task_constraints.get("structure_prediction_tool_override") or ""
    ).strip()
    override_mode = str(
        task_constraints.get("structure_prediction_execution_mode") or ""
    ).strip()
    secondary_tool_override = str(
        task_constraints.get("secondary_structure_annotation_tool_override") or ""
    ).strip()
    if not override_tool and not secondary_tool_override:
        return plan

    changed = False
    rewritten_steps = []
    for step in plan.steps:
        rewritten_step = step
        if _is_structure_prediction_step(step) and override_tool:
            rewritten_inputs = dict(step.inputs or {})
            rewritten_metadata = dict(step.metadata or {})
            rewritten_metadata.update(
                {
                    "issue172_structure_override_applied": True,
                    "issue172_structure_tool_original": step.tool,
                    "issue172_structure_tool_override": override_tool,
                }
            )
            if override_mode and override_tool == "openfold":
                rewritten_inputs["execution_mode"] = override_mode
            rewritten_step = step.model_copy(
                update={
                    "tool": override_tool,
                    "inputs": rewritten_inputs,
                    "metadata": rewritten_metadata,
                },
                deep=True,
            )
            changed = True
        elif _is_secondary_structure_annotation_step(step) and secondary_tool_override:
            rewritten_metadata = dict(step.metadata or {})
            rewritten_metadata.update(
                {
                    "issue172_secondary_structure_override_applied": True,
                    "issue172_secondary_structure_tool_original": step.tool,
                    "issue172_secondary_structure_tool_override": secondary_tool_override,
                }
            )
            rewritten_step = step.model_copy(
                update={
                    "tool": secondary_tool_override,
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


def _build_internal_reference_comparison(
    *,
    summary_rows: list[dict[str, Any]],
    internal_summary_path: Path,
) -> tuple[list[dict[str, Any]], str]:
    merged_rows = [
        {
            "group_id": str(row.get("group_id") or ""),
            "label": str(row.get("group_id") or ""),
            "scope": "external",
            "success_rate": row.get("success_rate"),
            "first_pass_success_rate": row.get("first_pass_success_rate"),
            "duration_ms_mean": row.get("duration_ms_mean"),
            "high_cost_call_mean": row.get("high_cost_call_mean"),
            "waiting_chain_complete_rate": row.get("waiting_chain_complete_rate"),
            "failure_traceable_rate": row.get("failure_traceable_rate"),
            "patch_events_mean": row.get("patch_events_mean"),
            "replan_events_mean": row.get("replan_events_mean"),
        }
        for row in summary_rows
    ]

    if not internal_summary_path.exists():
        return merged_rows, "missing_internal_reference"

    rows = _read_csv_rows(internal_summary_path)
    target_row = None
    target_group_id = "lite_belief_state"
    for row in rows:
        group_id = str(row.get("group_id") or "")
        if group_id == "lite_belief_state":
            target_row = row
            target_group_id = group_id
            break
    if target_row is None:
        for row in rows:
            group_id = str(row.get("group_id") or "")
            if group_id == "A6":
                target_row = row
                target_group_id = group_id
                break
    if target_row is None:
        return merged_rows, "missing_internal_reference"

    merged_rows.insert(
        0,
        {
            "group_id": target_group_id,
            "label": "Lite Belief-State",
            "scope": "internal_reference",
            "success_rate": _to_float(target_row.get("success_rate")),
            "first_pass_success_rate": _to_float(target_row.get("first_pass_success_rate")),
            "duration_ms_mean": _to_float(target_row.get("duration_ms_mean")),
            "high_cost_call_mean": _to_float(target_row.get("high_cost_call_mean")),
            "waiting_chain_complete_rate": _to_float(target_row.get("waiting_chain_complete_rate")),
            "failure_traceable_rate": _to_float(target_row.get("failure_traceable_rate")),
            "patch_events_mean": _to_float(target_row.get("patch_events_mean")),
            "replan_events_mean": _to_float(target_row.get("replan_events_mean")),
        },
    )
    return merged_rows, target_group_id


def _build_issue172_markdown_report(
    *,
    issue_id: int,
    run_manifest_path: Path,
    config_path: Path,
    freeze_id: str,
    dataset_version: str,
    summary_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    merged_rows: list[dict[str, Any]],
    internal_reference_group_id: str,
    generated_at: str,
) -> str:
    base_report = build_markdown_report(
        issue_id=issue_id,
        run_manifest_path=run_manifest_path,
        freeze_id=freeze_id,
        summary_rows=summary_rows,
        delta_rows=delta_rows,
        gate_rows=gate_rows,
        generated_at=generated_at,
    )
    lines = base_report.splitlines()
    acceptance_marker = "## Acceptance Mapping"
    if acceptance_marker in lines:
        lines = lines[:lines.index(acceptance_marker)]

    legacy_header = f"# Issue #{issue_id} Vertical Experiment Report (A0-A6)"
    if lines and lines[0] == legacy_header:
        lines[0] = "# External Baseline Experiment Report (E0/E1/E2)"

    insert_at = 5 if len(lines) >= 5 else len(lines)
    context_lines = [
        "",
        "## Horizontal Context",
        "",
        f"- config_path: `{config_path}`",
        f"- dataset_version: `{dataset_version}`",
        "- comparison_scope: `lite_belief_state / E0 / E1 / E2`",
        "- report_contract: `external_baseline_comparison`",
        "",
        "## Lite Belief-State vs E0-E2",
        "",
        "| group | scope | success_rate | first_pass | duration_ms_mean | high_cost_call_mean | waiting_chain_complete_rate | failure_traceable_rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines[insert_at:insert_at] = context_lines

    merged_table_lines = [
        "| {group_id} | {scope} | {success_rate:.4f} | {first_pass_success_rate:.4f} | {duration_ms_mean:.2f} | {high_cost_call_mean:.4f} | {waiting_chain_complete_rate:.4f} | {failure_traceable_rate:.4f} |".format(
            group_id=row.get("group_id"),
            scope=row.get("scope"),
            success_rate=float(row.get("success_rate") or 0.0),
            first_pass_success_rate=float(row.get("first_pass_success_rate") or 0.0),
            duration_ms_mean=float(row.get("duration_ms_mean") or 0.0),
            high_cost_call_mean=float(row.get("high_cost_call_mean") or 0.0),
            waiting_chain_complete_rate=float(row.get("waiting_chain_complete_rate") or 0.0),
            failure_traceable_rate=float(row.get("failure_traceable_rate") or 0.0),
        )
        for row in merged_rows
    ]
    marker = "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"
    marker_index = lines.index(marker) if marker in lines else len(lines)
    lines[marker_index + 1:marker_index + 1] = merged_table_lines
    lines.extend(
        [
            "",
            "## Acceptance Mapping",
            "",
            f"- Internal reference group: `{internal_reference_group_id}`",
            "- E0 validates single-trajectory external baseline behavior under the same whitelist and budget lineage.",
            "- E1 validates multi-branch candidate selection under the same dataset and cost envelope.",
            "- E2 validates text-based recovery rounds with explicit governance logging instead of hidden retries.",
            "- Unified metrics, rerun candidates, and traceability indexes are exported for downstream evidence-pack assembly.",
        ]
    )
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


def _resolve_manifest_path(*, manifest: Mapping[str, Any], output_dir: Path) -> Path:
    raw_path = manifest.get("run_manifest_path")
    if isinstance(raw_path, str) and raw_path:
        return Path(raw_path)
    return output_dir / "runs_manifest.json"


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


def _resolve_requirement2_capability_map(raw_value: Any) -> dict[str, list[str]]:
    if not isinstance(raw_value, dict):
        return dict(DEFAULT_REQUIREMENT2_CAPABILITY_MAP)
    resolved: dict[str, list[str]] = {}
    for key, value in raw_value.items():
        if isinstance(key, str) and isinstance(value, list):
            resolved[key] = [str(item) for item in value if isinstance(item, str)]
    return resolved or dict(DEFAULT_REQUIREMENT2_CAPABILITY_MAP)


def _resolve_thresholds(raw_value: Any) -> dict[str, float]:
    thresholds = dict(DEFAULT_OFFLINE_THRESHOLDS)
    if isinstance(raw_value, dict):
        for key, value in raw_value.items():
            if isinstance(key, str) and isinstance(value, (int, float)):
                thresholds[key] = float(value)
    return thresholds


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


def _resolve_rerun_policy(raw_value: Any) -> dict[str, Any]:
    policy = _dict_value(raw_value)
    return {
        "max_attempts": int(policy.get("max_attempts") or 2),
    }


def _string_list(value: Any, *, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    return [str(item) for item in value if isinstance(item, str) and item]


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _path_from_value(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def _path_exists(value: Any) -> bool:
    path = _path_from_value(value)
    return bool(path and path.exists())


def _sanitize_task_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return cleaned[:96]


def _datetime_now_tag() -> str:
    return now_iso().replace(":", "").replace("-", "").replace("+", "z")


def _git_short_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
            .lower()
        )
    except Exception:
        return "nogit"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    import csv

    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None
