from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/freeze_sft_dataset_v1.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location("freeze_sft_dataset_v1", SCRIPT_PATH)
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


def _build_sample(
    *,
    sample_id: str,
    split: str,
    status: str,
    tool_id: str,
    capability_id: str,
    adapter_mode: str,
    provider: str | None = None,
    model_id: str | None = None,
) -> dict:
    metadata: dict[str, str] = {"adapter_mode": adapter_mode}
    if provider:
        metadata["provider"] = provider
    if model_id:
        metadata["model_id"] = model_id

    candidate = {
        "candidate_id": f"{sample_id}_cand",
        "tool_id": tool_id,
        "capability_id": capability_id,
        "adapter_mode": adapter_mode,
        "metadata": metadata,
        "score_breakdown": {
            "feasibility": 0.9,
            "objective": 0.8,
            "risk": 0.2,
            "cost": 0.3,
            "overall": 0.8,
        },
        "risk_level": "low",
        "cost_estimate": "low",
    }

    return {
        "sample_id": sample_id,
        "context": {"task_id": f"task_{sample_id}"},
        "candidates": [candidate],
        "selected": {
            "selected_candidate_id": candidate["candidate_id"],
            "selected_candidate": candidate,
        },
        "outcome": {
            "final_status": "DONE",
            "step_results": [],
            "scores": {},
        },
        "audit_trace": {"event_ids": [], "decision_history": []},
        "quality_gate": {
            "status": status,
            "split": split,
            "capability_ids": [capability_id],
            "tool_lineage": [tool_id],
            "reject_codes": [],
        },
    }


def _build_tool_kg() -> dict:
    return {
        "tools": [
            {
                "tool_id": "esmfold",
                "capabilities": ["structure_prediction"],
                "execution": "nextflow",
                "version": "1.0.0",
                "priority": "P0",
            },
            {
                "tool_id": "objective_ranker",
                "capabilities": ["objective_scoring"],
                "execution": "python",
                "version": "0.1.0",
                "priority": "P0",
            },
            {
                "tool_id": "biopython_qc",
                "capabilities": ["quality_qc"],
                "execution": "python",
                "version": "0.4.0",
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
                "version": "1.2.0",
                "priority": "P0",
            },
        ]
    }


def _build_tool_extension() -> dict:
    return {
        "tool_candidates": [
            {
                "tool_id": "esmfold",
                "priority": "P0",
                "adapter_modes": ["local"],
                "capability_id": ["structure_prediction"],
            }
        ]
    }


