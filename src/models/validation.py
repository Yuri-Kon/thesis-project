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
