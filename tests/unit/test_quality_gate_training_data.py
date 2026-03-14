from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/quality_gate_training_data.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "quality_gate_training_data",
        SCRIPT_PATH,
    )
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


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _split_of(task_id: str) -> str:
    digest = hashlib.md5(task_id.encode("utf-8")).hexdigest()
    ratio = (int(digest[:8], 16) % 10000) / 10000.0
    if ratio < 0.7:
        return "train"
    if ratio < 0.85:
        return "val"
    return "test"


def _task_id_for_split(target_split: str) -> str:
    for idx in range(20000):
        candidate = f"task_{idx:05d}"
        if _split_of(candidate) == target_split:
            return candidate
    raise AssertionError(f"no task id found for split {target_split}")


def _build_sample(
    *,
    sample_id: str,
    task_id: str,
    capability_id: str,
    report_path: Path,
    structure_path: Path,
    tool_id: str = "esmfold",
    plddt_mean: float | None = 0.9,
    qc_pass: bool | None = None,
    score_breakdown: dict | None = None,
    risk_level: str | None = "low",
    cost_estimate: str | None = "low",
    candidate_tool_id: str | None = None,
    candidate_capability_id: str | None = None,
    final_status: str = "DONE",
    step_failed: bool = False,
    failure_type: str | None = None,
    include_candidate: bool = True,
    last_ts: str = "2026-03-15T00:00:00+00:00",
) -> dict:
    if score_breakdown is None:
        score_breakdown = {
            "feasibility": 0.8,
            "objective": 0.8,
            "risk": 0.8,
            "cost": 0.8,
            "overall": 0.8,
        }

    candidate_tool = candidate_tool_id if candidate_tool_id is not None else tool_id
    candidate_capability = (
        candidate_capability_id
        if candidate_capability_id is not None
        else capability_id
    )

    candidates: list[dict] = []
    selected_candidate: dict | None = None
    if include_candidate:
        selected_candidate = {
            "candidate_id": f"{sample_id}_cand_1",
            "score_breakdown": score_breakdown,
            "risk_level": risk_level,
            "cost_estimate": cost_estimate,
            "tool_id": candidate_tool,
            "capability_id": candidate_capability,
            "payload": {"sequence": "ACDEFG"},
        }
        candidates.append(selected_candidate)

    scores: dict = {}
    if plddt_mean is not None:
        scores["plddt_mean"] = plddt_mean
    if qc_pass is not None:
        scores["qc_pass"] = qc_pass

    step_result = {
        "step_id": "S1",
        "tool": tool_id,
        "status": "failed" if step_failed else "success",
        "failure_type": failure_type,
        "error_message": "boom" if step_failed else None,
    }

    return {
        "sample_id": sample_id,
        "context": {
            "task_id": task_id,
            "status_path": ["PLANNING", "PLANNED", "RUNNING", "DONE"],
            "time_window": {"last_ts": last_ts},
            "plan_metadata": {
                "kg_explanation": {
                    "steps": [
                        {
                            "step_id": "S1",
                            "tool_id": tool_id,
                            "capabilities": [{"capability_id": capability_id}],
                        }
                    ]
                }
            },
        },
        "candidates": candidates,
        "selected": {
            "selected_candidate_id": selected_candidate["candidate_id"]
            if selected_candidate
            else None,
            "selected_candidate": selected_candidate,
        },
        "outcome": {
            "final_status": final_status,
            "step_results": [step_result],
            "step_failure_types": [failure_type] if failure_type else [],
            "report_path": str(report_path),
            "structure_pdb_path": str(structure_path),
            "scores": scores,
        },
        "audit_trace": {
            "task_id": task_id,
            "event_ids": [f"{task_id}:1"],
            "decision_history": [],
            "pending_action_ids": [],
            "snapshot_ids": [],
            "decision_event_ids": [],
        },
    }


