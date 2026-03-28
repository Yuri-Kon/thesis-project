from __future__ import annotations

from pathlib import Path

import pytest

import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import Plan, PlanStep, ProteinDesignTask, StepResult, now_iso
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.storage.log_store import DEFAULT_LOG_DIR, read_timeline_events
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType
from src.workflow.patch_runner import PatchRunner


def _cleanup_task_log(task_id: str) -> None:
    path = Path(DEFAULT_LOG_DIR) / f"{task_id}.jsonl"
    if path.exists():
        path.unlink()


def _patch_runtime_kg() -> dict:
    return {
        "capabilities": [
            {"capability_id": "structure_prediction", "name": "Structure", "domain": "protein/structure"},
            {"capability_id": "quality_qc", "name": "QC", "domain": "protein/qc"},
        ],
        "io_types": [
            {
                "io_type_id": "sequence_to_structure",
                "input_types": ["sequence"],
                "output_types": ["structure_pdb", "plddt"],
                "combinable": True,
            },
            {
                "io_type_id": "sequence_structure_to_qc_metrics",
                "input_types": ["sequence", "pdb_path"],
                "output_types": ["qc_metrics"],
                "combinable": True,
            },
        ],
        "tools": [
            {
                "id": "failing_tool",
                "capabilities": ["structure_prediction"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": {"backend": "remote_model_service", "provider": "nim"},
                "constraints": {},
            },
            {
                "id": "esmfold",
                "capabilities": ["structure_prediction"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": "nextflow",
                "constraints": {},
            },
            {
                "id": "biopython_qc",
                "capabilities": ["quality_qc"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_structure_to_qc_metrics",
                    "inputs": {"sequence": "str", "pdb_path": "path"},
                    "outputs": {"qc_metrics": "dict"},
                },
                "execution": "python",
                "constraints": {},
            },
        ],
    }


def _build_runtime_objects(
    *,
    task_id: str,
    constraints: dict,
    step_tool: str,
) -> tuple[Plan, WorkflowContext, TaskRecord]:
    task = ProteinDesignTask(
        task_id=task_id,
        goal="layered-patch-test",
        constraints=constraints,
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[PlanStep(id="S1", tool=step_tool, inputs={"sequence": "MKTAYIAK"}, metadata={})],
        constraints=constraints,
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        plan=plan,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.RUNNING,
    )
    record = TaskRecord(
        id=task.task_id,
        status=ExternalStatus.RUNNING,
        internal_status=InternalStatus.RUNNING,
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=plan,
    )
    return plan, context, record


class _LayeredFallbackStepRunner:
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
                error_message="first attempt failed",
                error_details={},
                outputs={},
                metrics={"retry_exhausted": True},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
        if step.tool == "failing_tool":
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.TOOL_ERROR,
                error_message="parameter-level patch failed",
                error_details={},
                outputs={},
                metrics={},
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
            outputs={"pdb_path": "/tmp/a.pdb", "plddt": 0.9},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


class _AlwaysFailStepRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        self.calls.append(step.tool)
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="failed",
            failure_type=FailureType.TOOL_ERROR,
            error_message="all patch attempts failed",
            error_details={},
            outputs={},
            metrics={"retry_exhausted": True} if len(self.calls) == 1 else {},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


class _SingleFailStepRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        self.calls += 1
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="failed",
            failure_type=FailureType.RETRYABLE,
            error_message="retry exhausted",
            error_details={},
            outputs={},
            metrics={"retry_exhausted": True},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


@pytest.mark.integration
def test_layered_patch_promotes_from_parameter_to_tool_level(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _patch_runtime_kg())
    planner = PlannerAgent(
        tool_registry=[
            ToolSpec(
                id="failing_tool",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.6,
                safety_level=1,
                io_type="sequence_to_structure",
                adapter_mode="local",
                priority="P0",
            ),
            ToolSpec(
                id="esmfold",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.5,
                safety_level=1,
                io_type="sequence_to_structure",
                adapter_mode="local",
                priority="P0",
            ),
            ToolSpec(
                id="biopython_qc",
                capabilities=("quality_qc",),
                inputs=("sequence", "pdb_path"),
                outputs=("qc_metrics",),
                cost=0.2,
                safety_level=1,
                io_type="sequence_structure_to_qc_metrics",
                adapter_mode="local",
                priority="P0",
            ),
        ]
    )
    task_id = "int_layered_patch_tool_success"
    _cleanup_task_log(task_id)
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={
            "require_patch_confirm": False,
            "min_candidate_confidence": 0.0,
            "high_cost_min_overall": 0.0,
        },
        step_tool="failing_tool",
    )
    step_runner = _LayeredFallbackStepRunner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=planner)

    outcome = patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert step_runner.calls == ["failing_tool", "failing_tool", "esmfold"]
    assert context.status == InternalStatus.PATCHING
    assert record.status == ExternalStatus.WAITING_PATCH_CONFIRM
    assert outcome.step_results[0].status == "success"
    patch_meta = outcome.step_results[0].metrics.get("patch")
    assert patch_meta["layer"] == "tool_level"
    assert patch_meta["from_tool"] == "failing_tool"
    assert patch_meta["to_tool"] == "esmfold"
    assert patch_meta["capability_id"] == "structure_prediction"
    assert patch_meta["reason"] == "tool_swap_replacement_matrix"

    events = read_timeline_events(task_id)
    replace_events = [e for e in events if e.get("event_type") == "REPLACE_TOOL"]
    assert replace_events
    recovery = replace_events[-1]["data"]["recovery"]
    assert recovery["from_tool"] == "failing_tool"
    assert recovery["to_tool"] == "esmfold"
    assert recovery["capability_id"] == "structure_prediction"
    assert replace_events[-1]["data"]["runtime_state_summary"]["p_success"] == pytest.approx(0.5)


