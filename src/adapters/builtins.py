from __future__ import annotations

from src.adapters.dummy_adapter import DummyToolAdapter
from src.adapters.registry import get_adapter, register_adapter

__all__ = ["ensure_builtin_adapters"]


_BUILTIN_TOOL_IDS = (
    "dummy_tool",
    "dummy_tool_alt",
    "dummy_tool_safe",
)


def ensure_builtin_adapters() -> None:
    """注册内置 Dummy 适配器，供本地最小闭环使用"""
    for tool_id in _BUILTIN_TOOL_IDS:
        try:
            get_adapter(tool_id)
        except KeyError:
            register_adapter(DummyToolAdapter(tool_id))
