from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.planner import CandidateGateDecision, TopKResult
from src.models.contracts import (
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    ProteinDesignTask,
    RuntimeState,
    SafetyResult,
    StepResult,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.storage.log_store import DEFAULT_LOG_DIR, read_timeline_events
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, PlanRunError
from src.workflow.plan_runner import PlanRunner


def _cleanup_task_log(task_id: str) -> None:
    path = Path(DEFAULT_LOG_DIR) / f"{task_id}.jsonl"
    if path.exists():
        path.unlink()


def _build_runtime_objects(
    *,
    task_id: str,
    constraints: dict,
    runtime_state: RuntimeState | None = None,
) -> tuple[Plan, WorkflowContext, TaskRecord]:
    task = ProteinDesignTask(
        task_id=task_id,
        goal="workflow-action-selector-test",
        constraints=constraints,
        metadata={},
    )
    plan = Plan(
        task_id=task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="tool_a",
                inputs={"sequence": "MKTAYIAK"},
                metadata={},
            )
        ],
        constraints=constraints,
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        plan=plan,
        step_results={},
        safety_events=[],
        runtime_state=runtime_state,
        design_result=None,
        status=InternalStatus.RUNNING,
    )
    record = TaskRecord(
        id=task_id,
        status=ExternalStatus.RUNNING,
        internal_status=InternalStatus.RUNNING,
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=plan,
    )
    return plan, context, record


class _SuccessStepRunner:
    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={"stage_id": "S1", "sequence": "MKTAYIAK"},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


class _FailOnceStepRunner:
    def __init__(
        self,
        *,
        stage_id: str,
        failure_code: str,
        failure_type: FailureType = FailureType.RETRYABLE,
    ) -> None:
        self.stage_id = stage_id
        self.failure_code = failure_code
        self.failure_type = failure_type
        self.calls = 0

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        self.calls += 1
        if self.calls > 1:
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="success",
                failure_type=None,
                error_message=None,
                error_details={},
                outputs={"stage_id": self.stage_id, "sequence": "MKTAYIAK"},
                metrics={},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="failed",
            failure_type=self.failure_type,
            error_message="step failed",
            error_details={"failure_code": self.failure_code},
            outputs={"stage_id": self.stage_id},
            metrics={"retry_exhausted": True},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


class _PatchOnlyPlanner:
    def patch_top_k(self, request, *, k=3, runtime_state=None):  # type: ignore[override]
        raise RuntimeError("fallback planner.patch path only")

    def patch(self, request):  # type: ignore[override]
        step = request.original_plan.steps[0]
        return PlanPatch(
            task_id=request.task_id,
            operations=[
                PlanPatchOp(
                    op="replace_step",
                    target=step.id,
                    step=PlanStep(
                        id=step.id,
                        tool="tool_a",
                        inputs=step.inputs,
                        metadata=step.metadata,
                    ),
                )
            ],
            metadata={},
        )

    def evaluate_top_k_gate(
        self,
        *,
        candidate_kind,
        top_k_result,
        task_constraints,
    ):
        requires_hitl = bool(task_constraints.get("require_patch_confirm"))
        return CandidateGateDecision(
            requires_hitl=requires_hitl,
            reason="require_patch_confirm" if requires_hitl else "auto_patch",
            selected_candidate_id=top_k_result.default_recommendation,
            confidence=0.8,
            overall=0.7,
        )

    def replan(self, request):  # pragma: no cover - defensive fallback
        return request.original_plan


class _ObservationOnlyPatchPlanner(_PatchOnlyPlanner):
    def __init__(self) -> None:
        self.last_runtime_state = object()

    def patch_top_k(self, request, *, k=3, runtime_state=None):  # type: ignore[override]
        self.last_runtime_state = runtime_state
        raise RuntimeError("fallback planner.patch path only")


