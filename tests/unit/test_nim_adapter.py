from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.adapters.nim_adapter import NIMESMFoldAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


class MockNvidiaNIMClient:
    def call_sync(self, _payload: dict) -> dict:
        return {"pdb": "ATOM 1", "plddt": 90.0}


@pytest.fixture
def context() -> WorkflowContext:
    from src.models.contracts import ProteinDesignTask

    task = ProteinDesignTask(
        task_id="task123",
        goal="test protein design",
        constraints={},
    )
    return WorkflowContext(task=task)


def test_resolve_inputs_literal(context: WorkflowContext) -> None:
    adapter = NIMESMFoldAdapter(client=Mock())
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={"sequence": "ACDEFG"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "ACDEFG"
    assert resolved["task_id"] == "task123"
    assert resolved["step_id"] == "S1"


def test_resolve_inputs_reference(context: WorkflowContext) -> None:
    from src.models.contracts import StepResult

    adapter = NIMESMFoldAdapter(client=Mock())
    context.step_results["S1"] = StepResult(
        task_id="task123",
        step_id="S1",
        tool="protein_mpnn",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"sequence": "MKFLKFSLL"},
        metrics={"exec_type": "python"},
        risk_flags=[],
        logs_path=None,
        timestamp="2024-01-01T00:00:00Z",
    )
    step = PlanStep(
        id="S2",
        tool="esmfold",
        inputs={"sequence": "S1.sequence"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "MKFLKFSLL"


def test_resolve_inputs_missing_sequence(context: WorkflowContext) -> None:
    adapter = NIMESMFoldAdapter(client=Mock())
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={},
        metadata={},
    )

    with pytest.raises(ValueError) as exc_info:
        adapter.resolve_inputs(step, context)

    assert "sequence" in str(exc_info.value).lower()


def test_run_local_success(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.call_sync.return_value = {"pdb": "ATOM 1", "plddt": [80.0, 90.0]}
    adapter = NIMESMFoldAdapter(client=mock_client, output_dir=tmp_path / "pdb")

    outputs, metrics = adapter.run_local(
        {
            "sequence": "ACDEFG",
            "task_id": "task123",
            "step_id": "S1",
        }
    )

    assert Path(outputs["pdb_path"]).exists()
    assert outputs["plddt"] == 85.0
    assert metrics["provider"] == "nvidia_nim"


def test_run_local_missing_sequence() -> None:
    adapter = NIMESMFoldAdapter(client=Mock())
    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local({"task_id": "task123", "step_id": "S1"})

    assert exc_info.value.failure_type == FailureType.NON_RETRYABLE


def test_run_local_missing_pdb() -> None:
    mock_client = Mock()
    mock_client.call_sync.return_value = {"plddt": 90.0}
    adapter = NIMESMFoldAdapter(client=mock_client)

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local({"sequence": "ACDEFG", "task_id": "task123", "step_id": "S1"})

    assert exc_info.value.code == "NIM_INVALID_RESPONSE"


def test_run_local_missing_plddt_uses_bfactor(tmp_path: Path) -> None:
    mock_client = Mock()
    pdb_text = (
        "ATOM      1  N   MET A   1      11.485 -52.270  -9.149  1.00 68.72           N\n"
        "ATOM      2  CA  MET A   1      10.175 -52.100  -8.526  1.00 71.19           C\n"
    )
    mock_client.call_sync.return_value = {"pdbs": [pdb_text]}
    adapter = NIMESMFoldAdapter(client=mock_client, output_dir=tmp_path / "pdb")

    outputs, _metrics = adapter.run_local(
        {"sequence": "ACDEFG", "task_id": "task123", "step_id": "S1"}
    )

    assert outputs["plddt"] == pytest.approx(69.955, rel=1e-3)


@pytest.mark.unit
def test_nim_adapter_with_mock(tmp_path: Path) -> None:
    adapter = NIMESMFoldAdapter(
        client=MockNvidiaNIMClient(),
        output_dir=tmp_path / "pdb",
    )

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFG", "task_id": "task123", "step_id": "S1"}
    )

    assert Path(outputs["pdb_path"]).exists()
    assert metrics["provider"] == "nvidia_nim"
