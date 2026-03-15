from __future__ import annotations

import json
from pathlib import Path

from src.agents import executor as executor_module
from src.agents.executor import ExecutorAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask, StepResult, now_iso
from src.models.db import InternalStatus
from src.workflow import recovery as recovery_module
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType


def _build_context_with_s3_passed(
    *,
    max_iterations: int = 3,
    convergence_delta: float = 0.01,
    max_degradation_rounds: int = 1,
) -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task_s4_loop",
        goal="de_novo_design",
        constraints={
            "length_range": [20, 30],
            "plddt_threshold": 0.7,
            "structure_refinement": {
                "max_iterations": max_iterations,
                "convergence_delta": convergence_delta,
                "max_degradation_rounds": max_degradation_rounds,
            },
        },
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S2", tool="nim_esmfold", inputs={"sequence": "S1.sequence"}, metadata={"stage_id": "S2"}),
            PlanStep(id="S3", tool="biopython_qc", inputs={"structure_results": "S2.structure_results"}, metadata={"stage_id": "S3"}),
            PlanStep(id="S4", tool="protein_mpnn", inputs={"pdb_path": "S2.pdb_path"}, metadata={"stage_id": "S4"}),
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
        status=InternalStatus.RUNNING,
    )
    context.step_results["S3"] = StepResult(
        task_id=task.task_id,
        step_id="S3",
        tool="biopython_qc",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        inputs={},
        outputs={
            "stage_id": "S3",
            "pass_fail": True,
            "pass_count": 1,
            "fail_count": 0,
            "passed_samples": [
                {
                    "candidate_id": "s3_base",
                    "sequence": "ACDEFGHIKLMNPQRSTVWY",
                    "pdb_path": "/tmp/base.pdb",
                    "plddt": 0.8,
                    "lineage": {"stage_id": "S3", "source_candidate_id": "s2_base"},
                }
            ],
        },
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return context


def _build_context_with_s2_only() -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task_s4_s2_fallback",
        goal="de_novo_design",
        constraints={
            "length_range": [20, 30],
            "plddt_threshold": 0.7,
            "structure_refinement": {
                "max_iterations": 1,
                "convergence_delta": 0.01,
                "max_degradation_rounds": 1,
            },
        },
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S2", tool="nim_esmfold", inputs={"sequence": "S1.sequence"}, metadata={"stage_id": "S2"}),
            PlanStep(id="S4", tool="protein_mpnn", inputs={"pdb_path": "S2.pdb_path"}, metadata={"stage_id": "S4"}),
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
        status=InternalStatus.RUNNING,
    )
    context.step_results["S2"] = StepResult(
        task_id=task.task_id,
        step_id="S2",
        tool="nim_esmfold",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        inputs={},
        outputs={
            "stage_id": "S2",
            "structure_results": [
                {
                    "candidate_id": "s2_base",
                    "status": "success",
                    "sequence": "ACDEFGHIKLMNPQRSTVWY",
                    "pdb_path": "/tmp/s2_base.pdb",
                    "plddt": 0.82,
                    "tool_id": "nim_esmfold",
                    "lineage": {"stage_id": "S2", "source_candidate_id": "s1_base"},
                }
            ],
        },
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return context


def _mock_success_result(
    *,
    task_id: str,
    step: PlanStep,
    outputs: dict,
) -> StepResult:
    return StepResult(
        task_id=task_id,
        step_id=step.id,
        tool=step.tool,
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        inputs=step.inputs,
        outputs=outputs,
        metrics={"exec_type": "mock"},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )


def _mock_failed_result(
    *,
    task_id: str,
    step: PlanStep,
    code: str,
    message: str,
) -> StepResult:
    return StepResult(
        task_id=task_id,
        step_id=step.id,
        tool=step.tool,
        status="failed",
        failure_type=FailureType.TOOL_ERROR.value,
        error_message=message,
        error_details={"failure_code": code},
        inputs=step.inputs,
        outputs={},
        metrics={"exec_type": "mock"},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )


def _patch_audit_to_tmp(monkeypatch, tmp_path: Path) -> None:
    def _persist(*, task_id: str, step_id: str, audit_payload: dict):
        return recovery_module.persist_structure_refinement_audit(
            task_id=task_id,
            step_id=step_id,
            audit_payload=audit_payload,
            artifacts_dir=tmp_path,
        )

    monkeypatch.setattr(executor_module, "persist_structure_refinement_audit", _persist)


def test_refine_sequences_from_s3_runs_multi_round_until_converged(monkeypatch, tmp_path: Path):
    context = _build_context_with_s3_passed(max_iterations=3, convergence_delta=0.02)
    executor = ExecutorAgent()
    events: list[dict] = []
    _patch_audit_to_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(
        executor_module,
        "append_event",
        lambda _task_id, payload: events.append(payload),
    )

    plddt_by_sequence = {
        "MKTAYIAKQRQISFVKSHFS": 0.9,
        "MTEEEREAARRARERVERAAREAE": 0.905,
    }

    def _fake_run_step(step: PlanStep, _context: WorkflowContext) -> StepResult:
        if step.tool == "protein_mpnn":
            iteration = int(step.inputs["iteration"])
            if iteration == 1:
                sequence = "MKTAYIAKQRQISFVKSHFS"
            else:
                sequence = "MTEEEREAARRARERVERAAREAE"
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S4",
                    "sequence": sequence,
                    "sequence_score": 0.9,
                    "candidates": [{"sequence": sequence, "score": 0.9}],
                },
            )
        if step.tool in {"nim_esmfold", "esmfold"}:
            sequence = step.inputs["sequence"]
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S2",
                    "sequence": sequence,
                    "pdb_path": f"/tmp/{sequence}.pdb",
                    "plddt": plddt_by_sequence[sequence],
                },
            )
        raise AssertionError(f"unexpected tool: {step.tool}")

    monkeypatch.setattr(executor.step_runner, "run_step", _fake_run_step)
    result = executor.refine_sequences_from_s3(context)

    assert result.status == "success"
    assert result.outputs["stage_id"] == "S4"
    assert result.outputs["iteration_count"] == 2
    assert result.outputs["successful_iterations"] == 2
    assert result.outputs["stop_reason"] == "converged"
    assert result.outputs["gain_metrics"]["delta_vs_baseline"] == 0.105
    assert events and events[0]["data"]["stop_reason"] == "converged"

    audit_path = Path(result.artifacts["refinement_audit_path"])
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit_payload["summary"]["iteration_count"] == 2
    assert audit_payload["summary"]["stop_reason"] == "converged"


