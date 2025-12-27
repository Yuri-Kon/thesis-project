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
) -> TaskSnapshot:
    """Build a minimal TaskSnapshot for recovery."""
    external_state = state_override or to_external_status(context.status)
    step_ids = list(context.step_results.keys())
    return TaskSnapshot(
        snapshot_id=f"snapshot_{uuid4().hex[:8]}",
        task_id=context.task.task_id,
        state=external_state.value,
        plan_version=_extract_plan_version(context),
        current_step_index=len(step_ids),
        completed_step_ids=step_ids,
        artifacts={},
        pending_action_id=pending_action_id,
        created_at=now_iso(),
    )


def _extract_plan_version(context: WorkflowContext) -> Optional[str]:
    plan = context.plan
    if plan is None:
        return None
    if isinstance(plan.metadata, dict):
        value = plan.metadata.get("plan_version")
        if value is None:
            return None
        return str(value)
    return None
