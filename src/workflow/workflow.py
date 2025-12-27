from __future__ import annotations
from src.models.contracts import ProteinDesignTask, now_iso
from src.adapters.builtins import ensure_builtin_adapters
from src.models.db import (
    ExternalStatus,
    InternalStatus,
    TaskRecord,
)
from src.agents.planner import PlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.workflow.context import WorkflowContext

def run_task_sync(task: ProteinDesignTask) -> TaskRecord:
    """同步执行一次完整任务"""
    ensure_builtin_adapters()

    planner = PlannerAgent()
    executor = ExecutorAgent()
    summarizer = SummarizerAgent()

    # 初始 TaskRecord
    record = TaskRecord(
        id=task.task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
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
        status=InternalStatus.CREATED,
    )

    # 1. 规划
    plan = planner.plan_with_status(task, ctx, record=record)

    # 2. 执行
    # 注意：PlanRunner 会负责 PLANNED → RUNNING → SUMMARIZING
    executor.run_plan(plan, ctx, record=record, finalize_status=False)

    # 3. 汇总
    executor.summarize_and_finalize(ctx, record, summarizer)

    return record
