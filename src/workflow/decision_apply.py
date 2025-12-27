from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from src.models.contracts import (
    Decision,
    DecisionChoice,
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    PendingActionType,
    Plan,
    PlanPatch,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord, to_external_status
from src.storage.log_store import append_event
from src.workflow.context import WorkflowContext
from src.workflow.patch import apply_patch
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.workflow.snapshots import (
    SnapshotWriter,
    build_task_snapshot,
    default_snapshot_writer,
)
from src.workflow.status import StatusLogger, transition_task_status

EventLogger = Callable[[dict], None]

_ALLOWED_CHOICES = {
    PendingActionType.PLAN_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.REPLAN,
        DecisionChoice.CANCEL,
    },
    PendingActionType.PATCH_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.REPLAN,
        DecisionChoice.CANCEL,
    },
    PendingActionType.REPLAN_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.CONTINUE,
        DecisionChoice.CANCEL,
    },
}

_EXPECTED_EXTERNAL = {
    PendingActionType.PLAN_CONFIRM: ExternalStatus.WAITING_PLAN_CONFIRM,
    PendingActionType.PATCH_CONFIRM: ExternalStatus.WAITING_PATCH_CONFIRM,
    PendingActionType.REPLAN_CONFIRM: ExternalStatus.WAITING_REPLAN_CONFIRM,
}


class DecisionApplyError(ValueError):
    """Base error for decision application."""


class DecisionConflictError(DecisionApplyError):
    """409-like conflict: pending action already resolved or status mismatch."""

    status_code = 409


@dataclass(frozen=True)
class DecisionApplyResult:
    status: ExternalStatus
    internal_status: InternalStatus
    plan: Optional[Plan] = None
    plan_patch: Optional[PlanPatch] = None
    pending_action: Optional[PendingAction] = None


def apply_plan_confirm_decision(
    context: WorkflowContext,
    record: TaskRecord | None,
    decision: Decision,
    *,
    pending_action: PendingAction | None = None,
    event_logger: EventLogger | None = None,
    status_logger: StatusLogger | None = None,
    snapshot_writer: SnapshotWriter | None = None,
) -> DecisionApplyResult:
    """Apply a plan_confirm decision."""
    action = _resolve_pending_action(context, record, pending_action)
    _ensure_action_type(action, PendingActionType.PLAN_CONFIRM)
    _validate_decision_and_state(context, record, action, decision)

    logger = event_logger or _default_event_logger
    logger(_decision_event("DECISION_SUBMITTED", context, action, decision))

    selected_plan: Optional[Plan] = None
    if decision.choice == DecisionChoice.ACCEPT:
        candidate = _select_candidate(action, decision)
        selected_plan = _ensure_plan_payload(candidate)
        _apply_plan_to_context(context, record, selected_plan)
        transition_task_status(
            context,
            record,
            InternalStatus.PLANNED,
            reason="decision_accept_plan",
            logger=status_logger,
        )
        action.status = PendingActionStatus.DECIDED
    elif decision.choice == DecisionChoice.REPLAN:
        transition_task_status(
            context,
            record,
            InternalStatus.PLANNING,
            reason="decision_replan_requested",
            logger=status_logger,
        )
        action.status = PendingActionStatus.DECIDED
    elif decision.choice == DecisionChoice.CANCEL:
        transition_task_status(
            context,
            record,
            InternalStatus.CANCELLED,
            reason="decision_cancelled",
            logger=status_logger,
        )
        action.status = PendingActionStatus.CANCELLED
    else:
        raise DecisionApplyError(f"Unsupported decision choice: {decision.choice}")

    action.decided_at = now_iso()
    _sync_pending_action(context, record, action)
    logger(_decision_event("DECISION_APPLIED", context, action, decision))
    _write_snapshot(context, action, snapshot_writer)

    return DecisionApplyResult(
        status=to_external_status(context.status),
        internal_status=context.status,
        plan=selected_plan,
        pending_action=action,
    )


