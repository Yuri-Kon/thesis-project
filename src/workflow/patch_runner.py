from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.agents.candidate_generator.models import TopKResult
from src.agents.planner import PlannerAgent
from src.models.contracts import (
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanStep,
    RuntimeState,
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
    WorkflowActionSelectorResult,
    WorkflowActionSelectorInput,
    resolve_s6_recovery_action,
    select_workflow_action,
)
from src.workflow.snapshots import build_context_runtime_state_summary
from src.workflow.step_runner import StepRunner
from src.workflow.status import transition_task_status
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.workflow.runtime_policy import resolve_runtime_policy, runtime_policy_uses_belief_state
from src.workflow.patch_recovery_metadata import (
    extract_capability_from_step as _extract_capability_from_step_impl,
    extract_recovery_metadata,
)
from src.workflow.failure_codes import extract_step_failure_code


class StepRunnerLike(Protocol):
    """最小化约束的 StepRunner 接口（便于注入/测试）"""

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
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


@dataclass(frozen=True)
class PatchCandidateSet:
    plan_patch: PlanPatch
    selected_candidate: PendingActionCandidate
    patch_top_k: TopKResult
    candidate_set_v1_ready: bool


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
        return self._run_step_with_patch_impl(
            plan,
            step_index,
            context,
            record=record,
        )

    def _run_step_with_patch_impl(
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
            candidate_set = self._build_patch_candidate_set(
                plan=plan,
                context=context,
                step=step,
                step_index=step_index,
                result=result,
                patch_reason=patch_reason,
                runtime_state_preview=runtime_state_preview,
            )
            if candidate_set is None:
                return PatchRunOutcome(
                    plan=plan,
                    step_results=[result],
                    next_step_index=step_index + 1,
                )
            selected_candidate = candidate_set.selected_candidate
            gate = self._planner.evaluate_top_k_gate(
                candidate_kind="patch",
                top_k_result=candidate_set.patch_top_k,
                task_constraints=context.task.constraints,
            )
        except Exception as exc:
            recovery_meta = _extract_recovery_metadata(
                plan_patch=None,
                selected_candidate=selected_candidate,
                source_step=step,
            )
            _attach_recovery_upgrade_meta(
                result,
                recovery_meta,
                upgrade_reason="patch_failed",
            )
            _emit_recovery_escalation_event(
                context,
                step_id=step.id,
                reason="patch_failed",
                detail=f"patch candidate generation failed: {exc}",
                recovery=recovery_meta,
            )
            _enter_replan_waiting(context, record, reason="patch_failed")
            return PatchRunOutcome(
                plan=plan,
                step_results=[result],
                next_step_index=step_index + 1,
            )

        if gate.requires_hitl:
            recovery_meta = _extract_recovery_metadata(
                plan_patch=candidate_set.plan_patch,
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
                candidates=candidate_set.patch_top_k.candidates,
                default_suggestion=candidate_set.patch_top_k.default_recommendation,
                default_recommendation=candidate_set.patch_top_k.default_recommendation,
                explanation=f"{candidate_set.patch_top_k.explanation} gate={gate.reason}",
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
                require_v1_fields=candidate_set.candidate_set_v1_ready,
                require_s5_fields=candidate_set.candidate_set_v1_ready,
                require_shadow_rerank_fields=candidate_set.candidate_set_v1_ready,
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
        candidate_pairs = _extract_patch_candidates(candidate_set.patch_top_k)
        if not candidate_pairs:
            candidate_pairs = [(selected_candidate, candidate_set.plan_patch)]

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
            plan_patch=candidate_set.plan_patch,
            selected_candidate=selected_candidate,
            source_step=step,
        )
        if last_failed_result is not None:
            _attach_recovery_upgrade_meta(
                last_failed_result,
                escalation_recovery,
                upgrade_reason="patch_failed",
            )
            _attach_recovery_attempts(last_failed_result, recovery_attempts)
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
            _attach_recovery_attempts(result, recovery_attempts)
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

    def _build_patch_candidate_set(
        self,
        *,
        plan: Plan,
        context: WorkflowContext,
        step: PlanStep,
        step_index: int,
        result: StepResult,
        patch_reason: str,
        runtime_state_preview: RuntimeState | None,
    ) -> PatchCandidateSet | None:
        patch_request = build_patch_request(
            plan=plan,
            failed_step_index=step_index,
            failed_result=result,
            context=context,
        )
        try:
            patch_top_k = self._planner.patch_top_k(
                patch_request,
                k=_resolve_top_k(context.task.constraints.get("patch_top_k"), default=3),
                runtime_state=runtime_state_preview,
            )
            selected_candidate = _select_default_patch_candidate(patch_top_k)
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
                return None
            payload = selected_candidate.structured_payload
            if not isinstance(payload, PlanPatch):
                raise ValueError("patch_top_k default candidate is not PlanPatch")
            return PatchCandidateSet(
                plan_patch=payload,
                selected_candidate=selected_candidate,
                patch_top_k=patch_top_k,
                candidate_set_v1_ready=True,
            )
        except Exception:
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
            return PatchCandidateSet(
                plan_patch=plan_patch,
                selected_candidate=patch_candidate,
                patch_top_k=TopKResult(
                    candidates=[patch_candidate],
                    default_recommendation=patch_candidate.candidate_id,
                    explanation="fallback patch_top_k generated from planner.patch",
                ),
                candidate_set_v1_ready=False,
            )

    def _should_patch(self, result: StepResult) -> bool:
        if result.status != "failed":
            return False

        retry_exhausted = result.metrics.get("retry_exhausted", False)
        stage_id = _extract_stage_id(result)
        failure_code = extract_step_failure_code(result)
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
    ) -> RuntimeState | None:
        if not runtime_policy_uses_belief_state(context.task):
            return None
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
        runtime_state_preview: RuntimeState | None,
    ) -> WorkflowActionSelectorResult | None:
        if result.status != "failed":
            return None

        stage_id = _extract_stage_id(result)
        failure_code = extract_step_failure_code(result)
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
                runtime_state_summary=(
                    runtime_state_preview.to_summary_payload()
                    if runtime_state_preview is not None
                    else None
                ),
                runtime_policy=resolve_runtime_policy(context.task),
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
        runtime_state_preview: RuntimeState | None,
        phase: str,
        suggested_action: Any,
        suggested_reason: Any,
    ) -> WorkflowActionSelectorResult:
        decision = select_workflow_action(
            WorkflowActionSelectorInput(
                phase=phase,
                stage_id=_extract_stage_id(result),
                failure_code=extract_step_failure_code(result),
                failure_type=result.failure_type,
                retry_exhausted=bool(result.metrics.get("retry_exhausted")),
                safety_blocked=result.failure_type == FailureType.SAFETY_BLOCK,
                runtime_state_summary=(
                    runtime_state_preview.to_summary_payload()
                    if runtime_state_preview is not None
                    else None
                ),
                suggested_action=suggested_action if isinstance(suggested_action, str) else None,
                suggested_reason=suggested_reason if isinstance(suggested_reason, str) else None,
                runtime_policy=resolve_runtime_policy(context.task),
            )
        )
        _attach_workflow_action_meta(result, decision)
        return decision

    def _attach_patch_meta(
        self,
        patched_result: StepResult,
        *,
        original_step: PlanStep,
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
    return extract_recovery_metadata(
        plan_patch=plan_patch,
        selected_candidate=selected_candidate,
        source_step=source_step,
        patched_step=patched_step,
    )


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
    decision: WorkflowActionSelectorResult,
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
    _emit_recovery_event(
        context,
        event_name=event_name,
        step_id=step_id,
        recovery=recovery,
        data_overrides={
            "action_name": "patch",
            "decision": decision,
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
    _emit_recovery_event(
        context,
        event_name="RECOVERY_ESCALATED",
        step_id=step_id,
        recovery=recovery,
        data_overrides={
            "action_name": "replan",
            "reason": reason,
            "detail": detail,
        },
    )


def _emit_recovery_event(
    context: WorkflowContext,
    *,
    event_name: str,
    step_id: str,
    recovery: dict[str, Any],
    data_overrides: dict[str, Any],
) -> None:
    data = {
        "action_score": recovery.get("action_score"),
        "shadow_score": recovery.get("shadow_score"),
        "evidence_source": recovery.get("default_recommendation_reason"),
        "recovery": recovery,
        "runtime_state_summary": build_context_runtime_state_summary(
            context,
            require_runtime_state=True,
        ),
        **data_overrides,
    }
    append_event(
        context.task.task_id,
        {
            "event": event_name,
            "task_id": context.task.task_id,
            "step_id": step_id,
            "timestamp": now_iso(),
            "state": context.status.value,
            "external_status": to_external_status(context.status).value,
            "data": data,
        },
    )


def _extract_capability_from_step(step: PlanStep) -> str:
    return _extract_capability_from_step_impl(step)


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
                _recovery_layer_rank(pair[1]),
                0 if pair[0].candidate_id == top_k.default_recommendation else 1,
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


def _select_default_patch_candidate(top_k: TopKResult) -> PendingActionCandidate:
    selected = next(
        (
            candidate
            for candidate in top_k.candidates
            if candidate.candidate_id == top_k.default_recommendation
        ),
        top_k.candidates[0] if top_k.candidates else None,
    )
    if selected is None:
        raise ValueError("patch_top_k returned no candidates")
    return selected


def _attach_recovery_attempts(
    result: StepResult,
    recovery_attempts: list[dict[str, Any]],
) -> None:
    metrics = dict(result.metrics)
    recovery = metrics.get("recovery", {})
    if isinstance(recovery, dict):
        recovery["attempts"] = recovery_attempts
        metrics["recovery"] = recovery
    result.metrics = metrics


def _extract_stage_id(result: StepResult) -> str | None:
    outputs = result.outputs if isinstance(result.outputs, dict) else {}
    stage_id = outputs.get("stage_id")
    if isinstance(stage_id, str) and stage_id:
        return stage_id
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
