from __future__ import annotations

from src.agents import executor as executor_module
from src.agents.executor import ExecutorAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask, StepResult, now_iso
from src.models.db import InternalStatus
from src.workflow.context import WorkflowContext
from src.workflow.quality_gate import QUALITY_GATE_ALL_REJECTED_CODE


def _build_context_with_s2_results() -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task_s3_gate",
        goal="de_novo_design",
        constraints={
            "length_range": [20, 30],
            "plddt_threshold": 0.7,
            "quality_gate": {
                "max_residue_fraction": 0.75,
                "max_repeat_run": 7,
            },
        },
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(id="S1", tool="protgpt2", inputs={}, metadata={"stage_id": "S1"}),
            PlanStep(id="S2", tool="nim_esmfold", inputs={}, metadata={"stage_id": "S2"}),
            PlanStep(
                id="S3",
                tool="biopython_qc",
                inputs={"structure_results": "S2.structure_results"},
                metadata={"stage_id": "S3"},
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
                    "candidate_id": "cand_pass",
                    "status": "success",
                    "sequence": "ACDEFGHIKLMNPQRSTVWY",
                    "pdb_path": "/tmp/pass.pdb",
                    "plddt": 0.86,
                    "tool_id": "esmfold",
                    "lineage": {"stage_id": "S2", "source_candidate_id": "S1_primary"},
                },
                {
                    "candidate_id": "cand_invalid_seq",
                    "status": "success",
                    "sequence": "ACDEFGHIKLMNPQRSTV*Y",
                    "pdb_path": "/tmp/invalid_seq.pdb",
                    "plddt": 0.93,
                    "tool_id": "nim_esmfold",
                    "lineage": {"stage_id": "S2", "source_candidate_id": "S1_bad"},
                },
                {
                    "candidate_id": "cand_s2_failed",
                    "status": "failed",
                    "sequence": "MKTAYIAKQRQISFVKSHFS",
                    "failure_code": "S2_TOOL_UNAVAILABLE",
                    "failure_reason": "upstream failed",
                    "tool_id": "nim_esmfold",
                    "lineage": {"stage_id": "S2", "source_candidate_id": "S1_timeout"},
                },
            ],
        },
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return context


def test_quality_gate_from_s2_keeps_failed_samples_and_emits_trace(monkeypatch):
    context = _build_context_with_s2_results()
    executor = ExecutorAgent()
    events: list[dict] = []

    monkeypatch.setattr(
        executor_module,
        "append_event",
        lambda _task_id, payload: events.append(payload),
    )

    result = executor.quality_gate_from_s2(
        context,
        source_step_id="S2",
        quality_step_id="S3",
        max_candidates=3,
    )

    assert result.status == "success"
    assert result.outputs["stage_id"] == "S3"
    assert result.outputs["pass_count"] == 1
    assert result.outputs["fail_count"] == 2
    assert result.outputs["pass_fail"] is True
    assert len(result.outputs["failed_samples"]) == 2
    assert result.outputs["quality_gate"]["status"] == "PASS"
    assert result.metrics["requirement2"]["capability_id"] == "quality_qc"
    assert result.metrics["requirement2"]["io_type"] == "sequence_structure_to_qc_metrics"
    assert result.outputs["best_candidate_id"] == "cand_pass"

    assert len(events) == 1
    assert events[0]["event"] == "STEP_FINISHED"
    assert events[0]["data"]["stage_id"] == "S3"
    assert events[0]["data"]["quality_gate"]["fail_count"] == 2


def test_quality_gate_from_s2_fails_when_all_candidates_rejected(monkeypatch):
    context = _build_context_with_s2_results()
    s2_result = context.step_results["S2"]
    s2_result.outputs["structure_results"] = [
        {
            "candidate_id": "cand_1",
            "status": "failed",
            "failure_code": "S2_OUTPUT_INVALID",
            "failure_reason": "missing pdb",
            "sequence": "AAAAAAAAAAAAAAAAAAAA",
        },
        {
            "candidate_id": "cand_2",
            "status": "success",
            "sequence": "AAAAAAAAAAAAAAAAAAAA",
            "pdb_path": "/tmp/aa.pdb",
            "plddt": 0.2,
        },
    ]
    executor = ExecutorAgent()
    events: list[dict] = []
    monkeypatch.setattr(
        executor_module,
        "append_event",
        lambda _task_id, payload: events.append(payload),
    )

    result = executor.quality_gate_from_s2(
        context,
        source_step_id="S2",
        quality_step_id="S3",
        max_candidates=2,
    )

    assert result.status == "failed"
    assert result.error_details["failure_code"] == QUALITY_GATE_ALL_REJECTED_CODE
    assert result.outputs["pass_count"] == 0
    assert result.outputs["quality_gate"]["status"] == "BLOCK"
    assert events[0]["event"] == "STEP_FAILED"
