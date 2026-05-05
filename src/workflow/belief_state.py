from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.models.contracts import (
    RuntimeFailureContext,
    RuntimeState,
    RuntimeStateUpdateInput,
    SafetyResult,
    StepResult,
)
from src.models.budget_pressure import derive_budget_pressure

__all__ = [
    "BELIEF_STATE_UPDATE_RULES",
    "BeliefStateUpdateRule",
    "extract_failure_context",
    "update_runtime_state",
]

type BeliefDelta = float | str

_BASELINE_P_SUCCESS = 0.5
_BASELINE_P_STRUCTURAL_FAILURE = 0.25
_BASELINE_RECOVERY_MARGIN = 0.6
_BASELINE_EXPECTED_REMAINING_COST = 1.0
_BASELINE_EVIDENCE_SUFFICIENCY = 0.5
_STRUCTURAL_STAGE_IDS = {"S2", "S3", "S4"}


@dataclass(frozen=True)
class BeliefStateUpdateRule:
    """Lite belief-state 更新规则的可引用表项。"""

    signal: str
    observation: str
    p_success: BeliefDelta = "0"
    p_structural_failure: BeliefDelta = "0"
    recovery_margin: BeliefDelta = "0"
    expected_remaining_cost: BeliefDelta = "0"
    evidence_sufficiency: BeliefDelta = "via evidence_signal smoothing"
    rationale: str = ""


