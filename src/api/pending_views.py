from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, Field

from src.api.event_filters import normalize_text
from src.api.view_models import PendingActionToolDisplay, build_tool_display
from src.models.contracts import (
    ACTION_UTILITY_METADATA_KEY,
    DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
    FINAL_SCORE_METADATA_KEY,
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    PendingActionType,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
    RUNTIME_STATE_SUMMARY_METADATA_KEY,
    STATIC_SCORE_METADATA_KEY,
    WAITING_RUNTIME_SUMMARY_METADATA_KEY,
)
from src.models.db import TaskRecord

type ViewValue = str | int | float | bool | None | dict[str, object] | list[object]
type ViewObject = dict[str, object]


class PendingActionSummary(BaseModel):
    pending_action_id: str = Field(..., description="PendingAction ID")
    task_id: str = Field(..., description="所属任务 ID")
    action_type: PendingActionType = Field(..., description="待决策类型")
    status: PendingActionStatus = Field(..., description="PendingAction 状态")
    created_at: str = Field(..., description="创建时间")
    candidate_count: int = Field(..., description="候选数量")
    default_suggestion: str | None = Field(None, description="默认建议候选 ID")
    explanation: str = Field(..., description="待决策说明")
    summary: str = Field(..., description="候选摘要")


class PendingActionCandidateDisplay(BaseModel):
    rank: int = Field(..., description="候选排名（按返回顺序）")
    candidate_id: str
    is_default: bool
    summary: str
    explanation: str
    recommendation_reason: str
    risk_level: str | None = None
    cost_estimate: str | None = None
    expected_effect: str | None = None
    affected_steps: list[str] = Field(default_factory=list)
    recovery_semantics: str | None = None
    overall_score: float | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    runtime_state_summary: ViewObject = Field(default_factory=dict)
    workflow_action_reason: str | None = None
    theory_objects: ViewObject = Field(default_factory=dict)
    evidence_refs: list[ViewObject] = Field(default_factory=list)
    tool: PendingActionToolDisplay


class PendingActionDetail(BaseModel):
    pending_action_id: str
    task_id: str
    action_type: PendingActionType
    status: PendingActionStatus
    created_at: str
    default_suggestion: str | None = None
    explanation: str
    recommendation_summary: str
    runtime_state_summary: ViewObject = Field(default_factory=dict)
    workflow_action_reason: str | None = None
    theory_objects: ViewObject = Field(default_factory=dict)
    evidence_refs: list[ViewObject] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    candidates: list[PendingActionCandidateDisplay] = Field(default_factory=list)


def build_pending_action_summary(pending_action: PendingAction) -> str:
    """构造列表页摘要，只暴露候选概要而非完整候选内部结构。"""

    if not pending_action.candidates:
        return pending_action.explanation

    snippets: list[str] = []
    for candidate in pending_action.candidates[:2]:
        text = candidate.summary or candidate.explanation or candidate.candidate_id
        snippets.append(text.strip())

    summary = " | ".join(snippets)
    hidden_count = len(pending_action.candidates) - len(snippets)
    if hidden_count > 0:
        summary = f"{summary} | +{hidden_count} more"
    return summary


def build_pending_action_summary_model(
    *,
    task_id: str,
    pending_action: PendingAction,
) -> PendingActionSummary:
    """将 PendingAction 转成列表 API 的稳定摘要 DTO。"""

    return PendingActionSummary(
        pending_action_id=pending_action.pending_action_id,
        task_id=task_id,
        action_type=pending_action.action_type,
        status=pending_action.status,
        created_at=pending_action.created_at,
        candidate_count=len(pending_action.candidates),
        default_suggestion=(
            pending_action.default_suggestion or pending_action.default_recommendation
        ),
        explanation=pending_action.explanation,
        summary=build_pending_action_summary(pending_action),
    )


