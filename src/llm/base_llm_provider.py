from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

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

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


class ProviderConfig(BaseModel):
    """LLM Provider配置"""

    model_name: str
    api_key: str | None = None
    timeout: int = 300
    max_tokens: int | None = 2000
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    api_style: str | None = None
    structured_output_mode: str | None = None
    tool_strategy: str | None = None
    supports_patch: bool = True
    supports_replan: bool = True
    supports_reasoning: bool = False
    headers: dict[str, str] | None = None
    organization: str | None = None
    anthropic_version: str | None = None
    extra_body: JsonObject | None = None
    use_response_format: bool = True


class BaseProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    def call_planner(
        self, task: ProteinDesignTask, tool_registry: list["ToolSpec"]
    ) -> JsonObject:
        """生成 Plan, 返回 Plan schema 的 dict"""
        pass

    def call_patch(
        self, request: PatchRequest, tool_registry: list["ToolSpec"]
    ) -> JsonObject | None:
        """可选：生成 PlanPatch，默认不实现。"""
        _ = request
        _ = tool_registry
        return None

    def call_replan(
        self, request: ReplanRequest, tool_registry: list["ToolSpec"]
    ) -> JsonObject | None:
        """可选：生成 Replan Plan，默认不实现。"""
        _ = request
        _ = tool_registry
        return None

    def validate_plan(self, plan_dict: JsonObject) -> bool:
        """验证生成的计划是否符合 Plan schema"""
        try:
            _ = Plan.model_validate(plan_dict)
            return True
        except ValidationError:
            return False

    def validate_patch(self, patch_dict: JsonObject) -> bool:
        """验证生成的 patch 是否符合 PlanPatch schema"""
        try:
            _ = PlanPatch.model_validate(patch_dict)
            return True
        except ValidationError:
            return False
