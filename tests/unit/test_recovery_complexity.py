from __future__ import annotations

import pytest

import src.agents.planner as planner_module
from src.agents.candidate_generator.recovery_complexity import (
    RECOVERY_COMPLEXITY_SCHEMA_VERSION,
    derive_recovery_complexity,
)
from src.agents.planner import ToolSpec
from src.models.contracts import Plan, PlanStep


def test_recovery_complexity_is_recoverability_complement() -> None:
    derivation = derive_recovery_complexity(
        fallback_depth=0.25,
        runtime_state={
            "local_patchability": 0.80,
            "prefix_preservability": 0.70,
            "evidence_reusability": 0.60,
        },
    )

    expected_recoverability = 0.30 * 0.25 + 0.30 * 0.80 + 0.25 * 0.70 + 0.15 * 0.60

    assert derivation.recoverability == pytest.approx(expected_recoverability)
    assert derivation.recovery_complexity == pytest.approx(1.0 - expected_recoverability)
    assert derivation.components["retry_budget_ratio"].source == "inferred"
    assert derivation.components["retry_budget_ratio"].source_fields == (
        "score_breakdown.fallback_depth",
    )


def test_observed_recovery_components_take_priority() -> None:
    derivation = derive_recovery_complexity(
        fallback_depth=0.1,
        runtime_state={
            "retry_budget_ratio": 0.9,
            "local_patchability": 0.2,
            "prefix_preservability": 0.3,
            "evidence_reusability": 0.4,
        },
    )

    assert derivation.components["retry_budget_ratio"].value == pytest.approx(0.9)
    assert derivation.components["retry_budget_ratio"].source == "observed"
    assert derivation.components["local_patchability"].source == "observed"


def test_missing_evidence_reusability_is_explicit_default() -> None:
    derivation = derive_recovery_complexity(
        fallback_depth=0.5,
        runtime_state={},
    )

    metadata = derivation.to_metadata()

    assert metadata["schema_version"] == RECOVERY_COMPLEXITY_SCHEMA_VERSION
    assert metadata["derived_from_defaults"] is True
    components = metadata["components"]
    assert isinstance(components, dict)
    evidence = components["evidence_reusability"]
    assert isinstance(evidence, dict)
    assert evidence["source"] == "default"


def test_lower_retry_budget_increases_recovery_complexity() -> None:
    high_retry = derive_recovery_complexity(
        fallback_depth=0.9,
        runtime_state={"local_patchability": 0.6, "prefix_preservability": 0.6},
    )
    low_retry = derive_recovery_complexity(
        fallback_depth=0.1,
        runtime_state={"local_patchability": 0.6, "prefix_preservability": 0.6},
    )

    assert low_retry.recovery_complexity > high_retry.recovery_complexity


def test_higher_local_patchability_lowers_recovery_complexity() -> None:
    low_patch = derive_recovery_complexity(
        fallback_depth=0.5,
        runtime_state={"local_patchability": 0.2},
    )
    high_patch = derive_recovery_complexity(
        fallback_depth=0.5,
        runtime_state={"local_patchability": 0.8},
    )

    assert high_patch.recovery_complexity < low_patch.recovery_complexity


def test_planner_score_payload_exposes_recoverability_components() -> None:
    registry = [
        ToolSpec(
            id="seqgen_a",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence",),
        ),
        ToolSpec(
            id="seqgen_b",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence",),
        ),
    ]
    payload = Plan(
        task_id="score_recovery_complexity",
        steps=[PlanStep(id="S1", tool="seqgen_a", inputs={"goal": "stable"})],
    )

    score = planner_module._score_payload(
        payload,
        registry,
        runtime_state_summary={
            "p_success": 0.6,
            "p_structural_failure": 0.1,
            "recovery_margin": 0.7,
            "expected_remaining_cost": 0.4,
            "evidence_sufficiency": 0.8,
        },
    )

    expected_recoverability = (
        0.30 * score["retry_budget_ratio"]
        + 0.30 * score["local_patchability"]
        + 0.25 * score["prefix_preservability"]
        + 0.15 * score["evidence_reusability"]
    )

    assert score["recoverability"] == pytest.approx(expected_recoverability)
    assert score["recovery_complexity"] == pytest.approx(1.0 - expected_recoverability)
    assert score["fallback_depth"] != pytest.approx(score["recoverability"])
