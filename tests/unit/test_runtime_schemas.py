from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.contracts import (
    ACTION_UTILITY_METADATA_KEY,
    PendingActionCandidate,
    Plan,
)
from src.models.runtime_schemas import (
    ActionUtility,
    CostSchema,
    ObservationSchema,
    RecoverySchema,
    RiskSchema,
    RuntimeStateSchema,
    StateSchema,
    runtime_schema_field_mappings,
)


def _plan() -> Plan:
    return Plan(task_id="task_runtime_schema", steps=[])


def test_six_runtime_schemas_serialize_with_stable_defaults() -> None:
    """六类运行时 schema 应具备可序列化的稳定缺省值。"""

    cost = CostSchema(compute_cost=0.4, latency_cost=0.2)
    risk = RiskSchema(structural_risk=0.3, execution_risk=0.2)
    recovery = RecoverySchema(
        retry_budget_ratio=0.5,
        local_patchability=0.6,
        prefix_preservability=0.7,
        evidence_reusability=0.8,
    )
    state = RuntimeStateSchema()
    observation = ObservationSchema(
        source_refs=[
            {
                "source_type": "step_result",
                "ref": "StepResult:S2",
                "fields": ["metrics.plddt"],
            }
        ]
    )
    utility = ActionUtility(
        action="patch_local",
        utility=0.71,
        hard_constraints=["retry_exhausted"],
        tie_break_reason="local patchability wins",
        intervention_value=0.4,
        budget_pressure=0.3,
    )

    assert cost.weighted_cost() == pytest.approx(0.19)
    assert risk.weighted_risk() == pytest.approx(0.185)
    assert recovery.recoverability() == pytest.approx(0.625)
    assert recovery.recovery_complexity() == pytest.approx(0.375)
    assert state.to_summary_payload() == {
        "schema_version": 1,
        "p_success": 0.5,
        "p_structural_failure": 0.25,
        "recovery_margin": 0.6,
        "expected_remaining_cost": 1.0,
        "evidence_sufficiency": 0.5,
    }
    assert StateSchema is RuntimeStateSchema
    assert observation.model_dump()["source_refs"][0]["source_type"] == "step_result"
    assert utility.model_dump(exclude_none=True)["action"] == "patch_local"


def test_runtime_state_schema_restores_legacy_snapshot_payload() -> None:
    """旧快照缺字段时仍可恢复到 v1 缺省。"""

    restored = RuntimeStateSchema.from_snapshot_payload({"p_success": 0.8})

    assert restored.schema_version == 1
    assert restored.p_success == pytest.approx(0.8)
    assert restored.p_structural_failure == pytest.approx(0.25)
    assert restored.evidence_sufficiency == pytest.approx(0.5)
    assert restored.to_snapshot_payload()["last_update_source"] == "runtime_bootstrap"


def test_observation_schema_rejects_unapproved_sources() -> None:
    """Observation 只能引用设计文档允许的运行时来源。"""

    with pytest.raises(ValidationError):
        ObservationSchema(
            source_refs=[
                {
                    "source_type": "planner_free_text",
                    "ref": "Plan.metadata.note",
                }
            ]
        )


def test_action_utility_metadata_is_normalized_on_candidate() -> None:
    """候选 ActionUtility 应契约化，供 planner/event/UI 复用。"""

    candidate = PendingActionCandidate(
        candidate_id="cand_patch",
        payload=_plan(),
        score_breakdown={"overall": 0.7},
        metadata={
            ACTION_UTILITY_METADATA_KEY: {
                "action": "patch_local",
                "utility": 0.72,
                "hard_constraints": ["retry_exhausted"],
                "intervention_value": 0.45,
                "budget_pressure": 0.2,
            }
        },
    )

    utility = candidate.metadata[ACTION_UTILITY_METADATA_KEY]
    assert utility["schema_version"] == 1
    assert utility["action"] == "patch_local"
    assert utility["hard_constraints"] == ["retry_exhausted"]


def test_runtime_field_mapping_covers_shared_consumers() -> None:
    """字段映射应明确 snapshot/event/planner/UI/CLI 的稳定来源。"""

    mapping = runtime_schema_field_mappings()

    assert set(mapping) == {
        "cost",
        "risk",
        "recovery",
        "state",
        "observation",
        "action_utility",
    }
    assert "score_breakdown.cost" in mapping["cost"]["ui_summary_fields"]
    assert "score_breakdown.risk" in mapping["risk"]["cli_summary_fields"]
    assert "recovery_semantics" in mapping["recovery"]["ui_summary_fields"]
    assert "artifacts.runtime_state" in mapping["state"]["snapshot_fields"]
    assert "data.runtime_state_summary" in mapping["state"]["event_fields"]
    assert (
        "metadata.runtime_state_summary"
        in mapping["state"]["planner_metadata_fields"]
    )
    assert "runtime_state_summary" in mapping["state"]["ui_summary_fields"]
    assert "runtime_state_summary" in mapping["state"]["cli_summary_fields"]
    assert "metadata.action_utility" in mapping["action_utility"][
        "planner_metadata_fields"
    ]
