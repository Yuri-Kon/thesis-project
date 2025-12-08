from __future__ import annotations

from src.models.contracts import ProteinDesignTask, Plan, PlanStep


class PlannerAgent:
    """最小可用 PlannerAgent: 根据任务目标生成一个单步 Plan
    
    当前实现：固定生成一个单步计划，调用 dummy_tool
    后续将接入 KG 和 LLM 实现智能规划
    """

    def plan(self, task: ProteinDesignTask) -> Plan:
        """生成执行计划
        
        Args:
            task: 蛋白质设计任务
            
        Returns:
            Plan: 包含步骤列表的执行计划
        """
        # 最小版: 固定生成一个叫 S1 的步骤，调用 dummy_tool
        # 后续会被真实工具替代
        step = PlanStep(
            id="S1",
            tool="dummy_tool",
            inputs={
                "sequence": task.constraints.get(
                    "sequence",
                    "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR",
                )
            },
            metadata={},
        )

        return Plan(
            task_id=task.task_id,
            steps=[step],
            constraints=task.constraints,
            metadata={},
        )
