import pytest

from src.models.contracts import (
    Decision,
    DecisionChoice,
    PendingAction,
    PendingActionCandidate,
    PendingActionType,
    now_iso,
)
from src.models.validation import (
    DecisionValidationError,
    validate_decision_for_pending_action,
)


@pytest.mark.unit
def test_accept_with_unknown_candidate_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_unknown",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
        explanation="test",
    )
    decision = Decision(
        decision_id="dec_unknown",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="plan_x",
        decided_by="user_1",
    )

    with pytest.raises(DecisionValidationError):
        validate_decision_for_pending_action(pending_action, decision)


@pytest.mark.unit
def test_accept_without_selected_candidate_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_missing",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
        explanation="test",
    )
    decision = Decision.model_construct(
        decision_id="dec_missing",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id=None,
        decided_by="user_1",
        decided_at=now_iso(),
    )

    with pytest.raises(DecisionValidationError):
        validate_decision_for_pending_action(pending_action, decision)


@pytest.mark.unit
def test_invalid_choice_for_action_type_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_invalid_choice",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
        explanation="test",
    )
    decision = Decision(
        decision_id="dec_invalid_choice",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.CONTINUE,
        decided_by="user_1",
    )

    with pytest.raises(DecisionValidationError):
        validate_decision_for_pending_action(pending_action, decision)


@pytest.mark.unit
def test_valid_accept_passes(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_valid",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        ],
        explanation="test",
    )
    decision = Decision(
        decision_id="dec_valid",
        task_id=sample_task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="plan_a",
        decided_by="user_1",
    )

    validate_decision_for_pending_action(pending_action, decision)
