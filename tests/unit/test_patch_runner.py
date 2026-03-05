import pytest

from src.models.contracts import (
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    PendingActionStatus,
    PendingActionType,
    StepResult,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext
from src.workflow.patch_runner import PatchRunner
from src.workflow.errors import FailureType
from src.agents.planner import PlannerAgent, ToolSpec


class FakeStepRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        self.calls.append(step.tool)
        if len(self.calls) == 1:
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.RETRYABLE,
                error_message="boom",
                error_details={},
                outputs={},
                metrics={
                    "retry_exhausted": True,
                    "attempt_history": [
                        {"attempt": 1, "status": "failed", "failure_type": "RETRYABLE"}
                    ],
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={"dummy_output": "ok"},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


class FakePlanner(PlannerAgent):
    def __init__(self) -> None:
        super().__init__(
            tool_registry=[
                ToolSpec(
                    id="failing_tool",
                    capabilities=("structure_prediction",),
                    inputs=(),
                    outputs=("dummy_output",),
                    cost=1,
                    safety_level=1,
                    io_type="sequence_to_structure",
                    adapter_mode="local",
                    priority="P0",
                ),
                ToolSpec(
                    id="patched_tool",
                    capabilities=("structure_prediction",),
                    inputs=(),
                    outputs=("dummy_output",),
                    cost=0.5,
                    safety_level=1,
                    io_type="sequence_to_structure",
                    adapter_mode="local",
                    priority="P0",
                )
            ]
        )
        self.requests = []

    def patch(self, request):  # type: ignore[override]
        self.requests.append(request)
        step = request.original_plan.steps[0]
        patched_step = PlanStep(
            id=step.id,
            tool="patched_tool",
            inputs=step.inputs,
            metadata=step.metadata,
        )
        op = PlanPatchOp(op="replace_step", target=step.id, step=patched_step)
        return PlanPatch(task_id=request.task_id, operations=[op], metadata={})


def _mock_patch_kg():
    return {
        "capabilities": [
            {
                "capability_id": "structure_prediction",
                "name": "Structure Prediction",
                "domain": "protein/structure",
                "description": "test",
            }
        ],
        "io_types": [
            {
                "io_type_id": "sequence_to_structure",
                "input_types": ["sequence"],
                "output_types": ["structure_pdb"],
                "combinable": True,
            }
        ],
        "tools": [
            {
                "id": "failing_tool",
                "capabilities": ["structure_prediction"],
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {},
                    "outputs": {"dummy_output": "str"},
                },
                "execution": "python",
                "constraints": {},
            },
            {
                "id": "patched_tool",
                "capabilities": ["structure_prediction"],
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {},
                    "outputs": {"dummy_output": "str"},
                },
                "execution": "python",
                "constraints": {},
            },
        ],
    }


def test_patch_runner_triggers_patch_and_records_meta(sample_task, monkeypatch):
    monkeypatch.setattr("src.agents.planner.load_tool_kg", lambda: _mock_patch_kg())
    sample_task = sample_task.model_copy(
        update={
            "constraints": {
                **sample_task.constraints,
                "require_patch_confirm": False,
                "min_candidate_confidence": 0.0,
                "high_cost_min_overall": 0.0,
            }
        },
        deep=True,
    )
    plan = Plan(
        task_id=sample_task.task_id,
        steps=[PlanStep(id="S1", tool="failing_tool", inputs={}, metadata={})],
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=sample_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.RUNNING,
    )
    record = TaskRecord(
        id=sample_task.task_id,
        status=ExternalStatus.RUNNING,
        internal_status=InternalStatus.RUNNING,
        goal=sample_task.goal,
        constraints=sample_task.constraints,
        metadata=sample_task.metadata,
        plan=plan,
    )

    step_runner = FakeStepRunner()
    planner = FakePlanner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=planner)

    outcome = patch_runner.run_step_with_patch(plan, 0, context, record=record)
    patched_plan = outcome.plan
    patched_result = outcome.step_results[0]

    # patch 应被触发并自动应用
    assert step_runner.calls == ["failing_tool", "patched_tool"]

    # plan 应被替换为 patched 版本
    assert patched_plan.steps[0].tool == "patched_tool"
    assert context.plan is patched_plan
    assert record.plan is patched_plan
    assert outcome.next_step_index == 1
    assert outcome.pending_patch is None

    # patched step 应执行成功并返回
    assert patched_result.status == "success"
    assert patched_result.tool == "patched_tool"

    patch_meta = patched_result.metrics.get("patch")
    assert patch_meta and patch_meta["applied"] is True
    assert patch_meta["from_tool"] == "failing_tool"
    assert patch_meta["to_tool"] == "patched_tool"
    assert patch_meta["patched_status"] == "success"
    prev_attempt = patch_meta["previous_attempt"]
    assert prev_attempt["attempt_history"][0]["failure_type"] == "RETRYABLE"
    assert context.status == InternalStatus.PATCHING
    assert record.status == ExternalStatus.WAITING_PATCH_CONFIRM
    assert record.pending_action is None


