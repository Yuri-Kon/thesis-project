from __future__ import annotations

from typing import Any, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext

__all__ = ["DummyToolAdapter"]


class DummyToolAdapter(BaseToolAdapter):
    """内置 Dummy 工具适配器，用于最小闭环测试"""

    def __init__(self, tool_id: str, adapter_id: str | None = None) -> None:
        self.tool_id = tool_id
        self.adapter_id = adapter_id

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, val in step.inputs.items():
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
                    if not context.has_step_result(step_id):
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': step '{step_id}' not found in context"
                        )
                    try:
                        resolved_value = context.get_step_output(step_id, field)
                    except KeyError as exc:
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                        ) from exc
                    resolved[key] = resolved_value
                    continue
            resolved[key] = val
        return resolved

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return (
            {"dummy_output": f"executed {self.tool_id}", "inputs": inputs},
            {"exec_type": "dummy"},
        )
