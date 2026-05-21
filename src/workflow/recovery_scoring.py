from __future__ import annotations


def compute_stop_utility(
    *,
    p_success: float,
    budget_pressure: float,
    recovery_margin: float,
    safety_terminality: float,
    intervention_value: float,
) -> float:
    return _clip_float(
        0.32 * (1.0 - p_success)
        + 0.24 * min(budget_pressure, 1.0)
        + 0.18 * (1.0 - recovery_margin)
        + 0.16 * safety_terminality
        + 0.10 * (1.0 - intervention_value),
        lower=0.0,
        upper=1.0,
    )


def _clip_float(value: float, *, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))