BELIEF_STATE_UPDATE_RULES: tuple[BeliefStateUpdateRule, ...] = (
    BeliefStateUpdateRule(
        signal="step_result.success",
        observation="Any successful StepResult.",
        p_success=0.12,
        p_structural_failure=-0.08,
        recovery_margin=0.06,
        expected_remaining_cost="cost_reward += 0.35; no progress counters: c_t - 1.35",
        rationale="A completed step improves chain viability and frees recovery budget.",
    ),
    BeliefStateUpdateRule(
        signal="step_result.success@structural",
        observation="Successful structural stage or structural tool.",
        p_success=0.04,
        p_structural_failure=-0.05,
        rationale="Structural validation reduces latent structural-failure pressure.",
    ),
    BeliefStateUpdateRule(
        signal="step_result.failed",
        observation="Any failed StepResult.",
        p_success=-0.18,
        p_structural_failure=0.14,
        recovery_margin=-0.12,
        expected_remaining_cost="cost_penalty += 0.75; no progress counters: c_t + 1.25",
        rationale="Failure makes the current suffix less trustworthy and more expensive.",
    ),
    BeliefStateUpdateRule(
        signal="step_result.failed@structural",
        observation="Failure at structural stage or structural tool.",
        p_structural_failure=0.08,
        rationale="Structural failures imply stronger need for suffix replanning.",
    ),
    BeliefStateUpdateRule(
        signal="step_result.retry_exhausted",
        observation="Step metrics mark retry_exhausted=true.",
        p_success=-0.05,
        recovery_margin=-0.06,
        expected_remaining_cost="cost_penalty += 0.40",
        rationale="Retry exhaustion consumes local recovery options.",
    ),
    BeliefStateUpdateRule(
        signal="step_result.skipped",
        observation="StepResult status is skipped.",
        p_success=-0.02,
        expected_remaining_cost="cost_penalty += 0.15",
        rationale="A skipped step is weak negative evidence and small residual cost.",
    ),
    BeliefStateUpdateRule(
        signal="safety_result.warn",
        observation="SafetyResult action is warn; n_warn risk flags are present.",
        p_success="-0.04 - 0.01*n_warn",
        p_structural_failure=0.05,
        recovery_margin=-0.03,
        expected_remaining_cost="cost_penalty += 0.25",
        rationale="Warnings reduce confidence without making the route terminal.",
    ),
    BeliefStateUpdateRule(
        signal="safety_result.block",
        observation="SafetyResult action is block; n_block risk flags are present.",
        p_success="-0.18 - 0.02*n_block",
        p_structural_failure="0.12 + 0.01*n_block",
        recovery_margin=-0.16,
        expected_remaining_cost="cost_penalty += 0.75",
        rationale="Blocks represent strong negative evidence and high recovery pressure.",
    ),
    BeliefStateUpdateRule(
        signal="failure_context.patch_local",
        observation="Failure context normalizes recovery_action to patch_local.",
        p_success=-0.04,
        recovery_margin=-0.07,
        expected_remaining_cost="cost_penalty += 0.60",
        rationale="Local patching keeps the prefix but consumes repair headroom.",
    ),
    BeliefStateUpdateRule(
        signal="failure_context.suffix_replan",
        observation="Recovery action is suffix_replan or replan.",
        p_success=-0.10,
        p_structural_failure=0.08,
        recovery_margin=-0.12,
        expected_remaining_cost="cost_penalty += 1.20",
        rationale="Suffix replanning admits that the current suffix is unreliable.",
    ),
    BeliefStateUpdateRule(
        signal="failure_context.stop",
        observation="Recovery action is stop.",
        p_success=-0.15,
        recovery_margin="set to 0.0",
        rationale="Stop consumes all remaining recovery margin by construction.",
    ),
    BeliefStateUpdateRule(
        signal="failure_context.retry_exhausted",
        observation="Failure context carries retry_exhausted=true.",
        p_success=-0.03,
        recovery_margin=-0.04,
        expected_remaining_cost="cost_penalty += 0.25",
        rationale="Recovered failure context still records exhausted retry budget.",
    ),
    BeliefStateUpdateRule(
        signal="objective_evidence.progress",
        observation="Objective ranker reports objective_progress=p.",
        p_success="+0.04*clip(p,0,1)",
        evidence_sufficiency="pre-smoothing e_t += 0.03*clip(p,0,1)",
        rationale="Objective progress supports the current goal direction.",
    ),
    BeliefStateUpdateRule(
        signal="objective_evidence.sufficiency",
        observation="Objective ranker reports objective_evidence_sufficiency=q.",
        evidence_sufficiency="pre-smoothing e_t += 0.05*clip(q,0,1)",
        rationale="Direct objective evidence increases evidence sufficiency.",
    ),
    BeliefStateUpdateRule(
        signal="objective_evidence.gap",
        observation="Objective ranker reports objective_gap=g.",
        recovery_margin="+0.02*clip(g,0,1)",
        rationale="A visible objective gap leaves room for useful reranking decisions.",
    ),
    BeliefStateUpdateRule(
        signal="evidence_signal",
        observation="After all direct deltas, evidence_signal is estimated.",
        evidence_sufficiency="clip(0.70*e_t + 0.30*evidence_signal)",
        rationale="Evidence is smoothed to avoid overreacting to one observation.",
    ),
    BeliefStateUpdateRule(
        signal="progress_counters",
        observation="completed_steps and total_steps are available.",
        expected_remaining_cost="max(total_steps - completed_steps + cost_penalty, 0)",
        rationale="Explicit progress counters override heuristic one-step cost decay.",
    ),
)


