from __future__ import annotations

from pathlib import Path

from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.models.db import InternalStatus
from src.tools.visualization.adapter import VisualizationToolAdapter
from src.workflow.context import WorkflowContext


def test_visualization_step_runs_end_to_end(tmp_path: Path) -> None:
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
    register_adapter(VisualizationToolAdapter())

    pdb_fixture = Path(__file__).resolve().parents[1] / "fixtures" / "1crn.pdb"
    task = ProteinDesignTask(
        task_id="viz_task_001",
        goal="visualize a local pdb",
        constraints={},
        metadata={},
    )
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="visualize_structure",
                inputs={
                    "pdb_path": str(pdb_fixture),
                    "out_dir": str(tmp_path / "artifacts"),
                },
                metadata={},
            )
        ],
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.PLANNED,
    )

    try:
        executor = ExecutorAgent()
        executor.run_plan(plan, context, finalize_status=False, max_replans=1)
        executor.summarize_and_finalize(context, record=None, summarizer=SummarizerAgent())

        assert context.status == InternalStatus.DONE
        result = context.step_results["S1"]
        assert result.status == "success"
        assert Path(result.outputs["metrics_json_path"]).exists()
        assert Path(result.outputs["plotly_html_path"]).exists()
        assert Path(result.outputs["report_html_path"]).exists()
    finally:
        ADAPTER_REGISTRY._by_tool_id.clear()
        ADAPTER_REGISTRY._by_adapter_id.clear()
