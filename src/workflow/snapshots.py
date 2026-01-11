from __future__ import annotations

from typing import Callable, Optional
from uuid import uuid4

from src.models.contracts import TaskSnapshot, now_iso
from src.models.db import ExternalStatus, to_external_status
from src.storage.snapshot_store import append_snapshot
from src.workflow.context import WorkflowContext

SnapshotWriter = Callable[[TaskSnapshot], None]


def default_snapshot_writer(snapshot: TaskSnapshot) -> None:
    append_snapshot(snapshot)


def build_task_snapshot(
    context: WorkflowContext,
    *,
    state_override: Optional[ExternalStatus] = None,
    pending_action_id: Optional[str] = None,
    artifacts: Optional[dict] = None,
) -> TaskSnapshot:
    """构建用于恢复的最小化 TaskSnapshot

    Args:
        context: 包含任务状态的工作流上下文
        state_override: 可选的外部状态覆盖
        pending_action_id: 可选的待处理动作 ID
        artifacts: 可选的产物字典（例如远程作业上下文）
                  支持任意 JSON 可序列化数据，包括：
                  - 远程作业引用（job_id、endpoint、status、trace）
                  - 文件路径和 URI
                  - 其他恢复相关的元数据

    Returns:
        准备好持久化的 TaskSnapshot 实例
    """
    external_state = state_override or to_external_status(context.status)
    step_ids = list(context.step_results.keys())
    return TaskSnapshot(
        snapshot_id=f"snapshot_{uuid4().hex[:8]}",
        task_id=context.task.task_id,
        state=external_state.value,
        plan_version=_extract_plan_version(context),
        step_index=len(step_ids),
        current_step_index=len(step_ids),
        completed_step_ids=step_ids,
        artifacts=artifacts or {},
        pending_action_id=pending_action_id,
        created_at=now_iso(),
    )


def _extract_plan_version(context: WorkflowContext) -> Optional[int]:
    plan = context.plan
    if plan is None:
        return None
    if isinstance(plan.metadata, dict):
        value = plan.metadata.get("plan_version")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None