def update_runtime_state(
    *,
    previous_state: RuntimeState | None,
    update_input: RuntimeStateUpdateInput | None = None,
    step_result: StepResult | None = None,
    safety_result: SafetyResult | None = None,
    failure_context: RuntimeFailureContext | Mapping[str, Any] | None = None,
    completed_steps: int | None = None,
    total_steps: int | None = None,
    budget_cap: float | None = None,
) -> RuntimeState:
    """以确定性规则更新 Lite 版运行时 belief-state。

    第一版刻意采用小步、可解释的规则增减，确保结果能够：
    - 直接序列化；
    - 跨快照回放；
    - 被测试稳定复现。
    
    调用方优先传入 ``RuntimeStateUpdateInput``，以固定更新器输入边界。
    保留原有关键字参数仅用于兼容既有调用路径。

    更新规则以 ``BELIEF_STATE_UPDATE_RULES`` 暴露，供论文中的
    ``B(x_t, o_t, h_t)`` 表格、测试和审计说明复用。
    """

    update = _coerce_update_input(
        update_input=update_input,
        step_result=step_result,
        safety_result=safety_result,
        failure_context=failure_context,
        completed_steps=completed_steps,
        total_steps=total_steps,
        budget_cap=budget_cap,
    )
    step_result = update.step_result
    safety_result = update.safety_result
    failure_context = update.failure_context
    completed_steps = update.completed_steps
    total_steps = update.total_steps
    budget_cap = update.budget_cap

    state = previous_state or RuntimeState(
        p_success=_BASELINE_P_SUCCESS,
        p_structural_failure=_BASELINE_P_STRUCTURAL_FAILURE,
        recovery_margin=_BASELINE_RECOVERY_MARGIN,
        expected_remaining_cost=_initial_remaining_cost(
            completed_steps=completed_steps,
            total_steps=total_steps,
        ),
        evidence_sufficiency=_BASELINE_EVIDENCE_SUFFICIENCY,
        budget_cap=budget_cap,
        last_update_source="runtime_bootstrap",
        observation_summary={},
    )

    p_success = state.p_success
    p_structural_failure = state.p_structural_failure
    recovery_margin = _clamp_unit_interval(state.recovery_margin)
    expected_remaining_cost = state.expected_remaining_cost
    evidence_sufficiency = _clamp_unit_interval(state.evidence_sufficiency)
    budget_cap = budget_cap if budget_cap is not None else state.budget_cap
    observation_summary = dict(state.observation_summary)
    last_update_source = state.last_update_source
    cost_penalty = 0.0
    cost_reward = 0.0

    _write_progress_summary(
        observation_summary,
        completed_steps=completed_steps,
        total_steps=total_steps,
    )

    if step_result is not None:
        stage_id = _extract_stage_id(step_result)
        last_update_source = f"step_result:{step_result.step_id}"
        observation_summary.update(
            {
                "last_step_id": step_result.step_id,
                "last_step_status": step_result.status,
                "last_tool": step_result.tool,
                "last_stage_id": stage_id,
                "last_failure_type": _as_non_empty_text(step_result.failure_type),
                "last_failure_code": _extract_failure_code(step_result),
            }
        )

        if step_result.status == "success":
            p_success += 0.12
            p_structural_failure -= 0.08
            recovery_margin += 0.06
            cost_reward += 0.35
            if _is_structural_step(stage_id=stage_id, tool_id=step_result.tool):
                p_success += 0.04
                p_structural_failure -= 0.05
            objective_signal = _extract_objective_signal(step_result)
            if objective_signal:
                observation_summary.update(objective_signal)
                progress = _as_float(objective_signal.get("objective_progress"))
                gap = _as_float(objective_signal.get("objective_gap"))
                if progress is not None:
                    p_success += 0.04 * _clamp_unit_interval(progress)
                    evidence_sufficiency += 0.03 * _clamp_unit_interval(progress)
                objective_evidence = _as_float(
                    objective_signal.get("objective_evidence_sufficiency")
                )
                if objective_evidence is not None:
                    evidence_sufficiency += 0.05 * _clamp_unit_interval(
                        objective_evidence
                    )
                if gap is not None:
                    recovery_margin += 0.02 * _clamp_unit_interval(gap)
            structure_similarity_signal = _extract_structure_similarity_signal(step_result)
            if structure_similarity_signal:
                observation_summary.update(structure_similarity_signal)
        elif step_result.status == "failed":
            p_success -= 0.18
            p_structural_failure += 0.14
            recovery_margin -= 0.12
            cost_penalty += 0.75
            if _is_structural_step(stage_id=stage_id, tool_id=step_result.tool):
                p_structural_failure += 0.08
            if _as_bool(step_result.metrics.get("retry_exhausted")):
                p_success -= 0.05
                recovery_margin -= 0.06
                cost_penalty += 0.4
        elif step_result.status == "skipped":
            p_success -= 0.02
            cost_penalty += 0.15

    if safety_result is not None:
        last_update_source = f"safety_result:{safety_result.scope}"
        block_flags = sum(flag.level == "block" for flag in safety_result.risk_flags)
        warn_flags = sum(flag.level == "warn" for flag in safety_result.risk_flags)
        observation_summary.update(
            {
                "last_safety_action": safety_result.action,
                "last_safety_scope": safety_result.scope,
                "last_safety_phase": safety_result.phase,
                "last_safety_flag_count": len(safety_result.risk_flags),
                "last_safety_warn_count": warn_flags,
                "last_safety_block_count": block_flags,
            }
        )

        if safety_result.action == "warn":
            p_success -= 0.04 + (0.01 * warn_flags)
            p_structural_failure += 0.05
            recovery_margin -= 0.03
            cost_penalty += 0.25
        elif safety_result.action == "block":
            p_success -= 0.18 + (0.02 * block_flags)
            p_structural_failure += 0.12 + (0.01 * block_flags)
            recovery_margin -= 0.16
            cost_penalty += 0.75

    if failure_context is not None:
        failure_payload = failure_context.to_replay_payload()
        recovery_action = _normalize_recovery_action(failure_payload)
        failure_code = _as_non_empty_text(failure_payload.get("failure_code"))
        if failure_code:
            observation_summary["last_failure_code"] = failure_code
        if recovery_action:
            observation_summary["last_recovery_action"] = recovery_action

        if recovery_action == "patch_local":
            p_success -= 0.04
            recovery_margin -= 0.07
            cost_penalty += 0.6
        elif recovery_action in {"suffix_replan", "replan"}:
            p_success -= 0.1
            p_structural_failure += 0.08
            recovery_margin -= 0.12
            cost_penalty += 1.2
        elif recovery_action == "stop":
            p_success -= 0.15
            recovery_margin = 0.0

        if failure_context.retry_exhausted:
            p_success -= 0.03
            recovery_margin -= 0.04
            cost_penalty += 0.25

    expected_remaining_cost = _resolve_remaining_cost(
        previous_cost=expected_remaining_cost,
        step_result=step_result,
        completed_steps=completed_steps,
        total_steps=total_steps,
        cost_penalty=cost_penalty,
        cost_reward=cost_reward,
    )
    evidence_signal = _estimate_evidence_signal(
        step_result=step_result,
        safety_result=safety_result,
        failure_context=failure_context,
        completed_steps=completed_steps,
        total_steps=total_steps,
    )
    evidence_sufficiency = _resolve_evidence_sufficiency(
        previous_value=evidence_sufficiency,
        evidence_signal=evidence_signal,
    )
    budget_derivation = derive_budget_pressure(
        expected_remaining_cost=expected_remaining_cost,
        budget_cap=budget_cap,
    )
    observation_summary["evidence_signal"] = _round_metric(evidence_signal)
    observation_summary["budget_pressure"] = _round_metric(
        budget_derivation.budget_pressure
    )
    if budget_cap is not None:
        observation_summary["budget_cap"] = budget_cap

    return RuntimeState(
        p_success=_round_metric(_clamp_unit_interval(p_success)),
        p_structural_failure=_round_metric(
            _clamp_unit_interval(p_structural_failure)
        ),
        recovery_margin=_round_metric(_clamp_unit_interval(recovery_margin)),
        expected_remaining_cost=_round_metric(max(expected_remaining_cost, 0.0)),
        evidence_sufficiency=_round_metric(evidence_sufficiency),
        budget_pressure=_round_metric(budget_derivation.budget_pressure),
        budget_cap=budget_cap,
        last_update_source=last_update_source,
        observation_summary=_drop_none_values(observation_summary),
    )