def test_patch_runner_enters_waiting_patch_when_gate_requires_hitl(sample_task, monkeypatch):
    monkeypatch.setattr("src.agents.planner.load_tool_kg", lambda: _mock_patch_kg())
    sample_task = sample_task.model_copy(
        update={
            "constraints": {
                **sample_task.constraints,
                "require_patch_confirm": True,
            }
        },
        deep=True,
    )
    plan = Plan(
        task_id=sample_task.task_id,
        steps=[PlanStep(id="S1", tool="failing_tool", inputs={}, metadata={})],
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=sample_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.RUNNING,
    )
    record = TaskRecord(
        id=sample_task.task_id,
        status=ExternalStatus.RUNNING,
        internal_status=InternalStatus.RUNNING,
        goal=sample_task.goal,
        constraints=sample_task.constraints,
        metadata=sample_task.metadata,
        plan=plan,
    )

    step_runner = FakeStepRunner()
    planner = FakePlanner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=planner)

    outcome = patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert step_runner.calls == ["failing_tool"]
    assert not outcome.step_results
    assert outcome.next_step_index == 0
    assert context.status == InternalStatus.WAITING_PATCH
    assert record.status == ExternalStatus.WAITING_PATCH_CONFIRM
    assert record.pending_action is not None
    assert record.pending_action.action_type == PendingActionType.PATCH_CONFIRM
    assert record.pending_action.status == PendingActionStatus.PENDING


def test_patch_runner_enters_waiting_replan_on_patch_error(sample_task):
    plan = Plan(
        task_id=sample_task.task_id,
        steps=[PlanStep(id="S1", tool="failing_tool", inputs={}, metadata={})],
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=sample_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.RUNNING,
    )
    record = TaskRecord(
        id=sample_task.task_id,
        status=ExternalStatus.RUNNING,
        internal_status=InternalStatus.RUNNING,
        goal=sample_task.goal,
        constraints=sample_task.constraints,
        metadata=sample_task.metadata,
        plan=plan,
    )

    class FailingPlanner(PlannerAgent):
        def __init__(self) -> None:
            super().__init__(
                tool_registry=[
                    ToolSpec(
                        id="esmfold",
                        capabilities=("structure_prediction",),
                        inputs=("sequence",),
                        outputs=("pdb_path", "plddt"),
                        cost=1,
                        safety_level=1,
                    )
                ]
            )

        def patch(self, request):  # type: ignore[override]
            raise RuntimeError("planner patch failed")

    step_runner = FakeStepRunner()
    planner = FailingPlanner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=planner)

    with pytest.raises(RuntimeError):
        patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert context.status == InternalStatus.WAITING_REPLAN
    assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
    assert record.pending_action is not None
    assert record.pending_action.action_type == PendingActionType.REPLAN_CONFIRM
    assert record.pending_action.status == PendingActionStatus.PENDING
    assert record.pending_action.explanation
