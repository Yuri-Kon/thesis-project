from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, Field

from src.api.event_filters import normalize_text
from src.infra.tool_readiness import build_tool_readiness_snapshot
from src.models.contracts import PendingActionCandidate, TOOL_READINESS_METADATA_KEY

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
type MetadataMap = Mapping[str, object]


class ReadinessDisplay(BaseModel):
    available: bool
    availability_hint: str
    readiness_status: str | None = None
    degraded_reasons: list[str] = Field(default_factory=list)
    suggested_recovery: str | None = None
    readiness_snapshot: JsonObject = Field(default_factory=dict)


class PendingActionToolDisplay(BaseModel):
    tool_id: str | None = None
    adapter_id: str | None = None
    capability_id: str | None = None
    io_type: str | None = None
    adapter_mode: str | None = None
    execution_mode: str | None = None
    provider: str | None = None
    endpoint_type: str | None = None
    remote_job_id: str | None = None
    failure_code: str | None = None
    recovery_hint: str | None = None
    source: str = Field(..., description="工具来源(local/remote/mock/hybrid/unknown)")
    available: bool = Field(..., description="工具信息是否可用于决策展示")
    can_fallback: bool = Field(..., description="是否可回退到备选工具")
    availability_hint: str = Field(..., description="工具可用性提示")
    readiness_status: str | None = None
    degraded_reasons: list[str] = Field(default_factory=list)
    suggested_recovery: str | None = None
    readiness_snapshot: JsonObject = Field(default_factory=dict)


def build_tool_display(
    candidate: PendingActionCandidate,
) -> PendingActionToolDisplay:
    """构造 PendingAction 工具展示 DTO，不改变候选项原始契约。"""

    metadata = candidate.metadata
    tool_id = candidate.tool_id or normalize_text(metadata.get("tool_id"))
    capability_id = candidate.capability_id or normalize_text(
        metadata.get("capability_id")
    )
    io_type = candidate.io_type or normalize_text(metadata.get("io_type"))
    adapter_mode = candidate.adapter_mode or normalize_text(metadata.get("adapter_mode"))
    adapter_id = candidate.adapter_id or normalize_text(metadata.get("adapter_id"))
    execution_mode = candidate.execution_mode or normalize_text(
        metadata.get("execution_mode")
    )
    provider = candidate.provider or normalize_text(metadata.get("provider"))
    endpoint_type = candidate.endpoint_type or normalize_text(
        metadata.get("endpoint_type")
    )
    remote_job_id = candidate.remote_job_id or normalize_text(
        metadata.get("remote_job_id")
    )
    failure_code = normalize_text(metadata.get("failure_code"))
    recovery_hint = normalize_text(metadata.get("recovery_hint"))

    source = (
        adapter_mode
        if adapter_mode in {"local", "remote", "mock", "hybrid"}
        else "unknown"
    )

    missing = _missing_required_tool_fields(
        tool_id=tool_id,
        capability_id=capability_id,
        io_type=io_type,
        adapter_mode=adapter_mode,
    )
    can_fallback = _candidate_can_fallback(candidate, metadata=metadata)
    available = source != "unknown" and not missing
    availability_hint = _build_availability_hint(
        missing=missing,
        execution_mode=execution_mode,
        source=source,
        can_fallback=can_fallback,
    )

    readiness = _resolve_readiness_display(
        tool_id=tool_id,
        metadata=metadata,
        available=available,
        availability_hint=availability_hint,
    )

    return PendingActionToolDisplay(
        tool_id=tool_id,
        adapter_id=adapter_id,
        capability_id=capability_id,
        io_type=io_type,
        adapter_mode=adapter_mode,
        execution_mode=execution_mode,
        provider=provider,
        endpoint_type=endpoint_type,
        remote_job_id=remote_job_id,
        failure_code=failure_code,
        recovery_hint=recovery_hint,
        source=source,
        available=readiness.available,
        can_fallback=can_fallback,
        availability_hint=readiness.availability_hint,
        readiness_status=readiness.readiness_status,
        degraded_reasons=readiness.degraded_reasons,
        suggested_recovery=readiness.suggested_recovery,
        readiness_snapshot=readiness.readiness_snapshot,
    )