def build_pending_action_detail(
    record: TaskRecord,
    pending_action: PendingAction,
) -> PendingActionDetail:
    """构造 PendingAction 详情 DTO，隐藏 evidence / score 的组合细节。"""

    default_suggestion = (
        pending_action.default_suggestion or pending_action.default_recommendation
    )
    pending_evidence = _workflow_evidence_from_pending_action(pending_action)
    candidates = [
        _build_candidate_display(
            index=index,
            candidate=candidate,
            pending_action=pending_action,
            pending_evidence=pending_evidence,
            default_suggestion=default_suggestion,
        )
        for index, candidate in enumerate(pending_action.candidates, start=1)
    ]

    return PendingActionDetail(
        pending_action_id=pending_action.pending_action_id,
        task_id=record.id,
        action_type=pending_action.action_type,
        status=pending_action.status,
        created_at=pending_action.created_at,
        default_suggestion=default_suggestion,
        explanation=pending_action.explanation,
        recommendation_summary=_build_recommendation_summary(
            pending_action=pending_action,
            candidates=candidates,
            default_suggestion=default_suggestion,
        ),
        runtime_state_summary=_pending_runtime_state_summary(
            pending_action,
            pending_evidence,
        ),
        workflow_action_reason=_pending_workflow_action_reason(
            pending_action,
            pending_evidence,
        ),
        theory_objects=_pending_theory_objects(
            pending_action,
            pending_evidence,
            candidates,
        ),
        evidence_refs=_list_of_dicts(pending_evidence.get("evidence_refs")),
        score_breakdown=_default_score_breakdown(candidates),
        candidates=candidates,
    )


def _build_candidate_display(
    *,
    index: int,
    candidate: PendingActionCandidate,
    pending_action: PendingAction,
    pending_evidence: ViewObject,
    default_suggestion: str | None,
) -> PendingActionCandidateDisplay:
    is_default = candidate.candidate_id == default_suggestion
    summary = candidate.summary or candidate.explanation or candidate.candidate_id
    explanation = candidate.explanation or summary
    score_breakdown = _score_breakdown(candidate)
    tool_display = build_tool_display(candidate)
    return PendingActionCandidateDisplay(
        rank=index,
        candidate_id=candidate.candidate_id,
        is_default=is_default,
        summary=summary,
        explanation=explanation,
        recommendation_reason=_build_candidate_reason(
            candidate,
            is_default=is_default,
            tool_display=tool_display,
        ),
        risk_level=candidate.risk_level,
        cost_estimate=candidate.cost_estimate,
        expected_effect=_candidate_expected_effect(candidate),
        affected_steps=_candidate_affected_steps(candidate),
        recovery_semantics=_candidate_recovery_semantics(candidate),
        overall_score=score_breakdown.get("overall"),
        score_breakdown=score_breakdown,
        runtime_state_summary=_candidate_runtime_state_summary(
            candidate,
            pending_evidence,
        ),
        workflow_action_reason=_candidate_workflow_action_reason(
            candidate,
            pending_evidence,
        ),
        theory_objects=_candidate_theory_objects(
            candidate,
            pending_action,
            pending_evidence,
        ),
        evidence_refs=_candidate_evidence_refs(candidate, pending_evidence),
        tool=tool_display,
    )


def _build_candidate_reason(
    candidate: PendingActionCandidate,
    *,
    is_default: bool,
    tool_display: PendingActionToolDisplay,
) -> str:
    reason_parts: list[str] = []
    if is_default:
        reason_parts.append("默认推荐")
    overall = candidate.score_breakdown.get("overall")
    if isinstance(overall, (int, float)):
        reason_parts.append(f"overall={float(overall):.2f}")
    reason_parts.append(f"risk={candidate.risk_level or 'unknown'}")
    reason_parts.append(f"cost={candidate.cost_estimate or 'unknown'}")
    reason_parts.append(f"tool_source={tool_display.source}")
    if tool_display.execution_mode:
        reason_parts.append(f"execution_mode={tool_display.execution_mode}")
    if tool_display.provider:
        reason_parts.append(f"provider={tool_display.provider}")
    if tool_display.readiness_status:
        reason_parts.append(f"readiness={tool_display.readiness_status}")
    if tool_display.can_fallback:
        reason_parts.append("supports_fallback")
    return "; ".join(reason_parts)


