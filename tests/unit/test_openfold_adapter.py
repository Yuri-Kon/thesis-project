from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.adapters.biopython_qc_adapter import BioPythonQCAdapter
from src.adapters.openfold_adapter import OpenFold3Adapter
from src.engines.remote_model_service import JobStatus
from src.models.contracts import PlanStep, ProteinDesignTask
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def context() -> WorkflowContext:
    task = ProteinDesignTask(task_id="task_openfold_001", goal="test", constraints={})
    return WorkflowContext(task=task)


def test_resolve_inputs_literal(context: WorkflowContext) -> None:
    adapter = OpenFold3Adapter(nim_client=Mock(api_key="token"))
    step = PlanStep(id="S1", tool="openfold", inputs={"sequence": "ACDEFG"}, metadata={})

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "ACDEFG"
    assert resolved["task_id"] == "task_openfold_001"
    assert resolved["step_id"] == "S1"


def test_run_local_nim_success(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.api_key = "token"
    mock_client.call_sync.return_value = {"pdb": "ATOM 1", "plddt": 77.0}
    adapter = OpenFold3Adapter(
        execution_mode="nvidia_nim",
        nim_client=mock_client,
        output_dir=tmp_path,
    )

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFGHIK", "task_id": "task_openfold_001", "step_id": "S1"}
    )

    assert Path(outputs["pdb_path"]).exists()
    assert outputs["plddt"] == 77.0
    assert outputs["stage_id"] == "S2"
    assert outputs["sequence"] == "ACDEFGHIK"
    assert metrics["provider"] == "nvidia_nim"
    assert metrics["model_id"] == "openfold/openfold3/predict"
    submit_payload = mock_client.call_sync.call_args.args[0]
    molecule = submit_payload["inputs"][0]["molecules"][0]
    assert "msa" in molecule
    assert molecule["msa"]["main"]["a3m"]["alignment"].startswith(">query\nACDEFGHIK")


def test_run_local_nim_success_with_openfold3_outputs_list_format(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.api_key = "token"
    mock_client.call_sync.return_value = {
        "request_id": "rq_001",
        "outputs": [
            {
                "input_id": "rq_001",
                "structures_with_scores": [
                    {
                        "structure": "ATOM      1  CA  ALA A   1       1.000   0.000   0.000  1.00 77.20           C\nEND\n",
                        "scores": {"plddt": 77.2},
                    }
                ],
            }
        ],
    }
    adapter = OpenFold3Adapter(
        execution_mode="nvidia_nim",
        nim_client=mock_client,
        output_dir=tmp_path,
    )

    outputs, metrics = adapter.run_local(
        {
            "inputs": [
                {
                    "input_id": "rq_001",
                    "molecules": [
                        {
                            "type": "protein",
                            "id": "A",
                            "sequence": "ACDEFGHIK",
                        }
                    ],
                    "output_format": "pdb",
                }
            ],
            "task_id": "task_openfold_001",
            "step_id": "S1",
        }
    )

    assert Path(outputs["pdb_path"]).exists()
    assert outputs["plddt"] == 77.2
    assert outputs["stage_id"] == "S2"
    assert outputs["sequence"] == "ACDEFGHIK"
    assert metrics["provider"] == "nvidia_nim"
    submit_payload = mock_client.call_sync.call_args.args[0]
    molecule = submit_payload["inputs"][0]["molecules"][0]
    assert "msa" in molecule


def test_run_local_nim_sequence_too_long_raises() -> None:
    mock_client = Mock()
    mock_client.api_key = "token"
    adapter = OpenFold3Adapter(execution_mode="nvidia_nim", nim_client=mock_client)
    sequence = "M" * (adapter.max_sequence_length + 1)

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local({"sequence": sequence, "task_id": "t", "step_id": "S1"})

    assert exc_info.value.code == "NIM_INVALID_INPUT"


def test_run_local_rest_success(tmp_path: Path) -> None:
    mock_service = Mock()
    mock_service.submit_job.return_value = "job_123"
    mock_service.wait_for_completion.return_value = JobStatus.COMPLETED
    pdb_path = tmp_path / "prediction.pdb"
    pdb_path.write_text("ATOM 1", encoding="utf-8")
    mock_service.download_results.return_value = {
        "pdb_path": str(pdb_path),
        "plddt": 81.5,
        "metrics": {"plddt_mean": 81.5},
    }
    adapter = OpenFold3Adapter(
        execution_mode="openfold3_rest",
        service=mock_service,
        output_dir=tmp_path,
    )

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFG", "task_id": "task_openfold_001", "step_id": "S1"}
    )

    assert outputs["plddt"] == 81.5
    assert outputs["stage_id"] == "S2"
    assert outputs["sequence"] == "ACDEFG"
    assert metrics["provider"] == "openfold3_rest"
    assert metrics["job_id"] == "job_123"


