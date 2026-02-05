from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set

from src.kg.kg_client import ToolKGError, load_tool_kg
from src.llm.base_llm_provider import BaseProvider
from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanPatchOpType,
    PlanStep,
    ProteinDesignTask,
    ReplanRequest,
    StepResult,
)
from src.models.db import InternalStatus, TaskRecord, TERMINAL_INTERNAL_STATUSES
from src.workflow.context import WorkflowContext
from src.workflow.status import transition_task_status


@dataclass(frozen=True)
class ToolSpec:
    """简化版工具定义，模拟 ProteinToolKG 节点"""

    id: str
    capabilities: Sequence[str]
    inputs: Sequence[str]
    outputs: Sequence[str]
    cost: int = 1
    safety_level: int = 1


class PlannerAgent:
    """最小可用 PlannerAgent: 根据任务目标生成一个单步 Plan

    当前实现：支持可选的 LLM Provider 生成计划，或使用默认的单步计划
    默认工具注册表来自 ProteinToolKG（读取失败时回退到内置 dummy 列表）。
    """

    def __init__(
        self,
        tool_registry: Iterable[ToolSpec] | None = None,
        llm_provider: Optional[BaseProvider] = None,
    ) -> None:
        """初始化 PlannerAgent

        Args:
            tool_registry: 可用工具注册表，默认从 ProteinToolKG 读取
            llm_provider: 可选的 LLM Provider，用于生成计划
        """
        if tool_registry is None:
            tool_registry = _load_default_tool_registry()
        self._tool_registry: List[ToolSpec] = list(tool_registry)
        if not self._tool_registry:
            raise ValueError(
                "Tool registry is empty; ensure ProteinToolKG provides tools."
            )
        self._llm_provider = llm_provider

    def plan(self, task: ProteinDesignTask) -> Plan:
        """生成执行计划

        Args:
            task: 蛋白质设计任务

        Returns:
            Plan: 包含步骤列表的执行计划
        """
        # 如果未提供 Provider，回退到默认行为（向后兼容）
        if self._llm_provider is None:
            return self._default_plan(task)

        # 调用 LLM Provider 生成计划
        plan_dict = self._llm_provider.call_planner(
            task=task, tool_registry=self._tool_registry
        )

        # 验证并返回 Plan 对象
        plan = Plan.model_validate(plan_dict)
        plan = _resolve_plan_tools(
            plan,
            self._tool_registry,
            task.constraints,
        )
        _ensure_plan_tools_in_registry(plan, self._tool_registry)
        plan = _attach_kg_explanation(plan)
        return plan

    def _default_plan(self, task: ProteinDesignTask) -> Plan:
        """向后兼容的默认单步计划

        生成一个单步骤计划，调用第一个可用工具（或 dummy_tool）
        保持与原始 PlannerAgent 行为一致
        """
        if _is_de_novo_task(task):
            plan = _build_de_novo_plan(task, self._tool_registry)
            return _attach_kg_explanation(plan)
        if not self._tool_registry:
            raise ValueError("Tool registry is empty; cannot build default plan.")
        tool_id = self._tool_registry[0].id

        # 从任务约束中提取 sequence，或使用默认值
        sequence = task.constraints.get(
            "sequence", "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR"
        )

        # 构建单步计划
        step = PlanStep(
            id="S1",
            tool=tool_id,
            inputs={"sequence": sequence},
            metadata={},
        )

        plan = Plan(
            task_id=task.task_id,
            steps=[step],
            constraints=task.constraints,
            metadata={},
        )
        return _attach_kg_explanation(plan)

    def plan_with_status(
        self,
        task: ProteinDesignTask,
        context: WorkflowContext,
        *,
        record: TaskRecord | None = None,
    ) -> Plan:
        """生成 Plan 并驱动 PLANNING → PLANNED 状态变更。"""
        transition_task_status(
            context,
            record,
            InternalStatus.PLANNING,
            reason="task_created",
        )
        try:
            plan = self.plan(task)
        except Exception:
            self._mark_failed(context, record, reason="planning_failed")
            raise

        context.plan = plan
        if record is not None:
            record.plan = plan

        transition_task_status(
            context,
            record,
            InternalStatus.PLANNED,
            reason="plan_generated",
        )
        return plan

    # --- B3: 局部 Patch ---
    def patch(self, request: PatchRequest) -> PlanPatch:
        """基于 PatchRequest 生成最小 replace_step PlanPatch

        策略（最小可用版）：
        1. 锁定最近失败的 step 作为 target
        2. 读取 target 对应的工具能力与输入需求
        3. 在 registry 中筛选能力相同、输入可满足、成本/安全更优的候选
        4. 选最优候选生成 replace_step PlanPatch，保持 step.id 不变
        """
        _ensure_task_match(request)
        target_step = _locate_target_step(request)
        target_spec = _find_tool_spec(self._tool_registry, target_step.tool)

        available_inputs = _collect_available_inputs(
            request.context_step_results, target_step
        )
        candidate = _select_candidate(
            registry=self._tool_registry,
            capability=target_spec.capabilities[0] if target_spec.capabilities else "",
            available_inputs=available_inputs,
            exclude_tool=target_step.tool,
        )

        patched_step = target_step.model_copy(
            update={
                "tool": candidate.id,
                # 追加简单元数据，便于调试
                "metadata": {
                    **(target_step.metadata or {}),
                    "patched_from": target_step.tool,
                },
            },
            deep=True,
        )
        op = PlanPatchOp(
            op="replace_step",
            target=target_step.id,
            step=patched_step,
        )
        patch = PlanPatch(
            task_id=request.task_id,
            operations=[op],
            metadata={"strategy": "cost_first"},
        )
        patch.metadata["kg_explanation"] = _build_kg_explanation_for_steps(
            [patched_step]
        )
        return patch

    # --- B4: 再规划 ---
    def replan(self, request: ReplanRequest) -> Plan:
        """基于 ReplanRequest 生成最小再规划 Plan（替换失败步骤）"""
        _ensure_replan_task_match(request)
        if not request.original_plan.steps:
            raise ValueError("Original plan is empty, cannot replan")

        target_step = _locate_replan_target_step(request)
        target_spec = _find_tool_spec(self._tool_registry, target_step.tool)
        available_inputs = _collect_available_inputs([], target_step)
        try:
            candidate = _select_candidate(
                registry=self._tool_registry,
                capability=target_spec.capabilities[0]
                if target_spec.capabilities
                else "",
                available_inputs=available_inputs,
                exclude_tool=target_step.tool,
            )
        except ValueError:
            fallback_inputs = _collect_registry_inputs(self._tool_registry)
            candidate = _select_candidate(
                registry=self._tool_registry,
                capability=target_spec.capabilities[0]
                if target_spec.capabilities
                else "",
                available_inputs=fallback_inputs,
                exclude_tool=target_step.tool,
            )
        replanned_step = target_step.model_copy(
            update={
                "tool": candidate.id,
                "metadata": {
                    **(target_step.metadata or {}),
                    "replanned_from": target_step.tool,
                },
            },
            deep=True,
        )

        new_steps = [step.model_copy(deep=True) for step in request.original_plan.steps]
        for idx, step in enumerate(new_steps):
            if step.id == target_step.id:
                new_steps[idx] = replanned_step
                break

        replanned = Plan(
            task_id=request.task_id,
            steps=new_steps,
            constraints=request.original_plan.constraints,
            metadata={"strategy": "replace_failed_step", "reason": request.reason},
        )
        return _attach_kg_explanation(replanned)

    def _mark_failed(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        *,
        reason: str,
    ) -> None:
        if context.status in TERMINAL_INTERNAL_STATUSES:
            return
        transition_task_status(
            context,
            record,
            InternalStatus.FAILED,
            reason=reason,
        )


