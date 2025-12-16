"""
step_runner.py

本模块定义 StepRunner 的对外接口与行为契约

职责概述：

- 解析 PlanStep.inputs
- 调用底层执行后端(目前使用 dummy 执行， 后续会接入 ToolAdapter + Nextflow)
- 根据统一数据契约生成 StepResult, 并写入：
    - task_id / step_id / tool
    - status
    - outputs / metrics
    - risk_flags
    - logs_path
    - timestamp
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict

from src.models.contracts import PlanStep, StepResult
from src.workflow.context import WorkflowContext
from src.agents.safety import SafetyAgent
from src.workflow.errors import FailureType, StepRunError, classify_exception

__all__ = ["StepRunner"]

# 引用前缀常量：用于识别步骤引用格式（如 "S1.sequence"）
STEP_REF_PREFIX = "S"


class StepRunner:
    """负责执行单个 PlanStep 的执行器(微循环的最小单元)

    核心公开方法:
    - run_step(step, context) -> StepResult

    行为契约:
    1. 输入
        - step: Planner生成的PlanStep,对应一个工具调用
        - context: WorkflowContext, 包含当前任务、已完成步骤的结果等上下文信息
    2. 输入解析
        - 支持字面量，例如 {"temprature": 0.8}
        - 支持引用语义: 例如 {"sequence": "S1.sequence"}
            - "s1.sequence"表示：使用 WorkflowContext.step_results["S1"].outputs["sequence"]
            - 若引用格式非法或引用不存在，必须抛出 StepRunError 并标记为不可重试
    3. 执行逻辑
        - A1阶段不对接真实工具，仅模拟执行
        - 未来版本会通过 ToolAdapter + WorkflowEngineAdapter 接入 ProteinMPNN/ESMFold等真实工具
    4. 输出
        - 返回一个StepResult实例，并满足:
            - task_id == context.task.task_id
            - step_id == step.id
            - tool == step.tool
            - status == "success"（若输入解析失败则返回 failed）
            - outputs:
                - 必须至少包含：
                    - "dummy_output": str, 模拟执行的输出内容
                    - "inputs": Dict[str, Any], 为解析之后的输入字典
            - metrics:
                - 至少包含：
                    - "exec_type": "dummy"
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
    
    def __init__(self, safety_agent: SafetyAgent | None = None) -> None:
        """初始化 StepRunner
        
        Args:
            safety_agent: 可选，安全检查器。如果为 None，则使用默认的 SafetyAgent 实例
        """
        # A4: 默认使用真实 SafetyAgent, 便于生产代码
        from src.agents.safety import SafetyAgent as DefaultSafetyAgent
        self._safety_agent: SafetyAgent = safety_agent or DefaultSafetyAgent()

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        """执行单个 PlanStep, 返回标准化的 StepResult

        Args:
            step: 需要执行的计划步骤
            context: 当前任务的工作流上下文
        Returns:
            StepResult: 本步骤的执行结果
        Raises:
            StepRunError: 当安全阻断/输入解析失败/执行异常时
        """
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
                error_details={"code": "SAFETY_PRE_BLOCK", "phase": "safety_precheck"},
                outputs={},
                metrics={
                    "exec_type": "safety_precheck",
                    "duration_ms": duration_ms,
                },
                risk_flags=pre_safety_result.risk_flags,
                logs_path=None,
                timestamp=now_iso,
            )
        
        # 解析输入
        try:
            resolved_inputs = self._resolve_inputs(step, context)
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
                error_details={"phase": "input_resolution"},
                outputs={},
                metrics={
                    "exec_type": "input_resolution",
                    "duration_ms": duration_ms,
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso,
            )

        # A1: 执行工具（当前为 dummy，未来接 ToolAdapter / WorkflowEngine）
        try:
            dummy_output = self._execute_tool(step, resolved_inputs)
            outputs_payload = {
                "dummy_output": dummy_output,
                "inputs": resolved_inputs,
            }
            self._validate_outputs(step, outputs_payload)
        except StepRunError as exc:
            duration_ms = int((perf_counter() - t0) * 1000)
            now_iso = datetime.now(timezone.utc).isoformat()
            # 工具失败（可重试/不可重试由 failure_type 决定）
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="failed",
                failure_type=exc.failure_type,
                error_message=str(exc),
                error_details={"code": getattr(exc, "code", None), "phase": "tool_execution"},
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
                error_details={"phase": "tool_execution"},
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
            outputs={
                "dummy_output": dummy_output,
                "inputs": resolved_inputs,
            },
            metrics={
                "exec_type": "dummy",
                "duration_ms": duration_ms,
            },
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
                error_details={"code": "SAFETY_POST_BLOCK", "phase": "safety_postcheck"},
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
            outputs={
                "dummy_output": dummy_output,
                "inputs": resolved_inputs,
            },
            metrics={
                "exec_type": "dummy",
                "duration_ms": duration_ms,
            },
            risk_flags=risk_flags,
            logs_path=None,
            timestamp=now_iso,
        )

        return result

    def _add_safety_event(self, context: WorkflowContext, event) -> None:
        """安全事件写入上下文，兼容两种 WorkflowContext 形态"""
        if hasattr(context, 'add_safety_event'):
            context.add_safety_event(event)
        else:
            context.safety_events.append(event)

    def _resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        """解析 step.inputs

        将字面量保持原样拷贝
        将 "Sx.key" 的形式解析为 context.step_results["Sx"].outputs["key"]

       解析规则:
       - 若值为字符串且包含一个 '.', 且看起来像是引用形式 "Sx.key":
            - 尝试按引用解析:
                - step_id, field = val.split(".", 1)
                - 检查 step_id 是否存在（使用 context.has_step_result）
                - 使用 context.get_step_output(step_id, field) 获取值
            - 若解析失败，抛出 ValueError，包含详细的错误信息
       - 其他情况保持原样拷贝

        Args:
            step: 计划步骤
            context: 工作流上下文
        Returns:
            Dict[str, Any]: 已经解析的输入字典
        Raises:
            ValueError: 当引用格式非法或目标不存在时
        """

        resolved: Dict[str, Any] = {}

        for key, val in step.inputs.items():
            # 仅对形如 "Sx.key" 的字符串尝试做引用解析
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)

                # 简单过滤: 只有当 step_id 非空且以 "S" 开头时才尝试当作引用
                # 其他情况按字面量处理，避免损伤正常字符串
                if step_id and step_id.startswith(STEP_REF_PREFIX):
                    # 检查步骤是否存在，提供更清晰的错误信息
                    if not context.has_step_result(step_id):
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': step '{step_id}' not found in context"
                        )
                    
                    try:
                        resolved_value = context.get_step_output(step_id, field)
                    except KeyError as exc:
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                        ) from exc
                    resolved[key] = resolved_value
                    continue
            # 其他情况按字面量处理
            resolved[key] = val

        # 返回解析后的输入字典
        return resolved

    def _execute_tool(self, step: PlanStep, resolved_inputs: Dict[str, Any]) -> str:
        """执行工具的占位实现

        未来将替换为 ToolAdapter / WorkflowEngine 调用。
        返回 dummy 输出字符串；单测可通过 monkeypatch 覆盖以模拟工具失败/异常。
        """
        return f"executed {step.tool}"

    def _validate_outputs(self, step: PlanStep, outputs: Dict[str, Any]) -> None:
        """最小 IO 契约校验：必需字段存在且类型合理"""
        if not isinstance(outputs, dict):
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Tool outputs is not a dict",
                code="OUTPUT_NOT_DICT",
            )

        required = step.metadata.get("required_outputs", []) if step.metadata else []
        for key in required:
            if key not in outputs:
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Missing required output field '{key}'",
                    code="OUTPUT_MISSING",
                )

        type_hints: Dict[str, str] = step.metadata.get("output_types", {}) if step.metadata else {}
        for key, expected in type_hints.items():
            if key in outputs and not self._type_matches(outputs[key], expected):
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Output field '{key}' type mismatch, expected {expected}",
                    code="OUTPUT_TYPE_MISMATCH",
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
