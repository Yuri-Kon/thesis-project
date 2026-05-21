from __future__ import annotations

def normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def event_matches_filters(
    event: dict[str, object],
    *,
    event_type: str | None,
    tool_id: str | None,
    capability_id: str | None,
    adapter_mode: str | None,
    execution_mode: str | None,
) -> bool:
    """按 API 查询参数过滤时间线事件，不改变事件字段语义。"""

    if event_type and event.get("event_type") != event_type:
        return False

    if tool_id:
        # 工具相关字段可能来自执行、fallback 或 recovery，UI 查询需要统一覆盖。
        related_tools = {
            normalize_text(event.get("tool")),
            normalize_text(event.get("tool_id")),
            normalize_text(event.get("from_tool")),
            normalize_text(event.get("to_tool")),
        }
        related_tools.discard(None)
        if tool_id not in related_tools:
            return False

    if capability_id and event.get("capability_id") != capability_id:
        return False

    if adapter_mode and event.get("adapter_mode") != adapter_mode:
        return False

    if execution_mode and event.get("execution_mode") != execution_mode:
        return False

    return True