def test_refine_sequences_from_s3_stops_on_degradation(monkeypatch, tmp_path: Path):
    context = _build_context_with_s3_passed(
        max_iterations=3,
        convergence_delta=0.001,
        max_degradation_rounds=0,
    )
    executor = ExecutorAgent()
    _patch_audit_to_tmp(monkeypatch, tmp_path)

    plddt_by_sequence = {
        "ACDEFGHIKLMNPQRSTVWY": 0.86,
        "MKTAYIAKQRQISFVKSHFS": 0.78,
    }

    def _fake_run_step(step: PlanStep, _context: WorkflowContext) -> StepResult:
        if step.tool == "protein_mpnn":
            iteration = int(step.inputs["iteration"])
            sequence = (
                "ACDEFGHIKLMNPQRSTVWY"
                if iteration == 1
                else "MKTAYIAKQRQISFVKSHFS"
            )
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S4",
                    "sequence": sequence,
                    "sequence_score": 0.8,
                    "candidates": [{"sequence": sequence, "score": 0.8}],
                },
            )
        if step.tool in {"nim_esmfold", "esmfold"}:
            sequence = step.inputs["sequence"]
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S2",
                    "sequence": sequence,
                    "pdb_path": f"/tmp/{sequence}.pdb",
                    "plddt": plddt_by_sequence[sequence],
                },
            )
        raise AssertionError(f"unexpected tool: {step.tool}")

    monkeypatch.setattr(executor.step_runner, "run_step", _fake_run_step)
    result = executor.refine_sequences_from_s3(context)

    assert result.status == "success"
    assert result.outputs["stop_reason"] == "degradation_limit"
    assert result.outputs["lineage"]["rollback_applied"] is True
    assert result.outputs["plddt"] == 0.86
    assert result.outputs["iteration_count"] == 2