def apply_patch_confirm_decision(
    context: WorkflowContext,
    record: TaskRecord | None,
    decision: Decision,
    *,
    pending_action: PendingAction | None = None,
    event_logger: EventLogger | None = None,
    status_logger: StatusLogger | None = None,
    snapshot_writer: SnapshotWriter | None = None,
) -> DecisionApplyResult:
    """Apply a patch_confirm decision."""
    action = _resolve_pending_action(context, record, pending_action)
    _ensure_action_type(action, PendingActionType.PATCH_CONFIRM)
    _validate_decision_and_state(context, record, action, decision)

    logger = event_logger or _default_event_logger
    logger(_decision_event("DECISION_SUBMITTED", context, action, decision))

    selected_patch: Optional[PlanPatch] = None
    selected_plan: Optional[Plan] = None
    if decision.choice == DecisionChoice.ACCEPT:
        candidate = _select_candidate(action, decision)
        selected_patch = _ensure_patch_payload(candidate)
        selected_plan = _apply_patch_to_context(context, record, selected_patch)
        if context.status == InternalStatus.WAITING_PATCH:
            transition_task_status(
                context,
                record,
                InternalStatus.PATCHING,
                reason="decision_accept_patch",
                logger=status_logger,
            )
        transition_task_status(
            context,
            record,
            InternalStatus.RUNNING,
            reason="decision_patch_applied",
            logger=status_logger,
        )
        action.status = PendingActionStatus.DECIDED
    elif decision.choice == DecisionChoice.REPLAN:
        action.status = PendingActionStatus.CANCELLED
        action.decided_at = now_iso()
        _sync_pending_action(context, record, action)

        replan_action_id = f"{action.pending_action_id}_replan"
        replan_action = build_pending_action(
            task_id=context.task.task_id,
            action_type=PendingActionType.REPLAN_CONFIRM,
            candidates=[],
            pending_action_id=replan_action_id,
            default_suggestion=None,
            explanation="patch_confirm rejected; replan confirmation required",
        )
        enter_waiting_state(
            context,
            record,
            replan_action,
            InternalStatus.WAITING_REPLAN,
            reason="decision_replan_requested",
            event_logger=event_logger,
            status_logger=status_logger,
            snapshot_writer=snapshot_writer,
        )

        logger(_decision_event("DECISION_APPLIED", context, action, decision))
        _write_snapshot(context, replan_action, snapshot_writer)
        return DecisionApplyResult(
            status=to_external_status(context.status),
            internal_status=context.status,
            plan=None,
            plan_patch=None,
            pending_action=replan_action,
        )
    elif decision.choice == DecisionChoice.CANCEL:
        transition_task_status(
            context,
            record,
            InternalStatus.CANCELLED,
            reason="decision_cancelled",
            logger=status_logger,
        )
        action.status = PendingActionStatus.CANCELLED
    else:
        raise DecisionApplyError(f"Unsupported decision choice: {decision.choice}")

    action.decided_at = now_iso()
    _sync_pending_action(context, record, action)
    logger(_decision_event("DECISION_APPLIED", context, action, decision))
    _write_snapshot(context, action, snapshot_writer)

    return DecisionApplyResult(
        status=to_external_status(context.status),
        internal_status=context.status,
        plan=selected_plan,
        plan_patch=selected_patch,
        pending_action=action,
    )


def apply_replan_confirm_decision(
    context: WorkflowContext,
    record: TaskRecord | None,
    decision: Decision,
    *,
    pending_action: PendingAction | None = None,
    event_logger: EventLogger | None = None,
    status_logger: StatusLogger | None = None,
    snapshot_writer: SnapshotWriter | None = None,
) -> DecisionApplyResult:
    """Apply a replan_confirm decision."""
    action = _resolve_pending_action(context, record, pending_action)
    _ensure_action_type(action, PendingActionType.REPLAN_CONFIRM)
    _validate_decision_and_state(context, record, action, decision)

    logger = event_logger or _default_event_logger
    logger(_decision_event("DECISION_SUBMITTED", context, action, decision))

    selected_plan: Optional[Plan] = None
    if decision.choice == DecisionChoice.ACCEPT:
        candidate = _select_candidate(action, decision)
        selected_plan = _ensure_plan_payload(candidate)
        _apply_plan_to_context(context, record, selected_plan)
        transition_task_status(
            context,
            record,
            InternalStatus.PLANNING,
            reason="decision_accept_replan",
            logger=status_logger,
        )
        action.status = PendingActionStatus.DECIDED
    elif decision.choice == DecisionChoice.CONTINUE:
        transition_task_status(
            context,
            record,
            InternalStatus.RUNNING,
            reason="decision_continue_running",
            logger=status_logger,
        )
        action.status = PendingActionStatus.DECIDED
    elif decision.choice == DecisionChoice.CANCEL:
        transition_task_status(
            context,
            record,
            InternalStatus.CANCELLED,
            reason="decision_cancelled",
            logger=status_logger,
        )
        action.status = PendingActionStatus.CANCELLED
    else:
        raise DecisionApplyError(f"Unsupported decision choice: {decision.choice}")

    action.decided_at = now_iso()
    _sync_pending_action(context, record, action)
    logger(_decision_event("DECISION_APPLIED", context, action, decision))
    _write_snapshot(context, action, snapshot_writer)

    return DecisionApplyResult(
        status=to_external_status(context.status),
        internal_status=context.status,
        plan=selected_plan,
        pending_action=action,
    )


