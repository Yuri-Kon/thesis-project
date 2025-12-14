from __future__ import annotations

from src.models.contracts import Plan, StepResult
from src.workflow.context import WorkflowContext
from src.workflow.step_runner import StepRunner
from src.workflow.plan_runner import PlanRunner


class ExecutorAgent:
    """计划执行者与调度器，负责执行 Plan 并调用工具适配器
    
    当前实现：
    - 使用 StepRunner 执行单个步骤，支持输入解析（包括引用语义）
    - 使用 PlanRunner 执行完整计划，包含安全检查、状态管理等功能
    后续将通过 Adapter 调用真实工具（ESMFold、ProteinMPNN等）
    """

    def __init__(self, plan_runner: PlanRunner | None = None):
        """初始化 ExecutorAgent
        
        Args:
            plan_runner: 可选的 PlanRunner 实例。如果为 None，则创建默认实例。
        """
        self.step_runner = StepRunner()
        # 使用 PlanRunner 来执行完整计划，它包含安全检查、状态管理等功能
        self.plan_runner = plan_runner or PlanRunner(step_runner=self.step_runner)

    def run_step(self, step_id: str, context: WorkflowContext) -> StepResult:
        """执行单个步骤
        
        使用 StepRunner 来执行步骤，支持输入解析（包括引用语义）。
        
        Args:
            step_id: 步骤ID
            context: 工作流上下文
            
        Returns:
            StepResult: 步骤执行结果
            
        Raises:
            AssertionError: 当 context.plan 为 None 时
            StopIteration: 当 step_id 不存在时
            ValueError: 当输入引用无法解析时
        """
        assert context.plan is not None, "Plan must be set in context"
        step = next(s for s in context.plan.steps if s.id == step_id)

        # 使用 StepRunner 执行步骤，它会处理输入解析和执行逻辑
        result = self.step_runner.run_step(step, context)
        
        # 将结果添加到上下文中
        # 使用增强版 WorkflowContext 的 add_step_result 方法（如果可用），否则直接操作字典
        if hasattr(context, 'add_step_result'):
            context.add_step_result(result)
        else:
            context.step_results[step.id] = result
        
        return result

    def run_plan(self, plan: Plan, context: WorkflowContext) -> Plan:
        """执行完整计划
        
        使用 PlanRunner 来执行计划，它包含安全检查、状态管理等功能。
        
        Args:
            plan: 执行计划
            context: 工作流上下文
            
        Returns:
            Plan: 执行后的计划（当前实现不做修改）
        """
        # 使用 PlanRunner 执行计划，它包含安全检查、状态管理等功能
        return self.plan_runner.run_plan(plan, context)