# --- helpers ---


def _ensure_task_match(request: PatchRequest) -> None:
    if request.task_id != request.original_plan.task_id:
        raise ValueError(
            f"PatchRequest.task_id ({request.task_id}) does not match Plan.task_id ({request.original_plan.task_id})"
        )


def _ensure_replan_task_match(request: ReplanRequest) -> None:
    if request.task_id != request.original_plan.task_id:
        raise ValueError(
            f"ReplanRequest.task_id ({request.task_id}) does not match Plan.task_id ({request.original_plan.task_id})"
        )


def _locate_target_step(request: PatchRequest) -> PlanStep:
    failed_ids = [
        r.step_id for r in request.context_step_results if r.status == "failed"
    ]
    target_id = failed_ids[-1] if failed_ids else request.original_plan.steps[-1].id
    for step in request.original_plan.steps:
        if step.id == target_id:
            return step
    raise ValueError(f"Target step '{target_id}' not found in original plan")


def _locate_replan_target_step(request: ReplanRequest) -> PlanStep:
    target_id = (
        request.failed_steps[-1]
        if request.failed_steps
        else request.original_plan.steps[-1].id
    )
    for step in request.original_plan.steps:
        if step.id == target_id:
            return step
    raise ValueError(f"Target step '{target_id}' not found in original plan")


