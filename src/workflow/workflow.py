from __future__ import annotations
import shutil
from src.models.contracts import ProteinDesignTask, now_iso
from src.models.contracts import Plan, PlanStep
from src.adapters.builtins import ensure_builtin_adapters
from src.models.db import (
    ExternalStatus,
    InternalStatus,
    TERMINAL_INTERNAL_STATUSES,
    TaskRecord,
)
from src.agents.planner import PlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.workflow.context import WorkflowContext
from src.workflow.recovery import S6_TRIGGER_MATRIX_VERSION

S6_CONTROL_LAYER_MATRIX_VERSION = S6_TRIGGER_MATRIX_VERSION

_WAITING_INTERNAL_STATUSES = {
    InternalStatus.WAITING_PLAN_CONFIRM,
    InternalStatus.WAITING_PATCH,
    InternalStatus.WAITING_REPLAN,
}


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
    plan = _apply_sync_smoke_fallback(task, ctx, record, plan)
    if ctx.status in _WAITING_INTERNAL_STATUSES:
        return record

    # 2. 执行
    # 注意：PlanRunner 会负责 PLANNED → RUNNING → SUMMARIZING
    executor.run_plan(plan, ctx, record=record, finalize_status=False)
    if ctx.status in _WAITING_INTERNAL_STATUSES or ctx.status in TERMINAL_INTERNAL_STATUSES:
        return record

    # 3. 汇总
    executor.summarize_and_finalize(ctx, record, summarizer)

    return record


def _apply_sync_smoke_fallback(
    task: ProteinDesignTask,
    ctx: WorkflowContext,
    record: TaskRecord,
    plan: Plan,
) -> Plan:
    if shutil.which("nextflow") is not None:
        return plan
    if not any(step.tool in {"esmfold"} for step in plan.steps):
        return plan
    fallback_plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
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
        ],
        constraints=task.constraints,
        metadata={
            **(plan.metadata if isinstance(plan.metadata, dict) else {}),
            "sync_smoke_fallback": "dummy_tool",
            "sync_smoke_fallback_reason": "nextflow_unavailable",
        },
    )
    ctx.plan = fallback_plan
    record.plan = fallback_plan
    return fallback_plan
