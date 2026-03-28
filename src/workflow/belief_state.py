from __future__ import annotations

from typing import Any, Mapping

from src.models.contracts import (
    RuntimeFailureContext,
    RuntimeState,
    RuntimeStateUpdateInput,
    SafetyResult,
    StepResult,
)

__all__ = ["extract_failure_context", "update_runtime_state"]

_BASELINE_P_SUCCESS = 0.5
_BASELINE_P_STRUCTURAL_FAILURE = 0.25
_BASELINE_RECOVERY_MARGIN = 0.6
_BASELINE_EXPECTED_REMAINING_COST = 1.0
_STRUCTURAL_STAGE_IDS = {"S2", "S3", "S4"}


def update_runtime_state(
    *,
    previous_state: RuntimeState | None,
    update_input: RuntimeStateUpdateInput | None = None,
    step_result: StepResult | None = None,
    safety_result: SafetyResult | None = None,
    failure_context: RuntimeFailureContext | Mapping[str, Any] | None = None,
    completed_steps: int | None = None,
    total_steps: int | None = None,
) -> RuntimeState:
    """以确定性规则更新 Lite 版运行时 belief-state。

    第一版刻意采用小步、可解释的规则增减，确保结果能够：
    - 直接序列化；
    - 跨快照回放；
    - 被测试稳定复现。
    
    调用方优先传入 ``RuntimeStateUpdateInput``，以固定更新器输入边界。
    保留原有关键字参数仅用于兼容既有调用路径。
    """

    update = _coerce_update_input(
        update_input=update_input,
        step_result=step_result,
        safety_result=safety_result,
        failure_context=failure_context,
        completed_steps=completed_steps,
        total_steps=total_steps,
    )
    step_result = update.step_result
    safety_result = update.safety_result
    failure_context = update.failure_context
    completed_steps = update.completed_steps
    total_steps = update.total_steps

    state = previous_state or RuntimeState(
        p_success=_BASELINE_P_SUCCESS,
        p_structural_failure=_BASELINE_P_STRUCTURAL_FAILURE,
        recovery_margin=_BASELINE_RECOVERY_MARGIN,
        expected_remaining_cost=_initial_remaining_cost(
            completed_steps=completed_steps,
            total_steps=total_steps,
        ),
        last_update_source="runtime_bootstrap",
        observation_summary={},
    )

    p_success = state.p_success
    p_structural_failure = state.p_structural_failure
    recovery_margin = _clamp_unit_interval(state.recovery_margin)
    expected_remaining_cost = state.expected_remaining_cost
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

    return RuntimeState(
        p_success=_round_metric(_clamp_unit_interval(p_success)),
        p_structural_failure=_round_metric(
            _clamp_unit_interval(p_structural_failure)
        ),
        recovery_margin=_round_metric(_clamp_unit_interval(recovery_margin)),
        expected_remaining_cost=_round_metric(max(expected_remaining_cost, 0.0)),
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
) -> RuntimeStateUpdateInput:
    if update_input is not None:
        return update_input
    return RuntimeStateUpdateInput(
        step_result=step_result,
        safety_result=safety_result,
        failure_context=_coerce_failure_context(failure_context),
        completed_steps=completed_steps,
        total_steps=total_steps,
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


def _drop_none_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
