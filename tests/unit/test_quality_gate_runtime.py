from __future__ import annotations

from src.workflow.quality_gate import (
    QUALITY_GATE_ALL_REJECTED_CODE,
    QualityGateRejectCode,
    evaluate_quality_gate_batch,
)


def test_quality_gate_boundary_inputs_and_reject_codes_are_stable() -> None:
    candidates = [
        {
            "candidate_id": "source_failed",
            "status": "failed",
            "failure_code": "S2_TOOL_UNAVAILABLE",
            "failure_reason": "upstream timeout",
        },
        {
            "candidate_id": "missing_fields",
            "status": "success",
            "sequence": "",
            "pdb_path": "",
            "plddt": None,
        },
        {
            "candidate_id": "low_complex",
            "status": "success",
            "sequence": "AAAAAAAAAAAAAAAAAAAA",
            "pdb_path": "/tmp/low_complex.pdb",
            "plddt": 0.95,
        },
    ]

    report = evaluate_quality_gate_batch(candidates)
    rows = {row["candidate_id"]: row for row in report["qc_results"]}

    assert rows["source_failed"]["reject_codes"] == [
        QualityGateRejectCode.SOURCE_STRUCTURE_FAILED.value
    ]
    assert rows["missing_fields"]["reject_codes"] == [
        QualityGateRejectCode.PLDDT_MISSING.value,
        QualityGateRejectCode.SEQUENCE_MISSING.value,
        QualityGateRejectCode.STRUCTURE_MISSING.value,
    ]
    assert rows["low_complex"]["reject_codes"] == [
        QualityGateRejectCode.LOW_COMPLEXITY_COMPOSITION.value,
        QualityGateRejectCode.LOW_COMPLEXITY_REPEAT.value,
    ]
    assert report["pass_fail"] is False
    assert report["pass_count"] == 0
    assert report["fail_count"] == 3
    assert QUALITY_GATE_ALL_REJECTED_CODE == "S3_ALL_CANDIDATES_REJECTED"


def test_quality_gate_cross_tool_consistency_for_same_candidate_inputs() -> None:
    candidates = [
        {
            "candidate_id": "nim_row",
            "status": "success",
            "tool_id": "nim_esmfold",
            "sequence": "AAAAABBBBB",
            "pdb_path": "/tmp/nim.pdb",
            "plddt": 0.6,
        },
        {
            "candidate_id": "local_row",
            "status": "success",
            "tool_id": "esmfold",
            "sequence": "AAAAABBBBB",
            "pdb_path": "/tmp/local.pdb",
            "plddt": 0.6,
        },
    ]

    report = evaluate_quality_gate_batch(
        candidates,
        constraints={"min_length": 8, "max_length": 20, "plddt_threshold": 0.8},
    )
    rows = {row["candidate_id"]: row for row in report["qc_results"]}
    nim_codes = rows["nim_row"]["reject_codes"]
    local_codes = rows["local_row"]["reject_codes"]

    assert nim_codes == local_codes
    assert QualityGateRejectCode.PLDDT_BELOW_THRESHOLD.value in nim_codes
    assert QualityGateRejectCode.SEQUENCE_INVALID_CHAR.value in nim_codes
