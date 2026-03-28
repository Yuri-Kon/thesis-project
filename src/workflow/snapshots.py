from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import uuid4

from src.models.contracts import (
    RUNTIME_OBSERVATION_SUMMARY_ARTIFACT_KEY,
    RUNTIME_STATE_ARTIFACT_KEY,
    RuntimeState,
    TaskSnapshot,
    now_iso,
)
from src.models.db import ExternalStatus, to_external_status
from src.storage.snapshot_store import append_snapshot
from src.workflow.belief_state import update_runtime_state
from src.workflow.context import WorkflowContext

SnapshotWriter = Callable[[TaskSnapshot], None]

_WAITING_EXTERNAL_STATUSES = {
    ExternalStatus.WAITING_PLAN_CONFIRM,
    ExternalStatus.WAITING_PATCH_CONFIRM,
    ExternalStatus.WAITING_REPLAN_CONFIRM,
}


def default_snapshot_writer(snapshot: TaskSnapshot) -> None:
    append_snapshot(snapshot)


def build_task_snapshot(
    context: WorkflowContext,
    *,
    state_override: Optional[ExternalStatus] = None,
    pending_action_id: Optional[str] = None,
    artifacts: Optional[dict] = None,
    require_runtime_state: bool = False,
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
        require_runtime_state: 是否在写 snapshot 前确保最小 runtime_state 已落盘

    Returns:
        准备好持久化的 TaskSnapshot 实例
    """
    external_state = state_override or to_external_status(context.status)
    step_ids = list(context.step_results.keys())
    artifacts_payload = dict(artifacts or {})
    runtime_state = _resolve_runtime_state_for_snapshot(
        context,
        external_state=external_state,
        require_runtime_state=require_runtime_state,
    )
    _inject_runtime_state_artifacts(runtime_state, artifacts_payload)
    if context.pending_action is not None:
        artifacts_payload.setdefault(
            "pending_action", context.pending_action.model_dump()
        )
    return TaskSnapshot(
        snapshot_id=f"snapshot_{uuid4().hex[:8]}",
        task_id=context.task.task_id,
        state=external_state.value,
        plan_version=_extract_plan_version(context),
        step_index=len(step_ids),
        current_step_index=len(step_ids),
        completed_step_ids=step_ids,
        artifacts=artifacts_payload,
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


def _inject_runtime_state_artifacts(
    runtime_state: RuntimeState | None,
    artifacts_payload: dict[str, Any],
) -> None:
    if runtime_state is None:
        return

    artifacts_payload.setdefault(
        RUNTIME_STATE_ARTIFACT_KEY,
        runtime_state.to_snapshot_payload(),
    )

    if runtime_state.observation_summary:
        artifacts_payload.setdefault(
            RUNTIME_OBSERVATION_SUMMARY_ARTIFACT_KEY,
            dict(runtime_state.observation_summary),
        )


def _resolve_runtime_state_for_snapshot(
    context: WorkflowContext,
    *,
    external_state: ExternalStatus,
    require_runtime_state: bool,
) -> RuntimeState | None:
    if context.runtime_state is not None:
        return context.runtime_state
    if not (
        require_runtime_state
        or external_state in _WAITING_EXTERNAL_STATUSES
    ):
        return None

    context.runtime_state = update_runtime_state(
        previous_state=None,
        completed_steps=len(context.step_results),
        total_steps=_extract_total_step_count(context),
    )
    return context.runtime_state


def _extract_total_step_count(context: WorkflowContext) -> int | None:
    plan = context.plan
    if plan is None:
        return None
    return len(plan.steps)
