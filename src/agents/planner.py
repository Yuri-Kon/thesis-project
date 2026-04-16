from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Literal, Optional, Sequence, Set, Tuple

from src.adapters.registry import get_adapter
from src.kg.kg_client import ToolKGError, load_tool_kg
from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.baseline_provider import BaselineProvider
from src.llm.provider_registry import create_provider, load_provider_catalog
from src.agents.task_goal_parser import enrich_task_from_goal
from src.models.contracts import (
    ACTION_SCORE_METADATA_KEY,
    DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
    FINAL_SCORE_METADATA_KEY,
    PatchRequest,
    PendingActionType,
    PendingActionCandidate,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanPatchOpType,
    PlanStep,
    ProteinDesignTask,
    RERANK_REASON_METADATA_KEY,
    RecommendationReason,
    RerankReason,
    ReplanRequest,
    RuntimeState,
    RuntimeAdjustmentFactor,
    RuntimeAdjustmentSummary,
    RuntimeStateSummary,
    ScoreSummary,
    STATIC_SCORE_METADATA_KEY,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
    RUNTIME_STATE_SUMMARY_METADATA_KEY,
    StepResult,
    SHADOW_SCORE_METADATA_KEY,
    WAITING_RUNTIME_SUMMARY_METADATA_KEY,
    now_iso,
)
from src.models.validation import (
    CandidateExecutionValidationError,
    validate_candidate_set_output,
    validate_plan_executability,
)
from src.models.db import (
    InternalStatus,
    TaskRecord,
    TERMINAL_INTERNAL_STATUSES,
    to_external_status,
)
from src.storage.log_store import append_event
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
class _RuntimeShadowDecision:
    shadow_score: dict[str, Any]
    final_score: dict[str, Any]
    runtime_adjustment: dict[str, Any]
    rerank_reason: dict[str, Any]
    shadow_action: str
    shadow_reason: str
    explanation_fragment: str


@dataclass(frozen=True)
class _CandidatePayload:
    payload: Plan | PlanPatch
    primary_tool_id: str
    capability_bucket: str
    note: str
    recovery_layer: str | None = None
    recovery_reason: str | None = None


@dataclass(frozen=True)
class RuntimeFallbackConfig:
    """Planner 双路推理回退配置。"""

    enable_dual_route: bool = True
    force_external_only: bool = False
    schema_fail_threshold: int = 2
    executable_rate_threshold: float = 0.95
    executable_drop_threshold: float = 0.05
    consecutive_failure_threshold: int = 2
    sustained_high_risk_threshold: int = 2
    fallback_capability: str = "planner_generation"


@dataclass(frozen=True)
class RouteTrigger:
    """触发外部回退的原因与阈值描述。"""

    reason: str
    threshold: str


_PATCH_LAYER_PRIORITY = {
    "parameter_level": 0,
    "tool_level": 1,
    "structure_level": 2,
}

_S5_STAGE_ID = "S5"
_S5_STAGE_NAME = "objective_scoring"
_S5_INPUT_FIELDS = ("candidates", "metrics")
_S5_OUTPUT_FIELDS = (
    "score_breakdown",
    "top_k",
    "default_recommendation",
    "explanation",
)
_DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "feasibility": 0.2,
    "objective": 0.2,
    "risk": 0.15,
    "cost": 0.15,
    "confidence": 0.15,
    "tool_readiness": 0.075,
    "tool_coverage": 0.075,
}
_SCORE_WEIGHT_KEY_ALIASES: dict[str, str] = {
    "readiness": "tool_readiness",
    "coverage": "tool_coverage",
}

_P0_CAPABILITY_REPLACEMENT_MATRIX: dict[str, tuple[str, ...]] = {
    # Requirement-2: P0 capability swap matrix (structure prediction core path)
    "structure_prediction": ("nim_esmfold", "esmfold", "alphafold", "openfold2", "openfold"),
    # Requirement-2: minimal fallback path for quality_qc
    "quality_qc": ("biopython_qc", "dssp"),
    # Requirement-2: minimal fallback path for objective_scoring
    "objective_scoring": ("objective_ranker",),
}

_DEFAULT_EXTERNAL_PROVIDER_NAME = "external_baseline"
_DEFAULT_PROVIDER_CATALOG_PATH = Path(__file__).resolve().parents[2] / "configs" / "llm_providers.json"
_PLANNER_PROVIDER_ENV = "PLANNER_LLM_PROVIDER"
_PREFERRED_LOCAL_PROVIDER_ORDER = (
    "qwen-plus",
    "glm-5",
    "deepseek-chat",
    "deepseek-reasoner",
    "nemotron",
    "openai",
)