@pytest.mark.integration
def test_layered_patch_promotes_remote_to_local_tool_level(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _patch_runtime_kg())
    planner = PlannerAgent(
        tool_registry=[
            ToolSpec(
                id="failing_tool",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.6,
                safety_level=1,
                io_type="sequence_to_structure",
                adapter_mode="remote",
                priority="P0",
            ),
            ToolSpec(
                id="esmfold",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.5,
                safety_level=1,
                io_type="sequence_to_structure",
                adapter_mode="local",
                priority="P0",
            ),
            ToolSpec(
                id="biopython_qc",
                capabilities=("quality_qc",),
                inputs=("sequence", "pdb_path"),
                outputs=("qc_metrics",),
                cost=0.2,
                safety_level=1,
                io_type="sequence_structure_to_qc_metrics",
                adapter_mode="local",
                priority="P0",
            ),
        ]
    )
    task_id = "int_layered_patch_remote_to_local"
    _cleanup_task_log(task_id)
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={
            "require_patch_confirm": False,
            "min_candidate_confidence": 0.0,
            "high_cost_min_overall": 0.0,
        },
        step_tool="failing_tool",
    )
    step_runner = _LayeredFallbackStepRunner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=planner)

    outcome = patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert step_runner.calls == ["failing_tool", "failing_tool", "esmfold"]
    assert context.status == InternalStatus.PATCHING
    assert outcome.step_results[0].status == "success"
    patch_meta = outcome.step_results[0].metrics.get("patch")
    assert patch_meta["layer"] == "tool_level"
    assert patch_meta["from_tool"] == "failing_tool"
    assert patch_meta["to_tool"] == "esmfold"

    events = read_timeline_events(task_id)
    replace_events = [e for e in events if e.get("event_type") == "REPLACE_TOOL"]
    assert replace_events
    recovery = replace_events[-1]["data"]["recovery"]
    assert recovery["from_tool"] == "failing_tool"
    assert recovery["to_tool"] == "esmfold"
    assert replace_events[-1]["data"]["runtime_state_summary"]["p_success"] == pytest.approx(0.5)


