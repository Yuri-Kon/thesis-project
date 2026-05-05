from __future__ import annotations

from dataclasses import dataclass

import src.agents.planner as planner_module
from src.agents.candidate_generator.generator import (
    CANDIDATE_FEASIBILITY_METADATA_KEY,
    TOPK_DIVERSITY_METADATA_KEY,
    CandidateGenerator,
)
from src.agents.candidate_generator.recovery_complexity import (
    RECOVERY_COMPLEXITY_METADATA_KEY,
)
from src.agents.candidate_generator.models import (
    CandidateGenerationInput,
    CandidateGeneratorHooks,
    CandidatePayload,
)
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import (
    TOOL_READINESS_METADATA_KEY,
    Plan,
    PlanStep,
    ProteinDesignTask,
)


@dataclass(frozen=True)
class _ShadowDecision:
    shadow_score: dict[str, object]
    final_score: dict[str, object]
    runtime_adjustment: dict[str, object]
    rerank_reason: dict[str, object]
    shadow_action: str
    shadow_reason: str
    explanation_fragment: str


def _registry() -> list[ToolSpec]:
    return [
        ToolSpec(
            id="seqgen_a",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence",),
            cost=0.2,
            safety_level=1,
            io_type="goal_to_sequence",
            adapter_mode="local",
            priority="P0",
        ),
        ToolSpec(
            id="seqgen_b",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence",),
            cost=0.3,
            safety_level=1,
            io_type="goal_to_sequence",
            adapter_mode="local",
            priority="P1",
        ),
    ]


def _diverse_registry() -> list[ToolSpec]:
    return [
        *_registry(),
        ToolSpec(
            id="qc_a",
            capabilities=("quality_qc",),
            inputs=("goal",),
            outputs=("qc_report",),
            cost=0.4,
            safety_level=1,
            io_type="goal_to_qc",
            adapter_mode="local",
            priority="P1",
        ),
    ]


def _ready_capability(capability_id: str) -> dict:
    return {
        "capability_id": capability_id,
        "status": "ready",
        "reason": "unit test readiness",
        "degraded_reasons": [],
        "tools": [
            {
                "tool_id": "seqgen_a",
                "status": "ready",
                "reason": "ready",
            },
            {
                "tool_id": "seqgen_b",
                "status": "ready",
                "reason": "ready",
            },
        ],
    }


def _kg() -> dict:
    return {
        "tools": [
            {
                "id": "seqgen_a",
                "capabilities": ["sequence_generation"],
                "io": {
                    "io_type_id": "goal_to_sequence",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str"},
                },
                "execution": "python",
                "constraints": {},
            },
            {
                "id": "seqgen_b",
                "capabilities": ["sequence_generation"],
                "io": {
                    "io_type_id": "goal_to_sequence",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str"},
                },
                "execution": "python",
                "constraints": {},
            },
        ]
    }


