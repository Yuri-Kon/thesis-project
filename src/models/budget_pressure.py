"""预算压力的统一派生规则。"""

from __future__ import annotations

from dataclasses import dataclass

BUDGET_PRESSURE_SOURCE_REFS: tuple[str, ...] = (
    "sid:planner.runtime.belief_state_schema",
    "impl:budget_pressure.v1",
)
BUDGET_PRESSURE_MAX = 1.5
BUDGET_CAP_FLOOR = 0.1


@dataclass(frozen=True)
class BudgetPressureDerivation:
    """预算压力派生结果。"""

    expected_remaining_cost: float
    budget_pressure: float
    budget_cap: float | None
    source_fields: tuple[str, ...]
    reason: str


def derive_budget_pressure(
    *,
    expected_remaining_cost: float,
    budget_cap: float | None = None,
) -> BudgetPressureDerivation:
    """从原始剩余成本和可选预算上限派生预算压力。

    Args:
        expected_remaining_cost: 原始剩余成本暴露，允许大于 1。
        budget_cap: 可选预算上限；存在时作为归一化分母。

    Returns:
        裁剪到 `[0, 1.5]` 的预算压力及其来源说明。
    """

    remaining = max(float(expected_remaining_cost), 0.0)
    normalized_cap = _normalize_budget_cap(budget_cap)
    if normalized_cap is None:
        return BudgetPressureDerivation(
            expected_remaining_cost=remaining,
            budget_pressure=round(_clip_pressure(remaining), 6),
            budget_cap=None,
            source_fields=("runtime_state.expected_remaining_cost",),
            reason=(
                "Budget pressure falls back to clipped expected remaining cost "
                "because no budget cap is available."
            ),
        )
    return BudgetPressureDerivation(
        expected_remaining_cost=remaining,
        budget_pressure=round(_clip_pressure(remaining / normalized_cap), 6),
        budget_cap=normalized_cap,
        source_fields=(
            "runtime_state.expected_remaining_cost",
            "runtime_state.budget_cap",
        ),
        reason=(
            "Budget pressure is expected remaining cost normalized by budget cap."
        ),
    )


def coerce_optional_budget_cap(value: object) -> float | None:
    """解析可选预算上限，非法或非正值按缺失处理。"""

    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return _normalize_budget_cap(parsed)


def coerce_optional_budget_pressure(value: object) -> float | None:
    """解析可选预算压力，非法值按缺失处理。"""

    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return _clip_pressure(parsed)


def _normalize_budget_cap(value: float | None) -> float | None:
    if value is None:
        return None
    normalized = float(value)
    if normalized <= 0.0:
        return None
    return max(normalized, BUDGET_CAP_FLOOR)


def _clip_pressure(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > BUDGET_PRESSURE_MAX:
        return BUDGET_PRESSURE_MAX
    return value
