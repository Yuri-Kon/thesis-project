from __future__ import annotations

from typing import Optional

from src.models.contracts import (Decision, DecisionChoice, PendingAction,
                                  PendingActionCandidate, PendingActionType)

ALLOWED_DECISION_CHOICES = {
    PendingActionType.PLAN_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.REPLAN,
        DecisionChoice.CANCEL,
    },
    PendingActionType.PATCH_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.REPLAN,
        DecisionChoice.CANCEL,
    },
    PendingActionType.REPLAN_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.CONTINUE,
        DecisionChoice.CANCEL,
    },
}


class DecisionValidationError(ValueError):
    """Decision 与 PendingAction 约束冲突时抛出。"""


class CandidateSetValidationError(ValueError):
    """CandidateSetOutput 契约校验失败时抛出。"""


REQUIRED_SCORE_BREAKDOWN_FIELDS = frozenset(
    {"feasibility", "objective", "risk", "cost", "overall"}
)


def validate_candidate_set_output(
    pending_action: PendingAction,
    *,
    require_v1_fields: bool = True,
    require_default_recommendation: bool = True,
) -> None:
    """校验 CandidateSetOutput 契约（用于 Planner/HITL 输出）。

    Args:
        pending_action: 待校验的 PendingAction 对象。
        require_v1_fields: 是否要求每个候选必须包含 v1 字段集。
        require_default_recommendation: 是否要求存在默认推荐候选。

    Raises:
        CandidateSetValidationError: 候选字段或集合约束不满足。
    """
    if not pending_action.candidates:
        raise CandidateSetValidationError("candidates must not be empty")

    seen_ids: set[str] = set()
    for candidate in pending_action.candidates:
        candidate_id = _resolve_candidate_id(candidate)
        if not candidate_id:
            raise CandidateSetValidationError("candidate_id is required")
        if candidate_id in seen_ids:
            raise CandidateSetValidationError(
                f"candidate_id {candidate_id} is duplicated"
            )
        seen_ids.add(candidate_id)
        if require_v1_fields:
            _validate_candidate_v1_fields(candidate, candidate_id)

    default_id = (
        pending_action.default_recommendation or pending_action.default_suggestion
    )
    if require_default_recommendation and not default_id:
        raise CandidateSetValidationError(
            "default_recommendation is required for candidate set output"
        )
    if default_id and default_id not in seen_ids:
        raise CandidateSetValidationError(
            "default_recommendation is not in candidates"
        )


def _validate_candidate_v1_fields(
    candidate: PendingActionCandidate, candidate_id: str
) -> None:
    if candidate.structured_payload is None:
        raise CandidateSetValidationError(
            f"{candidate_id}.structured_payload is required"
        )
    if not candidate.score_breakdown:
        raise CandidateSetValidationError(f"{candidate_id}.score_breakdown is required")
    missing_keys = REQUIRED_SCORE_BREAKDOWN_FIELDS - set(candidate.score_breakdown)
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise CandidateSetValidationError(
            f"{candidate_id}.score_breakdown missing keys: {missing}"
        )
    if candidate.risk_level is None:
        raise CandidateSetValidationError(f"{candidate_id}.risk_level is required")
    if candidate.cost_estimate is None:
        raise CandidateSetValidationError(f"{candidate_id}.cost_estimate is required")
    if not candidate.explanation:
        raise CandidateSetValidationError(f"{candidate_id}.explanation is required")


def validate_decision_for_pending_action(
    pending_action: PendingAction,
    decision: Decision,
) -> None:
    """验证 Decision 是否可用于驱动 PendingAction。

    Args:
        pending_action: 待校验的 PendingAction。
        decision: 人工提交的 Decision。

    Raises:
        DecisionValidationError: 当 choice 非法、accept 缺少候选 ID，或候选不在列表中。
    """
    allowed_choices = ALLOWED_DECISION_CHOICES.get(pending_action.action_type)
    if allowed_choices is None:
        raise DecisionValidationError(
            f"Unsupported pending action type: {pending_action.action_type.value}"
        )
    if decision.choice not in allowed_choices:
        raise DecisionValidationError(
            f"Choice {decision.choice.value} is not allowed for "
            f"{pending_action.action_type.value}"
        )
    if decision.choice == DecisionChoice.ACCEPT:
        if not decision.selected_candidate_id:
            raise DecisionValidationError(
                "selected_candidate_id is required for accept"
            )
        candidate = find_pending_action_candidate(
            pending_action,
            decision.selected_candidate_id,
        )
        if candidate is None:
            raise DecisionValidationError("selected_candidate_id is not in candidates")


def find_pending_action_candidate(
    pending_action: PendingAction,
    candidate_id: str,
) -> Optional[PendingActionCandidate]:
    """在 PendingAction.candidates 中查找指定候选。

    Args:
        pending_action: 含候选列表的 PendingAction。
        candidate_id: 目标候选 ID。

    Returns:
        匹配的候选对象，未找到则返回 None。
    """
    for candidate in pending_action.candidates:
        resolved_id = _resolve_candidate_id(candidate)
        if resolved_id == candidate_id:
            return candidate
    return None


def _resolve_candidate_id(
    candidate: PendingActionCandidate,
) -> Optional[str]:
    """兼容不同字段命名以解析候选 ID。

    Args:
        candidate: 候选对象。

    Returns:
        候选 ID；若字段缺失则返回 None。
    """
    candidate_id = getattr(candidate, "candidate_id", None)
    if candidate_id is not None:
        return candidate_id
    return getattr(candidate, "id", None)
