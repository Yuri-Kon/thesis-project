from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.agents.planner import PlannerAgent, TopKResult
from src.models.contracts import (
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanStep,
    StepResult,
    now_iso,
)
from src.models.validation import validate_candidate_set_output
from src.models.db import TaskRecord, InternalStatus, to_external_status
from src.storage.log_store import append_event
from src.workflow.context import WorkflowContext
from src.workflow.belief_state import extract_failure_context, update_runtime_state
from src.workflow.errors import FailureType
from src.workflow.patch import apply_patch, build_patch_request
from src.workflow.recovery import (
    WorkflowActionSelectorInput,
    resolve_s6_recovery_action,
    select_workflow_action,
)
from src.workflow.snapshots import build_context_runtime_state_summary
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
        runtime_state_preview = self._build_runtime_state_preview(
            plan=plan,
            context=context,
            result=result,
        )

        action = self._select_failed_step_action(
            result,
            context=context,
            runtime_state_preview=runtime_state_preview,
        )
        if action is None:
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
        selected_candidate: PendingActionCandidate | None = None
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
                    runtime_state=runtime_state_preview,
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
                candidate_action = self._select_candidate_action(
                    context=context,
                    result=result,
                    runtime_state_preview=runtime_state_preview,
                    phase="patch",
                    suggested_action=selected_candidate.metadata.get("shadow_action"),
                    suggested_reason=selected_candidate.metadata.get(
                        "shadow_action_reason"
                    ),
                )
                if candidate_action.action != "patch_local":
                    return PatchRunOutcome(
                        plan=plan,
                        step_results=[result],
                        next_step_index=step_index + 1,
                    )
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
                    structured_payload=plan_patch,
                    summary="fallback patch candidate",
                    tool_id=step.tool,
                    capability_id=_extract_capability_from_step(step),
                    metadata={
                        "reason": patch_reason,
                        "recovery_layer": "tool_level",
                    },
                )
                selected_candidate = patch_candidate
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
        except Exception as exc:
            _emit_recovery_escalation_event(
                context,
                step_id=step.id,
                reason="patch_failed",
                detail=f"patch candidate generation failed: {exc}",
                recovery=_extract_recovery_metadata(
                    plan_patch=None,
                    selected_candidate=selected_candidate,
                    source_step=step,
                ),
            )
            _enter_replan_waiting(context, record, reason="patch_failed")
            raise

        if gate.requires_hitl:
            recovery_meta = _extract_recovery_metadata(
                plan_patch=plan_patch,
                selected_candidate=selected_candidate,
                source_step=step,
            )
            if gate.reason == "patch_high_risk":
                _attach_recovery_upgrade_meta(
                    result,
                    recovery_meta,
                    upgrade_reason="patch_high_risk",
                )
                _emit_recovery_escalation_event(
                    context,
                    step_id=step.id,
                    reason="patch_high_risk",
                    detail="patch candidate blocked by high risk gate; escalate to replan",
                    recovery=recovery_meta,
                )
                _enter_replan_waiting(context, record, reason="patch_high_risk")
                return PatchRunOutcome(
                    plan=plan,
                    step_results=[result],
                    next_step_index=step_index + 1,
                )

            pending_action = build_pending_action(
                task_id=context.task.task_id,
                action_type=PendingActionType.PATCH_CONFIRM,
                candidates=patch_top_k.candidates,
                default_suggestion=patch_top_k.default_recommendation,
                default_recommendation=patch_top_k.default_recommendation,
                explanation=f"{patch_top_k.explanation} gate={gate.reason}",
                metadata={
                    "workflow_action": result.metrics.get("workflow_action"),
                    "workflow_action_reason": result.metrics.get(
                        "workflow_action_reason"
                    ),
                    "workflow_action_evidence": result.metrics.get(
                        "workflow_action_evidence"
                    ),
                },
            )
            validate_candidate_set_output(
                pending_action,
                require_v1_fields=candidate_set_v1_ready,
                require_s5_fields=candidate_set_v1_ready,
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
        candidate_pairs = _extract_patch_candidates(patch_top_k)
        if not candidate_pairs:
            candidate_pairs = [(selected_candidate, plan_patch)]

        last_failed_result: StepResult | None = None
        recovery_attempts: list[dict[str, Any]] = []
        for index, (candidate, patch_payload) in enumerate(candidate_pairs, start=1):
            recovery = _extract_recovery_metadata(
                plan_patch=patch_payload,
                selected_candidate=candidate,
                source_step=step,
            )
            _emit_replacement_decision_event(
                context,
                step_id=step.id,
                decision="patch_apply_start",
                recovery=recovery,
            )
            try:
                patched_plan = apply_patch(plan, patch_payload)
            except Exception as exc:
                recovery_attempts.append(
                    {
                        "attempt": index,
                        "status": "apply_failed",
                        "error": str(exc),
                        "recovery": recovery,
                    }
                )
                continue

            if _has_insert_before_target(patch_payload, step.id):
                _commit_patched_plan(context, record, patched_plan)
                pending_patch = PendingPatch(
                    target_step_id=step.id,
                    original_step=step,
                    previous_result=result,
                    plan_patch=patch_payload,
                )
                return PatchRunOutcome(
                    plan=patched_plan,
                    step_results=[],
                    next_step_index=step_index,
                    pending_patch=pending_patch,
                )

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
                plan_patch=patch_payload,
            )
            recovery_attempts.append(
                {
                    "attempt": index,
                    "status": patched_result.status,
                    "tool": patched_result.tool,
                    "recovery": recovery,
                }
            )
            if patched_result.status != "failed":
                _commit_patched_plan(context, record, patched_plan)
                return PatchRunOutcome(
                    plan=patched_plan,
                    step_results=[patched_result],
                    next_step_index=patched_index + 1,
                )
            last_failed_result = patched_result

        escalation_recovery = _extract_recovery_metadata(
            plan_patch=plan_patch,
            selected_candidate=selected_candidate,
            source_step=step,
        )
        if last_failed_result is not None:
            _attach_recovery_upgrade_meta(
                last_failed_result,
                escalation_recovery,
                upgrade_reason="patch_failed",
            )
            metrics = dict(last_failed_result.metrics)
            recovery = metrics.get("recovery", {})
            if isinstance(recovery, dict):
                recovery["attempts"] = recovery_attempts
                metrics["recovery"] = recovery
            last_failed_result.metrics = metrics
        _emit_recovery_escalation_event(
            context,
            step_id=step.id,
            reason="patch_failed",
            detail="all patch layers failed; escalate to replan",
            recovery=escalation_recovery,
        )
        _enter_replan_waiting(context, record, reason="patch_failed")
        if last_failed_result is None:
            _attach_recovery_upgrade_meta(
                result,
                escalation_recovery,
                upgrade_reason="patch_failed",
            )
            metrics = dict(result.metrics)
            recovery = metrics.get("recovery", {})
            if isinstance(recovery, dict):
                recovery["attempts"] = recovery_attempts
                metrics["recovery"] = recovery
            result.metrics = metrics
            return PatchRunOutcome(
                plan=plan,
                step_results=[result],
                next_step_index=step_index + 1,
            )
        return PatchRunOutcome(
            plan=plan,
            step_results=[last_failed_result],
            next_step_index=step_index + 1,
        )

    def _should_patch(self, result: StepResult) -> bool:
        if result.status != "failed":
            return False

        retry_exhausted = result.metrics.get("retry_exhausted", False)
        stage_id = _extract_stage_id(result)
        failure_code = _extract_failure_code(result)
        action = resolve_s6_recovery_action(
            stage_id=stage_id,
            failure_code=failure_code,
            failure_type=result.failure_type,
            retry_exhausted=bool(retry_exhausted),
            safety_blocked=result.failure_type == FailureType.SAFETY_BLOCK,
        )
        result.metrics.setdefault("s6_trigger_stage_id", stage_id)
        result.metrics.setdefault("s6_trigger_failure_code", failure_code)
        result.metrics.setdefault("s6_recovery_action", action)
        return action == "patch"

    def _build_runtime_state_preview(
        self,
        *,
        plan: Plan,
        context: WorkflowContext,
        result: StepResult,
    ):
        completed_steps = len(context.step_results)
        if result.step_id not in context.step_results:
            completed_steps += 1
        return update_runtime_state(
            previous_state=context.runtime_state,
            step_result=result,
            failure_context=extract_failure_context(result),
            completed_steps=completed_steps,
            total_steps=len(plan.steps),
        )

    def _select_failed_step_action(
        self,
        result: StepResult,
        *,
        context: WorkflowContext,
        runtime_state_preview,
    ):
        if result.status != "failed":
            return None

        stage_id = _extract_stage_id(result)
        failure_code = _extract_failure_code(result)
        retry_exhausted = bool(result.metrics.get("retry_exhausted"))
        s6_action = resolve_s6_recovery_action(
            stage_id=stage_id,
            failure_code=failure_code,
            failure_type=result.failure_type,
            retry_exhausted=retry_exhausted,
            safety_blocked=result.failure_type == FailureType.SAFETY_BLOCK,
        )
        result.metrics.setdefault("s6_trigger_stage_id", stage_id)
        result.metrics.setdefault("s6_trigger_failure_code", failure_code)
        result.metrics.setdefault("s6_recovery_action", s6_action)

        decision = select_workflow_action(
            WorkflowActionSelectorInput(
                phase="patch",
                stage_id=stage_id,
                failure_code=failure_code,
                failure_type=result.failure_type,
                retry_exhausted=retry_exhausted,
                safety_blocked=result.failure_type == FailureType.SAFETY_BLOCK,
                runtime_state_summary=runtime_state_preview.to_summary_payload(),
            )
        )
        _attach_workflow_action_meta(result, decision)
        if decision.action != "patch_local":
            metrics = dict(result.metrics)
            metrics.setdefault("retry_exhausted", True)
            result.metrics = metrics
        if decision.action != "patch_local":
            return None
        return decision

    def _select_candidate_action(
        self,
        *,
        context: WorkflowContext,
        result: StepResult,
        runtime_state_preview,
        phase: str,
        suggested_action: Any,
        suggested_reason: Any,
    ):
        decision = select_workflow_action(
            WorkflowActionSelectorInput(
                phase=phase,
                stage_id=_extract_stage_id(result),
                failure_code=_extract_failure_code(result),
                failure_type=result.failure_type,
                retry_exhausted=bool(result.metrics.get("retry_exhausted")),
                safety_blocked=result.failure_type == FailureType.SAFETY_BLOCK,
                runtime_state_summary=runtime_state_preview.to_summary_payload(),
                suggested_action=suggested_action if isinstance(suggested_action, str) else None,
                suggested_reason=suggested_reason if isinstance(suggested_reason, str) else None,
            )
        )
        _attach_workflow_action_meta(result, decision)
        return decision

    def _attach_patch_meta(
        self,
        patched_result: StepResult,
        *,
        original_step,
        previous_result: StepResult,
        plan_patch: PlanPatch,
    ) -> None:
        """将 patch 关键信息写入 patched_result.metrics"""
        recovery = _extract_recovery_metadata(
            plan_patch=plan_patch,
            selected_candidate=None,
            source_step=original_step,
            patched_step=patched_result,
        )
        patch_info = {
            "applied": True,
            "ops": [op.op for op in plan_patch.operations],
            "from_tool": original_step.tool,
            "to_tool": patched_result.tool,
            "original_step_id": original_step.id,
            "patched_step_id": patched_result.step_id,
            "patched_status": patched_result.status,
            "previous_attempt": _summarize_result(previous_result),
            "layer": recovery.get("recovery_layer"),
            "capability_id": recovery.get("capability_id"),
            "reason": recovery.get("reason"),
        }
        metrics = dict(patched_result.metrics)
        metrics["patch"] = patch_info
        metrics["recovery"] = {
            **recovery,
            "upgrade_reason": (
                "patch_failed"
                if patched_result.status == "failed"
                else None
            ),
        }
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