def _missing_required_tool_fields(
    *,
    tool_id: str | None,
    capability_id: str | None,
    io_type: str | None,
    adapter_mode: str | None,
) -> list[str]:
    missing: list[str] = []
    if tool_id is None:
        missing.append("tool_id")
    if capability_id is None:
        missing.append("capability_id")
    if io_type is None:
        missing.append("io_type")
    if adapter_mode is None:
        missing.append("adapter_mode")
    return missing


def _candidate_can_fallback(
    candidate: PendingActionCandidate,
    *,
    metadata: MetadataMap,
) -> bool:
    # fallback 可能来自显式 metadata，也可能来自打分中的 fallback_depth。
    can_fallback = any(
        metadata.get(key)
        for key in (
            "fallback_tool",
            "fallback_tool_id",
            "fallback_from",
            "fallback_candidates",
            "fallback_options",
        )
    )
    fallback_depth = candidate.score_breakdown.get("fallback_depth")
    return can_fallback or (
        isinstance(fallback_depth, (int, float)) and fallback_depth > 0
    )


def _build_availability_hint(
    *,
    missing: list[str],
    execution_mode: str | None,
    source: str,
    can_fallback: bool,
) -> str:
    if missing:
        availability_hint = (
            f"Tool metadata missing ({', '.join(missing)}); use degraded display."
        )
    elif execution_mode == "openfold3_rest":
        availability_hint = (
            "OpenFold3 REST execution mode configured; availability depends on remote service health."
        )
    elif source == "remote":
        availability_hint = (
            "Remote adapter configured; availability depends on remote service health."
        )
    elif source == "local":
        availability_hint = "Local adapter configured."
    elif source == "mock":
        availability_hint = "Mock adapter configured for demo."
    elif source == "hybrid":
        availability_hint = "Hybrid adapter configured."
    else:
        availability_hint = "Tool source unknown; use degraded display."

    if can_fallback:
        return f"{availability_hint} Fallback path is available."
    return availability_hint


def _resolve_readiness_display(
    *,
    tool_id: str | None,
    metadata: MetadataMap,
    available: bool,
    availability_hint: str,
) -> ReadinessDisplay:
    readiness_snapshot: JsonObject = {}
    readiness_status: str | None = None
    degraded_reasons: list[str] = []
    suggested_recovery: str | None = None
    resolved_available = available
    resolved_hint = availability_hint

    if tool_id:
        raw_snapshot = metadata.get(TOOL_READINESS_METADATA_KEY)
        snapshot_mapping = (
            cast(Mapping[object, object], raw_snapshot)
            if isinstance(raw_snapshot, dict)
            else None
        )
        if (
            snapshot_mapping is not None
            and snapshot_mapping.get("tool_id") == tool_id
        ):
            readiness_snapshot = _json_object_from_raw_mapping(snapshot_mapping)
        else:
            readiness_snapshot = _json_object_from_mapping(
                build_tool_readiness_snapshot(tool_id)
            )
        readiness_status = normalize_text(readiness_snapshot.get("status"))
        reason = normalize_text(readiness_snapshot.get("reason"))
        if readiness_status and readiness_status != "ready" and reason:
            degraded_reasons.append(reason)
        suggested_recovery = normalize_text(readiness_snapshot.get("suggested_recovery"))
        if readiness_status:
            resolved_available = resolved_available and readiness_status == "ready"
            if readiness_status != "ready" and reason:
                resolved_hint = f"{resolved_hint} Readiness: {reason}"

    return ReadinessDisplay(
        available=resolved_available,
        availability_hint=resolved_hint,
        readiness_status=readiness_status,
        degraded_reasons=degraded_reasons,
        suggested_recovery=suggested_recovery,
        readiness_snapshot=readiness_snapshot,
    )


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(Sequence[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False


def _json_object_from_mapping(value: Mapping[str, object]) -> JsonObject:
    result: JsonObject = {}
    for key, item in value.items():
        if _is_json_value(item):
            result[key] = cast(JsonValue, item)
    return result


def _json_object_from_raw_mapping(value: Mapping[object, object]) -> JsonObject:
    result: JsonObject = {}
    for key, item in value.items():
        if isinstance(key, str) and _is_json_value(item):
            result[key] = cast(JsonValue, item)
    return result
