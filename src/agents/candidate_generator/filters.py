from __future__ import annotations

from typing import Any, Sequence

from src.models.contracts import PendingActionCandidate, Plan, PlanPatch


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
    return [
        operation.step.tool
        for operation in payload.operations
        if operation.step is not None
    ]


def payload_io_closed(
    payload: Plan | PlanPatch,
    registry_map: dict[str, Any],
    completed_step_results: Sequence[Any],
    constraints: dict[str, Any],
) -> bool:
    available = set(constraints.keys())
    available.add("goal")
    inputs = constraints.get("inputs")
    if isinstance(inputs, dict):
        available.update(inputs.keys())
    for result in completed_step_results:
        outputs = getattr(result, "outputs", None)
        if isinstance(outputs, dict):
            available.update(outputs.keys())

    steps = (
        payload.steps
        if isinstance(payload, Plan)
        else [
            operation.step
            for operation in payload.operations
            if operation.step is not None
        ]
    )
    for step in steps:
        spec = registry_map.get(step.tool)
        required_inputs = set(getattr(spec, "inputs", ()) or ())
        step_inputs = step.inputs if isinstance(step.inputs, dict) else {}
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
        outputs = getattr(spec, "outputs", ()) if spec is not None else ()
        available.update(outputs)
    return True


def string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if str(item)}
    return set()


def parse_safety_level(value: Any) -> int | None:
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


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
