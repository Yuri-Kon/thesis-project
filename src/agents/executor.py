from __future__ import annotations

from typing import Dict

from src.models.contracts import Plan, WorkflowContext, StepResult, RiskFlag, now_iso


class ExecutorAgent:
    """最小可用 ExecutorAgent：顺序执行 Plan，每一步生成一个假的 StepResult."""

    def run_step(self, step_id: str, context: WorkflowContext) -> StepResult:
        assert context.plan is not None
        step = next(s for s in context.plan.steps if s.id == step_id)

        # 假执行逻辑：根据输入生成一点“输出”，不调用任何外部模型
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
        # 顺序执行所有 step，目前不做重试/patch/replan
        context.plan = plan
        for step in plan.steps:
            self.run_step(step.id, context)
        return plan
