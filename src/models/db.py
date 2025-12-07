from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .contracts import (
    ProteinDesignTask,
    Plan,
    StepResult,
    DesignResult,
    SafetyResult,
    now_iso,
)

# 任务 & 步骤状态定义

class TaskStatus(str, Enum):
    """任务生命周期状态
    
    对齐状态机设计

    - CREATED: 任务已经在API层创建，但尚未进入规划流程
    - PLANNING: PlannerAgent 正在生成初始Plan
    - PLANNED: 初始 Plan 已经生成，等待执行
    - RUNNING: ExecutorAgent 正在按照 Plan 执行步骤
    - WAITING_PATCH: 某一步骤多次重试失败，等待Planner生成局部PlanPatch
    - PATCHING: PlannerAgent 正在根据 PatchRequest 生成PlanPatch
    - WAITING_REPLAN: 当前 Plan 无法局部修复，等待PlannerAgent生成新的子计划
    - REPLANNING: PlannerAgent 正在根据 ReplanRequest 重新规划未完成子计划
    - SUMMARIZING: SummarizerAgent 正在汇总结果并生成 DesignResult
    - DONE: 任务成功完成，DesignResult 已生成并持久化
    - FAILED: 任务执行失败且无法继续
    """
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING_PATCH = "WAITING_PATCH"
    PATCHING = "PATCHING"
    WAITING_REPLAN = "WAITING_REPLAN"
    REPLANNING = "REPLANNING"
    SUMMARIZING = "SUMMARIZING"
    DONE = "DONE"
    FAILED = "FAILED"

TERMINAL_STATES = {TaskStatus.DONE, TaskStatus.FAILED}

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
    status: TaskStatus
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    # 为了方便查询和可视化，直接展开一些字段
    goal: str
    constraints: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)

    # 计划和结果保存为 JSON 格式，后端可序列化为 TEXT / JSONB 等
    plan: Optional[Plan] = None
    design_result: Optional[DesignResult] = None

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
) -> TaskStatus:
    """根据当前上下文粗略推导 TaskStatus

    约定：
    - 只返回 CREATED / PLANNED / RUNNING / DONE / FAILED 这五种状态
    - 细粒度的 PLANNING / WAITING_PATCH / REPLANNING / SUMMARIZING 由LangGraph工作流在节点执行时
    显式设置，不在这里推导
    """

    # 已有最终结果 ⇒ DONE
    if design_result is not None:
        return TaskStatus.DONE

    # 强错误：有失败步骤 或 有 action == "block" 的安全事件 ⇒ FAILED
    has_failed_step = any(r.status == "failed" for r in step_results.values())
    has_block_safety = any(evt.action == "block" for evt in safety_events)

    if has_failed_step or has_block_safety:
        return TaskStatus.FAILED
    
    # 还没有 Plan ⇒ CREATED
    if plan is None:
        return TaskStatus.CREATED
    
    # 有 Plan 且已经至少成功/跳过了一些步骤 ⇒ RUNNING
    has_any_finished_step = any(
        r.status in ("success", "skipped") for r in step_results.values()
    )

    if has_any_finished_step:
        return TaskStatus.RUNNING
    
    # 有 Plan 但还没有执行任何一步 ⇒ PLANNED
    return TaskStatus.PLANNED

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
            "max_level": max(
                (flag.level for flag in result.risk_flags),
                default="ok"
            )
        }
        if result.risk_flags
        else {},
        last_result=result,
    )