def extract_failure_context(step_result: StepResult) -> RuntimeFailureContext:
    """从 StepResult 提取适合回放与复用的失败上下文。"""

    patch_meta = step_result.metrics.get("patch")
    recovery_meta = step_result.metrics.get("recovery")
    failure_context: dict[str, Any] = {
        "failure_type": _as_non_empty_text(step_result.failure_type),
        "failure_code": _extract_failure_code(step_result),
        "retry_exhausted": _as_bool(step_result.metrics.get("retry_exhausted")),
    }

    if isinstance(patch_meta, dict):
        failure_context["patch"] = {
            "applied": _as_bool(patch_meta.get("applied")),
            "layer": _as_non_empty_text(patch_meta.get("layer")),
            "reason": _as_non_empty_text(patch_meta.get("reason")),
        }
        failure_context["recovery_action"] = "patch_local"

    if isinstance(recovery_meta, dict):
        failure_context["recovery"] = {
            "reason": _as_non_empty_text(recovery_meta.get("reason")),
            "upgrade_reason": _as_non_empty_text(
                recovery_meta.get("upgrade_reason")
            ),
            "recovery_layer": _as_non_empty_text(
                recovery_meta.get("recovery_layer")
            ),
        }
        upgrade_reason = _as_non_empty_text(recovery_meta.get("upgrade_reason"))
        reason = _as_non_empty_text(recovery_meta.get("reason"))
        if upgrade_reason:
            failure_context["recovery_action"] = upgrade_reason
        elif reason and "replan" in reason:
            failure_context["recovery_action"] = "replan"

    s6_action = _as_non_empty_text(step_result.metrics.get("s6_recovery_action"))
    if s6_action:
        failure_context["recovery_action"] = s6_action

    return RuntimeFailureContext.model_validate(
        _drop_none_values(failure_context)
    )


