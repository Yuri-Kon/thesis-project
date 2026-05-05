"""Source refs 常量与轻量 helper。

本模块只承载设计 SID 与实现引用的短字符串常量，避免在 runtime
metadata 中散落不可追踪的裸字符串。
"""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

DesignRefStatus: TypeAlias = Literal["existing", "proposed"]
DesignRefStatusMap: TypeAlias = dict[str, DesignRefStatus]

SOURCE_REF_FEASIBILITY: Final[tuple[str, ...]] = (
    "sid:algo.adaptive.feasibility_filter",
    "impl:candidate_generator.feasibility.v1",
)

SOURCE_REF_POSTERIOR_OBJECTIVE: Final[tuple[str, ...]] = (
    "sid:algo.posterior_objective_scoring",
    "impl:posterior_score.v1",
    "impl:posterior_objective.v1",
)

SOURCE_REF_STATIC_SCORE: Final[tuple[str, ...]] = (
    "sid:algo.adaptive.optimization_objective",
    "sid:planner.algorithm.candidate_scoring",
    "impl:planner.score_breakdown.v1",
)

SOURCE_REF_RUNTIME_ADJUSTMENT: Final[tuple[str, ...]] = (
    "sid:planner.algorithm.runtime_adjustment_formula",
    "sid:planner.algorithm.runtime_reranking",
    "impl:planner.runtime_adjustment.v1",
)

SOURCE_REF_ACTION_UTILITY: Final[tuple[str, ...]] = (
    "sid:algo.schema.action_utility",
    "sid:algo.action_feature_derivation",
    "impl:runtime_evaluator.action_utility.v1",
    "impl:workflow.action_features.v1",
)

SOURCE_REF_DEFAULT_ACTION_UTILITY: Final[tuple[str, ...]] = (
    "sid:algo.schema.action_utility",
    "impl:runtime_evaluator.default.v1",
)

SOURCE_REF_ACTION_SELECTION: Final[tuple[str, ...]] = (
    "sid:algo.recovery_aware_action_selection",
    "sid:planner.algorithm.action_priority_resolution",
    "impl:recovery.select_workflow_action.v1",
)

SOURCE_REF_TERMINAL_STOP: Final[tuple[str, ...]] = (
    "sid:algo.terminal_stop_policy",
    "sid:planner.algorithm.stop_semantics",
    "impl:recovery.terminal_stop.v1",
)

PROPOSED_DESIGN_REF_STATUS: Final[DesignRefStatusMap] = {
    "sid:algo.adaptive.feasibility_filter": "proposed",
    "sid:algo.posterior_objective_scoring": "proposed",
    "sid:algo.action_feature_derivation": "proposed",
    "sid:algo.recovery_aware_action_selection": "proposed",
    "sid:algo.terminal_stop_policy": "proposed",
}


def as_source_refs(*refs: str) -> list[str]:
    """返回去重后的 source_refs 列表。

    保持输入顺序并拒绝空字符串；不做复杂 SID/impl 校验，避免在运行期
    引入额外语义判断。
    """

    normalized: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        text = ref.strip()
        if not text:
            raise ValueError("source_refs items must not be empty")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def design_ref_status_for(*refs: str) -> DesignRefStatusMap:
    """返回 refs 中 proposed SID 的状态映射。"""

    return {
        ref: status
        for ref, status in PROPOSED_DESIGN_REF_STATUS.items()
        if ref in refs
    }