def _find_tool_spec(registry: Sequence[ToolSpec], tool_id: str) -> ToolSpec:
    for spec in registry:
        if spec.id == tool_id:
            return spec
    raise ValueError(f"Tool '{tool_id}' not found in registry")


def _collect_registry_inputs(registry: Sequence[ToolSpec]) -> Set[str]:
    inputs: Set[str] = set()
    for spec in registry:
        inputs.update(spec.inputs)
    return inputs


def _collect_available_inputs(
    results: Sequence[StepResult], target_step: PlanStep
) -> Set[str]:
    available: Set[str] = set()
    for r in results:
        available.update(r.outputs.keys())

    # 解析 target_step 的输入引用/字面量，估计需要的字段
    for val in target_step.inputs.values():
        if isinstance(val, str) and "." in val:
            _, field = val.split(".", 1)
            available.add(field)
        elif isinstance(val, str):
            available.add(val)
        else:
            # 字面量键也可视为可用
            pass
    # 键名本身代表用户提供的输入
    available.update(target_step.inputs.keys())
    return available


def _select_candidate(
    registry: Sequence[ToolSpec],
    capability: str,
    available_inputs: Set[str],
    exclude_tool: str,
) -> ToolSpec:
    candidates: List[ToolSpec] = []
    for spec in registry:
        if spec.id == exclude_tool:
            continue
        if capability and capability not in spec.capabilities:
            continue
        if not set(spec.inputs).issubset(available_inputs):
            continue
        candidates.append(spec)

    if not candidates:
        raise ValueError(
            f"No alternative tool found for capability '{capability}' with inputs {sorted(available_inputs)}"
        )

    # 简化策略：按 cost 优先，其次 safety_level
    candidates.sort(key=lambda t: (t.cost, t.safety_level, t.id))
    return candidates[0]


def _load_tool_specs_from_kg() -> Sequence[ToolSpec]:
    kg = load_tool_kg()
    tools = kg.get("tools", [])
    if not isinstance(tools, list):
        raise ToolKGError("ProteinToolKG 'tools' must be a list")

    specs: List[ToolSpec] = []
    for tool in tools:
        tool_id = tool.get("id")
        io_spec = tool.get("io", {})
        inputs = tuple(io_spec.get("inputs", {}).keys())
        outputs = tuple(io_spec.get("outputs", {}).keys())
        if not tool_id or not inputs or not outputs:
            continue
        specs.append(
            ToolSpec(
                id=tool_id,
                capabilities=tuple(tool.get("capabilities", [])),
                inputs=inputs,
                outputs=outputs,
                cost=tool.get("cost_score", 1.0),
                safety_level=tool.get("safety_level", 1),
            )
        )
    if not specs:
        raise ToolKGError("ProteinToolKG contains no usable tools")
    return tuple(specs)


def _load_default_tool_registry() -> Sequence[ToolSpec]:
    return _load_tool_specs_from_kg()


def _ensure_plan_tools_in_registry(plan: Plan, registry: Sequence[ToolSpec]) -> None:
    registry_ids = {spec.id for spec in registry}
    missing = {step.tool for step in plan.steps if step.tool not in registry_ids}
    if missing:
        raise ValueError(
            f"Plan references tools not registered in ProteinToolKG: {sorted(missing)}"
        )