@pytest.mark.integration
def test_layered_patch_failure_escalates_to_replan_with_trace(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _patch_runtime_kg())
    planner = PlannerAgent(
        tool_registry=[
            ToolSpec(
                id="failing_tool",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.6,
                safety_level=1,
                io_type="sequence_to_structure",
                adapter_mode="local",
                priority="P0",
            ),
            ToolSpec(
                id="esmfold",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.5,
                safety_level=1,
                io_type="sequence_to_structure",
                adapter_mode="local",
                priority="P0",
            ),
        ]
    )
    task_id = "int_layered_patch_all_failed"
    _cleanup_task_log(task_id)
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={
            "require_patch_confirm": False,
            "min_candidate_confidence": 0.0,
            "high_cost_min_overall": 0.0,
        },
        step_tool="failing_tool",
    )
    patch_runner = PatchRunner(step_runner=_AlwaysFailStepRunner(), planner_agent=planner)

    outcome = patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert context.status == InternalStatus.WAITING_REPLAN
    assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
    assert outcome.step_results
    failed = outcome.step_results[0]
    recovery = failed.metrics.get("recovery")
    assert recovery["upgrade_reason"] == "patch_failed"
    assert isinstance(recovery.get("attempts"), list)
    assert len(recovery["attempts"]) >= 2

    events = read_timeline_events(task_id)
    escalated = [e for e in events if e.get("event_type") == "RECOVERY_ESCALATED"]
    assert escalated
    assert escalated[-1]["data"]["reason"] == "patch_failed"
    assert escalated[-1]["data"]["runtime_state_summary"]["p_success"] == pytest.approx(0.5)


@pytest.mark.integration
def test_high_risk_patch_escalates_to_replan(monkeypatch):
    kg = {
        "capabilities": [
            {"capability_id": "structure_prediction", "name": "Structure", "domain": "protein/structure"}
        ],
        "io_types": [
            {
                "io_type_id": "sequence_to_structure",
                "input_types": ["sequence"],
                "output_types": ["structure_pdb", "plddt"],
                "combinable": True,
            }
        ],
        "tools": [
            {
                "id": "risky_tool",
                "capabilities": ["structure_prediction"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": {"backend": "remote_model_service", "provider": "nim"},
                "constraints": {},
            }
        ],
    }
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: kg)
    planner = PlannerAgent(
        tool_registry=[
            ToolSpec(
                id="risky_tool",
                capabilities=("structure_prediction",),
                inputs=("sequence",),
                outputs=("pdb_path", "plddt"),
                cost=0.6,
                safety_level=5,
                io_type="sequence_to_structure",
                adapter_mode="remote",
                priority="P0",
            )
        ]
    )
    task_id = "int_layered_patch_high_risk"
    _cleanup_task_log(task_id)
    plan, context, record = _build_runtime_objects(
        task_id=task_id,
        constraints={
            "require_patch_confirm": False,
            "min_candidate_confidence": 0.0,
            "high_cost_min_overall": 0.0,
        },
        step_tool="risky_tool",
    )
    patch_runner = PatchRunner(step_runner=_SingleFailStepRunner(), planner_agent=planner)

    outcome = patch_runner.run_step_with_patch(plan, 0, context, record=record)

    assert context.status == InternalStatus.WAITING_REPLAN
    assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
    recovery = outcome.step_results[0].metrics.get("recovery")
    assert recovery["upgrade_reason"] == "patch_high_risk"

    events = read_timeline_events(task_id)
    escalated = [e for e in events if e.get("event_type") == "RECOVERY_ESCALATED"]
    assert escalated
    assert escalated[-1]["data"]["reason"] == "patch_high_risk"
    assert escalated[-1]["data"]["runtime_state_summary"]["p_success"] == pytest.approx(0.5)
