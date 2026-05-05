"""source_refs 常量与 helper 测试。"""

from __future__ import annotations

import pytest

from src.models.source_refs import (
    SOURCE_REF_ACTION_SELECTION,
    SOURCE_REF_ACTION_UTILITY,
    SOURCE_REF_DEFAULT_ACTION_UTILITY,
    SOURCE_REF_FEASIBILITY,
    SOURCE_REF_POSTERIOR_OBJECTIVE,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
    SOURCE_REF_STATIC_SCORE,
    SOURCE_REF_TERMINAL_STOP,
    as_source_refs,
    design_ref_status_for,
)

_REF_GROUPS = (
    SOURCE_REF_FEASIBILITY,
    SOURCE_REF_POSTERIOR_OBJECTIVE,
    SOURCE_REF_STATIC_SCORE,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
    SOURCE_REF_ACTION_UTILITY,
    SOURCE_REF_DEFAULT_ACTION_UTILITY,
    SOURCE_REF_ACTION_SELECTION,
    SOURCE_REF_TERMINAL_STOP,
)


def test_source_ref_groups_have_sid_and_impl() -> None:
    for refs in _REF_GROUPS:
        assert all(ref for ref in refs)
        assert any(ref.startswith("sid:") for ref in refs)
        assert any(ref.startswith("impl:") for ref in refs)
        assert all(":proposed" not in ref for ref in refs)


def test_as_source_refs_deduplicates_in_order() -> None:
    assert as_source_refs(" sid:a ", "impl:x", "sid:a") == ["sid:a", "impl:x"]


def test_as_source_refs_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="source_refs items must not be empty"):
        _ = as_source_refs("sid:a", " ")


def test_design_ref_status_for_reports_proposed_separately() -> None:
    assert design_ref_status_for(*SOURCE_REF_ACTION_UTILITY) == {
        "sid:algo.action_feature_derivation": "proposed",
    }