def _attach_kg_explanation(plan: Plan) -> Plan:
    explanation = _build_kg_explanation_for_steps(plan.steps)
    metadata = {**(plan.metadata or {})}
    metadata["kg_explanation"] = explanation
    return plan.model_copy(update={"metadata": metadata}, deep=True)


def _build_kg_explanation_for_steps(steps: Sequence[PlanStep]) -> dict:
    kg = load_tool_kg()
    tools = {tool.get("id"): tool for tool in kg.get("tools", []) if tool.get("id")}
    capabilities = {
        cap.get("capability_id"): cap
        for cap in kg.get("capabilities", [])
        if cap.get("capability_id")
    }
    io_types = {
        io_type.get("io_type_id"): io_type
        for io_type in kg.get("io_types", [])
        if io_type.get("io_type_id")
    }

    step_entries: List[dict] = []
    for step in steps:
        tool = tools.get(step.tool)
        if tool is None:
            raise ValueError(
                f"Tool '{step.tool}' not found in ProteinToolKG for explanation"
            )
        capability_entries: List[dict] = []
        for cap_id in tool.get("capabilities", []):
            cap = capabilities.get(cap_id, {})
            capability_entries.append(
                {
                    "capability_id": cap_id,
                    "name": cap.get("name"),
                    "domain": cap.get("domain"),
                }
            )
        io_type_id = tool.get("io", {}).get("io_type_id")
        io_type = io_types.get(io_type_id, {})
        step_entries.append(
            {
                "step_id": step.id,
                "tool_id": step.tool,
                "capabilities": capability_entries,
                "io_type": {
                    "io_type_id": io_type_id,
                    "input_types": io_type.get("input_types", []),
                    "output_types": io_type.get("output_types", []),
                    "combinable": io_type.get("combinable"),
                },
                "constraints": tool.get("constraints", {}),
            }
        )
    return {"steps": step_entries}


def _resolve_plan_tools(
    plan: Plan,
    registry: Sequence[ToolSpec],
    task_constraints: dict,
) -> Plan:
    registry_map = {spec.id: spec for spec in registry}
    available_inputs: Set[str] = set(task_constraints.keys())
    safety_level = task_constraints.get("safety_level")
    prefer_remote = _prefers_remote_tools(task_constraints)
    capability_index = _load_capability_index()
    resolved_steps: List[PlanStep] = []

    for step in plan.steps:
        if step.tool not in registry_map:
            capability = _extract_step_capability(step.metadata)
            if not capability:
                raise ValueError(
                    f"Plan step '{step.id}' references unknown tool "
                    f"'{step.tool}' without capability metadata"
                )
            capability_id = _resolve_capability_id(capability, capability_index)
            if not capability_id:
                raise ValueError(
                    f"Plan step '{step.id}' provides unknown capability "
                    f"'{capability}' not found in ProteinToolKG"
                )
            candidate = _select_tool_by_capability(
                registry=registry,
                capability=capability_id,
                available_inputs=available_inputs,
                safety_level=safety_level,
                io_hint=step.metadata.get("io_hint") if step.metadata else None,
                prefer_remote=prefer_remote,
            )
            new_metadata = {**(step.metadata or {})}
            new_metadata.update(
                {
                    "resolved_from": step.tool,
                    "resolved_capability": capability_id,
                    "resolution_strategy": "kg_capability",
                }
            )
            step = step.model_copy(
                update={
                    "tool": candidate.id,
                    "metadata": new_metadata,
                },
                deep=True,
            )

        resolved_steps.append(step)
        spec = registry_map.get(step.tool)
        if spec:
            available_inputs.update(spec.outputs)

    return plan.model_copy(update={"steps": resolved_steps}, deep=True)


def _extract_step_capability(metadata: dict | None) -> str:
    if not metadata:
        return ""
    capability = metadata.get("capability")
    if isinstance(capability, str) and capability:
        return capability
    capabilities = metadata.get("capabilities")
    if isinstance(capabilities, list) and capabilities:
        first = capabilities[0]
        if isinstance(first, str):
            return first
    return ""


