"""恢复动作效用特征的确定性派生规则。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from src.models.runtime_schemas import JsonObject
from src.workflow.errors import FailureType

FeatureSource = Literal["observed", "inferred", "default", "unknown"]

ACTION_FEATURE_NAMES: tuple[str, ...] = (
    "budget_pressure",
    "local_patchability",
    "evidence_reusability",
    "prefix_preservability",
    "budget_relief",
    "goal_realignment",
    "safety_terminality",
    "intervention_value",
)

ACTION_FEATURE_SOURCE_REFS: tuple[str, ...] = (
    "sid:algo.action_feature_derivation",
    "impl:workflow.action_features.v1",
)


@dataclass(frozen=True)
class DerivedActionFeature:
    """单个动作效用特征的值与来源。"""

    value: float
    source: FeatureSource
    source_fields: tuple[str, ...]
    reason: str

    def to_metadata(self) -> JsonObject:
        """返回可写入 ActionUtility metadata 的 JSON 结构。"""

        return {
            "value": round(self.value, 6),
            "source": self.source,
            "source_fields": list(self.source_fields),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ActionFeatureDerivation:
    """动作效用特征派生结果。"""

    values: dict[str, float]
    features: dict[str, DerivedActionFeature]
    source_refs: tuple[str, ...] = ACTION_FEATURE_SOURCE_REFS

    def features_metadata(self) -> JsonObject:
        """返回全部派生特征的 JSON metadata。"""

        return {name: feature.to_metadata() for name, feature in self.features.items()}

    def to_metadata(self) -> JsonObject:
        """返回派生结果的完整 JSON metadata。"""

        return {
            "features": self.features_metadata(),
            "source_refs": list(self.source_refs),
        }


def derive_action_features(
    *,
    runtime_state: Mapping[str, object],
    stage_id: str | None = None,
    failure_type: FailureType | str | None = None,
    retry_exhausted: bool = False,
    safety_blocked: bool = False,
    candidate_summary: Mapping[str, object] | None = None,
    completed_step_count: int | None = None,
    failed_step_index: int | None = None,
) -> ActionFeatureDerivation:
    """从运行时状态和失败上下文派生动作效用特征。

    Args:
        runtime_state: 当前运行时状态摘要。
        stage_id: 失败或决策所在阶段。
        failure_type: 失败类型。
        retry_exhausted: 当前步骤是否已耗尽 retry。
        safety_blocked: SafetyAgent 是否阻止继续。
        candidate_summary: 候选或目标评分摘要。
        completed_step_count: 已完成步骤数。
        failed_step_index: 失败步骤索引。

    Returns:
        带 value/source/source_fields/reason 的派生结果。
    """

    normalized_failure_type = _normalize_failure_type(failure_type)
    normalized_stage = _normalize_text(stage_id)
    candidate = candidate_summary or {}

    p_success = _unit_or_default(runtime_state.get("p_success"), 0.5)
    p_structural_failure = _unit_or_default(
        runtime_state.get("p_structural_failure"), 0.25
    )
    recovery_margin = _unit_or_default(runtime_state.get("recovery_margin"), 0.6)
    expected_remaining_cost = _float_or_default(
        runtime_state.get("expected_remaining_cost"), 1.0
    )
    evidence_sufficiency = _unit_or_default(
        runtime_state.get("evidence_sufficiency"), 0.5
    )
    has_context = _has_contextual_signal(
        runtime_state=runtime_state,
        candidate_summary=candidate_summary,
        stage_id=normalized_stage,
        failure_type=normalized_failure_type,
        retry_exhausted=retry_exhausted,
        safety_blocked=safety_blocked,
        completed_step_count=completed_step_count,
        failed_step_index=failed_step_index,
    )

    features: dict[str, DerivedActionFeature] = {}

    budget_pressure = _observed_or_none(runtime_state, "budget_pressure")
    if budget_pressure is not None:
        features["budget_pressure"] = _feature(
            budget_pressure,
            "observed",
            ("runtime_state.budget_pressure",),
            "Runtime state provided budget pressure explicitly.",
            upper=1.5,
        )
    else:
        features["budget_pressure"] = _feature(
            _clip(expected_remaining_cost, lower=0.0, upper=1.5),
            "inferred" if "expected_remaining_cost" in runtime_state else "default",
            ("runtime_state.expected_remaining_cost",),
            "Budget pressure is clipped from expected remaining cost.",
            upper=1.5,
        )

    budget_pressure_value = features["budget_pressure"].value

    local_patchability = _observed_or_none(runtime_state, "local_patchability")
    if local_patchability is not None:
        features["local_patchability"] = _feature(
            local_patchability,
            "observed",
            ("runtime_state.local_patchability",),
            "Runtime state provided local patchability explicitly.",
        )
    else:
        patch_value = (
            0.45 * recovery_margin
            + 0.35 * (1.0 - p_structural_failure)
            + 0.20 * evidence_sufficiency
        )
        if normalized_stage == "S1":
            patch_value += 0.18
        if normalized_failure_type in {FailureType.RETRYABLE, FailureType.TOOL_ERROR}:
            patch_value += 0.10
        if retry_exhausted and not safety_blocked:
            patch_value += 0.05
        if safety_blocked:
            patch_value -= 0.25
        if normalized_failure_type == FailureType.SAFETY_BLOCK:
            patch_value -= 0.15
        features["local_patchability"] = _feature(
            patch_value,
            "inferred" if has_context else "default",
            (
                "runtime_state.recovery_margin",
                "runtime_state.p_structural_failure",
                "runtime_state.evidence_sufficiency",
                "failure_context.stage_id",
                "failure_context.failure_type",
                "failure_context.retry_exhausted",
                "failure_context.safety_blocked",
            ),
            "Local patchability is inferred from recovery headroom, failure pressure, evidence, and failure locality.",
        )

    prefix_preservability = _observed_or_none(runtime_state, "prefix_preservability")
    if prefix_preservability is not None:
        features["prefix_preservability"] = _feature(
            prefix_preservability,
            "observed",
            ("runtime_state.prefix_preservability",),
            "Runtime state provided prefix preservability explicitly.",
        )
    else:
        prefix_value = (
            0.50 * recovery_margin
            + 0.30 * evidence_sufficiency
            + 0.20 * (1.0 - min(budget_pressure_value, 1.0))
        )
        source_fields = [
            "runtime_state.recovery_margin",
            "runtime_state.evidence_sufficiency",
            "derived.budget_pressure",
        ]
        if failed_step_index is not None and failed_step_index > 0:
            prefix_value += 0.10
            source_fields.append("failure_context.failed_step_index")
        elif failed_step_index == 0:
            prefix_value -= 0.15
            source_fields.append("failure_context.failed_step_index")
        if completed_step_count is not None and completed_step_count > 0:
            prefix_value += 0.08
            source_fields.append("failure_context.completed_step_count")
        features["prefix_preservability"] = _feature(
            prefix_value,
            "inferred" if has_context else "default",
            tuple(source_fields),
            "Prefix preservability is inferred from recovery margin, evidence sufficiency, budget pressure, and known execution progress.",
        )

    evidence_reusability = _observed_or_none(runtime_state, "evidence_reusability")
    if evidence_reusability is not None:
        features["evidence_reusability"] = _feature(
            evidence_reusability,
            "observed",
            ("runtime_state.evidence_reusability",),
            "Runtime state provided evidence reusability explicitly.",
        )
    else:
        candidate_evidence = _nested_numeric(
            candidate,
            ("posterior_objective", "evidence_sufficiency"),
        )
        if candidate_evidence is not None:
            features["evidence_reusability"] = _feature(
                candidate_evidence,
                "observed",
                ("candidate_summary.posterior_objective.evidence_sufficiency",),
                "Candidate posterior objective provided reusable evidence sufficiency.",
            )
        else:
            features["evidence_reusability"] = _feature(
                0.65 * evidence_sufficiency
                + 0.35 * features["prefix_preservability"].value,
                "inferred" if has_context else "default",
                (
                    "runtime_state.evidence_sufficiency",
                    "derived.prefix_preservability",
                ),
                "Evidence reusability is inferred from evidence sufficiency and prefix preservability.",
            )

    budget_relief = _observed_or_none(runtime_state, "budget_relief")
    if budget_relief is not None:
        features["budget_relief"] = _feature(
            budget_relief,
            "observed",
            ("runtime_state.budget_relief",),
            "Runtime state provided budget relief explicitly.",
        )
    else:
        if expected_remaining_cost >= 1.0 and features["prefix_preservability"].value >= 0.55:
            relief_value = 0.60
        elif expected_remaining_cost >= 1.0:
            relief_value = 0.45
        else:
            relief_value = 0.35
        features["budget_relief"] = _feature(
            relief_value,
            "inferred" if "expected_remaining_cost" in runtime_state else "default",
            (
                "runtime_state.expected_remaining_cost",
                "derived.prefix_preservability",
            ),
            "Budget relief is conservative because suffix replan is not assumed to be free.",
        )

    goal_realignment = _observed_or_none(runtime_state, "goal_realignment")
    if goal_realignment is not None:
        features["goal_realignment"] = _feature(
            goal_realignment,
            "observed",
            ("runtime_state.goal_realignment",),
            "Runtime state provided goal realignment explicitly.",
        )
    else:
        realignment_value = (
            0.40 * (1.0 - p_success)
            + 0.30 * p_structural_failure
            + 0.30 * (1.0 - evidence_sufficiency)
        )
        objective_gap = _nested_numeric(candidate, ("objective_gap",))
        objective_gap_source = "candidate_summary.objective_gap"
        if objective_gap is None:
            objective_gap = _nested_numeric(
                candidate,
                ("posterior_objective", "objective_gap"),
            )
            objective_gap_source = "candidate_summary.posterior_objective.objective_gap"
        source_fields = [
            "runtime_state.p_success",
            "runtime_state.p_structural_failure",
            "runtime_state.evidence_sufficiency",
        ]
        if objective_gap is not None:
            realignment_value = max(realignment_value, objective_gap)
            source_fields.append(objective_gap_source)
        features["goal_realignment"] = _feature(
            realignment_value,
            "inferred" if has_context else "default",
            tuple(source_fields),
            "Goal realignment is inferred from low success, structural pressure, missing evidence, and optional objective gap.",
        )

    safety_terminality = _observed_or_none(runtime_state, "safety_terminality")
    if safety_terminality is not None:
        features["safety_terminality"] = _feature(
            safety_terminality,
            "observed",
            ("runtime_state.safety_terminality",),
            "Runtime state provided safety terminality explicitly.",
        )
    else:
        safety_value = 1.0 if (
            safety_blocked or normalized_failure_type == FailureType.SAFETY_BLOCK
        ) else 0.0
        features["safety_terminality"] = _feature(
            safety_value,
            "inferred" if safety_value > 0.0 else "default",
            (
                "failure_context.safety_blocked",
                "failure_context.failure_type",
            ),
            "Safety terminality is only high when safety blocks continuation.",
        )

    intervention_value = _observed_or_none(runtime_state, "intervention_value")
    if intervention_value is not None:
        features["intervention_value"] = _feature(
            intervention_value,
            "observed",
            ("runtime_state.intervention_value",),
            "Runtime state provided intervention value explicitly.",
        )
    elif not has_context:
        features["intervention_value"] = _feature(
            0.5,
            "default",
            (),
            "No reliable runtime context is available, so intervention value defaults to neutral 0.5.",
        )
    else:
        uncertainty = _clip(
            1.0 - abs(p_success - (1.0 - p_structural_failure))
        )
        manual_salvageability = _clip(
            0.55 * features["local_patchability"].value
            + 0.45 * features["prefix_preservability"].value
        )
        artifact_salience = _clip(
            0.60 * evidence_sufficiency + 0.40 * recovery_margin
        )
        decision_gap = _clip(
            0.50 + 0.25 * recovery_margin - 0.25 * min(budget_pressure_value, 1.0)
        )
        features["intervention_value"] = _feature(
            0.30 * uncertainty
            + 0.25 * manual_salvageability
            + 0.25 * artifact_salience
            + 0.20 * decision_gap,
            "inferred",
            (
                "runtime_state.p_success",
                "runtime_state.p_structural_failure",
                "runtime_state.evidence_sufficiency",
                "runtime_state.recovery_margin",
                "derived.local_patchability",
                "derived.prefix_preservability",
                "derived.budget_pressure",
            ),
            "Intervention value is inferred from uncertainty, salvageability, artifact salience, and decision gap.",
        )

    values = {name: features[name].value for name in ACTION_FEATURE_NAMES}
    return ActionFeatureDerivation(values=values, features=features)


def _feature(
    value: float,
    source: FeatureSource,
    source_fields: tuple[str, ...],
    reason: str,
    *,
    upper: float = 1.0,
) -> DerivedActionFeature:
    return DerivedActionFeature(
        value=round(_clip(value, lower=0.0, upper=upper), 6),
        source=source,
        source_fields=source_fields,
        reason=reason,
    )


def _has_contextual_signal(
    *,
    runtime_state: Mapping[str, object],
    candidate_summary: Mapping[str, object] | None,
    stage_id: str | None,
    failure_type: FailureType | None,
    retry_exhausted: bool,
    safety_blocked: bool,
    completed_step_count: int | None,
    failed_step_index: int | None,
) -> bool:
    core_fields = {
        "p_success",
        "p_structural_failure",
        "recovery_margin",
        "expected_remaining_cost",
        "evidence_sufficiency",
    }
    return (
        bool(core_fields.intersection(runtime_state.keys()))
        or bool(candidate_summary)
        or stage_id is not None
        or failure_type is not None
        or retry_exhausted
        or safety_blocked
        or completed_step_count is not None
        or failed_step_index is not None
    )


def _observed_or_none(payload: Mapping[str, object], field: str) -> float | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _nested_numeric(payload: Mapping[str, object], path: tuple[str, ...]) -> float | None:
    current: object = dict(payload)
    for key in path:
        mapping = _string_mapping(current)
        if mapping is None:
            return None
        current = mapping.get(key)
    if isinstance(current, bool) or not isinstance(current, int | float):
        return None
    return float(current)


def _string_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    raw_mapping = cast(dict[object, object], value)
    normalized: dict[str, object] = {}
    for key, item in raw_mapping.items():
        if not isinstance(key, str):
            return None
        normalized[key] = item
    return normalized


def _unit_or_default(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return _clip(float(value))


def _float_or_default(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def _clip(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_failure_type(value: FailureType | str | None) -> FailureType | None:
    if isinstance(value, FailureType):
        return value
    if isinstance(value, str):
        try:
            return FailureType(value)
        except ValueError:
            return None
    return None
