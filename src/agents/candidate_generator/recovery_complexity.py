"""静态候选恢复复杂度的 recoverability 补量派生。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from src.models.runtime_schemas import (
    RECOVERY_COMPONENT_WEIGHTS,
    JsonObject,
    RecoverySchema,
)
from src.workflow.action_features import (
    ACTION_FEATURE_SOURCE_REFS,
    FeatureSource,
    derive_action_features,
)

RECOVERY_COMPLEXITY_METADATA_KEY = "recovery_complexity_source"
RECOVERY_COMPLEXITY_SCHEMA_VERSION = "recovery_complexity.v1"
RECOVERY_COMPLEXITY_FORMULA_VERSION = "recoverability_complement.v1"
RECOVERY_COMPLEXITY_SOURCE_REFS: tuple[str, ...] = (
    "sid:algo.schema.recovery",
    "sid:planner.algorithm.candidate_scoring",
    "impl:candidate_generator.recovery_complexity.v1",
)
RECOVERY_COMPONENT_NAMES: tuple[str, ...] = (
    "retry_budget_ratio",
    "local_patchability",
    "prefix_preservability",
    "evidence_reusability",
)


@dataclass(frozen=True)
class DerivedRecoveryComponent:
    """恢复复杂度分量的值、权重与来源。"""

    value: float
    weight: float
    source: FeatureSource
    source_fields: tuple[str, ...]
    reason: str

    def to_metadata(self) -> JsonObject:
        """返回可写入候选 metadata 的 JSON 结构。"""

        return {
            "value": round(self.value, 6),
            "weight": self.weight,
            "source": self.source,
            "source_fields": list(self.source_fields),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RecoveryComplexityDerivation:
    """恢复性与恢复复杂度的派生结果。"""

    recoverability: float
    recovery_complexity: float
    components: dict[str, DerivedRecoveryComponent]
    source_refs: tuple[str, ...] = RECOVERY_COMPLEXITY_SOURCE_REFS

    def score_values(self) -> dict[str, float]:
        """返回可并入 score_breakdown 的数值字段。"""

        values = {
            name: component.value for name, component in self.components.items()
        }
        values["recoverability"] = self.recoverability
        values["recovery_complexity"] = self.recovery_complexity
        return values

    def to_metadata(self) -> JsonObject:
        """返回 recovery_complexity 的审计 metadata。"""

        return {
            "schema_version": RECOVERY_COMPLEXITY_SCHEMA_VERSION,
            "formula_version": RECOVERY_COMPLEXITY_FORMULA_VERSION,
            "recoverability": round(self.recoverability, 6),
            "recovery_complexity": round(self.recovery_complexity, 6),
            "derived_from": list(RECOVERY_COMPONENT_NAMES),
            "derived_from_defaults": any(
                component.source in {"default", "unknown"}
                for component in self.components.values()
            ),
            "fallback_depth_role": "compat_input.retry_budget_ratio",
            "components": {
                name: component.to_metadata()
                for name, component in self.components.items()
            },
            "source_refs": list(self.source_refs),
            "action_feature_source_refs": list(ACTION_FEATURE_SOURCE_REFS),
        }


def derive_recovery_complexity(
    *,
    fallback_depth: float | None,
    runtime_state: Mapping[str, object] | None = None,
    candidate_summary: Mapping[str, object] | None = None,
) -> RecoveryComplexityDerivation:
    """按 Recovery Schema 公式派生静态恢复复杂度。

    Args:
        fallback_depth: 兼容旧静态评分的 fallback 深度，只作为 retry_budget_ratio
            的回退输入。
        runtime_state: 可选运行时状态或 belief-state 摘要。
        candidate_summary: 可选候选摘要，主要用于复用 posterior evidence。

    Returns:
        含 recoverability、recovery_complexity 和分量来源的派生结果。
    """

    normalized_runtime_state = runtime_state or {}
    action_features = derive_action_features(
        runtime_state=normalized_runtime_state,
        candidate_summary=candidate_summary,
    )
    retry_budget_ratio = _derive_retry_budget_ratio(
        fallback_depth=fallback_depth,
        runtime_state=normalized_runtime_state,
    )
    components = {
        "retry_budget_ratio": retry_budget_ratio,
        "local_patchability": _action_feature_component(
            "local_patchability",
            action_features.features["local_patchability"].value,
            action_features.features["local_patchability"].source,
            action_features.features["local_patchability"].source_fields,
            action_features.features["local_patchability"].reason,
        ),
        "prefix_preservability": _action_feature_component(
            "prefix_preservability",
            action_features.features["prefix_preservability"].value,
            action_features.features["prefix_preservability"].source,
            action_features.features["prefix_preservability"].source_fields,
            action_features.features["prefix_preservability"].reason,
        ),
        "evidence_reusability": _action_feature_component(
            "evidence_reusability",
            action_features.features["evidence_reusability"].value,
            action_features.features["evidence_reusability"].source,
            action_features.features["evidence_reusability"].source_fields,
            action_features.features["evidence_reusability"].reason,
        ),
    }
    schema = RecoverySchema(
        retry_budget_ratio=components["retry_budget_ratio"].value,
        local_patchability=components["local_patchability"].value,
        prefix_preservability=components["prefix_preservability"].value,
        evidence_reusability=components["evidence_reusability"].value,
    )
    return RecoveryComplexityDerivation(
        recoverability=schema.recoverability(),
        recovery_complexity=schema.recovery_complexity(),
        components=components,
    )


def _derive_retry_budget_ratio(
    *,
    fallback_depth: float | None,
    runtime_state: Mapping[str, object],
) -> DerivedRecoveryComponent:
    observed = _observed_unit(runtime_state, "retry_budget_ratio")
    if observed is not None:
        return _component(
            "retry_budget_ratio",
            observed,
            "observed",
            ("runtime_state.retry_budget_ratio",),
            "Runtime state provided retry budget ratio explicitly.",
        )
    nested = _nested_unit(runtime_state, ("recovery", "retry_budget_ratio"))
    if nested is not None:
        return _component(
            "retry_budget_ratio",
            nested,
            "observed",
            ("runtime_state.recovery.retry_budget_ratio",),
            "Runtime recovery schema provided retry budget ratio explicitly.",
        )
    if fallback_depth is not None:
        return _component(
            "retry_budget_ratio",
            fallback_depth,
            "inferred",
            ("score_breakdown.fallback_depth",),
            "Fallback depth is retained only as a compatibility input for retry budget ratio.",
        )
    return _component(
        "retry_budget_ratio",
        0.5,
        "default",
        (),
        "No retry budget signal is available, so retry budget ratio defaults to neutral 0.5.",
    )


def _action_feature_component(
    name: str,
    value: float,
    source: FeatureSource,
    source_fields: tuple[str, ...],
    reason: str,
) -> DerivedRecoveryComponent:
    return _component(name, value, source, source_fields, reason)


def _component(
    name: str,
    value: float,
    source: FeatureSource,
    source_fields: tuple[str, ...],
    reason: str,
) -> DerivedRecoveryComponent:
    return DerivedRecoveryComponent(
        value=round(_clip_unit(value), 6),
        weight=RECOVERY_COMPONENT_WEIGHTS[name],
        source=source,
        source_fields=source_fields,
        reason=reason,
    )


def _observed_unit(mapping: Mapping[str, object], key: str) -> float | None:
    return _unit_or_none(mapping.get(key))


def _nested_unit(mapping: Mapping[str, object], path: tuple[str, ...]) -> float | None:
    current: object = mapping
    for key in path:
        current_mapping = _string_mapping(current)
        if current_mapping is None:
            return None
        current = current_mapping.get(key)
    return _unit_or_none(current)


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


def _unit_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return _clip_unit(parsed)


def _clip_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value
