from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal, cast

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


def now_iso() -> str:
    """Small helper to generate ISO8601 timestamp strings."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


RUNTIME_STATE_SCHEMA_VERSION = 1
RUNTIME_STATE_ARTIFACT_KEY = "runtime_state"
RUNTIME_OBSERVATION_SUMMARY_ARTIFACT_KEY = "runtime_observation_summary"
RUNTIME_STATE_SUMMARY_METADATA_KEY = "runtime_state_summary"
DEFAULT_RECOMMENDATION_REASON_METADATA_KEY = "default_recommendation_reason"
ACTION_SCORE_METADATA_KEY = "action_score"
SHADOW_SCORE_METADATA_KEY = "shadow_score"
STATIC_SCORE_METADATA_KEY = "static_score"
FINAL_SCORE_METADATA_KEY = "final_score"
RUNTIME_ADJUSTMENT_METADATA_KEY = "runtime_adjustment"
RERANK_REASON_METADATA_KEY = "rerank_reason"
WAITING_RUNTIME_SUMMARY_METADATA_KEY = "waiting_runtime_summary"
DECISION_SUMMARY_ARTIFACT_KEY = "decision_summary"
CAPABILITY_READINESS_METADATA_KEY = "capability_readiness"
TOOL_READINESS_METADATA_KEY = "tool_readiness"
ADAPTER_ID_METADATA_KEY = "adapter_id"
EXECUTION_MODE_METADATA_KEY = "execution_mode"
PROVIDER_METADATA_KEY = "provider"
ENDPOINT_TYPE_METADATA_KEY = "endpoint_type"
REMOTE_JOB_ID_METADATA_KEY = "remote_job_id"


def _validate_runtime_state_schema_version(value: int) -> int:
    if value != RUNTIME_STATE_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {RUNTIME_STATE_SCHEMA_VERSION}"
        )
    return value


def _validate_probability_value(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("probability fields must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError("probability fields must be finite")
    if not 0.0 <= normalized <= 1.0:
        raise ValueError("probability fields must be between 0 and 1")
    return normalized


def _validate_finite_float_value(value: float, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


def _validate_non_empty_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


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
    tool: str  # 对应 ProteinToolKG中的tool.id
    # 支持字面值和 "S1.sequence" 形式的引用
    inputs: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)


class Plan(BaseModel):
    """PlannerAgent 输出的完整计划 JSON契约"""

    task_id: str
    steps: List[PlanStep]
    constraints: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)
    explanation: Optional[str] = None


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
    # additive observability fields: tool/tool_id remains the scientific identity.
    tool_id: Optional[str] = None
    adapter_id: Optional[str] = None
    execution_mode: Optional[str] = None
    provider: Optional[str] = None
    endpoint_type: Optional[str] = None
    remote_job_id: Optional[str] = None
    status: Literal["success", "failed", "skipped"]
    # 失败分类：对齐 FailureType 枚举的字符串值；成功时可为 None
    failure_type: Optional[str] = None
    # 简要错误信息，便于 patch/replan 和日志调试；成功时可为 None
    error_message: Optional[str] = None
    # 可选错误细节，用于附加上下文（例如 trace_id / 原始异常消息等）
    error_details: Dict = Field(default_factory=dict)
    inputs: Dict = Field(default_factory=dict)
    outputs: Dict = Field(default_factory=dict)
    artifacts: Dict = Field(default_factory=dict)
    metrics: Dict = Field(default_factory=dict)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    logs_path: Optional[str] = None
    timestamp: str

    @field_validator(
        "tool_id",
        "adapter_id",
        "execution_mode",
        "provider",
        "endpoint_type",
        "remote_job_id",
    )
    @classmethod
    def _validate_optional_invocation_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_non_empty_text(value, field_name="invocation metadata")

    @model_validator(mode="after")
    def _sync_invocation_metadata(self) -> "StepResult":
        """同步执行元数据，保持旧 metrics/error_details 消费者兼容。"""
        metrics = dict(self.metrics or {})
        self.metrics = metrics

        self.tool_id = _sync_step_metadata_field(
            metrics,
            field_name="tool_id",
            field_value=self.tool_id or self.tool,
        )
        self.adapter_id = _sync_step_metadata_field(
            metrics,
            field_name=ADAPTER_ID_METADATA_KEY,
            field_value=self.adapter_id,
        )
        self.execution_mode = _sync_step_metadata_field(
            metrics,
            field_name=EXECUTION_MODE_METADATA_KEY,
            field_value=self.execution_mode,
        )
        self.provider = _sync_step_metadata_field(
            metrics,
            field_name=PROVIDER_METADATA_KEY,
            field_value=self.provider,
        )
        self.endpoint_type = _sync_step_metadata_field(
            metrics,
            field_name=ENDPOINT_TYPE_METADATA_KEY,
            field_value=self.endpoint_type,
        )
        self.remote_job_id = _sync_step_metadata_field(
            metrics,
            field_name=REMOTE_JOB_ID_METADATA_KEY,
            field_value=self.remote_job_id or _coerce_non_empty_text(metrics.get("job_id")),
        )
        if self.failure_type is not None:
            metrics.setdefault("failure_type", self.failure_type)
        if isinstance(self.error_details, dict):
            failure_code = _coerce_non_empty_text(self.error_details.get("failure_code"))
            if failure_code is not None:
                metrics.setdefault("failure_code", failure_code)
        return self


class ToolReadiness(BaseModel):
    """单个 adapter/tool 的健康检查摘要。"""

    tool_id: str
    status: Literal["ready", "degraded", "unavailable"]
    reason: str = ""
    error_category: str | None = None
    capability_ids: List[str] = Field(default_factory=list)
    cost_prior: float | None = None
    risk_prior: float | None = None
    latency_prior: float | None = None
    suggested_recovery: str | None = None
    last_checked_at: str
    details: Dict[str, Any] = Field(default_factory=dict)
    metadata_profile: Dict[str, Any] | None = None


class CapabilityReadiness(BaseModel):
    """Capability 级 readiness 契约。

    该契约作为 Planner/API/Web/CLI 的同源视图，字段以 additive 方式扩展，
    不改变 ToolKG、候选和 EventLog 的既有核心语义。
    """

    capability_id: str
    status: Literal["ready", "degraded", "unavailable"]
    available_tools: List[ToolReadiness] = Field(default_factory=list)
    blocked_tools: List[ToolReadiness] = Field(default_factory=list)
    degraded_reasons: List[str] = Field(default_factory=list)
    last_checked_at: str
    cost_prior: float | None = None
    risk_prior: float | None = None
    suggested_recovery: str | None = None
    primary_tool_id: str | None = None
    fallback_tool_ids: List[str] = Field(default_factory=list)
    reason: str = ""
    tools: List[ToolReadiness] = Field(default_factory=list)


class RuntimeFailureContext(BaseModel):
    """运行时状态更新器消费的稳定失败上下文。"""

    model_config = ConfigDict(extra="forbid")

    failure_type: str | None = None
    failure_code: str | None = None
    retry_exhausted: bool = False
    recovery_action: str | None = None
    patch: Dict[str, Any] | None = None
    recovery: Dict[str, Any] | None = None

    @field_validator("failure_type", "failure_code", "recovery_action")
    @classmethod
    def _validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _validate_non_empty_text(value, field_name=info.field_name)

    @field_validator("patch", "recovery")
    @classmethod
    def _validate_optional_mapping(
        cls,
        value: Dict[str, Any] | None,
        info,
    ) -> Dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(f"{info.field_name} must be a mapping")
        try:
            json.dumps(value, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{info.field_name} must be JSON-serializable"
            ) from exc
        return value

    def to_replay_payload(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class RuntimeStateUpdateInput(BaseModel):
    """belief-state 更新器的稳定输入接口。"""

    model_config = ConfigDict(extra="forbid")

    step_result: StepResult | None = None
    safety_result: SafetyResult | None = None
    failure_context: RuntimeFailureContext | None = None
    completed_steps: int | None = None
    total_steps: int | None = None

    @field_validator("completed_steps", "total_steps")
    @classmethod
    def _validate_optional_progress_value(
        cls,
        value: int | None,
        info,
    ) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError(f"{info.field_name} must be an integer")
        normalized = int(value)
        if normalized < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return normalized

    @model_validator(mode="after")
    def _validate_bounds_and_observation(self) -> "RuntimeStateUpdateInput":
        if (
            self.completed_steps is not None
            and self.total_steps is not None
            and self.completed_steps > self.total_steps
        ):
            raise ValueError("completed_steps must be <= total_steps")
        if (
            self.step_result is None
            and self.safety_result is None
            and self.failure_context is None
            and self.completed_steps is None
            and self.total_steps is None
        ):
            raise ValueError(
                "at least one observation or progress counter must be provided"
            )
        return self

    @classmethod
    def from_step_result(
        cls,
        *,
        step_result: StepResult,
        failure_context: RuntimeFailureContext | None = None,
        completed_steps: int | None = None,
        total_steps: int | None = None,
    ) -> "RuntimeStateUpdateInput":
        return cls(
            step_result=step_result,
            failure_context=failure_context,
            completed_steps=completed_steps,
            total_steps=total_steps,
        )

    @classmethod
    def from_safety_result(
        cls,
        *,
        safety_result: SafetyResult,
        failure_context: RuntimeFailureContext | None = None,
        completed_steps: int | None = None,
        total_steps: int | None = None,
    ) -> "RuntimeStateUpdateInput":
        return cls(
            safety_result=safety_result,
            failure_context=failure_context,
            completed_steps=completed_steps,
            total_steps=total_steps,
        )

    def to_replay_payload(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class RuntimeState(BaseModel):
    """稳定的运行时状态 schema。

    该模型冻结 issue #227 所需的最小字段集合；后续扩展必须保持 additive。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=RUNTIME_STATE_SCHEMA_VERSION)
    p_success: float
    p_structural_failure: float
    recovery_margin: float
    expected_remaining_cost: float
    evidence_sufficiency: float = 0.5
    last_update_source: str
    observation_summary: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        return _validate_runtime_state_schema_version(value)

    @field_validator("p_success", "p_structural_failure", "evidence_sufficiency")
    @classmethod
    def _validate_probability(cls, value: float) -> float:
        return _validate_probability_value(value)

    @field_validator("recovery_margin")
    @classmethod
    def _validate_recovery_margin(cls, value: float) -> float:
        return _validate_finite_float_value(value, field_name="recovery_margin")

    @field_validator("expected_remaining_cost")
    @classmethod
    def _validate_expected_remaining_cost(cls, value: float) -> float:
        normalized = _validate_finite_float_value(
            value,
            field_name="expected_remaining_cost",
        )
        if normalized < 0.0:
            raise ValueError("expected_remaining_cost must be >= 0")
        return normalized

    @field_validator("last_update_source")
    @classmethod
    def _validate_last_update_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("last_update_source must not be empty")
        return normalized

    @field_validator("observation_summary")
    @classmethod
    def _validate_observation_summary(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("observation_summary must be a mapping")
        try:
            json.dumps(value, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "observation_summary must be JSON-serializable"
            ) from exc
        return value

    def to_snapshot_payload(self) -> Dict[str, Any]:
        """Serialize the stable persisted fields for TaskSnapshot.artifacts."""
        return self.model_dump(exclude={"observation_summary"})

    def to_summary_payload(self) -> Dict[str, Any]:
        """Serialize the candidate-facing runtime state summary."""
        return RuntimeStateSummary.from_runtime_state(self).model_dump()


class RuntimeStateSummary(BaseModel):
    """候选展示态可复用的运行时状态摘要。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=RUNTIME_STATE_SCHEMA_VERSION)
    p_success: float
    p_structural_failure: float
    recovery_margin: float
    expected_remaining_cost: float
    evidence_sufficiency: float = 0.5

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        return _validate_runtime_state_schema_version(value)

    @field_validator("p_success", "p_structural_failure", "evidence_sufficiency")
    @classmethod
    def _validate_probability(cls, value: float) -> float:
        return _validate_probability_value(value)

    @field_validator("recovery_margin")
    @classmethod
    def _validate_recovery_margin(cls, value: float) -> float:
        return _validate_finite_float_value(value, field_name="recovery_margin")

    @field_validator("expected_remaining_cost")
    @classmethod
    def _validate_expected_remaining_cost(cls, value: float) -> float:
        normalized = _validate_finite_float_value(
            value,
            field_name="expected_remaining_cost",
        )
        if normalized < 0.0:
            raise ValueError("expected_remaining_cost must be >= 0")
        return normalized

    @classmethod
    def from_runtime_state(cls, runtime_state: RuntimeState) -> "RuntimeStateSummary":
        return cls(
            schema_version=runtime_state.schema_version,
            p_success=runtime_state.p_success,
            p_structural_failure=runtime_state.p_structural_failure,
            recovery_margin=runtime_state.recovery_margin,
            expected_remaining_cost=runtime_state.expected_remaining_cost,
            evidence_sufficiency=runtime_state.evidence_sufficiency,
        )


class RecommendationReason(BaseModel):
    """默认建议理由的最小稳定摘要。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    selection_basis: Literal["static_score", "final_score"] = "static_score"
    rerank_applied: bool = False
    static_candidate_id: str | None = None
    static_score_gap: float | None = None
    shadow_candidate_id: str | None = None
    shadow_score_gap: float | None = None
    shadow_only: bool = True

    @field_validator("code", "message")
    @classmethod
    def _validate_text(cls, value: str, info) -> str:
        return _validate_non_empty_text(value, field_name=info.field_name)

    @field_validator("static_candidate_id", "shadow_candidate_id")
    @classmethod
    def _validate_optional_candidate_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_non_empty_text(value, field_name="candidate_id")

    @field_validator("static_score_gap", "shadow_score_gap")
    @classmethod
    def _validate_optional_gap(cls, value: float | None) -> float | None:
        if value is None:
            return value
        return _validate_finite_float_value(value, field_name="score_gap")


class ScoreSummary(BaseModel):
    """动作分或 shadow 分的最小稳定摘要。"""

    model_config = ConfigDict(extra="forbid")

    value: float
    source: str

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: float) -> float:
        normalized = _validate_finite_float_value(value, field_name="value")
        if not 0.0 <= normalized <= 1.0:
            raise ValueError("value must be between 0 and 1")
        return normalized

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        return _validate_non_empty_text(value, field_name="source")