def _coerce_update_input(
    *,
    update_input: RuntimeStateUpdateInput | None,
    step_result: StepResult | None,
    safety_result: SafetyResult | None,
    failure_context: RuntimeFailureContext | Mapping[str, Any] | None,
    completed_steps: int | None,
    total_steps: int | None,
    budget_cap: float | None,
) -> RuntimeStateUpdateInput:
    if update_input is not None:
        return update_input
    return RuntimeStateUpdateInput(
        step_result=step_result,
        safety_result=safety_result,
        failure_context=_coerce_failure_context(failure_context),
        completed_steps=completed_steps,
        total_steps=total_steps,
        budget_cap=budget_cap,
    )


def _coerce_failure_context(
    failure_context: RuntimeFailureContext | Mapping[str, Any] | None,
) -> RuntimeFailureContext | None:
    if failure_context is None:
        return None
    if isinstance(failure_context, RuntimeFailureContext):
        return failure_context
    return RuntimeFailureContext.model_validate(dict(failure_context))


def _initial_remaining_cost(
    *,
    completed_steps: int | None,
    total_steps: int | None,
) -> float:
    if total_steps is None or completed_steps is None:
        return _BASELINE_EXPECTED_REMAINING_COST
    return float(max(total_steps - completed_steps, 0))


def _resolve_remaining_cost(
    *,
    previous_cost: float,
    step_result: StepResult | None,
    completed_steps: int | None,
    total_steps: int | None,
    cost_penalty: float,
    cost_reward: float,
) -> float:
    if total_steps is not None and completed_steps is not None:
        base_cost = float(max(total_steps - completed_steps, 0))
        return max(base_cost + cost_penalty, 0.0)

    base_cost = previous_cost
    if step_result is not None:
        if step_result.status == "success":
            base_cost = max(base_cost - 1.0, 0.0)
        elif step_result.status == "failed":
            base_cost += 0.5
    return max(base_cost + cost_penalty - cost_reward, 0.0)


def _resolve_evidence_sufficiency(
    *,
    previous_value: float,
    evidence_signal: float,
) -> float:
    # 中文注释：派生量只在运行时现场计算，持久化主状态仍只保留 evidence_sufficiency 本身。
    return _clamp_unit_interval((0.70 * previous_value) + (0.30 * evidence_signal))


