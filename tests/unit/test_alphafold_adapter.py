from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.adapters.alphafold_adapter import AlphaFold2Adapter
from src.models.contracts import PlanStep, ProteinDesignTask, StepResult
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def context() -> WorkflowContext:
    task = ProteinDesignTask(task_id="task_af2_001", goal="test", constraints={})
    return WorkflowContext(task=task)


def test_resolve_inputs_literal(context: WorkflowContext) -> None:
    adapter = AlphaFold2Adapter(client=Mock())
    step = PlanStep(id="S1", tool="alphafold", inputs={"sequence": "ACDEFG"}, metadata={})

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "ACDEFG"
    assert resolved["task_id"] == "task_af2_001"
    assert resolved["step_id"] == "S1"


def test_resolve_inputs_reference(context: WorkflowContext) -> None:
    adapter = AlphaFold2Adapter(client=Mock())
    context.step_results["S1"] = StepResult(
        task_id="task_af2_001",
        step_id="S1",
        tool="protgpt2",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"sequence": "MKFLKFSLL"},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp="2026-03-16T00:00:00+00:00",
    )
    step = PlanStep(id="S2", tool="alphafold", inputs={"sequence": "S1.sequence"}, metadata={})

    resolved = adapter.resolve_inputs(step, context)
    assert resolved["sequence"] == "MKFLKFSLL"


def test_run_local_success(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.call_sync.return_value = {"pdb": "ATOM 1", "plddt": [80.0, 90.0]}
    adapter = AlphaFold2Adapter(client=mock_client, output_dir=tmp_path)

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFGHIK", "task_id": "task_af2_001", "step_id": "S1"}
    )

    assert Path(outputs["pdb_path"]).exists()
    assert outputs["plddt"] == 85.0
    assert outputs["stage_id"] == "S2"
    assert metrics["provider"] == "nvidia_nim"
    assert metrics["model_id"] == "deepmind/alphafold2"


def test_run_local_missing_sequence_raises() -> None:
    adapter = AlphaFold2Adapter(client=Mock())
    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local({"task_id": "task_af2_001", "step_id": "S1"})
    assert exc_info.value.failure_type == FailureType.NON_RETRYABLE


def test_run_local_sequence_too_long_raises() -> None:
    adapter = AlphaFold2Adapter(client=Mock())
    sequence = "M" * (adapter.max_sequence_length + 1)

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local({"sequence": sequence, "task_id": "task_af2_001", "step_id": "S1"})

    assert exc_info.value.code == "NIM_INVALID_INPUT"


def test_run_local_infers_plddt_from_bfactor(tmp_path: Path) -> None:
    mock_client = Mock()
    pdb_text = (
        "ATOM      1  N   MET A   1      11.485 -52.270  -9.149  1.00 68.72           N\n"
        "ATOM      2  CA  MET A   1      10.175 -52.100  -8.526  1.00 71.19           C\n"
    )
    mock_client.call_sync.return_value = {"pdb": pdb_text}
    adapter = AlphaFold2Adapter(client=mock_client, output_dir=tmp_path)

    outputs, _metrics = adapter.run_local(
        {"sequence": "ACDEFG", "task_id": "task_af2_001", "step_id": "S1"}
    )

    assert outputs["plddt"] == pytest.approx(69.955, rel=1e-3)
