"""CEBRA-WP 算法版本与子公式版本 registry。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from src.models.source_refs import (
    SOURCE_REF_ACTION_BIAS,
    SOURCE_REF_ACTION_UTILITY,
    SOURCE_REF_POSTERIOR_OBJECTIVE,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
    SOURCE_REF_STATIC_SCORE,
)

CEBRA_WP_ALGORITHM_VERSION: Final = "cebra_wp.v2"
CEBRA_WP_DOC_VERSION: Final = "core-algorithm-theory-v2"


@dataclass(frozen=True)
class FormulaVersionEntry:
    """算法总版本下的子公式/schema 版本条目。"""

    formula_id: str
    formula_version: str
    role: str
    schema_versions: tuple[str, ...]
    implementation_refs: tuple[str, ...]
    design_refs: tuple[str, ...]


CEBRA_WP_FORMULA_VERSION_ENTRIES: Final[tuple[FormulaVersionEntry, ...]] = (
    FormulaVersionEntry(
        formula_id="static_score",
        formula_version="static_score.v1",
        role="静态候选效用与 score_breakdown 归档版本。",
        schema_versions=("score_breakdown.v1",),
        implementation_refs=tuple(
            ref for ref in SOURCE_REF_STATIC_SCORE if ref.startswith("impl:")
        ),
        design_refs=tuple(
            ref for ref in SOURCE_REF_STATIC_SCORE if ref.startswith("sid:")
        ),
    ),
    FormulaVersionEntry(
        formula_id="posterior_score",
        formula_version="posterior_score.v1",
        role="证据加权 posterior objective scoring 归档版本。",
        schema_versions=("posterior_score.v1", "posterior_objective.v1"),
        implementation_refs=tuple(
            ref for ref in SOURCE_REF_POSTERIOR_OBJECTIVE if ref.startswith("impl:")
        ),
        design_refs=tuple(
            ref for ref in SOURCE_REF_POSTERIOR_OBJECTIVE if ref.startswith("sid:")
        ),
    ),
    FormulaVersionEntry(
        formula_id="runtime_adjustment",
        formula_version="runtime_adjustment.v1",
        role="基于 runtime state 的候选分数修正公式归档版本。",
        schema_versions=("runtime_adjustment.v1",),
        implementation_refs=tuple(
            ref for ref in SOURCE_REF_RUNTIME_ADJUSTMENT if ref.startswith("impl:")
        ),
        design_refs=tuple(
            ref for ref in SOURCE_REF_RUNTIME_ADJUSTMENT if ref.startswith("sid:")
        ),
    ),
    FormulaVersionEntry(
        formula_id="action_utility",
        formula_version="action_utility.v1",
        role="continue/patch_local/suffix_replan/stop 动作效用公式归档版本。",
        schema_versions=("action_utility.v1", "action_features.v1"),
        implementation_refs=tuple(
            ref for ref in SOURCE_REF_ACTION_UTILITY if ref.startswith("impl:")
        ),
        design_refs=tuple(
            ref for ref in SOURCE_REF_ACTION_UTILITY if ref.startswith("sid:")
        ),
    ),
    FormulaVersionEntry(
        formula_id="action_bias",
        formula_version="action_bias.v1",
        role="runtime delta 的动作偏置解释层归档版本。",
        schema_versions=("action_bias.v1",),
        implementation_refs=tuple(
            ref for ref in SOURCE_REF_ACTION_BIAS if ref.startswith("impl:")
        ),
        design_refs=tuple(
            ref for ref in SOURCE_REF_ACTION_BIAS if ref.startswith("sid:")
        ),
    ),
)

CEBRA_WP_FORMULA_VERSION_BY_ID: Final[dict[str, FormulaVersionEntry]] = {
    entry.formula_id: entry
    for entry in CEBRA_WP_FORMULA_VERSION_ENTRIES
}


def formula_version_entry(formula_id: str) -> FormulaVersionEntry:
    """按公式 ID 返回版本条目。"""

    return CEBRA_WP_FORMULA_VERSION_BY_ID[formula_id]