class _AllowSafetyAgent:
    def check_task_input(self, task, plan):
        return SafetyResult(
            task_id=task.task_id,
            phase="input",
            scope="task",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_post_step(self, step, step_result, context):
        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_final_result(self, context, design_result):
        return SafetyResult(
            task_id=context.task.task_id,
            phase="output",
            scope="result",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )


class _SuffixReplanPlanner(_PatchOnlyPlanner):
    def replan_top_k(self, request, *, k=3, runtime_state=None):  # type: ignore[override]
        suffix_plan = request.original_plan.model_copy(deep=True)
        suffix_plan.metadata["replan_mode"] = "suffix_replan"
        suffix_plan.metadata["variant"] = "suffix"

        full_plan = request.original_plan.model_copy(deep=True)
        full_plan.metadata["replan_mode"] = "full_replan"
        full_plan.metadata["variant"] = "full"

        return TopKResult(
            candidates=[
                PendingActionCandidate(
                    candidate_id="full_replan",
                    payload=full_plan,
                    structured_payload=full_plan,
                    summary="full replan",
                    metadata={"shadow_action": "continue"},
                ),
                PendingActionCandidate(
                    candidate_id="suffix_replan",
                    payload=suffix_plan,
                    structured_payload=suffix_plan,
                    summary="suffix replan",
                    metadata={"shadow_action": "suffix_replan"},
                ),
            ],
            default_recommendation="full_replan",
            explanation="replan candidates generated",
        )

    def evaluate_top_k_gate(
        self,
        *,
        candidate_kind,
        top_k_result,
        task_constraints,
    ):
        requires_hitl = bool(
            candidate_kind == "replan"
            and task_constraints.get("require_replan_confirm")
        )
        return CandidateGateDecision(
            requires_hitl=requires_hitl,
            reason="require_replan_confirm" if requires_hitl else "auto_replan",
            selected_candidate_id=top_k_result.default_recommendation,
            confidence=0.7,
            overall=0.6,
        )


class _ShadowStopPlanner(_PatchOnlyPlanner):
    def patch_top_k(self, request, *, k=3, runtime_state=None):  # type: ignore[override]
        patch = self.patch(request)
        return TopKResult(
            candidates=[
                PendingActionCandidate(
                    candidate_id="patch_stop",
                    payload=patch,
                    structured_payload=patch,
                    summary="stop via shadow action",
                    metadata={"shadow_action": "stop"},
                )
            ],
            default_recommendation="patch_stop",
            explanation="patch candidate generated with stop shadow action",
        )


@pytest.mark.integration
def test_workflow_action_selector_emits_continue_on_success():
    task_id = "int_workflow_action_continue"
    _cleanup_task_log(task_id)
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={},
    )
    runner = PlanRunner(
        step_runner=_SuccessStepRunner(),
        planner_agent=_PatchOnlyPlanner(),
        safety_agent=_AllowSafetyAgent(),
    )

    runner.run_plan(plan, context, record=record, finalize_status=False)

    events = read_timeline_events(task_id)
    finished = next(
        entry for entry in events if entry.get("event_type") == "STEP_FINISHED"
    )
    assert finished["action_name"] == "continue"
    assert context.status == InternalStatus.SUMMARIZING


@pytest.mark.integration
def test_workflow_action_selector_maps_patch_local_to_waiting_patch():
    task_id = "int_workflow_action_patch_local"
    _cleanup_task_log(task_id)
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={"require_patch_confirm": True},
    )
    runner = PlanRunner(
        step_runner=_FailOnceStepRunner(
            stage_id="S1",
            failure_code="S1_RETRY_EXHAUSTED",
        ),
        planner_agent=_PatchOnlyPlanner(),
        safety_agent=_AllowSafetyAgent(),
    )

    runner.run_plan(plan, context, record=record, finalize_status=False)

    assert context.status == InternalStatus.WAITING_PATCH
    assert record.status == ExternalStatus.WAITING_PATCH_CONFIRM
    assert context.pending_action is not None
    assert context.pending_action.action_type == PendingActionType.PATCH_CONFIRM
    assert context.pending_action.metadata["workflow_action"] == "patch_local"


@pytest.mark.integration
def test_dynamic_observation_only_policy_skips_runtime_state_but_keeps_patch_flow():
    task_id = "int_workflow_action_observation_only"
    _cleanup_task_log(task_id)
    planner = _ObservationOnlyPatchPlanner()
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={
            "require_patch_confirm": True,
            "runtime_policy": "dynamic_observation_only",
        },
    )
    runner = PlanRunner(
        step_runner=_FailOnceStepRunner(
            stage_id="S1",
            failure_code="S1_RETRY_EXHAUSTED",
        ),
        planner_agent=planner,
        safety_agent=_AllowSafetyAgent(),
    )

    runner.run_plan(plan, context, record=record, finalize_status=False)

    events = read_timeline_events(task_id)
    waiting = next(entry for entry in events if entry.get("event_type") == "WAITING_ENTER")
    assert context.status == InternalStatus.WAITING_PATCH
    assert context.runtime_state is None
    assert planner.last_runtime_state is None
    assert waiting["action_name"] == "patch"
    assert waiting["data"]["runtime_policy"] == "dynamic_observation_only"
    assert waiting["data"]["belief_state_enabled"] is False
    assert waiting["runtime_state_summary"] is None
    assert context.pending_action is not None
    assert context.pending_action.metadata["workflow_action"] == "patch_local"
    assert (
        context.pending_action.metadata["workflow_action_evidence"]["runtime_policy"]
        == "dynamic_observation_only"
    )


