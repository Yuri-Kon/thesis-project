from __future__ import annotations

from src.models.contracts import Plan, WorkflowContext, StepResult
from src.workflow.step_runner import StepRunner


class ExecutorAgent:
    """最小可用 ExecutorAgent：顺序执行 Plan，每一步生成一个假的 StepResult
    
    当前实现：使用 StepRunner 执行步骤，支持输入解析（包括引用语义）
    后续将通过 Adapter 调用真实工具（ESMFold、ProteinMPNN等）
    """

    def __init__(self):
        """初始化 ExecutorAgent，创建 StepRunner 实例"""
        self.step_runner = StepRunner()

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
        # 注意：如果 context 是 src.workflow.context.WorkflowContext，可以使用 add_step_result
        # 但为了兼容 src.models.contracts.WorkflowContext，直接操作字典
        context.step_results[step.id] = result
        
        return result

    def run_plan(self, plan: Plan, context: WorkflowContext) -> Plan:
        """执行完整计划
        
        Args:
            plan: 执行计划
            context: 工作流上下文
            
        Returns:
            Plan: 执行后的计划（当前实现不做修改）
        """
        context.plan = plan
        for step in plan.steps:
            self.run_step(step.id, context)
        return plan
