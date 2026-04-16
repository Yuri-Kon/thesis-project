from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.models.contracts import (
    Plan,
    PlanStep,
    ProteinDesignTask,
    RiskFlag,
    RuntimeFailureContext,
    RuntimeStateUpdateInput,
    SafetyResult,
    StepResult,
    now_iso,
)
from src.workflow.belief_state import extract_failure_context, update_runtime_state
from src.workflow.context import WorkflowContext


def _build_failed_step_result() -> StepResult:
    return StepResult(
        task_id="task_belief",
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


def test_extract_failure_context_returns_stable_schema() -> None:
    failure_context = extract_failure_context(_build_failed_step_result())

    assert failure_context == RuntimeFailureContext(
        failure_type="retryable",
        failure_code="NIM_TIMEOUT",
        retry_exhausted=True,
        recovery_action="patch_local",
        patch={
            "applied": True,
            "layer": "tool_swap",
            "reason": "remote_timeout",
        },
    )
    assert failure_context.to_replay_payload()["recovery_action"] == "patch_local"


def test_runtime_state_update_input_rejects_invalid_progress_bounds() -> None:
    with pytest.raises(ValidationError):
        RuntimeStateUpdateInput(completed_steps=3, total_steps=2)


def test_runtime_state_update_input_emits_replay_payload() -> None:
    step_result = _build_failed_step_result()
    failure_context = extract_failure_context(step_result)
    update_input = RuntimeStateUpdateInput.from_step_result(
        step_result=step_result,
        failure_context=failure_context,
        completed_steps=1,
        total_steps=4,
    )

    payload = update_input.to_replay_payload()

    assert payload["step_result"]["step_id"] == "S2"
    assert payload["failure_context"]["failure_code"] == "NIM_TIMEOUT"
    assert payload["completed_steps"] == 1
    assert payload["total_steps"] == 4
    json.dumps(payload, ensure_ascii=True)


def test_update_runtime_state_accepts_structured_update_input() -> None:
    step_result = _build_failed_step_result()
    update_input = RuntimeStateUpdateInput.from_step_result(
        step_result=step_result,
        failure_context=extract_failure_context(step_result),
        completed_steps=1,
        total_steps=4,
    )

    state = update_runtime_state(
        previous_state=None,
        update_input=update_input,
    )

    assert state.p_success == 0.2
    assert state.p_structural_failure == 0.47
    assert state.recovery_margin == 0.31
    assert state.expected_remaining_cost == 5.0
    assert state.evidence_sufficiency == 0.5015


def test_workflow_context_apply_runtime_state_update_is_runner_entrypoint() -> None:
    task = ProteinDesignTask(task_id="task_belief", goal="demo")
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="protein_mpnn", inputs={}, metadata={}),
            PlanStep(id="S2", tool="esmfold", inputs={}, metadata={}),
        ],
        constraints={},
        metadata={},
    )
    context = WorkflowContext(task=task, plan=plan)

    context.apply_runtime_state_update(
        safety_result=SafetyResult(
            task_id=task.task_id,
            phase="step",
            scope="step:S2",
            risk_flags=[
                RiskFlag(
                    level="warn",
                    code="LOW_CONFIDENCE",
                    message="confidence trending down",
                    scope="step",
                    step_id="S2",
                    details={},
                )
            ],
            action="warn",
            timestamp=now_iso(),
        )
    )

    assert context.runtime_state is not None
    assert context.runtime_state.last_update_source == "safety_result:step:S2"
    assert context.runtime_state.observation_summary["completed_steps"] == 0
    assert context.runtime_state.observation_summary["remaining_steps"] == 2
