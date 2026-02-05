from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import Plan, PlanStep, now_iso
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.tools.visualization.adapter import VisualizationToolAdapter
from src.workflow.context import WorkflowContext
from src.workflow.patch_runner import PatchRunner
from src.workflow.step_runner import StepRunner


class RecordingStepRunner:
    def __init__(self) -> None:
        self.last_result = None
        self._runner = StepRunner()

    def run_step(self, step: PlanStep, context: WorkflowContext):
        result = self._runner.run_step(step, context)
        self.last_result = result
        return result


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


def test_invalid_pdb_ref_enters_waiting_replan(sample_task, tmp_path: Path) -> None:
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
    register_adapter(VisualizationToolAdapter())

    missing_pdb = tmp_path / "missing.pdb"
    plan = Plan(
        task_id=sample_task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="visualize_structure",
                inputs={"pdb_path": str(missing_pdb), "out_dir": str(tmp_path / "out")},
                metadata={},
            )
        ],
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
        created_at=now_iso(),
        updated_at=now_iso(),
        goal=sample_task.goal,
        constraints=sample_task.constraints,
        metadata=sample_task.metadata,
        plan=plan,
        design_result=None,
        safety_events=[],
    )

    step_runner = RecordingStepRunner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=FailingPlanner())

    with pytest.raises(RuntimeError):
        patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert context.status == InternalStatus.WAITING_REPLAN
    assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
    assert step_runner.last_result is not None
    assert step_runner.last_result.status == "failed"
    assert step_runner.last_result.error_message

    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