def _direct_generator(
    *,
    readiness_status: str = "ready",
    unavailable_tools: set[str] | None = None,
    score_overrides: dict[str, float] | None = None,
) -> CandidateGenerator:
    unavailable_tool_ids = unavailable_tools or set()
    score_by_tool = score_overrides or {}

    def score_payload(payload: Plan, *_args: object, **_kwargs: object) -> dict[str, float]:
        primary_tool = payload.steps[0].tool
        overall = score_by_tool.get(
            primary_tool,
            0.9 if primary_tool == "seqgen_a" else 0.8,
        )
        return {
            "feasibility": 0.9,
            "objective": 0.8,
            "risk": 0.8,
            "cost": 0.8,
            "confidence": 0.8,
            "overall": overall,
        }

    def score_summary(score_breakdown: dict[str, float]) -> dict[str, object]:
        return {"value": score_breakdown["overall"], "source": "unit_test"}

    def readiness_metadata(*, tool_id: str, capability_id: str) -> dict[str, object]:
        status = "unavailable" if tool_id in unavailable_tool_ids else readiness_status
        return {
            TOOL_READINESS_METADATA_KEY: {
                "tool_id": tool_id,
                "status": status,
                "capability_id": capability_id,
            }
        }

    def passthrough_shadow(score_breakdown: dict[str, float]) -> _ShadowDecision:
        return _ShadowDecision(
            shadow_score={"value": score_breakdown["overall"], "source": "unit_test"},
            final_score={"value": score_breakdown["overall"], "source": "unit_test"},
            runtime_adjustment={"value": 0.0, "source": "unit_test"},
            rerank_reason={"code": "passthrough", "message": "passthrough"},
            shadow_action="continue",
            shadow_reason="no runtime state",
            explanation_fragment="No runtime rerank applied.",
        )

    def extract_score_value(candidate: object, key: str) -> float:
        metadata = getattr(candidate, "metadata")
        summary = metadata[key]
        if isinstance(summary, dict):
            value = summary.get("value")
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    return CandidateGenerator(
        CandidateGeneratorHooks(
            canonical_payload_fingerprint=lambda payload, tool_id, bucket: (
                f"{tool_id}:{bucket}:{payload.steps[0].id}"
            ),
            resolve_score_weights=lambda _constraints: {},
            score_payload=score_payload,
            primary_capability=lambda spec: spec.capabilities[0] if spec else "unknown",
            derive_cost_estimate=lambda _payload, _registry: "low",
            derive_risk_level=lambda _payload, _registry: "low",
            stable_candidate_id=lambda kind, _payload, tool_id, bucket: (
                f"{kind}:{tool_id}:{bucket}"
            ),
            build_s5_scoring_contract=lambda _weights: {"weights": {}},
            build_static_score_summary=score_summary,
            build_action_score_summary=score_summary,
            candidate_readiness_metadata=readiness_metadata,
            build_candidate_summary=lambda payload: payload.steps[0].tool,
            extract_patch_candidate_metadata=lambda _payload: {},
            extract_plan_candidate_metadata=lambda _payload: {},
            normalize_runtime_state_summary_input=lambda _state: None,
            build_shadow_passthrough_decision=passthrough_shadow,
            build_runtime_shadow_decision=lambda **_kwargs: passthrough_shadow(
                {"overall": 0.0}
            ),
            priority_rank=lambda _priority: 0,
            patch_layer_rank=lambda _payload: 0,
            extract_score_value=extract_score_value,
            build_default_recommendation_reason=lambda **kwargs: {
                "candidate_id": kwargs["candidate_id"]
            },
            summarize_rerank_reason=lambda _candidate: "rerank summary",
        )
    )


def _plan(tool_id: str, *, inputs: dict[str, object] | None = None) -> Plan:
    return Plan(
        task_id="direct_candidate_generator",
        steps=[PlanStep(id=f"S_{tool_id}", tool=tool_id, inputs=inputs or {})],
    )


def test_plan_top_k_uses_candidate_generator_context(monkeypatch):
    monkeypatch.setenv("PLANNER_LLM_PROVIDER", "none")
    monkeypatch.setattr(planner_module, "load_tool_kg", _kg)
    monkeypatch.setattr(
        planner_module,
        "build_capability_readiness_snapshot",
        _ready_capability,
    )
    planner = PlannerAgent(tool_registry=_registry())
    task = ProteinDesignTask(
        task_id="candidate_generator_context",
        goal="design stable peptide",
        constraints={
            "goal_type": "legacy_sequence_generation",
            "inputs": {"sequence": "AAAA"},
            "budget": {"cost_cap": 0.5},
        },
        metadata={"planner_capability_hints": ["sequence_generation"]},
    )

    topk = planner.plan_top_k(task, k=3)

    assert topk.default_suggestion == topk.default_recommendation
    assert "CandidateGenerator" in topk.explanation
    assert "Candidate differences:" in topk.explanation
    assert topk.candidates
    candidate = topk.candidates[0]
    assert candidate.metadata["candidate_generator"]["capability_hints"] == [
        "sequence_generation"
    ]
    feasibility = candidate.metadata[CANDIDATE_FEASIBILITY_METADATA_KEY]
    assert isinstance(feasibility, dict)
    assert feasibility["hard_feasible"] is True
    assert feasibility["auto_executable"] is True
    assert feasibility["allowed_for_default_recommendation"] is True
    assert "feasibility" not in candidate.metadata
    assert candidate.score_breakdown["recovery_complexity"] >= 0.0
    recovery_source = candidate.metadata[RECOVERY_COMPLEXITY_METADATA_KEY]
    assert isinstance(recovery_source, dict)
    assert recovery_source["recovery_complexity"] == candidate.score_breakdown[
        "recovery_complexity"
    ]
    assert recovery_source["derived_from"] == [
        "retry_budget_ratio",
        "local_patchability",
        "prefix_preservability",
        "evidence_reusability",
    ]
    assert candidate.score_breakdown["capability_hint_match"] == 1.0


