from __future__ import annotations

import json
from typing import Any, ClassVar

from src.agents.planner import PlannerAgent
from src.agents.safety import SafetyAgent
from src.models.contracts import (
    PendingActionStatus,
    PendingActionType,
    Plan,
    PlanStep,
    ReplanRequest,
    StepResult,
    now_iso,
)
from src.models.db import InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, PlanRunError, classify_exception
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.workflow.recovery import (
    WorkflowActionSelectorInput,
    build_terminal_stop_candidate,
    select_workflow_action,
)
from src.workflow.runtime_policy import resolve_runtime_policy
from src.workflow.snapshots import build_context_runtime_state_summary
from src.workflow.status import transition_task_status


class PlanRunnerRecoveryMixin:
    _planner: ClassVar[PlannerAgent]
    _safety_agent: ClassVar[SafetyAgent]

    def _add_safety_event(self, context: WorkflowContext, event: object) -> None:
        raise NotImplementedError

    def _add_failed_step_safety_event(
        self,
        step_result: StepResult,
        plan: Plan,
        context: WorkflowContext,
    ) -> bool:
        step = next((s for s in plan.steps if s.id == step_result.step_id), None)
        if step is None:
            return False
        safety_result = self._safety_agent.check_post_step(step, step_result, context)
        self._add_safety_event(context, safety_result)
        if safety_result.risk_flags:
            step_result.risk_flags = safety_result.risk_flags
        return safety_result.action == "block"

    def _build_replan_explanation(
        self,
        reason: str,
        failed_result: StepResult,
    ) -> str:
        failure_context = self._summarize_failure_result(failed_result)
        options = self._build_replan_options(failure_context.get("failure_code"))
        payload = {
            "action_name": self._extract_workflow_action(failed_result),
            "reason": reason,
            "failure": failure_context,
            "options": options,
        }
        return (
            f"replan requested: {reason}; "
            f"context={json.dumps(payload, ensure_ascii=True)}"
        )

    def _build_basic_replan_explanation(self, reason: str) -> str:
        payload = {
            "reason": reason,
            "options": ["replan", "cancel"],
        }
        return (
            f"replan requested: {reason}; "
            f"context={json.dumps(payload, ensure_ascii=True)}"
        )

    def _build_replan_options(self, failure_code: object) -> list[str]:
        options = ["replan", "cancel"]
        if isinstance(failure_code, str) and failure_code.startswith("NIM_"):
            options.append("switch_to_local_esmfold")
        if isinstance(failure_code, str) and failure_code.startswith("S3_"):
            options.append("suffix_replan")
        return options

    def _build_stop_explanation(self, failed_result: StepResult) -> str:
        payload = {
            "action_name": "stop",
            "terminal_policy": "stop",
            "failure": self._summarize_failure_result(failed_result),
            "options": ["accept_terminal_stop", "continue", "cancel"],
        }
        return (
            "adaptive terminal_stop requested; "
            f"context={json.dumps(payload, ensure_ascii=True)}"
        )

    def _summarize_failure_result(self, result: StepResult) -> dict[str, Any]:
        failure_code = None
        failure_reason = result.error_message
        if result.risk_flags:
            failure_code = result.risk_flags[0].code
            if result.risk_flags[0].message:
                failure_reason = result.risk_flags[0].message
        if not failure_code:
            failure_code = result.error_details.get("failure_code")
        patch_meta = result.metrics.get("patch")
        recovery_meta = result.metrics.get("recovery")
        return {
            "step_id": result.step_id,
            "tool": result.tool,
            "failure_type": result.failure_type,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "risk_flags": [flag.model_dump() for flag in result.risk_flags],
            "patch": patch_meta if isinstance(patch_meta, dict) else {},
            "recovery": recovery_meta if isinstance(recovery_meta, dict) else {},
        }

    def _coerce_failure_type(self, value: object) -> FailureType:
        """将 StepResult.failure_type 统一为 FailureType 枚举"""
        if isinstance(value, FailureType):
            return value
        if isinstance(value, str):
            try:
                return FailureType(value)
            except ValueError:
                pass
        return FailureType.NON_RETRYABLE

    def _extract_workflow_action(self, result: StepResult) -> str | None:
        action = result.metrics.get("workflow_action")
        if isinstance(action, str) and action:
            return action
        return None

    def _ensure_step_workflow_action(
        self,
        context: WorkflowContext,
        step_result: StepResult,
    ) -> None:
        if self._extract_workflow_action(step_result):
            return
        runtime_state_summary = build_context_runtime_state_summary(
            context,
            require_runtime_state=True,
        )
        decision = select_workflow_action(
            WorkflowActionSelectorInput(
                phase="execution",
                stage_id=(
                    step_result.outputs.get("stage_id")
                ),
                failure_code=(
                    step_result.error_details.get("failure_code")
                ),
                failure_type=step_result.failure_type,
                retry_exhausted=bool(step_result.metrics.get("retry_exhausted")),
                safety_blocked=step_result.failure_type == FailureType.SAFETY_BLOCK,
                runtime_state_summary=runtime_state_summary,
                runtime_policy=resolve_runtime_policy(context.task),
            )
        )
        metrics = dict(step_result.metrics)
        metrics["workflow_action"] = decision.action
        metrics["workflow_action_mapped_flow"] = decision.mapped_flow
        metrics["workflow_action_reason"] = decision.reason
        metrics["workflow_action_evidence"] = dict(decision.evidence_source)
        if (
            step_result.status == "failed"
            and decision.action != "continue"
            and "retry_exhausted" not in metrics
        ):
            metrics["retry_exhausted"] = True
        step_result.metrics = metrics

    def _should_skip_step(self, step: PlanStep, context: WorkflowContext) -> bool:
        """判断是否可跳过已成功且与当前计划一致的步骤"""
        result = context.step_results.get(step.id)
        if result is None:
            return False
        if result.status != "success":
            return False
        if result.tool != step.tool:
            return False
        return True

    def _has_patch_applied(self, step_results: list[StepResult]) -> bool:
        """判断当前批次结果中是否包含已应用的 patch"""
        for result in step_results:
            patch_meta = result.metrics.get("patch")
            if isinstance(patch_meta, dict) and patch_meta.get("applied") is True:
                return True
        return False

    def _request_replan(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        *,
        reason: str,
        failure_type: FailureType,
        message: str,
        code: str | None = None,
        step_id: str | None = None,
        explanation: str | None = None,
    ) -> None:
        """触发 WAITING_REPLAN，并抛出 PlanRunError 交给上层处理"""
        if context.status != InternalStatus.WAITING_REPLAN:
            pending_action = build_pending_action(
                task_id=context.task.task_id,
                action_type=PendingActionType.REPLAN_CONFIRM,
                candidates=[],
                default_suggestion=None,
                explanation=explanation or f"replan requested: {reason}",
            )
            enter_waiting_state(
                context,
                record,
                pending_action,
                InternalStatus.WAITING_REPLAN,
                reason=reason,
            )
            transition_task_status(
                context,
                record,
                InternalStatus.WAITING_REPLAN,
                reason=reason,
            )
        raise PlanRunError(
            failure_type=failure_type,
            message=message,
            step_id=step_id,
            code=code,
        )

    def _request_stop(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        *,
        failure_type: FailureType,
        message: str,
        step_id: str | None = None,
        explanation: str | None = None,
        failed_result: StepResult | None = None,
    ) -> None:
        if context.plan is None:
            raise PlanRunError(
                failure_type=failure_type,
                message=message,
                step_id=step_id,
                code="ADAPTIVE_STOP_REQUESTED",
            )
        failure_code = None
        failure_reason = message
        if failed_result is not None:
            failure_summary = self._summarize_failure_result(failed_result)
            raw_code = failure_summary.get("failure_code")
            if isinstance(raw_code, str) and raw_code:
                failure_code = raw_code
            raw_reason = failure_summary.get("failure_reason")
            if isinstance(raw_reason, str) and raw_reason:
                failure_reason = raw_reason
        runtime_state_summary = build_context_runtime_state_summary(
            context,
            require_runtime_state=True,
        )
        terminal_stop_candidate = build_terminal_stop_candidate(
            plan=context.plan,
            step_id=step_id,
            failure_type=failure_type,
            failure_code=failure_code,
            failure_reason=failure_reason,
            runtime_state_summary=runtime_state_summary,
            explanation=explanation,
        )
        pending_action = build_pending_action(
            task_id=context.task.task_id,
            action_type=PendingActionType.REPLAN_CONFIRM,
            candidates=[terminal_stop_candidate],
            default_suggestion=terminal_stop_candidate.candidate_id,
            default_recommendation=terminal_stop_candidate.candidate_id,
            explanation=explanation or "adaptive terminal_stop requested",
            metadata={
                "workflow_action": "stop",
                "workflow_action_mapped_flow": "stop",
                "workflow_action_reason": failure_reason,
                "workflow_action_target": "failed",
                "terminal_policy": "stop",
            },
        )
        enter_waiting_state(
            context,
            record,
            pending_action,
            InternalStatus.WAITING_REPLAN,
            reason="terminal_stop_requested",
        )
        transition_task_status(
            context,
            record,
            InternalStatus.WAITING_REPLAN,
            reason="terminal_stop_requested",
        )
        raise PlanRunError(
            failure_type=failure_type,
            message=message,
            step_id=step_id,
            code="ADAPTIVE_STOP_REQUESTED",
        )

    def _perform_replan(
        self,
        plan: Plan,
        context: WorkflowContext,
        record: TaskRecord | None,
        error: PlanRunError,
    ) -> Plan:
        """执行最小再规划闭环：WAITING_REPLAN → REPLANNING → RUNNING"""
        transition_task_status(
            context,
            record,
            InternalStatus.REPLANNING,
            reason="replan_requested",
        )
        self._resolve_pending_replan_action(context, record)
        request = ReplanRequest(
            task_id=context.task.task_id,
            original_plan=plan,
            failed_steps=[error.step_id] if error.step_id else [],
            safety_events=list(context.safety_events),
            reason=str(error),
        )
        try:
            try:
                replan_top_k = self._planner.replan_top_k(
                    request,
                    k=resolve_top_k(context.task.constraints.get("replan_top_k"), default=3),
                    runtime_state=context.runtime_state,
                )
                gate = self._planner.evaluate_top_k_gate(
                    candidate_kind="replan",
                    top_k_result=replan_top_k,
                    task_constraints=context.task.constraints,
                )
                if gate.requires_hitl:
                    waiting_action = build_pending_action(
                        task_id=context.task.task_id,
                        action_type=PendingActionType.REPLAN_CONFIRM,
                        candidates=replan_top_k.candidates,
                        default_suggestion=replan_top_k.default_recommendation,
                        default_recommendation=replan_top_k.default_recommendation,
                        explanation=f"{replan_top_k.explanation} gate={gate.reason}",
                    )
                    enter_waiting_state(
                        context,
                        record,
                        waiting_action,
                        InternalStatus.WAITING_REPLAN,
                        reason=gate.reason,
                    )
                    transition_task_status(
                        context,
                        record,
                        InternalStatus.WAITING_REPLAN,
                        reason=gate.reason,
                    )
                    return plan

                ordered_candidates = select_replan_candidates(
                    replan_top_k.candidates,
                    default_recommendation=replan_top_k.default_recommendation,
                    preferred_action=(
                        "suffix_replan"
                        if error.code == "SUFFIX_REPLAN_REQUESTED"
                        else None
                    ),
                )
                selected = ordered_candidates[0] if ordered_candidates else None
                if selected is None:
                    raise ValueError("replan_top_k returned empty candidates")
                payload = selected.structured_payload
                if not isinstance(payload, Plan):
                    raise ValueError("replan_top_k selected payload is not Plan")
                replanned_plan = payload
            except Exception:
                # 回退到旧 replan()，保持既有 Planner stub 兼容
                replanned_plan = self._planner.replan(request)
        except Exception as exc:
            transition_task_status(
                context,
                record,
                InternalStatus.FAILED,
                reason="replan_failed",
            )
            raise PlanRunError(
                failure_type=classify_exception(exc),
                message=f"Replan failed: {exc}",
                step_id=error.step_id,
                code="REPLAN_FAILED",
                cause=exc,
            ) from exc

        if replanned_plan.task_id != context.task.task_id:
            transition_task_status(
                context,
                record,
                InternalStatus.FAILED,
                reason="replan_failed",
            )
            raise PlanRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=(
                    "Replan produced plan with mismatched task_id: "
                    f"{replanned_plan.task_id} != {context.task.task_id}"
                ),
                step_id=error.step_id,
                code="REPLAN_TASK_MISMATCH",
            )

        context.plan = replanned_plan
        if record is not None:
            record.plan = replanned_plan

        transition_task_status(
            context,
            record,
            InternalStatus.RUNNING,
            reason="replan_succeeded",
        )
        return replanned_plan

    def _resolve_pending_replan_action(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
    ) -> None:
        action = context.pending_action
        if (
            action is None
            or action.action_type != PendingActionType.REPLAN_CONFIRM
            or action.status != PendingActionStatus.PENDING
        ):
            return
        action.status = PendingActionStatus.CANCELLED
        action.decided_at = now_iso()
        context.pending_action = action
        if record is not None:
            record.pending_action = action




