from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional, Sequence, Set, Tuple

from src.kg.kg_client import ToolKGError, load_tool_kg
from src.llm.base_llm_provider import BaseProvider
from src.models.contracts import (
    PatchRequest,
    PendingActionType,
    PendingActionCandidate,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanPatchOpType,
    PlanStep,
    ProteinDesignTask,
    ReplanRequest,
    StepResult,
)
from src.models.validation import validate_candidate_set_output
from src.models.db import InternalStatus, TaskRecord, TERMINAL_INTERNAL_STATUSES
from src.workflow.context import WorkflowContext
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.workflow.status import transition_task_status


@dataclass(frozen=True)
class ToolSpec:
    """简化版工具定义，模拟 ProteinToolKG 节点"""

    id: str
    capabilities: Sequence[str]
    inputs: Sequence[str]
    outputs: Sequence[str]
    cost: float = 1
    safety_level: int = 1
    io_type: str | None = None
    adapter_mode: Literal["local", "remote", "mock", "hybrid", "unknown"] = "unknown"
    priority: str | None = None


@dataclass(frozen=True)
class TopKResult:
    """Planner Top-K 候选输出（CandidateSetOutput v1 对齐）。"""

    candidates: List[PendingActionCandidate]
    default_recommendation: str | None
    explanation: str


@dataclass(frozen=True)
class CandidateGateDecision:
    """候选门控决策结果。"""

    requires_hitl: bool
    reason: str
    selected_candidate_id: str | None
    confidence: float
    overall: float


@dataclass(frozen=True)
class _CandidatePayload:
    payload: Plan | PlanPatch
    primary_tool_id: str
    capability_bucket: str
    note: str


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

    def plan_top_k(self, task: ProteinDesignTask, *, k: int = 3) -> TopKResult:
        """生成 Plan Top-K 候选（默认 K=3）。"""
        base_plan = self.plan(task)
        payloads = _build_plan_candidate_payloads(
            task=task,
            base_plan=base_plan,
            registry=self._tool_registry,
            top_k=_normalize_top_k(k),
        )
        return _build_top_k_result(
            payloads=payloads,
            registry=self._tool_registry,
            candidate_kind="plan",
            top_k=_normalize_top_k(k),
        )

    def patch_top_k(self, request: PatchRequest, *, k: int = 3) -> TopKResult:
        """生成 Patch Top-K 候选（统一 CandidateSetOutput v1 字段）。"""
        _ensure_task_match(request)
        payloads = _build_patch_candidate_payloads(
            request=request,
            registry=self._tool_registry,
            top_k=_normalize_top_k(k),
        )
        return _build_top_k_result(
            payloads=payloads,
            registry=self._tool_registry,
            candidate_kind="patch",
            top_k=_normalize_top_k(k),
        )

    def replan_top_k(self, request: ReplanRequest, *, k: int = 3) -> TopKResult:
        """生成 Replan Top-K 候选（统一 CandidateSetOutput v1 字段）。"""
        _ensure_replan_task_match(request)
        payloads = _build_replan_candidate_payloads(
            request=request,
            registry=self._tool_registry,
            top_k=_normalize_top_k(k),
        )
        return _build_top_k_result(
            payloads=payloads,
            registry=self._tool_registry,
            candidate_kind="replan",
            top_k=_normalize_top_k(k),
        )

    def evaluate_top_k_gate(
        self,
        *,
        candidate_kind: Literal["plan", "patch", "replan"],
        top_k_result: TopKResult,
        task_constraints: dict,
    ) -> CandidateGateDecision:
        """根据 score/risk/cost 阈值判断是否进入 WAITING_*。"""
        return _evaluate_top_k_gate(
            candidate_kind=candidate_kind,
            top_k_result=top_k_result,
            task_constraints=task_constraints,
        )

    def score_candidate_payload(self, payload: Plan | PlanPatch) -> dict[str, float]:
        """对单个候选 payload 打分（用于调试/测试）。"""
        return _score_payload(payload, self._tool_registry)

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
        """生成 Plan 并驱动 PLANNING → PLANNED/WAITING_PLAN_CONFIRM 状态变更。"""
        transition_task_status(
            context,
            record,
            InternalStatus.PLANNING,
            reason="task_created",
        )
        try:
            top_k_value = _resolve_top_k_value(
                task.constraints,
                key="plan_top_k",
                default=3,
            )
            top_k = self.plan_top_k(task, k=top_k_value)
            gate = self.evaluate_top_k_gate(
                candidate_kind="plan",
                top_k_result=top_k,
                task_constraints=task.constraints,
            )
            candidate = _require_default_candidate(top_k, expected_kind="plan")
            payload = candidate.structured_payload
            if not isinstance(payload, Plan):
                raise ValueError("plan_top_k returned non-Plan payload")
            plan = payload
        except Exception:
            self._mark_failed(context, record, reason="planning_failed")
            raise

        context.plan = plan
        if record is not None:
            record.plan = plan

        if gate.requires_hitl:
            pending_action = build_pending_action(
                task_id=task.task_id,
                action_type=PendingActionType.PLAN_CONFIRM,
                candidates=top_k.candidates,
                default_suggestion=top_k.default_recommendation,
                default_recommendation=top_k.default_recommendation,
                explanation=f"{top_k.explanation} gate={gate.reason}",
            )
            validate_candidate_set_output(pending_action)
            enter_waiting_state(
                context,
                record,
                pending_action,
                InternalStatus.WAITING_PLAN_CONFIRM,
                reason=gate.reason,
            )
            transition_task_status(
                context,
                record,
                InternalStatus.WAITING_PLAN_CONFIRM,
                reason=gate.reason,
            )
            return plan

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
        top_k = self.patch_top_k(request, k=1)
        candidate = _require_default_candidate(top_k, expected_kind="patch")
        payload = candidate.structured_payload
        if not isinstance(payload, PlanPatch):
            raise ValueError("patch_top_k returned non-PlanPatch payload")
        return payload

    # --- B4: 再规划 ---
    def replan(self, request: ReplanRequest) -> Plan:
        """基于 ReplanRequest 生成最小再规划 Plan（替换失败步骤）"""
        top_k = self.replan_top_k(request, k=1)
        candidate = _require_default_candidate(top_k, expected_kind="replan")
        payload = candidate.structured_payload
        if not isinstance(payload, Plan):
            raise ValueError("replan_top_k returned non-Plan payload")
        return payload

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