def test_plan_top_k_filters_blocked_tools_before_default_selection(monkeypatch):
    monkeypatch.setenv("PLANNER_LLM_PROVIDER", "none")
    monkeypatch.setattr(planner_module, "load_tool_kg", _kg)
    monkeypatch.setattr(
        planner_module,
        "build_capability_readiness_snapshot",
        _ready_capability,
    )
    planner = PlannerAgent(tool_registry=_registry())
    task = ProteinDesignTask(
        task_id="candidate_generator_filter",
        goal="design stable peptide",
        constraints={
            "goal_type": "legacy_sequence_generation",
            "inputs": {"sequence": "AAAA"},
            "blocked_tools": ["seqgen_a"],
        },
        metadata={},
    )

    topk = planner.plan_top_k(task, k=3)

    assert topk.candidates
    assert all(candidate.tool_id != "seqgen_a" for candidate in topk.candidates)
    assert topk.default_recommendation == topk.candidates[0].candidate_id
    candidate = topk.candidates[0]
    feasibility = candidate.metadata[CANDIDATE_FEASIBILITY_METADATA_KEY]
    assert isinstance(feasibility, dict)
    assert feasibility["hard_feasible"] is True
    assert feasibility["auto_executable"] is True
    assert feasibility["allowed_for_default_recommendation"] is True
    assert "feasibility" not in candidate.metadata
    assert "Filtered candidates before ranking" in topk.explanation


def test_generator_returns_degraded_soft_fallback_without_default():
    registry = [
        ToolSpec(
            id="seqgen_a",
            capabilities=("sequence_generation",),
            inputs=("target",),
            outputs=("sequence",),
            cost=0.2,
            safety_level=1,
            io_type="target_to_sequence",
            adapter_mode="local",
            priority="P0",
        )
    ]
    result = _direct_generator().generate(
        CandidateGenerationInput(
            candidate_kind="plan",
            payloads=[
                CandidatePayload(
                    payload=_plan("seqgen_a"),
                    primary_tool_id="seqgen_a",
                    capability_bucket="sequence_generation",
                    note="missing target input",
                )
            ],
            registry=registry,
            top_k=1,
            task_constraints={},
        )
    )

    assert result.candidates
    assert result.default_recommendation is None
    candidate = result.candidates[0]
    feasibility = candidate.metadata[CANDIDATE_FEASIBILITY_METADATA_KEY]
    assert isinstance(feasibility, dict)
    assert feasibility["filter_reason"] == "io_not_closed"
    assert feasibility["filter_class"] == "soft"
    assert feasibility["hard_feasible"] is False
    assert feasibility["soft_feasible"] is True
    assert feasibility["degraded_feasible"] is True
    assert feasibility["requires_hitl"] is True
    assert feasibility["auto_executable"] is False
    assert feasibility["allowed_for_top_k"] is True
    assert feasibility["allowed_for_default_recommendation"] is False
    assert feasibility["constraint_codes"] == ["schema.io_open"]
    assert "feasibility" not in candidate.metadata
    assert "No hard-feasible default recommendation exists" in result.explanation
    assert "require HITL" in result.explanation


def test_generator_backfills_degraded_candidate_but_keeps_eligible_default():
    result = _direct_generator(unavailable_tools={"seqgen_b"}).generate(
        CandidateGenerationInput(
            candidate_kind="plan",
            payloads=[
                CandidatePayload(
                    payload=_plan("seqgen_a", inputs={"goal": "design"}),
                    primary_tool_id="seqgen_a",
                    capability_bucket="sequence_generation",
                    note="eligible candidate",
                ),
                CandidatePayload(
                    payload=_plan("seqgen_b", inputs={"goal": "design"}),
                    primary_tool_id="seqgen_b",
                    capability_bucket="sequence_generation",
                    note="degraded candidate",
                ),
            ],
            registry=_registry(),
            top_k=2,
            task_constraints={},
        )
    )

    assert [candidate.tool_id for candidate in result.candidates] == [
        "seqgen_a",
        "seqgen_b",
    ]
    assert result.default_recommendation == result.candidates[0].candidate_id
    eligible_feasibility = result.candidates[0].metadata[
        CANDIDATE_FEASIBILITY_METADATA_KEY
    ]
    assert isinstance(eligible_feasibility, dict)
    assert eligible_feasibility["allowed_for_default_recommendation"] is True
    degraded_feasibility = result.candidates[1].metadata[
        CANDIDATE_FEASIBILITY_METADATA_KEY
    ]
    assert isinstance(degraded_feasibility, dict)
    assert degraded_feasibility["filter_reason"] == "tool_unavailable"
    assert degraded_feasibility["constraint_codes"] == ["tool.unavailable"]
    assert degraded_feasibility["requires_hitl"] is True
    assert degraded_feasibility["auto_executable"] is False
    assert degraded_feasibility["allowed_for_default_recommendation"] is False


