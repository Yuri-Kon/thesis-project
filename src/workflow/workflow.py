from __future__ import annotations
from src.models.contracts import ProteinDesignTask, now_iso
from src.adapters.builtins import ensure_builtin_adapters
from src.models.db import TaskRecord, TaskStatus, TERMINAL_STATES, derive_task_status
from src.agents.planner import PlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.workflow.context import WorkflowContext
from src.workflow.status import transition_task_status

def run_task_sync(task: ProteinDesignTask) -> TaskRecord:
    """同步执行一次完整任务"""
    ensure_builtin_adapters()

    planner = PlannerAgent()
    executor = ExecutorAgent()
    summarizer = SummarizerAgent()

    # 初始 TaskRecord
    record = TaskRecord(
        id=task.task_id,
        status=TaskStatus.CREATED,
        created_at=now_iso(),
        updated_at=now_iso(),
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=None,
        design_result=None,
        safety_events=[],
    )

    ctx = WorkflowContext(
        task=task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.CREATED,
    )

    def _mark_failed_if_needed() -> None:
        if ctx.status in TERMINAL_STATES:
            return
        transition_task_status(
            ctx,
            record,
            TaskStatus.FAILED,
            reason="workflow_error",
        )

    # 1. 规划
    try:
        transition_task_status(
            ctx,
            record,
            TaskStatus.PLANNING,
            reason="task_created",
        )
        plan = planner.plan(task)
        ctx.plan = plan
        record.plan = plan
        transition_task_status(
            ctx,
            record,
            TaskStatus.PLANNED,
            reason="plan_generated",
        )
    except Exception:
        _mark_failed_if_needed()
        raise

    # 2. 执行
    # 注意：先推进到 RUNNING，执行完成由 PlanRunner 推进到 SUMMARIZING
    try:
        transition_task_status(
            ctx,
            record,
            TaskStatus.RUNNING,
            reason="plan_execution_start",
        )
        executor.run_plan(plan, ctx, record=record, finalize_status=False)
    except Exception:
        _mark_failed_if_needed()
        raise

    # 3. 汇总
    try:
        transition_task_status(
            ctx,
            record,
            TaskStatus.SUMMARIZING,
            reason="plan_execution_completed",
        )
        design = summarizer.summarize(ctx)
        ctx.design_result = design
        record.design_result = design
    except Exception:
        _mark_failed_if_needed()
        raise

    # 4. 聚合状态
    final_status = derive_task_status(
        ctx.task,
        ctx.plan,
        ctx.step_results,
        ctx.safety_events,
        ctx.design_result,
    )

    final_reason = (
        "summarizer_completed"
        if final_status == TaskStatus.DONE
        else "workflow_failed"
    )
    transition_task_status(ctx, record, final_status, reason=final_reason)

    return record
