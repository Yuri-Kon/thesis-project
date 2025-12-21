from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext

__all__ = ["BaseToolAdapter"]


class BaseToolAdapter(ABC):
    """ToolAdapter 抽象基类，统一工具调用入口"""

    # 对应 ProteinToolKG 中的 tool.id
    tool_id: str
    # 可选适配器别名，用于注册表检索
    adapter_id: str | None = None

    @abstractmethod
    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        """将 PlanStep.inputs 解析为工具实际输入"""

    @abstractmethod
    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """本地执行工具并返回 (outputs, metrics)"""
