from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteTriggerSpec:
    reason: str
    threshold: str


def schema_failure_route_trigger(
    *,
    enable_dual_route: bool,
    schema_fail_streak: int,
    threshold: int,
) -> RouteTriggerSpec | None:
    """判断 schema 连续失败是否应该触发 external planner fallback。"""

    if not enable_dual_route or schema_fail_streak < threshold:
        return None
    return RouteTriggerSpec(
        reason="schema_fail_streak",
        threshold=f"schema_fail_streak={schema_fail_streak}>={threshold}",
    )


def executable_rate_route_trigger(
    *,
    enable_dual_route: bool,
    use_external: bool,
    fallback_available: bool,
    executable_rate: float,
    previous_rate: float | None,
    rate_threshold: float,
    drop_threshold: float,
) -> RouteTriggerSpec | None:
    """判断候选可执行率是否应该触发 external planner fallback。"""

    if not enable_dual_route or use_external or not fallback_available:
        return None
    drop = previous_rate - executable_rate if previous_rate is not None else 0.0
    if executable_rate < rate_threshold:
        return RouteTriggerSpec(
            reason="candidate_executable_rate_low",
            threshold=f"candidate_executable_rate={executable_rate:.3f}<{rate_threshold:.3f}",
        )
    if drop >= drop_threshold:
        return RouteTriggerSpec(
            reason="candidate_executable_rate_drop",
            threshold=f"candidate_executable_drop={drop:.3f}>={drop_threshold:.3f}",
        )
    return None
