from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Type

from anthropic import Anthropic

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
        self._client = Anthropic(
            api_key=self.config.api_key,
            base_url=self.endpoint,
            timeout=self.config.timeout,
        )

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

        tool_input = _normalize_tool_payload(tool_input)
        metadata = tool_input.setdefault("metadata", {})
        metadata["elapsed_seconds"] = time.time() - started_at
        return tool_input

    def _post_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.messages.create(
                **payload,
                extra_headers=self._build_extra_headers(),
            )
        except Exception as exc:
            raise Exception(f"LLM API 调用失败: {exc}") from exc

        if hasattr(response, "model_dump"):
            body = response.model_dump(mode="python")
        elif isinstance(response, dict):
            body = response
        else:
            raise ValueError(f"Anthropic 响应不是可解析对象: {type(response)}")
        if not isinstance(body, dict):
            raise ValueError(f"Anthropic 响应不是 dict: {type(body)}")
        return body

    def _build_extra_headers(self) -> dict[str, str]:
        headers = {
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


def _normalize_tool_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_json_like_value(payload)
    if not isinstance(normalized, dict):
        raise ValueError("Anthropic tool_use payload 归一化后不是 dict")
    return _normalize_plan_like_payload(normalized)


def _normalize_plan_like_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    if isinstance(normalized.get("steps"), list):
        normalized["steps"] = _normalize_plan_steps(normalized["steps"])
    if isinstance(normalized.get("operations"), list):
        normalized["operations"] = _normalize_patch_operations(normalized["operations"])
    return normalized


def _normalize_plan_steps(steps: list[Any]) -> list[Any]:
    step_id_map, tool_reference_map = _build_step_reference_maps(steps)
    normalized_steps: list[Any] = []
    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            normalized_steps.append(raw_step)
            continue
        step = dict(raw_step)
        step["id"] = f"S{index}"
        inputs = step.get("inputs")
        if isinstance(inputs, dict):
            step["inputs"] = {
                key: _normalize_reference_value(
                    value,
                    input_key=key,
                    step_id_map=step_id_map,
                    tool_reference_map=tool_reference_map,
                )
                for key, value in inputs.items()
            }
        normalized_steps.append(step)
    return normalized_steps


def _normalize_patch_operations(operations: list[Any]) -> list[Any]:
    pseudo_steps: list[dict[str, Any]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        step = operation.get("step")
        if not isinstance(step, dict):
            continue
        target = operation.get("target")
        pseudo_step = dict(step)
        if "id" not in pseudo_step and isinstance(target, str):
            pseudo_step["id"] = target
        pseudo_steps.append(pseudo_step)

    step_id_map, tool_reference_map = _build_step_reference_maps(pseudo_steps)
    normalized_operations: list[Any] = []
    for operation in operations:
        if not isinstance(operation, dict):
            normalized_operations.append(operation)
            continue
        normalized = dict(operation)
        target = normalized.get("target")
        if isinstance(target, str):
            normalized["target"] = _normalize_step_identifier(
                target,
                step_id_map=step_id_map,
            )
        step = normalized.get("step")
        if isinstance(step, dict):
            normalized_step = dict(step)
            step_id = normalized_step.get("id")
            if isinstance(step_id, str):
                normalized_step["id"] = _normalize_step_identifier(
                    step_id,
                    step_id_map=step_id_map,
                )
            inputs = normalized_step.get("inputs")
            if isinstance(inputs, dict):
                normalized_step["inputs"] = {
                    key: _normalize_reference_value(
                        value,
                        input_key=key,
                        step_id_map=step_id_map,
                        tool_reference_map=tool_reference_map,
                    )
                    for key, value in inputs.items()
                }
            normalized["step"] = normalized_step
        normalized_operations.append(normalized)
    return normalized_operations


def _build_step_reference_maps(
    steps: list[Any],
) -> tuple[dict[str, str], dict[str, str]]:
    step_id_map: dict[str, str] = {}
    tool_to_step_ids: dict[str, list[str]] = {}
    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        canonical_id = f"S{index}"
        raw_id = raw_step.get("id")
        if isinstance(raw_id, str):
            step_id_map[raw_id] = canonical_id
            compact = raw_id.strip()
            if compact:
                step_id_map[compact] = canonical_id
                if compact.isdigit():
                    step_id_map[f"step_{compact}"] = canonical_id
        step_id_map[str(index)] = canonical_id
        step_id_map[f"step_{index}"] = canonical_id

        tool_name = raw_step.get("tool")
        if isinstance(tool_name, str) and tool_name.strip():
            tool_to_step_ids.setdefault(tool_name.strip(), []).append(canonical_id)

    tool_reference_map = {
        tool_name: step_ids[0]
        for tool_name, step_ids in tool_to_step_ids.items()
        if len(step_ids) == 1
    }
    return step_id_map, tool_reference_map


def _normalize_reference_value(
    value: Any,
    *,
    input_key: str | None,
    step_id_map: dict[str, str],
    tool_reference_map: dict[str, str],
) -> Any:
    if isinstance(value, list):
        return [
            _normalize_reference_value(
                item,
                input_key=input_key,
                step_id_map=step_id_map,
                tool_reference_map=tool_reference_map,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _normalize_reference_value(
                item,
                input_key=key,
                step_id_map=step_id_map,
                tool_reference_map=tool_reference_map,
            )
            for key, item in value.items()
        }
    if not isinstance(value, str):
        return value

    normalized = _normalize_symbolic_reference(
        value,
        input_key=input_key,
        step_id_map=step_id_map,
        tool_reference_map=tool_reference_map,
    )
    if normalized is not None:
        return _normalize_reference_field_for_input_key(
            normalized,
            input_key=input_key,
        )
    return value


def _normalize_symbolic_reference(
    value: str,
    *,
    input_key: str | None,
    step_id_map: dict[str, str],
    tool_reference_map: dict[str, str],
) -> str | None:
    placeholder = _normalize_placeholder_reference(
        value,
        input_key=input_key,
        step_id_map=step_id_map,
    )
    if placeholder is not None:
        return placeholder

    head, sep, tail = value.partition(".")
    if not sep or not tail:
        return None

    normalized_head = step_id_map.get(head.strip())
    normalized_field = tail.strip()
    if normalized_head is None and normalized_field.startswith("output."):
        normalized_head = tool_reference_map.get(head.strip())
        normalized_field = normalized_field.removeprefix("output.").strip()
    if normalized_head is None:
        return None
    if not normalized_field:
        return None
    return f"{normalized_head}.{normalized_field}"


def _normalize_placeholder_reference(
    value: str,
    *,
    input_key: str | None,
    step_id_map: dict[str, str],
) -> str | None:
    payload = value.strip()
    if not (payload.startswith("<from_step_") and payload.endswith(">")):
        return None
    body = payload[len("<from_step_") : -1]
    step_token, sep, suffix = body.partition("_")
    canonical_step = step_id_map.get(step_token)
    if canonical_step is None:
        return None

    field = suffix.strip() if sep else ""
    if field == "output":
        field = ""
    if not field:
        field = _infer_reference_field(input_key)
    if not field:
        return None
    return f"{canonical_step}.{field}"


def _infer_reference_field(input_key: str | None) -> str | None:
    if not isinstance(input_key, str):
        return None
    lookup = {
        "sequence": "sequence",
        "pdb_path": "pdb_path",
        "candidates": "candidates",
        "structure_results": "structure_results",
        "qc_metrics": "qc_metrics",
        "score_table": "score_table",
        "top_k": "top_k",
    }
    return lookup.get(input_key.strip())


def _normalize_reference_field_for_input_key(
    value: str,
    *,
    input_key: str | None,
) -> str:
    head, sep, tail = value.partition(".")
    if not sep or not tail:
        return value
    expected_field = _infer_reference_field(input_key)
    if expected_field is None:
        return value
    normalized_field = tail.strip()
    if normalized_field == expected_field:
        return value
    if not _should_rewrite_reference_field(
        input_key=input_key,
        current_field=normalized_field,
        expected_field=expected_field,
    ):
        return value
    return f"{head.strip()}.{expected_field}"


def _should_rewrite_reference_field(
    *,
    input_key: str | None,
    current_field: str,
    expected_field: str,
) -> bool:
    if not isinstance(input_key, str):
        return False
    normalized_key = input_key.strip()
    if normalized_key == "sequence" and current_field in {"candidates", "sequence_candidates"}:
        return True
    if normalized_key == "candidates" and current_field == "sequence":
        return True
    if normalized_key == "pdb_path" and current_field in {"structure_pdb", "structure_path", "cif_path"}:
        return True
    if normalized_key == "structure_results" and current_field in {"pdb_path", "sequence", "plddt"}:
        return True
    return current_field == expected_field


def _normalize_step_identifier(
    value: str,
    *,
    step_id_map: dict[str, str],
) -> str:
    return step_id_map.get(value.strip(), value)


def _normalize_json_like_value(value: Any) -> Any:
    parsed = _parse_json_like_string(value)
    if parsed is not value:
        return _normalize_json_like_value(parsed)
    if isinstance(value, list):
        return [_normalize_json_like_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_json_like_value(item)
            for key, item in value.items()
        }
    return value


def _parse_json_like_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    payload = _strip_markdown_json_fence(value).strip()
    if not payload or payload[0] not in "[{":
        return value

    candidates = [payload]
    if '""' in payload:
        candidates.append(payload.replace('""', '"'))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return value


def _strip_markdown_json_fence(content: str) -> str:
    payload = content.strip()
    if not payload.startswith("```"):
        return payload

    lines = payload.splitlines()
    if not lines:
        return payload
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
