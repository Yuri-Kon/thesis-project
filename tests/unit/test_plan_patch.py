import pytest

from src.models.contracts import Plan, PlanPatch, PlanPatchOp, PlanStep
from src.workflow.patch import apply_patch


def _build_plan() -> Plan:
    return Plan(
        task_id="task-001",
        steps=[
            PlanStep(id="S1", tool="tool_a", inputs={}, metadata={}),
            PlanStep(id="S2", tool="tool_b", inputs={"y": "S1.out"}, metadata={}),
        ],
        constraints={},
        metadata={},
    )


def test_replace_step_returns_new_plan_without_mutating_original():
    plan = _build_plan()
    patch = PlanPatch(
        task_id=plan.task_id,
        operations=[
            PlanPatchOp(
                op="replace_step",
                target="S2",
                step=PlanStep(
                    id="S2",
                    tool="tool_b_new",
                    inputs={"y": "S1.out"},
                    metadata={"patched": True},
                ),
            )
        ],
        metadata={},
    )

    new_plan = apply_patch(plan, patch)

    assert new_plan is not plan
    assert [s.tool for s in new_plan.steps] == ["tool_a", "tool_b_new"]
    assert [s.tool for s in plan.steps] == ["tool_a", "tool_b"]


def test_replace_step_missing_target_raises_value_error():
    plan = _build_plan()
    patch = PlanPatch(
        task_id=plan.task_id,
        operations=[
            PlanPatchOp(
                op="replace_step",
                target="S3",
                step=PlanStep(id="S3", tool="tool_c", inputs={}, metadata={}),
            )
        ],
        metadata={},
    )

    with pytest.raises(ValueError):
        apply_patch(plan, patch)


def test_insert_before_allocates_unique_id_on_conflict():
    plan = _build_plan()
    patch = PlanPatch(
        task_id=plan.task_id,
        operations=[
            PlanPatchOp(
                op="insert_step_before",
                target="S2",
                step=PlanStep(
                    id="S1",  # 故意冲突，触发稳定的后缀生成
                    tool="tool_filter",
                    inputs={"x": "S1.out"},
                    metadata={},
                ),
            )
        ],
        metadata={},
    )

    new_plan = apply_patch(plan, patch)
    assert [s.id for s in new_plan.steps] == ["S1", "S1_1", "S2"]
    assert new_plan.steps[1].tool == "tool_filter"


def test_insert_after_inserts_in_order():
    plan = _build_plan()
    patch = PlanPatch(
        task_id=plan.task_id,
        operations=[
            PlanPatchOp(
                op="insert_step_after",
                target="S1",
                step=PlanStep(
                    id="S1_filter",
                    tool="tool_filter",
                    inputs={"x": "S1.out"},
                    metadata={},
                ),
            )
        ],
        metadata={},
    )

    new_plan = apply_patch(plan, patch)
    assert [s.id for s in new_plan.steps] == ["S1", "S1_filter", "S2"]
    assert new_plan.steps[1].tool == "tool_filter"


def test_task_id_mismatch_raises_value_error():
    plan = _build_plan()
    patch = PlanPatch(
        task_id="other-task",
        operations=[],
        metadata={},
    )

    with pytest.raises(ValueError):
        apply_patch(plan, patch)