def _estimate_evidence_signal(
    *,
    step_result: StepResult | None,
    safety_result: SafetyResult | None,
    failure_context: RuntimeFailureContext | None,
    completed_steps: int | None,
    total_steps: int | None,
) -> float:
    if (
        step_result is None
        and safety_result is None
        and failure_context is None
        and (completed_steps is None or completed_steps <= 0)
    ):
        return _BASELINE_EVIDENCE_SUFFICIENCY
    cheap_validation_coverage = _estimate_cheap_validation_coverage(
        step_result=step_result,
        completed_steps=completed_steps,
        total_steps=total_steps,
    )
    candidate_agreement = _estimate_candidate_agreement(
        step_result=step_result,
        safety_result=safety_result,
        failure_context=failure_context,
    )
    metric_completeness = _estimate_metric_completeness(
        step_result=step_result,
        safety_result=safety_result,
    )
    return _clamp_unit_interval(
        (0.40 * cheap_validation_coverage)
        + (0.30 * candidate_agreement)
        + (0.30 * metric_completeness)
    )


def _estimate_cheap_validation_coverage(
    *,
    step_result: StepResult | None,
    completed_steps: int | None,
    total_steps: int | None,
) -> float:
    coverage = 0.35
    if (
        completed_steps is not None
        and total_steps is not None
        and total_steps > 0
    ):
        coverage += 0.35 * min(max(completed_steps / total_steps, 0.0), 1.0)
    if step_result is None:
        return _clamp_unit_interval(coverage)
    stage_id = _extract_stage_id(step_result)
    if step_result.status == "success":
        coverage += 0.18
        if _is_structural_step(stage_id=stage_id, tool_id=step_result.tool):
            coverage += 0.08
    elif step_result.status == "failed":
        coverage -= 0.12
    return _clamp_unit_interval(coverage)


def _estimate_candidate_agreement(
    *,
    step_result: StepResult | None,
    safety_result: SafetyResult | None,
    failure_context: RuntimeFailureContext | None,
) -> float:
    agreement = 0.5
    if step_result is not None:
        stage_id = _extract_stage_id(step_result)
        if step_result.status == "success":
            agreement += 0.12
            if _is_structural_step(stage_id=stage_id, tool_id=step_result.tool):
                agreement += 0.08
            if _extract_structure_similarity_signal(step_result):
                agreement += 0.08
        elif step_result.status == "failed":
            agreement -= 0.18
    if safety_result is not None:
        if safety_result.action == "warn":
            agreement -= 0.08
        elif safety_result.action == "block":
            agreement -= 0.18
    if failure_context is not None:
        recovery_action = _normalize_recovery_action(
            failure_context.to_replay_payload()
        )
        if recovery_action == "patch_local":
            agreement += 0.04
        elif recovery_action in {"suffix_replan", "replan", "stop"}:
            agreement -= 0.08
    return _clamp_unit_interval(agreement)


def _estimate_metric_completeness(
    *,
    step_result: StepResult | None,
    safety_result: SafetyResult | None,
) -> float:
    completeness = 0.35
    if step_result is not None:
        if isinstance(step_result.outputs, dict) and step_result.outputs:
            completeness += 0.25
        if isinstance(step_result.metrics, dict) and step_result.metrics:
            completeness += 0.20
        if _extract_failure_code(step_result):
            completeness += 0.10
    if safety_result is not None and safety_result.risk_flags:
        completeness += 0.10
    return _clamp_unit_interval(completeness)


def _write_progress_summary(
    observation_summary: dict[str, Any],
    *,
    completed_steps: int | None,
    total_steps: int | None,
) -> None:
    if completed_steps is not None:
        observation_summary["completed_steps"] = completed_steps
    if total_steps is not None:
        observation_summary["total_steps"] = total_steps
    if completed_steps is None or total_steps is None or total_steps <= 0:
        return
    observation_summary["remaining_steps"] = max(total_steps - completed_steps, 0)
    observation_summary["completed_ratio"] = _round_metric(
        completed_steps / total_steps
    )


