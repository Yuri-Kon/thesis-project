from __future__ import annotations

import pytest

import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import Plan, PlanStep, ProteinDesignTask, StepResult, now_iso
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType
from src.workflow.patch_runner import PatchRunner


def _registry() -> list[ToolSpec]:
    return [
        ToolSpec(
            id="protgpt2",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence", "sequence_candidates"),
            cost=0.35,
            safety_level=1,
            io_type="goal_to_sequence_candidates",
            adapter_mode="remote",
            priority="P0",
        ),
        ToolSpec(
            id="esmfold",
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
            id="nim_esmfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path", "plddt"),
            cost=0.3,
            safety_level=1,
            io_type="sequence_to_structure",
            adapter_mode="remote",
            priority="P0",
        ),
        ToolSpec(
            id="protein_mpnn",
            capabilities=("sequence_design",),
            inputs=("pdb_path",),
            outputs=("sequence",),
            cost=0.4,
            safety_level=1,
            io_type="structure_to_sequence",
            adapter_mode="remote",
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
        ToolSpec(
            id="objective_ranker",
            capabilities=("objective_scoring",),
            inputs=("candidates",),
            outputs=("score_table", "top_k"),
            cost=0.25,
            safety_level=1,
            io_type="candidates_to_objective_scores_topk",
            adapter_mode="local",
            priority="P0",
        ),
    ]


def _kg() -> dict:
    return {
        "capabilities": [
            {"capability_id": "sequence_generation", "name": "Sequence Generation", "domain": "protein/design"},
            {"capability_id": "structure_prediction", "name": "Structure Prediction", "domain": "protein/structure"},
            {"capability_id": "sequence_design", "name": "Sequence Design", "domain": "protein/design"},
            {"capability_id": "quality_qc", "name": "Quality QC", "domain": "protein/qc"},
            {"capability_id": "objective_scoring", "name": "Objective Scoring", "domain": "protein/score"},
        ],
        "io_types": [
            {"io_type_id": "goal_to_sequence_candidates", "input_types": ["goal"], "output_types": ["sequence"], "combinable": True},
            {"io_type_id": "sequence_to_structure", "input_types": ["sequence"], "output_types": ["structure_pdb", "plddt"], "combinable": True},
            {"io_type_id": "structure_to_sequence", "input_types": ["structure_pdb"], "output_types": ["sequence"], "combinable": True},
            {"io_type_id": "sequence_structure_to_qc_metrics", "input_types": ["sequence", "structure_pdb"], "output_types": ["qc_metrics"], "combinable": True},
            {"io_type_id": "candidates_to_objective_scores_topk", "input_types": ["candidates"], "output_types": ["score_table", "top_k"], "combinable": True},
        ],
        "tools": [
            {
                "id": "protgpt2",
                "capabilities": ["sequence_generation"],
                "priority": "P0",
                "io": {
                    "io_type_id": "goal_to_sequence_candidates",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str", "sequence_candidates": "list"},
                },
                "execution": {"backend": "remote_model_service", "provider": "plm_rest"},
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
                "id": "nim_esmfold",
                "capabilities": ["structure_prediction"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": {"backend": "remote_model_service", "provider": "nvidia_nim"},
                "constraints": {},
            },
            {
                "id": "protein_mpnn",
                "capabilities": ["sequence_design"],
                "priority": "P0",
                "io": {
                    "io_type_id": "structure_to_sequence",
                    "inputs": {"pdb_path": "path"},
                    "outputs": {"sequence": "str"},
                },
                "execution": {"backend": "remote_model_service", "provider": "nvidia_nim"},
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
            {
                "id": "objective_ranker",
                "capabilities": ["objective_scoring"],
                "priority": "P0",
                "io": {
                    "io_type_id": "candidates_to_objective_scores_topk",
                    "inputs": {"candidates": "list"},
                    "outputs": {"score_table": "dict", "top_k": "list"},
                },
                "execution": "python",
                "constraints": {},
            },
        ],
    }


class _FailThenSuccessStepRunner:
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
                metrics={"retry_exhausted": True},
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
            outputs={"pdb_path": "/tmp/a.pdb", "plddt": 0.91},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


@pytest.mark.integration
def test_plan_gate_waiting_and_auto_paths(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _kg())
    planner = PlannerAgent(tool_registry=_registry())

    waiting_task = ProteinDesignTask(
        task_id="gate_plan_waiting",
        goal="de_novo_design",
        constraints={"length_range": [30, 50], "min_candidate_confidence": 0.99},
        metadata={},
    )
    waiting_ctx = WorkflowContext(
        task=waiting_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.CREATED,
    )
    waiting_record = TaskRecord(
        id=waiting_task.task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
        goal=waiting_task.goal,
        constraints=waiting_task.constraints,
        metadata=waiting_task.metadata,
        plan=None,
    )
    planner.plan_with_status(waiting_task, waiting_ctx, record=waiting_record)
    assert waiting_ctx.status == InternalStatus.WAITING_PLAN_CONFIRM
    assert waiting_record.status == ExternalStatus.WAITING_PLAN_CONFIRM
    assert waiting_ctx.pending_action is not None

    auto_task = ProteinDesignTask(
        task_id="gate_plan_auto",
        goal="de_novo_design",
        constraints={
            "length_range": [30, 50],
            "min_candidate_confidence": 0.2,
            "require_plan_confirm": False,
        },
        metadata={},
    )
    auto_ctx = WorkflowContext(
        task=auto_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.CREATED,
    )
    auto_record = TaskRecord(
        id=auto_task.task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
        goal=auto_task.goal,
        constraints=auto_task.constraints,
        metadata=auto_task.metadata,
        plan=None,
    )
    planner.plan_with_status(auto_task, auto_ctx, record=auto_record)
    assert auto_ctx.status == InternalStatus.PLANNED
    assert auto_record.status == ExternalStatus.PLANNED


@pytest.mark.integration
def test_patch_gate_waiting_and_auto_paths(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _kg())
    planner = PlannerAgent(tool_registry=_registry())
    step_runner = _FailThenSuccessStepRunner()
    patch_runner = PatchRunner(step_runner=step_runner, planner_agent=planner)

    def run_once(task_id: str, require_patch_confirm: bool) -> tuple[WorkflowContext, TaskRecord]:
        task = ProteinDesignTask(
            task_id=task_id,
            goal="patch-test",
            constraints={
                "sequence": "MKTAYIAK",
                "require_patch_confirm": require_patch_confirm,
                "min_candidate_confidence": 0.2,
            },
            metadata={},
        )
        plan = Plan(
            task_id=task_id,
            steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "MKTAYIAK"}, metadata={})],
            constraints=task.constraints,
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
        patch_runner.run_step_with_patch(plan, 0, context, record=record)
        return context, record

    waiting_ctx, waiting_record = run_once("gate_patch_waiting", True)
    assert waiting_ctx.status == InternalStatus.WAITING_PATCH
    assert waiting_record.status == ExternalStatus.WAITING_PATCH_CONFIRM
    assert waiting_ctx.pending_action is not None

    step_runner.calls.clear()
    auto_ctx, auto_record = run_once("gate_patch_auto", False)
    assert auto_ctx.status == InternalStatus.PATCHING
    assert auto_record.status == ExternalStatus.WAITING_PATCH_CONFIRM
