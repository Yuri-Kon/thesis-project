from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.provider_payload_parser import (
    ProviderPayloadParseResult,
    ProviderPayloadParser,
    ProviderPayloadValidationError,
)
from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    ProteinDesignTask,
    ReplanRequest,
)
from src.models.validation import (
    CandidateExecutionValidationError,
    validate_plan_executability,
)
from src.workflow.patch import apply_patch

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


_MAX_PROVIDER_REPAIR_RETRIES = 2
_TWO_STAGE_PLAN_STRATEGY = "two_stage_plan"


class PlanSkeletonStep(BaseModel):
    """两阶段规划中的单步骨架。

    Attributes:
        id: 可选步骤 ID，provider 层会归一化为 S1/S2/...。
        tool: 该步骤选择的工具 ID。
        metadata: 步骤级附加说明，不承载执行结果。
    """

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    tool: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanSkeleton(BaseModel):
    """两阶段规划第一阶段输出的计划骨架。

    Attributes:
        task_id: 任务 ID，可由 provider 层补齐。
        steps: 只包含步骤顺序和工具选择，不包含 inputs。
        constraints: 任务约束透传字段。
        metadata: 骨架生成元信息。
        explanation: 可选解释。
    """

    model_config = ConfigDict(extra="forbid")

    task_id: str | None = None
    steps: List[PlanSkeletonStep]
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    explanation: str | None = None


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
        if self._uses_two_stage_plan():
            return self._call_two_stage_planner(task, tool_registry)

        payload = self._request_tool_payload(
            system_prompt=self._build_plan_system_prompt(),
            user_prompt=self._build_plan_user_prompt(task, tool_registry),
            tool_name="emit_plan",
            tool_description="Emit a single Plan JSON object.",
            schema_model=Plan,
            candidate_kind="plan",
            tool_registry=tool_registry,
            validator=lambda candidate, parse_result: self._validate_plan_candidate(
                candidate,
                parse_result=parse_result,
                task=task,
                tool_registry=tool_registry,
                materialize_inputs=True,
            ),
        )
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

    def _call_two_stage_planner(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> Dict[str, Any]:
        skeleton = self._request_tool_payload(
            system_prompt=self._build_plan_skeleton_system_prompt(),
            user_prompt=self._build_plan_skeleton_user_prompt(task, tool_registry),
            tool_name="emit_plan_skeleton",
            tool_description="Emit a PlanSkeleton JSON object with steps and tools only.",
            schema_model=PlanSkeleton,
            candidate_kind="plan_skeleton",
            tool_registry=tool_registry,
            validator=lambda candidate, parse_result: self._validate_plan_skeleton_candidate(
                candidate,
                parse_result=parse_result,
                task=task,
                tool_registry=tool_registry,
            ),
        )
        skeleton_plan = PlanSkeleton.model_validate(skeleton)
        payload = self._request_tool_payload(
            system_prompt=self._build_plan_system_prompt(),
            user_prompt=self._build_plan_inputs_user_prompt(
                task,
                tool_registry,
                skeleton=skeleton_plan,
            ),
            tool_name="emit_plan",
            tool_description="Emit a single Plan JSON object aligned with the provided skeleton.",
            schema_model=Plan,
            candidate_kind="plan",
            tool_registry=tool_registry,
            validator=lambda candidate, parse_result: self._validate_plan_candidate(
                candidate,
                parse_result=parse_result,
                task=task,
                tool_registry=tool_registry,
                materialize_inputs=True,
                skeleton=skeleton_plan,
            ),
        )
        metadata = payload.setdefault("metadata", {})
        metadata.update(
            {
                "provider": "anthropic_messages",
                "model": self.config.model_name,
                "endpoint": self.endpoint,
                "provider_generation_mode": _TWO_STAGE_PLAN_STRATEGY,
                "provider_plan_skeleton": self._skeleton_summary(skeleton_plan),
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
            candidate_kind="patch",
            tool_registry=tool_registry,
            validator=lambda candidate, parse_result: self._validate_patch_candidate(
                candidate,
                parse_result=parse_result,
                request=request,
                tool_registry=tool_registry,
            ),
        )
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
            candidate_kind="replan",
            tool_registry=tool_registry,
            validator=lambda candidate, parse_result: self._validate_plan_candidate(
                candidate,
                parse_result=parse_result,
                task=self._build_validation_task(
                    task_id=request.task_id,
                    constraints=request.original_plan.constraints,
                ),
                tool_registry=tool_registry,
                materialize_inputs=False,
                constraints_override=request.original_plan.constraints,
            ),
        )
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
        schema_model: Type[BaseModel],
        candidate_kind: str,
        tool_registry: List["ToolSpec"],
        validator: Callable[[dict[str, Any], ProviderPayloadParseResult], dict[str, Any]],
    ) -> Dict[str, Any]:
        started_at = time.time()
        parser = ProviderPayloadParser(tool_registry)
        last_error: ProviderPayloadValidationError | None = None

        for attempt in range(_MAX_PROVIDER_REPAIR_RETRIES + 1):
            current_user_prompt = user_prompt
            if last_error is not None:
                current_user_prompt = self._build_repair_user_prompt(
                    base_user_prompt=user_prompt,
                    candidate_kind=candidate_kind,
                    tool_name=tool_name,
                    error=last_error,
                )
            response = self._post_messages(
                {
                    "model": self.config.model_name,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": current_user_prompt}],
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
            tool_input = self._extract_tool_input(response, tool_name=tool_name)
            parse_result = parser.parse(tool_input, candidate_kind=candidate_kind)
            try:
                validated = validator(
                    parse_result.normalized_payload or {},
                    parse_result,
                )
            except ProviderPayloadValidationError as exc:
                last_error = exc.with_attempts(attempt + 1)
                if attempt >= _MAX_PROVIDER_REPAIR_RETRIES:
                    raise last_error
                continue

            metadata = validated.setdefault("metadata", {})
            metadata["elapsed_seconds"] = time.time() - started_at
            metadata["provider_validation"] = {
                "candidate_kind": candidate_kind,
                "repair_attempts": attempt,
                "total_attempts": attempt + 1,
                "syntax_repairs": [repair.as_dict() for repair in parse_result.repairs],
            }
            return validated

        raise ValueError(f"{candidate_kind} provider validation failed without details")

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
            "steps 必须是 JSON array，不能是字符串；step id 必须是 S1/S2/...；"
            "跨步引用只能写成 S<n>.field；严禁输出 ${...}、$...、<...>、auto、"
            "CANDIDATES 之类裸占位符。"
        )

    def _build_plan_skeleton_system_prompt(self) -> str:
        return (
            "你是一个蛋白质设计规划助手。必须调用 emit_plan_skeleton 工具输出计划骨架，"
            "只决定步骤顺序和 tool，不要填写 inputs，不要输出执行结果。"
            "steps 必须是 JSON array；step id 必须是 S1/S2/...；"
            "tool 必须来自可用工具列表。"
        )

    def _build_plan_user_prompt(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> str:
        return (
            f"任务 ID: {task.task_id}\n"
            f"目标: {task.goal}\n"
            f"约束: {json.dumps(task.constraints, ensure_ascii=False, indent=2)}\n"
            f"可用工具:\n{self._format_tool_registry(tool_registry)}\n"
            "请生成完整 Plan。\n"
            "要求：\n"
            "- steps must be a JSON array, never a string\n"
            "- all step ids must be S1/S2/... in execution order\n"
            "- all cross-step references must be S<n>.field\n"
            "- do not emit ${...}, $CANDIDATES, $STEP_2, <generated_sequence>, <predicted_pdb>, auto\n"
        )

    def _build_plan_skeleton_user_prompt(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> str:
        return (
            f"任务 ID: {task.task_id}\n"
            f"目标: {task.goal}\n"
            f"约束: {json.dumps(task.constraints, ensure_ascii=False, indent=2)}\n"
            f"可用工具:\n{self._format_tool_registry(tool_registry)}\n"
            "请先生成 PlanSkeleton。\n"
            "要求：\n"
            "- steps must be a JSON array, never a string\n"
            "- each step must contain only id/tool/metadata, no inputs\n"
            "- all step ids must be S1/S2/... in execution order\n"
            "- tool must be selected from the available tools\n"
            "- do not emit execution outputs, placeholders, or cross-step references\n"
        )

    def _build_plan_inputs_user_prompt(
        self,
        task: ProteinDesignTask,
        tool_registry: List["ToolSpec"],
        *,
        skeleton: PlanSkeleton,
    ) -> str:
        skeleton_json = json.dumps(
            skeleton.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        return (
            f"任务 ID: {task.task_id}\n"
            f"目标: {task.goal}\n"
            f"约束: {json.dumps(task.constraints, ensure_ascii=False, indent=2)}\n"
            f"可用工具:\n{self._format_tool_registry(tool_registry)}\n"
            f"已确认 PlanSkeleton:\n{skeleton_json}\n"
            "请基于该 skeleton 生成完整 Plan。\n"
            "要求：\n"
            "- keep exactly the same step count, ids, order, and tools as PlanSkeleton\n"
            "- fill only executable inputs and metadata; do not invent execution outputs\n"
            "- steps must be a JSON array, never a string\n"
            "- all cross-step references must be S<n>.field\n"
            "- do not emit ${...}, $CANDIDATES, $STEP_2, <generated_sequence>, <predicted_pdb>, auto\n"
        )

    def _build_patch_system_prompt(self) -> str:
        return (
            "你是一个蛋白质设计恢复规划助手。必须调用 emit_patch 工具输出最小 PlanPatch，"
            "优先参数级，其次工具级，最后结构级。"
            "operations 必须是 JSON array；所有引用只能写成 S<n>.field；"
            "严禁输出 ${...}、$...、<...>、auto、裸占位符。"
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
            "请生成最小 PlanPatch。\n"
            "要求：\n"
            "- operations must be a JSON array\n"
            "- replace_step must keep the same target id\n"
            "- all references must use S<n>.field\n"
            "- do not emit ${...}, $STEP_2, $CANDIDATES, <...>, auto\n"
        )

    def _build_replan_system_prompt(self) -> str:
        return (
            "你是一个蛋白质设计再规划助手。必须调用 emit_replan 工具输出完整 Plan，"
            "优先 suffix_replan，保留成功前缀。"
            "steps 必须是 JSON array；step id 必须是 S1/S2/...；"
            "所有跨步引用只能使用 S<n>.field；严禁 ${...}、$...、<...>、auto。"
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
            "请生成新的 Plan。\n"
            "要求：\n"
            "- keep the successful prefix whenever possible\n"
            "- steps must be a JSON array, never a string\n"
            "- all step ids must be S1/S2/... in order\n"
            "- all references must use S<n>.field\n"
            "- do not emit ${...}, $..., <...>, auto, or bare placeholders\n"
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

    def _extract_tool_input(
        self,
        response: dict[str, Any],
        *,
        tool_name: str,
    ) -> dict[str, Any]:
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
        return tool_input

    def _validate_plan_candidate(
        self,
        candidate: dict[str, Any],
        *,
        parse_result: ProviderPayloadParseResult,
        task: ProteinDesignTask,
        tool_registry: List["ToolSpec"],
        materialize_inputs: bool,
        constraints_override: dict[str, Any] | None = None,
        skeleton: PlanSkeleton | None = None,
    ) -> dict[str, Any]:
        candidate = dict(candidate)
        candidate.setdefault("task_id", task.task_id)
        candidate.setdefault("metadata", {})
        self._raise_on_syntax_issues(
            candidate_kind="plan" if materialize_inputs else "replan",
            parse_result=parse_result,
        )
        try:
            plan = Plan.model_validate(candidate)
        except ValidationError as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="plan" if materialize_inputs else "replan",
                failure_type="SCHEMA_INVALID",
                issues=self._build_schema_issues(exc),
                normalized_payload=candidate,
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc

        if skeleton is not None:
            self._raise_on_skeleton_mismatch(
                plan=plan,
                skeleton=skeleton,
                parse_result=parse_result,
            )

        try:
            plan = self._prepare_plan_for_validation(
                plan,
                task=task,
                tool_registry=tool_registry,
                materialize_inputs=materialize_inputs,
                constraints_override=constraints_override,
            )
        except Exception as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="plan" if materialize_inputs else "replan",
                failure_type="EXECUTABILITY_INVALID",
                issues=[
                    {
                        "code": "PLAN_PREPARATION_INVALID",
                        "path": "$.steps",
                        "message": str(exc),
                    }
                ],
                normalized_payload=plan.model_dump(mode="json"),
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc
        try:
            validate_plan_executability(plan, task)
        except CandidateExecutionValidationError as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="plan" if materialize_inputs else "replan",
                failure_type="EXECUTABILITY_INVALID",
                issues=[issue.as_dict() for issue in exc.issues],
                normalized_payload=plan.model_dump(mode="json"),
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc
        return plan.model_dump(mode="json")

    def _validate_plan_skeleton_candidate(
        self,
        candidate: dict[str, Any],
        *,
        parse_result: ProviderPayloadParseResult,
        task: ProteinDesignTask,
        tool_registry: List["ToolSpec"],
    ) -> dict[str, Any]:
        candidate = dict(candidate)
        candidate.setdefault("task_id", task.task_id)
        candidate.setdefault("constraints", task.constraints)
        candidate.setdefault("metadata", {})
        self._raise_on_syntax_issues(
            candidate_kind="plan_skeleton",
            parse_result=parse_result,
        )
        try:
            skeleton = PlanSkeleton.model_validate(candidate)
        except ValidationError as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="plan_skeleton",
                failure_type="SCHEMA_INVALID",
                issues=self._build_schema_issues(exc),
                normalized_payload=candidate,
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc

        registry_ids = {tool.id for tool in tool_registry}
        issues: list[dict[str, Any]] = []
        for index, step in enumerate(skeleton.steps):
            if step.tool not in registry_ids:
                issues.append(
                    {
                        "code": "SKELETON_TOOL_UNKNOWN",
                        "path": f"$.steps[{index}].tool",
                        "message": f"tool '{step.tool}' is not in registry",
                        "observed": step.tool,
                        "repair_hint": "choose a tool id from the available tool registry",
                    }
                )
        if issues:
            raise ProviderPayloadValidationError(
                candidate_kind="plan_skeleton",
                failure_type="SCHEMA_INVALID",
                issues=issues,
                normalized_payload=skeleton.model_dump(mode="json"),
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            )
        return skeleton.model_dump(mode="json")

    def _validate_patch_candidate(
        self,
        candidate: dict[str, Any],
        *,
        parse_result: ProviderPayloadParseResult,
        request: PatchRequest,
        tool_registry: List["ToolSpec"],
    ) -> dict[str, Any]:
        candidate = dict(candidate)
        candidate.setdefault("task_id", request.task_id)
        candidate.setdefault("metadata", {})
        self._raise_on_syntax_issues(candidate_kind="patch", parse_result=parse_result)
        try:
            patch = PlanPatch.model_validate(candidate)
        except ValidationError as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="patch",
                failure_type="SCHEMA_INVALID",
                issues=self._build_schema_issues(exc),
                normalized_payload=candidate,
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc

        from src.agents.planner import _normalize_patch_input_contract_references

        patch = _normalize_patch_input_contract_references(
            patch,
            registry=tool_registry,
        )
        try:
            patched_plan = apply_patch(request.original_plan, patch)
            validation_task = self._build_validation_task(
                task_id=request.task_id,
                constraints=request.original_plan.constraints,
            )
            patched_plan = self._prepare_plan_for_validation(
                patched_plan,
                task=validation_task,
                tool_registry=tool_registry,
                materialize_inputs=False,
                constraints_override=request.original_plan.constraints,
            )
            validate_plan_executability(patched_plan, validation_task)
        except CandidateExecutionValidationError as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="patch",
                failure_type="EXECUTABILITY_INVALID",
                issues=[issue.as_dict() for issue in exc.issues],
                normalized_payload=patch.model_dump(mode="json"),
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc
        except Exception as exc:
            raise ProviderPayloadValidationError(
                candidate_kind="patch",
                failure_type="EXECUTABILITY_INVALID",
                issues=[
                    {
                        "code": "PATCH_APPLICATION_INVALID",
                        "path": "$.operations",
                        "message": str(exc),
                    }
                ],
                normalized_payload=patch.model_dump(mode="json"),
                parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
            ) from exc

        return patch.model_dump(mode="json")

    def _prepare_plan_for_validation(
        self,
        plan: Plan,
        *,
        task: ProteinDesignTask,
        tool_registry: List["ToolSpec"],
        materialize_inputs: bool,
        constraints_override: dict[str, Any] | None = None,
    ) -> Plan:
        from src.agents.planner import (
            _ensure_plan_tools_in_registry,
            _materialize_missing_plan_inputs,
            _normalize_plan_input_contract_references,
            _resolve_plan_tools,
        )

        constraints = constraints_override if isinstance(constraints_override, dict) else task.constraints
        prepared = _normalize_plan_input_contract_references(
            plan,
            registry=tool_registry,
        )
        prepared = _resolve_plan_tools(
            prepared,
            tool_registry,
            constraints,
        )
        if materialize_inputs:
            prepared = _materialize_missing_plan_inputs(
                prepared,
                tool_registry,
                task,
            )
        _ensure_plan_tools_in_registry(prepared, tool_registry)
        return prepared

    def _raise_on_syntax_issues(
        self,
        *,
        candidate_kind: str,
        parse_result: ProviderPayloadParseResult,
    ) -> None:
        if parse_result.is_compliant:
            return
        raise ProviderPayloadValidationError(
            candidate_kind=candidate_kind,
            failure_type="SYNTAX_INVALID",
            issues=[issue.as_dict() for issue in parse_result.issues],
            normalized_payload=parse_result.normalized_payload,
            parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
        )

    def _raise_on_skeleton_mismatch(
        self,
        *,
        plan: Plan,
        skeleton: PlanSkeleton,
        parse_result: ProviderPayloadParseResult,
    ) -> None:
        issues: list[dict[str, Any]] = []
        if len(plan.steps) != len(skeleton.steps):
            issues.append(
                {
                    "code": "PLAN_SKELETON_STEP_COUNT_MISMATCH",
                    "path": "$.steps",
                    "message": "final Plan must keep the same step count as PlanSkeleton",
                    "observed": len(plan.steps),
                    "repair_hint": "keep exactly the skeleton steps and fill only inputs",
                }
            )
        for index, skeleton_step in enumerate(skeleton.steps):
            if index >= len(plan.steps):
                break
            plan_step = plan.steps[index]
            if plan_step.id != skeleton_step.id:
                issues.append(
                    {
                        "code": "PLAN_SKELETON_STEP_ID_MISMATCH",
                        "path": f"$.steps[{index}].id",
                        "message": "final Plan step id must match PlanSkeleton",
                        "observed": plan_step.id,
                        "repair_hint": f"use {skeleton_step.id}",
                    }
                )
            if plan_step.tool != skeleton_step.tool:
                issues.append(
                    {
                        "code": "PLAN_SKELETON_TOOL_MISMATCH",
                        "path": f"$.steps[{index}].tool",
                        "message": "final Plan tool must match PlanSkeleton",
                        "observed": plan_step.tool,
                        "repair_hint": f"use {skeleton_step.tool}",
                    }
                )
        if not issues:
            return
        raise ProviderPayloadValidationError(
            candidate_kind="plan",
            failure_type="SCHEMA_INVALID",
            issues=issues,
            normalized_payload=plan.model_dump(mode="json"),
            parser_repairs=[repair.as_dict() for repair in parse_result.repairs],
        )

    def _uses_two_stage_plan(self) -> bool:
        return self.config.tool_strategy == _TWO_STAGE_PLAN_STRATEGY

    def _skeleton_summary(self, skeleton: PlanSkeleton) -> dict[str, Any]:
        return {
            "step_count": len(skeleton.steps),
            "steps": [
                {"id": step.id, "tool": step.tool}
                for step in skeleton.steps
            ],
        }

    def _build_repair_user_prompt(
        self,
        *,
        base_user_prompt: str,
        candidate_kind: str,
        tool_name: str,
        error: ProviderPayloadValidationError,
    ) -> str:
        issue_lines = []
        for index, issue in enumerate(error.issues[:8], start=1):
            line = f"{index}. {issue.get('path', '$')}: {issue.get('message', error.failure_type)}"
            observed = issue.get("observed")
            if observed is not None:
                line += f" | observed={json.dumps(observed, ensure_ascii=False)}"
            repair_hint = issue.get("repair_hint")
            if isinstance(repair_hint, str) and repair_hint:
                line += f" | fix={repair_hint}"
            issue_lines.append(line)

        return (
            f"{base_user_prompt}\n\n"
            "上一次输出未通过 provider 校验，请仅修复结构、字段和引用表达，"
            "不要改变任务意图，不要新增未请求步骤，不要填造假的执行结果。\n"
            f"目标工具调用: {tool_name}\n"
            f"候选类型: {candidate_kind}\n"
            f"失败分类: {error.failure_type}\n"
            f"修复轮次: {error.attempts}\n"
            "错误摘要:\n"
            + "\n".join(f"- {line}" for line in issue_lines)
            + "\n必须遵守:\n"
            "- 只输出一次对应工具调用\n"
            "- steps / operations 必须是真正的 JSON array，不能是字符串\n"
            "- 跨步引用只能使用 S<n>.field\n"
            "- 禁止 ${...}、$...、<...>、auto、裸 token（如 CANDIDATES）\n"
            "- 若是 patch，replace_step 必须保持 target id 不变\n"
        )

    def _build_schema_issues(self, exc: ValidationError) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for error in exc.errors():
            loc = error.get("loc") or ()
            path = "$"
            if isinstance(loc, tuple):
                segments: list[str] = ["$"]
                for item in loc:
                    if isinstance(item, int):
                        segments[-1] = f"{segments[-1]}[{item}]"
                    else:
                        segments.append(str(item))
                path = ".".join(segments)
            issues.append(
                {
                    "code": "SCHEMA_FIELD_INVALID",
                    "path": path,
                    "message": error.get("msg", "schema validation failed"),
                    "observed": error.get("input"),
                }
            )
        return issues

    def _build_validation_task(
        self,
        *,
        task_id: str,
        constraints: dict[str, Any] | None,
    ) -> ProteinDesignTask:
        return ProteinDesignTask(
            task_id=task_id,
            goal="provider_validation_probe",
            constraints=constraints or {},
            metadata={},
        )
