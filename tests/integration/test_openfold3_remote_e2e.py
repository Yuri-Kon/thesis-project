"""
OpenFold3 remote REST end-to-end integration tests.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pytest

from src.adapters.openfold_adapter import OpenFold3Adapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.engines.remote_model_service import JobStatus, RESTModelInvocationService
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.models.db import InternalStatus
from src.workflow.context import WorkflowContext


def _resolve_base_url() -> str:
    return (
        os.getenv("OPENFOLD3_E2E_BASE_URL")
        or os.getenv("OPENFOLD3_REST_BASE_URL")
        or "http://localhost:8200"
    ).rstrip("/")


def _resolve_headers() -> Optional[Dict[str, str]]:
    token = (
        os.getenv("OPENFOLD3_E2E_API_TOKEN")
        or os.getenv("OPENFOLD3_REST_API_TOKEN")
        or ""
    ).strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _resolve_sequence() -> str:
    sequence = str(
        os.getenv("OPENFOLD3_E2E_SEQUENCE", "ACDEFGHIKLMNPQRSTVWY")
    ).strip()
    return sequence or "ACDEFGHIKLMNPQRSTVWY"


def _resolve_poll_interval() -> float:
    try:
        value = float(os.getenv("OPENFOLD3_E2E_POLL_INTERVAL", "2.0"))
    except ValueError:
        value = 2.0
    return max(0.5, value)


def _resolve_max_poll_attempts(poll_interval: float) -> int:
    try:
        max_wait = float(os.getenv("OPENFOLD3_E2E_MAX_WAIT_SECONDS", "300"))
    except ValueError:
        max_wait = 300.0
    max_wait = max(poll_interval, max_wait)
    return max(1, int(max_wait / poll_interval))


def _snapshot_registry() -> tuple[dict, dict]:
    tool_snapshot = ADAPTER_REGISTRY._by_tool_id.copy()
    adapter_snapshot = ADAPTER_REGISTRY._by_adapter_id.copy()
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
    return tool_snapshot, adapter_snapshot


def _restore_registry(snapshot: tuple[dict, dict]) -> None:
    tool_snapshot, adapter_snapshot = snapshot
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_tool_id.update(tool_snapshot)
    ADAPTER_REGISTRY._by_adapter_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.update(adapter_snapshot)


def _probe_service(base_url: str, headers: Optional[Dict[str, str]]) -> None:
    with httpx.Client(timeout=5.0) as client:
        try:
            response = client.get(f"{base_url}/job/openfold3_e2e_probe", headers=headers)
        except httpx.RequestError as exc:
            pytest.skip(f"OpenFold3 REST not reachable at {base_url}: {exc}")

    if response.status_code == 401:
        pytest.skip(
            "OpenFold3 REST requires Authorization token. "
            "Set OPENFOLD3_E2E_API_TOKEN or OPENFOLD3_REST_API_TOKEN."
        )

    if response.status_code not in {200, 404}:
        pytest.skip(
            f"OpenFold3 REST probe got unexpected status {response.status_code} at {base_url}"
        )


def _build_service(config: Dict[str, Any]) -> RESTModelInvocationService:
    return RESTModelInvocationService(
        base_url=config["base_url"],
        timeout=120.0,
        poll_interval=config["poll_interval"],
        max_poll_attempts=config["max_poll_attempts"],
        headers=config["headers"],
    )


@pytest.fixture(scope="module")
def openfold3_remote_config() -> Dict[str, Any]:
    base_url = _resolve_base_url()
    headers = _resolve_headers()
    _probe_service(base_url, headers)
    poll_interval = _resolve_poll_interval()
    max_poll_attempts = _resolve_max_poll_attempts(poll_interval)
    return {
        "base_url": base_url,
        "headers": headers,
        "poll_interval": poll_interval,
        "max_poll_attempts": max_poll_attempts,
    }


@pytest.fixture
def clean_registry():
    snapshot = _snapshot_registry()
    try:
        yield
    finally:
        _restore_registry(snapshot)


@pytest.fixture
def openfold3_rest_service(openfold3_remote_config: Dict[str, Any]):
    service = _build_service(openfold3_remote_config)
    try:
        yield service
    finally:
        service.client.close()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(420)
def test_openfold3_rest_service_submit_poll_download_e2e(
    tmp_path: Path,
    openfold3_rest_service: RESTModelInvocationService,
) -> None:
    task_id = f"openfold3_e2e_{uuid.uuid4().hex[:8]}"
    step_id = "S2"
    payload = {"sequence": _resolve_sequence()}

    job_id = openfold3_rest_service.submit_job(
        payload=payload,
        task_id=task_id,
        step_id=step_id,
    )
    assert isinstance(job_id, str) and job_id

    final_status = openfold3_rest_service.wait_for_completion(job_id)
    assert final_status == JobStatus.COMPLETED

    outputs = openfold3_rest_service.download_results(
        job_id=job_id,
        output_dir=tmp_path / "openfold3_remote_outputs",
    )
    pdb_path = Path(str(outputs.get("pdb_path", "")))
    assert pdb_path.exists()
    assert pdb_path.suffix.lower() in {".pdb", ".cif", ".mmcif"}

    plddt = outputs.get("plddt")
    assert isinstance(plddt, (int, float))
    assert 0.0 <= float(plddt) <= 100.0

    artifacts = outputs.get("artifacts")
    assert isinstance(artifacts, list)
    assert len(artifacts) >= 1


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(420)
def test_executor_openfold3_rest_e2e(
    tmp_path: Path,
    openfold3_remote_config: Dict[str, Any],
    clean_registry: None,
) -> None:
    service = _build_service(openfold3_remote_config)
    try:
        register_adapter(
            OpenFold3Adapter(
                execution_mode="openfold3_rest",
                service=service,
                output_dir=tmp_path / "openfold3_step_outputs",
            )
        )

        task = ProteinDesignTask(
            task_id=f"openfold3_exec_{uuid.uuid4().hex[:8]}",
            goal="Predict structure via remote OpenFold3 REST service",
            constraints={},
        )
        plan = Plan(
            task_id=task.task_id,
            steps=[
                PlanStep(
                    id="S2",
                    tool="openfold",
                    inputs={"sequence": _resolve_sequence()},
                    metadata={},
                )
            ],
            constraints=task.constraints,
            metadata={},
        )
        context = WorkflowContext(
            task=task,
            plan=plan,
            status=InternalStatus.PLANNED,
        )

        executor = ExecutorAgent()
        result = executor.run_step("S2", context)
    finally:
        service.client.close()

    assert result.status == "success"
    assert result.metrics.get("provider") == "openfold3_rest"
    assert result.metrics.get("exec_type") == "remote"
    assert isinstance(result.metrics.get("job_id"), str)
    assert result.outputs.get("stage_id") == "S2"
    assert isinstance(result.outputs.get("plddt"), (int, float))

    output_path = Path(str(result.outputs.get("pdb_path", "")))
    assert output_path.exists()
    assert output_path.suffix.lower() in {".pdb", ".cif", ".mmcif"}
