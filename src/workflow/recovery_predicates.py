from __future__ import annotations


def has_failure_signal(
    *,
    failure_type_present: bool,
    failure_code_present: bool,
    retry_exhausted: bool,
    safety_blocked: bool,
) -> bool:
    return (
        failure_type_present
        or failure_code_present
        or retry_exhausted
        or safety_blocked
    )


def is_hard_blocked_suggestion(
    *,
    suggested_action: str,
    safety_blocked: bool,
) -> bool:
    return safety_blocked and suggested_action == "continue"


def should_choose_stop(
    *,
    allowed_actions: frozenset[str],
    allow_auto_stop: bool,
    u_stop: float,
    p_success: float,
    budget_pressure: float,
    recovery_margin: float,
    intervention_value: float,
) -> bool:
    if "stop" not in allowed_actions:
        return False
    if allow_auto_stop and u_stop >= 0.72:
        return True
    return (
        p_success <= 0.20
        and budget_pressure >= 0.85
        and recovery_margin <= 0.20
        and intervention_value <= 0.35
    )
