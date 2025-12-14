"""
safety.py

本模块定义 SafetyAgent 的接口和实现，负责全程安全审查。

职责概述：
- 在任务输入阶段进行安全检查（task_input）
- 在步骤执行前进行安全检查（pre_step）
- 在步骤执行后进行安全检查（post_step）
- 在最终结果阶段进行安全检查（final_result）

A4 阶段：实现接口框架和伪实现，返回 SafetyResult 占位。
"""
from __future__ import annotations

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    SafetyResult,
    RiskFlag,
    now_iso,
)
from src.workflow.context import WorkflowContext

__all__ = ["SafetyAgent"]


class SafetyAgent:
    """全程安全审查者，负责输入/过程/输出的风险识别与阻断
    
    在任务执行的不同阶段进行安全检查：
    - task_input: 检查任务输入（任务创建后，计划执行前）
    - pre_step: 检查步骤执行前的输入（每个步骤执行前）
    - post_step: 检查步骤执行后的输出（每个步骤执行后）
    - final_result: 检查最终结果（所有步骤执行完成后）
    
    A4 阶段实现：
    - 提供完整的接口定义
    - 实现伪实现，返回占位的 SafetyResult
    - 后续阶段将接入真实的安全检查规则和策略
    
    Attributes:
        无（A4 阶段暂不需要配置）
    """

    def check_task_input(
        self, task: ProteinDesignTask, plan: Plan | None = None
    ) -> SafetyResult:
        """检查任务输入阶段的安全性
        
        在任务创建后、计划执行前进行安全检查，验证：
        - 任务目标是否合法
        - 约束条件是否合理
        - 是否存在明显的安全风险
        
        Args:
            task: 蛋白质设计任务
            plan: 可选，已生成的计划（如果已生成）
            
        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作
            
        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=task.task_id,
            phase="input",
            scope="task",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_pre_step(
        self, step: PlanStep, context: WorkflowContext
    ) -> SafetyResult:
        """检查步骤执行前的安全性
        
        在每个步骤执行前进行安全检查，验证：
        - 步骤输入是否符合安全规范
        - 工具选择是否安全
        - 是否存在已知的安全风险
        
        Args:
            step: 即将执行的计划步骤
            context: 工作流上下文，包含任务信息、已完成步骤结果等
            
        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作
            
        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
            如果 action 为 "block"，调用方应该阻止步骤执行
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_post_step(
        self, step: PlanStep, step_result: StepResult, context: WorkflowContext
    ) -> SafetyResult:
        """检查步骤执行后的安全性
        
        在每个步骤执行后进行安全检查，验证：
        - 步骤输出是否符合安全规范
        - 是否存在风险序列或结构
        - 是否违反约束条件
        
        Args:
            step: 已执行的计划步骤
            step_result: 步骤执行结果
            context: 工作流上下文，包含任务信息、已完成步骤结果等
            
        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作
            
        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
            如果 action 为 "block"，调用方应该考虑触发重规划
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_final_result(
        self, context: WorkflowContext, design_result: DesignResult | None = None
    ) -> SafetyResult:
        """检查最终结果的安全性
        
        在所有步骤执行完成后进行最终安全检查，验证：
        - 最终设计结果是否符合安全规范
        - 是否存在高风险序列或结构
        - 是否满足所有约束条件
        
        Args:
            context: 工作流上下文，包含任务信息、所有步骤结果等
            design_result: 可选，已生成的最终设计结果（如果已生成）
            
        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作
            
        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
            如果 action 为 "block"，调用方应该考虑触发重规划或拒绝结果
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=context.task.task_id,
            phase="output",
            scope="result",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )
