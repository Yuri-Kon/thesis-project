"""
ESMFold 工作流集成测试

验证 Executor 能够通过 ESMFoldAdapter 和 WorkflowEngineAdapter 执行 Nextflow 流程。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.esmfold_adapter import ESMFoldAdapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.models.contracts import Plan, PlanStep, ProteinDesignTask
from src.workflow.context import WorkflowContext


@pytest.fixture
def esmfold_adapter(tmp_path: Path) -> ESMFoldAdapter:
    """创建测试用的 ESMFoldAdapter"""
    module_path = tmp_path / "esmfold.nf"
    module_path.write_text("// Mock Nextflow module")

    return ESMFoldAdapter(
        module_path=module_path,
        nextflow_profile="test",
    )


@pytest.fixture
def setup_registry(esmfold_adapter: ESMFoldAdapter):
    """设置适配器注册表"""
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
    register_adapter(esmfold_adapter)
    yield
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()


@patch("src.engines.nextflow_adapter.WorkflowEngineAdapter.execute")
def test_executor_runs_esmfold_step(
    mock_execute: MagicMock,
    setup_registry: None,
) -> None:
    """测试 Executor 能够运行 ESMFold 步骤"""
    # 模拟 Nextflow 执行成功
    mock_execute.return_value = (
        {
            "pdb_path": "/path/to/task123.pdb",
            "metrics": {
                "task_id": "task123",
                "tool": "esmfold",
                "plddt_mean": 0.85,
                "confidence": "high",
            },
        },
        {
            "exec_type": "nextflow",
            "duration_ms": 1000,
            "nextflow_exit_code": 0,
        },
    )

    # 创建任务和计划
    task = ProteinDesignTask(
        task_id="task123",
        goal="Design a stable protein",
        objective="Predict structure for sequence MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
        constraints={},
    )

    plan = Plan(
        task_id="task123",
        steps=[
            PlanStep(
                id="S1",
                tool="esmfold",
                inputs={"sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"},
                metadata={},
            )
        ],
        constraints={},
        metadata={},
    )

    # 创建上下文和执行器
    context = WorkflowContext(task=task, plan=plan)
    executor = ExecutorAgent()

    # 执行步骤
    result = executor.run_step("S1", context)

    # 验证结果
    assert result.status == "success"
    assert result.task_id == "task123"
    assert result.step_id == "S1"
    assert result.tool == "esmfold"
    assert "pdb_path" in result.outputs
    assert "metrics" in result.outputs
    assert result.metrics["exec_type"] == "nextflow"

    # 验证 Nextflow 被调用
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs["task_id"] == "task123"
    assert call_kwargs["step_id"] == "S1"
    assert call_kwargs["tool_name"] == "esmfold"