def test_openfold_output_can_flow_to_qc_with_minimal_processing(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.api_key = "token"
    mock_client.call_sync.return_value = {"pdb": "ATOM      1  CA  ALA A   1       1.000   0.000   0.000  1.00 77.00           C\nEND\n", "plddt": 77.0}
    adapter = OpenFold3Adapter(
        execution_mode="nvidia_nim",
        nim_client=mock_client,
        output_dir=tmp_path,
    )

    openfold_outputs, _ = adapter.run_local(
        {"sequence": "ACDEFGHIK", "task_id": "task_openfold_001", "step_id": "S2"}
    )

    qc_adapter = BioPythonQCAdapter()
    qc_outputs, _ = qc_adapter.run_local(
        {
            "sequence": openfold_outputs["sequence"],
            "pdb_path": openfold_outputs["pdb_path"],
            "plddt": openfold_outputs["plddt"],
            "plddt_threshold": 0.5,
            "task_id": "task_openfold_001",
            "step_id": "S3",
        }
    )

    assert qc_outputs["stage_id"] == "S3"
    assert qc_outputs["pass_fail"] is True
    assert qc_outputs["pass_count"] == 1


def test_run_local_rest_passes_query_format_to_remote_service(tmp_path: Path) -> None:
    mock_service = Mock()
    mock_service.submit_job.return_value = "job_124"
    mock_service.wait_for_completion.return_value = JobStatus.COMPLETED
    pdb_path = tmp_path / "prediction.pdb"
    pdb_path.write_text("ATOM 1", encoding="utf-8")
    mock_service.download_results.return_value = {
        "pdb_path": str(pdb_path),
        "plddt": 82.0,
        "metrics": {"plddt_mean": 82.0},
    }
    adapter = OpenFold3Adapter(
        execution_mode="openfold3_rest",
        service=mock_service,
        output_dir=tmp_path,
    )

    adapter.run_local(
        {
            "sequence": "ACDEFG",
            "query_format": "queries",
            "task_id": "task_openfold_001",
            "step_id": "S1",
        }
    )

    submit_kwargs = mock_service.submit_job.call_args.kwargs
    assert submit_kwargs["payload"]["query_format"] == "queries"


def test_run_local_rest_job_failed_raises() -> None:
    mock_service = Mock()
    mock_service.submit_job.return_value = "job_123"
    mock_service.wait_for_completion.return_value = JobStatus.FAILED
    adapter = OpenFold3Adapter(
        execution_mode="openfold3_rest",
        service=mock_service,
    )

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local({"sequence": "ACDEFG", "task_id": "t", "step_id": "S1"})

    assert exc_info.value.failure_type == FailureType.TOOL_ERROR
    assert exc_info.value.code == "REMOTE_JOB_FAILED"


def test_run_local_auto_picks_rest_when_base_url_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    mock_service = Mock()
    mock_service.submit_job.return_value = "job_321"
    mock_service.wait_for_completion.return_value = JobStatus.COMPLETED
    pdb_path = tmp_path / "prediction.pdb"
    pdb_path.write_text("ATOM 1", encoding="utf-8")
    mock_service.download_results.return_value = {
        "pdb_path": str(pdb_path),
        "plddt": 70.0,
        "metrics": {"plddt_mean": 70.0},
    }
    adapter = OpenFold3Adapter(
        execution_mode="auto",
        nim_client=Mock(api_key=""),
        service=mock_service,
        base_url="http://localhost:8200",
        output_dir=tmp_path,
    )

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFG", "task_id": "task_openfold_001", "step_id": "S1"}
    )

    assert outputs["plddt"] == 70.0
    assert metrics["provider"] == "openfold3_rest"