def _select_tool_by_capability(
    registry: Sequence[ToolSpec],
    capability: str,
    available_inputs: Set[str],
    safety_level: int | None,
    io_hint: dict | None,
    prefer_remote: bool,
) -> ToolSpec:
    hint_inputs: Set[str] = set()
    if isinstance(io_hint, dict):
        inputs = io_hint.get("inputs")
        if isinstance(inputs, list):
            hint_inputs = {val for val in inputs if isinstance(val, str)}

    candidates: List[ToolSpec] = []
    for spec in registry:
        if capability not in spec.capabilities:
            continue
        if safety_level is not None and spec.safety_level > safety_level:
            continue
        if not set(spec.inputs).issubset(available_inputs):
            continue
        if hint_inputs and not hint_inputs.issubset(available_inputs):
            continue
        candidates.append(spec)

    if not candidates:
        raise ValueError(
            f"No KG tool found for capability '{capability}' "
            f"with inputs {sorted(available_inputs)}"
        )

    candidates.sort(
        key=lambda t: (
            _remote_rank(t.id, prefer_remote),
            t.cost,
            t.safety_level,
            t.id,
        )
    )
    return candidates[0]


def _prefers_remote_tools(task_constraints: dict) -> bool:
    return bool(
        task_constraints.get("prefer_remote")
        or task_constraints.get("prefer_nim")
        or task_constraints.get("use_remote_tools")
        or task_constraints.get("use_nim")
    )


_DE_NOVO_GOAL_TYPE = "de_novo_design"


def _extract_goal_type(task: ProteinDesignTask) -> str:
    for container in (task.constraints, task.metadata):
        if isinstance(container, dict):
            goal_block = container.get("goal")
            if isinstance(goal_block, dict):
                goal_type = goal_block.get("type")
                if isinstance(goal_type, str) and goal_type:
                    return goal_type
            goal_type = container.get("goal_type")
            if isinstance(goal_type, str) and goal_type:
                return goal_type

    goal_value = task.goal
    if isinstance(goal_value, str):
        stripped = goal_value.strip()
        if stripped == _DE_NOVO_GOAL_TYPE:
            return stripped
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return ""
            if isinstance(parsed, dict):
                goal_type = parsed.get("type")
                if isinstance(goal_type, str) and goal_type:
                    return goal_type
    return ""


def _is_de_novo_task(task: ProteinDesignTask) -> bool:
    return _extract_goal_type(task) == _DE_NOVO_GOAL_TYPE


def _extract_length_range(constraints: dict) -> List[int] | None:
    value = constraints.get("length_range")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return [int(value[0]), int(value[1])]
        except (TypeError, ValueError):
            return None

    value = constraints.get("length")
    if isinstance(value, (int, float)):
        length = int(value)
        if length > 0:
            return [length, length]
    return None


def _extract_template_pdb(constraints: dict) -> str | None:
    for key in ("structure_template_pdb", "pdb_path"):
        value = constraints.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _build_de_novo_plan(
    task: ProteinDesignTask,
    registry: Sequence[ToolSpec],
) -> Plan:
    constraints = task.constraints or {}
    available_inputs: Set[str] = set(constraints.keys())
    template_pdb = _extract_template_pdb(constraints)
    if template_pdb:
        available_inputs.add("pdb_path")

    safety_level = constraints.get("safety_level")
    prefer_remote = _prefers_remote_tools(constraints)

    try:
        sequence_tool = _select_tool_by_capability(
            registry=registry,
            capability="sequence_design",
            available_inputs=available_inputs,
            safety_level=safety_level,
            io_hint=None,
            prefer_remote=prefer_remote,
        )
    except ValueError:
        fallback_inputs = _collect_registry_inputs(registry)
        sequence_tool = _select_tool_by_capability(
            registry=registry,
            capability="sequence_design",
            available_inputs=fallback_inputs,
            safety_level=safety_level,
            io_hint=None,
            prefer_remote=prefer_remote,
        )

    available_inputs.update(sequence_tool.outputs)

    try:
        structure_tool = _select_tool_by_capability(
            registry=registry,
            capability="structure_prediction",
            available_inputs=available_inputs,
            safety_level=safety_level,
            io_hint={"inputs": ["sequence"]},
            prefer_remote=prefer_remote,
        )
    except ValueError:
        fallback_inputs = _collect_registry_inputs(registry)
        structure_tool = _select_tool_by_capability(
            registry=registry,
            capability="structure_prediction",
            available_inputs=fallback_inputs,
            safety_level=safety_level,
            io_hint={"inputs": ["sequence"]},
            prefer_remote=prefer_remote,
        )

    step_inputs: dict = {
        "goal": task.goal,
    }
    length_range = _extract_length_range(constraints)
    if length_range:
        step_inputs["length_range"] = length_range
    if template_pdb:
        step_inputs["pdb_path"] = template_pdb

    steps = [
        PlanStep(
            id="S1",
            tool=sequence_tool.id,
            inputs=step_inputs,
            metadata={},
        ),
        PlanStep(
            id="S2",
            tool=structure_tool.id,
            inputs={"sequence": "S1.sequence"},
            metadata={},
        ),
    ]

    explanation = _build_de_novo_explanation(sequence_tool.id, structure_tool.id)

    return Plan(
        task_id=task.task_id,
        steps=steps,
        constraints=task.constraints,
        metadata={},
        explanation=explanation,
    )


