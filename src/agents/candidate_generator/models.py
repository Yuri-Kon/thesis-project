from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Sequence

from src.models.contracts import PendingActionCandidate, Plan, PlanPatch


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
    registry: Sequence[Any]
    top_k: int = 3
    task_constraints: dict[str, Any] | None = None
    confirmed_task_spec: dict[str, Any] | None = None
    capability_hints: Sequence[str] = ()
    readiness: dict[str, Any] | None = None
    completed_step_results: Sequence[Any] = ()
    runtime_state: Any | None = None
    budget: dict[str, Any] | None = None
    policy_mode: str = "balanced"


@dataclass(frozen=True)
class CandidateGeneratorHooks:
    """Planner 既有评分与展示函数注入点。"""

    canonical_payload_fingerprint: Callable[[Plan | PlanPatch, str, str], str]
    resolve_score_weights: Callable[[dict[str, Any]], dict[str, float]]
    score_payload: Callable[..., dict[str, float]]
    primary_capability: Callable[[Any | None], str]
    derive_cost_estimate: Callable[[Plan | PlanPatch, Sequence[Any]], str]
    derive_risk_level: Callable[[Plan | PlanPatch, Sequence[Any]], str]
    stable_candidate_id: Callable[[str, Plan | PlanPatch, str, str], str]
    build_s5_scoring_contract: Callable[[dict[str, float]], dict[str, Any]]
    build_static_score_summary: Callable[[dict[str, float]], dict[str, Any]]
    build_action_score_summary: Callable[[dict[str, float]], dict[str, Any]]
    candidate_readiness_metadata: Callable[..., dict[str, Any]]
    build_candidate_summary: Callable[[Plan | PlanPatch], str]
    extract_patch_candidate_metadata: Callable[[PlanPatch], dict[str, Any]]
    extract_plan_candidate_metadata: Callable[[Plan], dict[str, Any]]
    normalize_runtime_state_summary_input: Callable[[Any | None], dict[str, Any] | None]
    build_shadow_passthrough_decision: Callable[[dict[str, float]], Any]
    build_runtime_shadow_decision: Callable[..., Any]
    priority_rank: Callable[[str | None], int]
    patch_layer_rank: Callable[[Plan | PlanPatch], int]
    extract_score_value: Callable[[PendingActionCandidate, str], float]
    build_default_recommendation_reason: Callable[..., dict[str, Any]]
    summarize_rerank_reason: Callable[[PendingActionCandidate], str]