def test_refine_sequences_from_s3_rolls_back_after_refinement_failure(monkeypatch, tmp_path: Path):
    context = _build_context_with_s3_passed(max_iterations=3, convergence_delta=0.001)
    executor = ExecutorAgent()
    _patch_audit_to_tmp(monkeypatch, tmp_path)

    def _fake_run_step(step: PlanStep, _context: WorkflowContext) -> StepResult:
        if step.tool == "protein_mpnn":
            iteration = int(step.inputs["iteration"])
            if iteration == 1:
                return _mock_success_result(
                    task_id=_context.task.task_id,
                    step=step,
                    outputs={
                        "stage_id": "S4",
                        "sequence": "MKTAYIAKQRQISFVKSHFS",
                        "sequence_score": 0.9,
                        "candidates": [{"sequence": "MKTAYIAKQRQISFVKSHFS", "score": 0.9}],
                    },
                )
            return _mock_failed_result(
                task_id=_context.task.task_id,
                step=step,
                code="PROTEIN_MPNN_RUNTIME_ERROR",
                message="mpnn service unavailable",
            )
        if step.tool in {"nim_esmfold", "esmfold"}:
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S2",
                    "sequence": step.inputs["sequence"],
                    "pdb_path": "/tmp/refined_ok.pdb",
                    "plddt": 0.88,
                },
            )
        raise AssertionError(f"unexpected tool: {step.tool}")

    monkeypatch.setattr(executor.step_runner, "run_step", _fake_run_step)
    result = executor.refine_sequences_from_s3(context)

    assert result.status == "success"
    assert result.outputs["stop_reason"] == "refinement_failed"
    assert result.outputs["successful_iterations"] == 1
    assert result.outputs["lineage"]["rollback_applied"] is True
    assert result.outputs["plddt"] == 0.88

    audit_path = Path(result.artifacts["refinement_audit_path"])
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["summary"]["rollback_applied"] is True


def test_refine_sequences_from_s3_falls_back_to_s2_when_s3_missing(monkeypatch, tmp_path: Path):
    context = _build_context_with_s2_only()
    executor = ExecutorAgent()
    _patch_audit_to_tmp(monkeypatch, tmp_path)

    def _fake_run_step(step: PlanStep, _context: WorkflowContext) -> StepResult:
        if step.tool == "protein_mpnn":
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S4",
                    "sequence": "MKTAYIAKQRQISFVKSHFS",
                    "sequence_score": 0.9,
                    "candidates": [{"sequence": "MKTAYIAKQRQISFVKSHFS", "score": 0.9}],
                },
            )
        if step.tool in {"nim_esmfold", "esmfold"}:
            return _mock_success_result(
                task_id=_context.task.task_id,
                step=step,
                outputs={
                    "stage_id": "S2",
                    "sequence": step.inputs["sequence"],
                    "pdb_path": "/tmp/s4_refined.pdb",
                    "plddt": 0.9,
                },
            )
        raise AssertionError(f"unexpected tool: {step.tool}")

    monkeypatch.setattr(executor.step_runner, "run_step", _fake_run_step)
    result = executor.refine_sequences_from_s3(context)

    assert result.status == "success"
    assert result.outputs["source_step_id"] == "S2"
    assert result.outputs["successful_iterations"] == 1
    assert result.outputs["plddt"] == 0.9
