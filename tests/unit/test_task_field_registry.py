from __future__ import annotations

from src.models.task_intake import (
    TASK_FIELD_GROUPS,
    build_task_intake_schema,
    confirm_task_intake_session,
    create_task_intake_session,
)


def test_task_field_registry_exposes_required_contract_shape() -> None:
    """TaskFieldRegistry 应覆盖固定分组和字段契约键。"""

    schema = build_task_intake_schema()

    assert schema["version"] == "task-intake.v1"
    assert schema["groups"] == list(TASK_FIELD_GROUPS)
    assert set(schema["web_schema"]["groups"][0]) == {"id", "fields"}
    for field in schema["fields"].values():
        assert {
            "group",
            "type",
            "ui_control",
            "nl_aliases",
            "validators",
            "options",
            "default",
            "maps_to",
            "support_level",
            "audit_visibility",
        } <= set(field)
        assert field["group"] in TASK_FIELD_GROUPS


def test_task_profiles_mark_support_levels_and_capability_hints() -> None:
    """P0/P1/P2 场景模板应显式标注能力承诺边界。"""

    schema = build_task_intake_schema()
    profiles = schema["task_profiles"]

    assert profiles["de_novo_design"]["support_level"] == "P0"
    assert profiles["sequence_evaluation"]["support_level"] == "P0"
    assert profiles["template_constrained_design"]["support_level"] == "P0"
    assert profiles["stability_optimization"]["support_level"] == "P1"
    assert profiles["motif_scaffold_design"]["support_level"] == "P1"
    assert profiles["binding_design"]["support_level"] == "P2"
    assert profiles["enzyme_like_design"]["support_level"] == "P2"
    assert schema["planner_capability_hints"]["binding_design"] == [
        "binding_design",
        "docking_scoring",
    ]


def test_tool_selection_fields_defer_candidates_to_toolkg() -> None:
    """工具选择字段应从 ToolKG 派生候选，避免前端硬编码。"""

    schema = build_task_intake_schema()

    assert any(option["tool_id"] == "esmfold" for option in schema["tool_options"])
    for name in ("tools_allowed", "tools_excluded"):
        field = schema["fields"][name]
        assert field["ui_control"] == "multi_select"
        assert "esmfold" in field["options"]
        assert field["tool_options"][0]["tool_id"]
        assert field["validators"] == {"source": "ToolKG"}


def test_registry_derives_cli_llm_and_confirmed_spec_mapping() -> None:
    """Web/CLI/LLM/ConfirmedTaskSpec 视图应来自同一份 registry。"""

    schema = build_task_intake_schema()

    cli_flags = {entry["field"]: entry["flag"] for entry in schema["cli_arguments"]}
    cli_questions = {
        entry["field"]: entry["prompt"] for entry in schema["cli_questions"]
    }
    assert cli_flags["length_range"] == "--length-range"
    assert "length_range" in cli_questions["length_range"]
    assert schema["llm_extraction_schema"]["properties"]["task_kind"]["enum"]
    assert (
        schema["confirmed_task_spec_mapping"]["objective_type"]
        == "objective.objective_type"
    )


def test_confirmed_spec_carries_planner_capability_hints() -> None:
    """确认后的任务规格应带上 profile 派生的 Planner hints。"""

    session = create_task_intake_session(
        intake_id="intake_registry",
        text=None,
        structured_fields={
            "task_kind": "de_novo_design",
            "objective_type": "stability",
            "length_range": [100, 140],
        },
        source="api",
    )

    spec = confirm_task_intake_session(
        session,
        confirmed_by="tester",
        acknowledged_warnings=[],
    )

    assert spec.constraints["length_range"] == [100, 140]
    assert spec.metadata["planner_capability_hints"] == [
        "sequence_generation",
        "structure_prediction",
    ]


def test_profile_conditional_required_fields_are_enforced() -> None:
    """profile conditional_required 应参与缺失字段计算。"""

    session = create_task_intake_session(
        intake_id="intake_binding",
        text=None,
        structured_fields={
            "task_kind": "binding_design",
            "objective_type": "binding",
        },
        source="api",
    )

    assert session.missing_required_fields == ["binding_partner"]
