from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING, Dict, List, Optional
from pydantic import BaseModel, ValidationError

from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    ProteinDesignTask,
    ReplanRequest,
)

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


class ProviderConfig(BaseModel):
    """LLM Provider配置"""

    model_name: str
    api_key: Optional[str] = None
    timeout: int = 300
    max_tokens: int = 2000
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    extra_body: Optional[Dict[str, Any]] = None
    use_response_format: bool = True


class BaseProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    def call_planner(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> Dict:
        """生成 Plan, 返回 Plan schema 的 dict"""
        pass

    def call_patch(
        self, request: PatchRequest, tool_registry: List["ToolSpec"]
    ) -> Dict | None:
        """可选：生成 PlanPatch，默认不实现。"""
        return None

    def call_replan(
        self, request: ReplanRequest, tool_registry: List["ToolSpec"]
    ) -> Dict | None:
        """可选：生成 Replan Plan，默认不实现。"""
        return None

    def validate_plan(self, plan_dict: Dict) -> bool:
        """验证生成的计划是否符合 Plan schema"""
        try:
            Plan.model_validate(plan_dict)
            return True
        except ValidationError:
            return False

    def validate_patch(self, patch_dict: Dict) -> bool:
        """验证生成的 patch 是否符合 PlanPatch schema"""
        try:
            PlanPatch.model_validate(patch_dict)
            return True
        except ValidationError:
            return False
