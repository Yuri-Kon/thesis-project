from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/extract_training_samples.py")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _run_extractor(tmp_path: Path, output_dir: Path) -> None:
    logs_dir = tmp_path / "logs"
    snapshots_dir = tmp_path / "snapshots"
    reports_dir = tmp_path / "reports"
    metrics_dir = tmp_path / "metrics"

    main_task_id = "task_aaaa1111"
    hitl_task_id = "task_hitl_0001"

    _write_jsonl(
        logs_dir / f"{main_task_id}.jsonl",
        [
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": main_task_id,
                "from_status": "CREATED",
                "to_status": "PLANNING",
                "state": "PLANNING",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": main_task_id,
                "from_status": "PLANNING",
                "to_status": "PLANNED",
                "state": "PLANNED",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": main_task_id,
                "from_status": "PLANNED",
                "to_status": "RUNNING",
                "state": "RUNNING",
            },
            {
                "event": "STEP_FINISHED",
                "task_id": main_task_id,
                "step_id": "S1",
                "tool": "esmfold",
                "status": "success",
                "timestamp": "2026-03-14T10:00:00+00:00",
                "state": "RUNNING",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": main_task_id,
                "from_status": "RUNNING",
                "to_status": "SUMMARIZING",
                "state": "SUMMARIZING",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": main_task_id,
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "state": "DONE",
            },
        ],
    )

    _write_jsonl(
        logs_dir / f"{hitl_task_id}.jsonl",
        [
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": hitl_task_id,
                "from_status": "PLANNING",
                "to_status": "WAITING_PLAN_CONFIRM",
                "state": "WAITING_PLAN_CONFIRM",
            },
            {
                "event": "DECISION_SUBMITTED",
                "task_id": hitl_task_id,
                "pending_action_id": "pa_hitl_1",
                "decision_id": "decision_hitl_1",
                "choice": "accept",
                "selected_candidate_id": "plan_a",
                "state": "WAITING_PLAN_CONFIRM",
            },
            {
                "id": "evt-applied-1",
                "event_type": "DECISION_APPLIED",
                "task_id": hitl_task_id,
                "pending_action_id": "pa_hitl_1",
                "decision_id": "decision_hitl_1",
                "prev_status": "WAITING_PLAN_CONFIRM",
                "new_status": "PLANNED",
                "ts": "2026-03-14T10:01:00+00:00",
                "data": {
                    "choice": "accept",
                    "selected_candidate_id": "plan_a",
                    "action_type": "plan_confirm",
                },
            },
            {
                "id": "evt-exit-1",
                "event_type": "WAITING_EXIT",
                "task_id": hitl_task_id,
                "pending_action_id": "pa_hitl_1",
                "prev_status": "WAITING_PLAN_CONFIRM",
                "new_status": "PLANNED",
                "ts": "2026-03-14T10:01:01+00:00",
                "data": {
                    "action_type": "plan_confirm",
                    "action_status": "decided",
                    "waiting_state": "WAITING_PLAN_CONFIRM",
                },
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": hitl_task_id,
                "from_status": "PLANNED",
                "to_status": "RUNNING",
                "state": "RUNNING",
            },
            {
                "event": "STEP_FAILED",
                "task_id": hitl_task_id,
                "step_id": "S2",
                "tool": "nim_esmfold",
                "status": "failed",
                "failure_type": "timeout",
                "error_message": "timeout",
                "timestamp": "2026-03-14T10:02:00+00:00",
                "state": "RUNNING",
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": hitl_task_id,
                "from_status": "RUNNING",
                "to_status": "FAILED",
                "state": "FAILED",
            },
        ],
    )

    _write_jsonl(
        snapshots_dir / f"{hitl_task_id}.jsonl",
        [
            {
                "snapshot_id": "snapshot_hitl_1",
                "task_id": hitl_task_id,
                "state": "PLANNED",
                "artifacts": {
                    "pending_action": {
                        "pending_action_id": "pa_hitl_1",
                        "task_id": hitl_task_id,
                        "action_type": "plan_confirm",
                        "default_recommendation": "plan_a",
                        "candidates": [
                            {
                                "candidate_id": "plan_a",
                                "structured_payload": {
                                    "task_id": hitl_task_id,
                                    "steps": [{"id": "S1", "tool": "nim_esmfold", "inputs": {}, "metadata": {}}],
                                    "constraints": {},
                                    "metadata": {},
                                    "explanation": None,
                                },
                                "score_breakdown": {"overall": 0.88},
                                "risk_level": "low",
                                "cost_estimate": "medium",
                                "tool_id": "nim_esmfold",
                                "capability_id": "structure_prediction",
                                "io_type": "sequence_to_structure",
                                "adapter_mode": "remote",
                                "metadata": {
                                    "tool_version": "1.2.3",
                                    "source_link": "https://example.com/nim_esmfold",
                                    "provider": "nvidia_nim",
                                    "model_id": "nvidia/esmfold",
                                },
                            },
                            {
                                "candidate_id": "plan_b",
                                "structured_payload": {
                                    "task_id": hitl_task_id,
                                    "steps": [{"id": "S1", "tool": "esmfold", "inputs": {}, "metadata": {}}],
                                    "constraints": {},
                                    "metadata": {},
                                    "explanation": None,
                                },
                                "score_breakdown": {"overall": 0.7},
                                "risk_level": "low",
                                "cost_estimate": "low",
                                "tool_id": "esmfold",
                                "metadata": {},
                            },
                        ],
                    }
                },
            }
        ],
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    with (reports_dir / f"{main_task_id}.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "task_id": main_task_id,
                "structure_pdb_path": "output/pdb/task_aaaa1111_S1.pdb",
                "scores": {"plddt_mean": 0.9},
                "metadata": {"created_at": "2026-03-14T10:00:00+00:00"},
            },
            handle,
            ensure_ascii=True,
        )

    metrics_dir.mkdir(parents=True, exist_ok=True)
    with (metrics_dir / f"{main_task_id}_S1_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump({"task_id": main_task_id, "step_id": "S1", "tool": "esmfold"}, handle, ensure_ascii=True)

    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--logs-dir",
        str(logs_dir),
        "--snapshots-dir",
        str(snapshots_dir),
        "--reports-dir",
        str(reports_dir),
        "--metrics-dir",
        str(metrics_dir),
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.unit
class TestExtractTrainingSamplesScript:
    def test_extract_outputs_are_traceable(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "out"
        _run_extractor(tmp_path=tmp_path, output_dir=output_dir)

        samples = _read_jsonl(output_dir / "samples.jsonl")
        mapping_rows = _read_jsonl(output_dir / "sample_event_mapping.jsonl")
        stats = json.loads((output_dir / "stats.json").read_text(encoding="utf-8"))

        assert len(samples) == 2
        assert all("context" in sample for sample in samples)
        assert all("candidates" in sample for sample in samples)
        assert all("selected" in sample for sample in samples)
        assert all("outcome" in sample for sample in samples)
        assert all("audit_trace" in sample for sample in samples)

        hitl_sample = next(sample for sample in samples if sample["context"]["task_id"] == "task_hitl_0001")
        assert hitl_sample["selected"]["decision_id"] == "decision_hitl_1"
        assert hitl_sample["selected"]["selected_candidate_id"] == "plan_a"
        assert "evt-applied-1" in hitl_sample["audit_trace"]["event_ids"]
        assert any(c["tool_id"] == "nim_esmfold" for c in hitl_sample["candidates"])
        assert any(c["tool_version"] == "1.2.3" for c in hitl_sample["candidates"])

        assert any(row["event_id"] == "evt-applied-1" for row in mapping_rows)
        assert stats["counts"]["total_samples"] == 2
        assert stats["counts"]["samples_with_hitl"] == 1
        assert stats["traceability"]["samples_with_event_ids"] == 2
        assert stats["decision_choice_distribution"].get("accept", 0) >= 1

    def test_extract_is_reproducible_for_same_input(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "out"
        _run_extractor(tmp_path=tmp_path, output_dir=output_dir)

        first_samples = (output_dir / "samples.jsonl").read_text(encoding="utf-8")
        first_mapping = (output_dir / "sample_event_mapping.jsonl").read_text(encoding="utf-8")
        first_stats = (output_dir / "stats.json").read_text(encoding="utf-8")

        _run_extractor(tmp_path=tmp_path, output_dir=output_dir)

        second_samples = (output_dir / "samples.jsonl").read_text(encoding="utf-8")
        second_mapping = (output_dir / "sample_event_mapping.jsonl").read_text(encoding="utf-8")
        second_stats = (output_dir / "stats.json").read_text(encoding="utf-8")

        assert first_samples == second_samples
        assert first_mapping == second_mapping
        assert first_stats == second_stats
