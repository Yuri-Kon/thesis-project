import pytest
from pydantic import ValidationError

from src.models.contracts import (
    Decision,
    DecisionChoice,
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    PendingActionType,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    now_iso,
)
from src.models.db import InternalStatus, TaskRecord, to_external_status
from src.workflow.context import WorkflowContext
from src.workflow.decision_apply import (
    DecisionApplyError,
    DecisionConflictError,
    apply_patch_confirm_decision,
    apply_plan_confirm_decision,
    apply_replan_confirm_decision,
)


def _make_record(task_id: str, status: InternalStatus) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        status=to_external_status(status),
        internal_status=status,
        created_at=now_iso(),
        updated_at=now_iso(),
        goal="test",
        constraints={},
        metadata={},
        plan=None,
        design_result=None,
        safety_events=[],
        pending_action=None,
    )


def _make_patch(plan_step_id: str) -> PlanPatch:
    patched_step = PlanStep(
        id=plan_step_id,
        tool="patched_tool",
        inputs={"note": "patched"},
        metadata={},
    )
    op = PlanPatchOp(op="replace_step", target=plan_step_id, step=patched_step)
    return PlanPatch(task_id="test_task_001", operations=[op], metadata={})


def _capture_events():
    events: list[dict] = []
    return events, events.append


def _capture_snapshots():
    snapshots: list[object] = []
    return snapshots, snapshots.append


@pytest.mark.unit
def test_plan_confirm_accept_transitions_to_planned(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_plan_1",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
    )
    decision = Decision(
        decision_id="dec_1",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="plan_a",
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        plan=None,
        status=InternalStatus.WAITING_PLAN_CONFIRM,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_PLAN_CONFIRM)
    record.pending_action = pending_action

    events, event_logger = _capture_events()
    snapshots, snapshot_writer = _capture_snapshots()

    result = apply_plan_confirm_decision(
        context,
        record,
        decision,
        event_logger=event_logger,
        snapshot_writer=snapshot_writer,
    )

    assert context.status == InternalStatus.PLANNED
    assert record.status.value == "PLANNED"
    assert result.plan == sample_plan
    assert pending_action.status == PendingActionStatus.DECIDED
    assert events[0]["event"] == "DECISION_SUBMITTED"
    assert events[-1]["event"] == "DECISION_APPLIED"
    assert snapshots, "snapshot should be written after decision applied"


@pytest.mark.unit
def test_plan_confirm_replan_transitions_to_planning(sample_task):
    pending_action = PendingAction(
        pending_action_id="pa_plan_2",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[],
    )
    decision = Decision(
        decision_id="dec_2",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.REPLAN,
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_PLAN_CONFIRM,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_PLAN_CONFIRM)
    record.pending_action = pending_action

    apply_plan_confirm_decision(context, record, decision)

    assert context.status == InternalStatus.PLANNING
    assert pending_action.status == PendingActionStatus.DECIDED


@pytest.mark.unit
def test_patch_confirm_accept_transitions_to_running(sample_task, sample_plan):
    plan_patch = _make_patch(plan_step_id=sample_plan.steps[0].id)
    pending_action = PendingAction(
        pending_action_id="pa_patch_1",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PATCH_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="patch_a", payload=plan_patch)
        ],
    )
    decision = Decision(
        decision_id="dec_3",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="patch_a",
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        plan=sample_plan,
        status=InternalStatus.WAITING_PATCH,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_PATCH)
    record.plan = sample_plan
    record.pending_action = pending_action

    apply_patch_confirm_decision(context, record, decision)

    assert context.status == InternalStatus.RUNNING
    assert context.plan.steps[0].tool == "patched_tool"
    assert pending_action.status == PendingActionStatus.DECIDED


@pytest.mark.unit
def test_patch_confirm_replan_transitions_to_waiting_replan(sample_task):
    pending_action = PendingAction(
        pending_action_id="pa_patch_2",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PATCH_CONFIRM,
        candidates=[],
    )
    decision = Decision(
        decision_id="dec_4",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.REPLAN,
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_PATCH,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_PATCH)
    record.pending_action = pending_action

    result = apply_patch_confirm_decision(context, record, decision)

    assert context.status == InternalStatus.WAITING_REPLAN
    assert pending_action.status == PendingActionStatus.CANCELLED
    assert result.pending_action is not None
    assert result.pending_action.action_type == PendingActionType.REPLAN_CONFIRM
    assert result.pending_action.status == PendingActionStatus.PENDING