def _extract_recovery_metadata(
    *,
    plan_patch: PlanPatch | None,
    selected_candidate: PendingActionCandidate | None,
    source_step: PlanStep,
    patched_step: StepResult | None = None,
) -> dict[str, Any]:
    metadata = (
        plan_patch.metadata
        if plan_patch is not None and isinstance(plan_patch.metadata, dict)
        else {}
    )
    candidate_meta = (
        selected_candidate.metadata
        if selected_candidate is not None and isinstance(selected_candidate.metadata, dict)
        else {}
    )
    capability_id = metadata.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id:
        capability_id = selected_candidate.capability_id if selected_candidate else None
    if not isinstance(capability_id, str) or not capability_id:
        capability_id = _extract_capability_from_step(source_step)

    from_tool = metadata.get("from_tool")
    if not isinstance(from_tool, str) or not from_tool:
        from_tool = source_step.tool
    to_tool = metadata.get("to_tool")
    if not isinstance(to_tool, str) or not to_tool:
        to_tool = (
            patched_step.tool
            if patched_step is not None
            else (selected_candidate.tool_id if selected_candidate else source_step.tool)
        )
    recovery_layer = metadata.get("recovery_layer")
    if not isinstance(recovery_layer, str) or not recovery_layer:
        recovery_layer = str(candidate_meta.get("recovery_layer") or "tool_level")
    reason = metadata.get("reason")
    if not isinstance(reason, str) or not reason:
        reason = str(candidate_meta.get("reason") or candidate_meta.get("recovery_reason") or "patch_required")

    payload: dict[str, Any] = {
        "recovery_layer": recovery_layer,
        "capability_id": capability_id,
        "from_tool": from_tool,
        "to_tool": to_tool,
        "reason": reason,
        "candidate_id": selected_candidate.candidate_id if selected_candidate else None,
        "io_type": selected_candidate.io_type if selected_candidate else None,
        "adapter_mode": selected_candidate.adapter_mode if selected_candidate else None,
    }
    for key in (
        "runtime_state_summary",
        "action_score",
        "shadow_score",
        "default_recommendation_reason",
    ):
        value = candidate_meta.get(key)
        if value is not None:
            payload[key] = value
    if isinstance(metadata.get("strategy"), str):
        payload["strategy"] = metadata.get("strategy")
    return payload