def _normalize_recovery_action(failure_context: Mapping[str, Any]) -> str | None:
    action = _as_non_empty_text(failure_context.get("recovery_action"))
    if action:
        return action
    reason = _as_non_empty_text(failure_context.get("reason"))
    if reason and "replan" in reason:
        return "replan"
    return reason


def _extract_stage_id(step_result: StepResult) -> str | None:
    outputs = step_result.outputs if isinstance(step_result.outputs, dict) else {}
    stage_id = outputs.get("stage_id")
    return _as_non_empty_text(stage_id)


def _extract_failure_code(step_result: StepResult) -> str | None:
    if isinstance(step_result.error_details, dict):
        failure_code = _as_non_empty_text(step_result.error_details.get("failure_code"))
        if failure_code:
            return failure_code
    for flag in step_result.risk_flags:
        code = _as_non_empty_text(flag.code)
        if code:
            return code
    return None


def _is_structural_step(*, stage_id: str | None, tool_id: str) -> bool:
    if stage_id in _STRUCTURAL_STAGE_IDS:
        return True
    tool_key = tool_id.strip().lower()
    return any(
        token in tool_key
        for token in ("fold", "esm", "alphafold", "mpnn", "qc", "quality")
    )


def _extract_objective_signal(step_result: StepResult) -> dict[str, Any]:
    metrics = step_result.metrics
    outputs = step_result.outputs
    capability_id = _as_non_empty_text(outputs.get("capability_id"))
    tool_key = step_result.tool.strip().lower()
    if capability_id != "objective_scoring" and tool_key != "objective_ranker":
        return {}

    progress = _as_float(metrics.get("objective_progress"))
    if progress is None:
        progress = _as_float(outputs.get("objective_score"))
    gap = _as_float(metrics.get("objective_gap"))
    top_candidate_id = _as_non_empty_text(metrics.get("top_candidate_id"))
    if top_candidate_id is None:
        top_candidate_id = _as_non_empty_text(outputs.get("default_recommendation"))
    objective_evidence = _as_float(metrics.get("evidence_sufficiency"))
    if objective_evidence is None:
        posterior_score = outputs.get("posterior_score")
        if isinstance(posterior_score, dict):
            objective_evidence = _as_float(posterior_score.get("evidence_sufficiency"))

    payload: dict[str, Any] = {
        "objective_progress": (
            _round_metric(_clamp_unit_interval(progress))
            if progress is not None
            else None
        ),
        "objective_gap": _round_metric(max(gap, 0.0)) if gap is not None else None,
        "objective_top_candidate_id": top_candidate_id,
        "objective_warning_count": metrics.get("warning_count"),
        "objective_evidence_sufficiency": (
            _round_metric(_clamp_unit_interval(objective_evidence))
            if objective_evidence is not None
            else None
        ),
    }
    return _drop_none_values(payload)


def _extract_structure_similarity_signal(step_result: StepResult) -> dict[str, Any]:
    outputs = step_result.outputs if isinstance(step_result.outputs, dict) else {}
    capability_id = _as_non_empty_text(outputs.get("capability_id"))
    tool_key = step_result.tool.strip().lower()
    if capability_id != "structure_similarity_search" and tool_key != "foldseek":
        return {}

    hit_count = _as_float(outputs.get("hit_count"))
    top_hit = outputs.get("top_hit")
    top_tm_score = None
    top_coverage = None
    if isinstance(top_hit, dict):
        top_tm_score = _as_float(top_hit.get("tm_score"))
        top_coverage = _as_float(top_hit.get("coverage"))
    return _drop_none_values(
        {
            "structure_similarity_hit_count": int(hit_count) if hit_count is not None else None,
            "structure_similarity_top_tm_score": (
                _round_metric(_clamp_unit_interval(top_tm_score))
                if top_tm_score is not None
                else None
            ),
            "structure_similarity_top_coverage": (
                _round_metric(_clamp_unit_interval(top_coverage))
                if top_coverage is not None
                else None
            ),
        }
    )


def _clamp_unit_interval(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _round_metric(value: float) -> float:
    return round(float(value), 6)


def _as_non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _drop_none_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
