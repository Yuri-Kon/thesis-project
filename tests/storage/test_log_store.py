from __future__ import annotations

import json
from pathlib import Path

from src.storage.log_store import read_timeline_events


def test_read_timeline_events_extracts_registered_observability_fields(
    tmp_path: Path,
) -> None:
    """时间线读取应保留原有观测字段名称与嵌套来源优先级。"""

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    task_id = "task_obs_fields"
    payload = {
        "timestamp": "2026-05-20T12:00:00Z",
        "task_id": task_id,
        "event": "STEP_FAILED",
        "step_id": "S3",
        "data": {
            "tool": "esmfold",
            "capability_id": "structure_prediction",
            "recovery": {
                "to_tool": "openfold3",
                "recovery_layer": "tool_level",
                "reason": "remote fallback",
                "runtime_state_summary": {"budget_pressure": 0.8},
            },
            "waiting_runtime_summary": {
                "action_score": {"value": 0.42},
            },
        },
        "error_details": {
            "failure_code": "REMOTE_TIMEOUT",
            "remote_job_id": "job_001",
        },
    }
    (log_dir / f"{task_id}.jsonl").write_text(
        json.dumps(payload, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    [event] = read_timeline_events(task_id, log_dir=log_dir)

    assert event["event_type"] == "STEP_FAILED"
    assert event["tool_id"] == "esmfold"
    assert event["to_tool"] == "openfold3"
    assert event["capability_id"] == "structure_prediction"
    assert event["failure_code"] == "REMOTE_TIMEOUT"
    assert event["remote_job_id"] == "job_001"
    assert event["recovery_layer"] == "tool_level"
    assert event["recovery_reason"] == "remote fallback"
    assert event["runtime_state_summary"] == {"budget_pressure": 0.8}
    assert event["action_score"] == {"value": 0.42}
