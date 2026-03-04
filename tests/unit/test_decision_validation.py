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
    CandidateSetValidationError,
    DecisionValidationError,
    validate_candidate_set_output,
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


@pytest.mark.unit
def test_candidate_set_v1_validation_passes(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_candidate_set_ok",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="plan_a",
                structured_payload=sample_plan,
                score_breakdown={
                    "feasibility": 1.0,
                    "objective": 0.8,
                    "risk": 0.2,
                    "cost": 0.4,
                    "overall": 0.85,
                },
                risk_level="low",
                cost_estimate="medium",
                explanation="candidate a is balanced",
                tool_id="esmfold",
                capability_id="structure_prediction",
                io_type="sequence_to_structure",
                adapter_mode="remote",
            )
        ],
        default_recommendation="plan_a",
        explanation="test",
    )

    validate_candidate_set_output(pending_action)


@pytest.mark.unit
def test_candidate_set_missing_required_score_key_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_candidate_set_missing_score",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="plan_a",
                structured_payload=sample_plan,
                score_breakdown={
                    "feasibility": 1.0,
                    "objective": 0.8,
                    "risk": 0.2,
                    "overall": 0.85,
                },
                risk_level="low",
                cost_estimate="medium",
                explanation="candidate a",
                tool_id="esmfold",
                capability_id="structure_prediction",
                io_type="sequence_to_structure",
                adapter_mode="remote",
            )
        ],
        default_recommendation="plan_a",
        explanation="test",
    )

    with pytest.raises(
        CandidateSetValidationError,
        match="score_breakdown missing keys: cost",
    ):
        validate_candidate_set_output(pending_action)


@pytest.mark.unit
def test_candidate_set_default_recommendation_must_exist(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_candidate_set_bad_default",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="plan_a",
                structured_payload=sample_plan,
                score_breakdown={
                    "feasibility": 1.0,
                    "objective": 0.8,
                    "risk": 0.2,
                    "cost": 0.4,
                    "overall": 0.85,
                },
                risk_level="low",
                cost_estimate="medium",
                explanation="candidate a",
                tool_id="esmfold",
                capability_id="structure_prediction",
                io_type="sequence_to_structure",
                adapter_mode="remote",
            )
        ],
        default_recommendation="plan_x",
        explanation="test",
    )

    with pytest.raises(
        CandidateSetValidationError,
        match="default_recommendation is not in candidates",
    ):
        validate_candidate_set_output(pending_action)


@pytest.mark.unit
def test_candidate_set_missing_tool_fields_rejected(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_candidate_set_missing_tooling",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="plan_a",
                structured_payload=sample_plan,
                score_breakdown={
                    "feasibility": 1.0,
                    "objective": 0.8,
                    "risk": 0.2,
                    "cost": 0.4,
                    "overall": 0.85,
                },
                risk_level="low",
                cost_estimate="medium",
                explanation="candidate a",
            )
        ],
        default_recommendation="plan_a",
        explanation="test",
    )

    with pytest.raises(
        CandidateSetValidationError,
        match="plan_a\\.tool_id is required",
    ):
        validate_candidate_set_output(pending_action)


@pytest.mark.unit
def test_candidate_set_tooling_defaults_adapter_mode_to_unknown(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_candidate_set_tooling_default_mode",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="plan_a",
                structured_payload=sample_plan,
                score_breakdown={
                    "feasibility": 1.0,
                    "objective": 0.8,
                    "risk": 0.2,
                    "cost": 0.4,
                    "overall": 0.85,
                },
                risk_level="low",
                cost_estimate="medium",
                explanation="candidate a",
                tool_id="esmfold",
                capability_id="structure_prediction",
                io_type="sequence_to_structure",
            )
        ],
        default_recommendation="plan_a",
        explanation="test",
    )

    validate_candidate_set_output(pending_action)
    assert pending_action.candidates[0].adapter_mode == "unknown"


@pytest.mark.unit
def test_candidate_set_backward_compat_payload_only_passes(sample_task, sample_plan):
    pending_action = PendingAction(
        pending_action_id="pa_candidate_set_compat",
        task_id=sample_task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="plan_a",
                payload=sample_plan,
            )
        ],
        explanation="test",
        default_suggestion="plan_a",
    )

    validate_candidate_set_output(
        pending_action,
        require_v1_fields=False,
        require_default_recommendation=False,
    )
