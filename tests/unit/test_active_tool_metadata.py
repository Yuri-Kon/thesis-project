from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agents.planner import PlanStep, ToolSpec
import src.agents.planner as planner_module
from src.infra.active_tool_metadata import (
    ACTIVE_TOOL_METADATA_VERSION,
    build_high_cost_rules_from_metadata,
    load_active_tool_metadata,
    metadata_by_tool_id,
)
from src.infra.w12_vertical_experiment import normalize_high_cost_rules
from src.infra.tool_readiness import evaluate_tool_readiness


def test_active_tool_metadata_loads_required_profiles() -> None:
    profiles = metadata_by_tool_id()

    assert set(profiles) == {
        "protgpt2",
        "protein_mpnn",
        "esmfold",
        "nim_esmfold",
        "openfold",
        "biopython_qc",
        "dssp",
        "objective_ranker",
    }
    assert profiles["esmfold"].step_cost == pytest.approx(
        0.40 * 0.70 + 0.25 * 0.58 + 0.20 * 0.72 + 0.15 * 0.20
    )
    assert profiles["esmfold"].step_risk == pytest.approx(
        0.45 * 0.62 + 0.25 * 0.25 + 0.20 * 0.10 + 0.10 * 0.18
    )
    assert profiles["biopython_qc"].is_evidence_layer is True
    assert profiles["dssp"].capability_ids == (
        "quality_qc",
        "secondary_structure_annotation",
    )


def test_active_tool_metadata_rejects_invalid_prior(tmp_path: Path) -> None:
    payload = {
        "schema_version": ACTIVE_TOOL_METADATA_VERSION,
        "tools": [
            {
                "tool_id": "bad_tool",
                "capability_id": "quality_qc",
                "compute_cost_prior": 1.2,
                "latency_cost_prior": 0.1,
                "failure_impact_prior": 0.1,
                "human_dependency_prior": 0.1,
                "reliability_prior": 0.1,
                "structural_risk_prior": 0.1,
                "execution_risk_prior": 0.1,
                "safety_risk_prior": 0.1,
                "coupling_risk_prior": 0.1,
                "high_cost_flag": False,
                "evidence_role": "cheap_validation",
            }
        ],
    }
    path = tmp_path / "active_tool_metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="bad_tool.compute_cost_prior"):
        load_active_tool_metadata(path)


def test_high_cost_rules_are_derived_from_active_metadata() -> None:
    rules = build_high_cost_rules_from_metadata()
    normalized = normalize_high_cost_rules(None)

    rule_by_id = {rule["rule_id"]: rule for rule in rules}
    assert set(rule_by_id) == {"structure_mapping", "structure_refinement"}
    assert rule_by_id["structure_mapping"]["tool_ids"] == [
        "esmfold",
        "nim_esmfold",
        "openfold",
    ]
    assert rule_by_id["structure_mapping"]["cost_tier"] == "high"
    assert rule_by_id["structure_refinement"]["tool_ids"] == ["protein_mpnn"]
    assert normalized == rules


def test_planner_cost_and_risk_use_active_metadata() -> None:
    registry = [
        ToolSpec(
            id="biopython_qc",
            capabilities=("quality_qc",),
            inputs=("sequence",),
            outputs=("qc_metrics",),
            cost=1.0,
            safety_level=3,
            adapter_mode="remote",
        ),
        ToolSpec(
            id="openfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path",),
            cost=0.0,
            safety_level=1,
            adapter_mode="local",
        ),
    ]

    cheap_plan = planner_module.Plan(
        task_id="cheap",
        steps=[
            PlanStep(
                id="S1",
                tool="biopython_qc",
                inputs={"sequence": "ACDE"},
                expected_outputs=["qc_metrics"],
            )
        ]
    )
    expensive_plan = planner_module.Plan(
        task_id="expensive",
        steps=[
            PlanStep(
                id="S1",
                tool="openfold",
                inputs={"sequence": "ACDE"},
                expected_outputs=["pdb_path"],
            )
        ]
    )

    assert planner_module._derive_cost_estimate(cheap_plan, registry) == "low"
    assert planner_module._derive_risk_level(cheap_plan, registry) == "low"
    assert planner_module._derive_cost_estimate(expensive_plan, registry) == "high"
    assert planner_module._derive_risk_level(expensive_plan, registry) == "medium"


def test_tool_readiness_exposes_metadata_profile() -> None:
    payload = evaluate_tool_readiness("biopython_qc")

    assert payload["tool_id"] == "biopython_qc"
    assert payload["metadata_profile"]["tool_id"] == "biopython_qc"
    assert payload["metadata_profile"]["step_cost"] <= 0.25
    assert payload["metadata_profile"]["is_evidence_layer"] is True