_FORCE_CONFIRM_KEYS = {
    "plan": "require_plan_confirm",
    "patch": "require_patch_confirm",
    "replan": "require_replan_confirm",
}

_DEFAULT_FORCE_CONFIRM = {
    "plan": False,
    "patch": False,
    "replan": False,
}


def _resolve_top_k_value(
    constraints: dict,
    *,
    key: str,
    default: int,
) -> int:
    raw = constraints.get(key, default)
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return _normalize_top_k(parsed)


def _evaluate_top_k_gate(
    *,
    candidate_kind: Literal["plan", "patch", "replan"],
    top_k_result: TopKResult,
    task_constraints: dict,
) -> CandidateGateDecision:
    if not top_k_result.candidates:
        return CandidateGateDecision(
            requires_hitl=True,
            reason=f"{candidate_kind}_candidate_empty",
            selected_candidate_id=None,
            confidence=0.0,
            overall=0.0,
        )

    best = top_k_result.candidates[0]
    score = best.score_breakdown or {}
    overall = float(score.get("overall", 0.0))
    confidence = float(score.get("confidence", overall))
    risk_level = best.risk_level or "medium"
    cost_estimate = best.cost_estimate or "medium"

    key = _FORCE_CONFIRM_KEYS[candidate_kind]
    force_default = _DEFAULT_FORCE_CONFIRM[candidate_kind]
    force_confirm = bool(task_constraints.get(key, force_default))
    min_confidence = _safe_float(
        task_constraints.get("min_candidate_confidence"),
        default=0.0,
    )
    raw_high_cost_min_overall = task_constraints.get("high_cost_min_overall")
    high_cost_min_overall = (
        _safe_float(raw_high_cost_min_overall, default=0.75)
        if raw_high_cost_min_overall is not None
        else None
    )

    if force_confirm:
        return CandidateGateDecision(
            requires_hitl=True,
            reason=f"{candidate_kind}_confirm_required",
            selected_candidate_id=best.candidate_id,
            confidence=confidence,
            overall=overall,
        )
    if risk_level == "high":
        return CandidateGateDecision(
            requires_hitl=True,
            reason=f"{candidate_kind}_high_risk",
            selected_candidate_id=best.candidate_id,
            confidence=confidence,
            overall=overall,
        )
    if confidence < min_confidence:
        return CandidateGateDecision(
            requires_hitl=True,
            reason=f"{candidate_kind}_low_confidence",
            selected_candidate_id=best.candidate_id,
            confidence=confidence,
            overall=overall,
        )
    if (
        cost_estimate == "high"
        and high_cost_min_overall is not None
        and overall < high_cost_min_overall
    ):
        return CandidateGateDecision(
            requires_hitl=True,
            reason=f"{candidate_kind}_high_cost_low_benefit",
            selected_candidate_id=best.candidate_id,
            confidence=confidence,
            overall=overall,
        )

    return CandidateGateDecision(
        requires_hitl=False,
        reason=f"{candidate_kind}_auto_execute",
        selected_candidate_id=best.candidate_id,
        confidence=confidence,
        overall=overall,
    )


