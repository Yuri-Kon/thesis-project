from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.agents.planner import PlannerAgent, TopKResult
from src.models.contracts import (
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanStep,
    StepResult,
)
from src.models.validation import validate_candidate_set_output
from src.models.db import TaskRecord, InternalStatus
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType
from src.workflow.patch import apply_patch, build_patch_request
from src.workflow.step_runner import StepRunner
from src.workflow.status import transition_task_status
from src.workflow.pending_action import build_pending_action, enter_waiting_state


class StepRunnerLike(Protocol):
    """最小化约束的 StepRunner 接口（便于注入/测试）"""

    def run_step(self, step, context: WorkflowContext) -> StepResult:  # type: ignore
        ...


@dataclass(frozen=True)
class PendingPatch:
    target_step_id: str
    original_step: PlanStep
    previous_result: StepResult
    plan_patch: PlanPatch


@dataclass(frozen=True)
class PatchRunOutcome:
    plan: Plan
    step_results: list[StepResult]
    next_step_index: int
    pending_patch: PendingPatch | None = None


class PatchRunner:
    """封装“重试 → Patch → 再执行一次”的最小闭环

    - 依赖 StepRunner 执行步骤（含重试）
    - 当重试耗尽仍失败，或失败类型属于可补丁范围时，调用 Planner.patch 生成 PlanPatch
    - 本地 apply_patch 后对目标步骤再执行一次
    - 仅在 patch 触发时推进 WAITING_PATCH/PATCHING，其他状态交由 PlanRunner 负责
    """

    def __init__(
        self,
        step_runner: StepRunnerLike | None = None,
        planner_agent: PlannerAgent | None = None,
    ) -> None:
        self._step_runner: StepRunnerLike = step_runner or StepRunner()
        self._planner: PlannerAgent = planner_agent or PlannerAgent()

    def run_step_with_patch(
        self,
        plan: Plan,
        step_index: int,
        context: WorkflowContext,
        *,
        record: TaskRecord | None = None,
    ) -> PatchRunOutcome:
        """执行指定 step；必要时进行一次 patch 并重新执行该 step"""
        step = plan.steps[step_index]
        result = self._step_runner.run_step(step, context)

        if not self._should_patch(result):
            return PatchRunOutcome(
                plan=plan,
                step_results=[result],
                next_step_index=step_index + 1,
            )

        if context.status != InternalStatus.RUNNING:
            return PatchRunOutcome(
                plan=plan,
                step_results=[result],
                next_step_index=step_index + 1,
            )

        patch_reason = (
            "retry_exhausted"
            if result.metrics.get("retry_exhausted")
            else "patch_required"
        )
        try:
            patch_request = build_patch_request(
                plan=plan,
                failed_step_index=step_index,
                failed_result=result,
                context=context,
            )
            candidate_set_v1_ready = True
            try:
                patch_top_k = self._planner.patch_top_k(
                    patch_request,
                    k=_resolve_top_k(context.task.constraints.get("patch_top_k"), default=3),
                )
                selected_candidate = next(
                    (
                        candidate
                        for candidate in patch_top_k.candidates
                        if candidate.candidate_id == patch_top_k.default_recommendation
                    ),
                    patch_top_k.candidates[0] if patch_top_k.candidates else None,
                )
                if selected_candidate is None:
                    raise ValueError("patch_top_k returned no candidates")
                payload = selected_candidate.structured_payload
                if not isinstance(payload, PlanPatch):
                    raise ValueError("patch_top_k default candidate is not PlanPatch")
                plan_patch = payload
            except Exception:
                # 回退到旧路径，保持对自定义 Planner.patch 的兼容
                plan_patch = self._planner.patch(patch_request)
                patch_candidate = PendingActionCandidate(
                    candidate_id=f"patch_{step.id.lower()}",
                    payload=plan_patch,
                    summary="fallback patch candidate",
                    metadata={"reason": patch_reason},
                )
                patch_top_k = TopKResult(
                    candidates=[patch_candidate],
                    default_recommendation=patch_candidate.candidate_id,
                    explanation="fallback patch_top_k generated from planner.patch",
                )
                candidate_set_v1_ready = False
            gate = self._planner.evaluate_top_k_gate(
                candidate_kind="patch",
                top_k_result=patch_top_k,
                task_constraints=context.task.constraints,
            )
        except Exception:
            _enter_replan_waiting(context, record, reason="patch_failed")
            raise

        if gate.requires_hitl:
            pending_action = build_pending_action(
                task_id=context.task.task_id,
                action_type=PendingActionType.PATCH_CONFIRM,
                candidates=patch_top_k.candidates,
                default_suggestion=patch_top_k.default_recommendation,
                default_recommendation=patch_top_k.default_recommendation,
                explanation=f"{patch_top_k.explanation} gate={gate.reason}",
            )
            validate_candidate_set_output(
                pending_action,
                require_v1_fields=candidate_set_v1_ready,
            )
            enter_waiting_state(
                context,
                record,
                pending_action,
                InternalStatus.WAITING_PATCH,
            )
            transition_task_status(
                context,
                record,
                InternalStatus.WAITING_PATCH,
                reason=gate.reason,
            )
            return PatchRunOutcome(
                plan=plan,
                step_results=[],
                next_step_index=step_index,
            )

        transition_task_status(
            context,
            record,
            InternalStatus.WAITING_PATCH,
            reason="patch_auto_path",
        )
        transition_task_status(
            context,
            record,
            InternalStatus.PATCHING,
            reason="patch_start_auto",
        )
        try:
            patched_plan = apply_patch(plan, plan_patch)
        except Exception:
            _enter_replan_waiting(context, record, reason="patch_failed")
            raise

        # 将最新的 plan 写回 context（如果 task_id 匹配）
        if context.plan is None or context.plan.task_id == patched_plan.task_id:
            context.plan = patched_plan
        if record is not None and (
            record.plan is None or record.plan.task_id == patched_plan.task_id
        ):
            record.plan = patched_plan

        if _has_insert_before_target(plan_patch, step.id):
            pending_patch = PendingPatch(
                target_step_id=step.id,
                original_step=step,
                previous_result=result,
                plan_patch=plan_patch,
            )
            return PatchRunOutcome(
                plan=patched_plan,
                step_results=[],
                next_step_index=step_index,
                pending_patch=pending_patch,
            )

        # 优先使用原 step id 定位（避免插入操作改变索引）
        target_id = step.id
        patched_step = next(s for s in patched_plan.steps if s.id == target_id)
        patched_index = next(
            idx for idx, s in enumerate(patched_plan.steps) if s.id == target_id
        )

        patched_result = self._step_runner.run_step(patched_step, context)
        self._attach_patch_meta(
            patched_result,
            original_step=step,
            previous_result=result,
            plan_patch=plan_patch,
        )
        return PatchRunOutcome(
            plan=patched_plan,
            step_results=[patched_result],
            next_step_index=patched_index + 1,
        )

    def _should_patch(self, result: StepResult) -> bool:
        if result.status != "failed":
            return False
        if result.failure_type == FailureType.SAFETY_BLOCK:
            return False

        retry_exhausted = result.metrics.get("retry_exhausted", False)
        patchable_nonretryable = result.failure_type in (
            FailureType.TOOL_ERROR,
            FailureType.NON_RETRYABLE,
        )
        return bool(retry_exhausted or patchable_nonretryable)

    def _attach_patch_meta(
        self,
        patched_result: StepResult,
        *,
        original_step,
        previous_result: StepResult,
        plan_patch: PlanPatch,
    ) -> None:
        """将 patch 关键信息写入 patched_result.metrics"""
        patch_info = {
            "applied": True,
            "ops": [op.op for op in plan_patch.operations],
            "from_tool": original_step.tool,
            "to_tool": patched_result.tool,
            "original_step_id": original_step.id,
            "patched_step_id": patched_result.step_id,
            "patched_status": patched_result.status,
            "previous_attempt": _summarize_result(previous_result),
        }
        metrics = dict(patched_result.metrics)
        metrics["patch"] = patch_info
        patched_result.metrics = metrics

    def attach_patch_meta(
        self,
        patched_result: StepResult,
        pending_patch: PendingPatch,
    ) -> None:
        """对后续执行的目标步骤补齐 patch 元信息"""
        self._attach_patch_meta(
            patched_result,
            original_step=pending_patch.original_step,
            previous_result=pending_patch.previous_result,
            plan_patch=pending_patch.plan_patch,
        )


def _enter_replan_waiting(
    context: WorkflowContext,
    record: TaskRecord | None,
    *,
    reason: str,
) -> None:
    pending_action = build_pending_action(
        task_id=context.task.task_id,
        action_type=PendingActionType.REPLAN_CONFIRM,
        candidates=[],
        default_suggestion=None,
        explanation="patch failed; replan confirmation required",
    )
    enter_waiting_state(
        context,
        record,
        pending_action,
        InternalStatus.WAITING_REPLAN,
    )
    transition_task_status(
        context,
        record,
        InternalStatus.WAITING_REPLAN,
        reason=reason,
    )


def _summarize_result(result: StepResult) -> dict:
    """提取失败结果的关键摘要，重用 attempt_history 结构"""
    return {
        "status": result.status,
        "failure_type": result.failure_type,
        "error_message": result.error_message,
        "tool": result.tool,
        "attempt_history": result.metrics.get("attempt_history"),
    }


def _has_insert_before_target(plan_patch: PlanPatch, target_id: str) -> bool:
    return any(
        op.op == "insert_step_before" and op.target == target_id
        for op in plan_patch.operations
    )


def _resolve_top_k(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return 1
    return parsed
