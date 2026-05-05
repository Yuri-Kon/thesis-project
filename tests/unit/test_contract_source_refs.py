"""ScoreSummary / RuntimeAdjustmentSummary source_refs 兼容性测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.contracts import (
    ActionBiasSummary,
    RuntimeAdjustmentFactor,
    RuntimeAdjustmentSummary,
    ScoreSummary,
)
from src.models.source_refs import (
    SOURCE_REF_ACTION_BIAS,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
    as_source_refs,
)


def test_score_summary_source_refs_default_factory_keeps_old_constructors() -> None:
    summary = ScoreSummary(value=0.5, source="score_breakdown.overall.static.v1")
    assert summary.source_refs == []


def test_runtime_adjustment_source_refs_default_factory_keeps_old_constructors() -> None:
    summary = RuntimeAdjustmentSummary(
        value=0.1,
        source="planner.runtime_adjustment.continue.v1",
    )
    assert summary.source_refs == []


def test_runtime_adjustment_accepts_source_refs() -> None:
    summary = RuntimeAdjustmentSummary(
        value=0.1,
        source="planner.runtime_adjustment.continue.v1",
        source_refs=as_source_refs(*SOURCE_REF_RUNTIME_ADJUSTMENT),
    )
    assert "sid:planner.algorithm.runtime_adjustment_formula" in summary.source_refs
    assert "impl:planner.runtime_adjustment.v1" in summary.source_refs


def test_runtime_adjustment_accepts_action_bias() -> None:
    factor = RuntimeAdjustmentFactor(
        category="recovery",
        signal="fallback_depth",
        source="score_breakdown.fallback_depth",
        contribution=0.02,
        message="Local recovery bias.",
    )
    action_bias = ActionBiasSummary(
        action="patch_local",
        value=0.02,
        factors=[factor],
        source_refs=as_source_refs(*SOURCE_REF_ACTION_BIAS),
    )
    summary = RuntimeAdjustmentSummary(
        value=0.02,
        source="planner.runtime_adjustment.patch_local.v1",
        source_refs=as_source_refs(*SOURCE_REF_RUNTIME_ADJUSTMENT),
        action_bias=action_bias,
    )

    assert summary.action_bias is not None
    assert summary.action_bias.value == pytest.approx(summary.value)
    assert "impl:runtime_evaluator.compute_runtime_delta.v1" in summary.action_bias.source_refs


def test_score_summary_rejects_empty_source_ref() -> None:
    with pytest.raises(ValidationError):
        _ = ScoreSummary(
            value=0.5,
            source="score_breakdown.overall.static.v1",
            source_refs=["sid:algo.adaptive.optimization_objective", " "],
        )
