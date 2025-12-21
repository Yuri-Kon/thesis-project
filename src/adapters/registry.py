from __future__ import annotations

from typing import Dict

from src.adapters.base_tool_adapter import BaseToolAdapter

__all__ = [
    "AdapterRegistry",
    "ADAPTER_REGISTRY",
    "register_adapter",
    "get_adapter",
]


class AdapterRegistry:
    """集中管理 ToolAdapter 的注册与获取"""

    def __init__(self) -> None:
        self._by_tool_id: Dict[str, BaseToolAdapter] = {}
        self._by_adapter_id: Dict[str, BaseToolAdapter] = {}

    def register(self, adapter: BaseToolAdapter, *, adapter_id: str | None = None) -> None:
        tool_id = _require_id(getattr(adapter, "tool_id", None), "tool_id")
        resolved_adapter_id = adapter_id or getattr(adapter, "adapter_id", None) or tool_id
        resolved_adapter_id = _require_id(resolved_adapter_id, "adapter_id")

        self._ensure_available(tool_id, adapter, key_type="tool_id")
        self._ensure_available(resolved_adapter_id, adapter, key_type="adapter_id")

        self._by_tool_id[tool_id] = adapter
        self._by_adapter_id[resolved_adapter_id] = adapter

    def get(self, key: str) -> BaseToolAdapter:
        if key in self._by_tool_id:
            return self._by_tool_id[key]
        if key in self._by_adapter_id:
            return self._by_adapter_id[key]

        tool_ids = sorted(self._by_tool_id.keys())
        adapter_ids = sorted(self._by_adapter_id.keys())
        raise KeyError(
            "Adapter not found for key "
            f"'{key}'. Known tool_id={tool_ids} adapter_id={adapter_ids}"
        )

    def _ensure_available(self, key: str, adapter: BaseToolAdapter, *, key_type: str) -> None:
        mapping = self._by_tool_id if key_type == "tool_id" else self._by_adapter_id
        if key in mapping:
            existing = mapping[key]
            raise ValueError(
                f"Duplicate adapter registration for {key_type} "
                f"'{key}'. Existing={existing.__class__.__name__}"
            )


def _require_id(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


ADAPTER_REGISTRY = AdapterRegistry()


def register_adapter(adapter: BaseToolAdapter, *, adapter_id: str | None = None) -> None:
    ADAPTER_REGISTRY.register(adapter, adapter_id=adapter_id)


def get_adapter(key: str) -> BaseToolAdapter:
    return ADAPTER_REGISTRY.get(key)
