from __future__ import annotations

from typing import List, Set

from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    PlanPatchOp,
    StepResult,
)
from src.workflow.context import WorkflowContext


def apply_patch(plan: Plan, patch: PlanPatch) -> Plan:
    """根据 PlanPatch 返回新的 Plan（不修改原 plan 实例）
    
    支持的操作:
    - replace_step: 用新的 PlanStep 替换目标 id 的步骤（保持顺序不变）
    - insert_step_before/after: 在目标步骤前/后插入新步骤，若 id 冲突则按稳定规则生成唯一 id
    
    Args:
        plan: 原始 Plan
        patch: PlanPatch 操作集合
    Returns:
        Plan: 应用 patch 后的新 Plan
    Raises:
        ValueError: task_id 不一致、目标步骤不存在或输入非法
    """
    if plan.task_id != patch.task_id:
        raise ValueError(
            f"PlanPatch.task_id ({patch.task_id}) does not match Plan.task_id ({plan.task_id})"
        )

    steps = [step.model_copy(deep=True) for step in plan.steps]
    _ensure_unique_step_ids(steps)

    for op in patch.operations:
        steps = _apply_operation(steps, op)

    return plan.model_copy(update={"steps": steps}, deep=True)


def _apply_operation(steps: List, op: PlanPatchOp) -> List:
    if op.op == "replace_step":
        return _replace_step(steps, op)
    if op.op == "insert_step_before":
        return _insert_step(steps, op, position="before")
    if op.op == "insert_step_after":
        return _insert_step(steps, op, position="after")
    raise ValueError(f"Unsupported PlanPatch operation: {op.op}")


def _replace_step(steps: List, op: PlanPatchOp) -> List:
    idx = _find_step_index(steps, op.target)
    new_steps = list(steps)
    new_steps[idx] = op.step.model_copy(deep=True)
    return new_steps


def _insert_step(steps: List, op: PlanPatchOp, position: str) -> List:
    idx = _find_step_index(steps, op.target)
    existing_ids: Set[str] = {s.id for s in steps}
    step_to_insert = op.step.model_copy(deep=True)
    allocated_id = _allocate_step_id(step_to_insert.id, existing_ids)
    if allocated_id != step_to_insert.id:
        step_to_insert = step_to_insert.model_copy(update={"id": allocated_id})

    insert_at = idx if position == "before" else idx + 1
    new_steps = list(steps)
    new_steps.insert(insert_at, step_to_insert)
    return new_steps


def _find_step_index(steps: List, target: str) -> int:
    for i, step in enumerate(steps):
        if step.id == target:
            return i
    raise ValueError(f"Target step '{target}' not found in plan")


def _ensure_unique_step_ids(steps: List) -> None:
    seen: Set[str] = set()
    for step in steps:
        if step.id in seen:
            raise ValueError(f"Duplicate step id '{step.id}' found in Plan")
        seen.add(step.id)


def _allocate_step_id(desired_id: str, existing_ids: Set[str]) -> str:
    """稳定的 id 生成规则：若冲突则追加递增后缀 _1/_2/..."""
    if desired_id not in existing_ids:
        return desired_id

    suffix = 1
    while f"{desired_id}_{suffix}" in existing_ids:
        suffix += 1
    return f"{desired_id}_{suffix}"


def build_patch_request(
    plan: Plan,
    failed_step_index: int,
    failed_result: StepResult,
    context: WorkflowContext,
) -> PatchRequest:
    """构造 PatchRequest，附带失败上下文与可用 IO 摘要"""
    if plan.task_id != context.task.task_id:
        raise ValueError(
            f"WorkflowContext.task.task_id ({context.task.task_id}) does not match Plan.task_id ({plan.task_id})"
        )

    available_io: Set[str] = set()
    for result in context.step_results.values():
        available_io.update(result.outputs.keys())
    available_io.update(failed_result.outputs.keys())

    context_results = list(context.step_results.values())
    # 将失败的 result 也纳入上下文，以便 Planner 参考失败模式
    context_results.append(failed_result)

    reason = (
        f"step {failed_result.step_id} failed after retries exhausted "
        f"(index={failed_step_index}, failure_type={failed_result.failure_type}, "
        f"error={failed_result.error_message}); available_io={sorted(available_io)}"
    )

    return PatchRequest(
        task_id=plan.task_id,
        original_plan=plan,
        context_step_results=context_results,
        safety_events=list(context.safety_events),
        reason=reason,
    )