class RuntimeAdjustmentFactor(BaseModel):
    """runtime_adjustment 的可审计单因子。"""

    model_config = ConfigDict(extra="forbid")

    category: Literal["cost", "risk", "recovery", "evidence", "policy"]
    signal: str
    source: str
    contribution: float
    message: str

    @field_validator("signal", "source", "message")
    @classmethod
    def _validate_text(cls, value: str, info) -> str:
        return _validate_non_empty_text(value, field_name=info.field_name)

    @field_validator("contribution")
    @classmethod
    def _validate_contribution(cls, value: float) -> float:
        return _validate_finite_float_value(value, field_name="contribution")


class RuntimeAdjustmentSummary(BaseModel):
    """运行时修正摘要。"""

    model_config = ConfigDict(extra="forbid")

    value: float
    source: str
    formula_version: str = "v1"
    shadow_only: bool = True

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: float) -> float:
        normalized = _validate_finite_float_value(value, field_name="value")
        if not -1.0 <= normalized <= 1.0:
            raise ValueError("value must be between -1 and 1")
        return normalized

    @field_validator("source", "formula_version")
    @classmethod
    def _validate_text(cls, value: str, info) -> str:
        return _validate_non_empty_text(value, field_name=info.field_name)


class RerankReason(BaseModel):
    """shadow rerank 的最小可审计说明。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    shadow_only: bool = True
    runtime_state_fields: List[str] = Field(default_factory=list)
    candidate_metric_fields: List[str] = Field(default_factory=list)
    tool_metadata_fields: List[str] = Field(default_factory=list)
    factors: List[RuntimeAdjustmentFactor] = Field(default_factory=list)

    @field_validator("code", "message")
    @classmethod
    def _validate_text(cls, value: str, info) -> str:
        return _validate_non_empty_text(value, field_name=info.field_name)

    @field_validator(
        "runtime_state_fields",
        "candidate_metric_fields",
        "tool_metadata_fields",
        mode="before",
    )
    @classmethod
    def _normalize_string_list(cls, value: Any, info) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"{info.field_name} must be a list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"{info.field_name} items must be strings")
            normalized.append(_validate_non_empty_text(item, field_name=info.field_name))
        return normalized


class WaitingRuntimeSummary(BaseModel):
    """WAITING 场景下用于 HITL 回放的最小状态摘要。"""

    model_config = ConfigDict(extra="forbid")

    selected_candidate_id: str | None = None
    default_recommendation: str | None = None
    waiting_reason: str | None = None
    runtime_state_summary: RuntimeStateSummary | None = None
    default_recommendation_reason: RecommendationReason | None = None
    static_score: ScoreSummary | None = None
    runtime_adjustment: RuntimeAdjustmentSummary | None = None
    final_score: ScoreSummary | None = None
    rerank_reason: RerankReason | None = None
    action_score: ScoreSummary | None = None
    shadow_score: ScoreSummary | None = None

    @field_validator(
        "selected_candidate_id",
        "default_recommendation",
        "waiting_reason",
    )
    @classmethod
    def _validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return value
        return _validate_non_empty_text(value, field_name=info.field_name)


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
    target: str  # 目标 step_id
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
    """候选方案封装（兼容 CandidateSetOutput v1）。

    Attributes:
        candidate_id: 候选唯一标识。
        payload: 兼容字段，等价于 structured_payload。
        structured_payload: 候选承载的结构化对象（Plan 或 PlanPatch）。
        score_breakdown: 候选打分拆解（feasibility/objective/risk/cost/overall）。
        risk_level: 风险等级（low/medium/high）。
        cost_estimate: 成本等级（low/medium/high）。
        explanation: 候选解释。
        tool_id: 工具标识（与 metadata.tool_id 同步）。
        capability_id: 工具能力标识（与 metadata.capability_id 同步）。
        io_type: I/O 类型标识（与 metadata.io_type 同步）。
        adapter_mode: 适配器模式（local/remote/mock/hybrid/unknown）。
        adapter_id: 代码适配器标识。
        execution_mode: 运行通道标识（local/remote/rest/nim/openfold3_rest 等）。
        provider: 模型或远程服务提供方。
        endpoint_type: endpoint 类型（local/rest/nim 等）。
        remote_job_id: 远程作业 ID（如候选已有关联作业）。
        summary: 候选摘要信息。
        metadata: 额外元数据。
            - `runtime_state_summary` 可承载候选展示所需的轻量状态摘要。
            - `default_recommendation_reason` 可承载默认建议理由。
            - `action_score` / `shadow_score` 用于承载兼容动作分摘要。
            - `static_score` / `runtime_adjustment` / `final_score` / `rerank_reason`
              用于承载 shadow rerank 接口。
    """

    candidate_id: str
    payload: Plan | PlanPatch | None = None
    structured_payload: Plan | PlanPatch | None = None
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    risk_level: Literal["low", "medium", "high"] | None = None
    cost_estimate: Literal["low", "medium", "high"] | None = None
    explanation: str | None = None
    tool_id: str | None = None
    capability_id: str | None = None
    io_type: str | None = None
    adapter_mode: Literal["local", "remote", "mock", "hybrid", "unknown"] | None = None
    adapter_id: str | None = None
    execution_mode: str | None = None
    provider: str | None = None
    endpoint_type: str | None = None
    remote_job_id: str | None = None
    summary: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)

    @field_validator("candidate_id")
    @classmethod
    def _validate_candidate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("candidate_id must not be empty")
        return normalized

    @field_validator("score_breakdown")
    @classmethod
    def _validate_score_breakdown(
        cls, value: Dict[str, float]
    ) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        for key, score in value.items():
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise ValueError(f"score_breakdown[{key}] must be numeric")
            normalized[key] = float(score)
        return normalized

    @field_validator(
        "tool_id",
        "capability_id",
        "io_type",
        "adapter_id",
        "execution_mode",
        "provider",
        "endpoint_type",
        "remote_job_id",
    )
    @classmethod
    def _validate_tool_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool metadata fields must not be empty")
        return normalized

    @model_validator(mode="after")
    def _sync_payload_fields(self):
        payload = self.payload
        structured_payload = self.structured_payload
        if payload is None and structured_payload is None:
            raise ValueError(
                "either payload or structured_payload must be provided"
            )
        if payload is None:
            self.payload = structured_payload
            return self
        if structured_payload is None:
            self.structured_payload = payload
            return self
        if (
            type(payload) is not type(structured_payload)
            or payload.model_dump() != structured_payload.model_dump()
        ):
            raise ValueError("payload and structured_payload must be equivalent")
        return self

    @model_validator(mode="after")
    def _sync_tool_metadata(self):
        metadata = dict(self.metadata or {})
        self.metadata = metadata

        self.tool_id = _sync_metadata_field(
            metadata,
            field_name="tool_id",
            field_value=self.tool_id,
        )
        self.capability_id = _sync_metadata_field(
            metadata,
            field_name="capability_id",
            field_value=self.capability_id,
        )
        self.io_type = _sync_metadata_field(
            metadata,
            field_name="io_type",
            field_value=self.io_type,
        )
        self.adapter_mode = _sync_adapter_mode(
            metadata,
            field_value=self.adapter_mode,
        )
        self.adapter_id = _sync_metadata_field(
            metadata,
            field_name=ADAPTER_ID_METADATA_KEY,
            field_value=self.adapter_id,
        )
        self.execution_mode = _sync_metadata_field(
            metadata,
            field_name=EXECUTION_MODE_METADATA_KEY,
            field_value=self.execution_mode,
        )
        self.provider = _sync_metadata_field(
            metadata,
            field_name=PROVIDER_METADATA_KEY,
            field_value=self.provider,
        )
        self.endpoint_type = _sync_metadata_field(
            metadata,
            field_name=ENDPOINT_TYPE_METADATA_KEY,
            field_value=self.endpoint_type,
        )
        self.remote_job_id = _sync_metadata_field(
            metadata,
            field_name=REMOTE_JOB_ID_METADATA_KEY,
            field_value=self.remote_job_id,
        )

        has_any_tooling = any(
            value is not None
            for value in (
                self.tool_id,
                self.capability_id,
                self.io_type,
                self.adapter_id,
                self.execution_mode,
                self.provider,
                self.endpoint_type,
            )
        )
        if has_any_tooling and self.adapter_mode is None:
            self.adapter_mode = "unknown"
            metadata["adapter_mode"] = self.adapter_mode

        return self

    @model_validator(mode="after")
    def _sync_runtime_state_summary_metadata(self):
        metadata = dict(self.metadata or {})
        self.metadata = metadata
        summary_payload = metadata.get(RUNTIME_STATE_SUMMARY_METADATA_KEY)
        normalized_summary = (
            _normalize_runtime_state_summary(summary_payload)
            if summary_payload is not None
            else None
        )
        if normalized_summary is not None:
            metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY] = normalized_summary
        _normalize_candidate_runtime_contracts(
            metadata,
            runtime_state_summary=normalized_summary,
        )
        return self


def _sync_metadata_field(
    metadata: Dict[str, Any],
    *,
    field_name: str,
    field_value: str | None,
) -> str | None:
    metadata_value = metadata.get(field_name)
    if metadata_value is None:
        if field_value is not None:
            metadata[field_name] = field_value
        return field_value
    if not isinstance(metadata_value, str):
        raise ValueError(f"metadata.{field_name} must be a string")
    normalized = metadata_value.strip()
    if not normalized:
        raise ValueError(f"metadata.{field_name} must not be empty")
    if field_value is None:
        return normalized
    if field_value != normalized:
        raise ValueError(f"metadata.{field_name} must match {field_name}")
    metadata[field_name] = field_value
    return field_value


def _coerce_non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _sync_step_metadata_field(
    metrics: Dict[str, Any],
    *,
    field_name: str,
    field_value: str | None,
) -> str | None:
    metric_value = _coerce_non_empty_text(metrics.get(field_name))
    if metric_value is None:
        if field_value is not None:
            metrics[field_name] = field_value
        return field_value
    if field_value is None:
        return metric_value
    if field_value != metric_value:
        raise ValueError(f"metrics.{field_name} must match {field_name}")
    metrics[field_name] = field_value
    return field_value


def _sync_adapter_mode(
    metadata: Dict[str, Any],
    *,
    field_value: Literal["local", "remote", "mock", "hybrid", "unknown"] | None,
) -> Literal["local", "remote", "mock", "hybrid", "unknown"] | None:
    metadata_value = metadata.get("adapter_mode")
    if metadata_value is None:
        if field_value is not None:
            metadata["adapter_mode"] = field_value
        return field_value
    if not isinstance(metadata_value, str):
        raise ValueError("metadata.adapter_mode must be a string")
    normalized = metadata_value.strip().lower()
    allowed = {"local", "remote", "mock", "hybrid", "unknown"}
    if normalized not in allowed:
        raise ValueError(
            "metadata.adapter_mode must be one of "
            "local, remote, mock, hybrid, unknown"
        )
    if field_value is None:
        metadata["adapter_mode"] = normalized
        return cast(
            Literal["local", "remote", "mock", "hybrid", "unknown"],
            normalized,
        )
    if field_value != normalized:
        raise ValueError("metadata.adapter_mode must match adapter_mode")
    metadata["adapter_mode"] = field_value
    return field_value


def _normalize_runtime_state_summary(summary_payload: Any) -> Dict[str, Any]:
    if isinstance(summary_payload, RuntimeStateSummary):
        return summary_payload.model_dump()
    if isinstance(summary_payload, dict):
        return RuntimeStateSummary.model_validate(summary_payload).model_dump()
    raise ValueError(
        f"metadata.{RUNTIME_STATE_SUMMARY_METADATA_KEY} must be a mapping"
    )


def _normalize_recommendation_reason(reason_payload: Any) -> Dict[str, Any]:
    if isinstance(reason_payload, RecommendationReason):
        return reason_payload.model_dump()
    if isinstance(reason_payload, dict):
        return RecommendationReason.model_validate(reason_payload).model_dump()
    raise ValueError(
        f"metadata.{DEFAULT_RECOMMENDATION_REASON_METADATA_KEY} must be a mapping"
    )


def _normalize_runtime_adjustment_summary(summary_payload: Any) -> Dict[str, Any]:
    if isinstance(summary_payload, RuntimeAdjustmentSummary):
        return summary_payload.model_dump()
    if isinstance(summary_payload, dict):
        return RuntimeAdjustmentSummary.model_validate(summary_payload).model_dump()
    raise ValueError(
        f"metadata.{RUNTIME_ADJUSTMENT_METADATA_KEY} must be a mapping"
    )


def _normalize_rerank_reason(reason_payload: Any) -> Dict[str, Any]:
    if isinstance(reason_payload, RerankReason):
        return reason_payload.model_dump()
    if isinstance(reason_payload, dict):
        return RerankReason.model_validate(reason_payload).model_dump()
    raise ValueError(f"metadata.{RERANK_REASON_METADATA_KEY} must be a mapping")


def _normalize_score_summary(score_payload: Any, *, field_name: str) -> Dict[str, Any]:
    if isinstance(score_payload, ScoreSummary):
        return score_payload.model_dump()
    if isinstance(score_payload, dict):
        return ScoreSummary.model_validate(score_payload).model_dump()
    raise ValueError(f"metadata.{field_name} must be a mapping")


def _normalize_candidate_runtime_contracts(
    metadata: Dict[str, Any],
    *,
    runtime_state_summary: Dict[str, Any] | None = None,
) -> None:
    if runtime_state_summary is not None:
        metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY] = runtime_state_summary

    reason_payload = metadata.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY)
    if reason_payload is not None:
        metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY] = _normalize_recommendation_reason(
            reason_payload
        )

    action_score_payload = metadata.get(ACTION_SCORE_METADATA_KEY)
    if action_score_payload is not None:
        metadata[ACTION_SCORE_METADATA_KEY] = _normalize_score_summary(
            action_score_payload,
            field_name=ACTION_SCORE_METADATA_KEY,
        )

    shadow_score_payload = metadata.get(SHADOW_SCORE_METADATA_KEY)
    if shadow_score_payload is not None:
        metadata[SHADOW_SCORE_METADATA_KEY] = _normalize_score_summary(
            shadow_score_payload,
            field_name=SHADOW_SCORE_METADATA_KEY,
        )

    static_score_payload = metadata.get(STATIC_SCORE_METADATA_KEY)
    if static_score_payload is not None:
        metadata[STATIC_SCORE_METADATA_KEY] = _normalize_score_summary(
            static_score_payload,
            field_name=STATIC_SCORE_METADATA_KEY,
        )

    final_score_payload = metadata.get(FINAL_SCORE_METADATA_KEY)
    if final_score_payload is not None:
        metadata[FINAL_SCORE_METADATA_KEY] = _normalize_score_summary(
            final_score_payload,
            field_name=FINAL_SCORE_METADATA_KEY,
        )

    runtime_adjustment_payload = metadata.get(RUNTIME_ADJUSTMENT_METADATA_KEY)
    if runtime_adjustment_payload is not None:
        metadata[RUNTIME_ADJUSTMENT_METADATA_KEY] = _normalize_runtime_adjustment_summary(
            runtime_adjustment_payload
        )

    rerank_reason_payload = metadata.get(RERANK_REASON_METADATA_KEY)
    if rerank_reason_payload is not None:
        metadata[RERANK_REASON_METADATA_KEY] = _normalize_rerank_reason(
            rerank_reason_payload
        )


def _normalize_waiting_runtime_summary(summary_payload: Any) -> Dict[str, Any]:
    if isinstance(summary_payload, WaitingRuntimeSummary):
        return summary_payload.model_dump(exclude_none=True)
    if isinstance(summary_payload, dict):
        return WaitingRuntimeSummary.model_validate(summary_payload).model_dump(
            exclude_none=True
        )
    raise ValueError(
        f"metadata.{WAITING_RUNTIME_SUMMARY_METADATA_KEY} must be a mapping"
    )


class PendingAction(BaseModel):
    """等待人工决策的结构化对象。

    Attributes:
        pending_action_id: 待决策对象 ID。
        task_id: 任务 ID。
        action_type: 待决策类型。
        candidates: 候选集合。
        explanation: 解释说明文本。
        status: PendingAction 当前状态。
        default_suggestion: 兼容字段，等价于 default_recommendation。
        default_recommendation: 默认建议候选 ID（CandidateSetOutput v1）。
        created_at: 创建时间戳。
        decided_at: 决策完成时间戳。
        created_by: 创建者标识（通常为 system）。
        metadata: WAITING 回放或审计所需的附加摘要。
    """

    pending_action_id: str
    task_id: str
    action_type: PendingActionType
    candidates: List[PendingActionCandidate]
    explanation: str
    status: PendingActionStatus = PendingActionStatus.PENDING
    default_suggestion: Optional[str] = None
    default_recommendation: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    decided_at: Optional[str] = None
    created_by: str = "system"
    metadata: Dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sync_default_recommendation(self):
        suggestion = self.default_suggestion
        recommendation = self.default_recommendation
        if suggestion and recommendation and suggestion != recommendation:
            raise ValueError(
                "default_suggestion and default_recommendation must match"
            )
        resolved = recommendation or suggestion
        self.default_suggestion = resolved
        self.default_recommendation = resolved
        return self

    @model_validator(mode="after")
    def _sync_waiting_runtime_summary_metadata(self):
        metadata = dict(self.metadata or {})
        self.metadata = metadata
        summary_payload = metadata.get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
        if summary_payload is None:
            return self
        metadata[WAITING_RUNTIME_SUMMARY_METADATA_KEY] = _normalize_waiting_runtime_summary(
            summary_payload
        )
        return self


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
            raise ValueError("selected_candidate_id is required when choice is accept")
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
