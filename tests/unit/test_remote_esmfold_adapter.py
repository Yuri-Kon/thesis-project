"""
RemoteESMFoldAdapter 单元测试

测试 RemoteESMFoldAdapter 通过 RemoteModelInvocationService 执行远程预测的功能。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from src.engines.remote_model_service import JobStatus
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def mock_service() -> Mock:
    """创建一个 mock 的 RemoteModelInvocationService"""
    service = Mock()
    service.submit_job.return_value = "job123"
    service.wait_for_completion.return_value = JobStatus.COMPLETED
    service.download_results.return_value = {
        "pdb_path": "/output/structure.pdb",
        "metrics": {"pLDDT": 85.5},
        "artifacts": ["/output/structure.pdb"],
    }
    return service


@pytest.fixture
def adapter(mock_service: Mock, tmp_path: Path) -> RemoteESMFoldAdapter:
    """创建一个测试用的 RemoteESMFoldAdapter"""
    return RemoteESMFoldAdapter(
        service=mock_service,
        output_dir=tmp_path / "output",
    )


@pytest.fixture
def context() -> WorkflowContext:
    """创建一个空的 WorkflowContext"""
    from src.models.contracts import ProteinDesignTask

    task = ProteinDesignTask(
        task_id="task123",
        goal="test protein design",
        constraints={},
    )
    return WorkflowContext(task=task)


def test_init_with_service(mock_service: Mock) -> None:
    """测试使用服务实例初始化"""
    adapter = RemoteESMFoldAdapter(service=mock_service)
    assert adapter.service == mock_service
    assert adapter.tool_id == "esmfold"
    assert adapter.adapter_id == "esmfold_remote"


def test_init_with_base_url() -> None:
    """测试使用 base_url 初始化"""
    adapter = RemoteESMFoldAdapter(base_url="http://localhost:8000")
    assert adapter.service is not None
    assert adapter.tool_id == "esmfold"


def test_init_missing_both_raises_error() -> None:
    """测试缺少 service 和 base_url 时抛出错误"""
    with pytest.raises(ValueError) as exc_info:
        RemoteESMFoldAdapter()

    assert "Either 'service' or 'base_url' must be provided" in str(exc_info.value)


def test_resolve_inputs_literal_values(
    adapter: RemoteESMFoldAdapter, context: WorkflowContext
) -> None:
    """测试解析字面量输入"""
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={"sequence": "ACDEFGHIKLMNPQRSTVWY"},
        metadata={},
    )

    resolved = adapter.resolve_inputs(step, context)

    assert resolved["sequence"] == "ACDEFGHIKLMNPQRSTVWY"
    assert resolved["task_id"] == "task123"
    assert resolved["step_id"] == "S1"


def test_resolve_inputs_reference_syntax(
    adapter: RemoteESMFoldAdapter, context: WorkflowContext
) -> None:
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
    adapter: RemoteESMFoldAdapter, context: WorkflowContext
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

    assert "Missing required input 'sequence'" in str(exc_info.value)


def test_run_remote_success(adapter: RemoteESMFoldAdapter, mock_service: Mock, tmp_path: Path) -> None:
    """测试成功的远程执行"""
    inputs = {
        "sequence": "ACDEFGHIKLMNPQRSTVWY",
        "task_id": "task123",
        "step_id": "S1",
    }

    outputs, metrics = adapter.run_remote(inputs, output_dir=tmp_path / "output")

    # 验证服务调用
    mock_service.submit_job.assert_called_once_with(
        payload={"sequence": "ACDEFGHIKLMNPQRSTVWY"},
        task_id="task123",
        step_id="S1",
    )
    mock_service.wait_for_completion.assert_called_once_with("job123")
    mock_service.download_results.assert_called_once()

    # 验证输出
    assert outputs["pdb_path"] == "/output/structure.pdb"
    assert outputs["metrics"]["pLDDT"] == 85.5
    assert outputs["artifacts"] == ["/output/structure.pdb"]

    # 验证指标
    assert metrics["exec_type"] == "remote"
    assert metrics["job_id"] == "job123"
    assert "duration_ms" in metrics


def test_run_remote_missing_sequence(adapter: RemoteESMFoldAdapter) -> None:
    """测试缺少 sequence 输入时抛出错误"""
    inputs = {
        "task_id": "task123",
        "step_id": "S1",
    }

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_remote(inputs)

    assert exc_info.value.failure_type == FailureType.NON_RETRYABLE
    assert "Missing required input 'sequence'" in str(exc_info.value)


def test_run_remote_job_failed(adapter: RemoteESMFoldAdapter, mock_service: Mock) -> None:
    """测试远程作业失败"""
    mock_service.wait_for_completion.return_value = JobStatus.FAILED

    inputs = {
        "sequence": "ACDEFGHIKLMNPQRSTVWY",
        "task_id": "task123",
        "step_id": "S1",
    }

    with pytest.raises(StepRunError) as exc_info:
        adapter.run_remote(inputs)

    assert exc_info.value.failure_type == FailureType.TOOL_ERROR
    assert "failed" in str(exc_info.value)


def test_run_remote_manual_polling_without_wait_for_completion(
    mock_service: Mock
) -> None:
    """测试手动轮询（服务不支持 wait_for_completion）"""
    # 移除 wait_for_completion 方法
    delattr(mock_service, "wait_for_completion")

    # 模拟状态轮询
    mock_service.poll_status.side_effect = [
        JobStatus.PENDING,
        JobStatus.RUNNING,
        JobStatus.COMPLETED,
    ]
    mock_service.download_results.return_value = {
        "pdb_path": "/output/structure.pdb",
        "artifacts": ["/output/structure.pdb"],
    }

    adapter = RemoteESMFoldAdapter(service=mock_service)

    inputs = {
        "sequence": "ACDEFGHIKLMNPQRSTVWY",
        "task_id": "task123",
        "step_id": "S1",
    }

    with patch("time.sleep"):  # 跳过实际睡眠
        outputs, _metrics = adapter.run_remote(inputs)

    # 验证轮询被调用
    assert mock_service.poll_status.call_count == 3
    assert outputs["pdb_path"] == "/output/structure.pdb"


def test_run_remote_manual_polling_timeout(mock_service: Mock) -> None:
    """测试手动轮询超时"""
    # 移除 wait_for_completion 方法
    delattr(mock_service, "wait_for_completion")

    # 模拟一直返回 RUNNING 状态
    mock_service.poll_status.return_value = JobStatus.RUNNING

    adapter = RemoteESMFoldAdapter(service=mock_service)

    inputs = {
        "sequence": "ACDEFGHIKLMNPQRSTVWY",
        "task_id": "task123",
        "step_id": "S1",
    }

    with patch("time.sleep"):
        with pytest.raises(StepRunError) as exc_info:
            adapter.run_remote(inputs)

    assert exc_info.value.failure_type == FailureType.RETRYABLE
    assert "timeout" in str(exc_info.value)


def test_run_local_delegates_to_run_remote(
    adapter: RemoteESMFoldAdapter, mock_service: Mock
) -> None:
    """测试 run_local 委托到 run_remote"""
    inputs = {
        "sequence": "ACDEFGHIKLMNPQRSTVWY",
        "task_id": "task123",
        "step_id": "S1",
    }

    _outputs, metrics = adapter.run_local(inputs)

    # 验证服务调用（说明调用了 run_remote）
    mock_service.submit_job.assert_called_once()
    assert metrics["exec_type"] == "remote"
