"""
ProteinMPNNAdapter unit tests.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.protein_mpnn_adapter import ProteinMPNNAdapter
from src.models.contracts import PlanStep, ProteinDesignTask, StepResult
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def adapter(tmp_path: Path) -> ProteinMPNNAdapter:
    return ProteinMPNNAdapter(artifacts_dir=tmp_path, execution_mode="python")


@pytest.fixture
def context() -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task123",
        goal="test protein design",
        constraints={"length_range": [8, 12]},
    )
    return WorkflowContext(task=task)


def test_resolve_inputs_literal_values(
    adapter: ProteinMPNNAdapter, context: WorkflowContext
) -> None:
    step = PlanStep(
        id="S1",
        tool="protein_mpnn",
        inputs={"pdb_path": "/tmp/template.pdb", "length_range": [10, 12]},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["pdb_path"] == "/tmp/template.pdb"
    assert resolved["length_range"] == [10, 12]
    assert resolved["goal"] == "test protein design"
    assert resolved["task_id"] == "task123"
    assert resolved["step_id"] == "S1"


def test_resolve_inputs_reference_syntax(
    adapter: ProteinMPNNAdapter, context: WorkflowContext
) -> None:
    context.step_results["S1"] = StepResult(
        task_id="task123",
        step_id="S1",
        tool="esmfold",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"pdb_path": "/tmp/generated.pdb"},
        metrics={"exec_type": "nextflow"},
        risk_flags=[],
        logs_path=None,
        timestamp="2024-01-01T00:00:00Z",
    )
    step = PlanStep(
        id="S2",
        tool="protein_mpnn",
        inputs={"pdb_path": "S1.pdb_path"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["pdb_path"] == "/tmp/generated.pdb"
    assert resolved["length_range"] == [8, 12]


def test_resolve_inputs_missing_pdb_raises(adapter: ProteinMPNNAdapter, context: WorkflowContext) -> None:
    step = PlanStep(
        id="S1",
        tool="protein_mpnn",
        inputs={"length_range": [10, 12]},
        metadata={},
    )

    with pytest.raises(ValueError) as exc_info:
        adapter.resolve_inputs(step, context)

    assert "pdb_path" in str(exc_info.value)


def test_run_local_generates_candidates(adapter: ProteinMPNNAdapter) -> None:
    inputs = {
        "pdb_path": "/tmp/template.pdb",
        "length_range": [6, 8],
        "num_candidates": 3,
        "task_id": "task123",
        "step_id": "S1",
    }

    outputs, metrics = adapter.run_local(inputs)

    assert metrics["exec_type"] == "python"
    assert len(outputs["candidates"]) == 3
    assert 6 <= len(outputs["sequence"]) <= 8
    assert outputs["sequence_score"] is not None
    assert "artifacts" in outputs
    artifacts_path = Path(outputs["artifacts"]["candidates_path"])
    assert artifacts_path.exists()


def test_run_local_missing_pdb_raises(adapter: ProteinMPNNAdapter) -> None:
    inputs = {
        "length_range": [6, 8],
        "task_id": "task123",
        "step_id": "S1",
    }

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local(inputs)

    error = exc_info.value
    assert error.failure_type == FailureType.NON_RETRYABLE
    assert "pdb_path" in str(error).lower()
