from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.models.contracts import now_iso


TASK_FIELD_REGISTRY_VERSION = "task-intake.v1"
HIGH_CONFIDENCE_THRESHOLD = 0.80
LOW_CONFIDENCE_THRESHOLD = 0.50


class TaskIntakeStatus(str, Enum):
    """Task Intake 前置录入状态。"""

    COLLECTING = "collecting"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class TaskDraftFieldSource(str, Enum):
    """TaskSpecDraft 字段来源。"""

    USER_EXPLICIT = "user_explicit"
    LLM_EXTRACT = "llm_extract"
    SYSTEM_DEFAULT = "system_default"
    KG_DERIVED = "kg_derived"
    USER_MODIFIED = "user_modified"


class TaskDraftField(BaseModel):
    """TaskSpecDraft 中单个字段的可审计包装。"""

    value: Any
    source: TaskDraftFieldSource
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_span: str | None = None
    confirmed: bool = False
    warnings: list[str] = Field(default_factory=list)
    last_modified_by: str | None = None


class TaskSpecDraft(BaseModel):
    """可编辑、可解释的任务草稿。"""

    fields: dict[str, TaskDraftField] = Field(default_factory=dict)
    unmapped_text: list[str] = Field(default_factory=list)


class ConfirmedTaskSpec(BaseModel):
    """唯一允许进入正式 Task 创建的结构化输入。"""

    goal: str
    objective: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    initial_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("goal")
    @classmethod
    def _validate_goal(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("goal must not be empty")
        return normalized


class TaskIntakeSession(BaseModel):
    """一次正式 Task 创建前的录入会话。"""

    intake_id: str
    status: TaskIntakeStatus
    raw_input: dict[str, Any] = Field(default_factory=dict)
    draft: TaskSpecDraft = Field(default_factory=TaskSpecDraft)
    missing_required_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    unmapped_text: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    confirmed_task_spec: ConfirmedTaskSpec | None = None


class TaskIntakeCreateRequest(BaseModel):
    """创建 Task Intake 会话的请求。"""

    text: str | None = None
    structured_fields: dict[str, Any] = Field(default_factory=dict)
    source: Literal["web", "cli", "api", "script", "legacy"] = "api"


class TaskIntakePatchRequest(BaseModel):
    """更新 Task Intake 草稿字段的请求。"""

    fields: dict[str, Any] = Field(default_factory=dict)
    updated_by: str = "user"


class TaskIntakeConfirmRequest(BaseModel):
    """确认 Task Intake 并生成 ConfirmedTaskSpec 的请求。"""

    confirmed_by: str
    acknowledged_warnings: list[str] = Field(default_factory=list)


class IntentDraftClarificationRequest(BaseModel):
    """旧 IntentDraft clarification 入口的兼容请求。"""

    text: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    structured_fields: dict[str, Any] = Field(default_factory=dict)
    updated_by: str = "user"


def build_task_intake_schema() -> dict[str, Any]:
    """生成 Web/CLI 共享的字段注册表视图。"""

    return {
        "version": TASK_FIELD_REGISTRY_VERSION,
        "fields": _registry_fields(),
        "task_profiles": _task_profiles(),
        "conditional_required": [],
    }


def create_task_intake_session(
    *,
    intake_id: str,
    text: str | None,
    structured_fields: dict[str, Any] | None,
    source: str,
) -> TaskIntakeSession:
    """从自然语言和结构化字段创建 Task Intake 会话。"""

    raw_input: dict[str, Any] = {
        "text": text or "",
        "source": source,
        "structured_fields": dict(structured_fields or {}),
    }
    draft = TaskSpecDraft()

    if text:
        _merge_extracted_text(draft, text)
    _merge_structured_fields(
        draft,
        structured_fields or {},
        source=TaskDraftFieldSource.USER_EXPLICIT,
        confirmed=True,
        actor=source,
    )

    session = TaskIntakeSession(
        intake_id=intake_id,
        status=TaskIntakeStatus.COLLECTING,
        raw_input=raw_input,
        draft=draft,
    )
    return refresh_task_intake_session(session)


def patch_task_intake_session(
    session: TaskIntakeSession,
    *,
    fields: dict[str, Any],
    updated_by: str,
) -> TaskIntakeSession:
    """应用用户字段修改并重新计算确认状态。"""

    _merge_structured_fields(
        session.draft,
        fields,
        source=TaskDraftFieldSource.USER_MODIFIED,
        confirmed=True,
        actor=updated_by,
    )
    session.updated_at = now_iso()
    return refresh_task_intake_session(session)


def refresh_task_intake_session(session: TaskIntakeSession) -> TaskIntakeSession:
    """根据 registry 校验结果刷新缺失、歧义和状态。"""

    session.warnings = []
    session.ambiguous_fields = []
    session.unmapped_text = list(session.draft.unmapped_text)

    for field_name, field in list(session.draft.fields.items()):
        field.warnings = []
        error = _validate_registry_value(field_name, field.value)
        if error is not None:
            field.warnings.append(error)
            session.warnings.append(error)
        if field.confidence < HIGH_CONFIDENCE_THRESHOLD:
            session.ambiguous_fields.append(field_name)

    required = _required_fields_for(session.draft.fields)
    session.missing_required_fields = [
        field_name
        for field_name in required
        if field_name not in session.draft.fields
        or session.draft.fields[field_name].value in (None, "")
    ]
    if session.confirmed_task_spec is not None:
        session.status = TaskIntakeStatus.CONFIRMED
    elif session.missing_required_fields:
        session.status = TaskIntakeStatus.COLLECTING
    else:
        session.status = TaskIntakeStatus.NEEDS_CONFIRMATION
    session.updated_at = now_iso()
    return session


def confirm_task_intake_session(
    session: TaskIntakeSession,
    *,
    confirmed_by: str,
    acknowledged_warnings: list[str],
) -> ConfirmedTaskSpec:
    """确认草稿并生成 ConfirmedTaskSpec。"""

    refresh_task_intake_session(session)
    if session.missing_required_fields:
        missing = ", ".join(session.missing_required_fields)
        raise ValueError(f"missing required fields: {missing}")
    if session.ambiguous_fields:
        ambiguous = ", ".join(session.ambiguous_fields)
        raise ValueError(f"ambiguous fields require confirmation: {ambiguous}")
    if session.warnings:
        warnings = ", ".join(session.warnings)
        raise ValueError(f"field validation warnings must be resolved: {warnings}")

    for field in session.draft.fields.values():
        field.confirmed = True
        field.last_modified_by = confirmed_by

    confirmed_spec = _build_confirmed_spec(
        session,
        confirmed_by=confirmed_by,
        acknowledged_warnings=acknowledged_warnings,
    )
    session.confirmed_task_spec = confirmed_spec
    session.status = TaskIntakeStatus.CONFIRMED
    session.updated_at = now_iso()
    return confirmed_spec


def project_confirmed_task_spec(
    spec: ConfirmedTaskSpec,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """将 ConfirmedTaskSpec 投影为现有 ProteinDesignTask 字段。"""

    constraints = dict(spec.constraints)
    if spec.objective:
        constraints.setdefault("objective", dict(spec.objective))
    if spec.inputs:
        constraints.setdefault("inputs", dict(spec.inputs))
    metadata = dict(spec.metadata)
    metadata["confirmed_task_spec"] = spec.model_dump(mode="json")
    return spec.goal, constraints, metadata


def _registry_fields() -> dict[str, dict[str, Any]]:
    return {
        "task_kind": {
            "group": "objective",
            "type": "enum",
            "ui_control": "select",
            "nl_aliases": ["任务类型", "design mode", "task kind"],
            "validators": {},
            "options": [
                "de_novo_design",
                "sequence_evaluation",
                "template_constrained_design",
                "stability_optimization",
                "motif_scaffold_design",
                "binding_design",
                "enzyme_like_design",
            ],
            "default": "de_novo_design",
            "maps_to": "constraints.task_kind",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "objective_type": {
            "group": "objective",
            "type": "enum",
            "ui_control": "select",
            "nl_aliases": ["目标", "objective", "optimization target"],
            "validators": {},
            "options": ["stability", "structure", "binding", "activity"],
            "default": None,
            "maps_to": "objective.objective_type",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "length_range": {
            "group": "design_constraints",
            "type": "integer_range",
            "ui_control": "range",
            "nl_aliases": ["长度", "aa", "amino acids"],
            "validators": {"min": 1, "max": 5000},
            "options": [],
            "default": None,
            "maps_to": "constraints.length_range",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "sequence": {
            "group": "inputs",
            "type": "protein_sequence",
            "ui_control": "textarea",
            "nl_aliases": ["序列", "sequence"],
            "validators": {"alphabet": "ACDEFGHIKLMNPQRSTVWY"},
            "options": [],
            "default": None,
            "maps_to": "inputs.sequence",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "design_count": {
            "group": "execution_preferences",
            "type": "integer",
            "ui_control": "number",
            "nl_aliases": ["候选数", "design count"],
            "validators": {"min": 1, "max": 100},
            "options": [],
            "default": 4,
            "maps_to": "constraints.design_count",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "safety_level": {
            "group": "safety_constraints",
            "type": "enum",
            "ui_control": "select",
            "nl_aliases": ["安全等级", "safety"],
            "validators": {},
            "options": ["S0", "S1", "S2"],
            "default": "S1",
            "maps_to": "constraints.safety_level",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "run_profile": {
            "group": "execution_preferences",
            "type": "enum",
            "ui_control": "segmented",
            "nl_aliases": ["运行模式", "profile", "speed"],
            "validators": {},
            "options": ["fast_smoke", "balanced", "thorough"],
            "default": "balanced",
            "maps_to": "constraints.run_profile",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "require_plan_confirm": {
            "group": "planner_policy",
            "type": "boolean",
            "ui_control": "checkbox",
            "nl_aliases": ["确认计划", "plan confirmation"],
            "validators": {},
            "options": [],
            "default": True,
            "maps_to": "constraints.require_plan_confirm",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "tools_allowed": {
            "group": "execution_preferences",
            "type": "tool_id_list",
            "ui_control": "multi_select",
            "nl_aliases": ["允许工具", "allowed tools"],
            "validators": {"source": "ToolKG"},
            "options": [],
            "default": [],
            "maps_to": "constraints.tools_allowed",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "tools_excluded": {
            "group": "execution_preferences",
            "type": "tool_id_list",
            "ui_control": "multi_select",
            "nl_aliases": ["排除工具", "excluded tools"],
            "validators": {"source": "ToolKG"},
            "options": [],
            "default": [],
            "maps_to": "constraints.tools_excluded",
            "support_level": "P0",
            "audit_visibility": "public",
        },
    }


def _task_profiles() -> dict[str, dict[str, Any]]:
    return {
        "de_novo_design": {
            "support_level": "P0",
            "required": ["task_kind", "objective_type", "length_range"],
            "optional": [
                "design_count",
                "safety_level",
                "run_profile",
                "require_plan_confirm",
                "tools_allowed",
                "tools_excluded",
            ],
            "conditional_required": [],
            "capability_hints": ["sequence_generation", "structure_prediction"],
        },
        "sequence_evaluation": {
            "support_level": "P0",
            "required": ["task_kind", "sequence", "objective_type"],
            "optional": ["safety_level", "run_profile"],
            "conditional_required": [],
            "capability_hints": ["sequence_evaluation", "objective_scoring"],
        },
        "template_constrained_design": {
            "support_level": "P0",
            "required": ["task_kind", "objective_type", "length_range"],
            "optional": ["design_count", "safety_level", "run_profile"],
            "conditional_required": [],
            "capability_hints": ["structure_prediction", "sequence_design"],
        },
        "stability_optimization": {
            "support_level": "P1",
            "required": ["task_kind", "sequence"],
            "optional": ["objective_type", "run_profile"],
            "conditional_required": [],
            "capability_hints": ["objective_scoring"],
        },
        "motif_scaffold_design": {
            "support_level": "P1",
            "required": ["task_kind"],
            "optional": ["objective_type", "length_range"],
            "conditional_required": [],
            "capability_hints": ["motif_scaffolding"],
        },
        "binding_design": {
            "support_level": "P2",
            "required": ["task_kind", "objective_type"],
            "optional": ["length_range", "run_profile"],
            "conditional_required": [],
            "capability_hints": ["binding_design"],
        },
        "enzyme_like_design": {
            "support_level": "P2",
            "required": ["task_kind", "objective_type"],
            "optional": ["length_range", "run_profile"],
            "conditional_required": [],
            "capability_hints": ["enzyme_design"],
        },
    }


def _merge_extracted_text(draft: TaskSpecDraft, text: str) -> None:
    extracted: dict[str, TaskDraftField] = {}
    lowered = text.lower()
    if "de novo" in lowered or "de-novo" in lowered or "从头" in text:
        extracted["task_kind"] = TaskDraftField(
            value="de_novo_design",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.86,
            source_span="de novo",
        )
    elif "评估" in text or "evaluate" in lowered:
        extracted["task_kind"] = TaskDraftField(
            value="sequence_evaluation",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.84,
        )
    elif "template" in lowered or "模板" in text:
        extracted["task_kind"] = TaskDraftField(
            value="template_constrained_design",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.84,
        )

    if "稳定" in text or "stability" in lowered or "stable" in lowered:
        extracted["objective_type"] = TaskDraftField(
            value="stability",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.88,
            source_span="稳定",
        )
    elif "binding" in lowered or "结合" in text:
        extracted["objective_type"] = TaskDraftField(
            value="binding",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.72,
            source_span="binding",
        )

    range_match = re.search(r"(\d{2,4})\s*(?:-|~|到|至)\s*(\d{2,4})", text)
    if range_match:
        extracted["length_range"] = TaskDraftField(
            value=[int(range_match.group(1)), int(range_match.group(2))],
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.92,
            source_span=range_match.group(0),
        )
    else:
        approx_match = re.search(
            r"(?:约|大约|around|about)?\s*(\d{2,4})\s*(?:aa|氨基酸)",
            text,
            re.IGNORECASE,
        )
        if approx_match:
            center = int(approx_match.group(1))
            extracted["length_range"] = TaskDraftField(
                value=[max(1, center - 20), center + 20],
                source=TaskDraftFieldSource.LLM_EXTRACT,
                confidence=0.91,
                source_span=approx_match.group(0),
            )

    count_match = re.search(
        r"(\d{1,2})\s*(?:个)?(?:候选|candidate)",
        text,
        re.IGNORECASE,
    )
    if count_match:
        extracted["design_count"] = TaskDraftField(
            value=int(count_match.group(1)),
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.84,
            source_span=count_match.group(0),
        )

    if "快" in text or "fast" in lowered:
        extracted["run_profile"] = TaskDraftField(
            value="fast_smoke",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.82,
        )
    elif "balanced" in lowered or "均衡" in text:
        extracted["run_profile"] = TaskDraftField(
            value="balanced",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.86,
        )
    elif "thorough" in lowered or "全面" in text:
        extracted["run_profile"] = TaskDraftField(
            value="thorough",
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.86,
        )

    if "确认计划" in text or "confirm plan" in lowered:
        extracted["require_plan_confirm"] = TaskDraftField(
            value=True,
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=0.95,
            source_span="确认计划",
        )

    for field_name, field in extracted.items():
        if field.confidence < LOW_CONFIDENCE_THRESHOLD:
            draft.unmapped_text.append(str(field.source_span or field.value))
            continue
        draft.fields[field_name] = field

    if not extracted and text.strip():
        draft.unmapped_text.append(text.strip())


def _merge_structured_fields(
    draft: TaskSpecDraft,
    fields: dict[str, Any],
    *,
    source: TaskDraftFieldSource,
    confirmed: bool,
    actor: str,
) -> None:
    for field_name, raw_value in fields.items():
        value, confidence, source_span = _unwrap_field_value(raw_value)
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            draft.unmapped_text.append(f"{field_name}={value}")
            draft.fields.pop(field_name, None)
            continue
        draft.fields[field_name] = TaskDraftField(
            value=value,
            source=source,
            confidence=confidence,
            source_span=source_span,
            confirmed=confirmed and confidence >= HIGH_CONFIDENCE_THRESHOLD,
            last_modified_by=actor,
        )


def _unwrap_field_value(raw_value: Any) -> tuple[Any, float, str | None]:
    if isinstance(raw_value, dict) and "value" in raw_value:
        confidence = raw_value.get("confidence", 1.0)
        if not isinstance(confidence, (int, float)):
            confidence = 1.0
        source_span = raw_value.get("source_span")
        normalized_span = source_span if isinstance(source_span, str) else None
        return raw_value["value"], float(confidence), normalized_span
    return raw_value, 1.0, None


def _required_fields_for(fields: dict[str, TaskDraftField]) -> list[str]:
    task_kind = fields.get("task_kind")
    task_kind_value = task_kind.value if task_kind is not None else "de_novo_design"
    profiles = _task_profiles()
    profile = profiles.get(str(task_kind_value), profiles["de_novo_design"])
    return list(profile["required"])


def _validate_registry_value(field_name: str, value: Any) -> str | None:
    registry = _registry_fields()
    field = registry.get(field_name)
    if field is None:
        return f"unknown intake field: {field_name}"

    field_type = field["type"]
    if field_type == "enum" and value not in set(field["options"]):
        return f"{field_name} must be one of {field['options']}"
    if field_type == "boolean" and not isinstance(value, bool):
        return f"{field_name} must be a boolean"
    if field_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{field_name} must be an integer"
        validators = field.get("validators", {})
        if value < validators.get("min", value) or value > validators.get("max", value):
            return f"{field_name} is outside allowed range"
    if field_type == "integer_range":
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(
                isinstance(item, int) and not isinstance(item, bool)
                for item in value
            )
            or value[0] > value[1]
        ):
            return f"{field_name} must be [min, max] integers"
    if field_type == "protein_sequence":
        if not isinstance(value, str) or not value.strip():
            return f"{field_name} must be a non-empty sequence"
        alphabet = set(field["validators"]["alphabet"])
        invalid = set(value.upper()) - alphabet
        if invalid:
            return f"{field_name} contains invalid residues: {''.join(sorted(invalid))}"
    if field_type == "tool_id_list":
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            return f"{field_name} must be a list of tool ids"
    return None


def _build_confirmed_spec(
    session: TaskIntakeSession,
    *,
    confirmed_by: str,
    acknowledged_warnings: list[str],
) -> ConfirmedTaskSpec:
    fields = {name: field.value for name, field in session.draft.fields.items()}
    objective: dict[str, Any] = {}
    inputs: dict[str, Any] = {}
    constraints: dict[str, Any] = {}
    registry = _registry_fields()

    for field_name, value in fields.items():
        maps_to = registry[field_name]["maps_to"]
        if maps_to.startswith("objective."):
            objective[maps_to.split(".", 1)[1]] = value
        elif maps_to.startswith("inputs."):
            inputs[maps_to.split(".", 1)[1]] = value
        elif maps_to.startswith("constraints."):
            constraints[maps_to.split(".", 1)[1]] = value

    goal = _build_goal(fields)
    metadata = {
        "intake_id": session.intake_id,
        "field_registry_version": TASK_FIELD_REGISTRY_VERSION,
        "support_level": _support_level_for(fields),
        "confirmed_by": confirmed_by,
        "input_mode": _input_mode(session),
        "acknowledged_warnings": list(acknowledged_warnings),
        "raw_query": session.raw_input.get("text") or "",
        "unmapped_text": list(session.unmapped_text),
        "intake_summary": {
            "field_count": len(session.draft.fields),
            "ambiguous_fields": list(session.ambiguous_fields),
            "missing_required_fields": list(session.missing_required_fields),
        },
    }
    if "intent_draft_id" in session.raw_input:
        metadata["intent_draft_id"] = session.raw_input["intent_draft_id"]

    return ConfirmedTaskSpec(
        goal=goal,
        objective=objective,
        inputs=inputs,
        constraints=constraints,
        initial_artifacts=[],
        metadata=metadata,
    )


def _build_goal(fields: dict[str, Any]) -> str:
    task_kind = fields.get("task_kind", "de_novo_design")
    objective = fields.get("objective_type", "protein design")
    length_range = fields.get("length_range")
    if isinstance(length_range, list) and len(length_range) == 2:
        return (
            f"{task_kind} for {objective} "
            f"with length {length_range[0]}-{length_range[1]} aa"
        )
    return f"{task_kind} for {objective}"


def _support_level_for(fields: dict[str, Any]) -> str:
    task_kind = fields.get("task_kind", "de_novo_design")
    profile = _task_profiles().get(
        str(task_kind),
        _task_profiles()["de_novo_design"],
    )
    return str(profile["support_level"])


def _input_mode(session: TaskIntakeSession) -> str:
    has_text = bool(session.raw_input.get("text"))
    has_structured = bool(session.raw_input.get("structured_fields"))
    if has_text and has_structured:
        return "mixed_with_confirmation"
    if has_text:
        return "natural_language_with_confirmation"
    return "structured_with_confirmation"