@pytest.mark.integration
def test_workflow_action_selector_maps_suffix_replan_to_waiting_replan():
    task_id = "int_workflow_action_suffix_replan"
    _cleanup_task_log(task_id)
    runtime_state = RuntimeState(
        p_success=0.22,
        p_structural_failure=0.78,
        recovery_margin=0.04,
        expected_remaining_cost=2.1,
        last_update_source="test",
        observation_summary={},
    )
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={"require_replan_confirm": True},
        runtime_state=runtime_state,
    )
    runner = PlanRunner(
        step_runner=_FailOnceStepRunner(
            stage_id="S2",
            failure_code="S2_TIMEOUT",
        ),
        planner_agent=_SuffixReplanPlanner(),
        safety_agent=_AllowSafetyAgent(),
    )

    replanned = runner.run_plan(
        plan,
        context,
        record=record,
        finalize_status=False,
        max_replans=1,
    )

    events = read_timeline_events(task_id)
    failed = next(entry for entry in events if entry.get("event_type") == "STEP_FAILED")
    assert failed["action_name"] == "suffix_replan"
    assert context.status in {
        InternalStatus.WAITING_REPLAN,
        InternalStatus.SUMMARIZING,
    }


@pytest.mark.integration
def test_workflow_action_selector_maps_stop_to_controlled_waiting_path():
    task_id = "int_workflow_action_stop"
    _cleanup_task_log(task_id)
    runtime_state = RuntimeState(
        p_success=0.4,
        p_structural_failure=0.3,
        recovery_margin=0.4,
        expected_remaining_cost=1.5,
        last_update_source="test",
        observation_summary={},
    )
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={"require_replan_confirm": True},
        runtime_state=runtime_state,
    )
    runner = PlanRunner(
        step_runner=_FailOnceStepRunner(
            stage_id="S1",
            failure_code="S1_RETRY_EXHAUSTED",
        ),
        planner_agent=_ShadowStopPlanner(),
        safety_agent=_AllowSafetyAgent(),
    )

    with pytest.raises(PlanRunError) as exc_info:
        runner.run_plan(plan, context, record=record, finalize_status=False)

    assert exc_info.value.code == "ADAPTIVE_STOP_REQUESTED"
    events = read_timeline_events(task_id)
    failed = next(entry for entry in events if entry.get("event_type") == "STEP_FAILED")
    assert failed["action_name"] == "stop"
    assert context.status == InternalStatus.WAITING_REPLAN
    assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
    assert context.pending_action is not None
    assert context.pending_action.default_recommendation is not None
    assert context.pending_action.candidates[0].metadata["terminal_policy"] == "stop"
    assert context.pending_action.candidates[0].metadata["terminal_reason"] == "economic_stop"


@pytest.mark.integration
def test_workflow_action_selector_maps_stop_to_waiting_even_without_explicit_confirm():
    task_id = "int_workflow_action_stop_always_waiting"
    _cleanup_task_log(task_id)
    runtime_state = RuntimeState(
        p_success=0.4,
        p_structural_failure=0.3,
        recovery_margin=0.4,
        expected_remaining_cost=1.5,
        last_update_source="test",
        observation_summary={},
    )
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={},
        runtime_state=runtime_state,
    )
    runner = PlanRunner(
        step_runner=_FailOnceStepRunner(
            stage_id="S1",
            failure_code="S1_RETRY_EXHAUSTED",
        ),
        planner_agent=_ShadowStopPlanner(),
        safety_agent=_AllowSafetyAgent(),
    )

    with pytest.raises(PlanRunError) as exc_info:
        runner.run_plan(plan, context, record=record, finalize_status=False)

    assert exc_info.value.code == "ADAPTIVE_STOP_REQUESTED"
    assert context.status == InternalStatus.WAITING_REPLAN
    assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
    assert context.pending_action is not None
    assert context.pending_action.candidates[0].metadata["terminal_policy"] == "stop"


@pytest.mark.integration
def test_workflow_action_selector_prefers_suffix_replan_candidate_on_recovery():
    task_id = "int_workflow_action_replan_preference"
    _cleanup_task_log(task_id)
    runtime_state = RuntimeState(
        p_success=0.24,
        p_structural_failure=0.74,
        recovery_margin=0.03,
        expected_remaining_cost=2.2,
        last_update_source="test",
        observation_summary={},
    )
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={},
        runtime_state=runtime_state,
    )
    runner = PlanRunner(
        step_runner=_FailOnceStepRunner(
            stage_id="S2",
            failure_code="S2_TIMEOUT",
        ),
        planner_agent=_SuffixReplanPlanner(),
        safety_agent=_AllowSafetyAgent(),
    )

    replanned = runner.run_plan(
        plan,
        context,
        record=record,
        finalize_status=False,
        max_replans=1,
    )

    assert replanned.metadata["replan_mode"] == "suffix_replan"
    assert context.plan is replanned
