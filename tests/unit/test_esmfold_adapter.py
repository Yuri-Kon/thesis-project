"""
ESMFoldAdapter 单元测试

测试 ESMFold 适配器通过 WorkflowEngineAdapter 执行 Nextflow 的功能。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.esmfold_adapter import ESMFoldAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def adapter(tmp_path: Path) -> ESMFoldAdapter:
    """创建一个测试用的 ESMFoldAdapter"""
    module_path = tmp_path / "esmfold.nf"
    module_path.write_text("// Mock Nextflow module")

    return ESMFoldAdapter(
        module_path=module_path,
        nextflow_profile="test",
    )


@pytest.fixture
def context() -> WorkflowContext:
    """创建一个空的 WorkflowContext"""
    from src.models.contracts import ProteinDesignTask

    task = ProteinDesignTask(
        task_id="task123",
        goal="test protein design",
        objective="test",
        constraints={},
    )
    return WorkflowContext(task=task)


def test_resolve_inputs_literal_values(adapter: ESMFoldAdapter, context: WorkflowContext) -> None:
    """测试解析字面量输入"""
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={"sequence": "ACDEFGHIKLMNPQRSTVWY"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "ACDEFGHIKLMNPQRSTVWY"


def test_resolve_inputs_reference_syntax(adapter: ESMFoldAdapter, context: WorkflowContext) -> None:
    """测试解析引用语法（S1.field）"""
    from src.models.contracts import StepResult

    # 添加一个前置步骤的结果到上下文
    context.step_results["S1"] = StepResult(
        task_id="task123",
        step_id="S1",
        tool="protein_mpnn",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"},
        metrics={"exec_type": "python"},
        risk_flags=[],
        logs_path=None,
        timestamp="2024-01-01T00:00:00Z",
    )

    step = PlanStep(
        id="S2",
        tool="esmfold",
        inputs={"sequence": "S1.sequence"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"


def test_resolve_inputs_missing_sequence_raises_error(
    adapter: ESMFoldAdapter, context: WorkflowContext
) -> None:
    """测试缺少必需的 sequence 输入时抛出错误"""
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={},  # 缺少 sequence
        metadata={},
    )

    with pytest.raises(ValueError) as exc_info:
        adapter.resolve_inputs(step, context)

    assert "sequence" in str(exc_info.value).lower()


def test_resolve_inputs_invalid_reference_raises_error(
    adapter: ESMFoldAdapter, context: WorkflowContext
) -> None:
    """测试引用不存在的步骤时抛出错误"""
    step = PlanStep(
        id="S2",
        tool="esmfold",
        inputs={"sequence": "S1.sequence"},  # S1 不存在
        metadata={},
    )

    with pytest.raises(ValueError) as exc_info:
        adapter.resolve_inputs(step, context)

    assert "S1" in str(exc_info.value)
    assert "not found" in str(exc_info.value).lower()


@patch("src.engines.nextflow_adapter.WorkflowEngineAdapter.execute")
def test_run_local_success(mock_execute: MagicMock, adapter: ESMFoldAdapter) -> None:
    """测试成功执行 ESMFold"""
    # 模拟 WorkflowEngineAdapter.execute 返回
    mock_execute.return_value = (
        {
            "pdb_path": "/path/to/output.pdb",
            "metrics": {"plddt_mean": 0.85},
        },
        {
            "exec_type": "nextflow",
            "duration_ms": 1000,
            "nextflow_exit_code": 0,
        },
    )

    inputs = {
        "sequence": "ACDEFGHIKLMNPQRSTVWY",
        "task_id": "task123",
        "step_id": "S1",
    }

    outputs, metrics = adapter.run_local(inputs)

    # 验证调用了 execute
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs["task_id"] == "task123"
    assert call_kwargs["step_id"] == "S1"
    assert call_kwargs["tool_name"] == "esmfold"
    assert call_kwargs["inputs"]["sequence"] == "ACDEFGHIKLMNPQRSTVWY"

    # 验证返回值
    assert "pdb_path" in outputs
    assert "metrics" in outputs
    assert metrics["exec_type"] == "nextflow"


def test_run_local_missing_sequence_raises_error(adapter: ESMFoldAdapter) -> None:
    """测试缺少 sequence 输入时抛出错误"""
    inputs = {
        "task_id": "task123",
        "step_id": "S1",
    }

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_local(inputs)

    error = exc_info.value
    assert error.failure_type == FailureType.NON_RETRYABLE
    assert "sequence" in str(error).lower()


@patch("src.engines.nextflow_adapter.WorkflowEngineAdapter.execute")
def test_run_local_with_default_context(mock_execute: MagicMock, adapter: ESMFoldAdapter) -> None:
    """测试没有提供 task_id/step_id 时使用默认值"""
    mock_execute.return_value = (
        {"pdb_path": "/path/to/output.pdb"},
        {"exec_type": "nextflow", "duration_ms": 1000},
    )

    inputs = {"sequence": "ACDEFGHIKLMNPQRSTVWY"}

    adapter.run_local(inputs)

    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs["task_id"] == "unknown"
    assert call_kwargs["step_id"] == "unknown"
