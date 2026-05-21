from __future__ import annotations

from collections.abc import Callable, Mapping

from src.models.failure_codes import normalize_failure_code_value

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
type ObservabilityField = JsonObject | str | None
type ObservabilityFields = dict[str, ObservabilityField]

_PENDING_ACTION_NAME_MAP = {
    "plan_confirm": "plan",
    "patch_confirm": "patch",
    "replan_confirm": "replan",
}

_WAITING_STATUS_ACTION_NAME_MAP = {
    "WAITING_PLAN_CONFIRM": "plan",
    "WAITING_PATCH_CONFIRM": "patch",
    "WAITING_REPLAN_CONFIRM": "replan",
    "WAITING_PATCH": "patch",
    "WAITING_REPLAN": "replan",
}

_PATCH_EVENT_TYPES = {"PARAM_TWEAK", "REPLACE_TOOL", "STRUCTURE_PATCH"}


class FieldExtractionContext:
    """字段抽取上下文，集中缓存 data 下常用嵌套对象。"""

    payload: JsonObject
    data: JsonObject
    recovery: JsonObject
    patch: JsonObject
    fallback: JsonObject
    waiting_runtime_summary: JsonObject

    def __init__(self, *, payload: JsonObject, data: JsonObject) -> None:
        self.payload = payload
        self.data = data
        self.recovery = _mapping_field(data, "recovery")
        self.patch = _mapping_field(data, "patch")
        self.fallback = _mapping_field(data, "fallback")
        self.waiting_runtime_summary = _mapping_field(data, "waiting_runtime_summary")


type FieldExtractor = Callable[[FieldExtractionContext], ObservabilityField]


def extract_observability_fields(
    *,
    payload: JsonObject,
    data: JsonObject,
) -> ObservabilityFields:
    """按注册表抽取时间线观测字段，保持字段名和优先级稳定。"""

    context = FieldExtractionContext(payload=payload, data=data)
    # 注册表的顺序就是审计字段的阅读顺序；每个 extractor 只负责一个字段。
    return {
        field_name: extractor(context)
        for field_name, extractor in FIELD_EXTRACTORS.items()
    }


def _extract_tool_id(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "tool_id"),
        _string_field(context.payload, "tool"),
        _string_field(context.data, "tool_id"),
        _string_field(context.data, "tool"),
        _string_field(context.patch, "to_tool"),
        _string_field(context.recovery, "to_tool"),
        _string_field(context.fallback, "to_tool_id"),
        _string_field(context.patch, "from_tool"),
        _string_field(context.recovery, "from_tool"),
        _string_field(context.fallback, "from_tool_id"),
    )


def _extract_capability_id(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "capability_id"),
        _string_field(context.data, "capability_id"),
        _string_field(context.data, "capability"),
        _string_field(context.patch, "capability_id"),
        _string_field(context.recovery, "capability_id"),
    )


def _extract_io_type(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "io_type"),
        _string_field(context.data, "io_type"),
        _string_field(context.patch, "io_type"),
        _string_field(context.recovery, "io_type"),
    )


def _extract_adapter_mode(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "adapter_mode"),
        _string_field(context.data, "adapter_mode"),
        _string_field(context.patch, "adapter_mode"),
        _string_field(context.recovery, "adapter_mode"),
    )


def _extract_adapter_id(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "adapter_id"),
        _string_field(context.data, "adapter_id"),
        _string_field(context.patch, "adapter_id"),
        _string_field(context.recovery, "adapter_id"),
        _string_field(context.fallback, "to_adapter_id"),
    )


def _extract_execution_mode(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "execution_mode"),
        _string_field(context.data, "execution_mode"),
        _string_field(context.patch, "execution_mode"),
        _string_field(context.recovery, "execution_mode"),
        _string_field(context.fallback, "to_execution_mode"),
    )


def _extract_provider(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "provider"),
        _string_field(context.data, "provider"),
        _string_field(context.patch, "provider"),
        _string_field(context.recovery, "provider"),
    )


def _extract_endpoint_type(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "endpoint_type"),
        _string_field(context.data, "endpoint_type"),
        _string_field(context.patch, "endpoint_type"),
        _string_field(context.recovery, "endpoint_type"),
    )


def _extract_remote_job_id(context: FieldExtractionContext) -> str | None:
    remote_job_id = _first_text(
        _string_field(context.payload, "remote_job_id"),
        _string_field(context.data, "remote_job_id"),
        _string_field(context.data, "job_id"),
        _string_field(context.patch, "remote_job_id"),
        _string_field(context.recovery, "remote_job_id"),
    )
    if remote_job_id is not None:
        return remote_job_id
    error_details = _mapping_field(context.payload, "error_details")
    return _string_field(error_details, "remote_job_id")


def _extract_from_tool(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "from_tool"),
        _string_field(context.data, "from_tool"),
        _string_field(context.recovery, "from_tool"),
        _string_field(context.patch, "from_tool"),
        _string_field(context.fallback, "from_tool_id"),
    )


def _extract_to_tool(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "to_tool"),
        _string_field(context.data, "to_tool"),
        _string_field(context.recovery, "to_tool"),
        _string_field(context.patch, "to_tool"),
        _string_field(context.fallback, "to_tool_id"),
    )


def _extract_failure_type(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "failure_type"),
        _string_field(context.data, "failure_type"),
        _string_field(context.recovery, "failure_type"),
    )


