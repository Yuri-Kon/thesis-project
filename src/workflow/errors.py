"""
错误分类与运行期异常定义

为 StepRunner / PlanRunner 提供统一的失败类型枚举，区分：
- 可重试任务
- 不可重试任务
- 工具异常
- 安全阻断
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

__all__ = [
    "FailureType",
    "RunnerError",
    "StepRunError",
    "PlanRunError",
    "classify_exception",
    "is_retryable_failure",
]


class FailureType(str, Enum):
    """执行失败分类"""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    TOOL_ERROR = "tool_error"
    SAFETY_BLOCK = "safety_block"


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
    """静态判定某失败分类是否“理论上可重试”

    不包含重试次数、FSM 状态或 patch/replan 决策，仅用于粗粒度决策。
    """
    return failure_type == FailureType.RETRYABLE
