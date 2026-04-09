from __future__ import annotations

from src.models.contracts import (
    Plan,
    ProteinDesignTask,
    RiskFlag,
    SafetyResult,
    StepResult,
    now_iso,
)
from src.workflow.belief_state import extract_failure_context, update_runtime_state
from src.workflow.context import WorkflowContext
from src.workflow.plan_runner import _build_step_trace_data


def test_build_step_trace_data_contains_quality_gate_summary() -> None:
    step_result = StepResult(
        task_id="task_trace",
        step_id="S3",
        tool="biopython_qc",
        status="failed",
        failure_type="non_retryable",
        error_message="all rejected",
        error_details={"failure_code": "S3_ALL_CANDIDATES_REJECTED"},
        inputs={},
        outputs={
            "stage_id": "S3",
            "pass_count": 0,
            "fail_count": 2,
            "pass_fail": False,
            "reject_code_counts": {"S3_PLDDT_BELOW_THRESHOLD": 2},
            "failed_samples": [
                {
                    "candidate_id": "cand_1",
                    "reject_codes": ["S3_PLDDT_BELOW_THRESHOLD"],
                    "reason": "plddt too low",
                }
            ],
        },
        artifacts={},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )

    data = _build_step_trace_data(step_result)
    assert data["failure_code"] == "S3_ALL_CANDIDATES_REJECTED"
    assert data["stage_id"] == "S3"
    assert data["quality_gate"]["fail_count"] == 2
    assert data["quality_gate"]["failed_samples"][0]["candidate_id"] == "cand_1"


def test_update_runtime_state_with_success_step_is_deterministic() -> None:
    step_result = StepResult(
        task_id="task_trace",
        step_id="S2",
        tool="esmfold",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        inputs={},
        outputs={"stage_id": "S2", "pdb_path": "mock.pdb"},
        artifacts={},
        metrics={"duration_ms": 1200},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )

    state = update_runtime_state(
        previous_state=None,
        step_result=step_result,
        failure_context=extract_failure_context(step_result),
        completed_steps=1,
        total_steps=4,
    )

    assert state.last_update_source == "step_result:S2"
    assert state.p_success == 0.66
    assert state.p_structural_failure == 0.12
    assert state.recovery_margin == 0.66
    assert state.expected_remaining_cost == 3.0
    assert state.evidence_sufficiency == 0.5687
    assert state.observation_summary["completed_steps"] == 1
    assert state.observation_summary["remaining_steps"] == 3


def test_update_runtime_state_captures_patch_failure_context() -> None:
    failed_result = StepResult(
        task_id="task_trace",
        step_id="S2",
        tool="esmfold",
        status="failed",
        failure_type="retryable",
        error_message="remote endpoint timeout",
        error_details={"failure_code": "NIM_TIMEOUT"},
        inputs={},
        outputs={"stage_id": "S2"},
        artifacts={},
        metrics={
            "retry_exhausted": True,
            "patch": {
                "applied": True,
                "layer": "tool_swap",
                "reason": "remote_timeout",
            },
        },
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )

    state = update_runtime_state(
        previous_state=None,
        step_result=failed_result,
        failure_context=extract_failure_context(failed_result),
        completed_steps=1,
        total_steps=4,
    )

    assert state.p_success == 0.2
    assert state.p_structural_failure == 0.47
    assert state.recovery_margin == 0.31
    assert state.expected_remaining_cost == 5.0
    assert state.evidence_sufficiency == 0.5015
    assert state.observation_summary["last_failure_code"] == "NIM_TIMEOUT"
    assert state.observation_summary["last_recovery_action"] == "patch_local"


def test_update_runtime_state_handles_safety_block_and_suffix_replan() -> None:
    previous_state = update_runtime_state(
        previous_state=None,
        completed_steps=1,
        total_steps=4,
    )
    safety_result = SafetyResult(
        task_id="task_trace",
        phase="step",
        scope="step:S3",
        risk_flags=[
            RiskFlag(
                level="block",
                code="S3_ALL_CANDIDATES_REJECTED",
                message="all candidates rejected",
                scope="step",
                step_id="S3",
                details={},
            )
        ],
        action="block",
        timestamp=now_iso(),
    )

    state = update_runtime_state(
        previous_state=previous_state,
        safety_result=safety_result,
        failure_context={"recovery_action": "suffix_replan"},
        completed_steps=1,
        total_steps=4,
    )

    assert state.last_update_source == "safety_result:step:S3"
    assert state.p_success == 0.2
    assert state.p_structural_failure == 0.46
    assert state.recovery_margin == 0.32
    assert state.expected_remaining_cost == 4.95
    assert state.evidence_sufficiency == 0.4499
    assert state.observation_summary["last_safety_action"] == "block"
    assert state.observation_summary["last_recovery_action"] == "suffix_replan"


def test_workflow_context_helpers_refresh_runtime_state() -> None:
    task = ProteinDesignTask(task_id="task_trace", goal="demo")
    plan = Plan(task_id=task.task_id, steps=[], constraints={}, metadata={})
    context = WorkflowContext(task=task, plan=plan)

    context.add_safety_event(
        SafetyResult(
            task_id=task.task_id,
            phase="input",
            scope="task",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )
    )
    context.add_step_result(
        StepResult(
            task_id=task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            inputs={},
            outputs={"stage_id": "S1", "sequence": "AAAA"},
            artifacts={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
    )

    assert context.runtime_state is not None
    assert context.runtime_state.last_update_source == "step_result:S1"
    assert context.runtime_state.observation_summary["completed_steps"] == 1
