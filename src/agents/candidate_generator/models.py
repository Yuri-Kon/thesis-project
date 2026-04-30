from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping, Sequence
from typing import Literal, Protocol, TypeAlias

from src.models.contracts import PendingActionCandidate, Plan, PlanPatch

AdapterMode: TypeAlias = Literal["local", "remote", "mock", "hybrid", "unknown"]
Level: TypeAlias = Literal["low", "medium", "high"]
Metadata: TypeAlias = dict[str, object]
MetadataMapping: TypeAlias = Mapping[str, object]
SortKey: TypeAlias = (
    tuple[int, float, int, str, str, str] | tuple[float, int, str, str, str]
)


class ToolSpecLike(Protocol):
    """CandidateGenerator 使用的工具规格最小结构。"""

    id: str
    capabilities: Sequence[str]
    inputs: Sequence[str]
    outputs: Sequence[str]
    cost: float
    safety_level: int
    io_type: str | None
    adapter_mode: AdapterMode
    priority: str | None


class CompletedStepResultLike(Protocol):
    """CandidateGenerator 读取已完成步骤结果时需要的最小结构。"""

    outputs: Mapping[str, object]


class RuntimeShadowDecisionLike(Protocol):
    """Planner shadow rerank 决策对象的最小结构。"""

    shadow_score: Metadata
    final_score: Metadata
    runtime_adjustment: Metadata
    rerank_reason: Metadata
    shadow_action: str
    shadow_reason: str
    explanation_fragment: str


@dataclass(frozen=True)
class TopKResult:
    """Planner Top-K 候选输出（CandidateSetOutput v1 对齐）。"""

    candidates: list[PendingActionCandidate]
    default_recommendation: str | None
    explanation: str

    @property
    def default_suggestion(self) -> str | None:
        """兼容 HITL/UI 文案中的 default_suggestion 命名。"""
        return self.default_recommendation


@dataclass(frozen=True)
class CandidatePayload:
    """CandidateGenerator 的统一候选载荷。"""

    payload: Plan | PlanPatch
    primary_tool_id: str
    capability_bucket: str
    note: str
    recovery_layer: str | None = None
    recovery_reason: str | None = None


@dataclass(frozen=True)
class CandidateGenerationInput:
    """候选生成统一入口输入。"""

    candidate_kind: Literal["plan", "patch", "replan"]
    payloads: Sequence[CandidatePayload]
    registry: Sequence[ToolSpecLike]
    top_k: int = 3
    task_constraints: MetadataMapping | None = None
    confirmed_task_spec: MetadataMapping | None = None
    capability_hints: Sequence[str] = ()
    readiness: MetadataMapping | None = None
    completed_step_results: Sequence[CompletedStepResultLike] = ()
    runtime_state: object | None = None
    budget: MetadataMapping | None = None
    policy_mode: str = "balanced"


@dataclass(frozen=True)
class CandidateGeneratorHooks:
    """Planner 既有评分与展示函数注入点。"""

    canonical_payload_fingerprint: Callable[[Plan | PlanPatch, str, str], str]
    resolve_score_weights: Callable[[MetadataMapping], dict[str, float]]
    score_payload: Callable[..., dict[str, float]]
    primary_capability: Callable[[ToolSpecLike | None], str]
    derive_cost_estimate: Callable[[Plan | PlanPatch, Sequence[ToolSpecLike]], str]
    derive_risk_level: Callable[[Plan | PlanPatch, Sequence[ToolSpecLike]], str]
    stable_candidate_id: Callable[[str, Plan | PlanPatch, str, str], str]
    build_s5_scoring_contract: Callable[[dict[str, float]], Metadata]
    build_static_score_summary: Callable[[dict[str, float]], Metadata]
    build_action_score_summary: Callable[[dict[str, float]], Metadata]
    candidate_readiness_metadata: Callable[..., Metadata]
    build_candidate_summary: Callable[[Plan | PlanPatch], str]
    extract_patch_candidate_metadata: Callable[[PlanPatch], Metadata]
    extract_plan_candidate_metadata: Callable[[Plan], Metadata]
    normalize_runtime_state_summary_input: Callable[[object | None], Metadata | None]
    build_shadow_passthrough_decision: Callable[
        [dict[str, float]], RuntimeShadowDecisionLike
    ]
    build_runtime_shadow_decision: Callable[..., RuntimeShadowDecisionLike]
    priority_rank: Callable[[str | None], int]
    patch_layer_rank: Callable[[Plan | PlanPatch], int]
    extract_score_value: Callable[[PendingActionCandidate, str], float]
    build_default_recommendation_reason: Callable[..., Metadata]
    summarize_rerank_reason: Callable[[PendingActionCandidate], str]
