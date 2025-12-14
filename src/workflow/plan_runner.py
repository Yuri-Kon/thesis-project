from __future__ import annotations
from typing import Protocol
from src.models.contracts import Plan, StepResult
from src.workflow.context import WorkflowContext
from src.workflow.step_runner import StepRunner

class StepRunnerLike(Protocol):
    """最小化约束的 StepRunner 接口，用于依赖注入和单元测试"""

    def run_step(self, step, context: WorkflowContext) -> StepResult:
        """执行单个 PlanStep,返回 StepResult
        
        真实实现由 src/workflow/step_runner.StepRunner 提供
        """

class PlanRunner:
    """ PlanRunner v1: 顺序执行 Plan.steps, 并回写 WorkflowContext
    
    实现最小闭环的行为(v1版本): 依次执行 Plan 中的步骤
    使用 StepRunner 执行每个步骤，并将执行结果写入 WorkflowContext
    不包含安全检查、状态机更新、Patch、Replan 等高级逻辑

    Attributes:
        step_runner(StepRunner):
            通过构造函数注入的步骤执行器，需实现
            ``run_step(step, context) -> StepResult``
    Notes:
        本类为 v1 范围的 PlanRunner 实现，仅支持最基础的顺序执行 + 上下文写入，未来会在
        此基础上逐步扩展
    Version:
        v1(当前范围)
        - 输入：
            - plan(Plan)
            - context(WorkflowContext)
                要求: ``context.task.task_id == plan.tas_id``
                ``context.plan`` 允许为 ``None``, PlanRunner 会负责写入
        - 行为:
            1. 若 ``context.plan`` 为 ``None``, 则设置为当前 plan;
                若已有值，则不覆盖
            2. 按 ``plan.steps`` 顺序依次执行:
                - 对每个step:
                    - 调用 ``self.step_runnner.run_step(step, context)``
                    - 将 StepResult 写入 ``context.step_results[step_id]``
            3. 不执行安全检查
            4. 若 step_runner 抛出异常，PlanRunner 不捕获，直接向上抛给调用方处理
        - 输出:
            - 返回原始 ``plan`` 对象(为未来支持 Patch/Replan 留接口)
        
        Future Work:
            以下内容不属于 v1, 但预留扩展方向:
            - TaskStatus 状态机: 将在A3中扩展执行前后的状态更新
            - SafetyAgent: 将在 A4 中加入 step pre/post 检查并写入 SafetyResult
            - 失败类型区分与 Patch/Replan: 将在 Week4 基于 和核心算法规约接入完整的 Plan Runner 逻辑
    """
    def __init__(self, step_runner: StepRunnerLike | None = None)-> None:
        # 默认使用真实 StepRunner, 便于生产代码
        self._step_runner: StepRunnerLike = step_runner or StepRunner()
    
    def run_plan(self, plan: Plan, context: WorkflowContext)->Plan:
        """执行给定的 Plan, 顺序遍历 plan.steps, 调用 StepRunner 并写入 WorkflowContext"""
        # 基本一致性校验：task_id 必须一直
        if context.task.task_id != plan.task_id:
            raise ValueError(
                f"WorkflowContext.task.task_id ({context.task.task_id}) "
                f"does not match Plan.task_id ({plan.task_id})"
            )
        # 若 context.plan 为 None, 则设置为当前 plan
        if context.plan is None:
            context.plan = plan
        
        # 顺序执行 steps, 并将 StepResult 写回 context.step_results
        for step in plan.steps:
            step_result = self._step_runner.run_step(step, context)
            context.step_results[step_result.step_id] = step_result
        
        # v1 输出: 返回原始 plan(为未来更新后的 plan 预留接口)
        return plan
