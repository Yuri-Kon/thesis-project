from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_w12_issue173_governance import (
    aggregate_by_group,
    evaluate_task_governance,
)


@pytest.mark.unit
def test_evaluate_task_governance_counts_complete_chain_and_traceability(tmp_path: Path) -> None:
    task_id = "gov_task_001"
    log_file = tmp_path / f"{task_id}.jsonl"
    snapshot = tmp_path / f"{task_id}.snapshot.jsonl"
    snapshot.write_text("{}\n", encoding="utf-8")

    events = [
        {
            "event_type": "WAITING_ENTER",
            "task_id": task_id,
            "pending_action_id": "pa_1",
            "ts": "2026-03-16T00:00:00+00:00",
            "data": {"waiting_state": "WAITING_PATCH"},
            "prev_status": "RUNNING",
            "new_status": "WAITING_PATCH_CONFIRM",
        },
        {
            "event_type": "DECISION_APPLIED",
            "task_id": task_id,
            "pending_action_id": "pa_1",
            "decision_id": "d_1",
            "ts": "2026-03-16T00:00:01+00:00",
            "data": {"choice": "accept"},
            "prev_status": "WAITING_PATCH_CONFIRM",
            "new_status": "RUNNING",
        },
        {
            "event_type": "WAITING_EXIT",
            "task_id": task_id,
            "pending_action_id": "pa_1",
            "decision_id": "d_1",
            "ts": "2026-03-16T00:00:02+00:00",
            "data": {"waiting_state": "WAITING_PATCH"},
            "prev_status": "WAITING_PATCH_CONFIRM",
            "new_status": "RUNNING",
        },
        {
            "event": "STEP_FAILED",
            "task_id": task_id,
            "step_id": "S3",
            "tool": "esmfold",
            "timestamp": "2026-03-16T00:00:03+00:00",
            "data": {"failure_code": "S3_TIMEOUT"},
        },
    ]

    with log_file.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")

    result = evaluate_task_governance(
        task_id=task_id,
        group_id="A0",
        log_path=log_file,
        snapshot_path=snapshot,
    )

    assert result.waiting_chains_expected == 1
    assert result.waiting_chains_complete == 1
    assert result.replay_success_count == 1
    assert result.failed_events == 1
    assert result.traceable_failed_events == 1
    assert result.snapshot_exists is True
    assert result.log_exists is True


@pytest.mark.unit
def test_aggregate_by_group_handles_missing_chain_and_traceability(tmp_path: Path) -> None:
    task_id = "gov_task_002"
    log_file = tmp_path / f"{task_id}.jsonl"

    events = [
        {
            "event_type": "WAITING_ENTER",
            "task_id": task_id,
            "pending_action_id": "pa_2",
            "ts": "2026-03-16T00:00:00+00:00",
            "data": {"waiting_state": "WAITING_PLAN_CONFIRM"},
            "prev_status": "PLANNING",
            "new_status": "WAITING_PLAN_CONFIRM",
        },
        {
            "event": "STEP_FAILED",
            "task_id": task_id,
            "step_id": "S5",
            "timestamp": "2026-03-16T00:00:01+00:00",
            "data": {},
        },
    ]

    with log_file.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")

    task_metric = evaluate_task_governance(
        task_id=task_id,
        group_id="A1",
        log_path=log_file,
        snapshot_path=None,
    )

    assert task_metric.waiting_chains_expected == 1
    assert task_metric.waiting_chains_complete == 0
    assert task_metric.replay_success_count == 0
    assert task_metric.failed_events == 1
    assert task_metric.traceable_failed_events == 0

    grouped = aggregate_by_group([task_metric])
    assert len(grouped) == 1
    assert grouped[0].group_id == "A1"
    assert grouped[0].waiting_chains_complete == 0
    assert grouped[0].traceable_failed_events == 0
