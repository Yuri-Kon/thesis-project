"""
Full local workflow integration against real remote REST tools.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
import pytest

from src.adapters.biopython_qc_adapter import BioPythonQCAdapter
from src.adapters.openfold_adapter import OpenFold3Adapter
from src.adapters.protgpt2_adapter import ProtGPT2Adapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext


def _resolve_plm_base_url() -> str:
    return (
        os.getenv("PLM_E2E_BASE_URL")
        or os.getenv("PLM_REST_BASE_URL")
        or "http://localhost:8100"
    ).rstrip("/")


def _resolve_openfold_base_url() -> str:
    return (
        os.getenv("OPENFOLD3_E2E_BASE_URL")
        or os.getenv("OPENFOLD3_REST_BASE_URL")
        or "http://localhost:8200"
    ).rstrip("/")


def _probe(base_url: str, probe_id: str) -> None:
    with httpx.Client(timeout=5.0) as client:
        try:
            response = client.get(f"{base_url}/job/{probe_id}")
        except httpx.RequestError as exc:
            pytest.skip(f"Remote REST not reachable at {base_url}: {exc}")
    if response.status_code == 401:
        pytest.skip(f"Remote REST at {base_url} requires Authorization token.")
    if response.status_code not in {200, 404}:
        pytest.skip(
            f"Remote REST probe got unexpected status {response.status_code} at {base_url}"
        )


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


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(600)
def test_remote_rest_full_flow_e2e(tmp_path: Path) -> None:
    plm_base_url = _resolve_plm_base_url()
    openfold_base_url = _resolve_openfold_base_url()
    _probe(plm_base_url, "remote_rest_full_flow_plm_probe")
    _probe(openfold_base_url, "remote_rest_full_flow_openfold_probe")

    task_id = f"remote_rest_full_{uuid.uuid4().hex[:8]}"
    task = ProteinDesignTask(
        task_id=task_id,
        goal="Design a short antimicrobial peptide and predict its structure",
        constraints={
            "length_range": [20, 24],
            "num_candidates": 1,
            "plddt_threshold": 0.5,
        },
        metadata={"remote_rest_e2e": True},
    )
    plan = Plan(
        task_id=task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="protgpt2",
                inputs={
                    "goal": task.goal,
                    "length_range": [20, 24],
                    "num_candidates": 1,
                },
                metadata={"stage_id": "S1"},
            ),
            PlanStep(
                id="S2",
                tool="openfold",
                inputs={"sequence": "S1.sequence"},
                metadata={"stage_id": "S2"},
            ),
            PlanStep(
                id="S3",
                tool="biopython_qc",
                inputs={
                    "sequence": "S2.sequence",
                    "pdb_path": "S2.pdb_path",
                    "plddt": "S2.plddt",
                    "tool_id": "openfold",
                },
                metadata={"stage_id": "S3"},
            ),
        ],
        constraints=task.constraints,
        metadata={"plan_version": 1, "source": "remote_rest_e2e"},
    )
    record = TaskRecord(
        id=task_id,
        status=ExternalStatus.PLANNED,
        internal_status=InternalStatus.PLANNED,
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=plan,
    )
    context = WorkflowContext(
        task=task,
        plan=plan,
        status=InternalStatus.PLANNED,
    )

    snapshot = _snapshot_registry()
    try:
        register_adapter(
            ProtGPT2Adapter(
                base_url=plm_base_url,
                output_dir=tmp_path / "seq",
            )
        )
        register_adapter(
            OpenFold3Adapter(
                execution_mode="openfold3_rest",
                base_url=openfold_base_url,
                output_dir=tmp_path / "openfold3",
            )
        )
        register_adapter(BioPythonQCAdapter())

        executor = ExecutorAgent()
        summarizer = SummarizerAgent()
        executor.run_plan(plan, context, record=record, finalize_status=False)
        executor.summarize_and_finalize(context, record, summarizer)
    finally:
        _restore_registry(snapshot)

    assert context.status == InternalStatus.DONE
    assert record.status == ExternalStatus.DONE
    assert record.design_result is not None

    s1 = context.step_results["S1"]
    s2 = context.step_results["S2"]
    s3 = context.step_results["S3"]

    assert s1.status == "success"
    assert s1.metrics.get("provider") == "plm_rest"
    assert isinstance(s1.outputs.get("sequence"), str) and s1.outputs["sequence"]

    assert s2.status == "success"
    assert s2.metrics.get("provider") == "openfold3_rest"
    assert isinstance(s2.outputs.get("plddt"), (int, float))
    pdb_path = Path(str(s2.outputs.get("pdb_path", "")))
    assert pdb_path.exists()

    assert s3.status == "success"
    assert s3.outputs["quality_gate"]["status"] == "PASS"
    assert s3.outputs["quality_gate"]["qc_pass"] is True
    assert record.design_result.structure_pdb_path == str(pdb_path)
