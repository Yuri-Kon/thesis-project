"""
WorkflowEngineAdapter 单元测试

测试 Nextflow 执行后端的核心功能：
- 输入映射
- 输出解析
- 失败映射
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.engines.nextflow_adapter import WorkflowEngineAdapter
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def adapter(tmp_path: Path) -> WorkflowEngineAdapter:
    """创建一个测试用的 WorkflowEngineAdapter"""
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"
    work_dir.mkdir()
    output_dir.mkdir()

    return WorkflowEngineAdapter(
        nextflow_bin="nextflow",
        profile="test",
        work_dir=work_dir,
        output_dir=output_dir,
    )


@pytest.fixture
def mock_nextflow_success(tmp_path: Path) -> MagicMock:
    """模拟 Nextflow 成功执行"""
    output_dir = tmp_path / "output"

    # 创建输出目录结构
    (output_dir / "pdb").mkdir(parents=True)
    (output_dir / "metrics").mkdir(parents=True)
    (output_dir / "artifacts").mkdir(parents=True)

    # 创建测试输出文件
    def side_effect(*args, **kwargs):
        # 从命令行参数提取 task_id
        cmd = args[0]
        task_id_idx = cmd.index("--task_id") + 1
        task_id = cmd[task_id_idx]

        # 生成 PDB 文件
        pdb_file = output_dir / "pdb" / f"{task_id}.pdb"
        pdb_file.write_text("MOCK PDB CONTENT\n")

        # 生成 metrics 文件
        metrics_file = output_dir / "metrics" / f"{task_id}_metrics.json"
        metrics_data = {
            "task_id": task_id,
            "tool": "esmfold",
            "plddt_mean": 0.85,
        }
        metrics_file.write_text(json.dumps(metrics_data))

        # 模拟成功的 CompletedProcess
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        result.stdout = "Nextflow run completed"
        result.stderr = ""
        return result

    mock = MagicMock(side_effect=side_effect)
    return mock


def test_prepare_nextflow_params(adapter: WorkflowEngineAdapter) -> None:
    """测试 Nextflow 参数准备"""
    inputs = {"sequence": "ACDEFGHIKLMNPQRSTVWY"}
    params = adapter._prepare_nextflow_params(
        inputs=inputs,
        task_id="task123",
        step_id="S1",
        tool_name="esmfold",
    )

    assert params["sequence"] == "ACDEFGHIKLMNPQRSTVWY"
    assert params["task_id"] == "task123"
    assert params["step_id"] == "S1"
    assert params["tool"] == "esmfold"
    assert "output_dir" in params


def test_parse_outputs_with_pdb_and_metrics(adapter: WorkflowEngineAdapter, tmp_path: Path) -> None:
    """测试输出解析：包含 PDB 和 metrics"""
    task_id = "task123"

    # 创建测试输出
    pdb_dir = adapter.output_dir / "pdb"
    metrics_dir = adapter.output_dir / "metrics"
    pdb_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    pdb_file = pdb_dir / f"{task_id}.pdb"
    pdb_file.write_text("MOCK PDB")

    metrics_file = metrics_dir / f"{task_id}_metrics.json"
    metrics_data = {"plddt_mean": 0.85, "confidence": "high"}
    metrics_file.write_text(json.dumps(metrics_data))

    # 解析输出
    outputs = adapter._parse_outputs(
        task_id=task_id,
        step_id="S1",
        tool_name="esmfold",
    )

    assert "pdb_path" in outputs
    assert outputs["pdb_path"].endswith(f"{task_id}.pdb")
    assert "metrics" in outputs
    assert outputs["metrics"]["plddt_mean"] == 0.85


def test_parse_outputs_empty_when_no_files(adapter: WorkflowEngineAdapter) -> None:
    """测试输出解析：没有输出文件时返回空字典"""
    outputs = adapter._parse_outputs(
        task_id="task456",
        step_id="S1",
        tool_name="esmfold",
    )

    assert outputs == {}


def test_classify_nextflow_error(adapter: WorkflowEngineAdapter) -> None:
    """测试 Nextflow 错误分类"""
    # SIGKILL (OOM) - 可重试
    assert adapter._classify_nextflow_error(137) == FailureType.RETRYABLE

    # SIGTERM (超时) - 可重试
    assert adapter._classify_nextflow_error(143) == FailureType.RETRYABLE

    # 使用错误 - 不可重试
    assert adapter._classify_nextflow_error(2) == FailureType.NON_RETRYABLE

    # 其他错误 - 工具错误
    assert adapter._classify_nextflow_error(1) == FailureType.TOOL_ERROR


@patch("subprocess.run")
def test_execute_success(
    mock_run: MagicMock,
    adapter: WorkflowEngineAdapter,
    mock_nextflow_success: MagicMock,
    tmp_path: Path,
) -> None:
    """测试成功执行 Nextflow"""
    mock_run.side_effect = mock_nextflow_success

    module_path = tmp_path / "test.nf"
    module_path.write_text("// Mock Nextflow module")

    inputs = {"sequence": "ACDEFGHIKLMNPQRSTVWY"}
    outputs, metrics = adapter.execute(
        module_path=module_path,
        inputs=inputs,
        task_id="task123",
        step_id="S1",
        tool_name="esmfold",
    )

    # 验证调用了 subprocess.run
    assert mock_run.called

    # 验证输出
    assert "pdb_path" in outputs
    assert "metrics" in outputs
    assert outputs["metrics"]["plddt_mean"] == 0.85

    # 验证指标
    assert metrics["exec_type"] == "nextflow"
    assert "duration_ms" in metrics
    assert metrics["nextflow_exit_code"] == 0


@patch("subprocess.run")
def test_execute_failure_non_zero_exit(
    mock_run: MagicMock,
    adapter: WorkflowEngineAdapter,
    tmp_path: Path,
) -> None:
    """测试 Nextflow 执行失败（非零退出码）"""
    # 模拟 Nextflow 失败
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["nextflow", "run"],
        output="Error occurred",
    )

    module_path = tmp_path / "test.nf"
    module_path.write_text("// Mock Nextflow module")

    inputs = {"sequence": "ACDEFGHIKLMNPQRSTVWY"}

    with pytest.raises(StepRunError) as exc_info:
        adapter.execute(
            module_path=module_path,
            inputs=inputs,
            task_id="task123",
            step_id="S1",
            tool_name="esmfold",
        )

    error = exc_info.value
    assert error.failure_type == FailureType.TOOL_ERROR
    assert "exit code 1" in str(error)


@patch("subprocess.run")
def test_execute_failure_output_parse_error(
    mock_run: MagicMock,
    adapter: WorkflowEngineAdapter,
    tmp_path: Path,
) -> None:
    """测试输出解析失败"""
    # 模拟 Nextflow 成功，但输出文件格式错误
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = 0
    mock_run.return_value = result

    # 创建格式错误的 metrics 文件
    metrics_dir = adapter.output_dir / "metrics"
    metrics_dir.mkdir(parents=True)
    metrics_file = metrics_dir / "task123_metrics.json"
    metrics_file.write_text("INVALID JSON")

    module_path = tmp_path / "test.nf"
    module_path.write_text("// Mock Nextflow module")

    inputs = {"sequence": "ACDEFGHIKLMNPQRSTVWY"}

    with pytest.raises(StepRunError) as exc_info:
        adapter.execute(
            module_path=module_path,
            inputs=inputs,
            task_id="task123",
            step_id="S1",
            tool_name="esmfold",
        )

    error = exc_info.value
    assert error.failure_type == FailureType.NON_RETRYABLE
    assert "parse" in str(error).lower()


def test_find_output_file(adapter: WorkflowEngineAdapter) -> None:
    """测试输出文件查找"""
    # 创建测试文件
    test_dir = adapter.output_dir / "test"
    test_dir.mkdir(parents=True)

    file1 = test_dir / "task123_output.pdb"
    file2 = test_dir / "task123_other.pdb"
    file1.write_text("test")
    file2.write_text("test")

    # 查找文件
    found = adapter._find_output_file(test_dir, "task123", ".pdb")
    assert found is not None
    assert "task123" in found.name
    assert found.suffix == ".pdb"


def test_find_output_file_not_found(adapter: WorkflowEngineAdapter) -> None:
    """测试输出文件不存在"""
    test_dir = adapter.output_dir / "test"
    test_dir.mkdir(parents=True)

    found = adapter._find_output_file(test_dir, "task999", ".pdb")
    assert found is None
