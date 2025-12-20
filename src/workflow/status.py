from __future__ import annotations

from typing import Callable, Optional

from src.models.contracts import now_iso
from src.models.db import TERMINAL_STATES, TaskRecord, TaskStatus
from src.storage.log_store import append_event
from src.workflow.context import WorkflowContext

# 状态变更的轻量日志回调。
StatusLogger = Callable[[dict], None]


def _default_status_logger(event: dict) -> None:
    """默认状态日志记录器：写入 data/logs/{task_id}.jsonl"""
    task_id = event.get("task_id")
    if not task_id:
        return
    append_event(task_id, event)

# FSM 允许的状态迁移集合，用于基础校验。
_ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.PLANNING},
    TaskStatus.PLANNING: {TaskStatus.PLANNED},
    TaskStatus.PLANNED: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {
        TaskStatus.SUMMARIZING,
        TaskStatus.WAITING_PATCH,
        TaskStatus.WAITING_REPLAN,
    },
    TaskStatus.WAITING_PATCH: {TaskStatus.PATCHING},
    TaskStatus.PATCHING: {TaskStatus.RUNNING, TaskStatus.WAITING_REPLAN},
    TaskStatus.WAITING_REPLAN: {TaskStatus.REPLANNING},
    TaskStatus.REPLANNING: {TaskStatus.RUNNING},
    TaskStatus.SUMMARIZING: {TaskStatus.DONE},
    TaskStatus.DONE: set(),
    TaskStatus.FAILED: set(),
}


def transition_task_status(
    context: WorkflowContext,
    record: Optional[TaskRecord],
    to_status: TaskStatus,
    *,
    logger: Optional[StatusLogger] = None,
    reason: Optional[str] = None,
    update_timestamp: bool = True,
) -> None:
    """统一入口更新任务状态，并执行最基本校验。

    Args:
        context: 任务运行时上下文。
        record: 可选的持久化记录，用于同步更新状态和时间戳。
        to_status: 目标状态。
        logger: 可选的日志回调，记录 from/to 状态。
        reason: 可选的触发原因，用于日志记录。
        update_timestamp: 是否同步更新 record.updated_at。

    Raises:
        ValueError: 当 context/record 状态不一致、终态被修改或非法跳转时。
    """
    if record is not None and record.status != context.status:
        raise ValueError(
            "TaskStatus mismatch between record and context: "
            f"{record.status} != {context.status}"
        )

    from_status = context.status
    if from_status == to_status:
        return

    if from_status in TERMINAL_STATES:
        raise ValueError(
            f"Cannot transition from terminal status: {from_status}"
        )

    if to_status == TaskStatus.FAILED:
        _apply_status_update(
            context, record, from_status, to_status, logger, reason, update_timestamp
        )
        return

    allowed_targets = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed_targets:
        raise ValueError(
            f"Invalid task status transition: {from_status} -> {to_status}"
        )

    _apply_status_update(
        context,
        record,
        from_status,
        to_status,
        logger,
        reason,
        update_timestamp,
    )


def _apply_status_update(
    context: WorkflowContext,
    record: Optional[TaskRecord],
    from_status: TaskStatus,
    to_status: TaskStatus,
    logger: Optional[StatusLogger],
    reason: Optional[str],
    update_timestamp: bool,
) -> None:
    """内部辅助函数：更新状态并可选写入状态变更事件。"""
    context.status = to_status
    if record is not None:
        record.status = to_status
        if update_timestamp:
            record.updated_at = now_iso()

    log_handler = logger or _default_status_logger
    log_handler(
        {
            "event": "TASK_STATUS_CHANGED",
            "task_id": context.task.task_id,
            "from_status": from_status.value,
            "to_status": to_status.value,
            "state": context.status.value,
            "reason": reason,
        }
    )
