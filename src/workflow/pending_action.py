"""PendingAction 等待状态工具函数。

该模块用于在进入 WAITING_* 状态前构造并持久化 PendingAction，
并写入快照与事件日志以满足 HITL 约束。
"""
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
from src.workflow.snapshots import (
    SnapshotWriter,
    build_task_snapshot,
    default_snapshot_writer,
)

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
    explanation: str,
    created_by: str = "system",
) -> PendingAction:
    """构造最小化 PendingAction 实例。

    Args:
        task_id: 任务 ID。
        action_type: 待决策类型。
        candidates: 候选集合（可为空）。
        pending_action_id: 可选的 PendingAction ID（默认自动生成）。
        default_suggestion: 默认建议的候选 ID。
        explanation: 解释说明文本。
        created_by: 创建者标识（默认 system）。

    Returns:
        PendingAction 实例。
    """
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
    snapshot_writer: SnapshotWriter | None = None,
) -> None:
    """在进入 WAITING_* 前写入 PendingAction 与快照。

    NOTE: This helper does not transition task status. Callers must invoke
    transition_task_status explicitly to enter WAITING_*.

    Args:
        context: 工作流上下文。
        record: 可选的任务持久化记录。
        pending_action: 待写入的 PendingAction。
        to_status: 目标 WAITING_* 内部状态。
        reason: 可选的原因说明（仅用于调用方日志语义）。
        event_logger: 可选的事件日志回调。
        snapshot_writer: 可选的快照写入回调。

    Raises:
        ValueError: 当 PendingAction 与目标 WAITING_* 状态不匹配。
    """
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
    _ = reason


def _validate_waiting_transition(
    context: WorkflowContext,
    pending_action: PendingAction,
    to_status: InternalStatus,
    record: TaskRecord | None,
) -> None:
    """校验 WAITING_* 转移的 PendingAction 一致性。

    Args:
        context: 工作流上下文。
        pending_action: 待验证的 PendingAction。
        to_status: 目标 WAITING_* 内部状态。
        record: 可选的任务持久化记录。

    Raises:
        ValueError: 当状态或 pending_action 不一致时抛出。
    """
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
    """将 WAITING_* 内部状态映射为对外状态。

    Args:
        to_status: 内部状态。

    Returns:
        ExternalStatus 对外状态。
    """
    if to_status in _WAITING_ACTION_MAP:
        return to_external_status(to_status)
    return to_external_status(to_status)


def _default_event_logger(event: dict) -> None:
    """默认事件日志记录器（写入 log_store）。

    Args:
        event: 事件字典。
    """
    task_id = event.get("task_id")
    if not task_id:
        return
    append_event(task_id, event)
