"""
PLM remote REST end-to-end integration tests.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pytest

from src.adapters.protgpt2_adapter import ProtGPT2Adapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.engines.remote_model_service import JobStatus, RESTModelInvocationService
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.models.db import InternalStatus
from src.workflow.context import WorkflowContext


def _resolve_base_url() -> str:
    return (
        os.getenv("PLM_E2E_BASE_URL")
        or os.getenv("PLM_REST_BASE_URL")
        or "http://localhost:8100"
    ).rstrip("/")


def _resolve_headers() -> Optional[Dict[str, str]]:
    token = (
        os.getenv("PLM_E2E_API_TOKEN")
        or os.getenv("PLM_REST_API_TOKEN")
        or ""
    ).strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _resolve_poll_interval() -> float:
    try:
        value = float(os.getenv("PLM_E2E_POLL_INTERVAL", "2.0"))
    except ValueError:
        value = 2.0
    return max(0.5, value)


def _resolve_max_poll_attempts(poll_interval: float) -> int:
    try:
        max_wait = float(os.getenv("PLM_E2E_MAX_WAIT_SECONDS", "180"))
    except ValueError:
        max_wait = 180.0
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
            response = client.get(f"{base_url}/job/plm_e2e_probe", headers=headers)
        except httpx.RequestError as exc:
            pytest.skip(f"PLM REST not reachable at {base_url}: {exc}")

    if response.status_code == 401:
        pytest.skip(
            "PLM REST requires Authorization token. "
            "Set PLM_E2E_API_TOKEN or PLM_REST_API_TOKEN."
        )

    if response.status_code not in {200, 404}:
        pytest.skip(
            f"PLM REST probe got unexpected status {response.status_code} at {base_url}"
        )


def _build_service(config: Dict[str, Any]) -> RESTModelInvocationService:
    return RESTModelInvocationService(
        base_url=config["base_url"],
        timeout=180.0,
        poll_interval=config["poll_interval"],
        max_poll_attempts=config["max_poll_attempts"],
        headers=config["headers"],
    )


@pytest.fixture(scope="module")
def plm_remote_config() -> Dict[str, Any]:
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
def plm_rest_service(plm_remote_config: Dict[str, Any]):
    service = _build_service(plm_remote_config)
    try:
        yield service
    finally:
        service.client.close()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(420)
def test_plm_rest_service_submit_poll_download_e2e(
    tmp_path: Path,
    plm_rest_service: RESTModelInvocationService,
) -> None:
    task_id = f"plm_e2e_{uuid.uuid4().hex[:8]}"
    step_id = "S1"
    payload = {
        "goal": "Design a short antimicrobial peptide",
        "length_range": [20, 24],
        "num_return_sequences": 1,
    }

    job_id = plm_rest_service.submit_job(
        payload=payload,
        task_id=task_id,
        step_id=step_id,
    )
    assert isinstance(job_id, str) and job_id

    final_status = plm_rest_service.wait_for_completion(job_id)
    assert final_status == JobStatus.COMPLETED

    outputs = plm_rest_service.download_results(
        job_id=job_id,
        output_dir=tmp_path / "plm_remote_outputs",
    )
    sequence = outputs.get("sequence")
    candidates = outputs.get("candidates")
    artifacts = outputs.get("artifacts")

    assert isinstance(sequence, str) and sequence
    assert isinstance(candidates, list) and candidates
    assert isinstance(candidates[0], dict)
    assert candidates[0].get("sequence") == sequence
    assert isinstance(artifacts, list) and artifacts


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(420)
def test_executor_protgpt2_rest_e2e(
    tmp_path: Path,
    plm_remote_config: Dict[str, Any],
    clean_registry: None,
) -> None:
    service = _build_service(plm_remote_config)
    try:
        register_adapter(
            ProtGPT2Adapter(
                service=service,
                output_dir=tmp_path / "plm_step_outputs",
            )
        )

        task = ProteinDesignTask(
            task_id=f"plm_exec_{uuid.uuid4().hex[:8]}",
            goal="Design a short antimicrobial peptide",
            constraints={"length_range": [20, 24], "num_candidates": 1},
        )
        plan = Plan(
            task_id=task.task_id,
            steps=[
                PlanStep(
                    id="S1",
                    tool="protgpt2",
                    inputs={
                        "goal": task.goal,
                        "length_range": [20, 24],
                        "num_candidates": 1,
                    },
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
        result = executor.run_step("S1", context)
    finally:
        service.client.close()

    assert result.status == "success"
    assert result.metrics.get("provider") == "plm_rest"
    assert result.metrics.get("exec_type") == "remote"
    assert isinstance(result.metrics.get("job_id"), str)
    assert isinstance(result.outputs.get("sequence"), str)
    assert isinstance(result.outputs.get("candidates"), list)
