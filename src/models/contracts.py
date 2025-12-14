from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, Field

class ProteinDesignTask(BaseModel):
    """上层TaskAPI / CLI 提交的任务对象
    
    对应设计文档中的 ProteinDesignTask:
    - task_id: 系统生成的唯一ID
    - goal: 自然语言设计目标
    - constraints: 结构化约束，长度范围、安全等级等
    - metadata: 额外元信息，创建者、时间戳等
    """

    task_id: str
    goal: str
    constraints: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)

class PlanStep(BaseModel):
    """PlannerAgent 生成的单个步骤描述"""

    id: str
    tool: str # 对应 ProteinToolKG中的tool.id
    # 支持字面值和 "S1.sequence" 形式的引用
    inputs: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)

class Plan(BaseModel):
    """PlannerAgent 输出的完整计划 JSON契约"""

    task_id: str
    steps: List[PlanStep]
    constraints: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)

class RiskFlag(BaseModel):
    """单条风险标记，用于描述某一类安全风险"""

    level: Literal["ok", "warn", "block"]
    code: str
    message: str
    scope: Literal["input", "step", "output", "task"]
    step_id: Optional[str] = None
    details: Dict = Field(default_factory=dict)

class SafetyResult(BaseModel):
    """一次安全检查的结果(输入/步骤/输出/整体)"""

    task_id: str
    # 对齐文档: phase = "input" | "step" | "output"
    phase: Literal["input", "step", "output"]
    # "task" | f"step:{step_id}" | "result"
    scope: str
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    action: Literal["allow", "warn", "block"]
    timestamp: str

class StepResult(BaseModel):
    """ExecutoAgent 执行单个 PlanStep 的结果摘要"""

    task_id: str
    step_id: str
    tool: str
    status: Literal["success", "failed", "skipped"]
    outputs: Dict = Field(default_factory=dict)
    metrics: Dict = Field(default_factory=dict)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    logs_path: Optional[str] = None
    timestamp: str

class DesignResult(BaseModel):
    """SummarizerAgent 汇总后的最终设计结果"""
    task_id: str
    sequence: Optional[str] = None
    structure_pdb_path: Optional[str] = None
    scores: Dict = Field(default_factory=dict)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    report_path: str
    metadata: Dict = Field(default_factory=dict)

class WorkflowContext(BaseModel):
    """在一次任务生命周期内，各 Agent 共享的上下文对象
    
    对齐agent-design中的 WorkflowContext 结构:
    
    - task: 原始任务
    - plan: 当前正在使用的 Plan(可能经历多次replan)
    - step_results: 已完成步骤的结果map
    - safety_results: 所有安全检查记录
    - design_result: 最终输出
    - status: 任务当前执行状态（字符串形式，实际类型见 workflow/context.py）
    
    Note:
        本模块中的 WorkflowContext 是基础数据契约定义。
        workflow/context.py 中提供了增强版本，包含 status 字段（使用 TaskStatus 枚举）
        和辅助方法。
    """

    task: ProteinDesignTask
    plan: Optional[Plan] = None
    step_results: Dict[str, StepResult] = Field(default_factory=dict)
    safety_events: List[SafetyResult] = Field(default_factory=list)
    design_result: Optional[DesignResult] = None

class ReplanRequest(BaseModel):
    """ExecutorAgent / SafetyAgent 在运行期触发再规划时发送PlannerAgent的请求"""

    task_id: str
    original_plan: Plan
    failed_steps: List[str] = Field(default_factory=list)
    safety_events: List[SafetyResult] = Field(default_factory=list)
    reason: str

class PlanPatchOp(BaseModel):
    """单个 Plan Patch 操作
    
    op:
    - "replace_step"
    - "insert_step_before"
    - "insert_step_after"
    """

    op: Literal["replace_step", "insert_step_before", "insert_step_after"]
    target: str # 目标 step_id
    step: PlanStep

class PlanPatch(BaseModel):
    """PlannerAgent 针对局部问题生成的最小修改集合"""

    task_id: str
    operations: List[PlanPatchOp]
    metadata: Dict = Field(default_factory=dict)

class PatchRequest(BaseModel):
    """ExecutorAgent 针对某个局部失败 / 异常向 PlannerAgent 申请 Patch 的请求"""

    task_id: str
    original_plan: Plan
    context_step_results: List[StepResult] = Field(default_factory=list)
    safety_events: List[SafetyResult] = Field(default_factory=list)
    reason: str

def now_iso() -> str:
    """小工具，统一生成 ISO8601 时间字符串，后续各处可以复用"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")