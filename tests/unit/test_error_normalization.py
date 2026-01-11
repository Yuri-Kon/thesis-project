"""
测试失败归一化与标准化失败码

验证：
- FailureCode 枚举的定义
- ErrorMeta 结构的构建
- build_error_meta 辅助函数
- StepResult 中 error_details 的标准化格式
"""
from __future__ import annotations

import pytest

from src.workflow.errors import (
    FailureType,
    FailureCode,
    ErrorMeta,
    build_error_meta,
    StepRunError,
)


def test_failure_code_enum_values() -> None:
    """测试 FailureCode 枚举包含所有必需的失败码"""
    # 安全检查相关
    assert FailureCode.SAFETY_PRE_BLOCK.value == "SAFETY_PRE_BLOCK"
    assert FailureCode.SAFETY_POST_BLOCK.value == "SAFETY_POST_BLOCK"
    assert FailureCode.SAFETY_TASK_INPUT_BLOCK.value == "SAFETY_TASK_INPUT_BLOCK"
    assert FailureCode.SAFETY_FINAL_BLOCK.value == "SAFETY_FINAL_BLOCK"

    # 适配器查找失败
    assert FailureCode.ADAPTER_NOT_FOUND.value == "ADAPTER_NOT_FOUND"

    # 输入解析失败
    assert FailureCode.INPUT_RESOLUTION_FAILED.value == "INPUT_RESOLUTION_FAILED"
    assert FailureCode.INPUT_REFERENCE_NOT_FOUND.value == "INPUT_REFERENCE_NOT_FOUND"
    assert FailureCode.INPUT_FIELD_NOT_FOUND.value == "INPUT_FIELD_NOT_FOUND"

    # 输出验证失败
    assert FailureCode.OUTPUT_NOT_DICT.value == "OUTPUT_NOT_DICT"
    assert FailureCode.OUTPUT_MISSING.value == "OUTPUT_MISSING"
    assert FailureCode.OUTPUT_TYPE_MISMATCH.value == "OUTPUT_TYPE_MISMATCH"

    # 工具执行失败
    assert FailureCode.TOOL_EXECUTION_ERROR.value == "TOOL_EXECUTION_ERROR"
    assert FailureCode.TOOL_UNEXPECTED_ERROR.value == "TOOL_UNEXPECTED_ERROR"

    # 远程调用失败 - 提交阶段
    assert FailureCode.REMOTE_SUBMIT_NETWORK_ERROR.value == "REMOTE_SUBMIT_NETWORK_ERROR"
    assert FailureCode.REMOTE_SUBMIT_TIMEOUT.value == "REMOTE_SUBMIT_TIMEOUT"
    assert FailureCode.REMOTE_SUBMIT_HTTP_4XX.value == "REMOTE_SUBMIT_HTTP_4XX"
    assert FailureCode.REMOTE_SUBMIT_HTTP_5XX.value == "REMOTE_SUBMIT_HTTP_5XX"

    # 远程调用失败 - 轮询阶段
    assert FailureCode.REMOTE_POLL_NETWORK_ERROR.value == "REMOTE_POLL_NETWORK_ERROR"
    assert FailureCode.REMOTE_POLL_TIMEOUT.value == "REMOTE_POLL_TIMEOUT"
    assert FailureCode.REMOTE_POLL_HTTP_4XX.value == "REMOTE_POLL_HTTP_4XX"
    assert FailureCode.REMOTE_POLL_HTTP_5XX.value == "REMOTE_POLL_HTTP_5XX"
    assert FailureCode.REMOTE_JOB_UNKNOWN.value == "REMOTE_JOB_UNKNOWN"
    assert FailureCode.REMOTE_JOB_FAILED.value == "REMOTE_JOB_FAILED"

    # 远程调用失败 - 结果下载阶段
    assert FailureCode.REMOTE_DOWNLOAD_NETWORK_ERROR.value == "REMOTE_DOWNLOAD_NETWORK_ERROR"
    assert FailureCode.REMOTE_DOWNLOAD_TIMEOUT.value == "REMOTE_DOWNLOAD_TIMEOUT"
    assert FailureCode.REMOTE_DOWNLOAD_HTTP_4XX.value == "REMOTE_DOWNLOAD_HTTP_4XX"
    assert FailureCode.REMOTE_DOWNLOAD_HTTP_5XX.value == "REMOTE_DOWNLOAD_HTTP_5XX"


def test_build_error_meta_basic() -> None:
    """测试 build_error_meta 基础功能"""
    meta = build_error_meta(
        failure_code=FailureCode.TOOL_EXECUTION_ERROR,
        phase="tool_execution",
    )

    assert meta["failure_code"] == "TOOL_EXECUTION_ERROR"
    assert meta["phase"] == "tool_execution"
    assert "timestamp" in meta


def test_build_error_meta_with_remote_info() -> None:
    """测试 build_error_meta 包含远程调用信息"""
    meta = build_error_meta(
        failure_code=FailureCode.REMOTE_SUBMIT_HTTP_5XX,
        phase="remote_submit",
        remote_job_id="job123",
        remote_endpoint="https://api.example.com",
        http_status_code=500,
    )

    assert meta["failure_code"] == "REMOTE_SUBMIT_HTTP_5XX"
    assert meta["phase"] == "remote_submit"
    assert meta["remote_job_id"] == "job123"
    assert meta["remote_endpoint"] == "https://api.example.com"
    assert meta["http_status_code"] == 500


