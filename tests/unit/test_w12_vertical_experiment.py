from __future__ import annotations

import json
from pathlib import Path

from src.infra.w12_vertical_experiment import (
    DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    aggregate_group_metrics,
    compute_increment_deltas,
    extract_run_metrics,
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
                "step_id": "S1",
                "tool": "protgpt2",
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
    assert metrics["requirement2_coverage"]["sequence_core"] is True
    assert metrics["requirement2_coverage"]["structure_prediction"] is False
    assert metrics["layer_counter"]["parameter_level"] == 1


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
