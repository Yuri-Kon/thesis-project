from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set

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
    
    当前实现：固定生成一个单步计划，调用 dummy_tool
    后续将接入 KG 和 LLM 实现智能规划
    """

    def __init__(self, tool_registry: Iterable[ToolSpec] | None = None) -> None:
        # 允许注入自定义 registry，便于测试；默认使用内置 dummy 列表
        self._tool_registry: List[ToolSpec] = list(tool_registry or _DEFAULT_TOOL_REGISTRY)

    def plan(self, task: ProteinDesignTask) -> Plan:
        """生成执行计划
        
        Args:
            task: 蛋白质设计任务
            
        Returns:
            Plan: 包含步骤列表的执行计划
        """
        # 最小版: 固定生成一个叫 S1 的步骤，调用 dummy_tool
        # 后续会被真实工具替代
        step = PlanStep(
            id="S1",
            tool="dummy_tool",
            inputs={
                "sequence": task.constraints.get(
                    "sequence",
                    "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR",
                )
            },
            metadata={},
        )

        return Plan(
            task_id=task.task_id,
            steps=[step],
            constraints=task.constraints,
            metadata={},
        )

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

        available_inputs = _collect_available_inputs(request.context_step_results, target_step)
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
                "metadata": {**(target_step.metadata or {}), "patched_from": target_step.tool},
            },
            deep=True,
        )
        op = PlanPatchOp(
            op="replace_step",
            target=target_step.id,
            step=patched_step,
        )
        return PlanPatch(task_id=request.task_id, operations=[op], metadata={"strategy": "cost_first"})

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
                capability=target_spec.capabilities[0] if target_spec.capabilities else "",
                available_inputs=available_inputs,
                exclude_tool=target_step.tool,
            )
        except ValueError:
            fallback_inputs = _collect_registry_inputs(self._tool_registry)
            candidate = _select_candidate(
                registry=self._tool_registry,
                capability=target_spec.capabilities[0] if target_spec.capabilities else "",
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

        return Plan(
            task_id=request.task_id,
            steps=new_steps,
            constraints=request.original_plan.constraints,
            metadata={"strategy": "replace_failed_step", "reason": request.reason},
        )

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
    target_id = request.failed_steps[-1] if request.failed_steps else request.original_plan.steps[-1].id
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


def _collect_available_inputs(results: Sequence[StepResult], target_step: PlanStep) -> Set[str]:
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
        raise ValueError(f"No alternative tool found for capability '{capability}' with inputs {sorted(available_inputs)}")

    # 简化策略：按 cost 优先，其次 safety_level
    candidates.sort(key=lambda t: (t.cost, t.safety_level, t.id))
    return candidates[0]


# 默认工具注册表（可替换为 KG 查询）
_DEFAULT_TOOL_REGISTRY: Sequence[ToolSpec] = (
    ToolSpec(
        id="dummy_tool",
        capabilities=("design",),
        inputs=("sequence",),
        outputs=("dummy_output", "sequence"),
        cost=5,
        safety_level=2,
    ),
    ToolSpec(
        id="dummy_tool_alt",
        capabilities=("design",),
        inputs=("sequence",),
        outputs=("dummy_output", "sequence"),
        cost=2,
        safety_level=1,
    ),
    ToolSpec(
        id="dummy_tool_safe",
        capabilities=("design",),
        inputs=("sequence",),
        outputs=("dummy_output", "sequence"),
        cost=3,
        safety_level=0,
    ),
)