def _build_recommendation_summary(
    *,
    pending_action: PendingAction,
    candidates: list[PendingActionCandidateDisplay],
    default_suggestion: str | None,
) -> str:
    if not default_suggestion:
        return pending_action.explanation
    default_candidate = next(
        (item for item in candidates if item.candidate_id == default_suggestion),
        None,
    )
    if default_candidate is not None:
        return f"default={default_suggestion}; {default_candidate.recommendation_reason}"
    return f"default={default_suggestion}; reason not found"


def _default_score_breakdown(
    candidates: list[PendingActionCandidateDisplay],
) -> dict[str, float]:
    default_candidate = next((item for item in candidates if item.is_default), None)
    if default_candidate is not None:
        return default_candidate.score_breakdown
    if candidates:
        return candidates[0].score_breakdown
    return {}


def _score_breakdown(candidate: PendingActionCandidate) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in candidate.score_breakdown.items()
    }


def _dict_or_empty(value: object) -> ViewObject:
    if not isinstance(value, dict):
        return {}
    return _mapping_to_view_object(cast(Mapping[object, object], value))


def _list_of_dicts(value: object) -> list[ViewObject]:
    if not isinstance(value, list):
        return []
    rows: list[ViewObject] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, dict):
            rows.append(_mapping_to_view_object(cast(Mapping[object, object], item)))
    return rows


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item
        for item in cast(Sequence[object], value)
        if isinstance(item, str) and item.strip()
    ]


def _message_from_reason(value: object) -> str | None:
    if isinstance(value, dict):
        payload = cast(Mapping[object, object], value)
        message = normalize_text(payload.get("message"))
        code = normalize_text(payload.get("code"))
        return message or code
    return normalize_text(value)


def _compact_numeric_summary(
    value: object,
    *,
    keys: tuple[str, ...],
) -> ViewObject:
    payload = _dict_or_empty(value)
    if not payload:
        return {}

    summary: ViewObject = {}
    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            summary[key] = float(raw)
    for key in ("source", "formula_version", "shadow_only", "action"):
        raw = payload.get(key)
        if isinstance(raw, (str, bool)):
            summary[key] = raw
    return summary


def _score_summary_from_score_breakdown(
    score_breakdown: dict[str, float],
) -> ViewObject:
    overall = score_breakdown.get("overall")
    if not isinstance(overall, (int, float)) or isinstance(overall, bool):
        return {}
    return {
        "value": float(overall),
        "source": "score_breakdown.overall",
    }


def _selected_action_utility(
    pending_evidence: ViewObject,
    selected_action: str | None,
) -> ViewObject:
    action_utilities = _dict_or_empty(pending_evidence.get("action_utilities"))
    if selected_action:
        summary = _compact_numeric_summary(
            action_utilities.get(selected_action),
            keys=("utility", "value", "budget_pressure", "intervention_value"),
        )
        if summary:
            return summary
    explicit = _compact_numeric_summary(
        pending_evidence.get(ACTION_UTILITY_METADATA_KEY),
        keys=("utility", "value", "budget_pressure", "intervention_value"),
    )
    if explicit:
        return explicit
    if len(action_utilities) == 1:
        only_key, only_value = next(iter(action_utilities.items()))
        summary = _compact_numeric_summary(
            only_value,
            keys=("utility", "value", "budget_pressure", "intervention_value"),
        )
        if summary:
            _ = summary.setdefault("action", only_key)
            return summary
    return {}