def _attach_recovery_upgrade_meta(
    result: StepResult,
    recovery_meta: dict[str, Any],
    *,
    upgrade_reason: str,
) -> None:
    metrics = dict(result.metrics)
    recovery = dict(recovery_meta)
    recovery["upgrade_reason"] = upgrade_reason
    metrics["recovery"] = recovery
    result.metrics = metrics
    error_details = dict(result.error_details)
    error_details["recovery"] = recovery
    normalized_code = upgrade_reason.upper()
    if not normalized_code.startswith("PATCH_"):
        normalized_code = f"PATCH_{normalized_code}"
    error_details["failure_code"] = normalized_code
    result.error_details = error_details


def _attach_workflow_action_meta(
    result: StepResult,
    decision,
) -> None:
    metrics = dict(result.metrics)
    metrics["workflow_action"] = decision.action
    metrics["workflow_action_mapped_flow"] = decision.mapped_flow
    metrics["workflow_action_reason"] = decision.reason
    metrics["workflow_action_evidence"] = dict(decision.evidence_source)
    result.metrics = metrics


def _emit_replacement_decision_event(
    context: WorkflowContext,
    *,
    step_id: str,
    decision: str,
    recovery: dict[str, Any],
) -> None:
    layer = str(recovery.get("recovery_layer") or "tool_level")
    event_name = {
        "parameter_level": "PARAM_TWEAK",
        "tool_level": "REPLACE_TOOL",
        "structure_level": "STRUCTURE_PATCH",
    }.get(layer, "REPLACE_TOOL")
    append_event(
        context.task.task_id,
        {
            "event": event_name,
            "task_id": context.task.task_id,
            "step_id": step_id,
            "timestamp": now_iso(),
            "state": context.status.value,
            "external_status": to_external_status(context.status).value,
            "data": {
                "action_name": "patch",
                "action_score": recovery.get("action_score"),
                "decision": decision,
                "shadow_score": recovery.get("shadow_score"),
                "evidence_source": recovery.get("default_recommendation_reason"),
                "recovery": recovery,
                "runtime_state_summary": build_context_runtime_state_summary(
                    context,
                    require_runtime_state=True,
                ),
            },
        },
    )


