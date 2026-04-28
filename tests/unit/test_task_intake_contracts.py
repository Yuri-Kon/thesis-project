from __future__ import annotations

import pytest

from src.models.task_intake import (
    ConfirmedTaskSpec,
    TaskDraftField,
    TaskDraftFieldSource,
    TaskIntakeSession,
    TaskIntakeStatus,
    TaskSpecDraft,
    confirm_task_intake_session,
    create_task_intake_session,
    project_confirmed_task_spec,
)


def test_task_intake_session_defaults_and_status_values() -> None:
    """TaskIntakeSession 应表达前置录入状态和审计集合默认值。"""

    session = TaskIntakeSession(intake_id="intake_defaults")

    assert session.status == TaskIntakeStatus.COLLECTING
    assert set(TaskIntakeStatus) == {
        TaskIntakeStatus.COLLECTING,
        TaskIntakeStatus.NEEDS_CONFIRMATION,
        TaskIntakeStatus.CONFIRMED,
        TaskIntakeStatus.CANCELLED,
    }
    assert session.raw_input == {}
    assert session.draft == TaskSpecDraft()
    assert session.missing_required_fields == []
    assert session.ambiguous_fields == []
    assert session.unmapped_text == []
    assert session.warnings == []
    assert session.safety_check.action == "ok"
    assert session.audit_events == []


def test_task_draft_field_source_and_confirmation_contract() -> None:
    """TaskSpecDraft 字段包装应保留来源、置信度、确认和修改审计。"""

    field = TaskDraftField(
        value="stability",
        source=TaskDraftFieldSource.USER_EXPLICIT,
        confidence=0.9,
        source_span="stable",
        confirmed=True,
        warnings=["checked"],
        last_modified_by="tester",
    )

    assert {source.value for source in TaskDraftFieldSource} == {
        "user_explicit",
        "llm_extract",
        "system_default",
        "kg_derived",
        "user_modified",
    }
    assert field.model_dump(mode="json") == {
        "value": "stability",
        "source": "user_explicit",
        "confidence": 0.9,
        "source_span": "stable",
        "confirmed": True,
        "warnings": ["checked"],
        "last_modified_by": "tester",
    }


def test_task_intake_session_serialization_round_trip() -> None:
    """TaskIntakeSession 应支持稳定序列化/反序列化。"""

    session = create_task_intake_session(
        intake_id="intake_roundtrip",
        text="design de novo stable protein around 120 aa",
        structured_fields={},
        source="api",
    )

    restored = TaskIntakeSession.model_validate(session.model_dump(mode="json"))

    assert restored == session
    assert restored.draft.fields["task_kind"].source == TaskDraftFieldSource.LLM_EXTRACT
    assert restored.draft.fields["length_range"].value == [100, 140]


def test_confirmed_task_spec_projection_to_protein_design_task_shape() -> None:
    """ConfirmedTaskSpec 应可投影到现有 ProteinDesignTask 字段。"""

    spec = ConfirmedTaskSpec(
        goal="de_novo_design for stability",
        objective={"objective_type": "stability"},
        inputs={"sequence": "ACDE"},
        constraints={"length_range": [4, 8]},
        initial_artifacts=[{"kind": "sequence", "path": "input.fa"}],
        metadata={
            "intake_id": "intake_projection",
            "field_registry_version": "task-intake.v1",
            "support_level": "P0",
            "confirmed_by": "tester",
            "input_mode": "structured_with_confirmation",
            "acknowledged_warnings": [],
        },
    )

    goal, constraints, metadata = project_confirmed_task_spec(spec)

    assert goal == "de_novo_design for stability"
    assert constraints["length_range"] == [4, 8]
    assert constraints["objective"] == {"objective_type": "stability"}
    assert constraints["inputs"] == {"sequence": "ACDE"}
    assert metadata["intake_id"] == "intake_projection"
    assert metadata["confirmed_task_spec"]["initial_artifacts"] == [
        {"kind": "sequence", "path": "input.fa"}
    ]


