"""CEBRA-WP 算法版本 registry 测试。"""

from __future__ import annotations

from pathlib import Path

from src.models.algorithm_versions import (
    CEBRA_WP_ALGORITHM_VERSION,
    CEBRA_WP_DOC_VERSION,
    CEBRA_WP_FORMULA_VERSION_BY_ID,
    CEBRA_WP_FORMULA_VERSION_ENTRIES,
    formula_version_entry,
)


def test_cebra_wp_formula_versions_are_archived_under_algorithm_version() -> None:
    assert CEBRA_WP_ALGORITHM_VERSION == "cebra_wp.v2"
    assert CEBRA_WP_DOC_VERSION == "core-algorithm-theory-v2"
    assert [entry.formula_id for entry in CEBRA_WP_FORMULA_VERSION_ENTRIES] == [
        "static_score",
        "posterior_score",
        "runtime_adjustment",
        "action_utility",
        "action_bias",
    ]


def test_formula_version_registry_uses_stable_v1_children() -> None:
    assert formula_version_entry("static_score").formula_version == "static_score.v1"
    assert formula_version_entry("posterior_score").schema_versions == (
        "posterior_score.v1",
        "posterior_objective.v1",
    )
    assert formula_version_entry("runtime_adjustment").formula_version == (
        "runtime_adjustment.v1"
    )
    assert formula_version_entry("action_utility").formula_version == "action_utility.v1"
    assert formula_version_entry("action_bias").formula_version == "action_bias.v1"


def test_formula_version_entries_link_design_and_impl_refs() -> None:
    assert set(CEBRA_WP_FORMULA_VERSION_BY_ID) == {
        entry.formula_id
        for entry in CEBRA_WP_FORMULA_VERSION_ENTRIES
    }
    for entry in CEBRA_WP_FORMULA_VERSION_ENTRIES:
        assert entry.implementation_refs
        assert entry.design_refs
        assert all(ref.startswith("impl:") for ref in entry.implementation_refs)
        assert all(ref.startswith("sid:") for ref in entry.design_refs)


def test_algorithm_version_registry_doc_mentions_code_registry_entries() -> None:
    doc = Path("docs/algorithm-and-llm/algorithm-version-registry.md").read_text(
        encoding="utf-8",
    )
    assert CEBRA_WP_ALGORITHM_VERSION in doc
    assert CEBRA_WP_DOC_VERSION in doc
    for entry in CEBRA_WP_FORMULA_VERSION_ENTRIES:
        assert entry.formula_version in doc
        for ref in entry.implementation_refs:
            assert ref in doc
