from __future__ import annotations

from typing import Any

from src.models.contracts import PendingActionCandidate, PlanPatch, PlanStep, StepResult


def extract_recovery_metadata(
    *,
    plan_patch: PlanPatch | None,
    selected_candidate: PendingActionCandidate | None,
    source_step: PlanStep,
    patched_step: StepResult | None = None,
) -> dict[str, Any]:
    metadata = _patch_metadata(plan_patch)
    candidate_meta = _candidate_metadata(selected_candidate)
    payload = _base_recovery_payload(
        metadata=metadata,
        candidate_meta=candidate_meta,
        selected_candidate=selected_candidate,
        source_step=source_step,
        patched_step=patched_step,
    )
    _copy_candidate_recovery_fields(payload, candidate_meta)
    strategy = metadata.get("strategy")
    if isinstance(strategy, str):
        payload["strategy"] = strategy
    return payload


def extract_capability_from_step(step: PlanStep) -> str:
    metadata = step.metadata if isinstance(step.metadata, dict) else {}
    raw = metadata.get("capability")
    if isinstance(raw, str) and raw:
        return raw
    values = metadata.get("capabilities")
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and item:
                return item
    return "unknown"


def _patch_metadata(plan_patch: PlanPatch | None) -> dict[str, Any]:
    if plan_patch is not None and isinstance(plan_patch.metadata, dict):
        return plan_patch.metadata
    return {}


def _candidate_metadata(
    selected_candidate: PendingActionCandidate | None,
) -> dict[str, Any]:
    if selected_candidate is not None and isinstance(selected_candidate.metadata, dict):
        return selected_candidate.metadata
    return {}


def _base_recovery_payload(
    *,
    metadata: dict[str, Any],
    candidate_meta: dict[str, Any],
    selected_candidate: PendingActionCandidate | None,
    source_step: PlanStep,
    patched_step: StepResult | None,
) -> dict[str, Any]:
    return {
        "recovery_layer": _recovery_layer(metadata, candidate_meta),
        "capability_id": _capability_id(metadata, selected_candidate, source_step),
        "from_tool": _from_tool(metadata, source_step),
        "to_tool": _to_tool(metadata, selected_candidate, source_step, patched_step),
        "reason": _reason(metadata, candidate_meta),
        "candidate_id": selected_candidate.candidate_id if selected_candidate else None,
        "io_type": selected_candidate.io_type if selected_candidate else None,
        "adapter_mode": selected_candidate.adapter_mode if selected_candidate else None,
        "adapter_id": selected_candidate.adapter_id if selected_candidate else None,
        "execution_mode": selected_candidate.execution_mode if selected_candidate else None,
        "provider": selected_candidate.provider if selected_candidate else None,
        "endpoint_type": selected_candidate.endpoint_type if selected_candidate else None,
        "remote_job_id": selected_candidate.remote_job_id if selected_candidate else None,
    }


def _capability_id(
    metadata: dict[str, Any],
    selected_candidate: PendingActionCandidate | None,
    source_step: PlanStep,
) -> str | None:
    capability_id = metadata.get("capability_id")
    if isinstance(capability_id, str) and capability_id:
        return capability_id
    if selected_candidate is not None and selected_candidate.capability_id:
        return selected_candidate.capability_id
    return extract_capability_from_step(source_step)


def _from_tool(metadata: dict[str, Any], source_step: PlanStep) -> str:
    value = metadata.get("from_tool")
    if isinstance(value, str) and value:
        return value
    return source_step.tool


def _to_tool(
    metadata: dict[str, Any],
    selected_candidate: PendingActionCandidate | None,
    source_step: PlanStep,
    patched_step: StepResult | None,
) -> str:
    value = metadata.get("to_tool")
    if isinstance(value, str) and value:
        return value
    if patched_step is not None:
        return patched_step.tool
    if selected_candidate is not None and selected_candidate.tool_id:
        return selected_candidate.tool_id
    return source_step.tool


def _recovery_layer(
    metadata: dict[str, Any],
    candidate_meta: dict[str, Any],
) -> str:
    value = metadata.get("recovery_layer")
    if isinstance(value, str) and value:
        return value
    return str(candidate_meta.get("recovery_layer") or "tool_level")


def _reason(metadata: dict[str, Any], candidate_meta: dict[str, Any]) -> str:
    value = metadata.get("reason")
    if isinstance(value, str) and value:
        return value
    return str(
        candidate_meta.get("reason")
        or candidate_meta.get("recovery_reason")
        or "patch_required"
    )


def _copy_candidate_recovery_fields(
    payload: dict[str, Any],
    candidate_meta: dict[str, Any],
) -> None:
    for key in (
        "runtime_state_summary",
        "action_score",
        "shadow_score",
        "default_recommendation_reason",
    ):
        value = candidate_meta.get(key)
        if value is not None:
            payload[key] = value
