from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


AUGMENT_SCRIPT_PATH = Path("scripts/augment_requirement2_coverage.py")
QUALITY_GATE_SCRIPT_PATH = Path("scripts/quality_gate_training_data.py")


def _load_script_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
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


def _base_sample(report_path: Path, structure_path: Path) -> dict:
    return {
        "sample_id": "sample::seed",
        "context": {
            "task_id": "task_seed",
            "status_path": ["PLANNING", "PLANNED", "RUNNING", "DONE"],
            "time_window": {
                "first_ts": "2026-03-15T00:00:00+00:00",
                "last_ts": "2026-03-15T00:01:00+00:00",
            },
            "plan_metadata": {
                "kg_explanation": {
                    "steps": [
                        {
                            "step_id": "S1",
                            "tool_id": "esmfold",
                            "capabilities": [{"capability_id": "structure_prediction"}],
                        }
                    ]
                }
            },
        },
        "candidates": [
            {
                "candidate_id": "seed_cand",
                "tool_id": "esmfold",
                "capability_id": "structure_prediction",
                "adapter_mode": "local",
                "score_breakdown": {
                    "feasibility": 0.8,
                    "objective": 0.8,
                    "risk": 0.2,
                    "cost": 0.2,
                    "overall": 0.8,
                },
                "risk_level": "low",
                "cost_estimate": "low",
                "payload": {"sequence": "ACDEFG"},
            }
        ],
        "selected": {
            "selected_candidate_id": "seed_cand",
            "selected_candidate": {
                "candidate_id": "seed_cand",
                "tool_id": "esmfold",
                "capability_id": "structure_prediction",
                "payload": {"sequence": "ACDEFG"},
            },
        },
        "outcome": {
            "final_status": "DONE",
            "step_results": [
                {
                    "step_id": "S1",
                    "tool": "esmfold",
                    "status": "success",
                    "failure_type": None,
                    "error_message": None,
                }
            ],
            "step_failure_types": [],
            "report_path": str(report_path),
            "structure_pdb_path": str(structure_path),
            "scores": {"plddt_mean": 0.9},
        },
        "audit_trace": {
            "task_id": "task_seed",
            "event_ids": ["task_seed:1"],
            "decision_history": [],
            "pending_action_ids": [],
            "snapshot_ids": [],
            "decision_event_ids": [],
        },
    }


@pytest.mark.unit
def test_augment_requirement2_coverage_generates_missing_capability_samples(tmp_path: Path) -> None:
    augment_module = _load_script_module(
        AUGMENT_SCRIPT_PATH,
        "augment_requirement2_coverage",
    )
    quality_module = _load_script_module(
        QUALITY_GATE_SCRIPT_PATH,
        "quality_gate_training_data_for_addon_test",
    )

    base_samples_path = tmp_path / "base_samples.jsonl"
    base_gated_path = tmp_path / "base_gated.jsonl"
    output_dir = tmp_path / "out"
    quality_out_dir = tmp_path / "quality_out"
    reports_dir = tmp_path / "reports"
    pdb_dir = tmp_path / "pdb"
    tool_kg_path = tmp_path / "tool_kg.json"
    tool_extension_path = tmp_path / "tool_ext.json"

    reports_dir.mkdir(parents=True, exist_ok=True)
    pdb_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "seed.json"
    structure_path = pdb_dir / "seed.pdb"
    _write_json(report_path, {"sequence": "ACDEFG", "scores": {"plddt_mean": 0.9}})
    structure_path.write_text("ATOM 1\n", encoding="utf-8")

    seed_sample = _base_sample(report_path, structure_path)
    _write_jsonl(base_samples_path, [seed_sample])
    _write_jsonl(
        base_gated_path,
        [
            {
                **seed_sample,
                "quality_gate": {
                    "status": "PASS",
                    "split": "train",
                    "capability_ids": ["structure_prediction"],
                    "tool_lineage": ["esmfold"],
                    "reject_codes": [],
                },
            }
        ],
    )
    _write_json(
        tool_kg_path,
        {
            "tools": [
                {
                    "tool_id": "esmfold",
                    "capabilities": ["structure_prediction"],
                    "execution": "nextflow",
                    "version": "1.0.0",
                    "priority": "P0",
                },
                {
                    "tool_id": "protein_mpnn",
                    "capabilities": ["sequence_design"],
                    "execution": {
                        "backend": "remote_model_service",
                        "provider": "nvidia_nim",
                        "model_id": "ipd/proteinmpnn/predict",
                    },
                    "version": "1.0.0",
                    "priority": "P0",
                },
                {
                    "tool_id": "biopython_qc",
                    "capabilities": ["quality_qc"],
                    "execution": "python",
                    "version": "1.0.0",
                    "priority": "P0",
                },
                {
                    "tool_id": "objective_ranker",
                    "capabilities": ["objective_scoring"],
                    "execution": "python",
                    "version": "1.0.0",
                    "priority": "P0",
                },
            ]
        },
    )
    _write_json(tool_extension_path, {"tool_candidates": []})

    report = augment_module.augment_requirement2_coverage(
        base_samples_path=base_samples_path,
        base_gated_path=base_gated_path,
        output_dir=output_dir,
        tool_kg_path=tool_kg_path,
        tool_extension_kg_path=tool_extension_path,
    )

    assert report["requirement2_coverage"]["missing_groups_before"] == [
        "sequence_core",
        "quality_qc",
        "objective_scoring",
    ]
    assert report["requirement2_coverage"]["generated_addon_count"] == 3
    assert report["requirement2_coverage"]["missing_groups_after_expected"] == []

    addons = _read_jsonl(output_dir / "requirement2_addon_samples.jsonl")
    assert len(addons) == 3
    addon_caps = {
        row["candidates"][0]["capability_id"]
        for row in addons
    }
    assert addon_caps == {"sequence_design", "quality_qc", "objective_scoring"}

    quality_module.quality_gate_training_samples(
        samples_path=output_dir / "samples_with_addons.jsonl",
        output_dir=quality_out_dir,
        train_ratio=0.7,
        val_ratio=0.15,
        plddt_min=0.7,
        score_completeness_min=0.8,
        split_strategy="time",
    )
    gated_rows = _read_jsonl(quality_out_dir / "gated_samples.jsonl")
    status_by_sample = {row["sample_id"]: row["quality_gate"]["status"] for row in gated_rows}
    for row in addons:
        assert status_by_sample[row["sample_id"]] in {"PASS", "WARN"}
