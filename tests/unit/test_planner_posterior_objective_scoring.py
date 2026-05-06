from __future__ import annotations

import pytest

from src.agents.planner import PlannerAgent, ToolSpec
from src.agents.candidate_generator.builder import objective_metadata_from_payload_metadata
from src.models.contracts import Plan, PlanStep


def _registry() -> list[ToolSpec]:
    return [
        ToolSpec(
            id="objective_ranker",
            capabilities=("objective_scoring",),
            inputs=("candidates",),
            outputs=("top_k", "posterior_objective"),
            cost=0.4,
            safety_level=1,
            io_type="candidates_to_objective_scores_topk",
            adapter_mode="local",
            priority="P0",
        ),
    ]


def _plan(metadata: dict[str, object] | None = None) -> Plan:
    return Plan(
        task_id="posterior_scoring",
        steps=[
            PlanStep(
                id="S1",
                tool="objective_ranker",
                inputs={"candidates": []},
            )
        ],
        metadata=metadata or {},
    )


def test_score_payload_uses_sufficient_posterior_objective() -> None:
    planner = PlannerAgent(tool_registry=_registry())
    plan = _plan(
        {
            "posterior_objective": {
                "schema_version": "posterior_objective.v1",
                "aggregate_score": 0.91,
                "evidence_sufficiency": 0.73,
                "evidence_status": "direct",
            }
        }
    )

    score = planner.score_candidate_payload(plan)

    assert score["objective"] == pytest.approx(0.91)
    assert score["evidence_sufficiency"] == pytest.approx(0.73)
    assert score["overall"] < 0.91


def test_score_payload_blends_degraded_posterior_objective_without_double_bonus() -> None:
    planner = PlannerAgent(tool_registry=_registry())
    plan = _plan(
        {
            "posterior_objective": {
                "schema_version": "posterior_objective.v1",
                "aggregate_score": 0.20,
                "evidence_sufficiency": 0.10,
                "evidence_status": "degraded",
            }
        }
    )

    score = planner.score_candidate_payload(plan)

    avg_cost = 1.0 - score["cost"]
    prior_without_objective_ranker_bonus = 1.0 - avg_cost * 0.3
    expected = 0.70 * prior_without_objective_ranker_bonus + 0.30 * 0.20
    assert score["objective"] == pytest.approx(expected)
    assert score["objective"] < prior_without_objective_ranker_bonus
    assert score["evidence_sufficiency"] == pytest.approx(0.10)


def test_score_payload_keeps_prior_goal_fit_when_posterior_absent() -> None:
    planner = PlannerAgent(tool_registry=_registry())

    score = planner.score_candidate_payload(_plan())

    avg_cost = 1.0 - score["cost"]
    prior_with_objective_ranker_bonus = 1.0 - avg_cost * 0.3 + 0.08
    assert score["objective"] == pytest.approx(min(1.0, prior_with_objective_ranker_bonus))
    assert score["evidence_sufficiency"] == pytest.approx(0.5)


def test_score_payload_accepts_legacy_posterior_score_metadata() -> None:
    planner = PlannerAgent(tool_registry=_registry())
    plan = _plan(
        {
            "posterior_score": {
                "schema_version": "posterior_score.v1",
                "aggregate_score": 0.77,
                "evidence_sufficiency": 0.35,
                "evidence_status": "partial",
            }
        }
    )

    score = planner.score_candidate_payload(plan)

    assert score["objective"] == pytest.approx(0.77)
    assert score["evidence_sufficiency"] == pytest.approx(0.35)


def test_candidate_metadata_records_objective_provenance() -> None:
    metadata = objective_metadata_from_payload_metadata(
        {
            "posterior_objective": {
                "schema_version": "posterior_objective.v1",
                "aggregate_score": 0.82,
                "evidence_sufficiency": 0.44,
                "evidence_status": "proxy",
            }
        }
    )

    assert metadata["objective_score_source"] == "posterior_objective"
    assert metadata["objective_evidence_sufficiency"] == pytest.approx(0.44)
    assert metadata["objective_evidence_status"] == "proxy"
    posterior = metadata["posterior_objective"]
    assert isinstance(posterior, dict)
    assert posterior["schema_version"] == "posterior_objective.v1"


def test_candidate_metadata_marks_degraded_proxy_source() -> None:
    metadata = objective_metadata_from_payload_metadata(
        {
            "posterior_score": {
                "schema_version": "posterior_score.v1",
                "aggregate_score": 0.82,
                "evidence_sufficiency": 0.12,
                "evidence_status": "degraded",
            }
        }
    )

    assert metadata["objective_score_source"] == "degraded_proxy"
    assert metadata["objective_evidence_sufficiency"] == pytest.approx(0.12)
