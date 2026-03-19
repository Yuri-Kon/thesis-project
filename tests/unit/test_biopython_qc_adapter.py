from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.biopython_qc_adapter import BioPythonQCAdapter
from src.models.contracts import PlanStep, ProteinDesignTask
from src.workflow.context import WorkflowContext
from src.workflow.errors import StepRunError


def _write_min_pdb(path: Path, *, bfactor: float = 80.0) -> None:
    path.write_text(
        (
            "ATOM      1  N   MET A   1      11.485 -52.270  -9.149  1.00 "
            f"{bfactor:6.2f}"
            "           N\n"
            "ATOM      2  CA  MET A   1      10.175 -52.100  -8.526  1.00 "
            f"{bfactor:6.2f}"
            "           C\n"
            "END\n"
        ),
        encoding="utf-8",
    )


@pytest.fixture
def context() -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task_qc_001",
        goal="test",
        constraints={"plddt_threshold": 0.7},
    )
    return WorkflowContext(task=task)


def test_resolve_inputs_injects_threshold(context: WorkflowContext) -> None:
    adapter = BioPythonQCAdapter()
    step = PlanStep(
        id="S3",
        tool="biopython_qc",
        inputs={"sequence": "ACDEFGHIK", "pdb_path": "/tmp/test.pdb"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)
    assert resolved["plddt_threshold"] == 0.7
    assert resolved["task_id"] == "task_qc_001"
    assert resolved["step_id"] == "S3"


def test_run_local_single_candidate_pass(tmp_path: Path) -> None:
    pdb_path = tmp_path / "ok.pdb"
    _write_min_pdb(pdb_path, bfactor=85.0)

    adapter = BioPythonQCAdapter()
    outputs, metrics = adapter.run_local(
        {
            "sequence": "ACDEFGHIK",
            "pdb_path": str(pdb_path),
            "plddt": 0.92,
            "plddt_threshold": 0.7,
            "task_id": "task_qc_001",
            "step_id": "S3",
        }
    )

    assert outputs["stage_id"] == "S3"
    assert outputs["pass_count"] == 1
    assert outputs["fail_count"] == 0
    assert outputs["pass_fail"] is True
    assert outputs["quality_gate"]["status"] == "PASS"
    assert metrics["exec_type"] == "python"
    assert metrics["evaluated_candidates"] == 1


def test_run_local_batch_with_invalid_sequence_and_missing_pdb(tmp_path: Path) -> None:
    valid_pdb = tmp_path / "valid.pdb"
    _write_min_pdb(valid_pdb, bfactor=75.0)

    adapter = BioPythonQCAdapter()
    outputs, _metrics = adapter.run_local(
        {
            "structure_results": [
                {
                    "candidate_id": "c1",
                    "sequence": "ACDEFGHIK",
                    "pdb_path": str(valid_pdb),
                    "plddt": 0.8,
                    "tool_id": "nim_esmfold",
                },
                {
                    "candidate_id": "c2",
                    "sequence": "ACDE*GHIK",
                    "pdb_path": "/tmp/not-exist.pdb",
                    "plddt": 0.4,
                    "tool_id": "nim_esmfold",
                },
            ],
            "plddt_threshold": 0.7,
            "task_id": "task_qc_001",
            "step_id": "S3",
        }
    )

    assert outputs["pass_count"] == 1
    assert outputs["fail_count"] == 1
    assert outputs["pass_fail"] is True
    failed = {row["candidate_id"]: row for row in outputs["failed_samples"]}
    assert "c2" in failed
    assert "S3_SEQUENCE_INVALID_CHARS" in failed["c2"]["reject_codes"]
    assert "S3_PDB_NOT_FOUND" in failed["c2"]["reject_codes"]


def test_run_local_raises_when_no_candidates() -> None:
    adapter = BioPythonQCAdapter()
    with pytest.raises(StepRunError):
        adapter.run_local({"task_id": "task_qc_001", "step_id": "S3", "structure_results": []})
