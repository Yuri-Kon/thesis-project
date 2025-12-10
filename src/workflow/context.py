"""
workflow/context.py

本模块定义 WorkflowContext 的增强版本，提供任务执行过程中的完整上下文管理。

职责概述：
- 存储任务生命周期中的所有关键状态
- 提供便捷的上下文访问和操作方法
- 支持步骤结果、安全检查事件和设计结果的管理
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.contracts import (
    DesignResult,
    Plan,
    ProteinDesignTask,
    SafetyResult,
    StepResult,
)

__all__ = ["WorkflowContext"]


class WorkflowContext(BaseModel):
    """单个任务在 LangGraph / ExecutorAgent 执行流程中的完整上下文
    
    该模型用于存储任务生命周期中的所有关键状态，包括: 
    原始任务定义、当前有效的计划、步骤执行结果、安全检查记录、以及最终由 SummarizerAgent 生成的设计结果

    Attributes:
        task: ProteinDesignTask
            原始任务对象，由 API 层创建
            在任务整个生命周期中保持不变
            
        plan: Optional[Plan]
            当前生效的 Plan 实例
            - 初始值为 None
            - 在 PlannerAgent 生成初始 Plan 后被赋值
            - 在 Replan 时会替换为新的 Plan
            
        step_results: Dict[str, StepResult]
            已完成步骤的结果映射
            - key: step_id (例如 "S1", "S2")
            - value: 对应步骤执行产出的 StepResult
            ExecutorAgent / StepRunner 运行时会不断向此映射追加或更新步骤结果
            
        safety_events: List[SafetyResult]
            历史安全检查列表
            包括输入预检、步骤级 pre/post 检查、最终输出检查等
            
        design_result: Optional[DesignResult]
            SummarizerAgent 在 SUMMARIZING 阶段生成的最终设计成果
            在任务未完成前，此字段为 None数据契约
    """

    task: ProteinDesignTask
    plan: Optional[Plan] = None
    step_results: Dict[str, StepResult] = Field(default_factory=dict)
    safety_events: List[SafetyResult] = Field(default_factory=list)
    design_result: Optional[DesignResult] = None

    class Config:
        arbitrary_types_allowed = True
    
    def add_step_result(self, result: StepResult) -> None:
        """将单步执行结果写入上下文，使用 step_id 作为 key
        
        Args:
            result: 步骤执行结果
            
        Note:
            ExecutorAgent / StepRunner 可以统一调用这个方法
            如果 step_id 已存在，会覆盖之前的结果
        """
        self.step_results[result.step_id] = result
    
    def add_safety_event(self, event: SafetyResult) -> None:
        """记录一次安全检查结果
        
        Args:
            event: 安全检查结果事件
        """
        self.safety_events.append(event)

    def get_step_output(self, step_id: str, key: str) -> Any:
        """便捷访问，读取某一步的输出字段
        
        Args:
            step_id: 步骤ID (例如 "S1")
            key: 输出字段名
            
        Returns:
            步骤输出中对应 key 的值
            
        Raises:
            KeyError: 如果 step_id 不存在或 key 不在输出中
        """
        if step_id not in self.step_results:
            raise KeyError(f"Step '{step_id}' not found in step_results")
        return self.step_results[step_id].outputs[key]
    
    def has_step_result(self, step_id: str) -> bool:
        """检查指定步骤的结果是否存在
        
        Args:
            step_id: 步骤ID
            
        Returns:
            如果步骤结果存在返回 True，否则返回 False
        """
        return step_id in self.step_results
    
    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """获取指定步骤的执行结果
        
        Args:
            step_id: 步骤ID
            
        Returns:
            步骤执行结果，如果不存在则返回 None
        """
        return self.step_results.get(step_id)
    
    def get_all_step_ids(self) -> List[str]:
        """获取所有已完成步骤的ID列表
        
        Returns:
            步骤ID列表，按添加顺序返回
        """
        return list(self.step_results.keys())
    
    def get_completed_step_count(self) -> int:
        """获取已完成步骤的数量
        
        Returns:
            已完成步骤的数量
        """
        return len(self.step_results)
    
    def is_plan_ready(self) -> bool:
        """检查计划是否已准备好（plan 不为 None）
        
        Returns:
            如果 plan 不为 None 返回 True，否则返回 False
        """
        return self.plan is not None
    
    def is_design_complete(self) -> bool:
        """检查设计是否已完成（design_result 不为 None）
        
        Returns:
            如果 design_result 不为 None 返回 True，否则返回 False
        """
        return self.design_result is not None