def _extract_failure_code(context: FieldExtractionContext) -> str | None:
    failure_code = _first_text(
        _string_field(context.payload, "failure_code"),
        _string_field(context.data, "failure_code"),
        _string_field(context.recovery, "failure_code"),
    )
    if failure_code is not None:
        return failure_code
    error_details = _mapping_field(context.payload, "error_details")
    failure_code = normalize_failure_code_value(error_details.get("failure_code"))
    if failure_code is not None:
        return failure_code
    s6 = _mapping_field(context.data, "s6")
    return normalize_failure_code_value(s6.get("trigger_failure_code"))


def _extract_recovery_hint(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "recovery_hint"),
        _string_field(context.data, "recovery_hint"),
        _string_field(context.data, "suggested_recovery"),
        _string_field(context.recovery, "recovery_hint"),
        _string_field(context.recovery, "suggested_recovery"),
    )


def _extract_candidate_id(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "selected_candidate_id"),
        _string_field(context.data, "selected_candidate_id"),
        _string_field(context.data, "candidate_id"),
        _string_field(context.recovery, "candidate_id"),
    )


def _extract_decision_source(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.payload, "decided_by"),
        _string_field(context.data, "decided_by"),
        _string_field(context.data, "decision_source"),
        _string_field(context.payload, "actor_id"),
        _string_field(context.payload, "actor_type"),
    )


def _extract_action_name(context: FieldExtractionContext) -> str | None:
    action_name = _first_text(
        _string_field(context.payload, "action_name"),
        _string_field(context.data, "action_name"),
    )
    if action_name:
        return action_name

    s6 = _mapping_field(context.data, "s6")
    action_name = _string_field(s6, "action")
    if action_name:
        return action_name

    action_type = _first_text(
        _string_field(context.payload, "action_type"),
        _string_field(context.data, "action_type"),
    )
    if action_type:
        return _PENDING_ACTION_NAME_MAP.get(action_type, action_type)

    event_type = _canonical_event_type(context.payload)
    if event_type in _PATCH_EVENT_TYPES:
        return "patch"
    if event_type == "RECOVERY_ESCALATED":
        return "replan"

    for status_key in ("to_status", "new_status", "from_status", "prev_status"):
        status_value = _string_field(context.payload, status_key)
        if status_value and status_value in _WAITING_STATUS_ACTION_NAME_MAP:
            return _WAITING_STATUS_ACTION_NAME_MAP[status_value]

    return _string_field(context.recovery, "action_name")


def _extract_recovery_layer(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.recovery, "layer"),
        _string_field(context.recovery, "recovery_layer"),
        _string_field(context.patch, "layer"),
        _string_field(context.patch, "recovery_layer"),
    )


def _extract_recovery_reason(context: FieldExtractionContext) -> str | None:
    return _first_text(
        _string_field(context.recovery, "reason"),
        _string_field(context.recovery, "upgrade_reason"),
        _string_field(context.fallback, "reason"),
        _string_field(context.data, "reason"),
    )


def _extract_runtime_state_summary(context: FieldExtractionContext) -> JsonObject | None:
    return _first_mapping(
        context.data.get("runtime_state_summary"),
        context.waiting_runtime_summary.get("runtime_state_summary"),
        context.recovery.get("runtime_state_summary"),
    )


def _extract_action_score(context: FieldExtractionContext) -> JsonObject | None:
    return _first_mapping(
        context.data.get("action_score"),
        context.waiting_runtime_summary.get("action_score"),
        context.recovery.get("action_score"),
    )


def _extract_shadow_score(context: FieldExtractionContext) -> JsonObject | None:
    return _first_mapping(
        context.data.get("shadow_score"),
        context.waiting_runtime_summary.get("shadow_score"),
        context.recovery.get("shadow_score"),
    )


def _extract_waiting_runtime_summary(
    context: FieldExtractionContext,
) -> JsonObject | None:
    return context.waiting_runtime_summary or None


def _extract_evidence_source(context: FieldExtractionContext) -> JsonObject | None:
    return _first_mapping(
        context.data.get("evidence_source"),
        context.data.get("default_recommendation_reason"),
        context.waiting_runtime_summary.get("default_recommendation_reason"),
        context.recovery.get("evidence_source"),
        context.recovery.get("default_recommendation_reason"),
    )


FIELD_EXTRACTORS: Mapping[str, FieldExtractor] = {
    "tool_id": _extract_tool_id,
    "adapter_id": _extract_adapter_id,
    "execution_mode": _extract_execution_mode,
    "capability_id": _extract_capability_id,
    "io_type": _extract_io_type,
    "adapter_mode": _extract_adapter_mode,
    "provider": _extract_provider,
    "endpoint_type": _extract_endpoint_type,
    "remote_job_id": _extract_remote_job_id,
    "from_tool": _extract_from_tool,
    "to_tool": _extract_to_tool,
    "failure_type": _extract_failure_type,
    "failure_code": _extract_failure_code,
    "recovery_hint": _extract_recovery_hint,
    "candidate_id": _extract_candidate_id,
    "decision_source": _extract_decision_source,
    "action_name": _extract_action_name,
    "action_score": _extract_action_score,
    "shadow_score": _extract_shadow_score,
    "runtime_state_summary": _extract_runtime_state_summary,
    "waiting_runtime_summary": _extract_waiting_runtime_summary,
    "evidence_source": _extract_evidence_source,
    "recovery_layer": _extract_recovery_layer,
    "recovery_reason": _extract_recovery_reason,
}


def _canonical_event_type(payload: JsonObject) -> str | None:
    event_type = _string_field(payload, "event_type")
    if event_type:
        return event_type
    return _string_field(payload, "event")


def _first_text(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _first_mapping(*values: JsonValue) -> JsonObject | None:
    for value in values:
        if isinstance(value, dict):
            return dict(value)
    return None


def _mapping_field(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _string_field(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