def test_build_error_meta_with_retry_info() -> None:
    """测试 build_error_meta 包含重试信息"""
    meta = build_error_meta(
        failure_code=FailureCode.TOOL_EXECUTION_ERROR,
        phase="tool_execution",
        retry_count=2,
        max_retries=3,
    )

    assert meta["retry_count"] == 2
    assert meta["max_retries"] == 3


def test_build_error_meta_with_exception_info() -> None:
    """测试 build_error_meta 包含异常信息"""
    meta = build_error_meta(
        failure_code=FailureCode.TOOL_UNEXPECTED_ERROR,
        phase="tool_execution",
        exception_type="ValueError",
        exception_message="Invalid input",
    )

    assert meta["exception_type"] == "ValueError"
    assert meta["exception_message"] == "Invalid input"


def test_build_error_meta_with_context() -> None:
    """测试 build_error_meta 包含额外上下文"""
    meta = build_error_meta(
        failure_code=FailureCode.INPUT_RESOLUTION_FAILED,
        phase="input_resolution",
        context={"step_id": "S1", "field": "sequence"},
    )

    assert "context" in meta
    assert meta["context"]["step_id"] == "S1"
    assert meta["context"]["field"] == "sequence"


def test_build_error_meta_accepts_string_code() -> None:
    """测试 build_error_meta 接受字符串失败码"""
    meta = build_error_meta(
        failure_code="CUSTOM_ERROR",
        phase="custom_phase",
    )

    assert meta["failure_code"] == "CUSTOM_ERROR"
    assert meta["phase"] == "custom_phase"


def test_step_run_error_with_standard_code() -> None:
    """测试 StepRunError 使用标准化失败码"""
    error = StepRunError(
        failure_type=FailureType.RETRYABLE,
        message="Network error during job submission",
        code=FailureCode.REMOTE_SUBMIT_NETWORK_ERROR.value,
    )

    assert error.failure_type == FailureType.RETRYABLE
    assert error.code == "REMOTE_SUBMIT_NETWORK_ERROR"
    assert "Network error" in str(error)


def test_error_meta_structure_is_dict_compatible() -> None:
    """测试 ErrorMeta 结构与 Dict 兼容"""
    meta = build_error_meta(
        failure_code=FailureCode.TOOL_EXECUTION_ERROR,
        phase="tool_execution",
    )

    # ErrorMeta 应该是一个普通的字典
    assert isinstance(meta, dict)
    assert "failure_code" in meta
    assert "phase" in meta
    assert "timestamp" in meta


def test_build_error_meta_custom_timestamp() -> None:
    """测试 build_error_meta 使用自定义时间戳"""
    custom_timestamp = "2024-01-01T00:00:00+00:00"
    meta = build_error_meta(
        failure_code=FailureCode.TOOL_EXECUTION_ERROR,
        phase="tool_execution",
        timestamp=custom_timestamp,
    )

    assert meta["timestamp"] == custom_timestamp


def test_build_error_meta_omits_none_fields() -> None:
    """测试 build_error_meta 不包含 None 值字段"""
    meta = build_error_meta(
        failure_code=FailureCode.TOOL_EXECUTION_ERROR,
        phase="tool_execution",
        remote_job_id=None,  # 应该被省略
        retry_count=None,  # 应该被省略
    )

    assert "remote_job_id" not in meta
    assert "retry_count" not in meta
    assert "failure_code" in meta
    assert "phase" in meta


def test_error_meta_comprehensive_example() -> None:
    """测试 ErrorMeta 完整示例（模拟远程作业超时失败）"""
    meta = build_error_meta(
        failure_code=FailureCode.REMOTE_POLL_TIMEOUT,
        phase="remote_poll",
        timestamp="2024-01-01T12:00:00+00:00",
        remote_job_id="job_abc123",
        remote_endpoint="https://esmfold.example.com",
        retry_count=3,
        max_retries=3,
        exception_type="TimeoutError",
        exception_message="Job polling timeout after 60 attempts",
        context={
            "poll_attempts": 60,
            "poll_interval_ms": 5000,
            "last_known_status": "running",
        },
    )

    # 验证所有字段都正确填充
    assert meta["failure_code"] == "REMOTE_POLL_TIMEOUT"
    assert meta["phase"] == "remote_poll"
    assert meta["timestamp"] == "2024-01-01T12:00:00+00:00"
    assert meta["remote_job_id"] == "job_abc123"
    assert meta["remote_endpoint"] == "https://esmfold.example.com"
    assert meta["retry_count"] == 3
    assert meta["max_retries"] == 3
    assert meta["exception_type"] == "TimeoutError"
    assert meta["exception_message"] == "Job polling timeout after 60 attempts"
    assert meta["context"]["poll_attempts"] == 60
    assert meta["context"]["poll_interval_ms"] == 5000
    assert meta["context"]["last_known_status"] == "running"
