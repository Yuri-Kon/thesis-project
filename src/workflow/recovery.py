"""
workflow/recovery.py

Snapshot-based recovery logic for resuming interrupted tasks.

职责概述：
- 从快照恢复 WorkflowContext
- 提取远程作业上下文并支持继续执行
- 与 PlanRunner.run_plan(resume_from_existing=True) 协同
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from src.models.contracts import (
    PendingAction,
    Plan,
    PlanStep,
    ProteinDesignTask,
    StepResult,
    TaskSnapshot,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus
from src.models.event_log import EventLog, EventType
from src.storage.log_store import DEFAULT_LOG_DIR, read_event_logs
from src.storage.snapshot_store import read_latest_snapshot, DEFAULT_SNAPSHOT_DIR
from src.workflow.context import WorkflowContext

__all__ = [
    "restore_context_from_snapshot",
    "recover_context_with_event_logs",
    "extract_remote_job_context",
    "RemoteJobContext",
    "RecoveryResult",
]


class RemoteJobContext:
    """远程作业上下文，用于恢复中断的远程作业

    Attributes:
        job_id: 远程作业 ID
        endpoint: 远程服务端点 URL
        step_id: 关联的步骤 ID
        status: 作业状态（pending/running/completed/failed）
        submitted_at: 提交时间戳
        metadata: 额外的元数据
    """

    def __init__(
        self,
        job_id: str,
        endpoint: str,
        step_id: str,
        *,
        status: str = "unknown",
        submitted_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.job_id = job_id
        self.endpoint = endpoint
        self.step_id = step_id
        self.status = status
        self.submitted_at = submitted_at
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，用于存入快照"""
        return {
            "job_id": self.job_id,
            "endpoint": self.endpoint,
            "step_id": self.step_id,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RemoteJobContext:
        """从字典恢复远程作业上下文"""
        return cls(
            job_id=data["job_id"],
            endpoint=data["endpoint"],
            step_id=data["step_id"],
            status=data.get("status", "unknown"),
            submitted_at=data.get("submitted_at"),
            metadata=data.get("metadata"),
        )


@dataclass(frozen=True)
class RecoveryResult:
    """恢复结果，包含上下文与回放信息"""

    context: WorkflowContext
    snapshot: TaskSnapshot
    applied_event_logs: Sequence[EventLog]
    resume_from_existing: bool


def restore_context_from_snapshot(
    task: ProteinDesignTask,
    plan: Plan,
    *,
    task_id: Optional[str] = None,
    snapshot: Optional[TaskSnapshot] = None,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> Optional[WorkflowContext]:
    """从快照恢复 WorkflowContext

    Args:
        task: 原始任务对象
        plan: 当前的计划对象
        task_id: 任务 ID（如果未提供则从 task 获取）
        snapshot: 可选的快照对象（如果提供则直接使用，否则从文件读取）
        snapshot_dir: 快照目录

    Returns:
        恢复的 WorkflowContext，如果没有快照则返回 None

    Note:
        恢复的上下文将包含：
        - 原始任务对象
        - 当前计划
        - 已完成的步骤 ID 列表（从 snapshot.completed_step_ids）
        - 恢复的内部状态（从 snapshot.state）
        - 待处理的 pending_action（如果有）

        注意：step_results 会恢复为占位结果（不含真实 outputs），
        PlanRunner 的 resume_from_existing=True 模式会跳过已完成的步骤。
    """
    actual_task_id = task_id or task.task_id

    # 如果没有提供快照，从文件读取最新快照
    if snapshot is None:
        snapshot = read_latest_snapshot(
            actual_task_id,
            snapshot_dir=snapshot_dir,
        )

    # 如果没有快照，返回 None
    if snapshot is None:
        return None

    # 验证快照的 task_id 与传入的一致
    if snapshot.task_id != actual_task_id:
        raise ValueError(
            f"Snapshot task_id ({snapshot.task_id}) does not match "
            f"provided task_id ({actual_task_id})"
        )

    # 将 ExternalStatus 转换为 InternalStatus
    # 注意：这是一个简化的映射，实际可能需要更复杂的逻辑
    status_mapping = {
        ExternalStatus.CREATED.value: InternalStatus.CREATED,
        ExternalStatus.PLANNING.value: InternalStatus.PLANNING,
        ExternalStatus.WAITING_PLAN_CONFIRM.value: InternalStatus.WAITING_PLAN_CONFIRM,
        ExternalStatus.PLANNED.value: InternalStatus.PLANNED,
        ExternalStatus.RUNNING.value: InternalStatus.RUNNING,
        ExternalStatus.WAITING_PATCH_CONFIRM.value: InternalStatus.WAITING_PATCH,
        ExternalStatus.WAITING_REPLAN_CONFIRM.value: InternalStatus.WAITING_REPLAN,
        ExternalStatus.SUMMARIZING.value: InternalStatus.SUMMARIZING,
        ExternalStatus.DONE.value: InternalStatus.DONE,
        ExternalStatus.FAILED.value: InternalStatus.FAILED,
        ExternalStatus.CANCELLED.value: InternalStatus.CANCELLED,
    }
    internal_status = status_mapping.get(
        snapshot.state,
        InternalStatus.CREATED,
    )

    # 创建 WorkflowContext
    context = WorkflowContext(
        task=task,
        plan=plan,
        status=internal_status,
    )

    context.pending_action = _extract_pending_action(snapshot)
    _restore_completed_steps(context, plan, snapshot)

    return context


def extract_remote_job_context(
    snapshot: TaskSnapshot,
    step_id: str,
) -> Optional[RemoteJobContext]:
    """从快照的 artifacts 中提取远程作业上下文

    Args:
        snapshot: 任务快照
        step_id: 步骤 ID

    Returns:
        RemoteJobContext 对象，如果不存在则返回 None

    Note:
        远程作业上下文应存储在 snapshot.artifacts["remote_jobs"][step_id] 中
    """
    remote_jobs = snapshot.artifacts.get("remote_jobs")
    if not isinstance(remote_jobs, dict):
        return None

    job_data = remote_jobs.get(step_id)
    if not isinstance(job_data, dict):
        return None

    try:
        return RemoteJobContext.from_dict(job_data)
    except (KeyError, TypeError, ValueError):
        return None


def recover_context_with_event_logs(
    task: ProteinDesignTask,
    plan: Plan,
    *,
    task_id: Optional[str] = None,
    snapshot: Optional[TaskSnapshot] = None,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    log_dir: Optional[Path] = None,
) -> Optional[RecoveryResult]:
    """从快照恢复上下文，并结合 EventLog 回放对齐状态"""
    context = restore_context_from_snapshot(
        task=task,
        plan=plan,
        task_id=task_id,
        snapshot=snapshot,
        snapshot_dir=snapshot_dir,
    )
    if context is None:
        return None

    actual_snapshot = snapshot or read_latest_snapshot(
        task_id or task.task_id, snapshot_dir=snapshot_dir
    )
    if actual_snapshot is None:
        return None

    events = read_event_logs(
        actual_snapshot.task_id, log_dir=log_dir or DEFAULT_LOG_DIR
    )
    applied_events = _apply_event_log_replay(context, actual_snapshot, events)
    resume_from_existing = _should_resume_after_recovery(context)
    return RecoveryResult(
        context=context,
        snapshot=actual_snapshot,
        applied_event_logs=applied_events,
        resume_from_existing=resume_from_existing,
    )


def _restore_completed_steps(
    context: WorkflowContext,
    plan: Plan,
    snapshot: TaskSnapshot,
) -> None:
    step_ids = _resolve_completed_step_ids(plan, snapshot)
    if not step_ids:
        return
    step_lookup = {step.id: step for step in plan.steps}
    for step_id in step_ids:
        step = step_lookup.get(step_id)
        if step is None:
            continue
        context.step_results.setdefault(
            step_id,
            _build_stub_step_result(
                task_id=context.task.task_id,
                step=step,
                timestamp=snapshot.created_at or now_iso(),
            ),
        )


def _resolve_completed_step_ids(plan: Plan, snapshot: TaskSnapshot) -> list[str]:
    if snapshot.completed_step_ids:
        return list(snapshot.completed_step_ids)
    if snapshot.step_index <= 0:
        return []
    step_index = min(snapshot.step_index, len(plan.steps))
    return [step.id for step in plan.steps[:step_index]]


def _build_stub_step_result(
    *,
    task_id: str,
    step: PlanStep,
    timestamp: str,
) -> StepResult:
    return StepResult(
        task_id=task_id,
        step_id=step.id,
        tool=step.tool,
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={},
        metrics={"recovered": True, "outputs_missing": True},
        risk_flags=[],
        logs_path=None,
        timestamp=timestamp,
    )


def _extract_pending_action(snapshot: TaskSnapshot) -> Optional[PendingAction]:
    payload = snapshot.artifacts.get("pending_action")
    if not isinstance(payload, dict):
        return None
    try:
        action = PendingAction.model_validate(payload)
    except Exception:
        return None
    if snapshot.pending_action_id and action.pending_action_id != snapshot.pending_action_id:
        return None
    return action


def _apply_event_log_replay(
    context: WorkflowContext,
    snapshot: TaskSnapshot,
    events: Iterable[EventLog],
) -> list[EventLog]:
    filtered = _filter_events_after_snapshot(snapshot, events)
    pending_action = context.pending_action
    for event in filtered:
        if event.new_status is None:
            continue
        if event.event_type == EventType.WAITING_ENTER:
            context.status = _to_internal_status(event.new_status)
            if event.pending_action_id and pending_action:
                if pending_action.pending_action_id != event.pending_action_id:
                    pending_action = None
            if event.pending_action_id and pending_action is None:
                pending_action = _extract_pending_action(snapshot)
        elif event.event_type in (EventType.WAITING_EXIT, EventType.DECISION_APPLIED):
            context.status = _to_internal_status(event.new_status)
            if pending_action and event.pending_action_id:
                if pending_action.pending_action_id == event.pending_action_id:
                    pending_action = None
            else:
                pending_action = None
    if context.status not in (
        InternalStatus.WAITING_PLAN_CONFIRM,
        InternalStatus.WAITING_PATCH,
        InternalStatus.WAITING_REPLAN,
    ):
        pending_action = None
    context.pending_action = pending_action
    return filtered


def _filter_events_after_snapshot(
    snapshot: TaskSnapshot,
    events: Iterable[EventLog],
) -> list[EventLog]:
    snapshot_ts = _parse_iso(snapshot.created_at)
    if snapshot_ts is None:
        return list(events)
    filtered: list[EventLog] = []
    for event in events:
        event_ts = _parse_iso(event.ts)
        if event_ts is None or event_ts >= snapshot_ts:
            filtered.append(event)
    return filtered


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_internal_status(status: ExternalStatus) -> InternalStatus:
    mapping = {
        ExternalStatus.CREATED: InternalStatus.CREATED,
        ExternalStatus.PLANNING: InternalStatus.PLANNING,
        ExternalStatus.WAITING_PLAN_CONFIRM: InternalStatus.WAITING_PLAN_CONFIRM,
        ExternalStatus.PLANNED: InternalStatus.PLANNED,
        ExternalStatus.RUNNING: InternalStatus.RUNNING,
        ExternalStatus.WAITING_PATCH_CONFIRM: InternalStatus.WAITING_PATCH,
        ExternalStatus.WAITING_REPLAN_CONFIRM: InternalStatus.WAITING_REPLAN,
        ExternalStatus.SUMMARIZING: InternalStatus.SUMMARIZING,
        ExternalStatus.DONE: InternalStatus.DONE,
        ExternalStatus.FAILED: InternalStatus.FAILED,
        ExternalStatus.CANCELLED: InternalStatus.CANCELLED,
    }
    return mapping.get(status, InternalStatus.CREATED)


def _should_resume_after_recovery(context: WorkflowContext) -> bool:
    if context.status != InternalStatus.RUNNING:
        return False
    return bool(context.step_results)