def test_confirmed_task_spec_metadata_contains_required_audit_keys() -> None:
    """确认流程应保留 issue 要求的 metadata 审计键。"""

    session = create_task_intake_session(
        intake_id="intake_confirmed",
        text="design stable binding protein around 130 aa",
        structured_fields={
            "task_kind": "de_novo_design",
            "objective_type": "stability",
            "length_range": [120, 150],
        },
        source="web",
    )
    spec = confirm_task_intake_session(
        session,
        confirmed_by="tester",
        acknowledged_warnings=["reviewed"],
    )

    assert {
        "intake_id",
        "field_registry_version",
        "support_level",
        "confirmed_by",
        "input_mode",
        "acknowledged_warnings",
    } <= set(spec.metadata)
    assert spec.metadata["acknowledged_warnings"] == ["reviewed"]
    assert session.status == TaskIntakeStatus.CONFIRMED
    assert all(field.confirmed for field in session.draft.fields.values())


def test_structured_fields_override_raw_text_extraction() -> None:
    """原始自然语言只能进入 audit，不能覆盖已确认结构化字段。"""

    session = create_task_intake_session(
        intake_id="intake_raw_text",
        text="please evaluate binding protein around 300 aa",
        structured_fields={
            "task_kind": "de_novo_design",
            "objective_type": "stability",
            "length_range": [80, 120],
        },
        source="web",
    )
    spec = confirm_task_intake_session(
        session,
        confirmed_by="tester",
        acknowledged_warnings=[],
    )

    assert spec.constraints["task_kind"] == "de_novo_design"
    assert spec.objective["objective_type"] == "stability"
    assert spec.constraints["length_range"] == [80, 120]
    assert spec.metadata["raw_query"] == "please evaluate binding protein around 300 aa"


def test_intake_normalizes_units_and_carries_initial_artifacts() -> None:
    """Task Intake 应归一化单位并把合法 artifact ref 投影到确认规格。"""

    session = create_task_intake_session(
        intake_id="intake_units_artifacts",
        text=None,
        structured_fields={
            "task_kind": "de_novo_design",
            "objective_type": "stability",
            "length_range": {"min": 90, "max": 120, "unit": "aa"},
            "max_runtime_min": {"value": 2, "unit": "hour"},
            "initial_artifacts": [
                {"kind": "template", "path": "input/template.pdb"}
            ],
        },
        source="api",
    )

    spec = confirm_task_intake_session(
        session,
        confirmed_by="tester",
        acknowledged_warnings=[],
    )

    assert spec.constraints["length_range"] == [90, 120]
    assert spec.constraints["max_runtime_min"] == 120
    assert spec.initial_artifacts == [{"kind": "template", "path": "input/template.pdb"}]


def test_safety_warn_requires_acknowledgement_and_is_audited() -> None:
    """Safety warn 不阻止录入，但 confirm 前必须显式确认。"""

    session = create_task_intake_session(
        intake_id="intake_warn",
        text=None,
        structured_fields={
            "task_kind": "sequence_evaluation",
            "objective_type": "stability",
            "sequence": "ACDEFG",
            "forbidden_motifs": ["CDE"],
        },
        source="api",
    )

    assert session.safety_check.action == "warn"
    assert session.safety_check.risk_flags[0].code == "FORBIDDEN_MOTIF_PRESENT"
    assert "forbidden_motifs contains motif" in session.warnings[0]

    with pytest.raises(ValueError, match="--ack-warning"):
        confirm_task_intake_session(
            session,
            confirmed_by="tester",
            acknowledged_warnings=[],
        )

    spec = confirm_task_intake_session(
        session,
        confirmed_by="tester",
        acknowledged_warnings=["FORBIDDEN_MOTIF_PRESENT"],
    )

    assert spec.metadata["acknowledged_warnings"] == ["FORBIDDEN_MOTIF_PRESENT"]
    assert spec.metadata["safety_check"]["action"] == "warn"
    assert "INTAKE_CONFIRMED" in {
        event["event_type"] for event in spec.metadata["intake_audit_events"]
    }


def test_safety_block_prevents_confirmed_task_spec() -> None:
    """Safety block 不能被 acknowledgement 绕过。"""

    session = create_task_intake_session(
        intake_id="intake_block",
        text="design a toxin-like protein",
        structured_fields={
            "task_kind": "de_novo_design",
            "objective_type": "stability",
            "length_range": [80, 120],
        },
        source="api",
    )

    assert session.safety_check.action == "block"

    with pytest.raises(ValueError, match="blocked confirmation"):
        confirm_task_intake_session(
            session,
            confirmed_by="tester",
            acknowledged_warnings=["HIGH_RISK_BIOFUNCTION_REQUEST"],
        )

    assert session.confirmed_task_spec is None
