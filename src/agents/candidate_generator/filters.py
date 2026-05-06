from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import cast

from src.agents.candidate_generator.models import (
    AdapterMode,
    Level,
    Metadata,
    ToolSpecLike,
)
from src.models.contracts import PendingActionCandidate, Plan, PlanPatch


def object_mapping(value: object) -> Metadata:
    """将动态 mapping 收敛为字符串键元数据。"""
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(key): item for key, item in mapping.items()}


def normalize_level(value: object) -> Level | None:
    """归一化候选风险/成本等级。"""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"low", "medium", "high"}:
        return cast(Level, normalized)
    return None


def normalize_adapter_mode(value: object) -> AdapterMode:
    """归一化候选 adapter_mode。"""
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().lower()
    if normalized in {"local", "remote", "mock", "hybrid", "unknown"}:
        return cast(AdapterMode, normalized)
    return "unknown"


def candidate_difference_explanation(
    candidates: Sequence[PendingActionCandidate],
) -> str:
    if not candidates:
        return ""
    tools = sorted({candidate.tool_id or "unknown" for candidate in candidates})
    capabilities = sorted({candidate.capability_id or "unknown" for candidate in candidates})
    risks = sorted({candidate.risk_level or "unknown" for candidate in candidates})
    costs = sorted({candidate.cost_estimate or "unknown" for candidate in candidates})
    parts = [
        f"tools={','.join(tools)}",
        f"capabilities={','.join(capabilities)}",
        f"risk={','.join(risks)}",
        f"cost={','.join(costs)}",
    ]
    return "; ".join(parts)


def payload_tool_ids(payload: Plan | PlanPatch) -> list[str]:
    if isinstance(payload, Plan):
        return [step.tool for step in payload.steps]
    return [operation.step.tool for operation in payload.operations]


def payload_io_closed(
    payload: Plan | PlanPatch,
    registry_map: Mapping[str, ToolSpecLike],
    completed_step_results: Sequence[object],
    constraints: Mapping[str, object],
) -> bool:
    available = set(constraints.keys())
    available.add("goal")
    available.update(object_mapping(constraints.get("inputs")).keys())
    for result in completed_step_results:
        outputs = getattr(result, "outputs", None)
        available.update(object_mapping(outputs).keys())

    steps = (
        payload.steps
        if isinstance(payload, Plan)
        else [operation.step for operation in payload.operations]
    )
    for step in steps:
        spec = registry_map.get(step.tool)
        required_inputs = set(spec.inputs if spec is not None else ())
        step_inputs = object_mapping(cast(object, step.inputs))
        for required in required_inputs:
            if required in step_inputs:
                continue
            if required in available:
                continue
            return False
        for value in step_inputs.values():
            if isinstance(value, str) and "." in value:
                _head, field = value.split(".", 1)
                if field not in available:
                    return False
        if spec is not None:
            available.update(spec.outputs)
    return True


def string_set(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        items = cast(Iterable[object], value)
        return {str(item) for item in items if str(item)}
    return set()


def parse_safety_level(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized.startswith("S") and normalized[1:].isdigit():
            return int(normalized[1:])
        if normalized.isdigit():
            return int(normalized)
    return None


def safe_float(value: object) -> float | None:
    if not isinstance(value, (str, int, float)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def cost_level_exceeds(candidate_level: str | None, max_level: str | None) -> bool:
    if max_level is None:
        return False
    rank = {"low": 0, "medium": 1, "high": 2}
    normalized_candidate = str(candidate_level or "medium").strip().lower()
    normalized_max = str(max_level).strip().lower()
    if normalized_max not in rank:
        return False
    return rank.get(normalized_candidate, 1) > rank[normalized_max]
