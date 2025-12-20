from __future__ import annotations
from src.models.contracts import ProteinDesignTask, now_iso
from src.models.db import TaskRecord, TaskStatus, derive_task_status
from src.agents.planner import PlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.workflow.context import WorkflowContext
from src.workflow.status import transition_task_status

def run_task_sync(task: ProteinDesignTask) -> TaskRecord:
    """同步执行一次完整任务"""

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

    # 1. 规划
    transition_task_status(ctx, record, TaskStatus.PLANNING)
    plan = planner.plan(task)
    ctx.plan = plan
    record.plan = plan
    transition_task_status(ctx, record, TaskStatus.PLANNED)

    # 2. 执行
    # 注意：PlanRunner 会将状态从 PLANNED 更新为 RUNNING
    transition_task_status(ctx, record, TaskStatus.RUNNING)
    executor.run_plan(plan, ctx)

    # 3. 汇总
    transition_task_status(ctx, record, TaskStatus.SUMMARIZING)
    design = summarizer.summarize(ctx)
    ctx.design_result = design
    record.design_result = design

    # 4. 聚合状态
    final_status = derive_task_status(
        ctx.task,
        ctx.plan,
        ctx.step_results,
        ctx.safety_events,
        ctx.design_result,
    )

    transition_task_status(ctx, record, final_status)

    return record
