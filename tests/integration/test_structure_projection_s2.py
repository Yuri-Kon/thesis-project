from __future__ import annotations

from src.agents.executor import ExecutorAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask, StepResult, now_iso
from src.models.db import InternalStatus
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType


def _build_context_with_s1_candidates() -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task_s2_batch",
        goal="de_novo_design",
        constraints={"length_range": [20, 30]},
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="protgpt2",
                inputs={"goal": "de_novo_design"},
                metadata={
                    "stage_id": "S1",
                    "lineage": {
                        "stage_id": "S1",
                        "primary_tool_id": "protgpt2",
                        "fallback_tool_ids": ["seqgen_local"],
                    },
                },
            ),
            PlanStep(
                id="S2",
                tool="nim_esmfold",
                inputs={"sequence": "S1.sequence"},
                metadata={"stage_id": "S2"},
            ),
        ],
        constraints=task.constraints,
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        plan=plan,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.PLANNED,
    )
    context.step_results["S1"] = StepResult(
        task_id=task.task_id,
        step_id="S1",
        tool="protgpt2",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        inputs={},
        outputs={
            "sequence": "ACDEFGHIKLMNPQRSTVWY",
            "candidates": [
                {"sequence": "MKTAYIAKQRQISFVKSHFS", "score": 0.82},
                {"sequence": "INVALID*", "score": 0.10},
            ],
            "lineage": plan.steps[0].metadata.get("lineage"),
        },
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return context


def test_project_structures_from_s1_keeps_partial_success_and_lineage(monkeypatch):
    context = _build_context_with_s1_candidates()
    executor = ExecutorAgent()

    def _fake_run_step(step: PlanStep, _context: WorkflowContext) -> StepResult:
        seq = step.inputs["sequence"]
        if step.tool == "nim_esmfold" and seq == "ACDEFGHIKLMNPQRSTVWY":
            return StepResult(
                task_id=_context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.TOOL_ERROR.value,
                error_message="nim timeout",
                error_details={"failure_code": "NIM_TIMEOUT"},
                inputs=step.inputs,
                outputs={},
                metrics={},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
        if step.tool == "esmfold" and seq == "ACDEFGHIKLMNPQRSTVWY":
            return StepResult(
                task_id=_context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="success",
                failure_type=None,
                error_message=None,
                error_details={},
                inputs=step.inputs,
                outputs={
                    "pdb_path": "/tmp/primary_fb.pdb",
                    "plddt": 0.88,
                    "confidence": {"plddt_mean": 0.88, "level": "high"},
                    "stage_id": "S2",
                },
                metrics={"provider": "nextflow"},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
        return StepResult(
            task_id=_context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            inputs=step.inputs,
            outputs={
                "pdb_path": "/tmp/candidate_ok.pdb",
                "plddt": 0.91,
                "confidence": {"plddt_mean": 0.91, "level": "high"},
                "stage_id": "S2",
            },
            metrics={"provider": "nvidia_nim"},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

    monkeypatch.setattr(executor.step_runner, "run_step", _fake_run_step)

    result = executor.project_structures_from_s1(
        context,
        source_step_id="S1",
        structure_step_id="S2",
        max_candidates=3,
    )

    assert result.status == "success"
    assert result.outputs["stage_id"] == "S2"
    assert result.outputs["success_count"] == 2
    assert result.outputs["failure_count"] == 1
    assert result.outputs["best_candidate_id"] is not None
    rows = result.outputs["structure_results"]
    assert len(rows) == 3
    assert any(row.get("fallback_used") for row in rows if row.get("status") == "success")
    assert any(row.get("failure_code") == "S2_SEQUENCE_INVALID" for row in rows)
    for row in rows:
        assert row["lineage"]["stage_id"] == "S2"
        assert row["lineage"]["source_step_id"] == "S1"


def test_project_structures_from_s1_returns_failed_when_all_candidates_fail(monkeypatch):
    context = _build_context_with_s1_candidates()
    executor = ExecutorAgent()

    def _always_fail(step: PlanStep, _context: WorkflowContext) -> StepResult:
        return StepResult(
            task_id=_context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="failed",
            failure_type=FailureType.TOOL_ERROR.value,
            error_message="projection failed",
            error_details={"failure_code": "NIM_INVALID_RESPONSE"},
            inputs=step.inputs,
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

    monkeypatch.setattr(executor.step_runner, "run_step", _always_fail)

    result = executor.project_structures_from_s1(
        context,
        source_step_id="S1",
        structure_step_id="S2",
        max_candidates=2,
    )

    assert result.status == "failed"
    assert result.error_details["failure_code"] == "S2_ALL_CANDIDATES_FAILED"
    assert result.outputs["success_count"] == 0