def _workflow_evidence_from_pending_action(
    pending_action: PendingAction,
) -> ViewObject:
    evidence = _pending_metadata(pending_action).get("workflow_action_evidence")
    return _dict_or_empty(evidence)


def _candidate_runtime_state_summary(
    candidate: PendingActionCandidate,
    pending_evidence: ViewObject,
) -> ViewObject:
    metadata = candidate.metadata
    return (
        _dict_or_empty(metadata.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
        or _dict_or_empty(pending_evidence.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
    )


def _candidate_workflow_action_reason(
    candidate: PendingActionCandidate,
    pending_evidence: ViewObject,
) -> str | None:
    metadata = candidate.metadata
    return (
        _message_from_reason(metadata.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or _message_from_reason(pending_evidence.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or normalize_text(metadata.get("workflow_action_reason"))
        or normalize_text(metadata.get("rerank_reason"))
    )


def _candidate_evidence_refs(
    candidate: PendingActionCandidate,
    pending_evidence: ViewObject,
) -> list[ViewObject]:
    metadata = candidate.metadata
    return (
        _list_of_dicts(metadata.get("evidence_refs"))
        or _list_of_dicts(pending_evidence.get("evidence_refs"))
    )


def _candidate_theory_objects(
    candidate: PendingActionCandidate,
    pending_action: PendingAction,
    pending_evidence: ViewObject,
) -> ViewObject:
    metadata = candidate.metadata
    waiting_summary = _dict_or_empty(
        _pending_metadata(pending_action).get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
    )
    runtime_summary = _candidate_runtime_state_summary(candidate, pending_evidence)
    selected_action = (
        normalize_text(pending_evidence.get("selected_action"))
        or normalize_text(_pending_metadata(pending_action).get("workflow_action"))
        or normalize_text(waiting_summary.get("selected_action"))
    )

    theory = _candidate_score_theory(
        metadata=metadata,
        waiting_summary=waiting_summary,
        pending_evidence=pending_evidence,
        score_breakdown=candidate.score_breakdown,
    )
    if selected_action:
        theory["selected_action"] = selected_action

    action_utility = _selected_action_utility(pending_evidence, selected_action)
    if action_utility:
        theory["action_utility"] = action_utility

    _merge_numeric_runtime_flags(
        theory=theory,
        pending_evidence=pending_evidence,
        runtime_summary=runtime_summary,
    )
    return theory


def _candidate_score_theory(
    *,
    metadata: Mapping[str, object],
    waiting_summary: ViewObject,
    pending_evidence: ViewObject,
    score_breakdown: dict[str, float],
) -> ViewObject:
    static_score = (
        _compact_numeric_summary(metadata.get(STATIC_SCORE_METADATA_KEY), keys=("value",))
        or _compact_numeric_summary(waiting_summary.get(STATIC_SCORE_METADATA_KEY), keys=("value",))
        or _score_summary_from_score_breakdown(score_breakdown)
    )
    runtime_adjustment = (
        _compact_numeric_summary(metadata.get(RUNTIME_ADJUSTMENT_METADATA_KEY), keys=("value",))
        or _compact_numeric_summary(waiting_summary.get(RUNTIME_ADJUSTMENT_METADATA_KEY), keys=("value",))
        or _compact_numeric_summary(pending_evidence.get(RUNTIME_ADJUSTMENT_METADATA_KEY), keys=("value",))
    )
    final_score = (
        _compact_numeric_summary(metadata.get(FINAL_SCORE_METADATA_KEY), keys=("value",))
        or _compact_numeric_summary(waiting_summary.get(FINAL_SCORE_METADATA_KEY), keys=("value",))
    )

    theory: ViewObject = {}
    for key, value in (
        ("static_score", static_score),
        ("runtime_adjustment", runtime_adjustment),
        ("final_score", final_score),
    ):
        if value:
            theory[key] = value
    return theory


def _pending_theory_objects(
    pending_action: PendingAction,
    pending_evidence: ViewObject,
    candidates: list[PendingActionCandidateDisplay],
) -> ViewObject:
    if candidates:
        default_candidate = next((item for item in candidates if item.is_default), None)
        selected_candidate = default_candidate or candidates[0]
        theory = dict(selected_candidate.theory_objects)
    else:
        theory = {}

    waiting_summary = _dict_or_empty(
        _pending_metadata(pending_action).get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
    )
    selected_action = (
        normalize_text(pending_evidence.get("selected_action"))
        or normalize_text(_pending_metadata(pending_action).get("workflow_action"))
        or normalize_text(waiting_summary.get("selected_action"))
    )
    if selected_action:
        theory["selected_action"] = selected_action

    action_utility = _selected_action_utility(pending_evidence, selected_action)
    if action_utility:
        theory["action_utility"] = action_utility

    _merge_numeric_runtime_flags(
        theory=theory,
        pending_evidence=pending_evidence,
        runtime_summary=_pending_runtime_state_summary(pending_action, pending_evidence),
    )
    return theory


def _merge_numeric_runtime_flags(
    *,
    theory: ViewObject,
    pending_evidence: ViewObject,
    runtime_summary: ViewObject,
) -> None:
    for key in ("evidence_sufficiency", "budget_pressure"):
        raw = pending_evidence.get(key, runtime_summary.get(key))
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            theory[key] = float(raw)


def _candidate_affected_steps(candidate: PendingActionCandidate) -> list[str]:
    metadata = candidate.metadata
    explicit = _string_list(metadata.get("affected_steps")) or _string_list(
        metadata.get("affected_step_ids")
    )
    if explicit:
        return explicit

    operations = getattr(candidate.payload, "operations", None)
    if not isinstance(operations, Sequence):
        return []

    steps: list[str] = []
    for operation in operations:
        step_id = getattr(operation, "step_id", None)
        if isinstance(step_id, str) and step_id.strip():
            steps.append(step_id)
    return list(dict.fromkeys(steps))


def _candidate_expected_effect(candidate: PendingActionCandidate) -> str | None:
    metadata = candidate.metadata
    return (
        normalize_text(metadata.get("expected_effect"))
        or normalize_text(metadata.get("expected_effect_summary"))
        or normalize_text(metadata.get("recommendation_effect"))
    )


def _candidate_recovery_semantics(candidate: PendingActionCandidate) -> str | None:
    metadata = candidate.metadata
    return (
        normalize_text(metadata.get("recovery_semantics"))
        or normalize_text(metadata.get("recovery_action"))
        or normalize_text(metadata.get("recovery_layer"))
        or normalize_text(metadata.get("workflow_action"))
        or normalize_text(metadata.get("terminal_policy"))
    )


def _pending_runtime_state_summary(
    pending_action: PendingAction,
    pending_evidence: ViewObject,
) -> ViewObject:
    waiting_summary = _dict_or_empty(
        _pending_metadata(pending_action).get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
    )
    return (
        _dict_or_empty(waiting_summary.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
        or _dict_or_empty(pending_evidence.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
    )


def _pending_workflow_action_reason(
    pending_action: PendingAction,
    pending_evidence: ViewObject,
) -> str | None:
    waiting_summary = _dict_or_empty(
        _pending_metadata(pending_action).get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
    )
    return (
        _message_from_reason(waiting_summary.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or _message_from_reason(pending_evidence.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or normalize_text(_pending_metadata(pending_action).get("workflow_action_reason"))
        or normalize_text(pending_action.explanation)
    )


def _pending_metadata(pending_action: PendingAction) -> Mapping[str, object]:
    return cast(Mapping[str, object], pending_action.metadata)


def _mapping_to_view_object(value: Mapping[object, object]) -> ViewObject:
    return {str(key): item for key, item in value.items() if isinstance(key, str)}