def _emit_recovery_escalation_event(
    context: WorkflowContext,
    *,
    step_id: str,
    reason: str,
    detail: str,
    recovery: dict[str, Any],
) -> None:
    append_event(
        context.task.task_id,
        {
            "event": "RECOVERY_ESCALATED",
            "task_id": context.task.task_id,
            "step_id": step_id,
            "timestamp": now_iso(),
            "state": context.status.value,
            "external_status": to_external_status(context.status).value,
            "data": {
                "action_name": "replan",
                "action_score": recovery.get("action_score"),
                "reason": reason,
                "detail": detail,
                "shadow_score": recovery.get("shadow_score"),
                "evidence_source": recovery.get("default_recommendation_reason"),
                "recovery": recovery,
                "runtime_state_summary": build_context_runtime_state_summary(
                    context,
                    require_runtime_state=True,
                ),
            },
        },
    )


def _extract_capability_from_step(step: PlanStep) -> str:
    metadata = step.metadata if isinstance(step.metadata, dict) else {}
    raw = metadata.get("capability")
    if isinstance(raw, str) and raw:
        return raw
    values = metadata.get("capabilities")
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and item:
                return item
    return "unknown"


def _extract_patch_candidates(
    top_k: TopKResult,
) -> list[tuple[PendingActionCandidate, PlanPatch]]:
    pairs: list[tuple[PendingActionCandidate, PlanPatch]] = []
    for candidate in top_k.candidates:
        payload = candidate.structured_payload or candidate.payload
        if isinstance(payload, PlanPatch):
            pairs.append((candidate, payload))
    if not pairs:
        return []
    if top_k.default_recommendation:
        pairs.sort(
            key=lambda pair: (
                0 if pair[0].candidate_id == top_k.default_recommendation else 1,
                _recovery_layer_rank(pair[1]),
                pair[0].candidate_id,
            )
        )
    else:
        pairs.sort(
            key=lambda pair: (
                _recovery_layer_rank(pair[1]),
                pair[0].candidate_id,
            )
        )
    return pairs


def _extract_stage_id(result: StepResult) -> str | None:
    outputs = result.outputs if isinstance(result.outputs, dict) else {}
    stage_id = outputs.get("stage_id")
    if isinstance(stage_id, str) and stage_id:
        return stage_id
    return None


def _extract_failure_code(result: StepResult) -> str | None:
    details = result.error_details if isinstance(result.error_details, dict) else {}
    failure_code = details.get("failure_code")
    if isinstance(failure_code, str) and failure_code:
        return failure_code
    return None


def _recovery_layer_rank(patch: PlanPatch) -> int:
    metadata = patch.metadata if isinstance(patch.metadata, dict) else {}
    raw_rank = metadata.get("recovery_layer_rank")
    try:
        return int(raw_rank)
    except (TypeError, ValueError):
        return 99


def _commit_patched_plan(
    context: WorkflowContext,
    record: TaskRecord | None,
    patched_plan: Plan,
) -> None:
    if context.plan is None or context.plan.task_id == patched_plan.task_id:
        context.plan = patched_plan
    if record is not None and (
        record.plan is None or record.plan.task_id == patched_plan.task_id
    ):
        record.plan = patched_plan


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
        explanation=f"patch escalation ({reason}); replan confirmation required",
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
