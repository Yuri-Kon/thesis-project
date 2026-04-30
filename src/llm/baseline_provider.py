"""基线 LLM Provider - 简单确定性规划

该 provider 实现了一个简单的基线策略来生成计划。
它作为默认回退方案，以及与更复杂的基于 LLM 的 providers 进行对比的基线。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeGuard, cast, override

from src.llm.base_llm_provider import BaseProvider, JsonObject, JsonValue, ProviderConfig
from src.models.contracts import ProteinDesignTask

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


class BaselineProvider(BaseProvider):
    """生成简单单步计划的基线 provider

    该 provider 模拟原始 PlannerAgent 的行为:
    - 使用第一个可用工具生成单步计划
    - 直接使用任务约束作为输入
    - 无 LLM 调用，完全确定性

    适用于:
    - 测试和验证
    - 基线对比
    - LLM providers 不可用时的回退
    """

    def __init__(self, config: ProviderConfig | None = None) -> None:
        """初始化基线 provider

        Args:
            config: Provider 配置（基线版本未使用，为接口兼容性保留）
        """
        self.config: ProviderConfig = config or ProviderConfig(model_name="baseline")

    @override
    def call_planner(
        self,
        task: ProteinDesignTask,
        tool_registry: list["ToolSpec"],
    ) -> JsonObject:
        """生成简单的单步计划

        策略:
        1. 从注册表选择第一个工具
        2. 使用 task.constraints.get("sequence") 作为主要输入
        3. 生成 ID 为 "S1" 的单个步骤

        Args:
            task: 蛋白质设计任务
            tool_registry: 来自 planner 注册表的可用工具

        Returns:
            Plan 的 Dict 表示（task_id, steps, constraints, metadata）
        """
        if not tool_registry:
            raise ValueError(
                "Tool registry is empty; cannot build baseline plan."
            )
        tool_id = tool_registry[0].id

        # 从任务约束中提取 sequence 或使用默认值
        constraints = cast(dict[str, object], task.constraints)
        sequence_value = constraints.get(
            "sequence",
            "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR",
        )
        sequence = sequence_value if isinstance(sequence_value, str) else str(sequence_value)

        # 构建单步计划
        step: JsonObject = {
            "id": "S1",
            "tool": tool_id,
            "inputs": {"sequence": sequence},
            "metadata": {"provider": "baseline", "strategy": "single_step"},
        }

        plan_dict: JsonObject = {
            "task_id": task.task_id,
            "steps": [step],
            "constraints": _json_object_from_mapping(constraints),
            "metadata": {
                "provider": "baseline",
                "model": self.config.model_name,
            },
        }

        return plan_dict


def _json_object_from_mapping(mapping: dict[str, object]) -> JsonObject:
    result: JsonObject = {}
    for key, value in mapping.items():
        if _is_json_value(value):
            result[key] = value
        else:
            result[key] = str(value)
    return result


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(list[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False
