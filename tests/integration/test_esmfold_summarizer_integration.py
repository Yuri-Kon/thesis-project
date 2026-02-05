"""
ESMFold + Summarizer 集成测试

验证 ESMFold 执行后，Summarizer 能够正确汇总结果，生成包含 PDB 路径和 pLDDT 的报告。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.esmfold_adapter import ESMFoldAdapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
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
def test_esmfold_summarizer_integration(
    mock_execute: MagicMock,
    setup_registry: None,
    tmp_path: Path,
) -> None:
    """测试 ESMFold 执行后 Summarizer 能够正确汇总结果"""
    # 模拟 Nextflow 执行成功，返回 ESMFold 结果
    mock_execute.return_value = (
        {
            "pdb_path": "/path/to/predicted_structure.pdb",
            "metrics": {
                "task_id": "esmfold_test_001",
                "tool": "esmfold",
                "plddt_mean": 0.88,
                "confidence": "high",
            },
        },
        {
            "exec_type": "nextflow",
            "duration_ms": 5000,
            "nextflow_exit_code": 0,
        },
    )

    # 创建任务和计划
    task = ProteinDesignTask(
        task_id="esmfold_test_001",
        goal="Predict protein structure using ESMFold for sequence MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
        constraints={
            "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
        },
    )

    plan = Plan(
        task_id="esmfold_test_001",
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

    # 创建上下文和 Agent
    context = WorkflowContext(task=task, plan=plan)
    executor = ExecutorAgent()
    summarizer = SummarizerAgent()

    # 执行步骤
    step_result = executor.run_step("S1", context)

    # 验证执行结果
    assert step_result.status == "success"
    assert step_result.tool == "esmfold"
    assert "pdb_path" in step_result.outputs
    assert "metrics" in step_result.outputs

    # 将步骤结果添加到上下文
    context.step_results["S1"] = step_result

    # 汇总结果
    design_result = summarizer.summarize(context)

    # 验证汇总结果
    assert design_result.task_id == "esmfold_test_001"

    # 验证提取了 PDB 路径
    assert design_result.structure_pdb_path == "/path/to/predicted_structure.pdb"

    # 验证提取了 pLDDT 分数
    assert "plddt_mean" in design_result.scores
    assert design_result.scores["plddt_mean"] == 0.88

    # 验证提取了置信度
    assert "confidence" in design_result.scores
    assert design_result.scores["confidence"] == "high"

    # 验证报告路径已设置
    assert design_result.report_path is not None

    # 验证元数据
    assert "step_ids" in design_result.metadata
    assert "S1" in design_result.metadata["step_ids"]


def test_summarizer_handles_empty_esmfold_results(
    tmp_path: Path,
) -> None:
    """测试 Summarizer 优雅地处理没有 ESMFold 结果的情况（即使失败也能生成报告）"""
    # 创建任务和计划
    task = ProteinDesignTask(
        task_id="esmfold_test_002",
        goal="Test failure handling - ensure Summarizer can handle empty results",
        constraints={
            "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
        },
    )

    plan = Plan(
        task_id="esmfold_test_002",
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

    # 创建上下文和 Summarizer（不执行步骤，模拟失败情况）
    context = WorkflowContext(task=task, plan=plan)
    summarizer = SummarizerAgent()

    # 即使没有成功的步骤结果，Summarizer 也应该能够生成报告
    design_result = summarizer.summarize(context)

    # 验证汇总结果（应该是空的或默认值）
    assert design_result.task_id == "esmfold_test_002"
    assert design_result.structure_pdb_path is None  # 没有成功的结果
    assert design_result.scores == {}  # 没有分数
    assert design_result.report_path is not None  # 但报告路径应该存在
