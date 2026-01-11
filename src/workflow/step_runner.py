"""
step_runner.py

本模块定义 StepRunner 的对外接口与行为契约

职责概述：

- 通过 ToolAdapter 解析 PlanStep.inputs
- 通过 ToolAdapter 调用工具执行入口
- 根据统一数据契约生成 StepResult, 并写入：
    - task_id / step_id / tool
    - status
    - outputs / metrics
    - risk_flags
    - logs_path
    - timestamp
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter, sleep
from typing import Any, Callable, Dict

from src.models.contracts import PlanStep, StepResult
from src.adapters.registry import get_adapter
from src.workflow.context import WorkflowContext
from src.agents.safety import SafetyAgent
from src.workflow.errors import (
    FailureType,
    FailureCode,
    StepRunError,
    is_retryable_failure,
    build_error_meta,
)

__all__ = ["StepRunner", "StepRetryPolicy"]

@dataclass(frozen=True)
class StepRetryPolicy:
    """静态步骤级重试策略，不与 FSM / Patch / Replan 耦合"""

    max_attempts: int = 2
    # 失败后到下一次尝试的等待时间（毫秒），索引按尝试序号-1 截断使用
    backoff_schedule_ms: tuple[int, ...] = (1000, 3000)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        object.__setattr__(self, "backoff_schedule_ms", tuple(self.backoff_schedule_ms))

    def backoff_ms_for(self, attempt_index: int) -> int:
        """返回当前尝试后的等待时间（毫秒），未配置则为0"""
        if not self.backoff_schedule_ms:
            return 0
        idx = min(max(attempt_index - 1, 0), len(self.backoff_schedule_ms) - 1)
        return max(self.backoff_schedule_ms[idx], 0)


DEFAULT_STEP_RETRY_POLICY = StepRetryPolicy()


@dataclass(frozen=True)
class AttemptRecord:
    """单次尝试的摘要记录，便于日志与测试校验"""

    attempt: int
    status: str
    failure_type: Any
    error_message: Any

    def as_dict(self) -> Dict[str, Any]:
        return {
            "attempt": self.attempt,
            "status": self.status,
            "failure_type": self.failure_type,
            "error_message": self.error_message,
        }


class StepRunner:
    """负责执行单个 PlanStep 的执行器(微循环的最小单元)

    核心公开方法:
    - run_step(step, context) -> StepResult（内置步骤级重试）

    行为契约:
    1. 输入
        - step: Planner生成的PlanStep,对应一个工具调用
        - context: WorkflowContext, 包含当前任务、已完成步骤的结果等上下文信息
    2. 输入解析
        - 由 ToolAdapter.resolve_inputs 负责
        - 支持字面量与引用语义（如 "S1.sequence"）
    3. 执行逻辑
        - 通过 AdapterRegistry 获取 ToolAdapter
        - 使用 adapter.run_local 执行工具
    4. 输出
        - 返回一个StepResult实例，并满足:
            - task_id == context.task.task_id
            - step_id == step.id
            - tool == step.tool
            - status == "success"（若输入解析失败则返回 failed）
            - metrics:
                - 至少包含：
                    - "exec_type": "adapter_local" (若适配器未提供)
                    - "duration_ms": int
            - risk_flags:
                - A4阶段：从 SafetyAgent.post_step 检查结果中提取
            - logs_path:
                - A1 阶段可以为 None
            - timestamp: ISO 8601 时间字符串
    
    A4 扩展:
        - 接入 SafetyAgent，在执行前检查 pre_step，执行后检查 post_step
        - SafetyResult 写入 context.safety_events
        - 从 post_step 的 SafetyResult 中提取 risk_flags 写入 StepResult
    """
    
    def __init__(
        self,
        safety_agent: SafetyAgent | None = None,
        retry_policy: StepRetryPolicy | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        """初始化 StepRunner
        
        Args:
            safety_agent: 可选，安全检查器。如果为 None，则使用默认的 SafetyAgent 实例
            retry_policy: 步骤级重试策略（静态配置），不与 FSM/Patch/Replan 耦合
            sleep_fn: 可选，重试退避的等待函数，默认使用 time.sleep，测试可注入空函数
        """
        # A4: 默认使用真实 SafetyAgent, 便于生产代码
        from src.agents.safety import SafetyAgent as DefaultSafetyAgent
        self._safety_agent: SafetyAgent = safety_agent or DefaultSafetyAgent()
        self._retry_policy: StepRetryPolicy = retry_policy or DEFAULT_STEP_RETRY_POLICY
        self._sleep_fn: Callable[[float], None] = sleep_fn or sleep

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        """执行单个 PlanStep（带静态重试），返回最终 StepResult"""
        last_result: StepResult | None = None
        attempt_logs: list[AttemptRecord] = []
        retried_any = False

        for attempt_idx in range(1, self._retry_policy.max_attempts + 1):
            result = self._run_once(step, context)
            self._annotate_attempt_meta(result, attempt_idx)
            attempt_logs.append(self._build_attempt_record(result, attempt_idx))
            last_result = result

            if result.status == "success":
                return self._finalize_success(result, attempt_logs)

            failure_type = self._normalize_failure_type(result.failure_type)
            retried_any = retried_any or attempt_idx > 1
            exhausted = attempt_idx >= self._retry_policy.max_attempts
            if failure_type is None or not is_retryable_failure(failure_type):
                return self._finalize_failure(result, attempt_logs, retried_any, exhausted)

            if exhausted:
                return self._finalize_failure(result, attempt_logs, retried_any, True)

            backoff_ms = self._retry_policy.backoff_ms_for(attempt_idx)
            if backoff_ms > 0:
                self._sleep_fn(backoff_ms / 1000)

        return self._finalize_failure(last_result, attempt_logs, retried_any, True)  # type: ignore[arg-type]

    def _run_once(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        """单次尝试的执行流程（无重试），供 run_step 调用"""
        # 记录开始时间，用于 duration_ms
        t0 = perf_counter()

        # A4: 安全检查 - 步骤执行前
        pre_safety_result = self._safety_agent.check_pre_step(step, context)
        self._add_safety_event(context, pre_safety_result)
        if pre_safety_result.action == "block":
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.SAFETY_BLOCK,
                error_message=f"SafetyAgent blocked step {step.id} before execution",
                error_details=build_error_meta(
                    failure_code=FailureCode.SAFETY_PRE_BLOCK,
                    phase="safety_precheck",
                    timestamp=now_iso,
                ),
                outputs={},
                metrics={
                    "exec_type": "safety_precheck",
                    "duration_ms": duration_ms,
                },
                risk_flags=pre_safety_result.risk_flags,
                logs_path=None,
                timestamp=now_iso,
            )
        
        # 获取适配器
        try:
            adapter = get_adapter(step.tool)
        except KeyError as exc:
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.NON_RETRYABLE,
                error_message=str(exc),
                error_details=build_error_meta(
                    failure_code=FailureCode.ADAPTER_NOT_FOUND,
                    phase="adapter_lookup",
                    timestamp=now_iso,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                ),
                outputs={},
                metrics={
                    "exec_type": "adapter_lookup",
                    "duration_ms": duration_ms,
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso,
            )

        # 解析输入
        try:
            resolved_inputs = adapter.resolve_inputs(step, context)
        except ValueError as exc:
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.NON_RETRYABLE,
                error_message=str(exc),
                error_details=build_error_meta(
                    failure_code=FailureCode.INPUT_RESOLUTION_FAILED,
                    phase="input_resolution",
                    timestamp=now_iso,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                ),
                outputs={},
                metrics={
                    "exec_type": "input_resolution",
                    "duration_ms": duration_ms,
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso,
            )

        # 通过适配器执行工具
        try:
            outputs_payload, adapter_metrics = adapter.run_local(resolved_inputs)
            self._validate_outputs(step, outputs_payload)
        except StepRunError as exc:
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            # 工具失败（可重试/不可重试由 failure_type 决定）
            # StepRunError 已经包含 code，直接使用或构建标准化元数据
            error_code = getattr(exc, "code", None)
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=exc.failure_type,
                error_message=str(exc),
                error_details=build_error_meta(
                    failure_code=error_code or FailureCode.TOOL_EXECUTION_ERROR,
                    phase="tool_execution",
                    timestamp=now_iso,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                ),
                outputs={},
                metrics={
                    "exec_type": "tool_execution",
                    "duration_ms": duration_ms,
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso,
            )
        except Exception as exc:  # 未预期异常 ⇒ 工具异常
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.TOOL_ERROR,
                error_message=f"Unexpected tool exception: {exc}",
                error_details=build_error_meta(
                    failure_code=FailureCode.TOOL_UNEXPECTED_ERROR,
                    phase="tool_execution",
                    timestamp=now_iso,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                ),
                outputs={},
                metrics={
                    "exec_type": "tool_execution",
                    "duration_ms": duration_ms,
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso,
            )

        # 计算执行时间
        duration_ms = int((perf_counter() - t0) * 1000)

        # 生成 ISO 8601 时间戳
        now_iso = datetime.now(timezone.utc).isoformat()

        metrics_payload = dict(adapter_metrics or {})
        metrics_payload.setdefault("exec_type", "adapter_local")
        metrics_payload.setdefault("duration_ms", duration_ms)

        # A4: 安全检查 - 步骤执行后
        # 先构造一个临时的 StepResult 用于安全检查
        temp_result = StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs=outputs_payload,
            metrics=metrics_payload,
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso,
        )
        
        post_safety_result = self._safety_agent.check_post_step(
            step, temp_result, context
        )
        self._add_safety_event(context, post_safety_result)
        if post_safety_result.action == "block":
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=FailureType.SAFETY_BLOCK,
                error_message=f"SafetyAgent blocked step {step.id} after execution",
                error_details=build_error_meta(
                    failure_code=FailureCode.SAFETY_POST_BLOCK,
                    phase="safety_postcheck",
                    timestamp=now_iso,
                ),
                outputs=temp_result.outputs,
                metrics={
                    "exec_type": "safety_postcheck",
                    "duration_ms": duration_ms,
                },
                risk_flags=post_safety_result.risk_flags,
                logs_path=None,
                timestamp=now_iso,
            )
        
        # 从 post_safety_result 中提取 risk_flags
        risk_flags = post_safety_result.risk_flags

        # 构造最终的 StepResult，包含安全检查结果
        result = StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs=outputs_payload,
            metrics=metrics_payload,
            risk_flags=risk_flags,
            logs_path=None,
            timestamp=now_iso,
        )

        return result

    def _normalize_failure_type(self, failure_type: Any) -> FailureType | None:
        """容忍 str/枚举/None 的混合输入，统一为 FailureType"""
        if isinstance(failure_type, FailureType):
            return failure_type
        if isinstance(failure_type, str):
            try:
                return FailureType(failure_type)
            except ValueError:
                return None
        return None

    def _add_safety_event(self, context: WorkflowContext, event) -> None:
        """安全事件写入上下文，兼容两种 WorkflowContext 形态"""
        if hasattr(context, 'add_safety_event'):
            context.add_safety_event(event)
        else:
            context.safety_events.append(event)

    def _with_retry_flags(
        self,
        result: StepResult,
        retried: bool,
        retry_exhausted: bool,
    ) -> StepResult:
        """在最终 StepResult 的 metrics 中标记重试信息，不改变 failure_type"""
        metrics = dict(result.metrics)
        if retried:
            metrics["retried"] = True
        if retry_exhausted:
            metrics["retry_exhausted"] = True
        result.metrics = metrics
        return result

    def _build_attempt_record(self, result: StepResult, attempt_idx: int) -> AttemptRecord:
        """提取单次尝试的关键信息，便于日志与测试校验"""
        return AttemptRecord(
            attempt=attempt_idx,
            status=result.status,
            failure_type=result.failure_type,
            error_message=result.error_message,
        )

    def _attach_attempt_history(self, result: StepResult, attempt_logs: list[AttemptRecord]) -> None:
        """将累计的尝试记录附加到 StepResult.metrics"""
        history = [log.as_dict() if hasattr(log, "as_dict") else log for log in attempt_logs]
        metrics = dict(result.metrics)
        metrics["attempt_history"] = history
        result.metrics = metrics

    def _annotate_attempt_meta(self, result: StepResult, attempt_idx: int) -> None:
        """确保尝试元信息存在且不覆盖既有内容"""
        metrics = dict(result.metrics)
        metrics.setdefault("attempt", attempt_idx)
        metrics.setdefault("max_attempts", self._retry_policy.max_attempts)
        result.metrics = metrics

    def _finalize_success(
        self,
        result: StepResult,
        attempt_logs: list[AttemptRecord],
    ) -> StepResult:
        """成功路径：仅附加尝试历史，不继续重试"""
        self._attach_attempt_history(result, attempt_logs)
        return result

    def _finalize_failure(
        self,
        result: StepResult,
        attempt_logs: list[AttemptRecord],
        retried: bool,
        retry_exhausted: bool,
    ) -> StepResult:
        """失败路径：附加尝试历史与重试标记，不改变 failure_type"""
        self._attach_attempt_history(result, attempt_logs)
        return self._with_retry_flags(result, retried, retry_exhausted)

    def _validate_outputs(self, step: PlanStep, outputs: Dict[str, Any]) -> None:
        """最小 IO 契约校验：必需字段存在且类型合理"""
        if not isinstance(outputs, dict):
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Tool outputs is not a dict",
                code=FailureCode.OUTPUT_NOT_DICT.value,
            )

        required = step.metadata.get("required_outputs", []) if step.metadata else []
        for key in required:
            if key not in outputs:
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Missing required output field '{key}'",
                    code=FailureCode.OUTPUT_MISSING.value,
                )

        type_hints: Dict[str, str] = step.metadata.get("output_types", {}) if step.metadata else {}
        for key, expected in type_hints.items():
            if key in outputs and not self._type_matches(outputs[key], expected):
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Output field '{key}' type mismatch, expected {expected}",
                    code=FailureCode.OUTPUT_TYPE_MISMATCH.value,
                )

    def _type_matches(self, value: Any, type_name: str) -> bool:
        """简易类型匹配，覆盖常见内置类型名称"""
        mapping = {
            "str": str,
            "int": int,
            "float": float,
            "dict": dict,
            "list": list,
            "bool": bool,
        }
        py_type = mapping.get(type_name)
        if py_type is None:
            return True  # 未知类型名时不强校验，保持宽松
        return isinstance(value, py_type)