@pytest.mark.unit
def test_replan_confirm_continue_transitions_to_running(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_replan_1",
        task_id=sample_task.task_id,
        action_type=PendingActionType.REPLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="replan_a", payload=sample_plan)
        ],
    )
    decision = Decision(
        decision_id="dec_4",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.CONTINUE,
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_REPLAN,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_REPLAN)
    record.pending_action = pending_action

    apply_replan_confirm_decision(context, record, decision)

    assert context.status == InternalStatus.RUNNING
    assert pending_action.status == PendingActionStatus.DECIDED


@pytest.mark.unit
def test_replan_confirm_accept_transitions_to_planning(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_replan_2",
        task_id=sample_task.task_id,
        action_type=PendingActionType.REPLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="replan_a", payload=sample_plan)
        ],
    )
    decision = Decision(
        decision_id="dec_5",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="replan_a",
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_REPLAN,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_REPLAN)
    record.pending_action = pending_action

    result = apply_replan_confirm_decision(context, record, decision)

    assert context.status == InternalStatus.PLANNING
    assert result.plan == sample_plan
    assert pending_action.status == PendingActionStatus.DECIDED


@pytest.mark.unit
@pytest.mark.parametrize(
    "internal_status,action_type,apply_func",
    [
        (
            InternalStatus.WAITING_PLAN_CONFIRM,
            PendingActionType.PLAN_CONFIRM,
            apply_plan_confirm_decision,
        ),
        (
            InternalStatus.WAITING_PATCH,
            PendingActionType.PATCH_CONFIRM,
            apply_patch_confirm_decision,
        ),
        (
            InternalStatus.WAITING_REPLAN,
            PendingActionType.REPLAN_CONFIRM,
            apply_replan_confirm_decision,
        ),
    ],
)
def test_cancel_transitions_to_cancelled(
    sample_task,
    internal_status,
    action_type,
    apply_func,
):
    pending_action = PendingAction(
        pending_action_id=f"pa_cancel_{action_type.value}",
        task_id=sample_task.task_id,
        action_type=action_type,
        candidates=[],
    )
    decision = Decision(
        decision_id=f"dec_cancel_{action_type.value}",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.CANCEL,
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=internal_status,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, internal_status)
    record.pending_action = pending_action

    apply_func(context, record, decision)

    assert context.status == InternalStatus.CANCELLED
    assert pending_action.status == PendingActionStatus.CANCELLED


@pytest.mark.unit
def test_invalid_choice_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_invalid_1",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
    )
    decision = Decision(
        decision_id="dec_invalid_1",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.CONTINUE,
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_PLAN_CONFIRM,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_PLAN_CONFIRM)
    record.pending_action = pending_action

    with pytest.raises(DecisionApplyError):
        apply_plan_confirm_decision(context, record, decision)


@pytest.mark.unit
def test_missing_selected_candidate_rejected(sample_task):
    with pytest.raises(ValidationError):
        Decision(
            decision_id="dec_missing",
            task_id=sample_task.task_id,
            pending_action_id="pa_missing",
            choice=DecisionChoice.ACCEPT,
            decided_by="user_1",
        )


@pytest.mark.unit
def test_repeated_decision_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_repeat",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
        status=PendingActionStatus.DECIDED,
    )
    decision = Decision(
        decision_id="dec_repeat",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="plan_a",
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_PLAN_CONFIRM,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_PLAN_CONFIRM)
    record.pending_action = pending_action

    with pytest.raises(DecisionConflictError):
        apply_plan_confirm_decision(context, record, decision)


@pytest.mark.unit
def test_status_mismatch_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_mismatch",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
    )
    decision = Decision(
        decision_id="dec_mismatch",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="plan_a",
        decided_by="user_1",
    )
    context = WorkflowContext(
        task=sample_task,
        status=InternalStatus.WAITING_REPLAN,
        pending_action=pending_action,
    )
    record = _make_record(sample_task.task_id, InternalStatus.WAITING_REPLAN)
    record.pending_action = pending_action

    with pytest.raises(DecisionConflictError):
        apply_plan_confirm_decision(context, record, decision)
