from __future__ import annotations

from typing import Callable, Iterable, Optional
from uuid import uuid4

from src.models.contracts import (
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    PendingActionType,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord, to_external_status
from src.storage.log_store import append_event
from src.workflow.context import WorkflowContext
from src.workflow.snapshots import build_task_snapshot, default_snapshot_writer, SnapshotWriter
from src.workflow.status import StatusLogger, transition_task_status

EventLogger = Callable[[dict], None]

_WAITING_ACTION_MAP = {
    InternalStatus.WAITING_PLAN_CONFIRM: PendingActionType.PLAN_CONFIRM,
    InternalStatus.WAITING_PATCH: PendingActionType.PATCH_CONFIRM,
    InternalStatus.WAITING_REPLAN: PendingActionType.REPLAN_CONFIRM,
}


def build_pending_action(
    task_id: str,
    action_type: PendingActionType,
    candidates: Iterable[PendingActionCandidate] | None = None,
    *,
    pending_action_id: Optional[str] = None,
    default_suggestion: Optional[str] = None,
    explanation: Optional[str] = None,
    created_by: str = "system",
) -> PendingAction:
    """Build a minimal PendingAction instance."""
    return PendingAction(
        pending_action_id=pending_action_id or f"pa_{uuid4().hex[:8]}",
        task_id=task_id,
        action_type=action_type,
        status=PendingActionStatus.PENDING,
        candidates=list(candidates or []),
        default_suggestion=default_suggestion,
        explanation=explanation,
        created_at=now_iso(),
        decided_at=None,
        created_by=created_by,
    )


def enter_waiting_state(
    context: WorkflowContext,
    record: TaskRecord | None,
    pending_action: PendingAction,
    to_status: InternalStatus,
    *,
    reason: Optional[str] = None,
    event_logger: EventLogger | None = None,
    status_logger: StatusLogger | None = None,
    snapshot_writer: SnapshotWriter | None = None,
) -> None:
    """Write PendingAction and TaskSnapshot before entering WAITING_*."""
    _validate_waiting_transition(context, pending_action, to_status, record)
    context.pending_action = pending_action
    if record is not None:
        record.pending_action = pending_action

    log_handler = event_logger or _default_event_logger
    log_handler(
        {
            "event": "PENDING_ACTION_CREATED",
            "task_id": context.task.task_id,
            "pending_action_id": pending_action.pending_action_id,
            "action_type": pending_action.action_type.value,
            "candidate_ids": [c.candidate_id for c in pending_action.candidates],
            "default_suggestion": pending_action.default_suggestion,
        }
    )

    snapshot = build_task_snapshot(
        context,
        state_override=_to_external_waiting_status(to_status),
        pending_action_id=pending_action.pending_action_id,
    )
    (snapshot_writer or default_snapshot_writer)(snapshot)

    transition_task_status(
        context,
        record,
        to_status,
        reason=reason,
        logger=status_logger,
    )


def _validate_waiting_transition(
    context: WorkflowContext,
    pending_action: PendingAction,
    to_status: InternalStatus,
    record: TaskRecord | None,
) -> None:
    expected_action = _WAITING_ACTION_MAP.get(to_status)
    if expected_action is None:
        raise ValueError(f"{to_status.value} is not a WAITING_* status")
    if pending_action.status != PendingActionStatus.PENDING:
        raise ValueError("pending_action must be pending before entering WAITING_*")
    if pending_action.action_type != expected_action:
        raise ValueError(
            f"pending_action.action_type ({pending_action.action_type.value}) "
            f"does not match waiting status {to_status.value}"
        )
    if pending_action.task_id != context.task.task_id:
        raise ValueError("pending_action.task_id does not match task")
    if record is not None and record.status != to_external_status(context.status):
        raise ValueError("record status does not match context status")


def _to_external_waiting_status(to_status: InternalStatus) -> ExternalStatus:
    if to_status in _WAITING_ACTION_MAP:
        return to_external_status(to_status)
    return to_external_status(to_status)


def _default_event_logger(event: dict) -> None:
    task_id = event.get("task_id")
    if not task_id:
        return
    append_event(task_id, event)
