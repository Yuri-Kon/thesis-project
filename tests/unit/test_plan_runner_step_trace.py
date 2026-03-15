from __future__ import annotations

from src.models.contracts import StepResult, now_iso
from src.workflow.plan_runner import _build_step_trace_data


def test_build_step_trace_data_contains_quality_gate_summary() -> None:
    step_result = StepResult(
        task_id="task_trace",
        step_id="S3",
        tool="biopython_qc",
        status="failed",
        failure_type="non_retryable",
        error_message="all rejected",
        error_details={"failure_code": "S3_ALL_CANDIDATES_REJECTED"},
        inputs={},
        outputs={
            "stage_id": "S3",
            "pass_count": 0,
            "fail_count": 2,
            "pass_fail": False,
            "reject_code_counts": {"S3_PLDDT_BELOW_THRESHOLD": 2},
            "failed_samples": [
                {
                    "candidate_id": "cand_1",
                    "reject_codes": ["S3_PLDDT_BELOW_THRESHOLD"],
                    "reason": "plddt too low",
                }
            ],
        },
        artifacts={},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )

    data = _build_step_trace_data(step_result)
    assert data["failure_code"] == "S3_ALL_CANDIDATES_REJECTED"
    assert data["stage_id"] == "S3"
    assert data["quality_gate"]["fail_count"] == 2
    assert data["quality_gate"]["failed_samples"][0]["candidate_id"] == "cand_1"
