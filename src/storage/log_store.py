from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, TypeGuard, cast

from src.storage._field_extractors import extract_observability_fields

if TYPE_CHECKING:
    from src.models.event_log import EventLog

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
type TimelineEvent = dict[str, JsonValue]
type ObservabilityFields = dict[str, JsonObject | str | None]

# 事件日志默认目录，按 task_id 写入 jsonl 文件


def _resolve_default_log_dir() -> Path:
    explicit = os.getenv("PROTEIN_LOG_DIR")
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("PROTEIN_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "logs"
    return Path("data/logs")


DEFAULT_LOG_DIR = _resolve_default_log_dir()

_LEGACY_EVENT_TYPE_MAP = {
    "TASK_STATUS_CHANGED": "STATE_TRANSITION",
    "PENDING_ACTION_CREATED": "PENDING_ACTION_CREATED",
    "DECISION_APPLIED": "DECISION_APPLIED",
    "STEP_FINISHED": "STEP_FINISHED",
    "STEP_FAILED": "STEP_FAILED",
}


def append_event(
    task_id: str,
    event: Mapping[str, JsonValue],
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> None:
    """追加一条事件日志到 jsonl 文件中"""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{task_id}.jsonl"
    payload = json.dumps(dict(event), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as handle:
        _ = handle.write(payload + "\n")


def write_event_log(
    event_log: EventLog,
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> None:
    """将 EventLog 对象持久化到 jsonl 文件中

    Args:
        event_log: EventLog 实例
        log_dir: 日志目录路径
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{event_log.task_id}.jsonl"
    # 使用 model_dump() 转换为字典，保留所有字段
    payload = json.dumps(event_log.model_dump(mode="json"), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as handle:
        _ = handle.write(payload + "\n")


def read_event_logs(
    task_id: str,
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
    strict: bool = False,
) -> list["EventLog"]:
    """读取指定任务的 EventLog 记录（过滤非结构化事件）"""
    path = log_dir / f"{task_id}.jsonl"
    if not path.exists():
        return []

    from src.models.event_log import EventLog

    events: list[EventLog] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                raw_payload = _load_json(line)
            except json.JSONDecodeError:
                if strict:
                    raise
                continue
            payload = _as_json_object(raw_payload)
            if payload is None:
                if strict:
                    raise ValueError("EventLog payload must be a JSON object")
                continue
            if "event_type" not in payload:
                continue
            try:
                events.append(EventLog.model_validate(payload))
            except Exception:
                if strict:
                    raise
                continue
    return events


def read_timeline_events(
    task_id: str,
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
    strict: bool = False,
) -> list[TimelineEvent]:
    """读取任务时间线事件（兼容 event_type / event 两种格式）。"""
    path = log_dir / f"{task_id}.jsonl"
    if not path.exists():
        return []

    events: list[TimelineEvent] = []
    with path.open("r", encoding="utf-8") as handle:
        for seq, line in enumerate(handle):
            line = line.strip()
            if not line:
                continue
            try:
                raw_payload = _load_json(line)
            except json.JSONDecodeError:
                if strict:
                    raise
                continue
            payload = _as_json_object(raw_payload)
            if payload is None:
                if strict:
                    raise ValueError("timeline payload must be a JSON object")
                continue
            normalized = _normalize_timeline_event(
                payload=payload,
                task_id=task_id,
                seq=seq,
            )
            if normalized is None:
                continue
            events.append(normalized)

    events.sort(key=_timeline_sort_key)
    return events


def _normalize_timeline_event(
    *,
    payload: JsonObject,
    task_id: str,
    seq: int,
) -> TimelineEvent | None:
    event_type = _canonical_event_type(payload)
    if event_type is None:
        return None

    timestamp = _extract_timestamp(payload)
    from_status = _string_field(payload, "from_status") or _string_field(
        payload, "prev_status"
    )
    to_status = _string_field(payload, "to_status") or _string_field(
        payload, "new_status"
    )
    data = _mapping_field(payload, "data")
    observability = _extract_observability_fields(payload=payload, data=data)

    return {
        "seq": seq,
        "task_id": _string_field(payload, "task_id") or task_id,
        "ts": timestamp,
        "event_type": event_type,
        "source_event": _string_field(payload, "event")
        or _string_field(payload, "event_type"),
        "pending_action_id": _string_field(payload, "pending_action_id"),
        "decision_id": _string_field(payload, "decision_id"),
        "step_id": _string_field(payload, "step_id"),
        "tool": _string_field(payload, "tool"),
        "tool_id": observability["tool_id"],
        "adapter_id": observability["adapter_id"],
        "execution_mode": observability["execution_mode"],
        "capability_id": observability["capability_id"],
        "io_type": observability["io_type"],
        "adapter_mode": observability["adapter_mode"],
        "provider": observability["provider"],
        "endpoint_type": observability["endpoint_type"],
        "remote_job_id": observability["remote_job_id"],
        "from_tool": observability["from_tool"],
        "to_tool": observability["to_tool"],
        "failure_type": observability["failure_type"],
        "failure_code": observability["failure_code"],
        "recovery_hint": observability["recovery_hint"],
        "candidate_id": observability["candidate_id"],
        "decision_source": observability["decision_source"],
        "action_name": observability["action_name"],
        "action_score": observability["action_score"],
        "shadow_score": observability["shadow_score"],
        "runtime_state_summary": observability["runtime_state_summary"],
        "waiting_runtime_summary": observability["waiting_runtime_summary"],
        "evidence_source": observability["evidence_source"],
        "recovery_layer": observability["recovery_layer"],
        "recovery_reason": observability["recovery_reason"],
        "status": _string_field(payload, "status"),
        "from_status": from_status,
        "to_status": to_status,
        "actor_type": _string_field(payload, "actor_type"),
        "summary": _build_event_summary(
            event_type=event_type,
            payload=payload,
            from_status=from_status,
            to_status=to_status,
        ),
        "data": data,
        "payload": payload,
    }


def _timeline_sort_key(event: TimelineEvent) -> tuple[int, datetime, int]:
    parsed_ts = _parse_timestamp(event.get("ts"))
    seq = event.get("seq")
    seq_value = seq if isinstance(seq, int) else 0
    if parsed_ts is None:
        return (1, datetime.max, seq_value)
    return (0, parsed_ts, seq_value)


def _parse_timestamp(value: JsonValue) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_timestamp(payload: JsonObject) -> str | None:
    ts = _string_field(payload, "ts")
    if ts:
        return ts
    timestamp = _string_field(payload, "timestamp")
    if timestamp:
        return timestamp
    return None


def _canonical_event_type(payload: JsonObject) -> str | None:
    event_type = _string_field(payload, "event_type")
    if event_type:
        return event_type

    legacy_event = _string_field(payload, "event")
    if not legacy_event:
        return None
    return _LEGACY_EVENT_TYPE_MAP.get(legacy_event, legacy_event)


def _string_field(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _build_event_summary(
    *,
    event_type: str,
    payload: JsonObject,
    from_status: str | None,
    to_status: str | None,
) -> str:
    if event_type == "STATE_TRANSITION":
        left = from_status or "UNKNOWN"
        right = to_status or "UNKNOWN"
        return f"{left} -> {right}"

    if event_type == "PENDING_ACTION_CREATED":
        action_type = _string_field(payload, "action_type") or "unknown_action"
        return f"PendingAction created ({action_type})"

    if event_type == "DECISION_APPLIED":
        choice = _string_field(payload, "choice")
        if choice is None:
            decision_data = _mapping_field(payload, "data")
            value = decision_data.get("choice")
            if isinstance(value, str):
                choice = value
        return f"Decision applied ({choice or 'unknown'})"

    if event_type == "WAITING_ENTER":
        return "Enter waiting state"
    if event_type == "WAITING_EXIT":
        return "Exit waiting state"

    if event_type == "STEP_FAILED":
        step_id = _string_field(payload, "step_id") or "unknown_step"
        return f"Step failed ({step_id})"

    if event_type == "STEP_FINISHED":
        step_id = _string_field(payload, "step_id") or "unknown_step"
        return f"Step finished ({step_id})"

    return event_type


def _extract_observability_fields(
    *,
    payload: JsonObject,
    data: JsonObject,
) -> ObservabilityFields:
    # 旧函数名保留为门面，便于调用侧稳定；字段优先级由注册表模块维护。
    return extract_observability_fields(payload=payload, data=data)


def _mapping_field(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _load_json(line: str) -> object:
    return cast(object, json.loads(line))


def _as_json_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    result: JsonObject = {}
    for key, item in cast(Mapping[object, object], value).items():
        if isinstance(key, str) and _is_json_value(item):
            result[key] = item
    return result


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
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
