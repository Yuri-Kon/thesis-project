from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.storage.log_store import read_timeline_events


@pytest.mark.unit
def test_read_timeline_events_extracts_recovery_observability_fields(tmp_path: Path) -> None:
    task_id = "timeline_obs_001"
    log_file = tmp_path / f"{task_id}.jsonl"
    events = [
        {
            "event": "STEP_FAILED",
            "task_id": task_id,
            "step_id": "S3",
            "tool": "dummy_tool",
            "failure_type": "tool_error",
            "error_details": {"failure_code": "S3_TIMEOUT"},
            "timestamp": "2026-03-16T01:00:00+00:00",
            "data": {
                "recovery": {
                    "recovery_layer": "tool_level",
                    "from_tool": "dummy_tool",
                    "to_tool": "esmfold",
                    "capability_id": "structure_prediction",
                    "adapter_mode": "remote",
                    "io_type": "sequence_to_structure",
                    "reason": "retry_exhausted",
                    "candidate_id": "cand_patch_1",
                }
            },
        },
        {
            "event_type": "DECISION_APPLIED",
            "task_id": task_id,
            "decision_id": "d_001",
            "ts": "2026-03-16T01:00:01+00:00",
            "data": {
                "choice": "accept",
                "selected_candidate_id": "cand_001",
                "decision_source": "human_reviewer",
                "tool_id": "esmfold",
                "capability_id": "structure_prediction",
                "adapter_mode": "remote",
            },
        },
    ]

    with log_file.open("w", encoding="utf-8") as handle:
        for item in events:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")

    timeline = read_timeline_events(task_id, log_dir=tmp_path)

    assert len(timeline) == 2

    failed = timeline[0]
    assert failed["event_type"] == "STEP_FAILED"
    assert failed["failure_type"] == "tool_error"
    assert failed["failure_code"] == "S3_TIMEOUT"
    assert failed["from_tool"] == "dummy_tool"
    assert failed["to_tool"] == "esmfold"
    assert failed["capability_id"] == "structure_prediction"
    assert failed["adapter_mode"] == "remote"
    assert failed["io_type"] == "sequence_to_structure"
    assert failed["candidate_id"] == "cand_patch_1"
    assert failed["recovery_layer"] == "tool_level"
    assert failed["recovery_reason"] == "retry_exhausted"

    decision = timeline[1]
    assert decision["event_type"] == "DECISION_APPLIED"
    assert decision["candidate_id"] == "cand_001"
    assert decision["decision_source"] == "human_reviewer"
    assert decision["tool_id"] == "esmfold"
    assert decision["capability_id"] == "structure_prediction"


@pytest.mark.unit
def test_read_timeline_events_keeps_legacy_entries_compatible(tmp_path: Path) -> None:
    task_id = "timeline_legacy_001"
    log_file = tmp_path / f"{task_id}.jsonl"
    with log_file.open("w", encoding="utf-8") as handle:
        handle.write("{not-json}\n")
        handle.write(json.dumps({"event": "TASK_STATUS_CHANGED", "task_id": task_id}) + "\n")
        handle.write(json.dumps({"event": "STEP_FINISHED", "task_id": task_id, "step_id": "S1"}) + "\n")

    timeline = read_timeline_events(task_id, log_dir=tmp_path)

    assert len(timeline) == 2
    transition = timeline[0]
    assert transition["event_type"] == "STATE_TRANSITION"
    assert transition["tool_id"] is None
    assert transition["failure_code"] is None
    finished = timeline[1]
    assert finished["event_type"] == "STEP_FINISHED"
    assert finished["step_id"] == "S1"


@pytest.mark.unit
def test_read_timeline_events_extracts_planner_route_fields(tmp_path: Path) -> None:
    task_id = "timeline_route_001"
    log_file = tmp_path / f"{task_id}.jsonl"
    event = {
        "event": "PLANNER_ROUTE_DECISION",
        "task_id": task_id,
        "tool": "external_baseline",
        "timestamp": "2026-03-16T03:00:00+00:00",
        "data": {
            "from_tool": "planner_default",
            "to_tool": "external_baseline",
            "capability": "planner_generation",
            "trigger_threshold": "consecutive_execution_failures=2>=2",
        },
    }

    with log_file.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")

    timeline = read_timeline_events(task_id, log_dir=tmp_path)
    assert len(timeline) == 1
    route = timeline[0]
    assert route["event_type"] == "PLANNER_ROUTE_DECISION"
    assert route["tool_id"] == "external_baseline"
    assert route["from_tool"] == "planner_default"
    assert route["to_tool"] == "external_baseline"
    assert route["capability_id"] == "planner_generation"
