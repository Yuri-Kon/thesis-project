from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    from zai import ZaiClient

    ZAI_AVAILABLE = True
except ImportError:
    ZAI_AVAILABLE = False

from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.response_diagnostics import (
    build_empty_response_error,
    collect_stream_content_with_summary,
    extract_message_content_with_summary,
)
from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    ProteinDesignTask,
    ReplanRequest,
)

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


class ZaiChatProvider(BaseProvider):
    """使用 Z.AI SDK 的 GLM provider。"""

    def __init__(self, config: ProviderConfig, endpoint: Optional[str] = None):
        if not ZAI_AVAILABLE:
            raise ImportError("ZaiChatProvider 需要 zai-sdk。安装方式: pip install zai-sdk")

        self.config = config
        self.endpoint = endpoint
        client_kwargs = {"api_key": config.api_key}
        if endpoint:
            client_kwargs["base_url"] = endpoint
        if config.headers:
            client_kwargs["custom_headers"] = config.headers
        self.client = ZaiClient(**client_kwargs)

    def call_planner(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> Dict:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(task, tool_registry)
        plan_dict = self._request_json(
            system_prompt,
            user_prompt,
            schema_name="plan",
            schema_model=Plan,
        )
        if "task_id" not in plan_dict:
            plan_dict["task_id"] = task.task_id
        plan_dict.setdefault("metadata", {})
        plan_dict["metadata"].update(
            {
                "provider": "zai_chat",
                "model": self.config.model_name,
                "endpoint": self.endpoint or "default",
            }
        )
        if not self.validate_plan(plan_dict):
            raise ValueError(f"LLM 生成的 Plan 无效: {plan_dict}")
        return plan_dict

    def call_patch(
        self, request: PatchRequest, tool_registry: List["ToolSpec"]
    ) -> Dict | None:
        system_prompt = self._build_patch_system_prompt()
        user_prompt = self._build_patch_user_prompt(request, tool_registry)
        patch_dict = self._request_json(
            system_prompt,
            user_prompt,
            schema_name="plan_patch",
            schema_model=PlanPatch,
        )
        if patch_dict is None:
            return None
        if "task_id" not in patch_dict:
            patch_dict["task_id"] = request.task_id
        patch_dict.setdefault("metadata", {})
        patch_dict["metadata"].update(
            {
                "provider": "zai_chat",
                "model": self.config.model_name,
                "planning_mode": "patch",
                "endpoint": self.endpoint or "default",
            }
        )
        if not self.validate_patch(patch_dict):
            raise ValueError(f"LLM 生成的 PlanPatch 无效: {patch_dict}")
        return patch_dict

    def call_replan(
        self, request: ReplanRequest, tool_registry: List["ToolSpec"]
    ) -> Dict | None:
        system_prompt = self._build_replan_system_prompt()
        user_prompt = self._build_replan_user_prompt(request, tool_registry)
        plan_dict = self._request_json(
            system_prompt,
            user_prompt,
            schema_name="replan",
            schema_model=Plan,
        )
        if plan_dict is None:
            return None
        if "task_id" not in plan_dict:
            plan_dict["task_id"] = request.task_id
        plan_dict.setdefault("metadata", {})
        plan_dict["metadata"].update(
            {
                "provider": "zai_chat",
                "model": self.config.model_name,
                "planning_mode": "replan",
                "endpoint": self.endpoint or "default",
            }
        )
        if not self.validate_plan(plan_dict):
            raise ValueError(f"LLM 生成的 Replan 无效: {plan_dict}")
        return plan_dict

    def _request_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        schema_name: str,
        schema_model,
    ) -> Dict | None:
        start_time = time.time()
        try:
            request_kwargs = self._build_request_kwargs(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema_name=schema_name,
                schema_model=schema_model,
            )
            response = self.client.chat.completions.create(**request_kwargs)
        except Exception as e:
            raise Exception(f"LLM API 调用失败: {e}")

        elapsed = time.time() - start_time
        if self.config.stream:
            content, response_summary = collect_stream_content_with_summary(response)
        else:
            content, response_summary = extract_message_content_with_summary(response)
        if not content:
            raise build_empty_response_error(
                candidate_kind=schema_name,
                provider_name="zai_chat",
                model=self.config.model_name,
                endpoint=self.endpoint or "default",
                elapsed_seconds=elapsed,
                request_kwargs=request_kwargs,
                response_summary=response_summary,
                prompt_context={"system": system_prompt, "user": user_prompt},
            )
        content = _strip_markdown_json_fence(content)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 返回无效 JSON: {e}\n内容: {content}")
        if not isinstance(payload, dict):
            raise ValueError(f"LLM 响应不是 dict: {type(payload)}")
        payload.setdefault("metadata", {})
        payload["metadata"]["elapsed_seconds"] = elapsed
        return payload

    def _build_request_kwargs(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema_model,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        if self.config.max_tokens is not None:
            request_kwargs["max_tokens"] = self.config.max_tokens
        if self.config.stream:
            request_kwargs["stream"] = True
        else:
            response_format = self._build_response_format(
                schema_name=schema_name,
                schema_model=schema_model,
            )
            if response_format is not None:
                request_kwargs["response_format"] = response_format
        if self.config.extra_body:
            if "thinking" in self.config.extra_body:
                request_kwargs["thinking"] = self.config.extra_body["thinking"]
            if "extra_body" in self.config.extra_body:
                request_kwargs["extra_body"] = self.config.extra_body["extra_body"]
        return request_kwargs

    def _build_response_format(self, *, schema_name: str, schema_model) -> dict | None:
        if not self.config.use_response_format:
            return None
        mode = (self.config.structured_output_mode or "json_object").strip().lower()
        if mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema_model.model_json_schema(),
                    "strict": True,
                },
            }
        return {"type": "json_object"}

    def _collect_stream_content(self, response) -> str:
        parts: list[str] = []
        for chunk in response:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            reasoning = getattr(delta, "reasoning_content", None)
            if isinstance(reasoning, str) and reasoning:
                continue
            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                parts.append(content)
        return "".join(parts).strip()

    def _build_system_prompt(self) -> str:
        return """你是一个蛋白质设计规划助手。你的核心职责是：
1. 解析自然语言任务目标；
2. 从可用工具中选择合适工具链；
3. 生成可执行的结构化 Plan JSON。

给定:
- 一个带有目标和约束的蛋白质设计任务
- 一个包含可用工具的注册表（来自 ProteinToolKG）

输出:
- 一个遵循此 schema 的有效 JSON 计划:
  {
    "task_id": "string (将被提供)",
    "steps": [
      {
        "id": "S1", "S2", 等 (顺序步骤 ID),
        "tool": "来自注册表的 tool_id",
        "inputs": {
          "param": "值或符号引用如 'S1.sequence'"
        },
        "metadata": {}
      }
    ],
    "constraints": {},
    "metadata": {"explanation": "此计划的简要推理"}
  }

规则:
1. 步骤 ID 必须顺序: S1, S2, S3, 等
2. 工具名称必须与注册表中的 tool ID 完全匹配
3. 若不确定具体工具ID，请将 tool 设为 "unknown" 并在 metadata.capability 中提供能力
4. 使用符号引用 (如 "S1.sequence") 来引用前序步骤的输出
5. 不要内联或计算实际值 - 保持引用的符号形式
6. 链接步骤时考虑工具能力、输入和输出
7. 尽可能选择更简单的计划
8. 始终返回有效的 JSON
9. 必须把 task.goal 视为主要自然语言需求来源；如果约束中缺少 goal_type、prompt、length_range 等，可以根据 goal 合理补充到 returned constraints 中
10. 对 de novo 设计任务，优先生成“序列生成 -> 结构预测 -> 结构条件精修/再设计 -> 结构重映射或质量检查”的多步链，而不是退化成单步计划
11. 如果用户表达了本地/远程偏好，应优先选择对应 adapter_mode 的工具
12. 计划中的 inputs 应尽量保留自然语言目标或结构化约束，不要随意发明具体序列值
"""

    def _build_user_prompt(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> str:
        tools_desc = []
        for tool in tool_registry:
            tools_desc.append(
                f"- {tool.id}:\n"
                f"  能力: {', '.join(tool.capabilities)}\n"
                f"  输入: {', '.join(tool.inputs)}\n"
                f"  输出: {', '.join(tool.outputs)}\n"
                f"  成本: {tool.cost}, 安全级别: {tool.safety_level}"
            )

        tools_text = "\n".join(tools_desc)

        return f"""任务 ID: {task.task_id}
目标: {task.goal}
约束: {json.dumps(task.constraints, indent=2)}

可用工具:
{tools_text}

注意：如果不确定具体 tool_id，请将 tool 设置为 "unknown"，并在 metadata.capability 中提供能力标识。
请先理解目标中的自然语言要求，例如长度、是否需要结构预览、是否强调稳定性/可溶性、是否偏好本地或远程工具。
如果 goal 明显是蛋白质从零设计任务，请在 returned constraints 中补上:
- goal_type: de_novo_design
- prompt: 原始或精炼后的自然语言设计提示
- length_range: 若能从目标中提取
- prefer_remote: 若能从目标中提取

请生成一个多步计划来完成这个蛋白质设计任务。仅返回遵循系统提示中 schema 的有效 JSON。
"""

    def _build_patch_system_prompt(self) -> str:
        return """你是一个蛋白质设计恢复规划助手。你的任务是在步骤失败后生成最小可执行 PlanPatch JSON。

目标：
1. 优先参数级修补；
2. 其次工具级替换；
3. 最后结构级插入保护步骤；
4. 不要直接生成完整 Plan，除非无法用 patch 表达。

返回 schema:
{
  "task_id": "string",
  "operations": [
    {
      "op": "replace_step" | "insert_step_before" | "insert_step_after",
      "target": "existing_step_id",
      "step": {
        "id": "step_id",
        "tool": "tool_id",
        "inputs": {},
        "metadata": {}
      }
    }
  ],
  "metadata": {
    "recovery_layer": "parameter_level|tool_level|structure_level",
    "reason": "string"
  }
}

规则：
1. patch 必须是局部修改，不能无故改动其他步骤；
2. tool 必须来自注册表，或用 metadata.capability 指示待解析能力；
3. 保持 task_id 不变；
4. 尽量输出单个最优 patch；
5. 始终返回有效 JSON。"""

    def _build_patch_user_prompt(
        self, request: PatchRequest, tool_registry: List["ToolSpec"]
    ) -> str:
        tools_text = self._format_tool_registry(tool_registry)
        failed = request.context_step_results[-1] if request.context_step_results else None
        failed_payload = {
            "reason": request.reason,
            "failed_step_id": failed.step_id if failed else None,
            "failed_tool": failed.tool if failed else None,
            "failure_type": failed.failure_type if failed else None,
            "error_message": failed.error_message if failed else None,
        }
        return f"""任务 ID: {request.task_id}
原始计划: {json.dumps(request.original_plan.model_dump(mode='json'), ensure_ascii=False, indent=2)}
失败上下文: {json.dumps(failed_payload, ensure_ascii=False, indent=2)}

可用工具:
{tools_text}

请生成最小 PlanPatch。仅返回有效 JSON。"""

    def _build_replan_system_prompt(self) -> str:
        return """你是一个蛋白质设计再规划助手。你的任务是在 patch 不足以恢复时输出新的 Plan JSON。

目标：
1. 优先 suffix_replan，尽量保留成功前缀；
2. 仅在必要时重构后续步骤；
3. 始终返回完整可执行 Plan JSON。"""

    def _build_replan_user_prompt(
        self, request: ReplanRequest, tool_registry: List["ToolSpec"]
    ) -> str:
        tools_text = self._format_tool_registry(tool_registry)
        payload = {
            "reason": request.reason,
            "failed_steps": request.failed_steps,
            "safety_events": [event.model_dump(mode="json") for event in request.safety_events],
        }
        return f"""任务 ID: {request.task_id}
原始计划: {json.dumps(request.original_plan.model_dump(mode='json'), ensure_ascii=False, indent=2)}
再规划上下文: {json.dumps(payload, ensure_ascii=False, indent=2)}

可用工具:
{tools_text}

请生成新的 Plan。仅返回有效 JSON。"""

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
