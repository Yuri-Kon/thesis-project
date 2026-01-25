"""
NIM ESMFold integration tests.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.adapters.nim_adapter import NIMESMFoldAdapter
from src.adapters.protein_mpnn_adapter import ProteinMPNNAdapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.agents.planner import PlannerAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.models.db import InternalStatus
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType

_SKIP_NIM = pytest.mark.skipif(
    not os.environ.get("NIM_API_KEY"),
    reason="NIM_API_KEY not set",
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


@pytest.fixture
def clean_registry():
    snapshot = _snapshot_registry()
    try:
        yield
    finally:
        _restore_registry(snapshot)


@_SKIP_NIM
@pytest.mark.integration
@pytest.mark.timeout(120)
def test_nim_esmfold_single_step(
    tmp_path: Path,
    clean_registry: None,
) -> None:
    """Run a single NIM ESMFold step via ExecutorAgent."""
    register_adapter(NIMESMFoldAdapter(output_dir=tmp_path / "pdb"))

    task = ProteinDesignTask(
        task_id="test_nim_001",
        goal="Predict structure with NIM",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="nim_esmfold",
                inputs={"sequence": "MKFLKFSLLTAVLLSVVFA"},
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

    assert result.status == "success"
    assert "pdb_path" in result.outputs
    assert Path(result.outputs["pdb_path"]).exists()
    assert result.metrics.get("provider") == "nvidia_nim"


@_SKIP_NIM
@pytest.mark.integration
@pytest.mark.timeout(120)
def test_de_novo_with_nim(
    tmp_path: Path,
    clean_registry: None,
) -> None:
    """Execute a de novo plan (ProteinMPNN -> NIM ESMFold)."""
    template_path = tmp_path / "template.pdb"
    template_path.write_text("HEADER    TEMPLATE\nEND\n", encoding="utf-8")

    task = ProteinDesignTask(
        task_id="test_nim_002",
        goal="de_novo_design",
        constraints={
            "structure_template_pdb": str(template_path),
            "length_range": [20, 30],
            "prefer_nim": True,
        },
    )

    planner = PlannerAgent()
    plan = planner.plan(task)

    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "protein_mpnn"
    assert plan.steps[1].tool == "nim_esmfold"
    assert plan.steps[1].inputs.get("sequence") == "S1.sequence"

    register_adapter(
        ProteinMPNNAdapter(artifacts_dir=tmp_path / "artifacts")
    )
    register_adapter(NIMESMFoldAdapter(output_dir=tmp_path / "pdb"))

    context = WorkflowContext(
        task=task,
        plan=plan,
        status=InternalStatus.PLANNED,
    )
    executor = ExecutorAgent()
    executor.run_plan(plan, context, finalize_status=False)

    assert "S2" in context.step_results
    s1_result = context.step_results["S1"]
    s2_result = context.step_results["S2"]
    assert s2_result.status == "success"
    assert s2_result.inputs.get("sequence") == s1_result.outputs.get("sequence")
    assert s2_result.metrics.get("provider") == "nvidia_nim"
    assert Path(s2_result.outputs["pdb_path"]).exists()


@_SKIP_NIM
@pytest.mark.integration
@pytest.mark.timeout(120)
def test_nim_failure_handling(
    tmp_path: Path,
    clean_registry: None,
) -> None:
    """Ensure NIM failures are classified when input is invalid."""
    register_adapter(NIMESMFoldAdapter(output_dir=tmp_path / "pdb"))

    task = ProteinDesignTask(
        task_id="test_nim_003",
        goal="Trigger NIM failure",
        constraints={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="nim_esmfold",
                inputs={"sequence": "M" * 1000},
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

    assert result.status == "failed"
    assert result.failure_type in {FailureType.NON_RETRYABLE, FailureType.TOOL_ERROR}
    assert (
        result.error_details.get("failure_code")
        == FailureCode.NIM_INVALID_INPUT.value
    )
