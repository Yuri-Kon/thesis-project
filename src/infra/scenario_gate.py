from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from src.infra.tool_readiness import batch_check_capability_hints
from src.models.contracts import now_iso
from src.models.task_intake import (
    CapabilityHint,
    ScenarioGateResult,
    ScenarioGatingStatus,
    JsonObject,
)


def evaluate_scenario_gate(
    *,
    support_level: str,
    capability_hints: Sequence[CapabilityHint],
    tools_allowed: Sequence[str] | None = None,
    tools_excluded: Sequence[str] | None = None,
) -> ScenarioGateResult:
    """评估 P1/P2 场景门控，不创建 TaskRecord 或决定 HTTP 状态码。"""

    readiness = batch_check_capability_hints(
        capability_hints,
        tools_allowed=tools_allowed,
        tools_excluded=tools_excluded,
    )
    checked_at = _checked_at(readiness)
    required_blocked = [
        _hint_key(hint)
        for hint in capability_hints
        if hint["required"] and _status_for_hint(hint, readiness) == "unavailable"
    ]
    required_degraded = [
        _hint_key(hint)
        for hint in capability_hints
        if hint["required"] and _status_for_hint(hint, readiness) == "degraded"
    ]
    optional_warnings = [
        _hint_key(hint)
        for hint in capability_hints
        if not hint["required"] and _status_for_hint(hint, readiness) != "ready"
    ]
    degraded_hints = list(dict.fromkeys([*required_degraded, *optional_warnings]))

    normalized_support = support_level.strip().upper()
    if normalized_support == "P2" and (required_blocked or required_degraded):
        status = ScenarioGatingStatus.REJECT
    elif normalized_support == "P1" and required_blocked:
        status = ScenarioGatingStatus.DRAFT_ONLY
    elif normalized_support == "P1" and (required_degraded or optional_warnings):
        status = ScenarioGatingStatus.DEGRADED
    else:
        status = ScenarioGatingStatus.ALLOW

    user_message, user_message_zh = _gate_messages(
        status=status,
        support_level=normalized_support,
        blocked_hints=required_blocked,
        degraded_hints=degraded_hints,
    )
    return {
        "status": status.value,
        "support_level": normalized_support,
        "blocked_hints": required_blocked,
        "degraded_hints": degraded_hints,
        "readiness": cast(JsonObject, readiness),
        "checked_at": checked_at,
        "user_message": user_message,
        "user_message_zh": user_message_zh,
    }


def scenario_gate_from_metadata(
    metadata: Mapping[str, object],
) -> ScenarioGateResult | None:
    """从任务 metadata 读取已持久化的 scenario_gate。"""

    raw_gate = metadata.get("scenario_gate")
    if not isinstance(raw_gate, dict):
        return None
    gate = cast(dict[str, object], raw_gate)
    status = gate.get("status")
    support_level = gate.get("support_level")
    if not isinstance(status, str) or not isinstance(support_level, str):
        return None
    blocked = gate.get("blocked_hints")
    degraded = gate.get("degraded_hints")
    readiness = gate.get("readiness")
    checked_at = gate.get("checked_at")
    user_message = gate.get("user_message")
    user_message_zh = gate.get("user_message_zh")
    return {
        "status": status,
        "support_level": support_level,
        "blocked_hints": _string_items(blocked),
        "degraded_hints": _string_items(degraded),
        "readiness": cast(JsonObject, readiness) if isinstance(readiness, dict) else {},
        "checked_at": checked_at if isinstance(checked_at, str) else now_iso(),
        "user_message": user_message if isinstance(user_message, str) else "",
        "user_message_zh": (
            user_message_zh if isinstance(user_message_zh, str) else ""
        ),
    }


def _status_for_hint(
    hint: CapabilityHint,
    readiness: Mapping[str, Mapping[str, object]],
) -> str:
    snapshot = readiness.get(_hint_key(hint), {})
    raw_status = snapshot.get("status")
    if raw_status in {"ready", "degraded", "unavailable"}:
        return str(raw_status)
    return "unavailable"


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, str)]


def _hint_key(hint: CapabilityHint) -> str:
    io_type = hint.get("io_type", "").strip()
    return f"{hint['name']}:{io_type}" if io_type else hint["name"]


def _checked_at(readiness: Mapping[str, Mapping[str, object]]) -> str:
    for snapshot in readiness.values():
        checked_at = snapshot.get("checked_at") or snapshot.get("last_checked_at")
        if isinstance(checked_at, str) and checked_at:
            return checked_at
    return now_iso()


def _gate_messages(
    *,
    status: ScenarioGatingStatus,
    support_level: str,
    blocked_hints: Sequence[str],
    degraded_hints: Sequence[str],
) -> tuple[str, str]:
    if status == ScenarioGatingStatus.REJECT:
        blocked = ", ".join(blocked_hints or degraded_hints)
        return (
            f"{support_level} scenario is unsupported because required capabilities are not ready: {blocked}.",
            f"{support_level} 场景暂不支持，必需能力未就绪：{blocked}。",
        )
    if status == ScenarioGatingStatus.DRAFT_ONLY:
        blocked = ", ".join(blocked_hints)
        return (
            f"{support_level} scenario can only be saved as draft because required capabilities are unavailable: {blocked}.",
            f"{support_level} 场景只能保存为草稿，必需能力不可用：{blocked}。",
        )
    if status == ScenarioGatingStatus.DEGRADED:
        degraded = ", ".join(degraded_hints)
        return (
            f"{support_level} scenario has degraded capability readiness: {degraded}.",
            f"{support_level} 场景存在降级能力：{degraded}。",
        )
    return (
        f"{support_level or 'P0'} scenario capability readiness allows task creation.",
        f"{support_level or 'P0'} 场景能力就绪，可以创建任务。",
    )
