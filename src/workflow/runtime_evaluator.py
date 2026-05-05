"""RuntimeEvaluator: 统一 utility 计算、runtime adjustment、policy_mode 切换与动作选择。

从 Planner shadow-rerank 与 Workflow action-selector 中抽离核心公式，
输出 ActionUtility 供 Web/CLI 展示推荐动作、预算压力、风险与证据。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, cast

from src.models.contracts import (
    FINAL_SCORE_METADATA_KEY,
    RERANK_REASON_METADATA_KEY,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
    SHADOW_SCORE_METADATA_KEY,
    STATIC_SCORE_METADATA_KEY,
    PendingActionCandidate,
    RerankReason,
    RuntimeAdjustmentFactor,
    RuntimeAdjustmentSummary,
    ScoreSummary,
)
from src.models.runtime_schemas import (
    ActionUtility,
    JsonObject,
    RuntimeStateSchema,
)
from src.models.source_refs import (
    SOURCE_REF_ACTION_UTILITY,
    SOURCE_REF_DEFAULT_ACTION_UTILITY,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
    SOURCE_REF_STATIC_SCORE,
    as_source_refs,
)
from src.workflow.action_features import (
    ActionFeatureDerivation,
    derive_action_features,
)

__all__ = [
    "DYNAMIC_OBSERVATION_ONLY",
    "LITE_BELIEF_STATE",
    "STATIC_GATE",
    "STATIC_TOP1",
    "RuntimeEvaluator",
    "RuntimeEvaluation",
    "compute_runtime_delta",
    "evaluator_policy_trace",
    "policy_disables_rerank",
]

# -- policy mode constants ---------------------------------------------------
STATIC_TOP1 = "static_top1"
STATIC_GATE = "static_gate"
DYNAMIC_OBSERVATION_ONLY = "dynamic_observation_only"
LITE_BELIEF_STATE = "lite_belief_state"

_POLICY_MODES = frozenset(
    {STATIC_TOP1, STATIC_GATE, DYNAMIC_OBSERVATION_ONLY, LITE_BELIEF_STATE}
)
_RERANK_DISABLED_POLICIES = frozenset({STATIC_TOP1, STATIC_GATE})

# -- action space ------------------------------------------------------------
_RUNTIME_ACTIONS = ("continue", "patch_local", "suffix_replan", "stop")

# -- formula constants -------------------------------------------------------
_DELTA_CLAMP = 0.35
_SCORE_CLAMP_MIN = 0.0
_SCORE_CLAMP_MAX = 1.0

_STOP_P_SUCCESS_THRESHOLD = 0.20
_STOP_BUDGET_PRESSURE_THRESHOLD = 0.85
_STOP_RECOVERY_MARGIN_THRESHOLD = 0.20

_STRUCTURAL_FAILURE_THRESHOLD = 0.55
_RECOVERY_MARGIN_LOW = 0.1


# -- public helpers ----------------------------------------------------------


def policy_disables_rerank(policy_mode: str) -> bool:
    """static_top1 / static_gate 不执行运行时重排。"""
    return policy_mode.strip().lower() in _RERANK_DISABLED_POLICIES


def evaluator_policy_trace(policy_mode: str) -> dict[str, object]:
    normalized = policy_mode.strip().lower()
    if normalized not in _POLICY_MODES:
        normalized = LITE_BELIEF_STATE
    return {
        "policy_mode": normalized,
        "rerank_enabled": not policy_disables_rerank(normalized),
        "belief_state_enabled": normalized
        not in {STATIC_TOP1, STATIC_GATE, DYNAMIC_OBSERVATION_ONLY},
    }


# -- shared delta computation ------------------------------------------------


def compute_runtime_delta(
    *,
    p_success: float,
    p_structural_failure: float,
    recovery_margin: float,
    expected_remaining_cost: float,
    evidence_sufficiency: float,
    confidence: float,
    risk: float,
    cost: float,
    fallback_depth: float,
    feasibility: float,
    candidate_kind: str,
    replan_mode: str = "",
) -> tuple[float, str, str, list[RuntimeAdjustmentFactor]]:
    """计算单个候选的 runtime delta、shadow action、action reason 和因子列表。

    供 Planner shadow-rerank hooks 与 RuntimeEvaluator 共享公式。
    """
    budget_pressure = min(max(expected_remaining_cost, 0.0), 1.5)
    cost_pressure = min(budget_pressure, 1.0)
    margin_signal = max(-1.0, min(recovery_margin, 1.0))

    action, action_reason = _resolve_candidate_action_from_signals(
        candidate_kind=candidate_kind,
        replan_mode=replan_mode,
        p_success=p_success,
        p_structural_failure=p_structural_failure,
        recovery_margin=recovery_margin,
        budget_pressure=budget_pressure,
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

    factors = _build_adjustment_factors(
        evidence_effect, evidence_sufficiency_effect,
        risk_effect, recovery_effect, cost_effect,
    )

    if action == "patch_local":
        bonus = 0.04 * fallback_depth
        delta += bonus
        factors.append(_make_factor("recovery", "fallback_depth",
            "score_breakdown.fallback_depth", bonus,
            "Local patchability keeps more recovery options available."))
    elif action == "suffix_replan":
        replan_bonus = 0.02 * feasibility
        replan_penalty = -0.03 * cost_pressure
        delta += replan_bonus + replan_penalty
        factors.append(_make_factor("recovery", "feasibility",
            "score_breakdown.feasibility", replan_bonus,
            "Feasible suffix replacement preserves validated prefix value."))
        factors.append(_make_factor("cost", "cost_pressure",
            "runtime_state.expected_remaining_cost", replan_penalty,
            "Suffix replan still carries residual budget pressure."))
    elif action == "stop":
        penalty = -(0.12 + 0.06 * cost_pressure)
        delta += penalty
        factors.append(_make_factor("policy", "stop_guard",
            "runtime_state.p_success+runtime_state.expected_remaining_cost",
            penalty,
            "Stop guard applies when success is low and cost pressure is already high."))

    delta = max(-_DELTA_CLAMP, min(_DELTA_CLAMP, delta))

    return delta, action, action_reason, factors


# -- main evaluator ----------------------------------------------------------


@dataclass
class RuntimeEvaluation:
    """单次 evaluate_candidates 调用的完整输出。"""

    candidates: list[PendingActionCandidate] = field(default_factory=list)
    static_default_id: str | None = None
    reranked_default_id: str | None = None
    rerank_applied: bool = False
    policy_mode: str = LITE_BELIEF_STATE


class RuntimeEvaluator:
    """..."""

    _policy_mode: str

    def __init__(self, policy_mode: str = LITE_BELIEF_STATE) -> None:
        self._policy_mode = policy_mode.strip().lower()
        if self._policy_mode not in _POLICY_MODES:
            self._policy_mode = LITE_BELIEF_STATE

    # -- public API ----------------------------------------------------------

    @property
    def policy_mode(self) -> str:
        return self._policy_mode

    def evaluate_candidates(
        self,
        candidates: list[PendingActionCandidate],
        runtime_state: RuntimeStateSchema | Mapping[str, object] | None,
    ) -> RuntimeEvaluation:
        """对每个候选计算 runtime_adjustment 与 final_score，按 final_score 降序重排。

        约束:
        - feasibility = 0 的候选不会被复活（final_score 保持 0）
        - static_top1 / static_gate 模式下跳过重排
        """
        if not candidates:
            return RuntimeEvaluation(policy_mode=self._policy_mode)

        state = _coerce_state(runtime_state)
        static_default = _top_static_candidate(candidates)

        if policy_disables_rerank(self._policy_mode):
            return RuntimeEvaluation(
                candidates=list(candidates),
                static_default_id=static_default,
                reranked_default_id=static_default,
                rerank_applied=False,
                policy_mode=self._policy_mode,
            )

        if state is None:
            # 无 runtime state 时走 passthrough
            reranked = [_apply_passthrough(c) for c in candidates]
            reranked.sort(key=_final_score_key, reverse=True)
            top = reranked[0].candidate_id if reranked else None
            return RuntimeEvaluation(
                candidates=reranked,
                static_default_id=static_default,
                reranked_default_id=top,
                rerank_applied=False,
                policy_mode=self._policy_mode,
            )

        # 完整重排
        observation_only = self._policy_mode == DYNAMIC_OBSERVATION_ONLY
        reranked = [
            _apply_runtime_adjustment(c, state, observation_only=observation_only)
            for c in candidates
        ]
        reranked.sort(key=_final_score_key, reverse=True)
        top_id = reranked[0].candidate_id if reranked else None

        return RuntimeEvaluation(
            candidates=reranked,
            static_default_id=static_default,
            reranked_default_id=top_id,
            rerank_applied=True,
            policy_mode=self._policy_mode,
        )

    def select_action(
        self,
        candidates: list[PendingActionCandidate],
        runtime_state: RuntimeStateSchema | Mapping[str, object] | None,
        *,
        allow_auto_stop: bool = False,
        safety_blocked: bool = False,
    ) -> ActionUtility:
        """兼容性动作选择 helper。

        Workflow 级动作选择由 ``recovery.select_workflow_action()`` 负责；
        本方法不得作为 PlanRunner 恢复决策边界。

        硬约束优先级:
        1. safety_block → 候选被阻止，禁止 continue
        2. feasibility = 0 的候选不进入效用比较
        3. auto-stop 仅在满足全部门槛时允许
        """
        state = _coerce_state(runtime_state)
        if state is None:
            return self._default_action_utility("continue", reason="no runtime state")

        # 计算四动作效用
        action_features = derive_action_features(runtime_state=state)
        utilities = self.compute_action_utilities(
            state,
            action_features=action_features,
        )

        # 解析候选建议
        suggested = _top_candidate_action(candidates) if candidates else None

        # 硬约束: safety block
        if safety_blocked and "suffix_replan" in _RUNTIME_ACTIONS:
            replan_util = utilities.get("suffix_replan")
            if replan_util is not None and not self._should_auto_stop(
                utilities, state, allow_auto_stop, action_features=action_features
            ):
                return self._with_hard_constraint(
                    replan_util,
                    ["safety_block_disables_continue"],
                    "safety block escalates to suffix replan",
                )

        # 硬约束: auto-stop
        if self._should_auto_stop(
            utilities, state, allow_auto_stop, action_features=action_features
        ):
            stop_util = utilities.get("stop")
            if stop_util is not None:
                return self._with_hard_constraint(
                    stop_util,
                    ["auto_stop_threshold_met"],
                    "runtime stop threshold met; route through terminal_stop",
                )

        # 建议动作优先（除非硬阻止）
        if suggested is not None and suggested != "stop":
            return utilities.get(suggested) or self._best_utility(utilities)

        return self._best_utility(utilities)

    def compute_action_utilities(
        self,
        runtime_state: RuntimeStateSchema | Mapping[str, object],
        *,
        action_features: ActionFeatureDerivation | None = None,
    ) -> dict[str, ActionUtility]:
        """计算全部四个动作的标准化效用值。

        设计文档公式 (runtime-adaptation-formalization.md §7):
          s = p_success, f = p_structural_failure,
          r = recovery_margin, b = budget_pressure, e = evidence_sufficiency
        """
        state = _coerce_state(runtime_state)
        if state is None:
            return {
                a: self._default_action_utility(a, reason="no runtime state")
                for a in _RUNTIME_ACTIONS
            }

        s = _safe_clip(state.get("p_success"), 0.5)
        f_param = _safe_clip(state.get("p_structural_failure"), 0.25)
        r_margin = _safe_clip(state.get("recovery_margin"), 0.6)
        e_suff = _safe_clip(state.get("evidence_sufficiency"), 0.5)
        derivation = action_features or derive_action_features(runtime_state=state)
        feature_values = derivation.values
        lp = feature_values["local_patchability"]
        er_val = feature_values["evidence_reusability"]
        pp = feature_values["prefix_preservability"]
        br = feature_values["budget_relief"]
        gr = feature_values["goal_realignment"]
        safety_term = feature_values["safety_terminality"]
        iv = feature_values["intervention_value"]
        b = feature_values["budget_pressure"]
        utility_metadata: JsonObject = {
            "derived_features": derivation.features_metadata(),
            "action_feature_source_refs": list(derivation.source_refs),
        }

        bp = round(min(max(b, 0.0), 1.0), 6)
        return {
            "continue": ActionUtility(
                action="continue",
                utility=round(max(0.0, min(1.0, 0.38 * s + 0.14 * e_suff + 0.12 * r_margin - 0.22 * f_param - 0.14 * b)), 6),
                budget_pressure=bp,
                source_refs=as_source_refs(*SOURCE_REF_ACTION_UTILITY),
                metadata=utility_metadata,
            ),
            "patch_local": ActionUtility(
                action="patch_local",
                utility=round(max(0.0, min(1.0, 0.20 * s + 0.24 * r_margin + 0.18 * lp + 0.12 * er_val - 0.14 * f_param - 0.12 * b)), 6),
                budget_pressure=bp,
                source_refs=as_source_refs(*SOURCE_REF_ACTION_UTILITY),
                metadata=utility_metadata,
            ),
            "suffix_replan": ActionUtility(
                action="suffix_replan",
                utility=round(max(0.0, min(1.0, 0.18 * (1.0 - s) + 0.20 * f_param + 0.16 * (1.0 - r_margin) + 0.18 * pp + 0.14 * br + 0.14 * gr)), 6),
                budget_pressure=bp,
                source_refs=as_source_refs(*SOURCE_REF_ACTION_UTILITY),
                metadata=utility_metadata,
            ),
            "stop": ActionUtility(
                action="stop",
                utility=round(max(0.0, min(1.0, 0.32 * (1.0 - s) + 0.24 * b + 0.18 * (1.0 - r_margin) + 0.16 * safety_term + 0.10 * (1.0 - iv))), 6),
                budget_pressure=bp,
                intervention_value=round(iv, 6),
                terminal_reason="auto_stop: low success, high budget pressure, exhausted recovery margin",
                source_refs=as_source_refs(*SOURCE_REF_ACTION_UTILITY),
                metadata=utility_metadata,
            ),
        }

    # -- internal helpers ----------------------------------------------------

    def _should_auto_stop(
        self,
        utilities: dict[str, ActionUtility],
        state: dict[str, object],
        allow_auto_stop: bool,
        *,
        action_features: ActionFeatureDerivation | None = None,
    ) -> bool:
        if not allow_auto_stop:
            return False
        stop_u = utilities.get("stop")
        if stop_u is None:
            return False
        s = _safe_clip(state.get("p_success"), 0.5)
        r_margin = _safe_clip(state.get("recovery_margin"), 0.6)
        derivation = action_features or derive_action_features(runtime_state=state)
        b = derivation.values["budget_pressure"]
        iv = derivation.values["intervention_value"]
        return (
            stop_u.utility >= 0.72
            and s <= _STOP_P_SUCCESS_THRESHOLD
            and b >= _STOP_BUDGET_PRESSURE_THRESHOLD
            and r_margin <= _STOP_RECOVERY_MARGIN_THRESHOLD
            and iv <= 0.25
        )

    @staticmethod
    def _best_utility(
        utilities: dict[str, ActionUtility],
    ) -> ActionUtility:
        best = max(utilities.values(), key=lambda u: u.utility)
        # stop 需要显著优势才覆盖第二选择
        if best.action == "stop":
            others = [u for a, u in utilities.items() if a != "stop"]
            second_best = max(others, key=lambda u: u.utility) if others else None
            if second_best is not None and best.utility - second_best.utility < 0.06:
                return second_best
        return best

    @staticmethod
    def _default_action_utility(
        action: Literal["continue", "patch_local", "suffix_replan", "stop"],
        *,
        reason: str,
    ) -> ActionUtility:
        return ActionUtility(
            action=action,
            utility=0.5,
            source_refs=as_source_refs(*SOURCE_REF_DEFAULT_ACTION_UTILITY),
            metadata={"default_reason": reason},
        )

    @staticmethod
    def _with_hard_constraint(
        utility: ActionUtility,
        constraints: list[str],
        reason: str,
    ) -> ActionUtility:
        utility.hard_constraints = list(
            dict.fromkeys(utility.hard_constraints + constraints)
        )
        utility.metadata = dict(utility.metadata, hard_constraint_reason=reason)
        return utility


# -- per-candidate runtime adjustment ----------------------------------------


def _apply_runtime_adjustment(
    candidate: PendingActionCandidate,
    state: dict[str, object],
    *,
    observation_only: bool = False,
) -> PendingActionCandidate:
    """就地更新候选的 metadata (runtime_adjustment / final_score / rerank_reason)。"""
    metadata = dict(candidate.metadata)
    raw_bd = metadata.get("score_breakdown")
    score_breakdown: dict[str, float] = {}
    if isinstance(raw_bd, dict):
        bd = cast(dict[str, object], raw_bd)
        for k, v in bd.items():
            if isinstance(v, (int, float)):
                score_breakdown[k] = float(v)

    overall = float(score_breakdown.get("overall", 0.5))
    feasibility = float(score_breakdown.get("feasibility", 0.5))

    # feasibility = 0 的候选不复活
    if feasibility <= 0.0:
        return _attach_passthrough_metadata(candidate, metadata, overall, "feasibility_zero")

    if observation_only:
        return _attach_passthrough_metadata(candidate, metadata, overall, "observation_only")

    p_success = _safe_clip(state.get("p_success"), 0.5)
    p_structural_failure = _safe_clip(state.get("p_structural_failure"), 0.25)
    recovery_margin = _safe_clip(state.get("recovery_margin"), 0.6)
    evidence_sufficiency = _safe_clip(state.get("evidence_sufficiency"), 0.5)
    expected_remaining_cost = max(_safe_float(state.get("expected_remaining_cost"), 1.0), 0.0)

    confidence = float(score_breakdown.get("confidence", overall))
    risk = float(score_breakdown.get("risk", overall))
    cost = float(score_breakdown.get("cost", overall))
    fallback_depth = float(score_breakdown.get("fallback_depth", 0.5))

    # 候选类型推断
    candidate_kind = _infer_kind(metadata)

    delta, action, action_reason, factors = compute_runtime_delta(
        p_success=p_success,
        p_structural_failure=p_structural_failure,
        recovery_margin=recovery_margin,
        expected_remaining_cost=expected_remaining_cost,
        evidence_sufficiency=evidence_sufficiency,
        confidence=confidence,
        risk=risk,
        cost=cost,
        fallback_depth=fallback_depth,
        feasibility=feasibility,
        candidate_kind=candidate_kind,
        replan_mode=str(metadata.get("replan_mode", "")),
    )

    adjusted = max(_SCORE_CLAMP_MIN, min(_SCORE_CLAMP_MAX, overall + delta))

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
            "score_breakdown.overall", "score_breakdown.confidence",
            "score_breakdown.risk", "score_breakdown.cost",
            "score_breakdown.fallback_depth", "score_breakdown.feasibility",
        ],
        tool_metadata_fields=[],
        factors=factors,
    )

    return _attach_rerank_metadata(
        candidate, metadata, overall, delta, adjusted, rerank_reason,
        action, action_reason,
    )


def _apply_passthrough(
    candidate: PendingActionCandidate,
) -> PendingActionCandidate:
    metadata = dict(candidate.metadata)
    overall = _extract_overall(metadata)
    return _attach_passthrough_metadata(candidate, metadata, overall, "no_runtime_state")


def _attach_passthrough_metadata(
    candidate: PendingActionCandidate,
    metadata: dict[str, object],
    overall: float,
    reason_code: str,
) -> PendingActionCandidate:
    rerank_reason = RerankReason(
        code=f"shadow_passthrough_{reason_code}",
        message=(
            "No runtime_state was provided or rerank is disabled, "
            "so final_score mirrors static_score and remains shadow-only."
        ),
        shadow_only=True,
        runtime_state_fields=[],
        candidate_metric_fields=["score_breakdown.overall"],
        tool_metadata_fields=[],
        factors=[],
    )
    return _attach_rerank_metadata(
        candidate, metadata, overall, 0.0, overall, rerank_reason,
        "continue", "runtime_state is not available",
    )


def _attach_rerank_metadata(
    candidate: PendingActionCandidate,
    metadata: dict[str, object],
    overall: float,
    delta: float,
    adjusted: float,
    rerank_reason: RerankReason,
    shadow_action: str,
    shadow_reason: str,
) -> PendingActionCandidate:
    static_score = ScoreSummary(
        value=round(overall, 6),
        source="score_breakdown.overall.static.v1",
        source_refs=as_source_refs(*SOURCE_REF_STATIC_SCORE),
    )
    final_score = ScoreSummary(
        value=round(adjusted, 6),
        source=f"static_score+runtime_adjustment.{shadow_action}.v1",
        source_refs=as_source_refs(
            *SOURCE_REF_STATIC_SCORE,
            *SOURCE_REF_RUNTIME_ADJUSTMENT,
        ),
    )
    shadow_score = ScoreSummary(
        value=round(adjusted, 6),
        source=f"score_breakdown.overall+runtime_state.{shadow_action}.v1",
        source_refs=as_source_refs(*SOURCE_REF_RUNTIME_ADJUSTMENT),
    )
    runtime_adjustment = RuntimeAdjustmentSummary(
        value=round(delta, 6),
        source=f"planner.runtime_adjustment.{shadow_action}.v1",
        source_refs=as_source_refs(*SOURCE_REF_RUNTIME_ADJUSTMENT),
        formula_version="v1",
        shadow_only=False,
    )

    metadata[STATIC_SCORE_METADATA_KEY] = static_score.model_dump()
    metadata[RUNTIME_ADJUSTMENT_METADATA_KEY] = runtime_adjustment.model_dump()
    metadata[FINAL_SCORE_METADATA_KEY] = final_score.model_dump()
    metadata[SHADOW_SCORE_METADATA_KEY] = shadow_score.model_dump()
    metadata[RERANK_REASON_METADATA_KEY] = rerank_reason.model_dump()
    metadata["shadow_action"] = shadow_action
    metadata["shadow_action_reason"] = shadow_reason

    candidate.metadata = metadata
    return candidate


# -- action resolution ------------------------------------------------------


def _resolve_candidate_action_from_signals(
    *,
    candidate_kind: str,
    replan_mode: str,
    p_success: float,
    p_structural_failure: float,
    recovery_margin: float,
    budget_pressure: float,
) -> tuple[str, str]:
    if p_success <= _STOP_P_SUCCESS_THRESHOLD and budget_pressure >= _STOP_BUDGET_PRESSURE_THRESHOLD and recovery_margin <= _STOP_RECOVERY_MARGIN_THRESHOLD:
        return ("stop", "success probability is low, budget pressure is high, and recovery headroom is nearly exhausted")
    if candidate_kind == "patch":
        if p_structural_failure >= _STRUCTURAL_FAILURE_THRESHOLD and recovery_margin <= _RECOVERY_MARGIN_LOW:
            return ("suffix_replan", "structural failure pressure is high and local recovery margin is low")
        return ("patch_local", "failure still looks local and recovery margin remains acceptable")
    if candidate_kind == "replan":
        if replan_mode == "suffix_replan":
            return ("suffix_replan", "runtime pressure favors preserving the validated prefix and replacing the suffix")
        return ("continue", "runtime state does not justify escalating beyond the current suffix plan")
    return ("continue", "runtime state is only attached for shadow comparison and does not change planning semantics")


# -- factor construction ----------------------------------------------------


def _build_adjustment_factors(
    evidence_effect: float,
    evidence_sufficiency_effect: float,
    risk_effect: float,
    recovery_effect: float,
    cost_effect: float,
) -> list[RuntimeAdjustmentFactor]:
    return [
        _make_factor(
            "evidence", "p_success*confidence",
            "runtime_state.p_success+score_breakdown.confidence",
            evidence_effect,
            "Current evidence and candidate confidence adjust the shadow score.",
        ),
        _make_factor(
            "evidence", "evidence_sufficiency",
            "runtime_state.evidence_sufficiency+score_breakdown.feasibility",
            evidence_sufficiency_effect,
            "Evidence sufficiency raises confidence in routes backed by enough cheap validation.",
        ),
        _make_factor(
            "risk", "p_structural_failure",
            "runtime_state.p_structural_failure+score_breakdown.risk",
            risk_effect,
            "Structural failure pressure reduces the shadow score.",
        ),
        _make_factor(
            "recovery", "recovery_margin*fallback_depth",
            "runtime_state.recovery_margin+score_breakdown.fallback_depth",
            recovery_effect,
            "Recovery headroom and fallback depth shape the shadow rerank bonus.",
        ),
        _make_factor(
            "cost", "expected_remaining_cost",
            "runtime_state.expected_remaining_cost+score_breakdown.cost",
            cost_effect,
            "Remaining cost pressure penalizes expensive suffixes.",
        ),
    ]


def _make_factor(
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


# -- helpers ----------------------------------------------------------------


def _coerce_state(
    runtime_state: RuntimeStateSchema | Mapping[str, object] | None,
) -> dict[str, object] | None:
    if runtime_state is None:
        return None
    if isinstance(runtime_state, RuntimeStateSchema):
        return runtime_state.model_dump()
    return dict(runtime_state)


def _safe_clip(value: object, default: float = 0.5) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v
    return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _extract_overall(metadata: dict[str, object]) -> float:
    score_bd = metadata.get("score_breakdown")
    if isinstance(score_bd, dict):
        bd = cast(dict[str, object], score_bd)
        overall = bd.get("overall")
        if isinstance(overall, (int, float)):
            return float(overall)
    static = metadata.get(STATIC_SCORE_METADATA_KEY)
    if isinstance(static, dict):
        s = cast(dict[str, object], static)
        value = s.get("value")
        if isinstance(value, (int, float)):
            return float(value)
    return 0.5


def _final_score_key(candidate: PendingActionCandidate) -> float:
    metadata = dict(candidate.metadata)
    final = metadata.get(FINAL_SCORE_METADATA_KEY)
    if isinstance(final, dict):
        f = cast(dict[str, object], final)
        value = f.get("value")
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _top_static_candidate(
    candidates: list[PendingActionCandidate],
) -> str | None:
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda c: _extract_overall(dict(c.metadata)),
    )
    return best.candidate_id


def _top_candidate_action(
    candidates: list[PendingActionCandidate],
) -> str | None:
    if not candidates:
        return None
    metadata = dict(candidates[0].metadata)
    action = metadata.get("shadow_action")
    return str(action) if isinstance(action, str) and action else None


def _infer_kind(metadata: dict[str, object]) -> str:
    if metadata.get("replan_mode"):
        return "replan"
    if metadata.get("patch_layer") is not None or metadata.get("patch_span") is not None:
        return "patch"
    return "plan"
