from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from src.adapters.builtins import ensure_builtin_adapters
from src.adapters.registry import get_adapter
from src.kg.kg_client import load_tool_kg
from src.models.contracts import now_iso

__all__ = [
    "build_capability_readiness_matrix",
    "evaluate_tool_readiness",
]


def evaluate_tool_readiness(tool_id: str) -> Dict[str, Any]:
    """评估单个工具的可用性。"""
    try:
        adapter = get_adapter(tool_id)
    except KeyError:
        return {
            "tool_id": tool_id,
            "status": "unavailable",
            "reason": "adapter not registered",
        }

    try:
        health = adapter.healthcheck()
    except Exception as exc:  # pragma: no cover - 防御性分支
        return {
            "tool_id": tool_id,
            "status": "degraded",
            "reason": f"healthcheck failed: {exc}",
        }

    status = str(health.get("status") or "ready")
    if status not in {"ready", "degraded", "unavailable"}:
        status = "degraded"
    return {
        "tool_id": tool_id,
        "status": status,
        "reason": str(health.get("reason") or ""),
        "details": health,
    }


def build_capability_readiness_matrix() -> List[Dict[str, Any]]:
    """构建 capability 级 readiness 视图。"""
    ensure_builtin_adapters()
    kg = load_tool_kg()
    tools = kg.get("tools", [])
    capabilities = kg.get("capabilities", [])
    if not isinstance(tools, list) or not isinstance(capabilities, list):
        return []

    capability_tools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        for capability_id in tool.get("capabilities", []):
            if isinstance(capability_id, str):
                capability_tools[capability_id].append(tool)

    matrix: list[Dict[str, Any]] = []
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        capability_id = capability.get("capability_id")
        if not isinstance(capability_id, str):
            continue
        ranked_tools = sorted(
            capability_tools.get(capability_id, []),
            key=lambda item: (
                0 if _primary_capability(item) == capability_id else 1,
                _priority_rank(item.get("priority")),
                str(item.get("id") or ""),
            ),
        )
        tool_health = [
            evaluate_tool_readiness(str(tool.get("id")))
            for tool in ranked_tools
            if isinstance(tool.get("id"), str)
        ]

        primary_tool_id = next(
            (item["tool_id"] for item in tool_health),
            None,
        )
        fallback_tool_ids = [item["tool_id"] for item in tool_health[1:]]
        ready_tools = [item for item in tool_health if item["status"] == "ready"]

        status = "unavailable"
        reason = "no registered tool is ready"
        if tool_health:
            first = tool_health[0]
            if first["status"] == "ready":
                status = "ready"
                reason = first["reason"] or "primary tool is ready"
            elif ready_tools:
                status = "degraded"
                reason = "primary tool unavailable; fallback tool is ready"
            elif any(item["status"] == "degraded" for item in tool_health):
                status = "degraded"
                reason = "tool registered but health is degraded"

        matrix.append(
            {
                "capability_id": capability_id,
                "status": status,
                "primary_tool_id": primary_tool_id,
                "fallback_tool_ids": fallback_tool_ids,
                "reason": reason,
                "checked_at": now_iso(),
                "tools": tool_health,
            }
        )
    return matrix


def _priority_rank(value: Any) -> int:
    if not isinstance(value, str):
        return 9
    normalized = value.strip().upper()
    if normalized == "P0":
        return 0
    if normalized.startswith("P") and normalized[1:].isdigit():
        return int(normalized[1:])
    return 9


def _primary_capability(tool: dict[str, Any]) -> str | None:
    capabilities = tool.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return None
    first = capabilities[0]
    return first if isinstance(first, str) else None