def test_generator_records_topk_diversity_metadata_with_score_fallback():
    result = _direct_generator().generate(
        CandidateGenerationInput(
            candidate_kind="plan",
            payloads=[
                CandidatePayload(
                    payload=_plan("seqgen_a", inputs={"goal": "design"}),
                    primary_tool_id="seqgen_a",
                    capability_bucket="sequence_generation",
                    note="eligible candidate",
                ),
                CandidatePayload(
                    payload=_plan("seqgen_b", inputs={"goal": "design"}),
                    primary_tool_id="seqgen_b",
                    capability_bucket="sequence_generation",
                    note="eligible candidate",
                ),
            ],
            registry=_registry(),
            top_k=2,
            task_constraints={},
        )
    )

    for index, candidate in enumerate(result.candidates, start=1):
        diversity = candidate.metadata[TOPK_DIVERSITY_METADATA_KEY]
        assert isinstance(diversity, dict)
        assert diversity["schema_version"] == "topk_diversity.v1"
        assert diversity["strategy"] == "capability_coverage"
        assert diversity["selected_by"] == "_select_diverse_top_k"
        assert diversity["selection_mode"] == "score_ranking_fallback"
        assert diversity["selection_rank"] == index
        assert diversity["diversity_degraded"] is True
        assert diversity["fallback_reason"] == "single_capability_bucket"
        assert diversity["covered_capabilities"] == ["sequence_generation"]
        assert "impl:candidate_generator.topk_diversity.v1" in diversity["source_refs"]


def test_generator_selects_diverse_capability_bucket_over_pure_score_topk():
    result = _direct_generator(
        score_overrides={
            "seqgen_a": 0.90,
            "seqgen_b": 0.86,
            "qc_a": 0.80,
        }
    ).generate(
        CandidateGenerationInput(
            candidate_kind="plan",
            payloads=[
                CandidatePayload(
                    payload=_plan("seqgen_a", inputs={"goal": "design"}),
                    primary_tool_id="seqgen_a",
                    capability_bucket="sequence_generation",
                    note="best sequence candidate",
                ),
                CandidatePayload(
                    payload=_plan("seqgen_b", inputs={"goal": "design"}),
                    primary_tool_id="seqgen_b",
                    capability_bucket="sequence_generation",
                    note="second sequence candidate",
                ),
                CandidatePayload(
                    payload=_plan("qc_a", inputs={"goal": "design"}),
                    primary_tool_id="qc_a",
                    capability_bucket="quality_qc",
                    note="diverse quality candidate",
                ),
            ],
            registry=_diverse_registry(),
            top_k=2,
            task_constraints={},
        )
    )

    assert [candidate.tool_id for candidate in result.candidates] == [
        "seqgen_a",
        "qc_a",
    ]
    assert "seqgen_b" not in {candidate.tool_id for candidate in result.candidates}
    diversity = result.candidates[1].metadata[TOPK_DIVERSITY_METADATA_KEY]
    assert isinstance(diversity, dict)
    assert diversity["selection_mode"] == "capability_bucket_round_robin"
    assert diversity["diversity_degraded"] is False
    assert diversity["covered_capabilities"] == [
        "quality_qc",
        "sequence_generation",
    ]
    assert "SelectDiverseTopK" in result.explanation


def test_plan_top_k_applies_policy_mode_and_cost_filter(monkeypatch):
    monkeypatch.setenv("PLANNER_LLM_PROVIDER", "none")
    monkeypatch.setattr(planner_module, "load_tool_kg", _kg)
    monkeypatch.setattr(
        planner_module,
        "build_capability_readiness_snapshot",
        _ready_capability,
    )
    planner = PlannerAgent(tool_registry=_registry())
    task = ProteinDesignTask(
        task_id="candidate_generator_policy_cost",
        goal="design stable peptide",
        constraints={
            "goal_type": "legacy_sequence_generation",
            "inputs": {"sequence": "AAAA"},
            "policy_mode": "low_cost",
            "max_cost_level": "medium",
        },
        metadata={},
    )

    topk = planner.plan_top_k(task, k=3)

    assert topk.candidates
    assert all(candidate.cost_estimate != "high" for candidate in topk.candidates)
    assert all(
        "policy_mode_fit" in candidate.score_breakdown
        for candidate in topk.candidates
    )
