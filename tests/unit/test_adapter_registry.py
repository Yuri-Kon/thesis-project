from __future__ import annotations

from typing import Any, Dict, Tuple

import pytest

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.registry import (
    ADAPTER_REGISTRY,
    AdapterRegistry,
    get_adapter,
    register_adapter,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext


class DummyAdapter(BaseToolAdapter):
    tool_id = "dummy_tool"
    adapter_id = "dummy_adapter"

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return dict(step.inputs)

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return {"ok": True}, {}


class DummyAdapterSameTool(BaseToolAdapter):
    tool_id = "dummy_tool"
    adapter_id = "dummy_adapter_v2"

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return dict(step.inputs)

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return {"ok": True}, {}


class DummyAdapterSameAdapter(BaseToolAdapter):
    tool_id = "dummy_tool_alt"
    adapter_id = "dummy_adapter"

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return dict(step.inputs)

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return {"ok": True}, {}


@pytest.fixture(autouse=True)
def _clear_global_registry():
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
    yield
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()


def test_registry_get_by_tool_and_adapter_id():
    registry = AdapterRegistry()
    adapter = DummyAdapter()
    registry.register(adapter)
    assert registry.get("dummy_tool") is adapter
    assert registry.get("dummy_adapter") is adapter


def test_registry_duplicate_tool_id():
    registry = AdapterRegistry()
    registry.register(DummyAdapter())
    with pytest.raises(ValueError, match="tool_id"):
        registry.register(DummyAdapterSameTool())


def test_registry_duplicate_adapter_id():
    registry = AdapterRegistry()
    registry.register(DummyAdapter())
    with pytest.raises(ValueError, match="adapter_id"):
        registry.register(DummyAdapterSameAdapter())


def test_registry_missing_adapter():
    registry = AdapterRegistry()
    with pytest.raises(KeyError, match="Adapter not found"):
        registry.get("missing")


def test_global_registry_functions():
    adapter = DummyAdapter()
    register_adapter(adapter)
    assert get_adapter("dummy_tool") is adapter