def _resolve_pending_action(
    context: WorkflowContext,
    record: TaskRecord | None,
    pending_action: PendingAction | None,
) -> PendingAction:
    action = (
        pending_action
        or context.pending_action
        or (record.pending_action if record is not None else None)
    )
    if action is None:
        raise DecisionApplyError("PendingAction is required for decision application")
    if (
        context.pending_action
        and context.pending_action.pending_action_id != action.pending_action_id
    ):
        raise DecisionApplyError(
            "Context pending_action does not match provided action"
        )
    if (
        record is not None
        and record.pending_action
        and (record.pending_action.pending_action_id != action.pending_action_id)
    ):
        raise DecisionApplyError("Record pending_action does not match provided action")
    return action


def _ensure_action_type(
    action: PendingAction,
    expected: PendingActionType,
) -> None:
    if action.action_type != expected:
        raise DecisionApplyError(
            f"PendingAction.action_type ({action.action_type.value}) "
            f"does not match expected {expected.value}"
        )


def _validate_decision_and_state(
    context: WorkflowContext,
    record: TaskRecord | None,
    action: PendingAction,
    decision: Decision,
) -> None:
    if action.status != PendingActionStatus.PENDING:
        raise DecisionConflictError("PendingAction has already been decided")
    if decision.task_id != context.task.task_id:
        raise DecisionApplyError("Decision.task_id does not match task")
    if decision.pending_action_id != action.pending_action_id:
        raise DecisionApplyError("Decision.pending_action_id does not match action")
    expected_status = _EXPECTED_EXTERNAL[action.action_type]
    actual_status = to_external_status(context.status)
    if actual_status != expected_status:
        raise DecisionConflictError(
            f"Task status {actual_status.value} does not match "
            f"PendingAction {action.action_type.value}"
        )
    if record is not None and record.status != expected_status:
        raise DecisionConflictError(
            f"Record status {record.status.value} does not match "
            f"PendingAction {action.action_type.value}"
        )
    if decision.choice not in _ALLOWED_CHOICES[action.action_type]:
        raise DecisionApplyError(
            f"Choice {decision.choice.value} is not allowed for "
            f"{action.action_type.value}"
        )


def _select_candidate(
    action: PendingAction,
    decision: Decision,
) -> PendingActionCandidate:
    selected_id = decision.selected_candidate_id
    if not selected_id:
        raise DecisionApplyError("selected_candidate_id is required for accept")
    for candidate in action.candidates:
        if candidate.candidate_id == selected_id:
            return candidate
    raise DecisionApplyError("selected_candidate_id is not in candidates")


def _ensure_plan_payload(candidate: PendingActionCandidate) -> Plan:
    payload = candidate.payload
    if not isinstance(payload, Plan):
        raise DecisionApplyError("Selected candidate payload is not a Plan")
    return payload


def _ensure_patch_payload(candidate: PendingActionCandidate) -> PlanPatch:
    payload = candidate.payload
    if not isinstance(payload, PlanPatch):
        raise DecisionApplyError("Selected candidate payload is not a PlanPatch")
    return payload


def _apply_plan_to_context(
    context: WorkflowContext,
    record: TaskRecord | None,
    plan: Plan,
) -> None:
    context.plan = plan
    if record is not None:
        record.plan = plan


def _apply_patch_to_context(
    context: WorkflowContext,
    record: TaskRecord | None,
    patch: PlanPatch,
) -> Plan:
    if context.plan is None:
        raise DecisionApplyError("Cannot apply patch without an existing plan")
    patched_plan = apply_patch(context.plan, patch)
    context.plan = patched_plan
    if record is not None:
        record.plan = patched_plan
    return patched_plan


def _sync_pending_action(
    context: WorkflowContext,
    record: TaskRecord | None,
    action: PendingAction,
) -> None:
    context.pending_action = action
    if record is not None:
        record.pending_action = action


def _write_snapshot(
    context: WorkflowContext,
    action: PendingAction,
    snapshot_writer: SnapshotWriter | None,
) -> None:
    pending_id = None
    if (
        to_external_status(context.status)
        in (
            ExternalStatus.WAITING_PLAN_CONFIRM,
            ExternalStatus.WAITING_PATCH_CONFIRM,
            ExternalStatus.WAITING_REPLAN_CONFIRM,
        )
        and action.status == PendingActionStatus.PENDING
    ):
        pending_id = action.pending_action_id
    snapshot = build_task_snapshot(
        context,
        pending_action_id=pending_id,
    )
    (snapshot_writer or default_snapshot_writer)(snapshot)


def _decision_event(
    event_name: str,
    context: WorkflowContext,
    action: PendingAction,
    decision: Decision,
) -> dict:
    return {
        "event": event_name,
        "task_id": context.task.task_id,
        "pending_action_id": action.pending_action_id,
        "decision_id": decision.decision_id,
        "choice": decision.choice.value,
        "selected_candidate_id": decision.selected_candidate_id,
        "state": to_external_status(context.status).value,
        "internal_status": context.status.value,
    }


def _default_event_logger(event: dict) -> None:
    task_id = event.get("task_id")
    if not task_id:
        return
    append_event(task_id, event)
