"""ScoreSummary / RuntimeAdjustmentSummary source_refs 兼容性测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.contracts import RuntimeAdjustmentSummary, ScoreSummary
from src.models.source_refs import SOURCE_REF_RUNTIME_ADJUSTMENT, as_source_refs


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


def test_score_summary_rejects_empty_source_ref() -> None:
    with pytest.raises(ValidationError):
        _ = ScoreSummary(
            value=0.5,
            source="score_breakdown.overall.static.v1",
            source_refs=["sid:algo.adaptive.optimization_objective", " "],
        )