def _build_de_novo_explanation(sequence_tool_id: str, structure_tool_id: str) -> str:
    kg = load_tool_kg()
    tools = {tool.get("id"): tool for tool in kg.get("tools", []) if tool.get("id")}
    capabilities = {
        cap.get("capability_id"): cap
        for cap in kg.get("capabilities", [])
        if cap.get("capability_id")
    }

    sequence_tool = tools.get(sequence_tool_id, {})
    structure_tool = tools.get(structure_tool_id, {})

    def format_caps(tool: dict) -> str:
        cap_ids = tool.get("capabilities", [])
        labels = []
        for cap_id in cap_ids:
            cap_entry = capabilities.get(cap_id, {})
            name = cap_entry.get("name")
            if name:
                labels.append(f"{cap_id}({name})")
            else:
                labels.append(str(cap_id))
        return ", ".join(labels) if labels else "unknown"

    seq_name = sequence_tool.get("name") or sequence_tool_id
    seq_desc = sequence_tool.get("description") or ""
    seq_caps = format_caps(sequence_tool)

    struct_name = structure_tool.get("name") or structure_tool_id
    struct_desc = structure_tool.get("description") or ""
    struct_caps = format_caps(structure_tool)

    compat_from = structure_tool.get("compat", {}).get("from", [])
    compat_note = ""
    if isinstance(compat_from, list) and compat_from:
        compat_note = f"KG compat.from={', '.join(str(item) for item in compat_from)}"

    parts = [
        "de_novo_design 任务采用序列设计→结构预测两步链路。",
        f"ProteinToolKG 显示 {seq_name}({sequence_tool_id}) 能力={seq_caps}。{seq_desc}",
        f"ProteinToolKG 显示 {struct_name}({structure_tool_id}) 能力={struct_caps}。{struct_desc}",
    ]
    if compat_note:
        parts.append(compat_note)
    return " ".join(part for part in parts if part)


def _remote_rank(tool_id: str, prefer_remote: bool) -> int:
    is_remote = tool_id.startswith("nim_")
    if prefer_remote:
        return 0 if is_remote else 1
    return 0 if not is_remote else 1


def _load_capability_index() -> List[dict]:
    try:
        kg = load_tool_kg()
    except ToolKGError:
        return []
    capabilities = kg.get("capabilities", [])
    if isinstance(capabilities, list):
        return capabilities
    return []


def _normalize_text(value: str) -> List[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in value)
    return [token for token in normalized.split() if token]


def _resolve_capability_id(capability: str, index: List[dict]) -> str:
    if not capability:
        return ""
    normalized_tokens = set(_normalize_text(capability))
    for entry in index:
        cap_id = entry.get("capability_id")
        if not isinstance(cap_id, str) or not cap_id:
            continue
        if capability == cap_id:
            return cap_id
        id_tokens = set(_normalize_text(cap_id))
        name_tokens = set(_normalize_text(entry.get("name", "")))
        if id_tokens and id_tokens.issubset(normalized_tokens):
            return cap_id
        if name_tokens and name_tokens.issubset(normalized_tokens):
            return cap_id
    return ""
