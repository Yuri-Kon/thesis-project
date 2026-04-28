from __future__ import annotations

from src.models.task_intake import (
    TASK_FIELD_GROUPS,
    build_task_intake_schema,
    confirm_task_intake_session,
    create_task_intake_session,
    extract_task_intake_fields,
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
    assert schema["llm_extraction_schema"]["additionalProperties"] is False
    task_kind_schema = schema["llm_extraction_schema"]["properties"]["task_kind"]
    assert task_kind_schema["additionalProperties"] is False
    assert task_kind_schema["properties"]["source"]["const"] == "llm_extract"
    assert task_kind_schema["properties"]["value"]["enum"]
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


def test_natural_language_extraction_captures_p0_fields_with_confidence() -> None:
    """自然语言抽取应只写入带来源和置信度的 TaskSpecDraft 字段。"""

    draft = extract_task_intake_fields(
        "帮我设计一个大约120个氨基酸、稳定性优先的小蛋白，"
        "生成8个候选，先用快一点的模式，S1，最后需要我确认计划。"
    )

    assert draft.extraction_mode == "rule_extract"
    assert draft.fields["task_kind"].value == "de_novo_design"
    assert draft.fields["goal_summary"].source.value == "llm_extract"
    assert draft.fields["objective_type"].value == "stability"
    assert draft.fields["length_range"].value == [100, 140]
    assert draft.fields["design_count"].value == 8
    assert draft.fields["run_profile"].value == "fast_smoke"
    assert draft.fields["safety_level"].value == "S1"
    assert draft.fields["require_plan_confirm"].value is True
    assert draft.fields["length_range"].source_span == "大约120个氨基酸"
    assert all(field.confirmed is False for field in draft.fields.values())


def test_extraction_confidence_thresholds_and_run_profile_values() -> None:
    """低置信度字段应按阈值进入 ambiguous 或 unmapped。"""

    session = create_task_intake_session(
        intake_id="intake_thresholds",
        text=None,
        structured_fields={
            "task_kind": "de_novo_design",
            "objective_type": {
                "value": "binding",
                "confidence": 0.72,
                "source_span": "binding",
            },
            "goal_summary": {
                "value": "ignored",
                "confidence": 0.40,
                "source_span": "low confidence summary",
            },
            "length_range": [80, 120],
            "run_profile": "high_accuracy",
        },
        source="api",
    )

    assert "objective_type" in session.ambiguous_fields
    assert "goal_summary" not in session.draft.fields
    assert "goal_summary=ignored" in session.unmapped_text
    assert session.draft.fields["run_profile"].value == "high_accuracy"


def test_extraction_rejects_invalid_schema_and_falls_back_to_manual_form() -> None:
    """schema 不合法的抽取候选重试耗尽后应降级到手动表单。"""

    draft = extract_task_intake_fields(
        "design a stable protein around 120 aa",
        raw_candidates=[
            {
                "fields": {
                    "not_in_registry": {
                        "value": "x",
                        "source": "llm_extract",
                        "confidence": 0.9,
                    }
                }
            },
            {
                "fields": {
                    "run_profile": {
                        "value": "esmfold",
                        "source": "llm_extract",
                        "confidence": 0.9,
                    }
                }
            },
        ],
        max_attempts=2,
    )

    assert draft.extraction_mode == "manual_fallback"
    assert draft.fields == {}
    assert draft.unmapped_text == ["design a stable protein around 120 aa"]
    assert any("unknown field" in error for error in draft.extraction_errors)
    assert any("run_profile must be one of" in error for error in draft.extraction_errors)


def test_natural_language_tool_preference_is_validated_against_toolkg() -> None:
    """自然语言工具偏好只能进入 ToolKG 校验过的工具字段。"""

    draft = extract_task_intake_fields(
        "请设计稳定蛋白，around 120 aa，prefer esmfold tool，fast mode"
    )

    assert draft.fields["run_profile"].value == "fast_smoke"
    assert draft.fields["tools_allowed"].value == ["esmfold"]
    assert draft.fields["tools_allowed"].confidence < 0.80