@pytest.mark.unit
class TestFreezeSftDatasetV1:
    def test_freeze_outputs_manifest_and_requirement2_artifacts(self, tmp_path: Path) -> None:
        module = _load_script_module()

        gated_samples_path = tmp_path / "gated_samples.jsonl"
        quality_report_path = tmp_path / "quality_gate_report.json"
        output_root = tmp_path / "output"
        tool_kg_path = tmp_path / "tool_kg.json"
        tool_extension_path = tmp_path / "tool_ext.json"
        config_template_path = tmp_path / "configs" / "training" / "dataset_v1.example.json"

        rows = [
            _build_sample(
                sample_id="sample_s1",
                split="train",
                status="PASS",
                tool_id="esmfold",
                capability_id="structure_prediction",
                adapter_mode="local",
            ),
            _build_sample(
                sample_id="sample_s2",
                split="val",
                status="WARN",
                tool_id="objective_ranker",
                capability_id="objective_scoring",
                adapter_mode="local",
            ),
            _build_sample(
                sample_id="sample_s3",
                split="test",
                status="PASS",
                tool_id="biopython_qc",
                capability_id="quality_qc",
                adapter_mode="local",
            ),
            _build_sample(
                sample_id="sample_s4",
                split="train",
                status="PASS",
                tool_id="protein_mpnn",
                capability_id="sequence_design",
                adapter_mode="remote",
                provider="nvidia_nim",
                model_id="ipd/proteinmpnn/predict",
            ),
            _build_sample(
                sample_id="sample_s5",
                split="train",
                status="BLOCK",
                tool_id="esmfold",
                capability_id="structure_prediction",
                adapter_mode="local",
            ),
        ]
        _write_jsonl(gated_samples_path, rows)
        _write_json(quality_report_path, {"summary": {"counts": {"pass": 3, "warn": 1, "block": 1}}})
        _write_json(tool_kg_path, _build_tool_kg())
        _write_json(tool_extension_path, _build_tool_extension())

        manifest = module.freeze_sft_dataset_v1(
            gated_samples_path=gated_samples_path,
            quality_report_path=quality_report_path,
            output_root=output_root,
            dataset_version="unit-v1",
            previous_manifest_path=None,
            tool_kg_path=tool_kg_path,
            tool_extension_kg_path=tool_extension_path,
            config_template_path=config_template_path,
        )

        freeze_dir = output_root / "unit-v1"
        assert freeze_dir.exists()
        assert manifest["dataset_version"] == "unit-v1"
        assert manifest["dataset_counts"]["accepted_total"] == 4
        assert manifest["dataset_counts"]["blocked_total"] == 1
        assert manifest["requirement2"]["p0_core_minimum_coverage"]["satisfied"] is True

        matrix = json.loads((freeze_dir / "tool_coverage_matrix.json").read_text(encoding="utf-8"))
        assert matrix["structure_prediction"]["esmfold"]["local"]["sample_count"] == 1
        assert matrix["sequence_design"]["protein_mpnn"]["remote"]["sample_count"] == 1

        p0_tools = {
            item["tool_id"]: item
            for item in manifest["requirement2"]["p0_tool_registry"]
        }
        assert p0_tools["protein_mpnn"]["provider"] == "nvidia_nim"
        assert p0_tools["protein_mpnn"]["model_id"] == "ipd/proteinmpnn/predict"

        accepted = _read_jsonl(freeze_dir / "accepted_samples.jsonl")
        assert len(accepted) == 4
        assert all(row["quality_gate"]["status"] in {"PASS", "WARN"} for row in accepted)
        assert len(_read_jsonl(freeze_dir / "train.jsonl")) == 2
        assert len(_read_jsonl(freeze_dir / "val.jsonl")) == 1
        assert len(_read_jsonl(freeze_dir / "test.jsonl")) == 1

        field_dict = json.loads((freeze_dir / "field_dictionary.json").read_text(encoding="utf-8"))
        assert field_dict["total_fields"] > 0
        assert any(item["path"] == "sample.quality_gate.status" for item in field_dict["fields"])

        training_reader_config = json.loads(
            (freeze_dir / "training_reader_config.json").read_text(encoding="utf-8")
        )
        assert training_reader_config["dataset_version"] == "unit-v1"
        assert config_template_path.exists()

    def test_freeze_is_immutable_when_fingerprint_changes(self, tmp_path: Path) -> None:
        module = _load_script_module()

        gated_samples_path = tmp_path / "gated_samples.jsonl"
        quality_report_path = tmp_path / "quality_gate_report.json"
        output_root = tmp_path / "output"
        tool_kg_path = tmp_path / "tool_kg.json"
        tool_extension_path = tmp_path / "tool_ext.json"
        config_template_path = tmp_path / "configs" / "training" / "dataset_v1.example.json"

        rows = [
            _build_sample(
                sample_id="sample_s1",
                split="train",
                status="PASS",
                tool_id="esmfold",
                capability_id="structure_prediction",
                adapter_mode="local",
            )
        ]
        _write_jsonl(gated_samples_path, rows)
        _write_json(quality_report_path, {"summary": {"counts": {"pass": 1}}})
        _write_json(tool_kg_path, _build_tool_kg())
        _write_json(tool_extension_path, _build_tool_extension())

        first = module.freeze_sft_dataset_v1(
            gated_samples_path=gated_samples_path,
            quality_report_path=quality_report_path,
            output_root=output_root,
            dataset_version="unit-v1",
            previous_manifest_path=None,
            tool_kg_path=tool_kg_path,
            tool_extension_kg_path=tool_extension_path,
            config_template_path=config_template_path,
        )
        second = module.freeze_sft_dataset_v1(
            gated_samples_path=gated_samples_path,
            quality_report_path=quality_report_path,
            output_root=output_root,
            dataset_version="unit-v1",
            previous_manifest_path=None,
            tool_kg_path=tool_kg_path,
            tool_extension_kg_path=tool_extension_path,
            config_template_path=config_template_path,
        )
        assert second["dataset_fingerprint"] == first["dataset_fingerprint"]

        rows.append(
            _build_sample(
                sample_id="sample_s2",
                split="val",
                status="PASS",
                tool_id="objective_ranker",
                capability_id="objective_scoring",
                adapter_mode="local",
            )
        )
        _write_jsonl(gated_samples_path, rows)

        with pytest.raises(FileExistsError):
            module.freeze_sft_dataset_v1(
                gated_samples_path=gated_samples_path,
                quality_report_path=quality_report_path,
                output_root=output_root,
                dataset_version="unit-v1",
                previous_manifest_path=None,
                tool_kg_path=tool_kg_path,
                tool_extension_kg_path=tool_extension_path,
                config_template_path=config_template_path,
            )

    def test_freeze_records_delta_from_previous_manifest(self, tmp_path: Path) -> None:
        module = _load_script_module()

        gated_samples_path = tmp_path / "gated_samples.jsonl"
        quality_report_path = tmp_path / "quality_gate_report.json"
        output_root = tmp_path / "output"
        tool_kg_path = tmp_path / "tool_kg.json"
        tool_extension_path = tmp_path / "tool_ext.json"
        config_template_path = tmp_path / "configs" / "training" / "dataset_v1.example.json"

        previous_freeze_dir = output_root / "old-v1"
        previous_freeze_dir.mkdir(parents=True, exist_ok=True)
        previous_stats_path = previous_freeze_dir / "dataset_stats.json"
        previous_matrix_path = previous_freeze_dir / "tool_coverage_matrix.json"
        previous_manifest_path = previous_freeze_dir / "manifest.json"

        _write_json(
            previous_stats_path,
            {
                "capability_distribution": {"structure_prediction": 1},
                "split_counts": {"train": 1},
            },
        )
        _write_json(
            previous_matrix_path,
            {
                "structure_prediction": {
                    "esmfold": {"local": {"sample_count": 1, "occurrence_count": 1}}
                }
            },
        )
        _write_json(
            previous_manifest_path,
            {
                "dataset_version": "old-v1",
                "dataset_counts": {"input_total": 1, "accepted_total": 1, "blocked_total": 0},
                "split_counts": {"train": 1},
                "artifacts": {
                    "dataset_stats_path": str(previous_stats_path),
                    "tool_coverage_matrix_path": str(previous_matrix_path),
                },
                "requirement2": {
                    "p0_core_minimum_coverage": {
                        "satisfied": False,
                        "missing_groups": ["sequence_core", "quality_qc", "objective_scoring"],
                    }
                },
            },
        )

        rows = [
            _build_sample(
                sample_id="sample_s1",
                split="train",
                status="PASS",
                tool_id="esmfold",
                capability_id="structure_prediction",
                adapter_mode="local",
            ),
            _build_sample(
                sample_id="sample_s2",
                split="val",
                status="PASS",
                tool_id="objective_ranker",
                capability_id="objective_scoring",
                adapter_mode="local",
            ),
            _build_sample(
                sample_id="sample_s3",
                split="test",
                status="PASS",
                tool_id="biopython_qc",
                capability_id="quality_qc",
                adapter_mode="local",
            ),
            _build_sample(
                sample_id="sample_s4",
                split="train",
                status="PASS",
                tool_id="protein_mpnn",
                capability_id="sequence_design",
                adapter_mode="remote",
                provider="nvidia_nim",
                model_id="ipd/proteinmpnn/predict",
            ),
        ]
        _write_jsonl(gated_samples_path, rows)
        _write_json(quality_report_path, {"summary": {"counts": {"pass": 4}}})
        _write_json(tool_kg_path, _build_tool_kg())
        _write_json(tool_extension_path, _build_tool_extension())

        manifest = module.freeze_sft_dataset_v1(
            gated_samples_path=gated_samples_path,
            quality_report_path=quality_report_path,
            output_root=output_root,
            dataset_version="new-v1-1",
            previous_manifest_path=previous_manifest_path,
            tool_kg_path=tool_kg_path,
            tool_extension_kg_path=tool_extension_path,
            config_template_path=config_template_path,
        )

        assert "delta_from_previous" in manifest
        delta = manifest["delta_from_previous"]
        assert delta["previous_dataset_version"] == "old-v1"
        assert delta["dataset_counts_delta"]["accepted_total"] == 3
        assert delta["p0_core_coverage_change"]["previous_satisfied"] is False
        assert delta["p0_core_coverage_change"]["current_satisfied"] is True
        assert any(
            key.startswith("quality_qc|biopython_qc|")
            for key in delta["tool_coverage_matrix_delta"]["added_keys"]
        )

    def test_cli_runs_successfully(self, tmp_path: Path) -> None:
        gated_samples_path = tmp_path / "gated_samples.jsonl"
        quality_report_path = tmp_path / "quality_gate_report.json"
        output_root = tmp_path / "output"
        tool_kg_path = tmp_path / "tool_kg.json"
        tool_extension_path = tmp_path / "tool_ext.json"
        config_template_path = tmp_path / "configs" / "training" / "dataset_v1.example.json"

        rows = [
            _build_sample(
                sample_id="sample_s1",
                split="train",
                status="PASS",
                tool_id="esmfold",
                capability_id="structure_prediction",
                adapter_mode="local",
            )
        ]
        _write_jsonl(gated_samples_path, rows)
        _write_json(quality_report_path, {"summary": {"counts": {"pass": 1}}})
        _write_json(tool_kg_path, _build_tool_kg())
        _write_json(tool_extension_path, _build_tool_extension())

        cmd = [
            sys.executable,
            str(SCRIPT_PATH),
            "--gated-samples-path",
            str(gated_samples_path),
            "--quality-report-path",
            str(quality_report_path),
            "--output-root",
            str(output_root),
            "--dataset-version",
            "unit-cli-v1",
            "--tool-kg-path",
            str(tool_kg_path),
            "--tool-extension-kg-path",
            str(tool_extension_path),
            "--config-template-path",
            str(config_template_path),
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "unit-cli-v1" in result.stdout

    def test_cli_fail_on_missing_p0_core_returns_nonzero(self, tmp_path: Path) -> None:
        gated_samples_path = tmp_path / "gated_samples.jsonl"
        quality_report_path = tmp_path / "quality_gate_report.json"
        output_root = tmp_path / "output"
        tool_kg_path = tmp_path / "tool_kg.json"
        tool_extension_path = tmp_path / "tool_ext.json"
        config_template_path = tmp_path / "configs" / "training" / "dataset_v1.example.json"

        rows = [
            _build_sample(
                sample_id="sample_s1",
                split="train",
                status="PASS",
                tool_id="esmfold",
                capability_id="structure_prediction",
                adapter_mode="local",
            )
        ]
        _write_jsonl(gated_samples_path, rows)
        _write_json(quality_report_path, {"summary": {"counts": {"pass": 1}}})
        _write_json(tool_kg_path, _build_tool_kg())
        _write_json(tool_extension_path, _build_tool_extension())

        cmd = [
            sys.executable,
            str(SCRIPT_PATH),
            "--gated-samples-path",
            str(gated_samples_path),
            "--quality-report-path",
            str(quality_report_path),
            "--output-root",
            str(output_root),
            "--dataset-version",
            "unit-cli-v2",
            "--tool-kg-path",
            str(tool_kg_path),
            "--tool-extension-kg-path",
            str(tool_extension_path),
            "--config-template-path",
            str(config_template_path),
            "--fail-on-missing-p0-core",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 3