@pytest.mark.unit
class TestQualityGateTrainingData:
    def test_quality_gate_covers_requirement2_and_failures(self, tmp_path: Path) -> None:
        module = _load_script_module()

        samples_path = tmp_path / "samples.jsonl"
        output_dir = tmp_path / "out"
        reports_dir = tmp_path / "reports"
        pdb_dir = tmp_path / "pdb"
        reports_dir.mkdir(parents=True, exist_ok=True)
        pdb_dir.mkdir(parents=True, exist_ok=True)

        shared_pdb = pdb_dir / "shared.pdb"
        shared_pdb.write_text("ATOM 1\n", encoding="utf-8")
        unique_pdb = pdb_dir / "unique.pdb"
        unique_pdb.write_text("ATOM 2\n", encoding="utf-8")

        train_task = _task_id_for_split("train")
        test_task = _task_id_for_split("test")

        report_pass = reports_dir / "pass.json"
        _write_json(
            report_pass,
            {"sequence": "ACDEFG", "scores": {"plddt_mean": 0.9}},
        )
        report_dup = reports_dir / "dup.json"
        _write_json(
            report_dup,
            {"sequence": "ACDEFG", "scores": {"plddt_mean": 0.9}},
        )
        report_warn = reports_dir / "warn.json"
        _write_json(
            report_warn,
            {"sequence": "WXYZ", "scores": {"plddt_mean": 0.4}},
        )
        report_fail = reports_dir / "fail.json"
        _write_json(
            report_fail,
            {"sequence": "TTTT", "scores": {"plddt_mean": 0.8}},
        )
        report_qc = reports_dir / "qc.json"
        _write_json(
            report_qc,
            {"sequence": "QQQQ", "scores": {"qc_pass": False}},
        )
        report_obj = reports_dir / "obj.json"
        _write_json(
            report_obj,
            {"sequence": "LLLL", "scores": {"plddt_mean": 0.8}},
        )
        report_missing_tool = reports_dir / "missing_tool.json"
        _write_json(
            report_missing_tool,
            {"sequence": "MMMM", "scores": {"plddt_mean": 0.9}},
        )

        rows = [
            _build_sample(
                sample_id="sample::pass",
                task_id=train_task,
                capability_id="structure_prediction",
                report_path=report_pass,
                structure_path=shared_pdb,
            ),
            _build_sample(
                sample_id="sample::dup",
                task_id=test_task,
                capability_id="structure_prediction",
                report_path=report_dup,
                structure_path=shared_pdb,
            ),
            _build_sample(
                sample_id="sample::warn_plddt",
                task_id="task_warn_plddt",
                capability_id="structure_prediction",
                report_path=report_warn,
                structure_path=unique_pdb,
                plddt_mean=0.4,
            ),
            _build_sample(
                sample_id="sample::missing_failure",
                task_id="task_missing_failure",
                capability_id="structure_prediction",
                report_path=report_fail,
                structure_path=unique_pdb,
                final_status="FAILED",
                step_failed=True,
                failure_type=None,
            ),
            _build_sample(
                sample_id="sample::qc_block",
                task_id="task_qc_block",
                capability_id="quality_qc",
                report_path=report_qc,
                structure_path=unique_pdb,
                plddt_mean=None,
                qc_pass=False,
            ),
            _build_sample(
                sample_id="sample::objective_block",
                task_id="task_objective_block",
                capability_id="objective_scoring",
                report_path=report_obj,
                structure_path=unique_pdb,
                score_breakdown={"overall": 0.8},
            ),
            _build_sample(
                sample_id="sample::missing_tool",
                task_id="task_missing_tool",
                capability_id="structure_prediction",
                report_path=report_missing_tool,
                structure_path=unique_pdb,
                candidate_tool_id="",
                candidate_capability_id="",
            ),
        ]
        _write_jsonl(samples_path, rows)

        report = module.quality_gate_training_samples(
            samples_path=samples_path,
            output_dir=output_dir,
            train_ratio=0.7,
            val_ratio=0.15,
            plddt_min=0.7,
            score_completeness_min=0.8,
            split_strategy="time",
        )

        gated_rows = _read_jsonl(output_dir / "gated_samples.jsonl")
        failed_rows = _read_jsonl(output_dir / "failed_samples.jsonl")
        report_file = json.loads(
            (output_dir / "quality_gate_report.json").read_text(encoding="utf-8")
        )

        assert report["summary"]["counts"]["pass"] >= 1
        assert report["summary"]["counts"]["warn"] >= 1
        assert report["summary"]["counts"]["block"] >= 1
        assert report["summary"]["rates"]["pass_rate"] > 0
        assert "duplicate_rate" in report["summary"]["rates"]
        assert "missing_rate" in report["summary"]["rates"]

        assert any(
            "DUPLICATE_CROSS_TOOL" in row["quality_gate"]["reject_codes"]
            for row in gated_rows
        )
        assert any(
            "REQ2_QC_BLOCKED" in row["quality_gate"]["reject_codes"]
            for row in gated_rows
        )
        assert any(
            "REQ2_SCORE_COMPLETENESS_BELOW_THRESHOLD"
            in row["quality_gate"]["reject_codes"]
            for row in gated_rows
        )
        assert any(
            "MISSING_FAILURE_TYPE" in row["quality_gate"]["reject_codes"]
            for row in gated_rows
        )
        assert any(
            "REQ2_PLDDT_BELOW_THRESHOLD" in row["quality_gate"]["reject_codes"]
            for row in gated_rows
        )

        assert any(
            row["quality_gate"]["split"] in {"train", "val", "test"}
            for row in gated_rows
        )
        assert failed_rows, "blocked rows should be exported"
        assert any(
            isinstance(row.get("tool_context"), list) and row["tool_context"]
            for row in failed_rows
        )

        assert report_file["summary"]["major_issue_distribution"] == report["summary"][
            "major_issue_distribution"
        ]

    def test_cli_is_reproducible_and_split_stable(self, tmp_path: Path) -> None:
        samples_path = tmp_path / "samples.jsonl"
        output_dir = tmp_path / "out"
        reports_dir = tmp_path / "reports"
        pdb_dir = tmp_path / "pdb"
        reports_dir.mkdir(parents=True, exist_ok=True)
        pdb_dir.mkdir(parents=True, exist_ok=True)

        report_a = reports_dir / "a.json"
        report_b = reports_dir / "b.json"
        _write_json(report_a, {"sequence": "AAAA", "scores": {"plddt_mean": 0.9}})
        _write_json(report_b, {"sequence": "BBBB", "scores": {"plddt_mean": 0.9}})

        pdb_a = pdb_dir / "a.pdb"
        pdb_b = pdb_dir / "b.pdb"
        pdb_a.write_text("ATOM A\n", encoding="utf-8")
        pdb_b.write_text("ATOM B\n", encoding="utf-8")

        rows = [
            _build_sample(
                sample_id="sample::s1",
                task_id="task_same_split",
                capability_id="structure_prediction",
                report_path=report_a,
                structure_path=pdb_a,
            ),
            _build_sample(
                sample_id="sample::s2",
                task_id="task_same_split",
                capability_id="structure_prediction",
                report_path=report_b,
                structure_path=pdb_b,
            ),
        ]
        _write_jsonl(samples_path, rows)

        cmd = [
            sys.executable,
            str(SCRIPT_PATH),
            "--samples-path",
            str(samples_path),
            "--output-dir",
            str(output_dir),
            "--train-ratio",
            "0.70",
            "--val-ratio",
            "0.15",
            "--plddt-min",
            "0.70",
            "--score-completeness-min",
            "0.80",
            "--split-strategy",
            "time",
        ]

        first = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert first.returncode == 0, first.stderr
        first_gated = (output_dir / "gated_samples.jsonl").read_text(encoding="utf-8")
        first_failed = (output_dir / "failed_samples.jsonl").read_text(encoding="utf-8")
        first_report = (output_dir / "quality_gate_report.json").read_text(encoding="utf-8")

        second = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert second.returncode == 0, second.stderr
        second_gated = (output_dir / "gated_samples.jsonl").read_text(encoding="utf-8")
        second_failed = (output_dir / "failed_samples.jsonl").read_text(encoding="utf-8")
        second_report = (output_dir / "quality_gate_report.json").read_text(encoding="utf-8")

        assert first_gated == second_gated
        assert first_failed == second_failed
        assert first_report == second_report

        gated_rows = _read_jsonl(output_dir / "gated_samples.jsonl")
        splits = {row["quality_gate"]["split"] for row in gated_rows}
        assert len(splits) == 1

    def test_fail_on_block_returns_nonzero(self, tmp_path: Path) -> None:
        samples_path = tmp_path / "samples.jsonl"
        output_dir = tmp_path / "out"
        reports_dir = tmp_path / "reports"
        pdb_dir = tmp_path / "pdb"
        reports_dir.mkdir(parents=True, exist_ok=True)
        pdb_dir.mkdir(parents=True, exist_ok=True)

        report_path = reports_dir / "blocked.json"
        pdb_path = pdb_dir / "blocked.pdb"
        _write_json(report_path, {"sequence": "AAAA", "scores": {"plddt_mean": 0.9}})
        pdb_path.write_text("ATOM\n", encoding="utf-8")

        row = _build_sample(
            sample_id="sample::blocked",
            task_id="task_blocked",
            capability_id="structure_prediction",
            report_path=report_path,
            structure_path=pdb_path,
            candidate_tool_id="",
            candidate_capability_id="",
        )
        _write_jsonl(samples_path, [row])

        cmd = [
            sys.executable,
            str(SCRIPT_PATH),
            "--samples-path",
            str(samples_path),
            "--output-dir",
            str(output_dir),
            "--fail-on-block",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 2
