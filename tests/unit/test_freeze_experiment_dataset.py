from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/freeze_experiment_dataset.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location("freeze_experiment_dataset", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _build_sample(
    *,
    sample_id: str,
    task_id: str,
    quality_status: str,
    split: str,
    last_ts: str,
    final_status: str,
    step_failure_types: list[str],
    pending_action_ids: list[str],
    decision_actions: list[str],
) -> dict:
    decision_history = [
        {
            "event_id": f"{sample_id}:decision:{idx}",
            "action_type": action,
        }
        for idx, action in enumerate(decision_actions, start=1)
    ]
    selected_pending = pending_action_ids[0] if pending_action_ids else None
    return {
        "sample_id": sample_id,
        "context": {
            "task_id": task_id,
            "status_path": ["CREATED", "PLANNING", "PLANNED", "RUNNING", "SUMMARIZING", final_status],
            "time_window": {"last_ts": last_ts},
        },
        "selected": {
            "pending_action_id": selected_pending,
        },
        "outcome": {
            "final_status": final_status,
            "step_failure_types": step_failure_types,
            "step_results": [],
            "scores": {},
        },
        "audit_trace": {
            "task_id": task_id,
            "event_ids": [f"{sample_id}:evt:1"],
            "pending_action_ids": pending_action_ids,
            "decision_history": decision_history,
            "decision_event_ids": [],
            "snapshot_ids": [],
        },
        "quality_gate": {
            "status": quality_status,
            "split": split,
            "reject_codes": [],
        },
    }


def _write_plan_index(path: Path) -> None:
    _write_json(
        path,
        {
            "plan_freeze_id": "plan-freeze-unit",
            "validations": {
                "data_issue_on_critical_front": True,
            },
            "schedule": [
                {"number": 170, "start": "2026-03-16", "end": "2026-03-18"},
            ],
        },
    )


@pytest.mark.unit
def test_build_issue170_freeze_ready_and_compatible(tmp_path: Path) -> None:
    module = _load_script_module()

    gated_samples_path = tmp_path / "gated_samples.jsonl"
    quality_report_path = tmp_path / "quality_gate_report.json"
    plan_index_path = tmp_path / "execution_plan_index.json"
    _write_plan_index(plan_index_path)

    rows = [
        _build_sample(
            sample_id="sample::main",
            task_id="task_main",
            quality_status="PASS",
            split="train",
            last_ts="2026-03-16T10:00:00+08:00",
            final_status="DONE",
            step_failure_types=[],
            pending_action_ids=[],
            decision_actions=[],
        ),
        _build_sample(
            sample_id="sample::recovery",
            task_id="task_recovery",
            quality_status="PASS",
            split="val",
            last_ts="2026-03-17T10:00:00+08:00",
            final_status="FAILED",
            step_failure_types=["timeout"],
            pending_action_ids=["pa_recovery_1"],
            decision_actions=["patch_confirm"],
        ),
        _build_sample(
            sample_id="sample::hitl",
            task_id="task_hitl",
            quality_status="WARN",
            split="test",
            last_ts="2026-03-18T08:00:00+08:00",
            final_status="DONE",
            step_failure_types=[],
            pending_action_ids=["pa_hitl_1"],
            decision_actions=["plan_confirm"],
        ),
        _build_sample(
            sample_id="sample::outside",
            task_id="task_outside",
            quality_status="PASS",
            split="train",
            last_ts="2026-03-19T08:00:00+08:00",
            final_status="DONE",
            step_failure_types=[],
            pending_action_ids=[],
            decision_actions=[],
        ),
    ]
    _write_jsonl(gated_samples_path, rows)
    _write_json(quality_report_path, {"summary": {"counts": {"pass": 3, "warn": 1, "block": 0}}})

    manifest = module.build_issue170_freeze(
        gated_samples_path=gated_samples_path,
        quality_report_path=quality_report_path,
        output_root=tmp_path / "out",
        freeze_id="unit-freeze-170",
        time_window_start="2026-03-16T00:00:00+08:00",
        time_window_end="2026-03-18T23:59:59+08:00",
        min_d_main=1,
        min_d_recovery=1,
        min_d_hitl=1,
        min_hitl_pending_action_rate=1.0,
        include_missing_anchor=False,
        plan_index_path=plan_index_path,
    )

    assert manifest["freeze_id"] == "unit-freeze-170"
    assert manifest["downstream_ready"]["ready"] is True
    assert manifest["datasets"]["D-main"]["count"] == 2
    assert manifest["datasets"]["D-recovery"]["count"] == 1
    assert manifest["datasets"]["D-hitl"]["count"] == 2
    assert manifest["input"]["accepted_total_after_window_filter"] == 3
    assert manifest["plan_validation"]["checked"] is True

    manifest_path = Path(manifest["manifest_path"])
    assert manifest_path.exists()

    # Optional compatibility check with issue #171 validator when module is available.
    if importlib.util.find_spec("src.infra.w12_vertical_experiment") is not None:
        validator_module = importlib.import_module("src.infra.w12_vertical_experiment")
        validated = validator_module.validate_freeze_manifest(
            manifest,
            expected_freeze_id="unit-freeze-170",
            require_downstream_ready=True,
        )
        assert validated["freeze_id"] == "unit-freeze-170"


@pytest.mark.unit
def test_build_issue170_freeze_not_ready_when_minimum_not_met(tmp_path: Path) -> None:
    module = _load_script_module()
    gated_samples_path = tmp_path / "gated_samples.jsonl"
    _write_jsonl(
        gated_samples_path,
        [
            _build_sample(
                sample_id="sample::only_main",
                task_id="task_only_main",
                quality_status="PASS",
                split="train",
                last_ts="2026-03-16T12:00:00+08:00",
                final_status="DONE",
                step_failure_types=[],
                pending_action_ids=[],
                decision_actions=[],
            )
        ],
    )

    manifest = module.build_issue170_freeze(
        gated_samples_path=gated_samples_path,
        quality_report_path=None,
        output_root=tmp_path / "out",
        freeze_id="unit-not-ready",
        time_window_start="2026-03-16T00:00:00+08:00",
        time_window_end="2026-03-18T23:59:59+08:00",
        min_d_main=1,
        min_d_recovery=1,
        min_d_hitl=1,
        min_hitl_pending_action_rate=0.9,
        include_missing_anchor=False,
        plan_index_path=None,
    )

    assert manifest["downstream_ready"]["ready"] is False
    assert manifest["downstream_ready"]["gaps"]
