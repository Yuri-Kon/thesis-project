from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .contracts import (
    ProteinDesignTask,
    Plan,
    PendingAction,
    StepResult,
    DesignResult,
    SafetyResult,
    Decision,
    now_iso,
)

# 任务 & 步骤状态定义


class ExternalStatus(str, Enum):
    """对外语义状态(ExternalStatus)

    对齐 architecture.md 定义的 FSM 状态。
    """

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_PLAN_CONFIRM = "WAITING_PLAN_CONFIRM"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING_PATCH_CONFIRM = "WAITING_PATCH_CONFIRM"
    WAITING_REPLAN_CONFIRM = "WAITING_REPLAN_CONFIRM"
    SUMMARIZING = "SUMMARIZING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InternalStatus(str, Enum):
    """内部执行状态(InternalStatus)

    保留 PATCHING / REPLANNING / WAITING_* 等细粒度状态。
    """

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_PLAN_CONFIRM = "WAITING_PLAN_CONFIRM"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING_PATCH = "WAITING_PATCH"
    PATCHING = "PATCHING"
    WAITING_REPLAN = "WAITING_REPLAN"
    REPLANNING = "REPLANNING"
    SUMMARIZING = "SUMMARIZING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_EXTERNAL_STATUSES = {
    ExternalStatus.DONE,
    ExternalStatus.FAILED,
    ExternalStatus.CANCELLED,
}
TERMINAL_INTERNAL_STATUSES = {
    InternalStatus.DONE,
    InternalStatus.FAILED,
    InternalStatus.CANCELLED,
}

_INTERNAL_TO_EXTERNAL = {
    InternalStatus.WAITING_PATCH: ExternalStatus.WAITING_PATCH_CONFIRM,
    InternalStatus.PATCHING: ExternalStatus.WAITING_PATCH_CONFIRM,
    InternalStatus.WAITING_REPLAN: ExternalStatus.WAITING_REPLAN_CONFIRM,
    InternalStatus.REPLANNING: ExternalStatus.WAITING_REPLAN_CONFIRM,
}


def to_external_status(status: InternalStatus) -> ExternalStatus:
    """将 InternalStatus 映射为对外语义状态."""
    mapped = _INTERNAL_TO_EXTERNAL.get(status)
    if mapped is not None:
        return mapped
    return ExternalStatus[status.name]


class StepStatus(str, Enum):
    """单个步骤的生命周期状态

    - PENDING: 在 Plan 中但尚未执行
    - RUNNING: 正在执行
    - SUCCEEDED: 执行成功
    - FAILED: 执行失败
    - SKIPPED: 执行跳过(例如因为 replan / patch)
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# 持久化用 Record 模型


class TaskRecord(BaseModel):
    """用于持久化的任务记录

    这个模型代表数据库里的 task 表/集合中的一行/一条
    """

    id: str
    status: ExternalStatus
    internal_status: Optional[InternalStatus] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    # 为了方便查询和可视化，直接展开一些字段
    goal: str
    constraints: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)

    # 计划和结果保存为 JSON 格式，后端可序列化为 TEXT / JSONB 等
    plan: Optional[Plan] = None
    design_result: Optional[DesignResult] = None

    # 若处于 WAITING_*，记录当前待决策对象
    pending_action: Optional[PendingAction] = None

    # 决策记录（用于审计和回放）
    decisions: List[Decision] = Field(default_factory=list)

    # 安全事件汇总
    safety_events: List[SafetyResult] = Field(default_factory=list)


class StepRecord(BaseModel):
    """用于持久化的步骤执行记录"""

    task_id: str
    step_id: str
    tool: str

    status: StepStatus

    # 执行时间
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    # 度量和风险摘要，细节留在 StepResult 里
    metrics: Dict = Field(default_factory=dict)
    risk_flags: Dict = Field(default_factory=dict)

    # 挂上上一版本的 StepResult 以便详细追溯
    last_result: Optional[StepResult] = None


# 从运行期上下文推导状态的帮助函数


def derive_task_status(
    task: ProteinDesignTask,
    plan: Optional[Plan],
    step_results: Dict[str, StepResult],
    safety_events: List[SafetyResult],
    design_result: Optional[DesignResult],
) -> InternalStatus:
    """根据当前上下文粗略推导 InternalStatus

    约定：
    - 只返回 CREATED / PLANNED / RUNNING / DONE / FAILED 这五种状态
    - 细粒度状态由工作流显式设置，不在这里推导
    """

    # 已有最终结果 ⇒ DONE
    if design_result is not None:
        return InternalStatus.DONE

    # 强错误：有失败步骤 或 有 action == "block" 的安全事件 ⇒ FAILED
    has_failed_step = any(r.status == "failed" for r in step_results.values())
    has_block_safety = any(evt.action == "block" for evt in safety_events)

    if has_failed_step or has_block_safety:
        return InternalStatus.FAILED

    # 还没有 Plan ⇒ CREATED
    if plan is None:
        return InternalStatus.CREATED

    # 有 Plan 且已经至少成功/跳过了一些步骤 ⇒ RUNNING
    has_any_finished_step = any(
        r.status in ("success", "skipped") for r in step_results.values()
    )

    if has_any_finished_step:
        return InternalStatus.RUNNING

    # 有 Plan 但还没有执行任何一步 ⇒ PLANNED
    return InternalStatus.PLANNED


def step_result_to_record(result: StepResult) -> StepRecord:
    """将 StepResult 转化为 StepRecord 方便写入持久化层"""

    # 这里简单根据 StepResult.status 映射到 StepStatus
    status_map = {
        "success": StepStatus.SUCCEEDED,
        "failed": StepStatus.FAILED,
        "skipped": StepStatus.SKIPPED,
    }

    step_status = status_map.get(result.status, StepStatus.PENDING)

    # 最小版本：只有一个时间戳，用于 finished_at
    return StepRecord(
        task_id=result.task_id,
        step_id=result.step_id,
        tool=result.tool,
        status=step_status,
        started_at=None,
        finished_at=result.timestamp,
        metrics=result.metrics,
        risk_flags={
            "max_level": max((flag.level for flag in result.risk_flags), default="ok")
        }
        if result.risk_flags
        else {},
        last_result=result,
    )
