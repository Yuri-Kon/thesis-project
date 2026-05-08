from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/run_sft_qlora_baseline.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_sft_qlora_baseline", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_sample(*, tool_id: str, priority: str, final_status: str = "DONE") -> dict:
    return {
        "selected": {
            "action_type": "plan_confirm",
            "choice": "accept",
            "selected_candidate_id": f"cand::{tool_id}",
            "selected_candidate": {
                "tool_id": tool_id,
                "capability_id": "structure_prediction",
                "metadata": {
                    "priority": priority,
                },
                "risk_level": "low",
                "cost_estimate": "low",
            },
        },
        "context": {
            "task_id": f"task::{tool_id}",
            "sequence": "ACDEFG",
            "status_path": ["CREATED", "RUNNING", final_status],
            "plan_metadata": {"source": "unit"},
        },
        "outcome": {
            "final_status": final_status,
            "step_failure_types": [] if final_status == "DONE" else ["tool_error"],
        },
        "quality_gate": {
            "tool_lineage": {
                "tool_id": tool_id,
                "capability_id": "structure_prediction",
                "priority": priority,
            }
        },
    }


@pytest.mark.unit
def test_select_samples_respects_priority_and_tool_cap() -> None:
    module = _load_script_module()
    rows = [
        _build_sample(tool_id="tool_a", priority="P0"),
        _build_sample(tool_id="tool_a", priority="P0"),
        _build_sample(tool_id="tool_b", priority="P1"),
        _build_sample(tool_id="tool_c", priority="P2"),
    ]

    selected, report = module.select_samples_for_training(
        rows,
        allowed_priorities=["P0", "P1"],
        max_samples_per_tool=1,
        seed=1,
    )

    assert len(selected) == 2
    tool_ids = sorted(module._sample_tool_slice(item)[0] for item in selected)
    assert tool_ids == ["tool_a", "tool_b"]
    assert report["dropped_by_priority"] == 1
    assert report["dropped_by_tool_cap"] == 1


@pytest.mark.unit
def test_sample_tool_slice_uses_quality_lineage_when_priority_missing() -> None:
    module = _load_script_module()
    sample = _build_sample(tool_id="tool_a", priority="P0")
    sample["selected"]["selected_candidate"]["metadata"] = {}
    sample["quality_gate"]["tool_lineage"]["priority"] = "P1"

    tool_id, capability_id, priority = module._sample_tool_slice(sample)

    assert tool_id == "tool_a"
    assert capability_id == "structure_prediction"
    assert priority == "P1"


@pytest.mark.unit
def test_compute_tool_slice_stats_tracks_failure_ratio() -> None:
    module = _load_script_module()
    rows = [
        _build_sample(tool_id="tool_a", priority="P0", final_status="DONE"),
        _build_sample(tool_id="tool_a", priority="P0", final_status="FAILED"),
        _build_sample(tool_id="tool_b", priority="P1", final_status="DONE"),
    ]

    stats = module.compute_tool_slice_stats(rows)

    assert stats["tool_a"].samples == 2
    assert stats["tool_a"].failure_samples == 1
    assert stats["tool_a"].failure_ratio == 0.5
    assert stats["tool_b"].sample_ratio == pytest.approx(1.0 / 3.0, rel=0, abs=1e-6)


@pytest.mark.unit
def test_model_package_manifest_contains_checksums(tmp_path: Path) -> None:
    module = _load_script_module()
    model_dir = tmp_path / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "adapter_config.json").write_text('{"x":1}', encoding="utf-8")
    (model_dir / "adapter_model.safetensors").write_bytes(b"abc")

    manifest = module.build_model_package_manifest(model_dir)

    assert manifest["root"] == str(model_dir)
    assert len(manifest["files"]) == 2
    assert all(item["sha256"] for item in manifest["files"])
    assert len(manifest["package_checksum"]) == 64


@pytest.mark.unit
def test_render_model_card_includes_tool_coverage() -> None:
    module = _load_script_module()
    model_card = module.render_model_card(
        candidate_version="v0.3.0-rc1",
        dataset_version="dataset-v1",
        run_id="run-001",
        base_model="sshleifer/tiny-gpt2",
        sampling={"allowed_priorities": ["P0", "P1"]},
        train_stats={
            "tool_a": {
                "capability_id": "quality_qc",
                "priority": "P0",
                "samples": 3,
                "sample_ratio": 0.75,
                "failure_ratio": 0.0,
            }
        },
        known_limits=["small sample"],
    )

    assert "Planner SFT Baseline" in model_card
    assert "tool_a" in model_card
    assert "dataset-v1" in model_card
    assert "small sample" in model_card


@pytest.mark.unit
def test_load_config_requires_sections(tmp_path: Path) -> None:
    module = _load_script_module()
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"run": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing config key"):
        module.load_config(path)


@pytest.mark.unit
def test_fallback_validation_rows_picks_holdout() -> None:
    module = _load_script_module()
    rows = [
        _build_sample(tool_id="tool_a", priority="P0"),
        _build_sample(tool_id="tool_b", priority="P1"),
        _build_sample(tool_id="tool_c", priority="P1"),
        _build_sample(tool_id="tool_d", priority="P1"),
    ]

    holdout = module._fallback_validation_rows(rows, seed=7, holdout_ratio=0.25)

    assert len(holdout) == 1
    assert holdout[0] in rows
