from __future__ import annotations

import json
from pathlib import Path

from src.infra.w12_vertical_experiment import (
    DEFAULT_REPLAY_SAMPLE_DIR,
    DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    aggregate_group_metrics,
    compute_increment_deltas,
    extract_run_metrics,
    load_replay_sample,
    materialize_replay_sample,
    replay_sample,
    replay_samples,
    stable_hash,
    wilson_interval,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def test_wilson_interval_basic() -> None:
    low, high = wilson_interval(50, 100)
    assert low is not None
    assert high is not None
    assert 0.40 < low < 0.50
    assert 0.50 < high < 0.60


def test_extract_run_metrics_and_requirement2(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "task_a0.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_a0",
                "from_status": "RUNNING",
                "to_status": "REPLANNING",
                "reason": "replan_requested",
                "timestamp": "2026-03-15T10:00:00+00:00",
            },
            {
                "event": "PARAM_TWEAK",
                "task_id": "task_a0",
                "step_id": "S1",
                "timestamp": "2026-03-15T10:00:01+00:00",
                "data": {"recovery": {"recovery_layer": "parameter_level"}},
            },
            {
                "event": "STEP_FINISHED",
                "task_id": "task_a0",
                "step_id": "S2",
                "tool": "esmfold",
                "status": "success",
                "timestamp": "2026-03-15T10:00:02+00:00",
            },
            {
                "event": "WAITING_ENTER",
                "task_id": "task_a0",
                "pending_action_id": "pa_1",
                "ts": "2026-03-15T10:00:03+00:00",
            },
            {
                "event": "DECISION_APPLIED",
                "task_id": "task_a0",
                "pending_action_id": "pa_1",
                "ts": "2026-03-15T10:00:04+00:00",
            },
            {
                "event": "WAITING_EXIT",
                "task_id": "task_a0",
                "pending_action_id": "pa_1",
                "ts": "2026-03-15T10:00:05+00:00",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_a0",
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "reason": "summarizer_placeholder",
                "timestamp": "2026-03-15T10:00:06+00:00",
            },
        ],
    )

    run = {
        "run_id": "r1",
        "task_id": "task_a0",
        "task_key": "k1",
        "group_id": "A0",
        "replicate": 1,
        "event_log_path": str(log_path),
        "started_at": "2026-03-15T10:00:00+00:00",
        "finished_at": "2026-03-15T10:00:06+00:00",
        "status_external": "DONE",
        "freeze_id": "f1",
    }

    tool_map = {
        "protgpt2": ["sequence_generation"],
        "esmfold": ["structure_prediction"],
    }

    metrics = extract_run_metrics(
        run,
        tool_capability_map=tool_map,
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    assert metrics["success"] is True
    assert metrics["patch_event_count"] == 1
    assert metrics["replan_event_count"] == 1
    assert metrics["waiting_chain_complete"] is True
    assert metrics["requirement2_coverage"]["sequence_core"] is False
    assert metrics["requirement2_coverage"]["structure_prediction"] is True
    assert metrics["layer_counter"]["parameter_level"] == 1
    assert metrics["high_cost_call_count"] == 1
    assert metrics["high_cost_rule_hits"]["structure_mapping"] == 1


def test_replay_sample_materialization_extracts_runtime_snapshot_and_shadow_fields(
    tmp_path: Path,
) -> None:
    sample = load_replay_sample(
        DEFAULT_REPLAY_SAMPLE_DIR / "runtime_shadow_success_sample.json"
    )
    run = materialize_replay_sample(sample, output_dir=tmp_path)
    tool_map = {
        "seqgen_local": ["sequence_generation"],
        "esmfold": ["structure_prediction"],
    }

    metrics = extract_run_metrics(
        run,
        tool_capability_map=tool_map,
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    assert metrics["success"] is True
    assert metrics["waiting_chain_complete"] is True
    assert metrics["snapshot_linked"] is True
    assert metrics["report_linked"] is True
    assert metrics["runtime_state_observable"] is True
    assert metrics["shadow_output_observable"] is True
    assert metrics["replay_sample_id"] == "runtime_shadow_success_sample"
    assert metrics["replay_source_freeze_id"] == "issue209-baseline-freeze-smoke"


def test_extract_run_metrics_reads_latest_jsonl_snapshot(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "task_jsonl_snapshot.jsonl"
    snapshot_path = tmp_path / "snapshots" / "task_jsonl_snapshot.jsonl"
    report_path = tmp_path / "reports" / "task_jsonl_snapshot.json"

    _write_jsonl(
        log_path,
        [
            {
                "event": "STEP_FINISHED",
                "task_id": "task_jsonl_snapshot",
                "step_id": "S2",
                "tool": "esmfold",
                "status": "success",
                "timestamp": "2026-04-16T10:00:01+00:00",
                "data": {
                    "action_name": "continue",
                    "shadow_action": "continue",
                },
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_jsonl_snapshot",
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "timestamp": "2026-04-16T10:00:02+00:00",
            },
        ],
    )
    _write_jsonl(
        snapshot_path,
        [
            {"task_id": "task_jsonl_snapshot", "artifacts": {}},
            {
                "task_id": "task_jsonl_snapshot",
                "artifacts": {
                    "runtime_state": {
                        "p_success": 0.73,
                        "p_structural_failure": 0.19,
                    },
                    "decision_summary": {
                        "shadow_action": "continue",
                        "shadow_score": {"value": 0.88},
                    },
                },
            },
        ],
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{}", encoding="utf-8")

    metrics = extract_run_metrics(
        {
            "run_id": "r_jsonl_snapshot",
            "task_id": "task_jsonl_snapshot",
            "task_key": "k_jsonl_snapshot",
            "group_id": "lite_belief_state",
            "replicate": 1,
            "freeze_id": "f_jsonl_snapshot",
            "event_log_path": str(log_path),
            "snapshot_path": str(snapshot_path),
            "report_path": str(report_path),
            "status_external": "DONE",
        },
        tool_capability_map={"esmfold": ["structure_prediction"]},
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    assert metrics["snapshot_linked"] is True
    assert metrics["runtime_state_observable"] is True
    assert metrics["shadow_output_observable"] is True
    assert metrics["action_continue_count"] == 1
    assert metrics["shadow_action_agreement_rate"] == 1.0


def test_replay_sample_is_deterministic_for_same_fixture(tmp_path: Path) -> None:
    sample_path = DEFAULT_REPLAY_SAMPLE_DIR / "runtime_shadow_success_sample.json"
    tool_map = {
        "seqgen_local": ["sequence_generation"],
        "esmfold": ["structure_prediction"],
    }

    first = replay_sample(
        sample_path,
        output_dir=tmp_path / "bundle",
        tool_capability_map=tool_map,
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )
    second = replay_sample(
        sample_path,
        output_dir=tmp_path / "bundle",
        tool_capability_map=tool_map,
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    keys = (
        "success",
        "final_status",
        "waiting_chain_complete",
        "runtime_state_observable",
        "shadow_output_observable",
        "high_cost_call_count",
        "requirement2_coverage",
        "step_finished_count",
    )
    first_subset = {key: first[key] for key in keys}
    second_subset = {key: second[key] for key in keys}
    assert first_subset == second_subset
    assert stable_hash(first_subset) == stable_hash(second_subset)


def test_replay_samples_batch_returns_reusable_metrics(tmp_path: Path) -> None:
    tool_map = {
        "seqgen_local": ["sequence_generation"],
        "esmfold": ["structure_prediction"],
    }
    sample_paths = [
        DEFAULT_REPLAY_SAMPLE_DIR / "runtime_shadow_success_sample.json",
        DEFAULT_REPLAY_SAMPLE_DIR / "replan_waiting_shadow_sample.json",
    ]

    rows = replay_samples(
        sample_paths,
        output_dir=tmp_path / "batch",
        tool_capability_map=tool_map,
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    assert len(rows) == 2
    by_id = {row["replay_sample_id"]: row for row in rows}
    assert by_id["runtime_shadow_success_sample"]["shadow_output_observable"] is True
    assert by_id["replan_waiting_shadow_sample"]["replan_event_count"] == 1
    assert by_id["replan_waiting_shadow_sample"]["requirement2_coverage"]["sequence_core"] is True


def test_extract_run_metrics_tracks_action_counts_and_shadow_agreement(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "logs" / "task_action_metrics.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "event": "STEP_FINISHED",
                "task_id": "task_action_metrics",
                "step_id": "S1",
                "tool": "seqgen_local",
                "status": "success",
                "timestamp": "2026-04-16T10:10:01+00:00",
                "data": {
                    "action_name": "continue",
                    "shadow_action": "continue",
                },
            },
            {
                "event": "PARAM_TWEAK",
                "task_id": "task_action_metrics",
                "step_id": "S2",
                "timestamp": "2026-04-16T10:10:02+00:00",
                "data": {
                    "shadow_action": "patch",
                    "recovery": {"recovery_layer": "parameter_level"},
                },
            },
            {
                "event": "RECOVERY_ESCALATED",
                "task_id": "task_action_metrics",
                "step_id": "S3",
                "timestamp": "2026-04-16T10:10:03+00:00",
                "data": {
                    "action_name": "replan",
                    "shadow_action": "suffix_replan",
                    "recovery": {"upgrade_reason": "suffix_replan"},
                },
            },
            {
                "event": "STEP_FAILED",
                "task_id": "task_action_metrics",
                "step_id": "S4",
                "tool": "esmfold",
                "status": "failed",
                "timestamp": "2026-04-16T10:10:04+00:00",
                "data": {
                    "action_name": "stop",
                    "shadow_action": "suffix_replan",
                    "failure_code": "STOP_REQUESTED",
                },
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_action_metrics",
                "from_status": "RUNNING",
                "to_status": "FAILED",
                "timestamp": "2026-04-16T10:10:05+00:00",
            },
        ],
    )

    metrics = extract_run_metrics(
        {
            "run_id": "r_action_metrics",
            "task_id": "task_action_metrics",
            "task_key": "k_action_metrics",
            "group_id": "lite_belief_state",
            "replicate": 1,
            "freeze_id": "f_action_metrics",
            "event_log_path": str(log_path),
            "status_external": "FAILED",
        },
        tool_capability_map={
            "seqgen_local": ["sequence_generation"],
            "esmfold": ["structure_prediction"],
        },
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    assert metrics["action_continue_count"] == 1
    assert metrics["action_patch_local_count"] == 1
    assert metrics["action_suffix_replan_count"] == 1
    assert metrics["action_stop_count"] == 1
    assert metrics["shadow_action_observation_count"] == 4
    assert metrics["shadow_action_agreement_count"] == 3
    assert metrics["shadow_action_agreement_rate"] == 0.75


def test_aggregate_and_deltas(tmp_path: Path) -> None:
    def make_run(group_id: str, task_key: str, replicate: int, success: bool, patch_count: int) -> dict:
        return {
            "run_id": f"{group_id}_{task_key}_r{replicate}",
            "task_id": f"{group_id}_{task_key}_r{replicate}",
            "task_key": task_key,
            "group_id": group_id,
            "replicate": replicate,
            "freeze_id": "f1",
            "event_log_path": "",
            "snapshot_path": "",
            "report_path": "",
            "started_at": "2026-03-15T10:00:00+00:00",
            "finished_at": "2026-03-15T10:00:02+00:00",
            "duration_ms": 2000.0,
            "final_status": "DONE" if success else "FAILED",
            "success": success,
            "first_pass_success": success and patch_count == 0,
            "schema_valid": True,
            "executable_plan": success,
            "patch_event_count": patch_count,
            "replan_event_count": 0 if success else 1,
            "suffix_replan_event_count": 0,
            "waiting_enter_count": 0,
            "step_failed_count": 0 if success else 1,
            "step_finished_count": 1,
            "waiting_chain_complete": True,
            "failure_traceable": True,
            "action_continue_count": 1 if success else 0,
            "action_patch_local_count": patch_count,
            "action_suffix_replan_count": 0 if success else 1,
            "action_stop_count": 0,
            "shadow_action_agreement_count": 1 if success else 0,
            "shadow_action_observation_count": 1,
            "shadow_action_agreement_rate": 1.0 if success else 0.0,
            "layer_counter": {"parameter_level": patch_count} if patch_count else {},
            "tool_usage": {"protgpt2": 1},
            "capability_usage": {"sequence_generation": 1},
            "requirement2_coverage": {
                "sequence_core": True,
                "quality_qc": False,
                "objective_scoring": False,
                "structure_prediction": False,
            },
            "suffix_prefix_samples": [],
            "abnormal_reasons": [] if success else ["step_failed"],
            "step_failed_details": [],
        }

    runs = [
        make_run("A0", "k1", 1, False, 1),
        make_run("A0", "k2", 1, True, 1),
        make_run("A1", "k1", 1, True, 0),
        make_run("A1", "k2", 1, True, 0),
    ]

    aggregated = aggregate_group_metrics(
        runs,
        group_order=["A0", "A1"],
        iterations=300,
        seed=7,
        thresholds={
            "schema_valid_rate": 0.995,
            "executable_plan_rate": 0.95,
            "patch_minimality_hit_rate": 0.8,
            "suffix_replan_prefix_preservation_rate": 1.0,
        },
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    summary = {row["group_id"]: row for row in aggregated["summary_rows"]}
    assert summary["A0"]["success_rate"] == 0.5
    assert summary["A1"]["success_rate"] == 1.0
    assert summary["A1"]["patch_events_mean"] == 0.0
    assert summary["A0"]["high_cost_call_mean"] == 0.0
    assert summary["A0"]["runtime_state_observable_rate"] == 0.0
    assert summary["A1"]["shadow_output_observable_rate"] == 0.0
    assert summary["A1"]["action_continue_mean"] == 1.0
    assert summary["A0"]["action_patch_local_mean"] == 1.0
    assert summary["A0"]["action_suffix_replan_mean"] == 0.5
    assert summary["A1"]["shadow_action_agreement_rate"] == 1.0

    deltas = compute_increment_deltas(
        runs,
        group_order=["A0", "A1"],
        metric_key="success",
        iterations=400,
        seed=11,
    )
    assert len(deltas) == 1
    row = deltas[0]
    assert row["from_group"] == "A0"
    assert row["to_group"] == "A1"
    assert row["delta"] is not None
    assert row["pairing"] == "paired"


def test_requirement2_rows_include_new_similarity_and_secondary_structure_tools(
    tmp_path: Path,
) -> None:
    runs = [
        {
            "run_id": "r1",
            "task_id": "task1",
            "task_key": "k1",
            "group_id": "A0",
            "replicate": 1,
            "freeze_id": "f1",
            "event_log_path": "",
            "snapshot_path": "",
            "report_path": "",
            "started_at": "2026-03-15T10:00:00+00:00",
            "finished_at": "2026-03-15T10:00:02+00:00",
            "duration_ms": 2000.0,
            "final_status": "DONE",
            "success": True,
            "first_pass_success": True,
            "schema_valid": True,
            "executable_plan": True,
            "patch_event_count": 0,
            "replan_event_count": 0,
            "suffix_replan_event_count": 0,
            "waiting_enter_count": 0,
            "step_failed_count": 0,
            "step_finished_count": 3,
            "waiting_chain_complete": True,
            "failure_traceable": True,
            "layer_counter": {},
            "tool_usage": {"mmseqs2": 1, "blastp": 1, "dssp": 1},
            "capability_usage": {
                "sequence_similarity_search": 2,
                "secondary_structure_annotation": 1,
                "quality_qc": 1,
            },
            "requirement2_coverage": {
                "sequence_core": False,
                "quality_qc": True,
                "objective_scoring": False,
                "structure_prediction": False,
                "similarity_search": True,
                "secondary_structure": True,
            },
            "suffix_prefix_samples": [],
            "abnormal_reasons": [],
            "step_failed_details": [],
        }
    ]

    aggregated = aggregate_group_metrics(
        runs,
        group_order=["A0"],
        iterations=100,
        seed=7,
        thresholds={
            "schema_valid_rate": 0.995,
            "executable_plan_rate": 0.95,
            "patch_minimality_hit_rate": 0.8,
            "suffix_replan_prefix_preservation_rate": 1.0,
        },
        requirement2_capability_map=DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    )

    summary = aggregated["summary_rows"][0]
    rows = aggregated["requirement2_rows"]
    row_lookup = {(row["slice_type"], row["name"]): row for row in rows}

    assert summary["requirement2_similarity_search"] is True
    assert summary["requirement2_secondary_structure"] is True
    assert row_lookup[("tool", "mmseqs2")]["usage_count"] == 1
    assert row_lookup[("tool", "blastp")]["usage_count"] == 1
    assert row_lookup[("tool", "dssp")]["usage_count"] == 1
