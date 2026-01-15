from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infra.event_log_factory import make_waiting_exit
from src.models.contracts import (
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanStep,
    ProteinDesignTask,
    TaskSnapshot,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus
from src.storage.log_store import write_event_log
from src.workflow.pending_action import build_pending_action
from src.workflow.recovery import (
    recover_context_with_event_logs,
    restore_context_from_snapshot,
)


@pytest.mark.unit
def test_restore_context_from_snapshot_restores_completed_steps():
    task = ProteinDesignTask(
        task_id="task_recovery_steps",
        goal="recover steps",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDE"}, metadata={}),
            PlanStep(id="S2", tool="dummy_tool", inputs={"sequence": "S1.sequence"}, metadata={}),
        ],
    )
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_steps_001",
        task_id=task.task_id,
        state=ExternalStatus.RUNNING.value,
        plan_version=0,
        step_index=1,
        completed_step_ids=["S1"],
        artifacts={},
        created_at=now_iso(),
    )

    context = restore_context_from_snapshot(task=task, plan=plan, snapshot=snapshot)

    assert context is not None
    assert "S1" in context.step_results
    assert context.step_results["S1"].tool == "esmfold"
    assert context.step_results["S1"].status == "success"


@pytest.mark.unit
def test_recover_context_with_event_logs_updates_status_and_clears_pending_action():
    task = ProteinDesignTask(
        task_id="task_recovery_eventlog",
        goal="recovery eventlog",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDE"}, metadata={}),
        ],
    )
    candidate = PendingActionCandidate(
        candidate_id="plan_candidate_1",
        payload=plan,
        summary="plan candidate",
    )
    pending_action = build_pending_action(
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[candidate],
        explanation="waiting for plan confirm",
    )
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_waiting_001",
        task_id=task.task_id,
        state=ExternalStatus.WAITING_PLAN_CONFIRM.value,
        plan_version=0,
        step_index=0,
        completed_step_ids=[],
        artifacts={"pending_action": pending_action.model_dump()},
        pending_action_id=pending_action.pending_action_id,
        created_at="2026-01-01T00:00:00+00:00",
    )

    exit_event = make_waiting_exit(
        task_id=task.task_id,
        prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
        new_status=ExternalStatus.PLANNED,
        waiting_state=InternalStatus.WAITING_PLAN_CONFIRM.value,
        pending_action_id=pending_action.pending_action_id,
    )
    exit_event.ts = "2026-01-01T00:00:01+00:00"

    with TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        write_event_log(exit_event, log_dir=log_dir)
        result = recover_context_with_event_logs(
            task=task,
            plan=plan,
            snapshot=snapshot,
            log_dir=log_dir,
        )

    assert result is not None
    assert result.context.status == InternalStatus.PLANNED
    assert result.context.pending_action is None


@pytest.mark.unit
def test_recover_context_with_event_logs_is_idempotent():
    task = ProteinDesignTask(
        task_id="task_recovery_idempotent",
        goal="recovery idempotent",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDE"}, metadata={}),
        ],
    )
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_running_001",
        task_id=task.task_id,
        state=ExternalStatus.RUNNING.value,
        plan_version=0,
        step_index=0,
        completed_step_ids=[],
        artifacts={},
        created_at="2026-01-01T00:00:00+00:00",
    )

    with TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        first = recover_context_with_event_logs(
            task=task,
            plan=plan,
            snapshot=snapshot,
            log_dir=log_dir,
        )
        second = recover_context_with_event_logs(
            task=task,
            plan=plan,
            snapshot=snapshot,
            log_dir=log_dir,
        )

    assert first is not None
    assert second is not None
    assert first.context.status == second.context.status
    assert first.resume_from_existing == second.resume_from_existing


@pytest.mark.unit
def test_recover_context_missing_outputs_disables_resume():
    task = ProteinDesignTask(
        task_id="task_recovery_missing_outputs",
        goal="recovery missing outputs",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDE"}, metadata={}),
            PlanStep(
                id="S2",
                tool="dummy_tool",
                inputs={"sequence": "S1.sequence"},
                metadata={},
            ),
        ],
    )
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_running_missing_outputs",
        task_id=task.task_id,
        state=ExternalStatus.RUNNING.value,
        plan_version=0,
        step_index=1,
        completed_step_ids=["S1"],
        artifacts={},
        created_at=now_iso(),
    )

    with TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        result = recover_context_with_event_logs(
            task=task,
            plan=plan,
            snapshot=snapshot,
            log_dir=log_dir,
        )

    assert result is not None
    assert result.context.status == InternalStatus.RUNNING
    assert result.resume_from_existing is False
    assert result.context.step_results["S1"].metrics.get("outputs_missing") is True


@pytest.mark.unit
def test_recover_context_waiting_disables_resume():
    task = ProteinDesignTask(
        task_id="task_recovery_waiting",
        goal="recovery waiting",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDE"}, metadata={}),
        ],
    )
    pending_action = build_pending_action(
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="candidate_waiting",
                payload=plan,
                summary="waiting candidate",
            )
        ],
        explanation="waiting",
    )
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_waiting_002",
        task_id=task.task_id,
        state=ExternalStatus.WAITING_PLAN_CONFIRM.value,
        plan_version=0,
        step_index=1,
        completed_step_ids=["S1"],
        artifacts={"pending_action": pending_action.model_dump()},
        pending_action_id=pending_action.pending_action_id,
        created_at=now_iso(),
    )

    with TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        result = recover_context_with_event_logs(
            task=task,
            plan=plan,
            snapshot=snapshot,
            log_dir=log_dir,
        )

    assert result is not None
    assert result.context.status == InternalStatus.WAITING_PLAN_CONFIRM
    assert result.resume_from_existing is False
