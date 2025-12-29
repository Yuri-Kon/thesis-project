from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


def now_iso() -> str:
    """Small helper to generate ISO8601 timestamp strings."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

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
    # 失败分类：对齐 FailureType 枚举的字符串值；成功时可为 None
    failure_type: Optional[str] = None
    # 简要错误信息，便于 patch/replan 和日志调试；成功时可为 None
    error_message: Optional[str] = None
    # 可选错误细节，用于附加上下文（例如 trace_id / 原始异常消息等）
    error_details: Dict = Field(default_factory=dict)
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

# WorkflowContext 已移至 src.workflow.context
# 请使用 src.workflow.context.WorkflowContext（包含 status 字段和辅助方法）

class ReplanRequest(BaseModel):
    """ExecutorAgent / SafetyAgent 在运行期触发再规划时发送PlannerAgent的请求"""

    task_id: str
    original_plan: Plan
    failed_steps: List[str] = Field(default_factory=list)
    safety_events: List[SafetyResult] = Field(default_factory=list)
    reason: str

PlanPatchOpType = Literal[
    "replace_step",
    "insert_step_before",
    "insert_step_after",
]

class PlanPatchOp(BaseModel):
    """单个 Plan Patch 操作
    
    op:
    - "replace_step"
    - "insert_step_before"
    - "insert_step_after"
    """

    model_config = ConfigDict(extra="forbid")

    op: PlanPatchOpType
    target: str # 目标 step_id
    step: PlanStep

    @field_validator("step", mode="before")
    @classmethod
    def _fill_step_id(cls, value, info):
        """允许 replace_step 省略 step.id，其余操作需要显式 id"""
        if not isinstance(value, dict):
            return value

        op = info.data.get("op")
        target = info.data.get("target")
        has_id = "id" in value and value["id"]

        if op == "replace_step":
            # 默认为复用目标 step_id，保持局部修改语义
            return {"id": target, **value} if not has_id else value

        if not has_id:
            raise ValueError("insert step operations require an explicit step.id")
        return value

    @model_validator(mode="after")
    def _ensure_step_scope(self):
        """replace_step 不允许更换 id，避免破坏 Plan/PlanStep 契约"""
        if self.op == "replace_step" and self.step.id != self.target:
            raise ValueError(
                f"replace_step must keep the same id as target ({self.target})"
            )
        return self

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


class PendingActionType(str, Enum):
    """PendingAction 类型枚举。"""

    PLAN_CONFIRM = "plan_confirm"
    PATCH_CONFIRM = "patch_confirm"
    REPLAN_CONFIRM = "replan_confirm"


class PendingActionStatus(str, Enum):
    """PendingAction 状态枚举。"""

    PENDING = "pending"
    DECIDED = "decided"
    CANCELLED = "cancelled"


class PendingActionCandidate(BaseModel):
    """候选方案的最小封装。

    Attributes:
        candidate_id: 候选唯一标识。
        payload: 候选承载的对象（Plan 或 PlanPatch）。
        summary: 候选摘要信息。
        metadata: 额外元数据。
    """

    candidate_id: str
    payload: Plan | PlanPatch
    summary: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


class PendingAction(BaseModel):
    """等待人工决策的结构化对象。

    Attributes:
        pending_action_id: 待决策对象 ID。
        task_id: 任务 ID。
        action_type: 待决策类型。
        candidates: 候选集合。
        explanation: 解释说明文本。
        status: PendingAction 当前状态。
        default_suggestion: 默认建议候选 ID。
        created_at: 创建时间戳。
        decided_at: 决策完成时间戳。
        created_by: 创建者标识（通常为 system）。
    """

    pending_action_id: str
    task_id: str
    action_type: PendingActionType
    candidates: List[PendingActionCandidate]
    explanation: str
    status: PendingActionStatus = PendingActionStatus.PENDING
    default_suggestion: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    decided_at: Optional[str] = None
    created_by: str = "system"


class DecisionChoice(str, Enum):
    ACCEPT = "accept"
    REPLAN = "replan"
    CONTINUE = "continue"
    CANCEL = "cancel"


class Decision(BaseModel):
    """针对 PendingAction 的一次人工决策"""

    decision_id: str
    task_id: str
    pending_action_id: str
    choice: DecisionChoice
    selected_candidate_id: Optional[str] = None
    decided_by: str
    comment: Optional[str] = None
    decided_at: str = Field(default_factory=now_iso)

    @model_validator(mode="after")
    def _ensure_accept_has_candidate(self):
        if self.choice == DecisionChoice.ACCEPT and not self.selected_candidate_id:
            raise ValueError(
                "selected_candidate_id is required when choice is accept"
            )
        return self


class ArtifactRef(BaseModel):
    """Reference to a persisted artifact."""

    uri: str
    metadata: Dict = Field(default_factory=dict)


class TaskSnapshot(BaseModel):
    """任务在某一时间点的最小可恢复上下文"""

    snapshot_id: str
    task_id: str
    state: str
    plan_version: Optional[int] = None
    step_index: int = 0
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    current_step_index: int = 0
    completed_step_ids: List[str] = Field(default_factory=list)
    pending_action_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)

    @field_validator("state")
    @classmethod
    def _validate_state(cls, value: str) -> str:
        from src.models.db import ExternalStatus

        allowed_states = {status.value for status in ExternalStatus}
        if value not in allowed_states:
            raise ValueError(f"state must be one of {sorted(allowed_states)}")
        return value

    @field_validator("plan_version")
    @classmethod
    def _validate_plan_version(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        if value < 0:
            raise ValueError("plan_version must be >= 0")
        return value

    @field_validator("step_index")
    @classmethod
    def _validate_step_index(cls, value: int) -> int:
        if value < 0:
            raise ValueError("step_index must be >= 0")
        return value

    @field_validator("current_step_index")
    @classmethod
    def _validate_current_step_index(cls, value: int) -> int:
        if value < 0:
            raise ValueError("current_step_index must be >= 0")
        return value

    @field_validator("artifacts")
    @classmethod
    def _validate_artifacts(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("artifacts must be a mapping")
        for key, artifact in value.items():
            if not isinstance(key, str):
                raise ValueError("artifacts keys must be strings")
            if isinstance(artifact, ArtifactRef):
                continue
            try:
                json.dumps(artifact, ensure_ascii=True)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "artifacts must be JSON-serializable or ArtifactRef"
                ) from exc
        return value

    @model_validator(mode="after")
    def _sync_step_index(self):
        step_set = "step_index" in self.model_fields_set
        current_set = "current_step_index" in self.model_fields_set
        if step_set and not current_set:
            self.current_step_index = self.step_index
        elif current_set and not step_set:
            self.step_index = self.current_step_index
        elif self.step_index != self.current_step_index:
            raise ValueError("step_index must match current_step_index")
        return self
