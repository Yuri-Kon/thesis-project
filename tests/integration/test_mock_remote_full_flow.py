from __future__ import annotations

from pathlib import Path

from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.engines.remote_model_service import JobStatus, RemoteModelInvocationService
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext


class MockRemoteModelService(RemoteModelInvocationService):
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, str]] = {}

    def submit_job(self, payload, task_id, step_id) -> str:
        job_id = f"mock_{task_id}_{step_id}"
        self._jobs[job_id] = {
            "sequence": payload.get("sequence", ""),
        }
        return job_id

    def poll_status(self, job_id: str) -> JobStatus:
        return JobStatus.COMPLETED

    def wait_for_completion(self, job_id: str) -> JobStatus:
        return JobStatus.COMPLETED

    def download_results(self, job_id: str, output_dir: Path):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        pdb_path = output_dir / f"{job_id}.pdb"
        pdb_path.write_text("HEADER    MOCK STRUCTURE\nEND\n", encoding="utf-8")
        return {
            "pdb_path": str(pdb_path),
            "metrics": {"plddt_mean": 0.88, "confidence": "high"},
        }


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


def test_mock_remote_full_flow(tmp_path: Path) -> None:
    task_id = "task_mock_remote_flow"
    sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"
    task = ProteinDesignTask(
        task_id=task_id,
        goal="Mock remote ESMFold flow",
        constraints={"sequence": sequence, "method": "esmfold"},
        metadata={"demo": True},
    )
    plan = Plan(
        task_id=task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="esmfold",
                inputs={"sequence": sequence},
                metadata={"provider": "baseline"},
            )
        ],
        constraints=task.constraints,
        metadata={"plan_version": 0},
    )
    record = TaskRecord(
        id=task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
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
        adapter = RemoteESMFoldAdapter(
            service=MockRemoteModelService(),
            output_dir=tmp_path / "remote",
            enable_snapshot=False,
        )
        register_adapter(adapter)

        executor = ExecutorAgent()
        summarizer = SummarizerAgent()
        executor.run_plan(plan, context, record=record, finalize_status=False)
        executor.summarize_and_finalize(context, record, summarizer)
    finally:
        _restore_registry(snapshot)

    assert "S1" in context.step_results
    result = context.step_results["S1"]
    assert result.status == "success"
    assert "pdb_path" in result.outputs
    assert record.design_result is not None
    assert record.design_result.structure_pdb_path == result.outputs["pdb_path"]
    assert Path(record.design_result.structure_pdb_path).exists()
    assert record.status == ExternalStatus.DONE
