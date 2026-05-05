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


def test_update_runtime_state_derives_budget_pressure_from_budget_cap() -> None:
    step_result = _build_failed_step_result()
    update_input = RuntimeStateUpdateInput.from_step_result(
        step_result=step_result,
        failure_context=extract_failure_context(step_result),
        completed_steps=1,
        total_steps=4,
        budget_cap=10.0,
    )

    state = update_runtime_state(
        previous_state=None,
        update_input=update_input,
    )

    assert state.expected_remaining_cost == pytest.approx(5.0)
    assert state.budget_cap == pytest.approx(10.0)
    assert state.budget_pressure == pytest.approx(0.5)
    assert state.observation_summary["budget_pressure"] == pytest.approx(0.5)


def test_runtime_state_consumes_objective_signal_without_overriding_safety_block() -> None:
    """objective gap/progress 可进入观测摘要，但安全阻断仍会降低成功概率。"""

    step_result = StepResult(
        task_id="task_belief",
        step_id="S3",
        tool="objective_ranker",
        status="success",
        failure_type=None,
        error_message=None,
        inputs={},
        outputs={
            "capability_id": "objective_scoring",
            "objective_score": 0.9,
            "default_recommendation": "cand_a",
        },
        artifacts={},
        metrics={
            "objective_progress": 0.9,
            "objective_gap": 0.2,
            "top_candidate_id": "cand_a",
            "warning_count": 1,
        },
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    safety_block = SafetyResult(
        task_id="task_belief",
        phase="step",
        scope="step:S3",
        risk_flags=[
            RiskFlag(
                level="block",
                code="SCHEMA_VIOLATION",
                message="schema violation",
                scope="step",
                step_id="S3",
                details={},
            )
        ],
        action="block",
        timestamp=now_iso(),
    )

    objective_only = update_runtime_state(
        previous_state=None,
        step_result=step_result,
    )
    blocked = update_runtime_state(
        previous_state=None,
        step_result=step_result,
        safety_result=safety_block,
    )

    assert blocked.observation_summary["objective_progress"] == 0.9
    assert blocked.observation_summary["objective_gap"] == 0.2
    assert blocked.observation_summary["objective_top_candidate_id"] == "cand_a"
    assert blocked.p_success < objective_only.p_success
    assert blocked.observation_summary["last_safety_action"] == "block"


def test_runtime_state_consumes_structure_similarity_signal() -> None:
    """structure similarity hit 摘要应进入 runtime evidence observation。"""

    step_result = StepResult(
        task_id="task_belief",
        step_id="S4",
        tool="foldseek",
        status="success",
        failure_type=None,
        error_message=None,
        inputs={},
        outputs={
            "capability_id": "structure_similarity_search",
            "hit_count": 1,
            "top_hit": {"hit_id": "1abc_A", "tm_score": 0.82, "coverage": 0.91},
            "structure_similarity_hits": [
                {"hit_id": "1abc_A", "tm_score": 0.82, "coverage": 0.91}
            ],
        },
        artifacts={},
        metrics={"hit_count": 1},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )

    state = update_runtime_state(previous_state=None, step_result=step_result)

    assert state.observation_summary["structure_similarity_hit_count"] == 1
    assert state.observation_summary["structure_similarity_top_tm_score"] == 0.82
    assert state.observation_summary["structure_similarity_top_coverage"] == 0.91
    assert state.evidence_sufficiency > 0.5


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
