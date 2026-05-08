from __future__ import annotations

import json
from pathlib import Path

from src.infra.thesis_integration_analysis import analyze_issue222_results


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_thesis_integration_writes_overall_stratified_and_definition_outputs(
    tmp_path: Path,
) -> None:
    kg_path = tmp_path / "protein_tool_kg.json"
    _write_json(
        kg_path,
        {
            "tools": [
                {"id": "esmfold", "capabilities": ["structure_prediction"]},
                {"id": "seqgen_local", "capabilities": ["sequence_generation"]},
            ]
        },
    )

    success_log = tmp_path / "logs" / "lite_success.jsonl"
    _write_jsonl(
        success_log,
        [
            {
                "event": "STEP_FINISHED",
                "task_id": "task_lite_success",
                "step_id": "S2",
                "tool": "esmfold",
                "status": "success",
                "timestamp": "2026-04-17T10:00:01+00:00",
                "data": {"action_name": "continue", "shadow_action": "continue"},
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_lite_success",
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "timestamp": "2026-04-17T10:00:02+00:00",
            },
        ],
    )
    success_snapshot = tmp_path / "snapshots" / "lite_success.jsonl"
    _write_jsonl(success_snapshot, [{"artifacts": {"runtime_state": {"p_success": 0.8}}}])
    success_report = tmp_path / "reports" / "lite_success.json"
    _write_json(success_report, {})

    patch_log = tmp_path / "logs" / "dynamic_patch.jsonl"
    _write_jsonl(
        patch_log,
        [
            {
                "event": "PARAM_TWEAK",
                "task_id": "task_dynamic_patch",
                "step_id": "S1",
                "timestamp": "2026-04-17T11:00:01+00:00",
                "data": {"recovery": {"recovery_layer": "parameter_level"}},
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_dynamic_patch",
                "from_status": "RUNNING",
                "to_status": "REPLANNING",
                "reason": "suffix_replan_requested",
                "timestamp": "2026-04-17T11:00:02+00:00",
            },
            {
                "event": "RECOVERY_ESCALATED",
                "task_id": "task_dynamic_patch",
                "step_id": "S2",
                "timestamp": "2026-04-17T11:00:03+00:00",
                "data": {
                    "action_name": "replan",
                    "recovery": {
                        "replan_mode": "suffix_replan",
                        "prefix_preserved": True,
                    },
                },
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_dynamic_patch",
                "from_status": "RUNNING",
                "to_status": "FAILED",
                "timestamp": "2026-04-17T11:00:04+00:00",
            },
        ],
    )
    static_log = tmp_path / "logs" / "static_success.jsonl"
    _write_jsonl(
        static_log,
        [
            {
                "event": "STEP_FINISHED",
                "task_id": "task_static_success",
                "step_id": "S1",
                "tool": "seqgen_local",
                "status": "success",
                "timestamp": "2026-04-17T09:00:01+00:00",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_static_success",
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "timestamp": "2026-04-17T09:00:02+00:00",
            },
        ],
    )

    run_config = tmp_path / "run_configs" / "placeholder.json"
    _write_json(run_config, {})
    manifest = {
        "issue_id": 221,
        "run_manifest_path": str(tmp_path / "runs_manifest.json"),
        "config_path": str(tmp_path / "config.json"),
        "freeze_id": "issue209-baseline-freeze-20260326",
        "high_cost_rules": [
            {
                "rule_id": "structure_mapping",
                "tool_ids": ["esmfold"],
                "capability_ids": ["structure_prediction"],
            }
        ],
        "groups": [
            {"id": "static_top1"},
            {"id": "dynamic_no_belief_state"},
            {"id": "lite_belief_state"},
        ],
        "artifact_policy": {
            "all_runs_required": ["run_config_path", "event_log_path"],
            "success_runs_required": ["snapshot_path", "report_path"],
            "waiting_runs_required": ["snapshot_path"],
            "failed_runs_required": [],
        },
        "runs": [
            {
                "run_id": "static_easy",
                "task_id": "task_static_success",
                "task_key": "easy_task",
                "group_id": "static_top1",
                "replicate": 1,
                "freeze_id": "issue209-baseline-freeze-20260326",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "easy",
                "budget_tier": "standard",
                "runtime_policy": "static_single_candidate",
                "run_config_path": str(run_config),
                "event_log_path": str(static_log),
                "snapshot_path": "",
                "report_path": "",
                "status_external": "DONE",
            },
            {
                "run_id": "dynamic_hard",
                "task_id": "task_dynamic_patch",
                "task_key": "hard_task",
                "group_id": "dynamic_no_belief_state",
                "replicate": 1,
                "freeze_id": "issue209-baseline-freeze-20260326",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "hard",
                "budget_tier": "high_cost_sensitive",
                "runtime_policy": "dynamic_observation_only",
                "run_config_path": str(run_config),
                "event_log_path": str(patch_log),
                "snapshot_path": "",
                "report_path": "",
                "status_external": "FAILED",
            },
            {
                "run_id": "lite_hard",
                "task_id": "task_lite_success",
                "task_key": "hard_task",
                "group_id": "lite_belief_state",
                "replicate": 1,
                "freeze_id": "issue209-baseline-freeze-20260326",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "hard",
                "budget_tier": "high_cost_sensitive",
                "runtime_policy": "lite_belief_state",
                "run_config_path": str(run_config),
                "event_log_path": str(success_log),
                "snapshot_path": str(success_snapshot),
                "report_path": str(success_report),
                "status_external": "DONE",
            },
        ],
    }

    result = analyze_issue222_results(
        manifest=manifest,
        output_dir=tmp_path / "integration",
        kg_path=kg_path,
        bootstrap_iterations=100,
        seed=23,
    )

    overall = {row["group_id"]: row for row in result["overall_rows"]}
    assert overall["lite_belief_state"]["success_rate"] == 1.0
    assert overall["dynamic_no_belief_state"]["recovery_event_mean"] == 4.0
    assert overall["lite_belief_state"]["high_cost_call_mean"] == 1.0

    hard_rows = {
        row["group_id"]: row
        for row in result["stratified_rows"]
        if row["slice_value"] == "hard"
    }
    assert hard_rows["lite_belief_state"]["success_rate"] == 1.0
    assert hard_rows["dynamic_no_belief_state"]["success_rate"] == 0.0

    output_dir = tmp_path / "integration"
    assert (output_dir / "overall_metrics.csv").exists()
    assert (output_dir / "difficulty_stratified_metrics.csv").exists()
    assert (output_dir / "recovery_complexity_high_cost.csv").exists()
    assert (output_dir / "chart_summary_rows.csv").exists()
    assert (output_dir / "metric_definitions.json").exists()
    assert (output_dir / "integration_analysis_report.md").exists()
    definitions = json.loads((output_dir / "metric_definitions.json").read_text())
    assert {row["dimension"] for row in definitions} >= {"success", "cost", "recovery"}
