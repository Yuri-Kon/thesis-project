import pytest

from src.models.db import InternalStatus
from src.models.runtime_schemas import ActionUtility
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
    assert decision.evidence_source["selection_basis"] == "hard_priority"
    assert decision.evidence_source["hard_priority_applied"] is True
    assert decision.evidence_source["hard_priority_reason"]
    assert decision.evidence_source["selected_action"] == "suffix_replan"
    assert decision.evidence_source["selected_action_mapped_flow"] == "replan"


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
    assert decision.evidence_source["local_patchability"] == pytest.approx(0.369, rel=1e-3)
    assert decision.evidence_source["prefix_preservability"] == pytest.approx(0.258, rel=1e-3)
    assert decision.evidence_source["intervention_value"] == pytest.approx(0.4867625, rel=1e-3)
    derived = decision.evidence_source["derived_features"]
    assert derived["local_patchability"]["source"] == "inferred"
    assert derived["intervention_value"]["source"] == "inferred"
    assert "sid:algo.action_feature_derivation" in decision.evidence_source[
        "action_feature_source_refs"
    ]


@pytest.mark.unit
def test_selector_uses_input_action_utilities_as_evidence_source():
    utilities = {
        "continue": ActionUtility(action="continue", utility=0.91),
        "patch_local": ActionUtility(action="patch_local", utility=0.12),
    }

    decision = select_workflow_action(
        WorkflowActionSelectorInput(
            phase="execution",
            runtime_state_summary={"p_success": 0.74},
            action_utilities=utilities,
        )
    )

    evidence = decision.evidence_source
    assert evidence["action_utility_source"] == "input"
    assert evidence["action_utilities"]["continue"]["utility"] == pytest.approx(0.91)
    assert evidence["action_utilities"]["patch_local"]["utility"] == pytest.approx(0.12)
    assert "sid:algo.recovery_aware_action_selection" in evidence["source_refs"]
    assert "impl:recovery.select_workflow_action.v1" in evidence["source_refs"]


@pytest.mark.unit
def test_selector_computes_action_utilities_when_runtime_summary_is_available():
    decision = select_workflow_action(
        WorkflowActionSelectorInput(
            phase="execution",
            runtime_state_summary={
                "p_success": 0.44,
                "p_structural_failure": 0.24,
                "recovery_margin": 0.63,
                "expected_remaining_cost": 0.38,
            },
        )
    )

    evidence = decision.evidence_source
    assert evidence["action_utility_source"] == "computed"
    assert set(evidence["action_utilities"]) == {
        "continue",
        "patch_local",
        "suffix_replan",
        "stop",
    }


@pytest.mark.unit
def test_selector_marks_action_utilities_missing_without_runtime_summary():
    decision = select_workflow_action(WorkflowActionSelectorInput(phase="execution"))

    assert decision.evidence_source["action_utility_source"] == "missing"
    assert decision.evidence_source["action_utilities"] == {}
