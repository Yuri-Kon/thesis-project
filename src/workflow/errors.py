"""
错误分类与运行期异常定义

为 StepRunner / PlanRunner 提供统一的失败类型枚举，区分：
- 可重试任务
- 不可重试任务
- 工具异常
- 安全阻断

同时定义标准化的失败码（FailureCode）和错误元数据（ErrorMeta）结构，
用于统一本地执行和远程调用的失败归因与审计追踪。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, TypedDict

__all__ = [
    "FailureType",
    "FailureCode",
    "ErrorMeta",
    "RunnerError",
    "StepRunError",
    "PlanRunError",
    "classify_exception",
    "is_retryable_failure",
    "build_error_meta",
]


class FailureType(str, Enum):
    """执行失败分类"""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    TOOL_ERROR = "tool_error"
    SAFETY_BLOCK = "safety_block"


class FailureCode(str, Enum):
    """标准化失败码枚举

    用于统一本地执行和远程调用的失败归因。
    每个失败码对应一种具体的失败原因，便于：
    - 审计追踪
    - 失败统计分析
    - Patch/Replan 策略决策
    """

    # 安全检查相关失败
    SAFETY_PRE_BLOCK = "SAFETY_PRE_BLOCK"  # 步骤执行前安全阻断
    SAFETY_POST_BLOCK = "SAFETY_POST_BLOCK"  # 步骤执行后安全阻断
    SAFETY_TASK_INPUT_BLOCK = "SAFETY_TASK_INPUT_BLOCK"  # 任务输入安全阻断
    SAFETY_FINAL_BLOCK = "SAFETY_FINAL_BLOCK"  # 最终结果安全阻断

    # 适配器查找失败
    ADAPTER_NOT_FOUND = "ADAPTER_NOT_FOUND"  # 找不到工具适配器

    # 输入解析失败
    INPUT_RESOLUTION_FAILED = "INPUT_RESOLUTION_FAILED"  # 输入解析失败
    INPUT_REFERENCE_NOT_FOUND = "INPUT_REFERENCE_NOT_FOUND"  # 引用的步骤结果不存在
    INPUT_FIELD_NOT_FOUND = "INPUT_FIELD_NOT_FOUND"  # 引用的字段不存在

    # 输出验证失败
    OUTPUT_NOT_DICT = "OUTPUT_NOT_DICT"  # 输出不是字典
    OUTPUT_MISSING = "OUTPUT_MISSING"  # 缺少必需输出字段
    OUTPUT_TYPE_MISMATCH = "OUTPUT_TYPE_MISMATCH"  # 输出类型不匹配

    # 工具执行失败
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"  # 工具执行异常
    TOOL_UNEXPECTED_ERROR = "TOOL_UNEXPECTED_ERROR"  # 工具未预期异常

    # 远程调用失败 - 提交阶段
    REMOTE_SUBMIT_NETWORK_ERROR = "REMOTE_SUBMIT_NETWORK_ERROR"  # 提交作业时网络错误
    REMOTE_SUBMIT_TIMEOUT = "REMOTE_SUBMIT_TIMEOUT"  # 提交作业超时
    REMOTE_SUBMIT_HTTP_4XX = "REMOTE_SUBMIT_HTTP_4XX"  # 提交作业 HTTP 4xx 错误
    REMOTE_SUBMIT_HTTP_5XX = "REMOTE_SUBMIT_HTTP_5XX"  # 提交作业 HTTP 5xx 错误
    REMOTE_SUBMIT_INVALID_RESPONSE = "REMOTE_SUBMIT_INVALID_RESPONSE"  # 提交响应格式无效
    REMOTE_SUBMIT_UNEXPECTED_ERROR = "REMOTE_SUBMIT_UNEXPECTED_ERROR"  # 提交作业未预期异常

    # 远程调用失败 - 轮询阶段
    REMOTE_POLL_NETWORK_ERROR = "REMOTE_POLL_NETWORK_ERROR"  # 轮询状态时网络错误
    REMOTE_POLL_TIMEOUT = "REMOTE_POLL_TIMEOUT"  # 轮询超时
    REMOTE_POLL_HTTP_4XX = "REMOTE_POLL_HTTP_4XX"  # 轮询状态 HTTP 4xx 错误
    REMOTE_POLL_HTTP_5XX = "REMOTE_POLL_HTTP_5XX"  # 轮询状态 HTTP 5xx 错误
    REMOTE_POLL_UNEXPECTED_ERROR = "REMOTE_POLL_UNEXPECTED_ERROR"  # 轮询状态未预期异常
    REMOTE_JOB_UNKNOWN = "REMOTE_JOB_UNKNOWN"  # 远程作业状态未知
    REMOTE_JOB_FAILED = "REMOTE_JOB_FAILED"  # 远程作业执行失败

    # 远程调用失败 - 结果下载阶段
    REMOTE_DOWNLOAD_NETWORK_ERROR = "REMOTE_DOWNLOAD_NETWORK_ERROR"  # 下载结果时网络错误
    REMOTE_DOWNLOAD_TIMEOUT = "REMOTE_DOWNLOAD_TIMEOUT"  # 下载结果超时
    REMOTE_DOWNLOAD_HTTP_4XX = "REMOTE_DOWNLOAD_HTTP_4XX"  # 下载结果 HTTP 4xx 错误
    REMOTE_DOWNLOAD_HTTP_5XX = "REMOTE_DOWNLOAD_HTTP_5XX"  # 下载结果 HTTP 5xx 错误
    REMOTE_DOWNLOAD_UNEXPECTED_ERROR = "REMOTE_DOWNLOAD_UNEXPECTED_ERROR"  # 下载结果未预期异常

    # 通用失败码
    UNKNOWN_ERROR = "UNKNOWN_ERROR"  # 未知错误


class ErrorMeta(TypedDict, total=False):
    """标准化错误元数据结构

    用于在 StepResult.error_details 中存储统一的失败信息。
    所有字段都是可选的，但建议尽可能填充以便追踪和调试。
    """

    failure_code: str  # 标准失败码（FailureCode 枚举值）
    phase: str  # 失败阶段（如 "adapter_lookup", "input_resolution", "tool_execution", "safety_precheck" 等）
    timestamp: str  # 失败时间戳（ISO 8601 格式）

    # 远程调用相关信息
    remote_job_id: Optional[str]  # 远程作业 ID
    remote_endpoint: Optional[str]  # 远程服务端点
    http_status_code: Optional[int]  # HTTP 状态码

    # 上下文信息
    retry_count: Optional[int]  # 重试次数
    max_retries: Optional[int]  # 最大重试次数

    # 原始异常信息
    exception_type: Optional[str]  # 异常类型
    exception_message: Optional[str]  # 异常消息

    # 附加上下文（可扩展）
    context: Optional[Dict[str, Any]]  # 额外上下文信息


class RunnerError(RuntimeError):
    """执行流程中的基类异常，携带统一的失败分类与错误码"""

    def __init__(
        self,
        failure_type: FailureType,
        message: str,
        *,
        code: Optional[str] = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_type = failure_type
        self.code = code or failure_type.value
        self.__cause__ = cause

    def __repr__(self) -> str:  # pragma: no cover - 辅助调试
        return (
            f"{self.__class__.__name__}"
            f"(failure_type={self.failure_type}, code={self.code}, message={self.args[0]!r})"
        )


class StepRunError(RunnerError):
    """单步执行过程中产生的异常"""


class PlanRunError(RunnerError):
    """Plan 级执行异常，保留触发的 step_id"""

    def __init__(
        self,
        failure_type: FailureType,
        message: str,
        *,
        step_id: str | None = None,
        code: Optional[str] = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(failure_type, message, code=code, cause=cause)
        self.step_id = step_id

    @classmethod
    def from_step_error(cls, step_id: str, error: StepRunError) -> "PlanRunError":
        return cls(
            failure_type=error.failure_type,
            message=str(error),
            step_id=step_id,
            code=error.code,
            cause=error,
        )


def classify_exception(exc: Exception) -> FailureType:
    """将任意异常映射为 FailureType，统一重试/阻断决策的入口"""
    if isinstance(exc, RunnerError):
        return exc.failure_type

    if isinstance(exc, TimeoutError):
        return FailureType.RETRYABLE

    if isinstance(exc, ValueError):
        return FailureType.NON_RETRYABLE

    return FailureType.TOOL_ERROR


def is_retryable_failure(failure_type: FailureType) -> bool:
    """静态判定某失败分类是否"理论上可重试"

    不包含重试次数、FSM 状态或 patch/replan 决策，仅用于粗粒度决策。
    """
    return failure_type == FailureType.RETRYABLE


def build_error_meta(
    failure_code: str | FailureCode,
    phase: str,
    *,
    timestamp: Optional[str] = None,
    remote_job_id: Optional[str] = None,
    remote_endpoint: Optional[str] = None,
    http_status_code: Optional[int] = None,
    retry_count: Optional[int] = None,
    max_retries: Optional[int] = None,
    exception_type: Optional[str] = None,
    exception_message: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ErrorMeta:
    """构建标准化的错误元数据

    统一构建 StepResult.error_details 的辅助函数，确保失败信息结构一致。

    Args:
        failure_code: 标准失败码（FailureCode 枚举值或字符串）
        phase: 失败阶段
        timestamp: 失败时间戳（ISO 8601 格式），如果未提供则使用当前时间
        remote_job_id: 远程作业 ID（远程调用失败时）
        remote_endpoint: 远程服务端点（远程调用失败时）
        http_status_code: HTTP 状态码（远程调用失败时）
        retry_count: 重试次数
        max_retries: 最大重试次数
        exception_type: 原始异常类型
        exception_message: 原始异常消息
        context: 额外上下文信息

    Returns:
        ErrorMeta: 标准化的错误元数据字典
    """
    from datetime import datetime, timezone

    # 规范化 failure_code
    if isinstance(failure_code, FailureCode):
        failure_code_str = failure_code.value
    else:
        failure_code_str = str(failure_code)

    # 如果未提供 timestamp，使用当前时间
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    # 构建基础元数据
    meta: ErrorMeta = {
        "failure_code": failure_code_str,
        "phase": phase,
        "timestamp": timestamp,
    }

    # 添加可选字段（仅添加非 None 的字段）
    if remote_job_id is not None:
        meta["remote_job_id"] = remote_job_id
    if remote_endpoint is not None:
        meta["remote_endpoint"] = remote_endpoint
    if http_status_code is not None:
        meta["http_status_code"] = http_status_code
    if retry_count is not None:
        meta["retry_count"] = retry_count
    if max_retries is not None:
        meta["max_retries"] = max_retries
    if exception_type is not None:
        meta["exception_type"] = exception_type
    if exception_message is not None:
        meta["exception_message"] = exception_message
    if context is not None:
        meta["context"] = context

    return meta
