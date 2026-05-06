from __future__ import annotations

import pytest

import src.agents.planner as planner_module
from src.models.contracts import Plan, PlanStep
from src.models.source_refs import SOURCE_REF_ACTION_BIAS


def test_planner_shadow_runtime_adjustment_carries_action_bias() -> None:
    payload = Plan(
        task_id="action_bias_shadow",
        steps=[PlanStep(id="S1", tool="mock_tool", inputs={})],
    )

    decision = planner_module._build_runtime_shadow_decision(
        candidate_kind="patch",
        payload=payload,
        score_breakdown={
            "overall": 0.6,
            "confidence": 0.7,
            "risk": 0.5,
            "cost": 0.5,
            "fallback_depth": 0.8,
            "feasibility": 0.7,
        },
        runtime_state_summary={
            "schema_version": 1,
            "p_success": 0.6,
            "p_structural_failure": 0.2,
            "recovery_margin": 0.6,
            "expected_remaining_cost": 0.4,
            "evidence_sufficiency": 0.6,
        },
    )

    action_bias = decision.runtime_adjustment["action_bias"]

    assert isinstance(action_bias, dict)
    assert action_bias["action"] == "patch_local"
    assert action_bias["value"] == pytest.approx(decision.runtime_adjustment["value"])
    assert action_bias["factors"] == decision.rerank_reason["factors"]
    assert set(SOURCE_REF_ACTION_BIAS).issubset(set(action_bias["source_refs"]))
