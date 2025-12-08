from __future__ import annotations

from typing import Dict

from src.models.contracts import Plan, WorkflowContext, StepResult, now_iso


class ExecutorAgent:
    """最小可用 ExecutorAgent：顺序执行 Plan，每一步生成一个假的 StepResult
    
    当前实现：使用 dummy 执行逻辑，不调用真实工具
    后续将通过 Adapter 调用真实工具（ESMFold、ProteinMPNN等）
    """

    def run_step(self, step_id: str, context: WorkflowContext) -> StepResult:
        """执行单个步骤
        
        Args:
            step_id: 步骤ID
            context: 工作流上下文
            
        Returns:
            StepResult: 步骤执行结果
        """
        assert context.plan is not None, "Plan must be set in context"
        step = next(s for s in context.plan.steps if s.id == step_id)

        # 假执行逻辑：根据输入生成一点"输出"，不调用任何外部模型
        # 后续将通过 Adapter 调用真实工具
        sequence = step.inputs.get("sequence", "")
        outputs: Dict = {
            "note": f"dummy execution for step {step.id} with tool {step.tool}",
            "sequence_length": len(sequence),
        }
        metrics: Dict = {
            "runtime_ms": 1,
            "backend": "dummy_executor",
        }

        result = StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            outputs=outputs,
            metrics=metrics,
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

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
