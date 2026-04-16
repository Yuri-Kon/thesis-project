import pytest

from src.models.db import InternalStatus
from src.workflow.errors import FailureType
from src.workflow.recovery import (
    WorkflowActionSelectorInput,
    resolve_workflow_action_route,
    select_workflow_action,
)


@pytest.mark.unit
def test_selector_safety_block_overrides_continue_suggestion():
    decision = select_workflow_action(
        WorkflowActionSelectorInput(
            phase="execution",
            stage_id="S3",
            failure_code="SAFETY_POST_BLOCK",
            failure_type=FailureType.SAFETY_BLOCK,
            safety_blocked=True,
            suggested_action="continue",
            runtime_state_summary={
                "p_success": 0.61,
                "p_structural_failure": 0.42,
                "recovery_margin": 0.18,
                "expected_remaining_cost": 1.7,
            },
        )
    )

    assert decision.action == "suffix_replan"
    assert decision.mapped_flow == "replan"
    assert decision.evidence_source["basis"] == "hard_priority"


@pytest.mark.unit
def test_selector_stop_route_maps_to_waiting_replan_and_failed_terminal():
    decision = select_workflow_action(
        WorkflowActionSelectorInput(
            phase="execution",
            stage_id="S2",
            failure_code="S2_TIMEOUT",
            failure_type=FailureType.RETRYABLE,
            retry_exhausted=True,
            runtime_state_summary={
                "p_success": 0.12,
                "p_structural_failure": 0.63,
                "recovery_margin": 0.08,
                "expected_remaining_cost": 4.7,
                "budget_pressure": 0.91,
                "intervention_value": 0.22,
            },
        )
    )
    route = resolve_workflow_action_route(decision.action)

    assert decision.action == "stop"
    assert decision.mapped_flow == "stop"
    assert route.waiting_status == InternalStatus.WAITING_REPLAN
    assert route.terminal_status == InternalStatus.FAILED
    assert route.terminal_policy == "stop"


@pytest.mark.unit
def test_selector_derives_runtime_features_from_core_belief_state_only():
    decision = select_workflow_action(
        WorkflowActionSelectorInput(
            phase="execution",
            stage_id="S3",
            failure_code="S3_ALL_CANDIDATES_REJECTED",
            failure_type=FailureType.NON_RETRYABLE,
            retry_exhausted=True,
            runtime_state_summary={
                "p_success": 0.18,
                "p_structural_failure": 0.62,
                "recovery_margin": 0.12,
                "expected_remaining_cost": 1.1,
                "evidence_sufficiency": 0.66,
            },
        )
    )

    assert decision.action == "suffix_replan"
    assert decision.evidence_source["budget_pressure"] == pytest.approx(1.1)
    assert decision.evidence_source["evidence_sufficiency"] == pytest.approx(0.66)
    assert decision.evidence_source["local_patchability"] == pytest.approx(0.459, rel=1e-3)
    assert decision.evidence_source["prefix_preservability"] == pytest.approx(0.258, rel=1e-3)
    assert decision.evidence_source["intervention_value"] == pytest.approx(0.4991375, rel=1e-3)
