from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest

import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.models.contracts import (
    Decision,
    DecisionChoice,
    PendingActionType,
    Plan,
    PlanStep,
    ProteinDesignTask,
    StepResult,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.models.event_log import EventType
from src.storage.log_store import DEFAULT_LOG_DIR, read_timeline_events
from src.workflow.context import WorkflowContext
from src.workflow.decision_apply import apply_patch_confirm_decision
from src.workflow.errors import FailureType
from src.workflow.errors import PlanRunError
from src.workflow.plan_runner import PlanRunner


def _cleanup_task_log(task_id: str) -> None:
    path = Path(DEFAULT_LOG_DIR) / f"{task_id}.jsonl"
    if path.exists():
        path.unlink()


def _s6_runtime_kg() -> dict:
    return {
        "capabilities": [
            {"capability_id": "sequence_generation", "name": "Sequence", "domain": "protein/design"},
            {"capability_id": "structure_prediction", "name": "Structure", "domain": "protein/structure"},
            {"capability_id": "quality_qc", "name": "QC", "domain": "protein/qc"},
            {"capability_id": "sequence_design", "name": "Refinement", "domain": "protein/design"},
            {"capability_id": "objective_scoring", "name": "Objective", "domain": "protein/score"},
        ],
        "io_types": [
            {
                "io_type_id": "goal_to_sequence_candidates",
                "input_types": ["goal"],
                "output_types": ["sequence"],
                "combinable": True,
            },
            {
                "io_type_id": "sequence_to_structure",
                "input_types": ["sequence"],
                "output_types": ["pdb_path", "plddt"],
                "combinable": True,
            },
            {
                "io_type_id": "sequence_structure_to_qc_metrics",
                "input_types": ["sequence", "pdb_path"],
                "output_types": ["qc_metrics"],
                "combinable": True,
            },
            {
                "io_type_id": "structure_to_sequence",
                "input_types": ["pdb_path"],
                "output_types": ["sequence"],
                "combinable": True,
            },
            {
                "io_type_id": "candidates_to_objective_scores_topk",
                "input_types": ["candidates"],
                "output_types": ["score_table", "top_k"],
                "combinable": True,
            },
        ],
        "tools": [
            {
                "id": "seqgen_local",
                "capabilities": ["sequence_generation"],
                "priority": "P0",
                "io": {
                    "io_type_id": "goal_to_sequence_candidates",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str"},
                },
                "execution": "python",
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
                    "outputs": {"qc_metrics": "list"},
                },
                "execution": "python",
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
                "execution": "python",
                "constraints": {},
            },
            {
                "id": "objective_ranker_v2",
                "capabilities": ["objective_scoring"],
                "priority": "P1",
                "io": {
                    "io_type_id": "candidates_to_objective_scores_topk",
                    "inputs": {"candidates": "list"},
                    "outputs": {"score_table": "dict", "top_k": "list"},
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


def _s6_registry() -> list[ToolSpec]:
    return [
        ToolSpec(
            id="seqgen_local",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence",),
            cost=0.2,
            safety_level=1,
            io_type="goal_to_sequence_candidates",
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
        ToolSpec(
            id="protein_mpnn",
            capabilities=("sequence_design",),
            inputs=("pdb_path",),
            outputs=("sequence",),
            cost=0.3,
            safety_level=1,
            io_type="structure_to_sequence",
            adapter_mode="local",
            priority="P0",
        ),
        ToolSpec(
            id="objective_ranker_v2",
            capabilities=("objective_scoring",),
            inputs=("candidates",),
            outputs=("score_table", "top_k"),
            cost=0.35,
            safety_level=1,
            io_type="candidates_to_objective_scores_topk",
            adapter_mode="local",
            priority="P1",
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


class _SixStageStepRunner:
    def __init__(self, *, fail_stage: str | None = None):
        self._fail_stage = fail_stage
        self._calls = defaultdict(int)

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        self._calls[step.id] += 1

        if self._fail_stage == "S3" and step.id == "S3":
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.NON_RETRYABLE,
                error_message="quality gate rejected all candidates",
                error_details={"failure_code": "S3_ALL_CANDIDATES_REJECTED"},
                outputs={"stage_id": "S3"},
                metrics={"retry_exhausted": True},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )

        if self._fail_stage == "S5_once" and step.id == "S5" and self._calls[step.id] == 1:
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.RETRYABLE,
                error_message="objective scoring transient failure",
                error_details={"failure_code": "S5_SCORE_TEMP_UNAVAILABLE"},
                outputs={"stage_id": "S5"},
                metrics={"retry_exhausted": True},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )

        outputs = _success_outputs(step.id)
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs=outputs,
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )


def _success_outputs(step_id: str) -> dict:
    if step_id == "S1":
        return {"stage_id": "S1", "sequence": "MKTAYIAK"}
    if step_id == "S2":
        return {"stage_id": "S2", "pdb_path": "/tmp/s2.pdb", "plddt": 0.82}
    if step_id == "S3":
        return {
            "stage_id": "S3",
            "qc_metrics": [{"candidate_id": "c1", "status": "PASS"}],
            "pass_count": 1,
            "fail_count": 0,
        }
    if step_id == "S4":
        return {"stage_id": "S4", "sequence": "MKTAYIAKGG"}
    if step_id == "S5":
        return {
            "stage_id": "S5",
            "score_table": {"c1": 0.88},
            "top_k": ["c1"],
        }
    return {"stage_id": step_id}


def _build_plan(task_id: str, constraints: dict) -> tuple[Plan, WorkflowContext, TaskRecord]:
    task = ProteinDesignTask(
        task_id=task_id,
        goal="six-stage-e2e",
        constraints=constraints,
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="seqgen_local", inputs={"goal": "de_novo_design"}, metadata={"stage_id": "S1"}),
            PlanStep(id="S2", tool="esmfold", inputs={"sequence": "S1.sequence"}, metadata={"stage_id": "S2"}),
            PlanStep(
                id="S3",
                tool="biopython_qc",
                inputs={"sequence": "S1.sequence", "pdb_path": "S2.pdb_path"},
                metadata={"stage_id": "S3"},
            ),
            PlanStep(id="S4", tool="protein_mpnn", inputs={"pdb_path": "S2.pdb_path"}, metadata={"stage_id": "S4"}),
            PlanStep(
                id="S5",
                tool="objective_ranker_v2",
                inputs={"candidates": "S3.qc_metrics"},
                metadata={"stage_id": "S5"},
            ),
        ],
        constraints=constraints,
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        status=InternalStatus.PLANNED,
        plan=None,
        step_results={},
        design_result=None,
        safety_events=[],
        pending_action=None,
    )
    record = TaskRecord(
        id=task.task_id,
        status=ExternalStatus.PLANNED,
        internal_status=InternalStatus.PLANNED,
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=None,
    )
    return plan, context, record


@pytest.mark.integration
def test_six_stage_waiting_patch_decision_replay_to_done(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _s6_runtime_kg())
    planner = PlannerAgent(tool_registry=_s6_registry())
    runner = PlanRunner(
        step_runner=_SixStageStepRunner(fail_stage="S5_once"),
        planner_agent=planner,
    )

    task_id = "int_s6_patch_decision_replay_done"
    _cleanup_task_log(task_id)
    plan, context, record = _build_plan(
        task_id,
        constraints={
            "require_patch_confirm": True,
            "require_replan_confirm": True,
            "min_candidate_confidence": 0.0,
            "high_cost_min_overall": 0.0,
        },
    )

    runner.run_plan(plan, context, record=record, finalize_status=False)
    assert context.status == InternalStatus.WAITING_PATCH
    assert record.status == ExternalStatus.WAITING_PATCH_CONFIRM
    assert context.pending_action is not None
    assert context.pending_action.action_type == PendingActionType.PATCH_CONFIRM

    decision = Decision(
        decision_id=f"decision_{task_id}",
        task_id=task_id,
        pending_action_id=context.pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id=context.pending_action.default_recommendation,
        decided_by="integration-test",
    )
    apply_patch_confirm_decision(context, record, decision)
    assert context.status == InternalStatus.RUNNING

    runner.run_plan(
        context.plan or plan,
        context,
        record=record,
        finalize_status=True,
        resume_from_existing=True,
    )
    assert context.status == InternalStatus.DONE
    assert record.status == ExternalStatus.DONE

    events = read_timeline_events(task_id)
    event_types = [entry.get("event_type") for entry in events]
    assert EventType.WAITING_ENTER.value in event_types
    assert EventType.DECISION_APPLIED.value in event_types
    assert EventType.WAITING_EXIT.value in event_types


@pytest.mark.integration
def test_s6_trigger_matrix_routes_s3_failure_to_replan(monkeypatch):
    monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _s6_runtime_kg())
    planner = PlannerAgent(tool_registry=_s6_registry())
    runner = PlanRunner(
        step_runner=_SixStageStepRunner(fail_stage="S3"),
        planner_agent=planner,
    )

    task_id = "int_s6_trigger_matrix_s3_replan"
    _cleanup_task_log(task_id)
    plan, context, record = _build_plan(
        task_id,
        constraints={
            "require_replan_confirm": True,
            "min_candidate_confidence": 0.0,
            "high_cost_min_overall": 0.0,
        },
    )

    try:
        runner.run_plan(plan, context, record=record, finalize_status=False)
    except PlanRunError:
        pass

    assert context.status in {InternalStatus.WAITING_REPLAN, InternalStatus.FAILED}
    if context.status == InternalStatus.WAITING_REPLAN:
        assert record.status == ExternalStatus.WAITING_REPLAN_CONFIRM
        assert context.pending_action is not None
        assert context.pending_action.action_type == PendingActionType.REPLAN_CONFIRM

    failed_s3 = context.step_results["S3"]
    assert failed_s3.metrics.get("s6_recovery_action") == "replan"
    assert failed_s3.metrics.get("s6_trigger_stage_id") == "S3"
    assert failed_s3.metrics.get("s6_trigger_failure_code") == "S3_ALL_CANDIDATES_REJECTED"

    events = read_timeline_events(task_id)
    assert any(
        entry.get("event_type") == "STEP_FAILED"
        and isinstance(entry.get("data"), dict)
        and entry["data"].get("s6", {}).get("action") == "replan"
        for entry in events
    )