def _safe_float(value: object, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return parsed


def _normalize_top_k(value: int) -> int:
    if value <= 0:
        return 1
    return value


def _require_default_candidate(
    result: TopKResult,
    *,
    expected_kind: str,
) -> PendingActionCandidate:
    if not result.candidates or not result.default_recommendation:
        raise ValueError(f"{expected_kind}_top_k produced no candidates")
    for candidate in result.candidates:
        if candidate.candidate_id == result.default_recommendation:
            return candidate
    raise ValueError(
        f"{expected_kind}_top_k default recommendation "
        f"'{result.default_recommendation}' is missing from candidates"
    )


def _build_plan_candidate_payloads(
    *,
    task: ProteinDesignTask,
    base_plan: Plan,
    registry: Sequence[ToolSpec],
    top_k: int,
) -> List[_CandidatePayload]:
    if not base_plan.steps:
        raise ValueError("Plan is empty; cannot build Top-K candidates")

    registry_map = {spec.id: spec for spec in registry}
    payloads: List[_CandidatePayload] = [
        _CandidatePayload(
            payload=base_plan,
            primary_tool_id=base_plan.steps[0].tool,
            capability_bucket=(
                _resolve_step_capability(
                    base_plan.steps[0], registry_map.get(base_plan.steps[0].tool)
                )
                or "unknown"
            ),
            note="base",
        )
    ]

    available_inputs: Set[str] = set(task.constraints.keys())
    max_variants_per_step = max(1, top_k * 2)
    for idx, step in enumerate(base_plan.steps):
        step_inputs = set(available_inputs)
        step_spec = registry_map.get(step.tool)
        capability = _resolve_step_capability(step, step_spec)
        alternatives = _rank_candidate_tools(
            registry=registry,
            capability=capability,
            available_inputs=step_inputs,
            exclude_tool=step.tool,
        )
        for alternative in alternatives[:max_variants_per_step]:
            replaced_step = step.model_copy(
                update={
                    "tool": alternative.id,
                    "metadata": {
                        **(step.metadata or {}),
                        "candidate_from": step.tool,
                        "candidate_strategy": "tool_swap",
                    },
                },
                deep=True,
            )
            new_steps = [plan_step.model_copy(deep=True) for plan_step in base_plan.steps]
            new_steps[idx] = replaced_step
            candidate_plan = base_plan.model_copy(
                update={
                    "steps": new_steps,
                    "metadata": {
                        **(base_plan.metadata or {}),
                        "candidate_strategy": "top_k_plan",
                    },
                },
                deep=True,
            )
            candidate_plan = _attach_kg_explanation(candidate_plan)
            payloads.append(
                _CandidatePayload(
                    payload=candidate_plan,
                    primary_tool_id=alternative.id,
                    capability_bucket=_primary_capability(alternative),
                    note=f"step:{step.id}:{step.tool}->{alternative.id}",
                )
            )

        if step_spec:
            available_inputs.update(step_spec.outputs)

    return payloads


def _build_patch_candidate_payloads(
    *,
    request: PatchRequest,
    registry: Sequence[ToolSpec],
    top_k: int,
) -> List[_CandidatePayload]:
    target_step = _locate_target_step(request)
    target_spec = _find_tool_spec(registry, target_step.tool)
    capability = _primary_capability(target_spec)

    available_inputs = _collect_available_inputs(
        request.context_step_results, target_step
    )
    alternatives = _rank_candidate_tools(
        registry=registry,
        capability=capability,
        available_inputs=available_inputs,
        exclude_tool=target_step.tool,
    )
    if not alternatives:
        fallback_inputs = _collect_registry_inputs(registry)
        alternatives = _rank_candidate_tools(
            registry=registry,
            capability=capability,
            available_inputs=fallback_inputs,
            exclude_tool=target_step.tool,
        )
    if not alternatives:
        raise ValueError(
            f"No alternative tool found for capability '{capability}' "
            f"with inputs {sorted(available_inputs)}"
        )

    payloads: List[_CandidatePayload] = []
    max_candidates = max(1, top_k * 2)
    for alternative in alternatives[:max_candidates]:
        patched_step = target_step.model_copy(
            update={
                "tool": alternative.id,
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
        payloads.append(
            _CandidatePayload(
                payload=patch,
                primary_tool_id=alternative.id,
                capability_bucket=_primary_capability(alternative),
                note=f"target:{target_step.id}:{target_step.tool}->{alternative.id}",
            )
        )
    return payloads


def _build_replan_candidate_payloads(
    *,
    request: ReplanRequest,
    registry: Sequence[ToolSpec],
    top_k: int,
) -> List[_CandidatePayload]:
    if not request.original_plan.steps:
        raise ValueError("Original plan is empty, cannot replan")

    target_step = _locate_replan_target_step(request)
    target_spec = _find_tool_spec(registry, target_step.tool)
    capability = _primary_capability(target_spec)
    available_inputs = _collect_available_inputs([], target_step)

    alternatives = _rank_candidate_tools(
        registry=registry,
        capability=capability,
        available_inputs=available_inputs,
        exclude_tool=target_step.tool,
    )
    if not alternatives:
        fallback_inputs = _collect_registry_inputs(registry)
        alternatives = _rank_candidate_tools(
            registry=registry,
            capability=capability,
            available_inputs=fallback_inputs,
            exclude_tool=target_step.tool,
        )
    if not alternatives:
        raise ValueError(
            f"No alternative tool found for capability '{capability}' "
            f"with inputs {sorted(available_inputs)}"
        )

    target_index = next(
        idx for idx, step in enumerate(request.original_plan.steps) if step.id == target_step.id
    )
    prefix_index = target_index - 1

    payloads: List[_CandidatePayload] = []
    max_candidates = max(1, top_k * 2)
    for alternative in alternatives[:max_candidates]:
        replanned_step = target_step.model_copy(
            update={
                "tool": alternative.id,
                "metadata": {
                    **(target_step.metadata or {}),
                    "replanned_from": target_step.tool,
                },
            },
            deep=True,
        )
        new_steps = [step.model_copy(deep=True) for step in request.original_plan.steps]
        new_steps[target_index] = replanned_step
        replanned = Plan(
            task_id=request.task_id,
            steps=new_steps,
            constraints=request.original_plan.constraints,
            metadata={
                "strategy": "replace_failed_step",
                "reason": request.reason,
                "replan_mode": "suffix_replan",
                "preserve_prefix_until_step_index": prefix_index,
            },
        )
        payloads.append(
            _CandidatePayload(
                payload=_attach_kg_explanation(replanned),
                primary_tool_id=alternative.id,
                capability_bucket=_primary_capability(alternative),
                note=f"target:{target_step.id}:{target_step.tool}->{alternative.id}",
            )
        )
    return payloads


def _build_top_k_result(
    *,
    payloads: Sequence[_CandidatePayload],
    registry: Sequence[ToolSpec],
    candidate_kind: str,
    top_k: int,
) -> TopKResult:
    if not payloads:
        raise ValueError(f"No payload candidates generated for {candidate_kind}")

    registry_map = {spec.id: spec for spec in registry}
    unique_payloads: List[_CandidatePayload] = []
    seen_fingerprints: Set[str] = set()
    for payload in payloads:
        fingerprint = _canonical_payload_fingerprint(
            payload.payload,
            payload.primary_tool_id,
            payload.capability_bucket,
        )
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        unique_payloads.append(payload)

    ranked_rows: List[Tuple[PendingActionCandidate, Tuple, str]] = []
    for payload in unique_payloads:
        score_breakdown = _score_payload(payload.payload, registry)
        primary_tool = registry_map.get(payload.primary_tool_id)
        capability_id = payload.capability_bucket or _primary_capability(primary_tool)
        tool_id = payload.primary_tool_id
        io_type = primary_tool.io_type if primary_tool and primary_tool.io_type else "unknown"
        adapter_mode = primary_tool.adapter_mode if primary_tool else "unknown"
        cost_estimate = _derive_cost_estimate(payload.payload, registry)
        risk_level = _derive_risk_level(payload.payload, registry)
        candidate_id = _stable_candidate_id(
            candidate_kind,
            payload.payload,
            payload.primary_tool_id,
            payload.capability_bucket,
        )
        metadata = {
            "candidate_kind": candidate_kind,
            "capability_bucket": capability_id,
            "tool_id": tool_id,
            "capability_id": capability_id,
            "io_type": io_type,
            "adapter_mode": adapter_mode,
            "generation_note": payload.note,
        }
        candidate = PendingActionCandidate(
            candidate_id=candidate_id,
            structured_payload=payload.payload,
            score_breakdown=score_breakdown,
            risk_level=risk_level,
            cost_estimate=cost_estimate,
            explanation=(
                f"{candidate_kind} candidate with primary tool "
                f"{tool_id} in capability bucket {capability_id}."
            ),
            summary=_build_candidate_summary(payload.payload),
            tool_id=tool_id,
            capability_id=capability_id,
            io_type=io_type,
            adapter_mode=adapter_mode,
            metadata=metadata,
        )
        priority_rank = _priority_rank(primary_tool.priority if primary_tool else None)
        sort_key = (
            -score_breakdown["overall"],
            priority_rank,
            capability_id,
            tool_id,
            candidate_id,
        )
        ranked_rows.append((candidate, sort_key, capability_id))

    ranked_rows.sort(key=lambda row: row[1])
    selected_rows = _select_diverse_top_k(
        ranked_rows=ranked_rows,
        top_k=top_k,
    )
    candidates = [row[0] for row in selected_rows]
    default_recommendation = candidates[0].candidate_id if candidates else None
    explanation = (
        f"{candidate_kind} Top-K generated with deterministic sort "
        f"(requested={top_k}, returned={len(candidates)}). "
        "Ranking uses overall score desc + stable tie-break; "
        "selection uses capability-bucket round-robin."
    )
    if len(candidates) < top_k:
        explanation = (
            f"{explanation} Degraded to available candidates because "
            "registry constraints did not produce enough unique options."
        )
    return TopKResult(
        candidates=candidates,
        default_recommendation=default_recommendation,
        explanation=explanation,
    )


def _select_diverse_top_k(
    *,
    ranked_rows: Sequence[Tuple[PendingActionCandidate, Tuple, str]],
    top_k: int,
) -> List[Tuple[PendingActionCandidate, Tuple, str]]:
    bucket_rows: dict[str, List[Tuple[PendingActionCandidate, Tuple, str]]] = {}
    bucket_order: List[str] = []
    for row in ranked_rows:
        bucket = row[2] or "unknown"
        if bucket not in bucket_rows:
            bucket_rows[bucket] = []
            bucket_order.append(bucket)
        bucket_rows[bucket].append(row)

    selected: List[Tuple[PendingActionCandidate, Tuple, str]] = []
    while len(selected) < top_k:
        progressed = False
        for bucket in bucket_order:
            rows = bucket_rows[bucket]
            if not rows:
                continue
            selected.append(rows.pop(0))
            progressed = True
            if len(selected) >= top_k:
                break
        if not progressed:
            break
    return selected


def _build_candidate_summary(payload: Plan | PlanPatch) -> str:
    if isinstance(payload, Plan):
        tools = [step.tool for step in payload.steps]
        return f"plan_steps={len(payload.steps)} tools={','.join(tools)}"
    ops = [op.op for op in payload.operations]
    return f"patch_ops={len(payload.operations)} ops={','.join(ops)}"


def _score_payload(payload: Plan | PlanPatch, registry: Sequence[ToolSpec]) -> dict[str, float]:
    registry_map = {spec.id: spec for spec in registry}
    tool_ids = _extract_payload_tool_ids(payload)
    risk_scores: List[float] = []
    cost_scores: List[float] = []
    readiness_scores: List[float] = []
    capabilities: Set[str] = set()
    objective_bonus = 0.0
    for tool_id in tool_ids:
        spec = registry_map.get(tool_id)
        if spec is None:
            continue
        tool_risk, tool_cost = _tool_risk_cost_score(spec)
        risk_scores.append(tool_risk)
        cost_scores.append(tool_cost)
        readiness_scores.append(_tool_readiness_score(spec))
        capabilities.update(spec.capabilities)
        if "objective_scoring" in spec.capabilities or spec.id == "objective_ranker":
            objective_bonus = max(objective_bonus, 0.08)

    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.55
    avg_cost = sum(cost_scores) / len(cost_scores) if cost_scores else 0.55
    tool_readiness = (
        sum(readiness_scores) / len(readiness_scores) if readiness_scores else 0.5
    )
    tool_coverage = _tool_coverage_score(tool_ids, capabilities)
    fallback_depth = _fallback_depth_score(tool_ids, registry_map, registry)

    feasibility = min(1.0, max(0.0, 0.5 + 0.25 * tool_coverage + 0.25 * fallback_depth))
    objective = min(
        1.0,
        max(0.0, 1.0 - avg_cost * 0.3 + objective_bonus),
    )
    risk = max(0.0, 1.0 - avg_risk)
    cost = max(0.0, 1.0 - avg_cost)
    confidence = min(
        1.0,
        max(
            0.0,
            0.35 * feasibility
            + 0.25 * tool_readiness
            + 0.2 * tool_coverage
            + 0.2 * fallback_depth,
        ),
    )
    overall = (
        0.2 * feasibility
        + 0.2 * objective
        + 0.15 * risk
        + 0.15 * cost
        + 0.15 * confidence
        + 0.075 * tool_readiness
        + 0.075 * tool_coverage
    )
    return {
        "feasibility": round(feasibility, 6),
        "objective": round(objective, 6),
        "risk": round(risk, 6),
        "cost": round(cost, 6),
        "confidence": round(confidence, 6),
        "tool_readiness": round(tool_readiness, 6),
        "tool_coverage": round(tool_coverage, 6),
        "fallback_depth": round(fallback_depth, 6),
        "overall": round(overall, 6),
    }


def _derive_risk_level(
    payload: Plan | PlanPatch,
    registry: Sequence[ToolSpec],
) -> Literal["low", "medium", "high"]:
    registry_map = {spec.id: spec for spec in registry}
    risk_scores = [
        _tool_risk_cost_score(registry_map[tool_id])[0]
        for tool_id in _extract_payload_tool_ids(payload)
        if tool_id in registry_map
    ]
    if not risk_scores:
        return "medium"
    normalized = sum(risk_scores) / len(risk_scores)
    if normalized <= 0.33:
        return "low"
    if normalized <= 0.66:
        return "medium"
    return "high"


def _derive_cost_estimate(
    payload: Plan | PlanPatch,
    registry: Sequence[ToolSpec],
) -> Literal["low", "medium", "high"]:
    registry_map = {spec.id: spec for spec in registry}
    cost_scores = [
        _tool_risk_cost_score(registry_map[tool_id])[1]
        for tool_id in _extract_payload_tool_ids(payload)
        if tool_id in registry_map
    ]
    if not cost_scores:
        return "medium"
    normalized = sum(cost_scores) / len(cost_scores)
    if normalized <= 0.33:
        return "low"
    if normalized <= 0.66:
        return "medium"
    return "high"


def _tool_readiness_score(spec: ToolSpec) -> float:
    adapter_base = {
        "local": 0.9,
        "hybrid": 0.82,
        "remote": 0.72,
        "mock": 0.6,
        "unknown": 0.55,
    }
    base = adapter_base.get(spec.adapter_mode, 0.55)
    priority_bonus = 0.06 if _priority_rank(spec.priority) == 0 else 0.0
    safety_penalty = min(0.18, max(0, spec.safety_level - 1) * 0.05)
    return min(1.0, max(0.0, base + priority_bonus - safety_penalty))


def _tool_coverage_score(tool_ids: Sequence[str], capabilities: Set[str]) -> float:
    if not tool_ids:
        return 0.0
    return min(1.0, len(capabilities) / max(1, len(tool_ids)))


def _fallback_depth_score(
    tool_ids: Sequence[str],
    registry_map: dict[str, ToolSpec],
    registry: Sequence[ToolSpec],
) -> float:
    fallback_scores: List[float] = []
    for tool_id in tool_ids:
        spec = registry_map.get(tool_id)
        if spec is None:
            continue
        capability = _primary_capability(spec)
        alternatives = [
            candidate
            for candidate in registry
            if candidate.id != spec.id and capability in candidate.capabilities
        ]
        fallback_scores.append(min(1.0, len(alternatives) / 3.0))
    if not fallback_scores:
        return 0.0
    return sum(fallback_scores) / len(fallback_scores)


def _tool_risk_cost_score(spec: ToolSpec) -> tuple[float, float]:
    adapter_risk = {
        "local": 0.22,
        "hybrid": 0.32,
        "remote": 0.44,
        "mock": 0.15,
        "unknown": 0.38,
    }
    adapter_cost = {
        "local": 0.42,
        "hybrid": 0.45,
        "remote": 0.34,
        "mock": 0.12,
        "unknown": 0.48,
    }
    capability_risk = {
        "sequence_generation": 0.08,
        "sequence_design": 0.05,
        "structure_prediction": 0.14,
        "quality_qc": -0.08,
        "objective_scoring": -0.04,
    }
    capability_cost = {
        "sequence_generation": 0.12,
        "sequence_design": 0.1,
        "structure_prediction": 0.2,
        "quality_qc": 0.05,
        "objective_scoring": 0.08,
    }
    risk = adapter_risk.get(spec.adapter_mode, 0.38)
    cost = adapter_cost.get(spec.adapter_mode, 0.48)
    for capability in spec.capabilities:
        risk += capability_risk.get(capability, 0.0)
        cost += capability_cost.get(capability, 0.0)
    # 补充基础安全/资源成本信号
    risk += max(0, spec.safety_level - 1) * 0.06
    cost += min(0.35, float(spec.cost) * 0.2)
    return (
        min(1.0, max(0.0, risk)),
        min(1.0, max(0.0, cost)),
    )


def _extract_payload_tool_ids(payload: Plan | PlanPatch) -> List[str]:
    if isinstance(payload, Plan):
        return [step.tool for step in payload.steps]
    tool_ids: List[str] = []
    for op in payload.operations:
        if op.step is not None:
            tool_ids.append(op.step.tool)
    return tool_ids


def _stable_candidate_id(
    candidate_kind: str,
    payload: Plan | PlanPatch,
    primary_tool_id: str,
    capability_bucket: str,
) -> str:
    fingerprint = _canonical_payload_fingerprint(
        payload,
        primary_tool_id,
        capability_bucket,
    )
    return f"{candidate_kind}_{fingerprint[:12]}"


def _canonical_payload_fingerprint(
    payload: Plan | PlanPatch,
    primary_tool_id: str,
    capability_bucket: str,
) -> str:
    canonical_blob = json.dumps(
        {
            "payload": payload.model_dump(mode="json"),
            "primary_tool_id": primary_tool_id,
            "capability_bucket": capability_bucket,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha1(canonical_blob.encode("utf-8")).hexdigest()


def _resolve_step_capability(step: PlanStep, spec: ToolSpec | None) -> str:
    if spec is not None and spec.capabilities:
        return spec.capabilities[0]
    return _extract_step_capability(step.metadata)


def _primary_capability(spec: ToolSpec | None) -> str:
    if spec is None or not spec.capabilities:
        return "unknown"
    return str(spec.capabilities[0])


def _rank_candidate_tools(
    *,
    registry: Sequence[ToolSpec],
    capability: str,
    available_inputs: Set[str],
    exclude_tool: str,
) -> List[ToolSpec]:
    candidates: List[ToolSpec] = []
    for spec in registry:
        if spec.id == exclude_tool:
            continue
        if capability and capability not in spec.capabilities:
            continue
        if not set(spec.inputs).issubset(available_inputs):
            continue
        candidates.append(spec)
    candidates.sort(
        key=lambda spec: (
            _priority_rank(spec.priority),
            spec.cost,
            spec.safety_level,
            spec.id,
        )
    )
    return candidates


def _priority_rank(priority: str | None) -> int:
    if not priority:
        return 9
    normalized = priority.strip().upper()
    if normalized == "P0":
        return 0
    if normalized.startswith("P") and normalized[1:].isdigit():
        return int(normalized[1:])
    return 9


def _infer_adapter_mode(
    execution: object,
) -> Literal["local", "remote", "mock", "hybrid", "unknown"]:
    if isinstance(execution, str):
        normalized = execution.strip().lower()
        if normalized in {"nextflow", "python", "shell", "local"}:
            return "local"
        if normalized in {"mock"}:
            return "mock"
        if normalized in {"external_api", "remote_model_service", "remote"}:
            return "remote"
        return "unknown"
    if isinstance(execution, dict):
        backend = str(execution.get("backend", "")).strip().lower()
        if backend in {"remote_model_service", "external_api"}:
            return "remote"
        if backend in {"nextflow", "python", "local"}:
            return "local"
        if backend == "mock":
            return "mock"
    return "unknown"


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
    candidates = _rank_candidate_tools(
        registry=registry,
        capability=capability,
        available_inputs=available_inputs,
        exclude_tool=exclude_tool,
    )
    if not candidates:
        raise ValueError(
            f"No alternative tool found for capability '{capability}' with inputs {sorted(available_inputs)}"
        )
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
                cost=float(tool.get("cost_score", 1.0)),
                safety_level=tool.get("safety_level", 1),
                io_type=io_spec.get("io_type_id"),
                adapter_mode=_infer_adapter_mode(tool.get("execution")),
                priority=tool.get("priority")
                if isinstance(tool.get("priority"), str)
                else None,
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
            _priority_rank(t.priority),
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
    available_inputs.add("goal")
    template_pdb = _extract_template_pdb(constraints)
    if template_pdb:
        available_inputs.add("pdb_path")

    safety_level = constraints.get("safety_level")
    prefer_remote = _prefers_remote_tools(constraints)

    try:
        sequence_tool = _select_tool_by_capability(
            registry=registry,
            capability="sequence_generation",
            available_inputs=available_inputs,
            safety_level=safety_level,
            io_hint=None,
            prefer_remote=prefer_remote,
        )
    except ValueError:
        fallback_inputs = _collect_registry_inputs(registry)
        sequence_tool = _select_tool_by_capability(
            registry=registry,
            capability="sequence_generation",
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
    prompt = constraints.get("prompt")
    if isinstance(prompt, str) and prompt:
        step_inputs["prompt"] = prompt
    num_candidates = constraints.get("num_candidates")
    if isinstance(num_candidates, int) and num_candidates > 0:
        step_inputs["num_candidates"] = num_candidates
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
        "de_novo_design 任务采用序列生成→结构预测两步链路。",
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
