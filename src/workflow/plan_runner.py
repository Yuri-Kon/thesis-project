from __future__ import annotations
from typing import Protocol
from src.models.contracts import Plan, StepResult
from src.models.db import TaskStatus
from src.workflow.context import WorkflowContext
from src.workflow.step_runner import StepResult, StepRunner

class StepRunnerLike(Protocol):
    """最小化约束的 StepRunner 接口，用于依赖注入和单元测试"""

    def run_step(self, step, context: WorkflowContext) -> StepResult:
        """执行单个 PlanStep,返回 StepResult
        
        真实实现由 src/workflow/step_runner.StepRunner 提供
        """

class PlanRunner:
    """PlanRunner: 顺序执行 Plan.steps, 并回写 WorkflowContext, 管理任务状态
    
    实现最小闭环的行为: 依次执行 Plan 中的步骤
    使用 StepRunner 执行每个步骤，并将执行结果写入 WorkflowContext
    同时管理 TaskStatus 状态转换

    Attributes:
        step_runner(StepRunner):
            通过构造函数注入的步骤执行器，需实现
            ``run_step(step, context) -> StepResult``
    
    Version:
        v2(A3扩展): 在 v1 基础上增加 TaskStatus 状态管理
        
        完整状态机流程 (CREATED → PLANNING → PLANNED → RUNNING → SUMMARIZING → DONE/FAILED):
        - CREATED → PLANNING: 由 PlannerAgent 负责（任务创建后开始规划）
        - PLANNING → PLANNED: 由 PlannerAgent 负责（规划完成，生成 Plan）
        - PLANNED → RUNNING: 由 PlanRunner 负责（开始执行计划）
        - RUNNING → SUMMARIZING: 由 SummarizerAgent 负责（执行完成，开始汇总）
        - SUMMARIZING → DONE/FAILED: 由 SummarizerAgent 负责（汇总完成，任务结束）
        
        PlanRunner 的状态转换职责:
        - 主要职责: 当 ``context.status == PLANNED`` 时，更新为 ``RUNNING``
        - 其他状态: 若 ``context.status`` 不是 ``PLANNED``，PlanRunner 不改变状态
          （允许上层已经设置状态的情况，例如已经是 RUNNING 或终端状态）
        - 终端状态保护: 若 ``context.status`` 为 ``DONE`` 或 ``FAILED``，保持状态不变
          （终端状态不应被 PlanRunner 改变）
        
        - 输入：
            - plan(Plan)
            - context(WorkflowContext)
                要求: ``context.task.task_id == plan.task_id``
                ``context.plan`` 允许为 ``None``, PlanRunner 会负责写入
                ``context.status`` 建议为 ``PLANNED``，表示计划已生成，可以开始执行
                但也支持其他状态（如 ``CREATED``, ``RUNNING`` 等），PlanRunner 会根据状态决定是否更新
        - 行为:
            1. 状态预检查与更新:
                - 若 ``context.status == PLANNED``, 则更新为 ``RUNNING``
                - 若 ``context.status`` 不是 ``PLANNED``，仍会执行步骤，但不更新状态
                   （允许上层已经设置状态的情况，例如已经是 RUNNING 或终端状态）
            2. 若 ``context.plan`` 为 ``None``, 则设置为当前 plan;
                若已有值，则不覆盖
            3. 按 ``plan.steps`` 顺序依次执行:
                - 对每个step:
                    - 调用 ``self._step_runner.run_step(step, context)``
                    - 将 StepResult 写入 ``context.step_results[step_id]``
            4. 执行完成后:
                - 状态保持为执行时的状态（通常是 RUNNING，如果初始状态是 PLANNED）
                - （SUMMARIZING 和 DONE/FAILED 状态由 SummarizerAgent 或上层逻辑负责更新）
            5. 异常处理:
                - 若 step_runner 抛出异常，PlanRunner 不捕获，直接向上抛给调用方处理
                - 异常发生时，状态保持为执行时的状态（通常是 RUNNING，如果初始状态是 PLANNED）
                - 上层调用方负责根据异常情况决定是否更新为 FAILED
        - 输出:
            - 返回原始 ``plan`` 对象(为未来支持 Patch/Replan 留接口)
        
        Future Work:
            - SafetyAgent: 将在 A4 中加入 step pre/post 检查并写入 SafetyResult
            - 失败类型区分与 Patch/Replan: 将在 Week4 基于核心算法规约接入完整的 Plan Runner 逻辑
            - 状态回滚: 未来可能需要在异常时支持状态回滚机制
    """
    def __init__(self, step_runner: StepRunnerLike | None = None)-> None:
        # 默认使用真实 StepRunner, 便于生产代码
        self._step_runner: StepRunnerLike = step_runner or StepRunner()
    
    def run_plan(self, plan: Plan, context: WorkflowContext) -> Plan:
        """执行给定的 Plan, 顺序遍历 plan.steps, 调用 StepRunner 并写入 WorkflowContext
        
        同时管理 TaskStatus 状态转换：
        - 如果 context.status 为 PLANNED，则更新为 RUNNING（主要职责）
        - 如果 context.status 不是 PLANNED，保持原状态不变（允许上层已设置状态）
        - 执行完成后，状态保持为执行时的状态（通常是 RUNNING）
        
        Args:
            plan: 要执行的计划对象
            context: 工作流上下文，包含任务信息、当前状态等
            
        Returns:
            Plan: 返回原始 plan 对象（为未来支持 Patch/Replan 预留接口）
            
        Raises:
            ValueError: 当 context.task.task_id 与 plan.task_id 不一致时
            RuntimeError: 当 step_runner 执行步骤时抛出异常（直接向上传播）
            
        Note:
            - 状态转换遵循完整状态机流程：CREATED → PLANNING → PLANNED → RUNNING → SUMMARIZING → DONE/FAILED
            - PlanRunner 主要负责 PLANNED → RUNNING 的转换
            - 其他状态转换由相应的 Agent 负责（PlannerAgent、SummarizerAgent 等）
        """
        # 基本一致性校验：task_id 必须一致
        if context.task.task_id != plan.task_id:
            raise ValueError(
                f"WorkflowContext.task.task_id ({context.task.task_id}) "
                f"does not match Plan.task_id ({plan.task_id})"
            )
        
        # A3: 状态更新 - 如果状态为 PLANNED，则更新为 RUNNING
        if context.status == TaskStatus.PLANNED:
            context.status = TaskStatus.RUNNING
        
        # 若 context.plan 为 None, 则设置为当前 plan
        if context.plan is None:
            context.plan = plan
        
        # 顺序执行 steps, 并将 StepResult 写回 context.step_results
        for step in plan.steps:
            step_result = self._step_runner.run_step(step, context)
            context.step_results[step_result.step_id] = step_result
        
        # A3: 执行完成后，状态保持为 RUNNING
        # （SUMMARIZING 和 DONE/FAILED 由 SummarizerAgent 或上层逻辑负责）
        
        # 返回原始 plan(为未来支持 Patch/Replan 预留接口)
        return plan
