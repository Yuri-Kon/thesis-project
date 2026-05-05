from __future__ import annotations

import pytest

from src.models.budget_pressure import derive_budget_pressure


@pytest.mark.unit
def test_budget_pressure_normalizes_by_budget_cap() -> None:
    high_cap = derive_budget_pressure(
        expected_remaining_cost=1.2,
        budget_cap=2.0,
    )
    low_cap = derive_budget_pressure(
        expected_remaining_cost=1.2,
        budget_cap=0.5,
    )

    assert high_cap.expected_remaining_cost == pytest.approx(1.2)
    assert high_cap.budget_pressure == pytest.approx(0.6)
    assert low_cap.budget_pressure == pytest.approx(1.5)
    assert high_cap.source_fields == (
        "runtime_state.expected_remaining_cost",
        "runtime_state.budget_cap",
    )


@pytest.mark.unit
def test_budget_pressure_falls_back_to_clipped_remaining_cost() -> None:
    derivation = derive_budget_pressure(expected_remaining_cost=2.2)

    assert derivation.budget_pressure == pytest.approx(1.5)
    assert derivation.budget_cap is None
    assert derivation.source_fields == ("runtime_state.expected_remaining_cost",)
