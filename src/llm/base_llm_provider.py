from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional
from pydantic import BaseModel, ValidationError

from src.models.contracts import ProteinDesignTask, Plan

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


class ProviderConfig(BaseModel):
    """LLM Provider配置"""

    model_name: str
    api_key: Optional[str] = None
    timeout: int = 30
    max_tokens: int = 2000


class BaseProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    def call_planner(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> Dict:
        """生成 Plan, 返回 Plan schema 的 dict"""
        pass

    def validate_plan(self, plan_dict: Dict) -> bool:
        """验证生成的计划是否符合 Plan schema"""
        try:
            Plan.model_validate(plan_dict)
            return True
        except ValidationError:
            return False
