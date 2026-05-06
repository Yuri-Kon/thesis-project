import pytest

from src.workflow.action_features import ACTION_FEATURE_NAMES, derive_action_features
from src.workflow.errors import FailureType


@pytest.mark.unit
def test_derives_all_required_features_with_sources():
    derivation = derive_action_features(runtime_state={})

    assert set(derivation.values) == set(ACTION_FEATURE_NAMES)
    assert derivation.values["intervention_value"] == pytest.approx(0.5)
    for name in ACTION_FEATURE_NAMES:
        feature = derivation.features[name]
        assert 0.0 <= feature.value <= 1.5
        assert feature.source in {"observed", "inferred", "default", "unknown"}
        assert isinstance(feature.source_fields, tuple)
        assert feature.reason


@pytest.mark.unit
def test_intervention_value_is_inferred_when_context_is_available():
    derivation = derive_action_features(
        runtime_state={
            "p_success": 0.18,
            "p_structural_failure": 0.62,
            "recovery_margin": 0.12,
            "expected_remaining_cost": 1.1,
            "evidence_sufficiency": 0.66,
        },
        failure_type=FailureType.NON_RETRYABLE,
        retry_exhausted=True,
    )

    feature = derivation.features["intervention_value"]
    assert feature.source == "inferred"
    assert feature.value > 0.0
    assert "derived.local_patchability" in feature.source_fields


@pytest.mark.unit
def test_safety_block_sets_safety_terminality():
    derivation = derive_action_features(
        runtime_state={"p_success": 0.5},
        failure_type=FailureType.SAFETY_BLOCK,
        safety_blocked=True,
    )

    feature = derivation.features["safety_terminality"]
    assert feature.value == pytest.approx(1.0)
    assert feature.source == "inferred"


@pytest.mark.unit
def test_retryable_tool_error_increases_local_patchability():
    base = derive_action_features(
        runtime_state={
            "recovery_margin": 0.4,
            "p_structural_failure": 0.4,
            "evidence_sufficiency": 0.5,
        }
    )
    retryable = derive_action_features(
        runtime_state={
            "recovery_margin": 0.4,
            "p_structural_failure": 0.4,
            "evidence_sufficiency": 0.5,
        },
        failure_type=FailureType.TOOL_ERROR,
        retry_exhausted=True,
    )

    assert retryable.values["local_patchability"] > base.values["local_patchability"]


@pytest.mark.unit
def test_failed_suffix_step_increases_prefix_preservability():
    first_step = derive_action_features(
        runtime_state={
            "recovery_margin": 0.5,
            "evidence_sufficiency": 0.5,
            "expected_remaining_cost": 0.5,
        },
        failed_step_index=0,
    )
    suffix_step = derive_action_features(
        runtime_state={
            "recovery_margin": 0.5,
            "evidence_sufficiency": 0.5,
            "expected_remaining_cost": 0.5,
        },
        completed_step_count=2,
        failed_step_index=2,
    )

    assert suffix_step.values["prefix_preservability"] > first_step.values["prefix_preservability"]


@pytest.mark.unit
def test_high_budget_pressure_does_not_default_to_high_budget_relief():
    derivation = derive_action_features(
        runtime_state={
            "expected_remaining_cost": 1.2,
            "recovery_margin": 0.1,
            "evidence_sufficiency": 0.2,
        }
    )

    assert derivation.values["budget_relief"] == pytest.approx(0.45)
    assert derivation.features["budget_relief"].source == "inferred"


@pytest.mark.unit
def test_budget_pressure_uses_budget_cap_when_available():
    high_cap = derive_action_features(
        runtime_state={
            "expected_remaining_cost": 1.2,
            "budget_cap": 2.0,
        }
    )
    low_cap = derive_action_features(
        runtime_state={
            "expected_remaining_cost": 1.2,
            "budget_cap": 0.5,
        }
    )

    assert high_cap.values["budget_pressure"] == pytest.approx(0.6)
    assert low_cap.values["budget_pressure"] == pytest.approx(1.5)
    assert "runtime_state.budget_cap" in high_cap.features["budget_pressure"].source_fields
    assert high_cap.values["budget_relief"] == pytest.approx(low_cap.values["budget_relief"])


@pytest.mark.unit
def test_observed_values_take_priority():
    derivation = derive_action_features(
        runtime_state={
            "local_patchability": 0.2,
            "intervention_value": 0.1,
            "safety_terminality": 0.0,
        },
        failure_type=FailureType.SAFETY_BLOCK,
        safety_blocked=True,
    )

    assert derivation.values["local_patchability"] == pytest.approx(0.2)
    assert derivation.features["local_patchability"].source == "observed"
    assert derivation.values["intervention_value"] == pytest.approx(0.1)
    assert derivation.features["intervention_value"].source == "observed"
    assert derivation.values["safety_terminality"] == pytest.approx(0.0)
    assert derivation.features["safety_terminality"].source == "observed"
