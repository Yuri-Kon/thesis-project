from __future__ import annotations

import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import ProteinDesignTask


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
        constraints={"goal_type": "sequence_evaluation", "budget": {"cost_cap": 0.5}},
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
    assert candidate.score_breakdown["recovery_complexity"] >= 0.0
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
        constraints={"goal_type": "sequence_evaluation", "blocked_tools": ["seqgen_a"]},
        metadata={},
    )

    topk = planner.plan_top_k(task, k=3)

    assert topk.candidates
    assert all(candidate.tool_id != "seqgen_a" for candidate in topk.candidates)
    assert topk.default_recommendation == topk.candidates[0].candidate_id
    assert "Filtered candidates before ranking" in topk.explanation


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
            "goal_type": "sequence_evaluation",
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