class PlannerAgent:
    """最小可用 PlannerAgent: 根据任务目标生成一个单步 Plan

    当前实现：支持可选的 LLM Provider 生成计划，或使用默认的单步计划
    默认工具注册表来自 ProteinToolKG（读取失败时回退到内置 dummy 列表）。
    """

    def __init__(
        self,
        tool_registry: Iterable[ToolSpec] | None = None,
        llm_provider: Optional[BaseProvider] = None,
        fallback_llm_provider: Optional[BaseProvider] = None,
    ) -> None:
        """初始化 PlannerAgent

        Args:
            tool_registry: 可用工具注册表，默认从 ProteinToolKG 读取
            llm_provider: 可选的 LLM Provider，用于生成计划
            fallback_llm_provider: 外部兜底 Provider（默认 baseline）
        """
        if tool_registry is None:
            tool_registry = _load_default_tool_registry()
        self._tool_registry: List[ToolSpec] = list(tool_registry)
        if not self._tool_registry:
            raise ValueError(
                "Tool registry is empty; ensure ProteinToolKG provides tools."
            )
        self._llm_provider = llm_provider or _load_configured_llm_provider()
        self._fallback_llm_provider = (
            fallback_llm_provider
            if fallback_llm_provider is not None
            else BaselineProvider(ProviderConfig(model_name=_DEFAULT_EXTERNAL_PROVIDER_NAME))
        )
        self._runtime_fallback_state: dict[str, dict[str, Any]] = {}

    def plan(
        self,
        task: ProteinDesignTask,
        *,
        use_external: bool = False,
    ) -> Plan:
        """生成执行计划

        Args:
            task: 蛋白质设计任务
            use_external: 是否使用 external fallback provider

        Returns:
            Plan: 包含步骤列表的执行计划
        """
        enriched_task = enrich_task_from_goal(task)
        return self._plan_from_route(enriched_task, use_external=use_external)

    def plan_top_k(
        self,
        task: ProteinDesignTask,
        *,
        k: int = 3,
        runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None = None,
    ) -> TopKResult:
        """生成 Plan Top-K 候选（默认 K=3）。"""
        base_plan = self.plan(task)
        return self._build_plan_top_k(
            task,
            base_plan,
            k=_normalize_top_k(k),
            runtime_state=runtime_state,
        )

    def _build_plan_top_k(
        self,
        task: ProteinDesignTask,
        base_plan: Plan,
        *,
        k: int,
        runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None = None,
    ) -> TopKResult:
        """基于 base_plan 组装 plan top-k 结果。"""
        payloads = _build_plan_candidate_payloads(
            task=task,
            base_plan=base_plan,
            registry=self._tool_registry,
            top_k=k,
        )
        return _build_top_k_result(
            payloads=payloads,
            registry=self._tool_registry,
            candidate_kind="plan",
            top_k=k,
            task_constraints=task.constraints,
            runtime_state=runtime_state,
        )

    def patch_top_k(
        self,
        request: PatchRequest,
        *,
        k: int = 3,
        runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None = None,
    ) -> TopKResult:
        """生成 Patch Top-K 候选（统一 CandidateSetOutput v1 字段）。"""
        _ensure_task_match(request)
        payloads: list[_CandidatePayload] = []
        payloads.extend(
            self._build_provider_patch_candidates(
                request=request,
                top_k=_normalize_top_k(k),
            )
        )
        payloads.extend(
            _build_patch_candidate_payloads(
                request=request,
                registry=self._tool_registry,
                top_k=_normalize_top_k(k),
            )
        )
        return _build_top_k_result(
            payloads=payloads,
            registry=self._tool_registry,
            candidate_kind="patch",
            top_k=_normalize_top_k(k),
            task_constraints=request.original_plan.constraints,
            runtime_state=runtime_state,
        )

    def replan_top_k(
        self,
        request: ReplanRequest,
        *,
        k: int = 3,
        runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None = None,
    ) -> TopKResult:
        """生成 Replan Top-K 候选（统一 CandidateSetOutput v1 字段）。"""
        _ensure_replan_task_match(request)
        payloads: list[_CandidatePayload] = []
        payloads.extend(
            self._build_provider_replan_candidates(
                request=request,
                top_k=_normalize_top_k(k),
            )
        )
        payloads.extend(
            _build_replan_candidate_payloads(
                request=request,
                registry=self._tool_registry,
                top_k=_normalize_top_k(k),
            )
        )
        return _build_top_k_result(
            payloads=payloads,
            registry=self._tool_registry,
            candidate_kind="replan",
            top_k=_normalize_top_k(k),
            task_constraints=request.original_plan.constraints,
            runtime_state=runtime_state,
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

    def score_candidate_payload(
        self,
        payload: Plan | PlanPatch,
        *,
        task_constraints: dict[str, Any] | None = None,
        runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """对单个候选 payload 打分（用于调试/测试）。"""
        score_weights = _resolve_score_weights(task_constraints or {})
        score_breakdown = _score_payload(
            payload,
            self._tool_registry,
            score_weights=score_weights,
        )
        if runtime_state is None:
            return score_breakdown
        runtime_summary = _normalize_runtime_state_summary_input(runtime_state)
        shadow = _build_runtime_shadow_decision(
            candidate_kind=_infer_candidate_kind(payload),
            payload=payload,
            score_breakdown=score_breakdown,
            runtime_state_summary=runtime_summary,
        )
        return {
            **score_breakdown,
            "static_score": float(score_breakdown.get("overall", 0.0)),
            "runtime_adjustment": float(shadow.runtime_adjustment["value"]),
            "final_score": float(shadow.final_score["value"]),
            "shadow_overall": float(shadow.shadow_score["value"]),
        }

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

    def _plan_from_route(
        self,
        task: ProteinDesignTask,
        *,
        use_external: bool,
    ) -> Plan:
        if use_external:
            plan = self._plan_from_provider(task, provider=self._fallback_llm_provider)
            provider_name = _provider_name(self._fallback_llm_provider)
            return self._attach_route_metadata(
                plan,
                provider_tier="external",
                provider_name=provider_name,
            )

        # local path keeps backward-compatible default behavior
        if self._llm_provider is None:
            plan = self._default_plan(task)
            return self._attach_route_metadata(
                plan,
                provider_tier="local",
                provider_name="planner_default",
            )

        plan = self._plan_from_provider(task, provider=self._llm_provider)
        provider_name = _provider_name(self._llm_provider)
        return self._attach_route_metadata(
            plan,
            provider_tier="local",
            provider_name=provider_name,
        )

    def _plan_from_provider(
        self,
        task: ProteinDesignTask,
        *,
        provider: BaseProvider,
    ) -> Plan:
        plan_dict = provider.call_planner(task=task, tool_registry=self._tool_registry)
        plan = Plan.model_validate(plan_dict)
        plan = _resolve_plan_tools(
            plan,
            self._tool_registry,
            task.constraints,
        )
        plan = _materialize_missing_plan_inputs(
            plan,
            self._tool_registry,
            task,
        )
        _ensure_plan_tools_in_registry(plan, self._tool_registry)
        return _attach_kg_explanation(plan)

    def _attach_route_metadata(
        self,
        plan: Plan,
        *,
        provider_tier: Literal["local", "external"],
        provider_name: str,
    ) -> Plan:
        metadata = dict(plan.metadata or {})
        route_meta = dict(metadata.get("planner_route", {}))
        route_meta["provider_tier"] = provider_tier
        route_meta["provider_name"] = provider_name
        metadata["planner_route"] = route_meta
        return plan.model_copy(update={"metadata": metadata})

    def _estimate_executable_rate(
        self,
        top_k_result: TopKResult,
        task: ProteinDesignTask,
    ) -> float:
        total = 0
        executable = 0
        for candidate in top_k_result.candidates:
            payload = candidate.structured_payload
            if not isinstance(payload, Plan):
                continue
            total += 1
            try:
                validate_plan_executability(payload, task)
                executable += 1
            except CandidateExecutionValidationError:
                continue
            except Exception:
                continue
        if total == 0:
            return 0.0
        return executable / total

    def plan_with_status(
        self,
        task: ProteinDesignTask,
        context: WorkflowContext,
        *,
        record: TaskRecord | None = None,
    ) -> Plan:
        """生成 Plan 并驱动 PLANNING → PLANNED/WAITING_PLAN_CONFIRM 状态变更。"""
        task = enrich_task_from_goal(task)
        context.task = task
        if record is not None:
            record.goal = task.goal
            record.constraints = task.constraints
            record.metadata = task.metadata
        transition_task_status(
            context,
            record,
            InternalStatus.PLANNING,
            reason="task_created",
        )
        runtime_cfg = _resolve_runtime_fallback_config(task.constraints)
        runtime_state = dict(self._runtime_fallback_state.get(task.task_id, {}))
        route_trigger: RouteTrigger | None = _resolve_pre_route_trigger(
            context=context,
            cfg=runtime_cfg,
        )

        try:
            top_k_value = _resolve_top_k_value(
                task.constraints,
                key="plan_top_k",
                default=3,
            )
            use_external = route_trigger is not None
            if use_external:
                base_plan = self.plan(task, use_external=True)
            else:
                try:
                    base_plan = self.plan(task, use_external=False)
                    runtime_state["schema_fail_streak"] = 0
                except Exception:
                    streak = _safe_int(runtime_state.get("schema_fail_streak"), default=0) + 1
                    runtime_state["schema_fail_streak"] = streak
                    if runtime_cfg.enable_dual_route and streak >= runtime_cfg.schema_fail_threshold:
                        route_trigger = RouteTrigger(
                            reason="schema_fail_streak",
                            threshold=(
                                f"schema_fail_streak={streak}"
                                f">={runtime_cfg.schema_fail_threshold}"
                            ),
                        )
                        use_external = True
                        base_plan = self.plan(task, use_external=True)
                    else:
                        self._runtime_fallback_state[task.task_id] = dict(runtime_state)
                        raise

            top_k = self._build_plan_top_k(
                task,
                base_plan,
                k=_normalize_top_k(top_k_value),
                runtime_state=context.runtime_state,
            )
            executable_rate = self._estimate_executable_rate(top_k, task)
            previous_rate = _safe_optional_float(runtime_state.get("last_executable_rate"))

            if (
                runtime_cfg.enable_dual_route
                and not use_external
                and self._fallback_llm_provider is not None
            ):
                drop = (
                    previous_rate - executable_rate
                    if previous_rate is not None
                    else 0.0
                )
                trigger: RouteTrigger | None = None
                if executable_rate < runtime_cfg.executable_rate_threshold:
                    trigger = RouteTrigger(
                        reason="candidate_executable_rate_low",
                        threshold=(
                            f"candidate_executable_rate={executable_rate:.3f}"
                            f"<{runtime_cfg.executable_rate_threshold:.3f}"
                        ),
                    )
                elif drop >= runtime_cfg.executable_drop_threshold:
                    trigger = RouteTrigger(
                        reason="candidate_executable_rate_drop",
                        threshold=(
                            f"candidate_executable_drop={drop:.3f}"
                            f">={runtime_cfg.executable_drop_threshold:.3f}"
                        ),
                    )
                if trigger is not None:
                    route_trigger = trigger
                    use_external = True
                    base_plan = self.plan(task, use_external=True)
                    top_k = self._build_plan_top_k(
                        task,
                        base_plan,
                        k=_normalize_top_k(top_k_value),
                        runtime_state=context.runtime_state,
                    )
                    executable_rate = self._estimate_executable_rate(top_k, task)

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

        route_meta = plan.metadata.get("planner_route", {}) if isinstance(plan.metadata, dict) else {}
        to_provider = str(route_meta.get("provider_name") or "planner_default")
        from_provider = str(runtime_state.get("last_provider_name") or to_provider)
        if route_trigger is not None or from_provider != to_provider:
            append_event(
                task.task_id,
                {
                    "event": "PLANNER_ROUTE_DECISION",
                    "task_id": task.task_id,
                    "timestamp": now_iso(),
                    "tool": to_provider,
                    "from_tool": from_provider,
                    "to_tool": to_provider,
                    "capability_id": runtime_cfg.fallback_capability,
                    "state": context.status.value,
                    "external_status": to_external_status(context.status).value,
                    "data": {
                        "from_tool": from_provider,
                        "to_tool": to_provider,
                        "capability_id": runtime_cfg.fallback_capability,
                        "trigger_reason": route_trigger.reason if route_trigger else "route_stable",
                        "trigger_threshold": route_trigger.threshold if route_trigger else "",
                        "enable_dual_route": runtime_cfg.enable_dual_route,
                    },
                },
            )

        runtime_state["last_provider_name"] = to_provider
        runtime_state["last_executable_rate"] = round(executable_rate, 6)
        self._runtime_fallback_state[task.task_id] = dict(runtime_state)

        context.plan = plan
        if record is not None:
            record.plan = plan

        if gate.requires_hitl:
            pending_action_metadata = _build_pending_action_runtime_metadata(
                default_candidate=candidate,
                default_recommendation=top_k.default_recommendation,
                waiting_reason=gate.reason,
            )
            pending_action = build_pending_action(
                task_id=task.task_id,
                action_type=PendingActionType.PLAN_CONFIRM,
                candidates=top_k.candidates,
                default_suggestion=top_k.default_recommendation,
                default_recommendation=top_k.default_recommendation,
                explanation=f"{top_k.explanation} gate={gate.reason}",
                metadata=pending_action_metadata,
            )
            validate_candidate_set_output(
                pending_action,
                require_s5_fields=True,
                require_shadow_rerank_fields=True,
            )
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

    def _build_provider_patch_candidates(
        self,
        *,
        request: PatchRequest,
        top_k: int,
    ) -> list[_CandidatePayload]:
        provider = self._llm_provider
        if provider is None:
            return []
        try:
            patch_dict = provider.call_patch(request, self._tool_registry)
        except Exception:
            return []
        if not isinstance(patch_dict, dict):
            return []
        try:
            patch = PlanPatch.model_validate(patch_dict)
        except Exception:
            return []
        route_name = _provider_name(provider)
        target_step = _locate_patch_target_step(request)
        primary_tool_id = _extract_primary_tool_id_from_patch(patch, fallback=target_step.tool)
        capability_bucket = _extract_primary_capability_from_patch(
            patch,
            registry=self._tool_registry,
            fallback_step=target_step,
        )
        patch = _attach_provider_metadata_to_patch(patch, provider_name=route_name)
        return [
            _CandidatePayload(
                payload=patch,
                primary_tool_id=primary_tool_id,
                capability_bucket=capability_bucket,
                note=f"llm_patch:{route_name}",
                recovery_layer=_extract_patch_recovery_layer(patch),
                recovery_reason=_extract_patch_recovery_reason(patch),
            )
        ]

    def _build_provider_replan_candidates(
        self,
        *,
        request: ReplanRequest,
        top_k: int,
    ) -> list[_CandidatePayload]:
        provider = self._llm_provider
        if provider is None:
            return []
        try:
            plan_dict = provider.call_replan(request, self._tool_registry)
        except Exception:
            return []
        if not isinstance(plan_dict, dict):
            return []
        try:
            plan = Plan.model_validate(plan_dict)
            plan = _resolve_plan_tools(
                plan,
                self._tool_registry,
                request.original_plan.constraints,
            )
            _ensure_plan_tools_in_registry(plan, self._tool_registry)
            plan = _attach_provider_metadata_to_plan(plan, provider_name=_provider_name(provider))
            plan = _attach_kg_explanation(plan)
        except Exception:
            return []
        primary_tool = plan.steps[-1].tool if plan.steps else request.original_plan.steps[-1].tool
        primary_spec = _find_tool_spec(self._tool_registry, primary_tool)
        return [
            _CandidatePayload(
                payload=plan,
                primary_tool_id=primary_tool,
                capability_bucket=_primary_capability(primary_spec),
                note=f"llm_replan:{_provider_name(provider)}",
            )
        ]


# --- helpers ---


def _provider_name(provider: BaseProvider) -> str:
    config = getattr(provider, "config", None)
    model_name = getattr(config, "model_name", None)
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    return provider.__class__.__name__


def _load_configured_llm_provider() -> BaseProvider | None:
    if not _DEFAULT_PROVIDER_CATALOG_PATH.exists():
        return None
    try:
        catalog = load_provider_catalog(_DEFAULT_PROVIDER_CATALOG_PATH)
    except Exception:
        return None
    provider_alias = _resolve_local_provider_alias(catalog)
    if not provider_alias:
        return None
    settings = catalog.providers.get(provider_alias)
    if settings is None:
        return None
    try:
        return create_provider(settings)
    except Exception:
        return None


def _resolve_local_provider_alias(catalog: object | None = None) -> str | None:
    explicit = os.getenv(_PLANNER_PROVIDER_ENV)
    if isinstance(explicit, str):
        explicit = explicit.strip()
        if explicit:
            if explicit.lower() in {"none", "disabled", "off", "baseline"}:
                return None
            return explicit

    providers = getattr(catalog, "providers", None)
    if isinstance(providers, dict):
        ordered_aliases: list[str] = []
        seen_aliases: set[str] = set()
        for alias in _PREFERRED_LOCAL_PROVIDER_ORDER:
            if alias in providers:
                ordered_aliases.append(alias)
                seen_aliases.add(alias)
        for alias in providers:
            if alias not in seen_aliases:
                ordered_aliases.append(alias)

        for alias in ordered_aliases:
            if alias == "baseline":
                continue
            settings = providers[alias]
            api_key = getattr(settings, "api_key", None)
            if isinstance(api_key, str) and api_key.strip():
                return alias
            api_key_env = getattr(settings, "api_key_env", None)
            if isinstance(api_key_env, str) and api_key_env.strip() and os.getenv(api_key_env):
                return alias
            if alias == "openai" and os.getenv("OPENAI_API_KEY"):
                return alias
    return None


def _safe_int(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_runtime_fallback_config(constraints: dict[str, Any]) -> RuntimeFallbackConfig:
    runtime_cfg = constraints.get("runtime_fallback")
    payload = runtime_cfg if isinstance(runtime_cfg, dict) else {}

    return RuntimeFallbackConfig(
        enable_dual_route=_safe_bool(payload.get("enable_dual_route"), default=True),
        force_external_only=(
            _safe_bool(payload.get("force_external_only"), default=False)
            or _safe_bool(os.getenv("PLANNER_FORCE_EXTERNAL_FALLBACK"), default=False)
        ),
        schema_fail_threshold=max(1, _safe_int(payload.get("schema_fail_threshold"), default=2)),
        executable_rate_threshold=min(
            1.0,
            max(0.0, _safe_float(payload.get("executable_rate_threshold"), default=0.95)),
        ),
        executable_drop_threshold=max(
            0.0,
            _safe_float(payload.get("executable_drop_threshold"), default=0.05),
        ),
        consecutive_failure_threshold=max(
            1,
            _safe_int(payload.get("consecutive_failure_threshold"), default=2),
        ),
        sustained_high_risk_threshold=max(
            1,
            _safe_int(payload.get("sustained_high_risk_threshold"), default=2),
        ),
        fallback_capability=_safe_text(
            payload.get("fallback_capability"),
            default="planner_generation",
        ),
    )


def _resolve_pre_route_trigger(
    *,
    context: WorkflowContext,
    cfg: RuntimeFallbackConfig,
) -> RouteTrigger | None:
    if cfg.force_external_only:
        return RouteTrigger(
            reason="force_external_only",
            threshold="force_external_only=true",
        )
    if not cfg.enable_dual_route:
        return None

    consecutive_failures = _count_consecutive_execution_failures(context)
    if consecutive_failures >= cfg.consecutive_failure_threshold:
        return RouteTrigger(
            reason="consecutive_execution_failures",
            threshold=(
                f"consecutive_execution_failures={consecutive_failures}"
                f">={cfg.consecutive_failure_threshold}"
            ),
        )

    sustained_high_risk = _count_sustained_high_risk_events(context)
    if sustained_high_risk >= cfg.sustained_high_risk_threshold:
        return RouteTrigger(
            reason="sustained_high_risk",
            threshold=(
                f"sustained_high_risk={sustained_high_risk}"
                f">={cfg.sustained_high_risk_threshold}"
            ),
        )
    return None


def _count_consecutive_execution_failures(context: WorkflowContext) -> int:
    results = list(context.step_results.values())
    results.sort(key=lambda item: item.timestamp)
    count = 0
    for result in reversed(results):
        if result.status != "failed":
            break
        count += 1
    return count


def _count_sustained_high_risk_events(context: WorkflowContext) -> int:
    events = list(context.safety_events)
    events.sort(key=lambda item: item.timestamp)
    count = 0
    for event in reversed(events):
        if event.action == "block":
            count += 1
            continue
        if event.action == "warn":
            count += 1
            continue
        has_high_flag = any(flag.level in {"warn", "block"} for flag in event.risk_flags)
        if not has_high_flag:
            break
        count += 1
    return count


def _safe_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _safe_text(value: object, *, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return default


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


def _locate_patch_target_step(request: PatchRequest) -> PlanStep:
    return _locate_target_step(request)


def _extract_primary_tool_id_from_patch(payload: PlanPatch, *, fallback: str) -> str:
    for op in payload.operations:
        if op.step is not None and isinstance(op.step.tool, str) and op.step.tool:
            return op.step.tool
    return fallback


def _extract_primary_capability_from_patch(
    payload: PlanPatch,
    *,
    registry: Sequence[ToolSpec],
    fallback_step: PlanStep,
) -> str:
    tool_id = _extract_primary_tool_id_from_patch(payload, fallback=fallback_step.tool)
    try:
        spec = _find_tool_spec(registry, tool_id)
        return _primary_capability(spec)
    except Exception:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        capability = metadata.get("capability_id")
        if isinstance(capability, str) and capability:
            return capability
        fallback_meta = fallback_step.metadata if isinstance(fallback_step.metadata, dict) else {}
        fallback_capability = fallback_meta.get("capability_id") or fallback_meta.get("capability")
        if isinstance(fallback_capability, str) and fallback_capability:
            return fallback_capability
        return ""


def _extract_patch_recovery_layer(payload: PlanPatch) -> str | None:
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    value = metadata.get("recovery_layer")
    return value if isinstance(value, str) and value else None


def _extract_patch_recovery_reason(payload: PlanPatch) -> str | None:
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    value = metadata.get("reason")
    return value if isinstance(value, str) and value else None


def _attach_provider_metadata_to_patch(
    payload: PlanPatch,
    *,
    provider_name: str,
) -> PlanPatch:
    metadata = dict(payload.metadata or {})
    route_meta = dict(metadata.get("planner_route", {}))
    route_meta["provider_tier"] = "local"
    route_meta["provider_name"] = provider_name
    metadata["planner_route"] = route_meta
    return payload.model_copy(update={"metadata": metadata}, deep=True)


def _attach_provider_metadata_to_plan(
    payload: Plan,
    *,
    provider_name: str,
) -> Plan:
    metadata = dict(payload.metadata or {})
    route_meta = dict(metadata.get("planner_route", {}))
    route_meta["provider_tier"] = "local"
    route_meta["provider_name"] = provider_name
    metadata["planner_route"] = route_meta
    return payload.model_copy(update={"metadata": metadata}, deep=True)


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
    is_de_novo = _is_de_novo_task(task)
    base_plan = _ensure_s1_contract_metadata(
        task=task,
        plan=base_plan,
        registry=registry,
    )
    primary_s1_tool_id = _extract_primary_s1_tool_id(base_plan)
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
    available_inputs.add("goal")
    max_variants_per_step = max(1, top_k * 2)
    for idx, step in enumerate(base_plan.steps):
        step_inputs = set(available_inputs)
        step_spec = registry_map.get(step.tool)
        capability = _resolve_step_capability(step, step_spec)
        is_s1 = is_de_novo and _is_sequence_exploration_step(step, step_spec)
        if is_s1:
            step_inputs = _collect_sequence_exploration_inputs(task.constraints)
            alternatives = _rank_sequence_exploration_tools(
                registry=registry,
                available_inputs=step_inputs,
                exclude_tool=step.tool,
            )
        else:
            alternatives = _rank_candidate_tools(
                registry=registry,
                capability=capability,
                available_inputs=step_inputs,
                exclude_tool=step.tool,
            )
        for alternative in alternatives[:max_variants_per_step]:
            replacement_inputs = _materialize_inputs_for_tool(
                base_inputs=step.inputs,
                task=task,
                target_tool=alternative,
            )
            if replacement_inputs is None:
                continue
            replaced_step = step.model_copy(
                update={
                    "tool": alternative.id,
                    "inputs": replacement_inputs,
                    "metadata": {
                        **(step.metadata or {}),
                        "candidate_from": step.tool,
                        "candidate_strategy": "tool_swap",
                    },
                },
                deep=True,
            )
            if is_s1:
                fallback_tool_ids = _collect_s1_fallback_tool_ids(
                    registry=registry,
                    primary_tool_id=primary_s1_tool_id or step.tool,
                    available_inputs=step_inputs,
                )
                replaced_step = _attach_s1_contract_to_step(
                    step=replaced_step,
                    task=task,
                    selected_tool=alternative,
                    primary_tool_id=primary_s1_tool_id or step.tool,
                    fallback_tool_ids=fallback_tool_ids,
                    source_tier=(
                        "primary"
                        if alternative.id == (primary_s1_tool_id or step.tool)
                        else "fallback"
                    ),
                    source_reason="tool_swap",
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
    failed_result = _latest_failed_step_result(
        request.context_step_results,
        target_step.id,
    )

    available_inputs = _collect_available_inputs(
        request.context_step_results, target_step
    )
    alternatives = _rank_patch_alternatives(
        registry=registry,
        capability=capability,
        available_inputs=available_inputs,
        exclude_tool=target_step.tool,
    )
    if not alternatives:
        fallback_inputs = _collect_registry_inputs(registry)
        alternatives = _rank_patch_alternatives(
            registry=registry,
            capability=capability,
            available_inputs=fallback_inputs,
            exclude_tool=target_step.tool,
        )

    payloads: List[_CandidatePayload] = []
    parameter_patch = _build_parameter_level_patch(
        request=request,
        target_step=target_step,
        target_capability=capability,
        failed_result=failed_result,
    )
    if parameter_patch is not None:
        payloads.append(
            _CandidatePayload(
                payload=parameter_patch,
                primary_tool_id=target_step.tool,
                capability_bucket=capability,
                note=f"target:{target_step.id}:param_tweak:{target_step.tool}",
                recovery_layer="parameter_level",
                recovery_reason="parameter_tweak",
            )
        )

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
            metadata=_build_patch_metadata(
                target_capability=capability,
                source_tool=target_step.tool,
                selected_tool=alternative.id,
                recovery_layer="tool_level",
                reason="tool_swap_replacement_matrix",
                request_reason=request.reason,
            ),
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
                recovery_layer="tool_level",
                recovery_reason="tool_swap_replacement_matrix",
            )
        )

    structure_patch = _build_structure_level_patch(
        request=request,
        registry=registry,
        target_step=target_step,
        target_capability=capability,
    )
    if structure_patch is not None:
        payloads.append(
            _CandidatePayload(
                payload=structure_patch,
                primary_tool_id=target_step.tool,
                capability_bucket=capability,
                note=f"target:{target_step.id}:structure_guard",
                recovery_layer="structure_level",
                recovery_reason="insert_guard_step",
            )
        )

    if not payloads:
        raise ValueError(
            f"No patch candidate found for capability '{capability}' "
            f"with inputs {sorted(available_inputs)}"
        )
    return payloads


def _latest_failed_step_result(
    results: Sequence[StepResult],
    step_id: str,
) -> StepResult | None:
    for result in reversed(list(results)):
        if result.step_id == step_id and result.status == "failed":
            return result
    return None


def _build_parameter_level_patch(
    *,
    request: PatchRequest,
    target_step: PlanStep,
    target_capability: str,
    failed_result: StepResult | None,
) -> PlanPatch | None:
    param_updates = _derive_param_updates(failed_result, target_step)
    if not param_updates:
        return None

    patched_step = target_step.model_copy(
        update={
            "metadata": {
                **(target_step.metadata or {}),
                "patched_from": target_step.tool,
                "patch_param_updates": param_updates,
            }
        },
        deep=True,
    )
    op = PlanPatchOp(
        op="replace_step",
        target=target_step.id,
        step=patched_step,
    )
    return PlanPatch(
        task_id=request.task_id,
        operations=[op],
        metadata=_build_patch_metadata(
            target_capability=target_capability,
            source_tool=target_step.tool,
            selected_tool=target_step.tool,
            recovery_layer="parameter_level",
            reason="parameter_tweak",
            request_reason=request.reason,
            param_updates=param_updates,
        ),
    )


def _derive_param_updates(
    failed_result: StepResult | None,
    target_step: PlanStep,
) -> dict:
    updates: dict[str, object] = {}
    failure_type = failed_result.failure_type if failed_result is not None else None
    if failure_type in {"RETRYABLE", "TOOL_ERROR"}:
        updates["retry_profile"] = "conservative"
    error_message = (failed_result.error_message or "").lower() if failed_result else ""
    if "timeout" in error_message:
        updates["timeout_multiplier"] = 1.5
    if "memory" in error_message or "oom" in error_message:
        updates["batch_size"] = 1

    metadata = target_step.metadata if isinstance(target_step.metadata, dict) else {}
    if "temperature" in metadata:
        try:
            current = float(metadata["temperature"])
            updates["temperature"] = max(0.0, min(1.0, round(current * 0.8, 3)))
        except (TypeError, ValueError):
            pass

    if not updates:
        updates["patch_mode"] = "safe_default_retry"
    return updates


def _build_structure_level_patch(
    *,
    request: PatchRequest,
    registry: Sequence[ToolSpec],
    target_step: PlanStep,
    target_capability: str,
) -> PlanPatch | None:
    available_inputs = _collect_available_inputs(request.context_step_results, target_step)
    guard_tools = _rank_structure_guard_tools(
        registry=registry,
        available_inputs=available_inputs,
        exclude_tool=target_step.tool,
    )
    for guard_tool in guard_tools:
        guard_inputs = _materialize_structure_guard_inputs(
            target_step=target_step,
            guard_tool=guard_tool,
        )
        if guard_inputs is None:
            continue
        guard_step = PlanStep(
            id=f"{target_step.id}_guard",
            tool=guard_tool.id,
            inputs=guard_inputs,
            metadata={
                "stage_id": "S6",
                "stage_name": "patch_replan_control",
                "recovery_guard_for": target_step.id,
                "recovery_layer": "structure_level",
                "capability_id": _primary_capability(guard_tool),
            },
        )
        op = PlanPatchOp(
            op="insert_step_after",
            target=target_step.id,
            step=guard_step,
        )
        return PlanPatch(
            task_id=request.task_id,
            operations=[op],
            metadata=_build_patch_metadata(
                target_capability=target_capability,
                source_tool=target_step.tool,
                selected_tool=guard_tool.id,
                recovery_layer="structure_level",
                reason="insert_guard_step",
                request_reason=request.reason,
            ),
        )
    return None


def _rank_structure_guard_tools(
    *,
    registry: Sequence[ToolSpec],
    available_inputs: Set[str],
    exclude_tool: str,
) -> List[ToolSpec]:
    ranked: List[ToolSpec] = []
    seen: Set[str] = set()
    for capability in ("quality_qc", "objective_scoring"):
        candidates = _rank_patch_alternatives(
            registry=registry,
            capability=capability,
            available_inputs=available_inputs | {"sequence", "pdb_path", "plddt", "candidates"},
            exclude_tool=exclude_tool,
        )
        for candidate in candidates:
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            ranked.append(candidate)
    return ranked


def _materialize_structure_guard_inputs(
    *,
    target_step: PlanStep,
    guard_tool: ToolSpec,
) -> dict | None:
    resolved: dict[str, object] = {}
    source_inputs = target_step.inputs if isinstance(target_step.inputs, dict) else {}
    output_ref_aliases = {
        "sequence": "sequence",
        "pdb_path": "pdb_path",
        "structure_pdb": "pdb_path",
        "plddt": "plddt",
        "candidates": "candidates",
        "qc_metrics": "qc_metrics",
        "structure_metrics": "structure_metrics",
    }
    for required in guard_tool.inputs:
        if required in source_inputs:
            resolved[required] = source_inputs[required]
            continue
        alias = output_ref_aliases.get(required)
        if alias is not None:
            resolved[required] = f"{target_step.id}.{alias}"
            continue
        return None
    return resolved


def _build_patch_metadata(
    *,
    target_capability: str,
    source_tool: str,
    selected_tool: str,
    recovery_layer: str,
    reason: str,
    request_reason: str,
    param_updates: dict | None = None,
) -> dict:
    metadata: dict[str, object] = {
        "strategy": "layered_patch_v1",
        "recovery_layer": recovery_layer,
        "recovery_layer_rank": _PATCH_LAYER_PRIORITY.get(recovery_layer, 99),
        "reason": reason,
        "request_reason": request_reason,
        "capability_id": target_capability,
        "from_tool": source_tool,
        "to_tool": selected_tool,
        "replacement_matrix": list(
            _P0_CAPABILITY_REPLACEMENT_MATRIX.get(target_capability, ())
        ),
    }
    if param_updates:
        metadata["param_updates"] = param_updates
    return metadata


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
    task_constraints: dict[str, Any] | None = None,
    runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None = None,
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

    score_weights = _resolve_score_weights(task_constraints or {})
    runtime_state_summary = _normalize_runtime_state_summary_input(runtime_state)
    static_ranked_rows: List[Tuple[PendingActionCandidate, Tuple, str]] = []
    effective_ranked_rows: List[Tuple[PendingActionCandidate, Tuple, str]] = []
    for payload in unique_payloads:
        score_breakdown = _score_payload(
            payload.payload,
            registry,
            score_weights=score_weights,
        )
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
            "s5_contract": _build_s5_scoring_contract(score_weights),
            STATIC_SCORE_METADATA_KEY: _build_static_score_summary(score_breakdown),
            ACTION_SCORE_METADATA_KEY: _build_action_score_summary(score_breakdown),
        }
        explanation = (
            f"{candidate_kind} candidate with primary tool "
            f"{tool_id} in capability bucket {capability_id}."
        )
        payload_metadata = payload.payload.metadata if isinstance(payload.payload.metadata, dict) else {}
        planner_route = payload_metadata.get("planner_route")
        if isinstance(planner_route, dict):
            metadata["planner_route"] = dict(planner_route)
        if payload.recovery_layer:
            metadata["recovery_layer"] = payload.recovery_layer
        if payload.recovery_reason:
            metadata["recovery_reason"] = payload.recovery_reason
        if isinstance(payload.payload, PlanPatch):
            patch_meta = _extract_patch_candidate_metadata(payload.payload)
            if patch_meta:
                metadata.update(patch_meta)
        if isinstance(payload.payload, Plan):
            s1_metadata = _extract_s1_candidate_metadata(payload.payload)
            if s1_metadata:
                metadata.update(s1_metadata)
                metadata["sequence_confidence"] = score_breakdown.get("confidence")
        if runtime_state_summary is None:
            shadow = _build_shadow_passthrough_decision(score_breakdown)
        else:
            metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY] = dict(runtime_state_summary)
            shadow = _build_runtime_shadow_decision(
                candidate_kind=candidate_kind,
                payload=payload.payload,
                score_breakdown=score_breakdown,
                runtime_state_summary=runtime_state_summary,
            )
            metadata["shadow_action"] = shadow.shadow_action
            metadata["shadow_action_reason"] = shadow.shadow_reason
            explanation = f"{explanation} {shadow.explanation_fragment}"
        metadata[RUNTIME_ADJUSTMENT_METADATA_KEY] = shadow.runtime_adjustment
        metadata[FINAL_SCORE_METADATA_KEY] = shadow.final_score
        metadata[RERANK_REASON_METADATA_KEY] = shadow.rerank_reason
        metadata[SHADOW_SCORE_METADATA_KEY] = shadow.shadow_score
        candidate = PendingActionCandidate(
            candidate_id=candidate_id,
            structured_payload=payload.payload,
            score_breakdown=score_breakdown,
            risk_level=risk_level,
            cost_estimate=cost_estimate,
            explanation=explanation,
            summary=_build_candidate_summary(payload.payload),
            tool_id=tool_id,
            capability_id=capability_id,
            io_type=io_type,
            adapter_mode=adapter_mode,
            metadata=metadata,
        )
        priority_rank = _priority_rank(primary_tool.priority if primary_tool else None)
        patch_layer_rank = _patch_layer_rank(payload.payload)
        static_score_value = _extract_score_value(candidate, STATIC_SCORE_METADATA_KEY)
        final_score_value = _extract_score_value(candidate, FINAL_SCORE_METADATA_KEY)
        if candidate_kind == "patch":
            static_sort_key = (
                patch_layer_rank,
                -static_score_value,
                priority_rank,
                capability_id,
                tool_id,
                candidate_id,
            )
            effective_sort_key = (
                patch_layer_rank,
                -final_score_value,
                priority_rank,
                capability_id,
                tool_id,
                candidate_id,
            )
        else:
            static_sort_key = (
                -static_score_value,
                priority_rank,
                capability_id,
                tool_id,
                candidate_id,
            )
            effective_sort_key = (
                -final_score_value,
                priority_rank,
                capability_id,
                tool_id,
                candidate_id,
            )
        static_ranked_rows.append((candidate, static_sort_key, capability_id))
        effective_ranked_rows.append((candidate, effective_sort_key, capability_id))

    static_ranked_rows.sort(key=lambda row: row[1])
    static_selected_rows = _select_diverse_top_k(
        ranked_rows=static_ranked_rows,
        top_k=top_k,
    )
    static_selected_rows = sorted(static_selected_rows, key=lambda row: row[1])
    selected_rows = static_selected_rows
    if runtime_state_summary is not None:
        effective_ranked_rows.sort(key=lambda row: row[1])
        selected_rows = _select_diverse_top_k(
            ranked_rows=effective_ranked_rows,
            top_k=top_k,
        )
        selected_rows = sorted(selected_rows, key=lambda row: row[1])
    candidates = [row[0] for row in selected_rows]
    static_candidates = [row[0] for row in static_selected_rows]
    default_candidate = candidates[0] if candidates else None
    static_default_candidate = static_candidates[0] if static_candidates else None
    default_recommendation = default_candidate.candidate_id if default_candidate else None
    if candidates:
        default_candidate.metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY] = (
            _build_default_recommendation_reason(
                candidate_kind=candidate_kind,
                candidate_id=default_candidate.candidate_id,
                default_candidate=default_candidate,
                static_candidate=static_default_candidate,
                rerank_applied=runtime_state_summary is not None,
            )
        )
    explanation = (
        f"{candidate_kind} Top-K generated with deterministic sort "
        f"(requested={top_k}, returned={len(candidates)}). "
        "Ranking uses overall score desc + stable tie-break; "
        "selection uses capability-bucket round-robin."
    )
    if candidates and runtime_state_summary is not None and default_candidate is not None:
        shadow_action = str(default_candidate.metadata.get("shadow_action") or "continue")
        rerank_summary = _summarize_rerank_reason(default_candidate)
        explanation = (
            f"{candidate_kind} Top-K generated with deterministic sort "
            f"(requested={top_k}, returned={len(candidates)}). "
            "Ranking uses final_score desc + stable tie-break; "
            "selection uses capability-bucket round-robin."
        )
        if (
            static_default_candidate is not None
            and static_default_candidate.candidate_id != default_candidate.candidate_id
        ):
            explanation = (
                f"{explanation} Runtime rerank updated default recommendation "
                f"from {static_default_candidate.candidate_id} to {default_candidate.candidate_id}. "
                f"{rerank_summary} action={shadow_action}."
            )
        else:
            explanation = (
                f"{explanation} Runtime rerank kept default recommendation "
                f"at {default_candidate.candidate_id}. {rerank_summary} action={shadow_action}."
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


def _build_action_score_summary(score_breakdown: dict[str, float]) -> dict[str, Any]:
    summary = ScoreSummary(
        value=float(score_breakdown.get("overall", 0.0)),
        source="score_breakdown.overall",
    )
    return summary.model_dump()


def _build_static_score_summary(score_breakdown: dict[str, float]) -> dict[str, Any]:
    summary = ScoreSummary(
        value=float(score_breakdown.get("overall", 0.0)),
        source="score_breakdown.overall.static.v1",
    )
    return summary.model_dump()


def _build_shadow_score_summary(score_breakdown: dict[str, float]) -> dict[str, Any]:
    summary = ScoreSummary(
        value=float(score_breakdown.get("overall", 0.0)),
        source="score_breakdown.overall_passthrough",
    )
    return summary.model_dump()


def _normalize_runtime_state_summary_input(
    runtime_state: RuntimeState | RuntimeStateSummary | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if runtime_state is None:
        return None
    if isinstance(runtime_state, RuntimeState):
        return runtime_state.to_summary_payload()
    if isinstance(runtime_state, RuntimeStateSummary):
        return runtime_state.model_dump()
    if isinstance(runtime_state, dict):
        return RuntimeStateSummary.model_validate(runtime_state).model_dump()
    raise ValueError("runtime_state must be RuntimeState, RuntimeStateSummary, or mapping")


def _build_shadow_passthrough_decision(
    score_breakdown: dict[str, float],
) -> _RuntimeShadowDecision:
    static_value = round(float(score_breakdown.get("overall", 0.0)), 6)
    final_score = ScoreSummary(
        value=static_value,
        source="static_score+runtime_adjustment.shadow_passthrough.v1",
    )
    runtime_adjustment = RuntimeAdjustmentSummary(
        value=0.0,
        source="planner.runtime_adjustment.shadow_passthrough.v1",
        formula_version="v1",
        shadow_only=True,
    )
    rerank_reason = RerankReason(
        code="shadow_passthrough",
        message=(
            "No runtime_state was provided, so final_score mirrors static_score "
            "and remains shadow-only."
        ),
        shadow_only=True,
        runtime_state_fields=[],
        candidate_metric_fields=["score_breakdown.overall"],
        tool_metadata_fields=[],
        factors=[],
    )
    return _RuntimeShadowDecision(
        shadow_score=_build_shadow_score_summary(score_breakdown),
        final_score=final_score.model_dump(),
        runtime_adjustment=runtime_adjustment.model_dump(),
        rerank_reason=rerank_reason.model_dump(),
        shadow_action="continue",
        shadow_reason="runtime_state is not available",
        explanation_fragment=(
            "Shadow rerank is in passthrough mode; "
            f"static_score={static_value:.2f}, runtime_adjustment=0.00, final_score={static_value:.2f}."
        ),
    )


def _build_runtime_shadow_decision(
    *,
    candidate_kind: str,
    payload: Plan | PlanPatch,
    score_breakdown: dict[str, float],
    runtime_state_summary: dict[str, Any],
) -> _RuntimeShadowDecision:
    p_success = _safe_float(runtime_state_summary.get("p_success"), default=0.5)
    p_structural_failure = _safe_float(
        runtime_state_summary.get("p_structural_failure"),
        default=0.5,
    )
    recovery_margin = _safe_runtime_margin(runtime_state_summary.get("recovery_margin"))
    expected_remaining_cost = _safe_non_negative_float(
        runtime_state_summary.get("expected_remaining_cost"),
        default=0.0,
    )
    evidence_sufficiency = _safe_float(
        runtime_state_summary.get("evidence_sufficiency"),
        default=0.5,
    )
    budget_pressure = min(max(expected_remaining_cost, 0.0), 1.5)
    cost_pressure = min(budget_pressure, 1.0)
    margin_signal = max(-1.0, min(recovery_margin, 1.0))
    overall = _safe_float(score_breakdown.get("overall"), default=0.0)
    confidence = _safe_float(score_breakdown.get("confidence"), default=overall)
    risk = _safe_float(score_breakdown.get("risk"), default=overall)
    cost = _safe_float(score_breakdown.get("cost"), default=overall)
    fallback_depth = _safe_float(score_breakdown.get("fallback_depth"), default=0.5)
    feasibility = _safe_float(score_breakdown.get("feasibility"), default=0.5)
    action, reason = _resolve_shadow_action(
        candidate_kind=candidate_kind,
        payload=payload,
        p_success=p_success,
        p_structural_failure=p_structural_failure,
        recovery_margin=recovery_margin,
        budget_pressure=budget_pressure,
        cost_pressure=cost_pressure,
    )
    evidence_effect = 0.18 * (p_success - 0.5) * confidence
    evidence_sufficiency_effect = (
        0.10 * ((2.0 * evidence_sufficiency) - 1.0) * max(confidence, feasibility)
    )
    risk_effect = -0.16 * p_structural_failure * (1.0 - risk)
    recovery_effect = 0.10 * margin_signal * fallback_depth
    cost_effect = -0.14 * cost_pressure * (1.0 - cost)
    delta = (
        evidence_effect
        + evidence_sufficiency_effect
        + risk_effect
        + recovery_effect
        + cost_effect
    )
    factors = [
        _build_runtime_adjustment_factor(
            category="evidence",
            signal="p_success*confidence",
            source="runtime_state.p_success+score_breakdown.confidence",
            contribution=evidence_effect,
            message="Current evidence and candidate confidence adjust the shadow score.",
        ),
        _build_runtime_adjustment_factor(
            category="evidence",
            signal="evidence_sufficiency",
            source="runtime_state.evidence_sufficiency+score_breakdown.feasibility",
            contribution=evidence_sufficiency_effect,
            message="Evidence sufficiency raises confidence in routes backed by enough cheap validation.",
        ),
        _build_runtime_adjustment_factor(
            category="risk",
            signal="p_structural_failure",
            source="runtime_state.p_structural_failure+score_breakdown.risk",
            contribution=risk_effect,
            message="Structural failure pressure reduces the shadow score.",
        ),
        _build_runtime_adjustment_factor(
            category="recovery",
            signal="recovery_margin*fallback_depth",
            source="runtime_state.recovery_margin+score_breakdown.fallback_depth",
            contribution=recovery_effect,
            message="Recovery headroom and fallback depth shape the shadow rerank bonus.",
        ),
        _build_runtime_adjustment_factor(
            category="cost",
            signal="expected_remaining_cost",
            source="runtime_state.expected_remaining_cost+score_breakdown.cost",
            contribution=cost_effect,
            message="Remaining cost pressure penalizes expensive suffixes.",
        ),
    ]
    if action == "patch_local":
        patch_bonus = 0.04 * fallback_depth
        delta += patch_bonus
        factors.append(
            _build_runtime_adjustment_factor(
                category="recovery",
                signal="fallback_depth",
                source="score_breakdown.fallback_depth",
                contribution=patch_bonus,
                message="Local patchability keeps more recovery options available.",
            )
        )
    elif action == "suffix_replan":
        replan_recovery_bonus = 0.02 * feasibility
        replan_cost_penalty = -0.03 * cost_pressure
        delta += replan_recovery_bonus + replan_cost_penalty
        factors.append(
            _build_runtime_adjustment_factor(
                category="recovery",
                signal="feasibility",
                source="score_breakdown.feasibility",
                contribution=replan_recovery_bonus,
                message="Feasible suffix replacement preserves validated prefix value.",
            )
        )
        factors.append(
            _build_runtime_adjustment_factor(
                category="cost",
                signal="cost_pressure",
                source="runtime_state.expected_remaining_cost",
                contribution=replan_cost_penalty,
                message="Suffix replan still carries residual budget pressure.",
            )
        )
    elif action == "stop":
        stop_penalty = -(0.12 + 0.06 * cost_pressure)
        delta += stop_penalty
        factors.append(
            _build_runtime_adjustment_factor(
                category="policy",
                signal="stop_guard",
                source="runtime_state.p_success+runtime_state.expected_remaining_cost",
                contribution=stop_penalty,
                message="Stop guard applies when success is low and cost pressure is already high.",
            )
        )
    delta = max(-0.35, min(0.35, delta))
    adjusted = max(0.0, min(1.0, overall + delta))
    final_score = ScoreSummary(
        value=round(adjusted, 6),
        source=f"static_score+runtime_adjustment.{action}.v1",
    )
    shadow_score = ScoreSummary(
        value=round(adjusted, 6),
        source=f"score_breakdown.overall+runtime_state.{action}.v1",
    )
    runtime_adjustment = RuntimeAdjustmentSummary(
        value=round(delta, 6),
        source=f"planner.runtime_adjustment.{action}.v1",
        formula_version="v1",
        shadow_only=False,
    )
    rerank_reason = RerankReason(
        code=f"shadow_{action}",
        message=(
            "Runtime rerank uses final_score as the audited ordering signal for "
            "candidate ranking and default recommendation."
        ),
        shadow_only=False,
        runtime_state_fields=[
            "runtime_state.p_success",
            "runtime_state.p_structural_failure",
            "runtime_state.recovery_margin",
            "runtime_state.expected_remaining_cost",
            "runtime_state.evidence_sufficiency",
        ],
        candidate_metric_fields=[
            "score_breakdown.overall",
            "score_breakdown.confidence",
            "score_breakdown.risk",
            "score_breakdown.cost",
            "score_breakdown.fallback_depth",
            "score_breakdown.feasibility",
        ],
        tool_metadata_fields=[],
        factors=factors,
    )
    explanation_fragment = (
        "Runtime rerank records static_score, runtime_adjustment, and final_score separately; "
        f"static_score={overall:.2f}, runtime_adjustment={delta:.2f}, final_score={adjusted:.2f}; "
        f"signals use p_success={p_success:.2f}, p_structural_failure={p_structural_failure:.2f}, "
        f"recovery_margin={recovery_margin:.2f}, expected_remaining_cost={expected_remaining_cost:.2f}, "
        f"evidence_sufficiency={evidence_sufficiency:.2f}; "
        f"shadow_action={action} because {reason}."
    )
    return _RuntimeShadowDecision(
        shadow_score=shadow_score.model_dump(),
        final_score=final_score.model_dump(),
        runtime_adjustment=runtime_adjustment.model_dump(),
        rerank_reason=rerank_reason.model_dump(),
        shadow_action=action,
        shadow_reason=reason,
        explanation_fragment=explanation_fragment,
    )


def _build_runtime_adjustment_factor(
    *,
    category: Literal["cost", "risk", "recovery", "evidence", "policy"],
    signal: str,
    source: str,
    contribution: float,
    message: str,
) -> RuntimeAdjustmentFactor:
    return RuntimeAdjustmentFactor(
        category=category,
        signal=signal,
        source=source,
        contribution=round(contribution, 6),
        message=message,
    )


def _resolve_shadow_action(
    *,
    candidate_kind: str,
    payload: Plan | PlanPatch,
    p_success: float,
    p_structural_failure: float,
    recovery_margin: float,
    budget_pressure: float,
    cost_pressure: float,
) -> tuple[str, str]:
    if (
        p_success <= 0.20
        and budget_pressure >= 0.85
        and recovery_margin <= 0.20
    ):
        return (
            "stop",
            "success probability is low, budget pressure is high, and recovery headroom is nearly exhausted",
        )
    if candidate_kind == "patch":
        if p_structural_failure >= 0.55 and recovery_margin <= 0.1:
            return (
                "suffix_replan",
                "structural failure pressure is high and local recovery margin is low",
            )
        return (
            "patch_local",
            "failure still looks local and recovery margin remains acceptable",
        )
    if candidate_kind == "replan":
        replan_mode = ""
        if isinstance(payload, Plan):
            metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
            raw_mode = metadata.get("replan_mode")
            if isinstance(raw_mode, str):
                replan_mode = raw_mode
        if replan_mode == "suffix_replan":
            return (
                "suffix_replan",
                "runtime pressure favors preserving the validated prefix and replacing the suffix",
            )
        return (
            "continue",
            "runtime state does not justify escalating beyond the current suffix plan",
        )
    return (
        "continue",
        "runtime state is only attached for shadow comparison and does not change planning semantics",
    )


def _infer_candidate_kind(payload: Plan | PlanPatch) -> str:
    if isinstance(payload, PlanPatch):
        return "patch"
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    if isinstance(metadata.get("replan_mode"), str):
        return "replan"
    return "plan"


def _safe_non_negative_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return 0.0
    return parsed


def _safe_runtime_margin(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_default_recommendation_reason(
    *,
    candidate_kind: str,
    candidate_id: str,
    default_candidate: PendingActionCandidate,
    static_candidate: PendingActionCandidate | None = None,
    rerank_applied: bool,
) -> dict[str, Any]:
    message = (
        f"{candidate_kind} candidate {candidate_id} is the current default "
        "recommendation after deterministic static ranking."
    )
    selection_basis: Literal["static_score", "final_score"] = "static_score"
    rerank_shadow_only = True
    static_candidate_id = None
    static_score_gap = None
    if rerank_applied:
        selection_basis = "final_score"
        rerank_shadow_only = False
        static_candidate_id = (
            static_candidate.candidate_id if static_candidate is not None else None
        )
        if static_candidate is not None:
            static_score_gap = round(
                _extract_score_value(default_candidate, FINAL_SCORE_METADATA_KEY)
                - _extract_score_value(static_candidate, FINAL_SCORE_METADATA_KEY),
                6,
            )
            if static_candidate_id != candidate_id:
                message = (
                    f"{candidate_kind} candidate {candidate_id} becomes the current "
                    "default recommendation after runtime reranking by final_score. "
                    f"Static default was {static_candidate_id}, final_score gap={static_score_gap:+.6f}."
                )
            else:
                message = (
                    f"{candidate_kind} candidate {candidate_id} remains the default "
                    "recommendation after runtime reranking by final_score."
                )
    reason = RecommendationReason(
        code=f"{candidate_kind}_ranked_first",
        message=message,
        selection_basis=selection_basis,
        rerank_applied=rerank_applied,
        static_candidate_id=static_candidate_id,
        static_score_gap=static_score_gap,
        shadow_only=rerank_shadow_only,
    )
    return reason.model_dump()


def _extract_score_value(candidate: PendingActionCandidate, metadata_key: str) -> float:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    score = metadata.get(metadata_key)
    if not isinstance(score, dict):
        return 0.0
    return _safe_float(score.get("value"), default=0.0)


def _summarize_rerank_reason(candidate: PendingActionCandidate) -> str:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    rerank_reason = metadata.get(RERANK_REASON_METADATA_KEY)
    if not isinstance(rerank_reason, dict):
        return "Runtime rerank reasons are attached in candidate metadata."

    factors = rerank_reason.get("factors")
    if not isinstance(factors, list):
        return str(rerank_reason.get("message") or "Runtime rerank reasons are attached in candidate metadata.")

    category_labels = {
        "cost": "remaining cost pressure",
        "risk": "structural risk pressure",
        "recovery": "recovery margin",
        "evidence": "evidence confidence",
        "policy": "stop guard",
    }
    categories: list[str] = []
    for factor in factors:
        if not isinstance(factor, dict):
            continue
        contribution = _safe_float(factor.get("contribution"), default=0.0)
        if abs(contribution) <= 1e-9:
            continue
        label = category_labels.get(str(factor.get("category") or ""), "")
        if label and label not in categories:
            categories.append(label)
    if not categories:
        return str(rerank_reason.get("message") or "Runtime rerank reasons are attached in candidate metadata.")
    return "Runtime rerank reasons include " + ", ".join(categories) + "."


def _build_pending_action_runtime_metadata(
    *,
    default_candidate: PendingActionCandidate,
    default_recommendation: str | None,
    waiting_reason: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    candidate_metadata = (
        default_candidate.metadata
        if isinstance(default_candidate.metadata, dict)
        else {}
    )
    waiting_summary: dict[str, Any] = {
        "selected_candidate_id": default_candidate.candidate_id,
        "waiting_reason": waiting_reason,
    }
    if default_recommendation:
        waiting_summary["default_recommendation"] = default_recommendation
    for key in (
        RUNTIME_STATE_SUMMARY_METADATA_KEY,
        DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
        STATIC_SCORE_METADATA_KEY,
        RUNTIME_ADJUSTMENT_METADATA_KEY,
        FINAL_SCORE_METADATA_KEY,
        RERANK_REASON_METADATA_KEY,
        ACTION_SCORE_METADATA_KEY,
        SHADOW_SCORE_METADATA_KEY,
    ):
        value = candidate_metadata.get(key)
        if value is not None:
            waiting_summary[key] = value
    if waiting_summary:
        metadata[WAITING_RUNTIME_SUMMARY_METADATA_KEY] = waiting_summary
    return metadata


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
    layer = ""
    if isinstance(payload.metadata, dict):
        raw_layer = payload.metadata.get("recovery_layer")
        if isinstance(raw_layer, str) and raw_layer:
            layer = f" layer={raw_layer}"
    return f"patch_ops={len(payload.operations)} ops={','.join(ops)}{layer}"


def _extract_patch_candidate_metadata(payload: PlanPatch) -> dict:
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    extracted: dict[str, object] = {}
    for key in (
        "strategy",
        "recovery_layer",
        "recovery_layer_rank",
        "reason",
        "capability_id",
        "from_tool",
        "to_tool",
        "request_reason",
    ):
        value = metadata.get(key)
        if value is not None:
            extracted[key] = value
    replacement_matrix = metadata.get("replacement_matrix")
    if isinstance(replacement_matrix, (tuple, list)):
        extracted["replacement_matrix"] = list(replacement_matrix)
    return extracted


def _patch_layer_rank(payload: Plan | PlanPatch) -> int:
    if isinstance(payload, Plan):
        return 999
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    raw_rank = metadata.get("recovery_layer_rank")
    try:
        return int(raw_rank)
    except (TypeError, ValueError):
        pass
    raw_layer = metadata.get("recovery_layer")
    if isinstance(raw_layer, str):
        return _PATCH_LAYER_PRIORITY.get(raw_layer, 999)
    return 999


def _score_payload(
    payload: Plan | PlanPatch,
    registry: Sequence[ToolSpec],
    *,
    score_weights: dict[str, float] | None = None,
) -> dict[str, float]:
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
    normalized_weights = _normalize_score_weights(score_weights or _DEFAULT_SCORE_WEIGHTS)
    overall = (
        normalized_weights["feasibility"] * feasibility
        + normalized_weights["objective"] * objective
        + normalized_weights["risk"] * risk
        + normalized_weights["cost"] * cost
        + normalized_weights["confidence"] * confidence
        + normalized_weights["tool_readiness"] * tool_readiness
        + normalized_weights["tool_coverage"] * tool_coverage
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


def _build_s5_scoring_contract(
    score_weights: dict[str, float],
) -> dict[str, Any]:
    return {
        "stage_id": _S5_STAGE_ID,
        "stage_name": _S5_STAGE_NAME,
        "field_order": {
            "inputs": list(_S5_INPUT_FIELDS),
            "outputs": list(_S5_OUTPUT_FIELDS),
        },
        "inputs": {
            "candidates": "list[PendingActionCandidate]",
            "metrics": "dict[str,float]",
        },
        "outputs": {
            "score_breakdown": "dict[str,float]",
            "top_k": "list[PendingActionCandidate]",
            "default_recommendation": "str",
            "explanation": "str",
        },
        "weights": dict(score_weights),
    }


def _resolve_score_weights(task_constraints: dict[str, Any]) -> dict[str, float]:
    raw_weights = task_constraints.get("score_weights")
    if not isinstance(raw_weights, dict):
        raw_objective_weights = task_constraints.get("objective_weights")
        if isinstance(raw_objective_weights, dict):
            raw_weights = raw_objective_weights
        else:
            raw_weights = {}

    merged = dict(_DEFAULT_SCORE_WEIGHTS)
    for raw_key, raw_value in raw_weights.items():
        if not isinstance(raw_key, str):
            continue
        key = _SCORE_WEIGHT_KEY_ALIASES.get(raw_key, raw_key)
        if key not in merged:
            continue
        parsed = _parse_positive_float(raw_value)
        if parsed is None:
            continue
        merged[key] = parsed
    return _normalize_score_weights(merged)


def _normalize_score_weights(weights: dict[str, float]) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for key in _DEFAULT_SCORE_WEIGHTS:
        raw_value = weights.get(key, _DEFAULT_SCORE_WEIGHTS[key])
        parsed = _parse_positive_float(raw_value)
        cleaned[key] = parsed if parsed is not None else _DEFAULT_SCORE_WEIGHTS[key]
    total = sum(cleaned.values())
    if total <= 0:
        return dict(_DEFAULT_SCORE_WEIGHTS)
    return {
        key: round(value / total, 6)
        for key, value in cleaned.items()
    }


def _parse_positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


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
    try:
        adapter = get_adapter(spec.id)
    except KeyError:
        adapter = None
    if adapter is not None:
        try:
            health = adapter.healthcheck()
        except Exception:
            health = {"status": "degraded"}
        status = str(health.get("status") or "ready")
        if status == "unavailable":
            base -= 0.55
        elif status == "degraded":
            base -= 0.22
        elif status == "ready":
            base += 0.05
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


def _rank_patch_alternatives(
    *,
    registry: Sequence[ToolSpec],
    capability: str,
    available_inputs: Set[str],
    exclude_tool: str,
) -> List[ToolSpec]:
    ranked = _rank_candidate_tools(
        registry=registry,
        capability=capability,
        available_inputs=available_inputs,
        exclude_tool=exclude_tool,
    )
    indexed = {tool.id: idx for idx, tool in enumerate(ranked)}
    ranked.sort(
        key=lambda tool: (
            _replacement_matrix_rank(capability, tool.id),
            indexed.get(tool.id, 999),
            tool.id,
        )
    )
    return ranked


def _replacement_matrix_rank(capability: str, tool_id: str) -> int:
    order = _P0_CAPABILITY_REPLACEMENT_MATRIX.get(capability, ())
    if not order:
        return 999
    try:
        return order.index(tool_id)
    except ValueError:
        return len(order) + 1


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


def _materialize_missing_plan_inputs(
    plan: Plan,
    registry: Sequence[ToolSpec],
    task: ProteinDesignTask,
) -> Plan:
    registry_map = {spec.id: spec for spec in registry}
    output_sources: dict[str, str] = {}
    resolved_steps: list[PlanStep] = []

    for step in plan.steps:
        spec = registry_map.get(step.tool)
        if spec is None:
            resolved_steps.append(step)
            continue

        resolved_inputs = _fill_missing_required_inputs(
            spec=spec,
            task=task,
            existing_inputs=step.inputs,
            output_sources=output_sources,
        )
        resolved_steps.append(
            step.model_copy(update={"inputs": resolved_inputs}, deep=True)
        )

        for output_name in spec.outputs:
            output_sources[output_name] = step.id

    merged_constraints = dict(task.constraints or {})
    merged_constraints.update(plan.constraints or {})
    return plan.model_copy(
        update={
            "steps": resolved_steps,
            "constraints": merged_constraints,
        },
        deep=True,
    )


def _fill_missing_required_inputs(
    *,
    spec: ToolSpec,
    task: ProteinDesignTask,
    existing_inputs: dict[str, Any],
    output_sources: dict[str, str],
) -> dict[str, Any]:
    resolved_inputs = dict(existing_inputs)
    constraints = task.constraints or {}
    template = _extract_template_pdb(constraints)
    defaults = {
        "goal": task.goal,
        "length_range": _extract_length_range(constraints),
        "prompt": constraints.get("prompt"),
        "template": template,
        "pdb_path": template,
    }

    for required_key in spec.inputs:
        if required_key in resolved_inputs:
            continue
        if required_key in constraints:
            resolved_inputs[required_key] = constraints[required_key]
            continue
        source_step_id = output_sources.get(required_key)
        if source_step_id is not None:
            resolved_inputs[required_key] = f"{source_step_id}.{required_key}"
            continue
        default_value = defaults.get(required_key)
        if default_value is not None:
            resolved_inputs[required_key] = default_value

    return resolved_inputs


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
_S1_STAGE_ID = "S1"
_S1_STAGE_NAME = "sequence_exploration"
_S1_SEQUENCE_SOURCE_PRIMARY = "primary"
_S1_SEQUENCE_SOURCE_FALLBACK = "fallback"
_S4_STAGE_ID = "S4"
_S4_STAGE_NAME = "structure_conditioned_refinement"
_S4_DEFAULT_MAX_ITERATIONS = 3
_S4_DEFAULT_CONVERGENCE_DELTA = 0.01
_S4_DEFAULT_MAX_DEGRADATION_ROUNDS = 1
_S1_INPUT_FIELDS = ("goal", "length_range", "prompt", "template")
_S1_OUTPUT_FIELDS = (
    "sequence",
    "candidates",
    "candidate_confidence",
    "candidate_source",
)


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
    for key in ("template", "structure_template_pdb", "pdb_path"):
        value = constraints.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _collect_sequence_exploration_inputs(constraints: dict) -> Set[str]:
    inputs: Set[str] = set(constraints.keys())
    inputs.add("goal")
    template = _extract_template_pdb(constraints)
    if template:
        inputs.update({"template", "structure_template_pdb", "pdb_path"})
    return inputs


def _extract_structure_refinement_config(constraints: dict) -> dict:
    local = (
        constraints.get("structure_refinement")
        if isinstance(constraints.get("structure_refinement"), dict)
        else {}
    )

    max_iterations_raw = local.get("max_iterations", constraints.get("s4_max_iterations"))
    convergence_raw = local.get(
        "convergence_delta",
        constraints.get("s4_convergence_delta"),
    )
    max_degradation_raw = local.get(
        "max_degradation_rounds",
        constraints.get("s4_max_degradation_rounds"),
    )

    try:
        max_iterations = int(max_iterations_raw)
    except (TypeError, ValueError):
        max_iterations = _S4_DEFAULT_MAX_ITERATIONS
    max_iterations = max(1, max_iterations)

    try:
        convergence_delta = float(convergence_raw)
    except (TypeError, ValueError):
        convergence_delta = _S4_DEFAULT_CONVERGENCE_DELTA
    convergence_delta = max(0.0, convergence_delta)

    try:
        max_degradation_rounds = int(max_degradation_raw)
    except (TypeError, ValueError):
        max_degradation_rounds = _S4_DEFAULT_MAX_DEGRADATION_ROUNDS
    max_degradation_rounds = max(0, max_degradation_rounds)

    return {
        "max_iterations": max_iterations,
        "convergence_delta": convergence_delta,
        "max_degradation_rounds": max_degradation_rounds,
    }


def _build_s1_io_contract(task: ProteinDesignTask) -> dict:
    constraints = task.constraints or {}
    prompt = constraints.get("prompt")
    return {
        "inputs": {
            "goal": task.goal,
            "length_range": _extract_length_range(constraints),
            "prompt": prompt if isinstance(prompt, str) and prompt else None,
            "template": _extract_template_pdb(constraints),
        },
        "outputs": {
            "sequence": "str",
            "candidates": "list",
            "candidate_confidence": "score_breakdown.confidence",
            "candidate_source": "metadata.sequence_source",
        },
        "field_order": {
            "inputs": list(_S1_INPUT_FIELDS),
            "outputs": list(_S1_OUTPUT_FIELDS),
        },
    }


def _collect_s1_fallback_tool_ids(
    *,
    registry: Sequence[ToolSpec],
    primary_tool_id: str,
    available_inputs: Set[str],
) -> List[str]:
    ranked = _rank_sequence_exploration_tools(
        registry=registry,
        available_inputs=available_inputs,
        exclude_tool=primary_tool_id,
    )
    return [spec.id for spec in ranked]


def _attach_s1_contract_to_step(
    *,
    step: PlanStep,
    task: ProteinDesignTask,
    selected_tool: ToolSpec,
    primary_tool_id: str,
    fallback_tool_ids: Sequence[str],
    source_tier: Literal["primary", "fallback"],
    source_reason: str,
) -> PlanStep:
    metadata = {**(step.metadata or {})}
    metadata["stage_id"] = _S1_STAGE_ID
    metadata["stage_name"] = _S1_STAGE_NAME
    metadata["sequence_source"] = source_tier
    metadata["sequence_source_tool_id"] = selected_tool.id
    metadata["candidate_confidence_field"] = "score_breakdown.confidence"
    metadata["s1_contract"] = _build_s1_io_contract(task)
    metadata["lineage"] = {
        "stage_id": _S1_STAGE_ID,
        "strategy": "toolkg_capability_topk",
        "primary_tool_id": primary_tool_id,
        "selected_tool_id": selected_tool.id,
        "fallback_tool_ids": list(fallback_tool_ids),
        "source_tier": source_tier,
        "source_reason": source_reason,
        "capability_id": _primary_capability(selected_tool),
        "io_type": selected_tool.io_type or "unknown",
        "adapter_mode": selected_tool.adapter_mode,
    }
    return step.model_copy(update={"metadata": metadata}, deep=True)


def _extract_primary_s1_tool_id(plan: Plan) -> str | None:
    for step in plan.steps:
        if _is_sequence_exploration_step(step):
            return step.tool
    return None


def _extract_s1_candidate_metadata(plan: Plan) -> dict:
    for step in plan.steps:
        if not _is_sequence_exploration_step(step):
            continue
        metadata = step.metadata if isinstance(step.metadata, dict) else {}
        lineage = metadata.get("lineage")
        s1_contract = metadata.get("s1_contract")
        payload: dict = {
            "stage_id": _S1_STAGE_ID,
            "sequence_source": metadata.get("sequence_source"),
            "sequence_source_tool_id": metadata.get("sequence_source_tool_id"),
        }
        if isinstance(lineage, dict):
            payload["lineage"] = lineage
        if isinstance(s1_contract, dict):
            payload["s1_contract"] = s1_contract
        return payload
    return {}


def _ensure_s1_contract_metadata(
    *,
    task: ProteinDesignTask,
    plan: Plan,
    registry: Sequence[ToolSpec],
) -> Plan:
    if not _is_de_novo_task(task) or not plan.steps:
        return plan
    step_index = next(
        (
            idx
            for idx, step in enumerate(plan.steps)
            if _is_sequence_exploration_step(
                step,
                _find_tool_spec(registry, step.tool),
            )
        ),
        None,
    )
    if step_index is None:
        return plan
    selected_step = plan.steps[step_index]
    selected_tool = _find_tool_spec(registry, selected_step.tool)
    if selected_tool is None:
        return plan

    inputs = _collect_sequence_exploration_inputs(task.constraints or {})
    fallback_tool_ids = _collect_s1_fallback_tool_ids(
        registry=registry,
        primary_tool_id=selected_tool.id,
        available_inputs=inputs,
    )
    source_tier = (
        _S1_SEQUENCE_SOURCE_PRIMARY
        if selected_tool.id not in set(fallback_tool_ids)
        else _S1_SEQUENCE_SOURCE_FALLBACK
    )
    patched_step = _attach_s1_contract_to_step(
        step=selected_step,
        task=task,
        selected_tool=selected_tool,
        primary_tool_id=selected_tool.id,
        fallback_tool_ids=fallback_tool_ids,
        source_tier=source_tier,
        source_reason="base_plan",
    )
    patched_steps = [step.model_copy(deep=True) for step in plan.steps]
    patched_steps[step_index] = patched_step
    return plan.model_copy(update={"steps": patched_steps}, deep=True)


def _rank_sequence_exploration_tools(
    *,
    registry: Sequence[ToolSpec],
    available_inputs: Set[str],
    exclude_tool: str,
) -> List[ToolSpec]:
    ranked: List[ToolSpec] = []
    seen: Set[str] = set()
    for capability in ("sequence_generation", "sequence_design"):
        candidates = _rank_candidate_tools(
            registry=registry,
            capability=capability,
            available_inputs=available_inputs,
            exclude_tool=exclude_tool,
        )
        for candidate in candidates:
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            ranked.append(candidate)
    return ranked


def _materialize_inputs_for_tool(
    *,
    base_inputs: dict,
    task: ProteinDesignTask,
    target_tool: ToolSpec,
) -> dict | None:
    resolved_inputs = dict(base_inputs)
    constraints = task.constraints or {}
    template = _extract_template_pdb(constraints)

    defaults = {
        "goal": task.goal,
        "length_range": _extract_length_range(constraints),
        "prompt": constraints.get("prompt"),
        "template": template,
        "pdb_path": template,
    }
    for key in _S1_INPUT_FIELDS:
        value = defaults.get(key)
        if key not in resolved_inputs and value is not None:
            resolved_inputs[key] = value

    for required_key in target_tool.inputs:
        if required_key in resolved_inputs:
            continue
        if required_key in constraints:
            resolved_inputs[required_key] = constraints[required_key]
            continue
        value = defaults.get(required_key)
        if value is not None:
            resolved_inputs[required_key] = value
            continue
        return None

    return resolved_inputs


def _is_sequence_exploration_step(
    step: PlanStep,
    spec: ToolSpec | None = None,
) -> bool:
    metadata = step.metadata if isinstance(step.metadata, dict) else {}
    if metadata.get("stage_id") == _S1_STAGE_ID:
        return True
    capability = _extract_step_capability(metadata)
    if capability == "sequence_generation":
        return True
    return spec is not None and "sequence_generation" in set(spec.capabilities)


def _build_de_novo_plan(
    task: ProteinDesignTask,
    registry: Sequence[ToolSpec],
) -> Plan:
    constraints = task.constraints or {}
    available_inputs = _collect_sequence_exploration_inputs(constraints)
    template_pdb = _extract_template_pdb(constraints)

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
    available_inputs.update(structure_tool.outputs)

    try:
        refinement_tool = _select_tool_by_capability(
            registry=registry,
            capability="sequence_design",
            available_inputs=available_inputs,
            safety_level=safety_level,
            io_hint={"inputs": ["pdb_path"]},
            prefer_remote=prefer_remote,
        )
    except ValueError:
        try:
            refinement_tool = _find_tool_spec(registry, "protein_mpnn")
        except ValueError:
            fallback_inputs = _collect_registry_inputs(registry)
            refinement_tool = _select_tool_by_capability(
                registry=registry,
                capability="sequence_design",
                available_inputs=fallback_inputs,
                safety_level=safety_level,
                io_hint={"inputs": ["pdb_path"]},
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
        step_inputs["template"] = template_pdb

    fallback_tool_ids = _collect_s1_fallback_tool_ids(
        registry=registry,
        primary_tool_id=sequence_tool.id,
        available_inputs=available_inputs,
    )
    s1_step = _attach_s1_contract_to_step(
        step=PlanStep(
            id="S1",
            tool=sequence_tool.id,
            inputs=step_inputs,
            metadata={},
        ),
        task=task,
        selected_tool=sequence_tool,
        primary_tool_id=sequence_tool.id,
        fallback_tool_ids=fallback_tool_ids,
        source_tier=_S1_SEQUENCE_SOURCE_PRIMARY,
        source_reason="de_novo_template",
    )
    refinement_config = _extract_structure_refinement_config(constraints)

    s4_inputs: dict = {
        "pdb_path": "S2.pdb_path",
    }
    if length_range:
        s4_inputs["length_range"] = length_range

    steps = [
        s1_step,
        PlanStep(
            id="S2",
            tool=structure_tool.id,
            inputs={"sequence": "S1.sequence"},
            metadata={
                "stage_id": "S2",
                "stage_name": "structure_projection",
            },
        ),
        PlanStep(
            id=_S4_STAGE_ID,
            tool=refinement_tool.id,
            inputs=s4_inputs,
            metadata={
                "stage_id": _S4_STAGE_ID,
                "stage_name": _S4_STAGE_NAME,
                "loop_path": ["S4", "S2", "S3"],
                "loop_control": refinement_config,
                "stop_conditions": {
                    "max_iterations": refinement_config["max_iterations"],
                    "convergence_delta": refinement_config["convergence_delta"],
                    "max_degradation_rounds": refinement_config[
                        "max_degradation_rounds"
                    ],
                },
            },
        ),
        PlanStep(
            id="S2R",
            tool=structure_tool.id,
            inputs={"sequence": "S4.sequence"},
            metadata={
                "stage_id": "S2",
                "stage_name": "structure_projection",
                "source_stage_id": "S4",
            },
        ),
    ]

    explanation = _build_de_novo_explanation(
        sequence_tool.id,
        structure_tool.id,
        refinement_tool.id,
    )

    return Plan(
        task_id=task.task_id,
        steps=steps,
        constraints=task.constraints,
        metadata={},
        explanation=explanation,
    )


def _build_de_novo_explanation(
    sequence_tool_id: str,
    structure_tool_id: str,
    refinement_tool_id: str,
) -> str:
    kg = load_tool_kg()
    tools = {tool.get("id"): tool for tool in kg.get("tools", []) if tool.get("id")}
    capabilities = {
        cap.get("capability_id"): cap
        for cap in kg.get("capabilities", [])
        if cap.get("capability_id")
    }

    sequence_tool = tools.get(sequence_tool_id, {})
    structure_tool = tools.get(structure_tool_id, {})
    refinement_tool = tools.get(refinement_tool_id, {})

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
    refine_name = refinement_tool.get("name") or refinement_tool_id
    refine_desc = refinement_tool.get("description") or ""
    refine_caps = format_caps(refinement_tool)

    compat_from = structure_tool.get("compat", {}).get("from", [])
    compat_note = ""
    if isinstance(compat_from, list) and compat_from:
        compat_note = f"KG compat.from={', '.join(str(item) for item in compat_from)}"

    parts = [
        "de_novo_design 任务采用序列生成→结构预测→结构条件精修→结构重映射链路。",
        f"ProteinToolKG 显示 {seq_name}({sequence_tool_id}) 能力={seq_caps}。{seq_desc}",
        f"ProteinToolKG 显示 {struct_name}({structure_tool_id}) 能力={struct_caps}。{struct_desc}",
        f"ProteinToolKG 显示 {refine_name}({refinement_tool_id}) 能力={refine_caps}。{refine_desc}",
        "S4 按 max_iterations/convergence_delta/max_degradation_rounds 控制迭代停止，并在 S4 后执行结构重映射保证序列-结构一致。",
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
