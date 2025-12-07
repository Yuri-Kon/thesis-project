from __future__ import annotations

from typing import List
from src.models.contracts import ProteinDesignTask, Plan, PlanStep

# 一个规则极其简单的Planner

class PlannerAgent:
    """最小可用 PlannerAgent: 根据任务目标生成一个单步 Plan"""

    def plan(self, task: ProteinDesignTask) -> Plan:
        # 最小版, 固定生成一个叫 S1 的步骤，调用一个逻辑上的工具 "dummy_tool"
        step = PlanStep(
            id="S1",
            tool="dummy_tool", # 之后会被真实工具代替
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

        # replan / patch 暂且不实现，后续阶段再补充
    
