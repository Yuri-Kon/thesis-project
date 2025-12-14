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
            - 若引用格式非法或引用不存在，必须抛出 ValueError
    3. 执行逻辑
        - A1阶段不对接真实工具，仅模拟执行
        - 未来版本会通过 ToolAdapter + WorkflowEngineAdapter 接入 ProteinMPNN/ESMFold等真实工具
    4. 输出
        - 返回一个StepResult实例，并满足:
            - task_id == context.task.task_id
            - step_id == step.id
            - tool == step.tool
            - status == "success" (A1 阶段无失败分支)
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
            ValueError: 当 step.inputs 中存在无法解析的引用时
        """
        # A4: 安全检查 - 步骤执行前
        pre_safety_result = self._safety_agent.check_pre_step(step, context)
        # 兼容两种 WorkflowContext 类型
        if hasattr(context, 'add_safety_event'):
            context.add_safety_event(pre_safety_result)
        else:
            context.safety_events.append(pre_safety_result)
        
        # 记录开始时间，用于 duration_ms
        t0 = perf_counter()

        # 解析输入
        resolved_inputs = self._resolve_inputs(step, context)

        # A1: dummy 执行逻辑
        # 未来这里会根据 step.tool 调用对应的 ToolAdapter / WorkflowEngineAdapter
        dummy_output = f"executed {step.tool}"

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
        # 兼容两种 WorkflowContext 类型
        if hasattr(context, 'add_safety_event'):
            context.add_safety_event(post_safety_result)
        else:
            context.safety_events.append(post_safety_result)
        
        # 从 post_safety_result 中提取 risk_flags
        risk_flags = post_safety_result.risk_flags

        # 构造最终的 StepResult，包含安全检查结果
        result = StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
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
