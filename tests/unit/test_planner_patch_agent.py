import pytest

import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import PatchRequest, Plan, PlanStep, PlanPatch, StepResult, now_iso


def _build_registry():
    return [
        ToolSpec(
            id="t_fail",
            capabilities=("fold",),
            inputs=("sequence",),
            outputs=("structure",),
            cost=5,
            safety_level=2,
        ),
        ToolSpec(
            id="t_alt_high",
            capabilities=("fold",),
            inputs=("sequence",),
            outputs=("structure",),
            cost=3,
            safety_level=1,
        ),
        ToolSpec(
            id="t_alt_low",
            capabilities=("fold",),
            inputs=("sequence",),
            outputs=("structure",),
            cost=1,
            safety_level=3,
        ),
    ]


def _mock_kg_for_registry():
    return {
        "capabilities": [
            {
                "capability_id": "fold",
                "name": "Fold",
                "domain": "protein/structure",
                "description": "Test folding capability.",
            }
        ],
        "io_types": [
            {
                "io_type_id": "sequence_to_structure",
                "input_types": ["sequence"],
                "output_types": ["structure"],
                "combinable": True,
            }
        ],
        "tools": [
            {
                "id": "t_fail",
                "capabilities": ["fold"],
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"structure": "path"},
                },
                "constraints": {},
            },
            {
                "id": "t_alt_high",
                "capabilities": ["fold"],
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"structure": "path"},
                },
                "constraints": {},
            },
            {
                "id": "t_alt_low",
                "capabilities": ["fold"],
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"structure": "path"},
                },
                "constraints": {},
            },
        ],
    }


def _step_result(step_id: str, outputs: dict) -> StepResult:
    return StepResult(
        task_id="task-001",
        step_id=step_id,
        tool="t_prev",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs=outputs,
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )


def _build_request():
    plan = Plan(
        task_id="task-001",
        steps=[
            PlanStep(id="S1", tool="t_fail", inputs={"sequence": "S0.sequence"}, metadata={})
        ],
        constraints={},
        metadata={},
    )
    return PatchRequest(
        task_id=plan.task_id,
        original_plan=plan,
        context_step_results=[_step_result("S0", {"sequence": "AAA"})],
        safety_events=[],
        reason="tool_failed",
    )


def test_patch_returns_replace_step_with_cheapest_candidate(monkeypatch):
    monkeypatch.setattr(
        planner_module,
        "load_tool_kg",
        lambda: _mock_kg_for_registry(),
    )
    agent = PlannerAgent(tool_registry=_build_registry())
    request = _build_request()

    patch = agent.patch(request)

    assert isinstance(patch, PlanPatch)
    assert len(patch.operations) == 1
    op = patch.operations[0]
    assert op.op == "replace_step"
    assert op.target == "S1"
    assert op.step.tool == "t_alt_low"  # 选择 cost 最低的候选


def test_patch_raises_when_no_compatible_tool(monkeypatch):
    # registry 中的候选需要额外输入，无法满足
    registry = [
        ToolSpec(
            id="t_fail",
            capabilities=("fold",),
            inputs=("sequence",),
            outputs=("structure",),
            cost=5,
            safety_level=2,
        ),
        ToolSpec(
            id="t_alt_need_extra",
            capabilities=("fold",),
            inputs=("sequence", "template"),
            outputs=("structure",),
            cost=1,
            safety_level=1,
        ),
    ]
    monkeypatch.setattr(
        planner_module,
        "load_tool_kg",
        lambda: _mock_kg_for_registry(),
    )
    agent = PlannerAgent(tool_registry=registry)
    request = _build_request()

    with pytest.raises(ValueError):
        agent.patch(request)
