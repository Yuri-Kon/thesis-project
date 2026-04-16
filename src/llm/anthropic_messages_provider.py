from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Type

import httpx

from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    ProteinDesignTask,
    ReplanRequest,
)

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


class AnthropicMessagesProvider(BaseProvider):
    """Anthropic-compatible Messages provider for structured planner outputs."""

    def __init__(self, config: ProviderConfig, endpoint: str | None = None):
        self.config = config
        self.endpoint = (endpoint or "https://api.anthropic.com").rstrip("/")
        self._headers = self._build_headers()

    def call_planner(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> Dict:
        payload = self._request_tool_payload(
            system_prompt=self._build_plan_system_prompt(),
            user_prompt=self._build_plan_user_prompt(task, tool_registry),
            tool_name="emit_plan",
            tool_description="Emit a single Plan JSON object.",
            schema_model=Plan,
        )
        payload.setdefault("task_id", task.task_id)
        metadata = payload.setdefault("metadata", {})
        metadata.update(
            {
                "provider": "anthropic_messages",
                "model": self.config.model_name,
                "endpoint": self.endpoint,
            }
        )
        if not self.validate_plan(payload):
            raise ValueError(f"LLM 生成的 Plan 无效: {payload}")
        return payload

    def call_patch(
        self, request: PatchRequest, tool_registry: List["ToolSpec"]
    ) -> Dict | None:
        if not self.config.supports_patch:
            return None
        payload = self._request_tool_payload(
            system_prompt=self._build_patch_system_prompt(),
            user_prompt=self._build_patch_user_prompt(request, tool_registry),
            tool_name="emit_patch",
            tool_description="Emit a single PlanPatch JSON object.",
            schema_model=PlanPatch,
        )
        payload.setdefault("task_id", request.task_id)
        metadata = payload.setdefault("metadata", {})
        metadata.update(
            {
                "provider": "anthropic_messages",
                "model": self.config.model_name,
                "planning_mode": "patch",
                "endpoint": self.endpoint,
            }
        )
        if not self.validate_patch(payload):
            raise ValueError(f"LLM 生成的 PlanPatch 无效: {payload}")
        return payload

    def call_replan(
        self, request: ReplanRequest, tool_registry: List["ToolSpec"]
    ) -> Dict | None:
        if not self.config.supports_replan:
            return None
        payload = self._request_tool_payload(
            system_prompt=self._build_replan_system_prompt(),
            user_prompt=self._build_replan_user_prompt(request, tool_registry),
            tool_name="emit_replan",
            tool_description="Emit a single Plan JSON object for replan.",
            schema_model=Plan,
        )
        payload.setdefault("task_id", request.task_id)
        metadata = payload.setdefault("metadata", {})
        metadata.update(
            {
                "provider": "anthropic_messages",
                "model": self.config.model_name,
                "planning_mode": "replan",
                "endpoint": self.endpoint,
            }
        )
        if not self.validate_plan(payload):
            raise ValueError(f"LLM 生成的 Replan 无效: {payload}")
        return payload

    def _request_tool_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_description: str,
        schema_model: Type[Plan] | Type[PlanPatch],
    ) -> Dict[str, Any]:
        started_at = time.time()
        response = self._post_messages(
            {
                "model": self.config.model_name,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": self.config.max_tokens or 4000,
                "temperature": self.config.temperature,
                "tools": [
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": schema_model.model_json_schema(),
                    }
                ],
                "tool_choice": {"type": "tool", "name": tool_name},
            }
        )
        content = response.get("content")
        if not isinstance(content, list):
            raise ValueError("Anthropic 响应缺少 content 列表")

        tool_input = None
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == tool_name
            ):
                tool_input = block.get("input")
                break

        if not isinstance(tool_input, dict):
            raise ValueError("Anthropic 响应缺少结构化 tool_use payload")

        metadata = tool_input.setdefault("metadata", {})
        metadata["elapsed_seconds"] = time.time() - started_at
        return tool_input

    def _post_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.endpoint}/v1/messages",
                headers=self._headers,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            raise Exception(f"LLM API 调用失败: {exc}") from exc

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise ValueError(f"Anthropic 响应不是合法 JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise ValueError(f"Anthropic 响应不是 dict: {type(body)}")
        return body

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "x-api-key": self.config.api_key or "dummy-key",
            "anthropic-version": self.config.anthropic_version or "2023-06-01",
        }
        if self.config.headers:
            headers.update(self.config.headers)
        return headers

    def _build_plan_system_prompt(self) -> str:
        return (
            "你是一个蛋白质设计规划助手。必须调用 emit_plan 工具输出单个结构化 Plan，"
            "不要输出自由文本 JSON，不要补执行结果。"
        )

    def _build_plan_user_prompt(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> str:
        return (
            f"任务 ID: {task.task_id}\n"
            f"目标: {task.goal}\n"
            f"约束: {json.dumps(task.constraints, ensure_ascii=False, indent=2)}\n"
            f"可用工具:\n{self._format_tool_registry(tool_registry)}\n"
            "请生成完整 Plan。"
        )

    def _build_patch_system_prompt(self) -> str:
        return (
            "你是一个蛋白质设计恢复规划助手。必须调用 emit_patch 工具输出最小 PlanPatch，"
            "优先参数级，其次工具级，最后结构级。"
        )

    def _build_patch_user_prompt(
        self, request: PatchRequest, tool_registry: List["ToolSpec"]
    ) -> str:
        failed = request.context_step_results[-1] if request.context_step_results else None
        failed_payload = {
            "reason": request.reason,
            "failed_step_id": failed.step_id if failed else None,
            "failed_tool": failed.tool if failed else None,
            "failure_type": failed.failure_type if failed else None,
            "error_message": failed.error_message if failed else None,
        }
        return (
            f"任务 ID: {request.task_id}\n"
            f"原始计划: {json.dumps(request.original_plan.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n"
            f"失败上下文: {json.dumps(failed_payload, ensure_ascii=False, indent=2)}\n"
            f"可用工具:\n{self._format_tool_registry(tool_registry)}\n"
            "请生成最小 PlanPatch。"
        )

    def _build_replan_system_prompt(self) -> str:
        return (
            "你是一个蛋白质设计再规划助手。必须调用 emit_replan 工具输出完整 Plan，"
            "优先 suffix_replan，保留成功前缀。"
        )

    def _build_replan_user_prompt(
        self, request: ReplanRequest, tool_registry: List["ToolSpec"]
    ) -> str:
        payload = {
            "reason": request.reason,
            "failed_steps": request.failed_steps,
            "safety_events": [event.model_dump(mode="json") for event in request.safety_events],
        }
        return (
            f"任务 ID: {request.task_id}\n"
            f"原始计划: {json.dumps(request.original_plan.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n"
            f"再规划上下文: {json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            f"可用工具:\n{self._format_tool_registry(tool_registry)}\n"
            "请生成新的 Plan。"
        )

    def _format_tool_registry(self, tool_registry: List["ToolSpec"]) -> str:
        return "\n".join(
            [
                (
                    f"- {tool.id}:\n"
                    f"  能力: {', '.join(tool.capabilities)}\n"
                    f"  输入: {', '.join(tool.inputs)}\n"
                    f"  输出: {', '.join(tool.outputs)}"
                )
                for tool in tool_registry
            ]
        )
