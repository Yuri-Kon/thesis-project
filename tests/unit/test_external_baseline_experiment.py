from __future__ import annotations

import json
from pathlib import Path

from src.infra.external_baseline_experiment import (
    build_issue172_run_manifest,
    evaluate_issue172_run_manifest,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def test_external_baseline_run_manifest_materializes_dry_run_configs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config = {
        "issue_id": 172,
        "platform_freeze_config_path": str(
            repo_root / "configs/experiments/benchmark_platform_adapters.json"
        ),
        "task_freeze_config_path": str(
            repo_root / "configs/experiments/baseline_experiment_contract.json"
        ),
        "output_root": str(tmp_path / "out"),
        "repeats": 2,
        "base_constraints": {"prefer_remote": False},
        "groups": [
            {
                "id": "E0",
                "label": "ReAct-style 单轨迹",
                "comparison_order": 0,
                "baseline_family": "react_style_external",
                "agent_style": "single_trajectory",
                "supports_current_repo": True,
                "constraint_overrides": {
                    "runtime_policy": "static_single_candidate",
                    "plan_top_k": 1,
                    "patch_top_k": 1,
                    "replan_top_k": 1,
                },
                "decision_policy": {"max_patch_accepts": 0, "max_replan_accepts": 0},
            },
            {
                "id": "E1",
                "label": "ToT-style 多分支",
                "comparison_order": 1,
                "baseline_family": "tot_style_external",
                "agent_style": "multi_branch_selection",
                "supports_current_repo": True,
                "constraint_overrides": {
                    "runtime_policy": "static_single_candidate",
                    "plan_top_k": 3,
                    "patch_top_k": 1,
                    "replan_top_k": 1,
                },
                "decision_policy": {"max_patch_accepts": 0, "max_replan_accepts": 0},
            },
            {
                "id": "E2",
                "label": "Reflexion-style 反思恢复",
                "comparison_order": 2,
                "baseline_family": "reflexion_style_external",
                "agent_style": "reflection_recovery",
                "supports_current_repo": True,
                "constraint_overrides": {
                    "runtime_policy": "dynamic_observation_only",
                    "plan_top_k": 1,
                    "patch_top_k": 3,
                    "replan_top_k": 3,
                },
                "decision_policy": {"max_patch_accepts": 1, "max_replan_accepts": 1},
            },
        ],
    }

    manifest, run_dir = build_issue172_run_manifest(
        config=config,
        config_path=repo_root / "configs/experiments/external_baseline_experiment.json",
        output_root=tmp_path / "out",
        run_id="external-baseline-dry-run",
        repeats_override=1,
        dry_run=True,
    )

    assert manifest["freeze_id"] == "platform-adapter-freeze-20260412"
    assert manifest["run_manifest_path"] == str(run_dir / "runs_manifest.json")
    assert len(manifest["runs"]) == 12
    first_run = manifest["runs"][0]
    assert first_run["group_id"] == "E0"
    assert first_run["status_external"] == "DRY_RUN"
    assert Path(first_run["run_config_path"]).exists()
    run_config = json.loads(Path(first_run["run_config_path"]).read_text(encoding="utf-8"))
    assert run_config["constraints"]["runtime_policy"] == "static_single_candidate"
    assert (run_dir / "runs_manifest.json").exists()
    assert (run_dir / "run_log_index.csv").exists()


def test_external_baseline_evaluator_writes_outputs(tmp_path: Path) -> None:
    run_config_path = tmp_path / "run_configs" / "success.json"
    run_config_path.parent.mkdir(parents=True, exist_ok=True)
    run_config_path.write_text("{}", encoding="utf-8")

    log_path = tmp_path / "logs" / "success.jsonl"
    snapshot_path = tmp_path / "snapshots" / "success.jsonl"
    report_path = tmp_path / "reports" / "success.json"
    _write_jsonl(
        log_path,
        [
            {
                "event": "STEP_FINISHED",
                "task_id": "task_success",
                "step_id": "S2",
                "tool": "esmfold",
                "status": "success",
                "timestamp": "2026-04-20T12:00:01+00:00",
                "data": {
                    "action_name": "continue",
                    "shadow_action": "continue",
                },
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_success",
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "timestamp": "2026-04-20T12:00:02+00:00",
            },
        ],
    )
    _write_jsonl(
        snapshot_path,
        [
            {
                "task_id": "task_success",
                "artifacts": {
                    "runtime_state": {"p_success": 0.74},
                    "decision_summary": {
                        "shadow_action": "continue",
                        "shadow_score": {"value": 0.84},
                    },
                },
            }
        ],
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{}", encoding="utf-8")

    kg_path = tmp_path / "protein_tool_kg.json"
    kg_path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "id": "esmfold",
                        "capabilities": ["structure_prediction"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    internal_summary_path = tmp_path / "vertical_metrics_summary.csv"
    internal_summary_path.write_text(
        "\n".join(
            [
                "group_id,success_rate,first_pass_success_rate,duration_ms_mean,high_cost_call_mean,waiting_chain_complete_rate,failure_traceable_rate,patch_events_mean,replan_events_mean",
                "lite_belief_state,0.75,0.5,101.0,1.0,1.0,1.0,0.3,0.1",
            ]
        ),
        encoding="utf-8",
    )

    manifest = {
        "issue_id": 172,
        "config_path": str(tmp_path / "runs_manifest_config.json"),
        "run_manifest_path": str(tmp_path / "actual_runs_manifest.json"),
        "freeze_id": "issue199-platform-freeze-20260412",
        "dataset_version": "issue170-remote-batch3-20260316",
        "high_cost_rules": [],
        "groups": [
            {"id": "E0"},
            {"id": "E2"},
        ],
        "artifact_policy": {
            "all_runs_required": ["run_config_path", "event_log_path"],
            "success_runs_required": ["snapshot_path", "report_path"],
            "waiting_runs_required": ["snapshot_path"],
            "failed_runs_required": [],
        },
        "rerun_policy": {"max_attempts": 2},
        "runs": [
            {
                "run_id": "success_run",
                "task_id": "task_success",
                "task_key": "enzyme_like_fold",
                "group_id": "E2",
                "replicate": 1,
                "attempt_number": 1,
                "freeze_id": "issue199-platform-freeze-20260412",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "medium",
                "budget_tier": "standard",
                "agent_style": "reflection_recovery",
                "run_config_path": str(run_config_path),
                "event_log_path": str(log_path),
                "snapshot_path": str(snapshot_path),
                "report_path": str(report_path),
                "status_external": "DONE",
            },
            {
                "run_id": "failed_run",
                "task_id": "task_failed",
                "task_key": "binding_scaffold",
                "group_id": "E0",
                "replicate": 1,
                "attempt_number": 1,
                "freeze_id": "issue199-platform-freeze-20260412",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "hard",
                "budget_tier": "high_cost_sensitive",
                "agent_style": "single_trajectory",
                "run_config_path": "",
                "event_log_path": "",
                "snapshot_path": "",
                "report_path": "",
                "status_external": "FAILED",
            },
        ],
    }

    result = evaluate_issue172_run_manifest(
        manifest=manifest,
        output_dir=tmp_path / "evaluation",
        kg_path=kg_path,
        bootstrap_iterations=200,
        seed=11,
        internal_summary_path=internal_summary_path,
    )

    assert len(result["run_level_results"]) == 2
    success_row = next(
        row for row in result["run_level_results"] if row["run_id"] == "success_run"
    )
    assert success_row["artifact_complete"] is True
    assert success_row["action_continue_count"] == 1

    assert len(result["rerun_candidates"]) == 1
    candidate = result["rerun_candidates"][0]
    assert candidate["run_id"] == "failed_run"
    assert "status:FAILED" in candidate["reasons"]

    evaluation_dir = tmp_path / "evaluation"
    assert (evaluation_dir / "run_level_results.jsonl").exists()
    assert (evaluation_dir / "horizontal_metrics_summary.csv").exists()
    assert (evaluation_dir / "lite_belief_state_vs_e0_e2.csv").exists()
    report = (evaluation_dir / "horizontal_report.md").read_text(encoding="utf-8")
    assert "External Baseline Experiment Report (E0/E1/E2)" in report
    assert "Lite Belief-State vs E0-E2" in report
    assert str(tmp_path / "actual_runs_manifest.json") in report
    assert str(tmp_path / "runs_manifest_config.json") in report
