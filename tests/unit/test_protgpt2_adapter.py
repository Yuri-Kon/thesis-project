from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.adapters.protgpt2_adapter import ProtGPT2Adapter
from src.engines.remote_model_service import JobStatus
from src.models.contracts import PlanStep, ProteinDesignTask, StepResult
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def mock_service() -> Mock:
    service = Mock()
    service.submit_job.return_value = "plm_job_123"
    service.wait_for_completion.return_value = JobStatus.COMPLETED
    service.download_results.return_value = {
        "sequence": "ACDEFGHIK",
        "candidates": [
            {"sequence": "ACDEFGHIK", "score": -0.1},
            {"sequence": "ACDEFGHIM", "score": -0.2},
        ],
        "artifacts": ["/tmp/candidates.fasta", "/tmp/summary.json"],
    }
    return service


@pytest.fixture
def context() -> WorkflowContext:
    task = ProteinDesignTask(
        task_id="task_plm_001",
        goal="de_novo_design",
        constraints={"length_range": [30, 40]},
    )
    return WorkflowContext(task=task)


def test_resolve_inputs_includes_defaults(
    mock_service: Mock,
    context: WorkflowContext,
) -> None:
    adapter = ProtGPT2Adapter(service=mock_service)
    step = PlanStep(
        id="S1",
        tool="protgpt2",
        inputs={},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["goal"] == "de_novo_design"
    assert resolved["length_range"] == [30, 40]
    assert resolved["task_id"] == "task_plm_001"
    assert resolved["step_id"] == "S1"


def test_resolve_inputs_reference_syntax(
    mock_service: Mock,
    context: WorkflowContext,
) -> None:
    adapter = ProtGPT2Adapter(service=mock_service)
    context.step_results["S1"] = StepResult(
        task_id="task_plm_001",
        step_id="S1",
        tool="dummy",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"prompt": "<|endoftext|>ACD"},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    step = PlanStep(
        id="S2",
        tool="protgpt2",
        inputs={"prompt": "S1.prompt", "goal": "de_novo_design"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)
    assert resolved["prompt"] == "<|endoftext|>ACD"


def test_run_remote_success_normalizes_outputs(mock_service: Mock) -> None:
    adapter = ProtGPT2Adapter(service=mock_service)
    outputs, metrics = adapter.run_remote(
        {
            "goal": "de_novo_design",
            "length_range": [50, 60],
            "num_candidates": 2,
            "task_id": "task_plm_001",
            "step_id": "S1",
        }
    )

    mock_service.submit_job.assert_called_once_with(
        payload={
            "goal": "de_novo_design",
            "length_range": [50, 60],
            "num_candidates": 2,
            "num_return_sequences": 2,
        },
        task_id="task_plm_001",
        step_id="S1",
    )
    mock_service.wait_for_completion.assert_called_once_with("plm_job_123")
    mock_service.download_results.assert_called_once()

    assert outputs["sequence"] == "ACDEFGHIK"
    assert len(outputs["candidates"]) == 2
    assert outputs["artifacts"]["files"] == [
        "/tmp/candidates.fasta",
        "/tmp/summary.json",
    ]
    assert metrics["exec_type"] == "remote"
    assert metrics["provider"] == "plm_rest"
    assert metrics["job_id"] == "plm_job_123"


def test_run_remote_fails_when_sequence_missing(mock_service: Mock) -> None:
    mock_service.download_results.return_value = {"candidates": [], "artifacts": []}
    adapter = ProtGPT2Adapter(service=mock_service)

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_remote(
            {
                "goal": "de_novo_design",
                "task_id": "task_plm_001",
                "step_id": "S1",
            }
        )

    assert exc_info.value.failure_type == FailureType.TOOL_ERROR
    assert "missing 'sequence'" in str(exc_info.value)


def test_run_remote_job_failed(mock_service: Mock) -> None:
    mock_service.wait_for_completion.return_value = JobStatus.FAILED
    adapter = ProtGPT2Adapter(service=mock_service)

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_remote(
            {
                "goal": "de_novo_design",
                "task_id": "task_plm_001",
                "step_id": "S1",
            }
        )

    assert exc_info.value.failure_type == FailureType.TOOL_ERROR
    assert "failed" in str(exc_info.value)