def resolve_top_k(value: object, *, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed <= 0:
        return 1
    return parsed


def select_replan_candidates(
    candidates: list[Any],
    *,
    default_recommendation: str | None,
    preferred_action: str | None,
) -> list[Any]:
    preferred: list[tuple[int, str, Any]] = []
    fallback: list[tuple[int, str, Any]] = []
    for candidate in candidates:
        metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
        shadow_action = metadata.get("shadow_action")
        payload = candidate.structured_payload
        replan_mode = None
        if isinstance(payload, Plan):
            payload_meta = payload.metadata
            raw_mode = payload_meta.get("replan_mode")
            if isinstance(raw_mode, str):
                replan_mode = raw_mode
        rank = (
            0
            if default_recommendation is not None
            and candidate.candidate_id == default_recommendation
            else 1
        )
        row = (rank, candidate.candidate_id, candidate)
        if preferred_action == "suffix_replan" and (
            shadow_action == "suffix_replan" or replan_mode == "suffix_replan"
        ):
            preferred.append(row)
        else:
            fallback.append(row)
    return [item[2] for item in sorted(preferred) + sorted(fallback)]


def should_require_replan_confirm(error: PlanRunError) -> bool:
    return (
        error.failure_type == FailureType.SAFETY_BLOCK
        or error.code in {
            "SAFETY_TASK_INPUT_BLOCK",
            "SAFETY_FINAL_BLOCK",
            "SAFETY_POST_BLOCK",
            "ADAPTIVE_STOP_REQUESTED",
        }
    )


def has_recovery_upgrade(step_result: StepResult) -> bool:
    recovery = step_result.metrics.get("recovery")
    if not isinstance(recovery, dict):
        return False
    upgrade_reason = recovery.get("upgrade_reason")
    return isinstance(upgrade_reason, str) and bool(upgrade_reason)
