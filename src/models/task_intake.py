from __future__ import annotations

from copy import deepcopy
import re
from enum import Enum
from typing import Literal, NotRequired, TypedDict, cast

from pydantic import BaseModel, Field, field_validator

from src.kg.kg_client import ToolKGError, get_tool_nodes
from src.models.contracts import now_iso


TASK_FIELD_REGISTRY_VERSION = "task-intake.v1"
HIGH_CONFIDENCE_THRESHOLD = 0.80
LOW_CONFIDENCE_THRESHOLD = 0.50
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
type IntakeActorType = Literal["api", "web", "cli", "script", "legacy", "system"]
type IntakeSourceType = Literal["web", "cli", "api", "script", "legacy"]
type ExtractionMode = Literal["none", "rule_extract", "llm_extract", "manual_fallback"]


class RegistryField(TypedDict):
    group: str
    type: str
    ui_control: str
    nl_aliases: list[str]
    validators: JsonObject
    options: list[str]
    default: JsonValue
    maps_to: str
    support_level: str
    audit_visibility: str
    tool_options: NotRequired[list[JsonObject]]


class TaskProfile(TypedDict):
    support_level: str
    required: list[str]
    optional: list[str]
    conditional_required: list[JsonObject]
    capability_hints: list[str]


class ToolOption(TypedDict, total=False):
    tool_id: str
    label: JsonValue
    capabilities: list[str]
    support_level: JsonValue
    execution: JsonValue


class TaskFieldRegistry(TypedDict):
    version: str
    groups: list[str]
    fields: dict[str, RegistryField]
    task_profiles: dict[str, TaskProfile]


_HIGH_RISK_FUNCTION_KEYWORDS: tuple[str, ...] = (
    "toxin",
    "virulence",
    "pathogenicity",
    "immune evasion",
    "host range",
    "gain of function",
)
TaskIntakeAuditEventName = Literal[
    "INTAKE_CREATED",
    "INTAKE_PARSED",
    "INTAKE_FIELD_UPDATED",
    "INTAKE_SAFETY_CHECKED",
    "INTAKE_CONFIRMED",
    "INTAKE_CANCELLED",
]
TASK_FIELD_GROUPS: tuple[str, ...] = (
    "objective",
    "inputs",
    "design_constraints",
    "quality_constraints",
    "structure_constraints",
    "function_constraints",
    "safety_constraints",
    "execution_preferences",
    "planner_policy",
)
TASK_FIELD_REGISTRY: TaskFieldRegistry = {
    "version": TASK_FIELD_REGISTRY_VERSION,
    "groups": list(TASK_FIELD_GROUPS),
    "fields": {
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
        "goal_summary": {
            "group": "objective",
            "type": "string",
            "ui_control": "textarea",
            "nl_aliases": ["目标摘要", "goal summary", "confirmed goal"],
            "validators": {"min_length": 1, "max_length": 2000},
            "options": [],
            "default": None,
            "maps_to": "objective.description",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "objective_description": {
            "group": "objective",
            "type": "string",
            "ui_control": "textarea",
            "nl_aliases": ["目标描述", "goal", "description"],
            "validators": {"min_length": 1, "max_length": 2000},
            "options": [],
            "default": None,
            "maps_to": "objective.description",
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
        "template_pdb": {
            "group": "inputs",
            "type": "string",
            "ui_control": "file_or_text",
            "nl_aliases": ["模板结构", "template pdb", "template structure"],
            "validators": {"min_length": 1, "max_length": 4096},
            "options": [],
            "default": None,
            "maps_to": "inputs.template_pdb",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "initial_artifacts": {
            "group": "inputs",
            "type": "artifact_ref_list",
            "ui_control": "artifact_picker",
            "nl_aliases": ["初始产物", "artifacts", "artifact refs"],
            "validators": {"ref_schemes": ["artifact", "task", "relative_path"]},
            "options": [],
            "default": [],
            "maps_to": "initial_artifacts",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "target_ligand": {
            "group": "inputs",
            "type": "string",
            "ui_control": "text",
            "nl_aliases": ["配体", "ligand", "small molecule"],
            "validators": {"min_length": 1, "max_length": 512},
            "options": [],
            "default": None,
            "maps_to": "inputs.target_ligand",
            "support_level": "P2",
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
        "design_count": {
            "group": "design_constraints",
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
        "quality_metric": {
            "group": "quality_constraints",
            "type": "enum",
            "ui_control": "select",
            "nl_aliases": ["质量指标", "quality metric"],
            "validators": {},
            "options": ["plddt", "ptm", "sequence_similarity", "custom_score"],
            "default": "plddt",
            "maps_to": "constraints.quality_metric",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "min_quality_score": {
            "group": "quality_constraints",
            "type": "number",
            "ui_control": "number",
            "nl_aliases": ["最低质量", "min quality", "score threshold"],
            "validators": {"min": 0.0, "max": 1.0},
            "options": [],
            "default": None,
            "maps_to": "constraints.min_quality_score",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "target_fold": {
            "group": "structure_constraints",
            "type": "string",
            "ui_control": "text",
            "nl_aliases": ["目标折叠", "fold", "topology"],
            "validators": {"min_length": 1, "max_length": 512},
            "options": [],
            "default": None,
            "maps_to": "constraints.target_fold",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "secondary_structure_bias": {
            "group": "structure_constraints",
            "type": "enum",
            "ui_control": "select",
            "nl_aliases": ["二级结构偏好", "secondary structure"],
            "validators": {},
            "options": ["alpha", "beta", "mixed", "none"],
            "default": "none",
            "maps_to": "constraints.secondary_structure_bias",
            "support_level": "P1",
            "audit_visibility": "public",
        },
        "motif_pattern": {
            "group": "function_constraints",
            "type": "string",
            "ui_control": "text",
            "nl_aliases": ["motif", "基序", "functional motif"],
            "validators": {"min_length": 1, "max_length": 512},
            "options": [],
            "default": None,
            "maps_to": "constraints.motif_pattern",
            "support_level": "P1",
            "audit_visibility": "public",
        },
        "binding_partner": {
            "group": "function_constraints",
            "type": "string",
            "ui_control": "text",
            "nl_aliases": ["结合对象", "binding partner", "target protein"],
            "validators": {"min_length": 1, "max_length": 512},
            "options": [],
            "default": None,
            "maps_to": "constraints.binding_partner",
            "support_level": "P2",
            "audit_visibility": "public",
        },
        "active_site_residues": {
            "group": "function_constraints",
            "type": "residue_list",
            "ui_control": "tag_input",
            "nl_aliases": ["活性位点", "active site residues"],
            "validators": {"pattern": "^[A-Z][0-9]+$"},
            "options": [],
            "default": [],
            "maps_to": "constraints.active_site_residues",
            "support_level": "P2",
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
        "forbidden_motifs": {
            "group": "safety_constraints",
            "type": "string_list",
            "ui_control": "tag_input",
            "nl_aliases": ["禁用片段", "forbidden motifs"],
            "validators": {"min_item_length": 1, "max_item_length": 128},
            "options": [],
            "default": [],
            "maps_to": "constraints.forbidden_motifs",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "forbidden_functions": {
            "group": "safety_constraints",
            "type": "string_list",
            "ui_control": "tag_input",
            "nl_aliases": ["禁用功能", "forbidden functions"],
            "validators": {"min_item_length": 1, "max_item_length": 256},
            "options": [],
            "default": [],
            "maps_to": "constraints.forbidden_functions",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "organism": {
            "group": "safety_constraints",
            "type": "string",
            "ui_control": "text",
            "nl_aliases": ["物种", "organism", "host organism"],
            "validators": {"min_length": 1, "max_length": 512},
            "options": [],
            "default": None,
            "maps_to": "constraints.organism",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "run_profile": {
            "group": "execution_preferences",
            "type": "enum",
            "ui_control": "segmented",
            "nl_aliases": ["运行模式", "profile", "speed"],
            "validators": {},
            "options": ["fast_smoke", "balanced", "high_accuracy"],
            "default": "balanced",
            "maps_to": "constraints.run_profile",
            "support_level": "P0",
            "audit_visibility": "public",
        },
        "max_runtime_min": {
            "group": "execution_preferences",
            "type": "integer",
            "ui_control": "number",
            "nl_aliases": ["最长运行时间", "max runtime", "time budget"],
            "validators": {"min": 1, "max": 10080},
            "options": [],
            "default": 60,
            "maps_to": "constraints.max_runtime_min",
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
        "allow_replan": {
            "group": "planner_policy",
            "type": "boolean",
            "ui_control": "checkbox",
            "nl_aliases": ["允许重规划", "allow replan"],
            "validators": {},
            "options": [],
            "default": True,
            "maps_to": "constraints.allow_replan",
            "support_level": "P0",
            "audit_visibility": "public",
        },
    },
    "task_profiles": {
        "de_novo_design": {
            "support_level": "P0",
            "required": ["task_kind", "objective_type", "length_range"],
            "optional": [
                "objective_description",
                "goal_summary",
                "design_count",
                "quality_metric",
                "min_quality_score",
                "target_fold",
                "initial_artifacts",
                "forbidden_motifs",
                "forbidden_functions",
                "organism",
                "safety_level",
                "run_profile",
                "max_runtime_min",
                "require_plan_confirm",
                "allow_replan",
                "tools_allowed",
                "tools_excluded",
            ],
            "conditional_required": [],
            "capability_hints": ["sequence_generation", "structure_prediction"],
        },
        "sequence_evaluation": {
            "support_level": "P0",
            "required": ["task_kind", "sequence", "objective_type"],
            "optional": [
                "quality_metric",
                "min_quality_score",
                "initial_artifacts",
                "safety_level",
                "run_profile",
                "tools_allowed",
                "tools_excluded",
            ],
            "conditional_required": [],
            "capability_hints": [
                "sequence_evaluation",
                "objective_scoring",
                "quality_qc",
            ],
        },
        "template_constrained_design": {
            "support_level": "P0",
            "required": ["task_kind", "objective_type", "length_range", "template_pdb"],
            "optional": [
                "design_count",
                "quality_metric",
                "min_quality_score",
                "target_fold",
                "initial_artifacts",
                "safety_level",
                "run_profile",
                "tools_allowed",
                "tools_excluded",
            ],
            "conditional_required": [],
            "capability_hints": ["sequence_design", "structure_prediction"],
        },
        "stability_optimization": {
            "support_level": "P1",
            "required": ["task_kind", "sequence"],
            "optional": [
                "objective_type",
                "quality_metric",
                "min_quality_score",
                "secondary_structure_bias",
                "run_profile",
            ],
            "conditional_required": [],
            "capability_hints": ["objective_scoring", "stability_simulation"],
        },
        "motif_scaffold_design": {
            "support_level": "P1",
            "required": ["task_kind", "motif_pattern"],
            "optional": [
                "objective_type",
                "length_range",
                "template_pdb",
                "secondary_structure_bias",
            ],
            "conditional_required": [],
            "capability_hints": ["motif_scaffolding", "backbone_generation"],
        },
        "binding_design": {
            "support_level": "P2",
            "required": ["task_kind", "objective_type"],
            "optional": ["length_range", "target_ligand", "run_profile"],
            "conditional_required": [
                {
                    "if": {"field": "objective_type", "equals": "binding"},
                    "required": ["binding_partner"],
                    "reason": "binding objective needs an explicit target partner",
                }
            ],
            "capability_hints": ["binding_design", "docking_scoring"],
        },
        "enzyme_like_design": {
            "support_level": "P2",
            "required": ["task_kind", "objective_type"],
            "optional": ["length_range", "motif_pattern", "active_site_residues"],
            "conditional_required": [
                {
                    "if": {"field": "objective_type", "equals": "activity"},
                    "required": ["active_site_residues"],
                    "reason": "enzyme-like activity needs active-site anchors",
                }
            ],
            "capability_hints": ["enzyme_design", "function_annotation"],
        },
    },
}


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

    value: JsonValue
    source: TaskDraftFieldSource
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_span: str | None = None
    confirmed: bool = False
    warnings: list[str] = Field(default_factory=list)
    last_modified_by: str | None = None


class TaskIntakeSafetyRisk(BaseModel):
    """Intake 输入预检查发现的单条风险。"""

    level: Literal["ok", "warn", "block"]
    code: str
    message: str
    scope: Literal["input"] = "input"
    details: JsonObject = Field(default_factory=dict)


class TaskIntakeSafetyCheck(BaseModel):
    """正式 Task 创建前的 Safety 输入预检查结果。"""

    action: Literal["ok", "warn", "block"] = "ok"
    risk_flags: list[TaskIntakeSafetyRisk] = Field(default_factory=list)
    checked_at: str = Field(default_factory=now_iso)
    input_summary: JsonObject = Field(default_factory=dict)


class TaskIntakeAuditEvent(BaseModel):
    """Task Intake 级审计事件，不替代正式 Task EventLog。"""

    event_type: TaskIntakeAuditEventName
    intake_id: str
    timestamp: str = Field(default_factory=now_iso)
    actor_type: IntakeActorType = "system"
    actor_id: str | None = None
    data: JsonObject = Field(default_factory=dict)


class TaskSpecDraft(BaseModel):
    """可编辑、可解释的任务草稿。"""

    fields: dict[str, TaskDraftField] = Field(default_factory=dict)
    unmapped_text: list[str] = Field(default_factory=list)
    extraction_mode: Literal[
        "none",
        "rule_extract",
        "llm_extract",
        "manual_fallback",
    ] = "none"
    extraction_errors: list[str] = Field(default_factory=list)


class ConfirmedTaskSpec(BaseModel):
    """唯一允许进入正式 Task 创建的结构化输入。"""

    goal: str
    objective: JsonObject = Field(default_factory=dict)
    inputs: JsonObject = Field(default_factory=dict)
    constraints: JsonObject = Field(default_factory=dict)
    initial_artifacts: list[JsonObject] = Field(default_factory=list)
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("goal")
    @classmethod
    def _validate_goal(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("goal must not be empty")
        return normalized

    @field_validator("initial_artifacts")
    @classmethod
    def _validate_initial_artifacts(
        cls,
        value: list[JsonObject],
    ) -> list[JsonObject]:
        error = _validate_artifact_ref_list("initial_artifacts", value)
        if error is not None:
            raise ValueError(error)
        return value


class TaskIntakeSession(BaseModel):
    """一次正式 Task 创建前的录入会话。"""

    intake_id: str
    status: TaskIntakeStatus = TaskIntakeStatus.COLLECTING
    raw_input: JsonObject = Field(default_factory=dict)
    draft: TaskSpecDraft = Field(default_factory=TaskSpecDraft)
    missing_required_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    unmapped_text: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_check: TaskIntakeSafetyCheck = Field(default_factory=TaskIntakeSafetyCheck)
    audit_events: list[TaskIntakeAuditEvent] = Field(default_factory=list)
    human_summary: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    confirmed_task_spec: ConfirmedTaskSpec | None = None


class TaskIntakeCreateRequest(BaseModel):
    """创建 Task Intake 会话的请求。"""

    text: str | None = None
    structured_fields: JsonObject = Field(default_factory=dict)
    source: IntakeSourceType = "api"


class TaskIntakePatchRequest(BaseModel):
    """更新 Task Intake 草稿字段的请求。"""

    fields: JsonObject = Field(default_factory=dict)
    updated_by: str = "user"


class TaskIntakeConfirmRequest(BaseModel):
    """确认 Task Intake 并生成 ConfirmedTaskSpec 的请求。"""

    confirmed_by: str
    acknowledged_warnings: list[str] = Field(default_factory=list)


class IntentDraftClarificationRequest(BaseModel):
    """旧 IntentDraft clarification 入口的兼容请求。"""

    text: str | None = None
    fields: JsonObject = Field(default_factory=dict)
    structured_fields: JsonObject = Field(default_factory=dict)
    updated_by: str = "user"


def build_task_intake_schema() -> JsonObject:
    """生成 Web/CLI 共享的字段注册表视图。"""

    registry = get_task_field_registry()
    fields = _registry_fields()
    tool_options = build_tool_kg_options()
    _attach_tool_options(fields, tool_options)
    registry["fields"] = cast(JsonValue, fields)
    registry["tool_options"] = cast(JsonValue, tool_options)
    registry["web_schema"] = build_task_intake_web_schema()
    registry["cli_arguments"] = cast(JsonValue, build_task_intake_cli_arguments())
    registry["cli_questions"] = cast(JsonValue, build_task_intake_cli_questions())
    registry["llm_extraction_schema"] = build_task_intake_llm_extraction_schema()
    registry["confirmed_task_spec_mapping"] = cast(
        JsonValue,
        build_confirmed_task_spec_mapping(),
    )
    registry["planner_capability_hints"] = cast(
        JsonValue,
        build_planner_capability_hints(),
    )
    registry["conditional_required"] = cast(
        JsonValue, _all_conditional_required_rules()
    )
    return registry


def get_task_field_registry() -> JsonObject:
    """返回版本化 TaskFieldRegistry 的独立副本。"""

    return cast(JsonObject, cast(object, deepcopy(TASK_FIELD_REGISTRY)))


def build_task_intake_web_schema() -> JsonObject:
    """从 registry 派生 Web 表单分组 schema。"""

    fields = _schema_fields()
    return cast(
        JsonObject,
        {
            "groups": [
                {
                    "id": group,
                    "fields": [
                        name
                        for name, definition in fields.items()
                        if definition["group"] == group
                    ],
                }
                for group in TASK_FIELD_GROUPS
            ],
            "fields": fields,
        },
    )


def build_task_intake_cli_arguments() -> list[JsonObject]:
    """从 registry 派生 CLI 字段参数说明。"""

    required_by = _field_required_profile_index()
    return cast(
        list[JsonObject],
        [
            {
                "field": name,
                "flag": f"--{name.replace('_', '-')}",
                "type": definition["type"],
                "default": definition["default"],
                "required_by_profiles": required_by.get(name, []),
                "nl_aliases": list(definition["nl_aliases"]),
            }
            for name, definition in _schema_fields().items()
        ],
    )


def build_task_intake_cli_questions() -> list[JsonObject]:
    """从 registry 派生 CLI 交互式问题说明。"""

    required_by = _field_required_profile_index()
    return cast(
        list[JsonObject],
        [
            {
                "field": name,
                "prompt": _cli_prompt_for_field(name, definition),
                "type": definition["type"],
                "ui_control": definition["ui_control"],
                "options": list(definition["options"]),
                "default": definition["default"],
                "required_by_profiles": required_by.get(name, []),
            }
            for name, definition in _schema_fields().items()
        ],
    )


def build_task_intake_llm_extraction_schema() -> JsonObject:
    """从 registry 派生自然语言字段抽取 schema。"""

    properties: JsonObject = {}
    for name, definition in _schema_fields().items():
        value_schema: JsonObject = {
            "type": cast(JsonValue, _json_schema_type_for_field(definition)),
            "description": ", ".join(definition["nl_aliases"]),
        }
        if definition["type"] == "tool_id_list":
            value_schema["items"] = {
                "type": "string",
                "enum": cast(JsonValue, list(definition["options"])),
            }
        elif definition["type"] == "artifact_ref_list":
            value_schema["items"] = {"type": "object"}
        elif definition["options"]:
            value_schema["enum"] = cast(JsonValue, list(definition["options"]))
        properties[name] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "confidence", "source"],
            "properties": {
                "value": value_schema,
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "source": {"const": TaskDraftFieldSource.LLM_EXTRACT.value},
                "source_span": {"type": "string"},
            },
        }
    return cast(
        JsonObject,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        },
    )


def build_confirmed_task_spec_mapping() -> dict[str, str]:
    """从 registry 派生 ConfirmedTaskSpec 字段映射。"""

    return {
        name: str(definition["maps_to"])
        for name, definition in _registry_fields().items()
    }


def build_planner_capability_hints() -> dict[str, list[str]]:
    """从 profile 派生 Planner capability hints。"""

    return {
        name: list(profile["capability_hints"])
        for name, profile in _task_profiles().items()
    }


def build_tool_kg_options() -> list[JsonObject]:
    """从 ProteinToolKG 派生 Web/CLI 可用的工具选项。"""

    try:
        tools = get_tool_nodes()
    except ToolKGError:
        return []

    options: list[JsonObject] = []
    for tool in tools:
        tool_id = tool.get("id") or tool.get("tool_id")
        if not isinstance(tool_id, str) or not tool_id:
            continue
        capabilities = tool.get("capabilities", [])
        execution = tool.get("execution")
        options.append(
            cast(
                JsonObject,
                {
                    "tool_id": tool_id,
                    "label": tool_id,
                    "capabilities": list(capabilities),
                    "support_level": cast(JsonValue, tool.get("priority")),
                    "execution": cast(JsonValue, execution),
                },
            )
        )
    return options


def create_task_intake_session(
    *,
    intake_id: str,
    text: str | None,
    structured_fields: JsonObject | None,
    source: str,
) -> TaskIntakeSession:
    """从自然语言和结构化字段创建 Task Intake 会话。"""

    raw_input: JsonObject = {
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
    _append_intake_audit_event(
        session,
        "INTAKE_CREATED",
        actor_type=source,
        data=cast(
            JsonObject,
            {
                "source": source,
                "raw_input_summary": _raw_input_summary(raw_input),
            },
        ),
    )
    if text or draft.fields or draft.unmapped_text or draft.extraction_errors:
        _append_intake_audit_event(
            session,
            "INTAKE_PARSED",
            actor_type="system",
            data=cast(
                JsonObject,
                {
                    "extraction_mode": draft.extraction_mode,
                    "field_names": sorted(draft.fields),
                    "unmapped_text_count": len(draft.unmapped_text),
                    "extraction_error_count": len(draft.extraction_errors),
                },
            ),
        )
    return refresh_task_intake_session(session)


def patch_task_intake_session(
    session: TaskIntakeSession,
    *,
    fields: JsonObject,
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
    _append_intake_audit_event(
        session,
        "INTAKE_FIELD_UPDATED",
        actor_type="system",
        actor_id=updated_by,
        data=cast(JsonObject, {"field_names": sorted(fields)}),
    )
    session.updated_at = now_iso()
    return refresh_task_intake_session(session)


def cancel_task_intake_session(
    session: TaskIntakeSession,
    *,
    cancelled_by: str,
    reason: str | None = None,
) -> TaskIntakeSession:
    """取消 Task Intake 会话并记录 intake 级审计事件。"""

    session.status = TaskIntakeStatus.CANCELLED
    session.updated_at = now_iso()
    _append_intake_audit_event(
        session,
        "INTAKE_CANCELLED",
        actor_type="system",
        actor_id=cancelled_by,
        data={"reason": reason or ""},
    )
    return session


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
    session.safety_check = _run_safety_input_precheck(session)
    session.warnings.extend(
        risk.message for risk in session.safety_check.risk_flags if risk.level == "warn"
    )
    _append_intake_audit_event(
        session,
        "INTAKE_SAFETY_CHECKED",
        actor_type="system",
        data={
            "action": session.safety_check.action,
            "risk_codes": [risk.code for risk in session.safety_check.risk_flags],
            "risk_count": len(session.safety_check.risk_flags),
        },
    )

    required = _required_fields_for(session.draft.fields)
    session.missing_required_fields = [
        field_name
        for field_name in required
        if field_name not in session.draft.fields
        or session.draft.fields[field_name].value in (None, "")
    ]
    if session.status == TaskIntakeStatus.CANCELLED:
        session.status = TaskIntakeStatus.CANCELLED
    elif session.confirmed_task_spec is not None:
        session.status = TaskIntakeStatus.CONFIRMED
    elif session.missing_required_fields:
        session.status = TaskIntakeStatus.COLLECTING
    else:
        session.status = TaskIntakeStatus.NEEDS_CONFIRMATION
    session.human_summary = _build_human_summary(session)
    session.updated_at = now_iso()
    return session


def confirm_task_intake_session(
    session: TaskIntakeSession,
    *,
    confirmed_by: str,
    acknowledged_warnings: list[str],
) -> ConfirmedTaskSpec:
    """确认草稿并生成 ConfirmedTaskSpec。"""

    if session.status == TaskIntakeStatus.CANCELLED:
        raise ValueError("cancelled intake cannot be confirmed")
    _ = refresh_task_intake_session(session)
    if session.missing_required_fields:
        missing = ", ".join(session.missing_required_fields)
        raise ValueError(f"missing required fields: {missing}")
    if session.ambiguous_fields:
        ambiguous = ", ".join(session.ambiguous_fields)
        raise ValueError(f"ambiguous fields require confirmation: {ambiguous}")
    field_warnings = _field_validation_warnings(session)
    if field_warnings:
        warnings = ", ".join(field_warnings)
        raise ValueError(f"field validation warnings must be resolved: {warnings}")
    if session.safety_check.action == "block":
        blocked = ", ".join(
            risk.message
            for risk in session.safety_check.risk_flags
            if risk.level == "block"
        )
        raise ValueError(f"safety input precheck blocked confirmation: {blocked}")
    missing_acknowledgements = _missing_acknowledged_warnings(
        session,
        acknowledged_warnings,
    )
    if missing_acknowledgements:
        missing = ", ".join(missing_acknowledgements)
        raise ValueError(
            "safety warnings require acknowledgement before confirm: "
            + f"{missing}; CLI: design intake confirm "
            + f"{session.intake_id} --ack-warning <warning-code>"
        )

    for field in session.draft.fields.values():
        field.confirmed = True
        field.last_modified_by = confirmed_by

    _append_intake_audit_event(
        session,
        "INTAKE_CONFIRMED",
        actor_type="system",
        actor_id=confirmed_by,
        data=cast(
            JsonObject,
            {
                "acknowledged_warnings": list(acknowledged_warnings),
                "safety_action": session.safety_check.action,
            },
        ),
    )
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
) -> tuple[str, JsonObject, JsonObject]:
    """将 ConfirmedTaskSpec 投影为现有 ProteinDesignTask 字段。"""

    constraints = dict(spec.constraints)
    if spec.objective:
        _ = constraints.setdefault("objective", dict(spec.objective))
    if spec.inputs:
        _ = constraints.setdefault("inputs", dict(spec.inputs))
    metadata = dict(spec.metadata)
    metadata["confirmed_task_spec"] = cast(JsonValue, spec.model_dump(mode="json"))
    return spec.goal, constraints, metadata


def _registry_fields() -> dict[str, RegistryField]:
    return deepcopy(TASK_FIELD_REGISTRY["fields"])


def _schema_fields() -> dict[str, RegistryField]:
    fields = _registry_fields()
    _attach_tool_options(fields, build_tool_kg_options())
    return fields


def _attach_tool_options(
    fields: dict[str, RegistryField],
    tool_options: list[JsonObject],
) -> None:
    tool_ids = [
        tool_id
        for option in tool_options
        if isinstance((tool_id := option.get("tool_id")), str)
    ]
    for field_name in ("tools_allowed", "tools_excluded"):
        if field_name in fields:
            fields[field_name]["options"] = list(tool_ids)
            fields[field_name]["tool_options"] = deepcopy(tool_options)


def _task_profiles() -> dict[str, TaskProfile]:
    return deepcopy(TASK_FIELD_REGISTRY["task_profiles"])


def _all_conditional_required_rules() -> list[JsonObject]:
    rules: list[JsonObject] = []
    for profile_name, profile in _task_profiles().items():
        for rule in profile.get("conditional_required", []):
            item = dict(rule)
            item["profile"] = profile_name
            rules.append(item)
    return rules


def _field_required_profile_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for profile_name, profile in _task_profiles().items():
        for field_name in profile["required"]:
            index.setdefault(field_name, []).append(profile_name)
        for rule in profile.get("conditional_required", []):
            required = rule.get("required", [])
            if not isinstance(required, list):
                continue
            for field_name in required:
                if not isinstance(field_name, str):
                    continue
                index.setdefault(field_name, []).append(profile_name)
    return index


def _json_schema_type_for_field(definition: RegistryField) -> str | list[str]:
    field_type = definition["type"]
    if field_type in {"integer", "integer_range"}:
        return "integer" if field_type == "integer" else "array"
    if field_type == "number":
        return "number"
    if field_type == "boolean":
        return "boolean"
    if field_type in {
        "string_list",
        "residue_list",
        "tool_id_list",
        "artifact_ref_list",
    }:
        return "array"
    return "string"


def _cli_prompt_for_field(field_name: str, definition: RegistryField) -> str:
    alias = definition["nl_aliases"][0] if definition["nl_aliases"] else field_name
    return f"{alias} ({field_name})"


def extract_task_intake_fields(
    text: str,
    *,
    raw_candidates: list[JsonObject] | None = None,
    max_attempts: int = 2,
) -> TaskSpecDraft:
    """从自然语言抽取 TaskSpecDraft，并在 schema 失败时降级手动表单。

    自然语言抽取属于 Task Intake 前置层，只返回可审计草稿字段；Planner
    只能在用户确认后消费 ConfirmedTaskSpec。
    """

    normalized_text = text.strip()
    draft = TaskSpecDraft()
    if not normalized_text:
        return draft

    candidates = raw_candidates or [_build_rule_extraction_payload(normalized_text)]
    errors: list[str] = []
    for candidate in candidates[: max(1, max_attempts)]:
        verified = _verify_extraction_payload(candidate, raw_text=normalized_text)
        if not verified.extraction_errors:
            return verified
        errors.extend(verified.extraction_errors)

    draft.unmapped_text.append(normalized_text)
    draft.extraction_mode = "manual_fallback"
    draft.extraction_errors = list(dict.fromkeys(errors)) or [
        "natural language extraction returned no valid schema candidate"
    ]
    return draft


def _merge_extracted_text(draft: TaskSpecDraft, text: str) -> None:
    extracted_draft = extract_task_intake_fields(text)
    draft.fields.update(extracted_draft.fields)
    draft.unmapped_text.extend(extracted_draft.unmapped_text)
    draft.extraction_mode = extracted_draft.extraction_mode
    draft.extraction_errors.extend(extracted_draft.extraction_errors)


def _build_rule_extraction_payload(text: str) -> JsonObject:
    fields: JsonObject = {}
    source_spans: list[str] = []

    def add_field(
        field_name: str,
        value: JsonValue,
        confidence: float,
        source_span: str | None = None,
    ) -> None:
        fields[field_name] = {
            "value": value,
            "source": TaskDraftFieldSource.LLM_EXTRACT.value,
            "confidence": confidence,
            "source_span": source_span,
        }
        if source_span:
            source_spans.append(source_span)

    lowered = text.lower()
    design_intent = any(
        marker in lowered
        for marker in ("design", "de novo", "de-novo", "generate", "protein")
    ) or any(marker in text for marker in ("设计", "生成", "蛋白", "从头"))
    if "de novo" in lowered or "de-novo" in lowered or "从头" in text:
        add_field("task_kind", "de_novo_design", 0.86, "de novo")
    elif "评估" in text or "evaluate" in lowered:
        add_field(
            "task_kind",
            "sequence_evaluation",
            0.84,
            _first_present_span(text, ["评估", "evaluate"]),
        )
    elif "template" in lowered or "模板" in text:
        add_field(
            "task_kind",
            "template_constrained_design",
            0.84,
            _first_present_span(text, ["模板", "template"]),
        )
    elif design_intent:
        add_field(
            "task_kind",
            "de_novo_design",
            0.80,
            _first_present_span(text, ["设计", "design", "生成", "protein"]),
        )

    if "稳定" in text or "stability" in lowered or "stable" in lowered:
        add_field(
            "objective_type",
            "stability",
            0.88,
            _first_present_span(text, ["稳定", "stability", "stable"]),
        )
    elif "binding" in lowered or "结合" in text:
        add_field(
            "objective_type",
            "binding",
            0.72,
            _first_present_span(text, ["binding", "结合"]),
        )
    elif "结构" in text or "structure" in lowered:
        add_field(
            "objective_type",
            "structure",
            0.78,
            _first_present_span(text, ["结构", "structure"]),
        )
    elif "活性" in text or "activity" in lowered:
        add_field(
            "objective_type",
            "activity",
            0.76,
            _first_present_span(text, ["活性", "activity"]),
        )

    range_match = re.search(r"(\d{2,4})\s*(?:-|~|到|至)\s*(\d{2,4})", text)
    if range_match:
        add_field(
            "length_range",
            [int(range_match.group(1)), int(range_match.group(2))],
            0.92,
            range_match.group(0),
        )
    else:
        approx_match = re.search(
            r"(?:约|大约|around|about)?\s*(\d{2,4})\s*(?:个)?\s*(?:aa|氨基酸)",
            text,
            re.IGNORECASE,
        )
        if approx_match:
            center = int(approx_match.group(1))
            add_field(
                "length_range",
                [max(1, center - 20), center + 20],
                0.91,
                approx_match.group(0),
            )

    count_match = re.search(
        r"(\d{1,2})\s*(?:个)?(?:候选|candidate)",
        text,
        re.IGNORECASE,
    )
    if count_match:
        add_field(
            "design_count",
            int(count_match.group(1)),
            0.84,
            count_match.group(0),
        )

    if "快" in text or "fast" in lowered:
        add_field(
            "run_profile",
            "fast_smoke",
            0.82,
            _first_present_span(text, ["快", "fast"]),
        )
    elif "balanced" in lowered or "均衡" in text:
        add_field(
            "run_profile",
            "balanced",
            0.86,
            _first_present_span(text, ["均衡", "balanced"]),
        )
    elif (
        "high accuracy" in lowered
        or "high-accuracy" in lowered
        or "thorough" in lowered
        or "高精度" in text
        or "全面" in text
    ):
        add_field(
            "run_profile",
            "high_accuracy",
            0.86,
            _first_present_span(text, ["高精度", "全面", "high accuracy", "thorough"]),
        )

    safety_match = re.search(r"\bS[0-2]\b", text, re.IGNORECASE)
    if safety_match:
        add_field(
            "safety_level",
            safety_match.group(0).upper(),
            0.9,
            safety_match.group(0),
        )
    elif "低风险" in text or "low risk" in lowered:
        add_field(
            "safety_level",
            "S1",
            0.70,
            _first_present_span(text, ["低风险", "low risk"]),
        )
    elif "安全" in text or "safe" in lowered:
        add_field(
            "safety_level", "S1", 0.68, _first_present_span(text, ["安全", "safe"])
        )

    if "无需确认计划" in text or "no plan confirmation" in lowered:
        add_field(
            "require_plan_confirm",
            False,
            0.92,
            _first_present_span(text, ["无需确认计划", "no plan confirmation"]),
        )
    elif "确认计划" in text or "confirm plan" in lowered:
        add_field(
            "require_plan_confirm",
            True,
            0.95,
            _first_present_span(text, ["确认计划", "confirm plan"]),
        )

    tool_preferences = _extract_tool_preferences(text)
    if tool_preferences:
        add_field(
            "tools_allowed",
            cast(JsonValue, tool_preferences),
            0.76,
            ", ".join(tool_preferences),
        )

    if fields and design_intent and "goal_summary" not in fields:
        add_field("goal_summary", _goal_summary_from_text(text), 0.84, text.strip())

    return cast(
        JsonObject,
        {
            "fields": fields,
            "unmapped_text": [],
            "source_spans": cast(JsonValue, source_spans),
            "mode": "rule_extract",
        },
    )


def _verify_extraction_payload(
    payload: JsonObject,
    *,
    raw_text: str,
) -> TaskSpecDraft:
    mode: ExtractionMode = "llm_extract"
    raw_mode = payload.get("mode")
    if raw_mode in {"rule_extract", "llm_extract", "manual_fallback", "none"}:
        mode = cast(ExtractionMode, raw_mode)
    draft = TaskSpecDraft(extraction_mode=mode)
    raw_fields = payload.get("fields", payload)
    if not isinstance(raw_fields, dict):
        draft.extraction_errors.append("extraction payload fields must be an object")
        return draft

    registry = _registry_fields()
    for field_name, raw_field in raw_fields.items():
        if field_name not in registry:
            draft.extraction_errors.append(
                f"extraction returned unknown field: {field_name}"
            )
            continue
        try:
            value, confidence, source_span, source = _unwrap_extracted_field(raw_field)
            if source != TaskDraftFieldSource.LLM_EXTRACT.value:
                draft.extraction_errors.append(
                    f"{field_name} source must be llm_extract"
                )
                continue
            value = _normalize_registry_value(field_name, value)
        except ValueError as exc:
            draft.extraction_errors.append(f"{field_name}: {exc}")
            continue

        field = TaskDraftField(
            value=value,
            source=TaskDraftFieldSource.LLM_EXTRACT,
            confidence=confidence,
            source_span=source_span,
            confirmed=False,
        )
        if field.confidence < LOW_CONFIDENCE_THRESHOLD:
            draft.unmapped_text.append(str(field.source_span or field.value))
            continue
        error = _validate_registry_value(field_name, field.value)
        if error is not None:
            draft.extraction_errors.append(error)
            continue
        draft.fields[field_name] = field

    raw_unmapped_text = payload.get("unmapped_text")
    if isinstance(raw_unmapped_text, list):
        for item in raw_unmapped_text:
            if isinstance(item, str) and item.strip():
                draft.unmapped_text.append(item.strip())

    if not draft.fields and raw_text.strip() and not draft.unmapped_text:
        draft.unmapped_text.append(raw_text.strip())
    return draft


def _unwrap_extracted_field(
    raw_field: JsonValue,
) -> tuple[JsonValue, float, str | None, str]:
    if not isinstance(raw_field, dict):
        raise ValueError("field extraction must be an object")
    if "value" not in raw_field:
        raise ValueError("field extraction must include value")
    confidence = raw_field.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("field extraction must include numeric confidence")
    source = raw_field.get("source")
    if not isinstance(source, str):
        raise ValueError("field extraction must include source")
    source_span = raw_field.get("source_span")
    if source_span is not None and not isinstance(source_span, str):
        raise ValueError("source_span must be a string when present")
    return raw_field["value"], float(confidence), source_span, source


def _first_present_span(text: str, needles: list[str]) -> str | None:
    lowered = text.lower()
    for needle in needles:
        if not needle:
            continue
        if needle in text or needle.lower() in lowered:
            return needle
    return None


def _goal_summary_from_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())[:2000]


def _extract_tool_preferences(text: str) -> list[str]:
    lowered = text.lower()
    has_tool_cue = any(
        marker in lowered for marker in ("use", "prefer", "allowed", "tool")
    ) or any(marker in text for marker in ("使用", "优先", "允许", "工具"))
    if not has_tool_cue:
        return []
    allowed = _allowed_tool_ids()
    return sorted(tool_id for tool_id in allowed if tool_id.lower() in lowered)


def _merge_structured_fields(
    draft: TaskSpecDraft,
    fields: JsonObject,
    *,
    source: TaskDraftFieldSource,
    confirmed: bool,
    actor: str,
) -> None:
    for field_name, raw_value in fields.items():
        value, confidence, source_span = _unwrap_field_value(raw_value)
        value = _normalize_registry_value(field_name, value)
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            draft.unmapped_text.append(f"{field_name}={value}")
            _ = draft.fields.pop(field_name, None)
            continue
        draft.fields[field_name] = TaskDraftField(
            value=value,
            source=source,
            confidence=confidence,
            source_span=source_span,
            confirmed=confirmed and confidence >= HIGH_CONFIDENCE_THRESHOLD,
            last_modified_by=actor,
        )


def _unwrap_field_value(raw_value: JsonValue) -> tuple[JsonValue, float, str | None]:
    if isinstance(raw_value, dict) and "value" in raw_value and "unit" not in raw_value:
        confidence = raw_value.get("confidence", 1.0)
        if not isinstance(confidence, (int, float)):
            confidence = 1.0
        source_span = raw_value.get("source_span")
        normalized_span = source_span if isinstance(source_span, str) else None
        return raw_value["value"], float(confidence), normalized_span
    return raw_value, 1.0, None


def _normalize_registry_value(field_name: str, value: JsonValue) -> JsonValue:
    registry = _registry_fields()
    field = registry.get(field_name)
    if field is None:
        return value

    field_type = field["type"]
    if field_type == "integer_range" and isinstance(value, dict):
        unit = str(value.get("unit", "aa")).strip().lower()
        if unit not in {"aa", "amino_acid", "amino_acids", "residue", "residues"}:
            raise ValueError(f"{field_name} unit must be amino-acid based")
        lower = value.get("min", value.get("start"))
        upper = value.get("max", value.get("end"))
        if (
            not isinstance(lower, int)
            or isinstance(lower, bool)
            or not isinstance(upper, int)
            or isinstance(upper, bool)
        ):
            raise ValueError(f"{field_name} min/max must be integers")
        return [lower, upper]

    if field_name == "max_runtime_min" and isinstance(value, dict):
        raw_amount = value.get("value")
        unit = str(value.get("unit", "min")).strip().lower()
        multipliers = {
            "m": 1,
            "min": 1,
            "minute": 1,
            "minutes": 1,
            "h": 60,
            "hr": 60,
            "hour": 60,
            "hours": 60,
            "d": 1440,
            "day": 1440,
            "days": 1440,
        }
        if unit not in multipliers:
            raise ValueError("max_runtime_min unit must be minutes, hours, or days")
        if not isinstance(raw_amount, (int, float)) or isinstance(raw_amount, bool):
            raise ValueError("max_runtime_min value must be numeric")
        minutes = raw_amount * multipliers[unit]
        if not float(minutes).is_integer():
            raise ValueError("max_runtime_min must normalize to whole minutes")
        return int(minutes)

    return value


def _required_fields_for(fields: dict[str, TaskDraftField]) -> list[str]:
    task_kind = fields.get("task_kind")
    task_kind_value = task_kind.value if task_kind is not None else "de_novo_design"
    profiles = _task_profiles()
    profile = profiles.get(str(task_kind_value), profiles["de_novo_design"])
    required = list(profile["required"])
    for rule in profile.get("conditional_required", []):
        condition = rule.get("if", {})
        if not isinstance(condition, dict):
            continue
        condition_field = fields.get(str(condition.get("field")))
        raw_required = rule.get("required", [])
        if (
            condition_field is not None
            and condition_field.value == condition.get("equals")
            and isinstance(raw_required, list)
        ):
            required.extend(str(field_name) for field_name in raw_required)
    return list(dict.fromkeys(required))


def _numeric_validator_value(
    validators: JsonObject,
    key: str,
    default: int | float,
) -> int | float:
    value = validators.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return default


def _string_validator_value(
    validators: JsonObject,
    key: str,
    default: str,
) -> str:
    value = validators.get(key)
    if isinstance(value, str):
        return value
    return default


def _validate_registry_value(field_name: str, value: JsonValue) -> str | None:
    registry = _registry_fields()
    field = registry.get(field_name)
    if field is None:
        return f"unknown intake field: {field_name}"

    field_type = field["type"]
    if field_type == "enum" and value not in set(field["options"]):
        return f"{field_name} must be one of {field['options']}"
    if field_type == "string":
        if not isinstance(value, str) or not value.strip():
            return f"{field_name} must be a non-empty string"
        validators = field.get("validators", {})
        min_length = int(_numeric_validator_value(validators, "min_length", 0))
        max_length = int(_numeric_validator_value(validators, "max_length", len(value)))
        if len(value) < min_length:
            return f"{field_name} is shorter than allowed"
        if len(value) > max_length:
            return f"{field_name} is longer than allowed"
    if field_type == "boolean" and not isinstance(value, bool):
        return f"{field_name} must be a boolean"
    if field_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{field_name} must be an integer"
        validators = field.get("validators", {})
        minimum = int(_numeric_validator_value(validators, "min", value))
        maximum = int(_numeric_validator_value(validators, "max", value))
        if value < minimum or value > maximum:
            return f"{field_name} is outside allowed range"
    if field_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"{field_name} must be a number"
        validators = field.get("validators", {})
        minimum = _numeric_validator_value(validators, "min", value)
        maximum = _numeric_validator_value(validators, "max", value)
        if value < minimum or value > maximum:
            return f"{field_name} is outside allowed range"
    if field_type == "integer_range":
        validators = field.get("validators", {})
        minimum = int(_numeric_validator_value(validators, "min", 0))
        maximum = int(_numeric_validator_value(validators, "max", 0))
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(
                isinstance(item, int) and not isinstance(item, bool) for item in value
            )
        ):
            return f"{field_name} must be [min, max] integers"
        lower = value[0]
        upper = value[1]
        if not isinstance(lower, int) or not isinstance(upper, int):
            return f"{field_name} must be [min, max] integers"
        if lower > upper or lower < minimum or upper > maximum:
            return f"{field_name} must be [min, max] integers"
    if field_type == "protein_sequence":
        if not isinstance(value, str) or not value.strip():
            return f"{field_name} must be a non-empty sequence"
        alphabet = set(_string_validator_value(field["validators"], "alphabet", ""))
        invalid = set(value.upper()) - alphabet
        if invalid:
            return f"{field_name} contains invalid residues: {''.join(sorted(invalid))}"
    if field_type in {"string_list", "tool_id_list"}:
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            return f"{field_name} must be a list of strings"
        if field_type == "tool_id_list":
            values = {item for item in value if isinstance(item, str)}
            invalid_tool_ids = sorted(values - _allowed_tool_ids())
            if invalid_tool_ids:
                return (
                    f"{field_name} contains unknown tool_id(s): "
                    f"{', '.join(invalid_tool_ids)}"
                )
    if field_type == "residue_list":
        if not isinstance(value, list) or not all(
            isinstance(item, str) and re.match(r"^[A-Z][0-9]+$", item) for item in value
        ):
            return f"{field_name} must be residue ids like A42"
    if field_type == "artifact_ref_list":
        return _validate_artifact_ref_list(field_name, value)
    return None


def _allowed_tool_ids() -> set[str]:
    return {
        tool_id
        for option in build_tool_kg_options()
        if isinstance((tool_id := option.get("tool_id")), str)
    }


def _validate_artifact_ref_list(field_name: str, value: object) -> str | None:
    if not isinstance(value, list):
        return f"{field_name} must be a list of artifact refs"

    artifacts = cast(list[object], value)
    for index, raw_artifact in enumerate(artifacts):
        artifact = cast(dict[object, object], raw_artifact)
        if not isinstance(raw_artifact, dict):
            return f"{field_name}[{index}] must be an object"
        kind = artifact.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            return f"{field_name}[{index}].kind must be a non-empty string"

        ref_values = [
            artifact.get("artifact_id"),
            artifact.get("uri"),
            artifact.get("path"),
            artifact.get("ref"),
        ]
        if not any(isinstance(item, str) and item.strip() for item in ref_values):
            return f"{field_name}[{index}] must include artifact_id, uri, path, or ref"

        artifact_id = artifact.get("artifact_id")
        if isinstance(artifact_id, str) and not re.match(
            r"^[A-Za-z0-9_.:-]+$",
            artifact_id,
        ):
            return f"{field_name}[{index}].artifact_id is invalid"

        uri = artifact.get("uri")
        if isinstance(uri, str) and not (
            uri.startswith("artifact://") or uri.startswith("task://")
        ):
            return f"{field_name}[{index}].uri must use artifact:// or task://"

        path = artifact.get("path")
        if isinstance(path, str) and (
            path.startswith("/")
            or path.startswith("~")
            or ".." in path.split("/")
            or not path.strip()
        ):
            return f"{field_name}[{index}].path must be a safe relative path"

        ref = artifact.get("ref")
        if isinstance(ref, str) and not re.match(
            r"^task_[A-Za-z0-9_:-]+\.[A-Za-z][A-Za-z0-9_.-]*$",
            ref,
        ):
            return f"{field_name}[{index}].ref must look like task_id.artifact_key"

    return None


def _run_safety_input_precheck(session: TaskIntakeSession) -> TaskIntakeSafetyCheck:
    fields = {name: field.value for name, field in session.draft.fields.items()}
    input_summary = _build_safety_input_summary(session, fields)
    risk_flags: list[TaskIntakeSafetyRisk] = []
    safety_text = _safety_search_text(fields, session.raw_input)

    if any(term in safety_text for term in ("weapon", "bioweapon", "病原增强")):
        risk_flags.append(
            TaskIntakeSafetyRisk(
                level="block",
                code="SAFETY_INPUT_BLOCK",
                message="input appears to request a blocked unsafe biological use",
                details={"terms": ["weapon", "bioweapon", "病原增强"]},
            )
        )

    sequence = fields.get("sequence")
    forbidden_motifs = fields.get("forbidden_motifs")
    if isinstance(sequence, str) and isinstance(forbidden_motifs, list):
        normalized_sequence = sequence.upper()
        for motif in forbidden_motifs:
            if isinstance(motif, str) and motif.upper() in normalized_sequence:
                risk_flags.append(
                    TaskIntakeSafetyRisk(
                        level="warn",
                        code="FORBIDDEN_MOTIF_PRESENT",
                        message=(
                            "forbidden_motifs contains motif present in sequence: "
                            f"{motif}"
                        ),
                        details={"motif": motif},
                    )
                )

    for forbidden_function in _coerce_string_list(fields.get("forbidden_functions")):
        if _text_mentions_forbidden_function(
            fields, session.raw_input, forbidden_function
        ):
            risk_flags.append(
                TaskIntakeSafetyRisk(
                    level="block",
                    code="FORBIDDEN_FUNCTION_REQUESTED",
                    message=(
                        "input requests a function listed in forbidden_functions: "
                        f"{forbidden_function}"
                    ),
                    details={"forbidden_function": forbidden_function},
                )
            )

    if _mentions_high_risk_intent(fields, session.raw_input):
        risk_flags.append(
            TaskIntakeSafetyRisk(
                level="block",
                code="HIGH_RISK_BIOFUNCTION_REQUEST",
                message="input appears to request a high-risk biological function",
                details={"keywords": list(_HIGH_RISK_FUNCTION_KEYWORDS)},
            )
        )

    if fields.get("safety_level") == "S2" or any(
        term in safety_text for term in ("pathogenic", "毒性", "病原")
    ):
        risk_flags.append(
            TaskIntakeSafetyRisk(
                level="warn",
                code="SAFETY_INPUT_WARN",
                message="input may need additional safety review before task creation",
                details={"safety_level": fields.get("safety_level")},
            )
        )

    action: Literal["ok", "warn", "block"] = "ok"
    if any(risk.level == "block" for risk in risk_flags):
        action = "block"
    elif any(risk.level == "warn" for risk in risk_flags):
        action = "warn"
    return TaskIntakeSafetyCheck(
        action=action,
        risk_flags=risk_flags,
        input_summary=input_summary,
    )


def _field_validation_warnings(session: TaskIntakeSession) -> list[str]:
    """收集 registry 字段校验错误，避免与可确认 Safety warn 混淆。"""

    warnings: list[str] = []
    for field in session.draft.fields.values():
        warnings.extend(field.warnings)
    return warnings


def _missing_acknowledged_warnings(
    session: TaskIntakeSession,
    acknowledged_warnings: list[str],
) -> list[str]:
    """返回尚未确认的 Safety warn code/message。"""

    acknowledged = {item.strip() for item in acknowledged_warnings if item.strip()}
    missing: list[str] = []
    for risk in session.safety_check.risk_flags:
        if risk.level != "warn":
            continue
        if risk.code not in acknowledged and risk.message not in acknowledged:
            missing.append(risk.code)
    return missing


def _append_intake_audit_event(
    session: TaskIntakeSession,
    event_type: TaskIntakeAuditEventName,
    *,
    actor_type: str = "system",
    actor_id: str | None = None,
    data: JsonObject | None = None,
) -> None:
    """追加 intake 级审计事件。"""

    normalized_actor: IntakeActorType = (
        cast(IntakeActorType, actor_type)
        if actor_type
        in {
            "api",
            "web",
            "cli",
            "script",
            "legacy",
            "system",
        }
        else "system"
    )
    session.audit_events.append(
        TaskIntakeAuditEvent(
            event_type=event_type,
            intake_id=session.intake_id,
            actor_type=normalized_actor,
            actor_id=actor_id,
            data=data or {},
        )
    )


def _raw_input_summary(raw_input: JsonObject) -> JsonObject:
    text = raw_input.get("text")
    structured = raw_input.get("structured_fields")
    structured_field_names = sorted(structured) if isinstance(structured, dict) else []
    return cast(
        JsonObject,
        {
            "source": raw_input.get("source"),
            "text_length": len(text) if isinstance(text, str) else 0,
            "structured_field_names": cast(JsonValue, structured_field_names),
        },
    )


def _build_safety_input_summary(
    session: TaskIntakeSession,
    fields: JsonObject,
) -> JsonObject:
    safety_constraints = {
        name: fields[name]
        for name in (
            "safety_level",
            "forbidden_motifs",
            "forbidden_functions",
            "organism",
        )
        if name in fields
    }
    return cast(
        JsonObject,
        {
            "raw_input_summary": _raw_input_summary(session.raw_input),
            "confirmed_spec_draft": _build_confirmed_spec_draft_payload(session),
            "safety_constraints": safety_constraints,
            "forbidden_functions": cast(
                JsonValue,
                _coerce_string_list(fields.get("forbidden_functions")),
            ),
            "organism": fields.get("organism"),
        },
    )


def _build_confirmed_spec_draft_payload(session: TaskIntakeSession) -> JsonObject:
    fields = {name: field.value for name, field in session.draft.fields.items()}
    objective: JsonObject = {}
    inputs: JsonObject = {}
    constraints: JsonObject = {}
    initial_artifacts: list[JsonObject] = []
    registry = _registry_fields()

    for field_name, value in fields.items():
        maps_to = registry[field_name]["maps_to"]
        if maps_to.startswith("objective."):
            objective[maps_to.split(".", 1)[1]] = value
        elif maps_to.startswith("inputs."):
            inputs[maps_to.split(".", 1)[1]] = value
        elif maps_to.startswith("constraints."):
            constraints[maps_to.split(".", 1)[1]] = value
        elif maps_to == "initial_artifacts":
            initial_artifacts = _artifact_refs_from_value(value)

    return cast(
        JsonObject,
        {
            "goal": _build_goal(fields),
            "objective": objective,
            "inputs": inputs,
            "constraints": constraints,
            "initial_artifacts": cast(JsonValue, initial_artifacts),
            "metadata": {
                "intake_id": session.intake_id,
                "field_registry_version": TASK_FIELD_REGISTRY_VERSION,
            },
        },
    )


def _artifact_refs_from_value(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    artifacts: list[JsonObject] = []
    for item in value:
        if isinstance(item, dict):
            artifacts.append(item)
    return artifacts


def _coerce_string_list(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _text_mentions_forbidden_function(
    fields: JsonObject,
    raw_input: JsonObject,
    forbidden_function: str,
) -> bool:
    target = forbidden_function.strip().lower()
    if not target:
        return False
    return target in _safety_search_text(fields, raw_input)


def _mentions_high_risk_intent(
    fields: JsonObject,
    raw_input: JsonObject,
) -> bool:
    haystack = _safety_search_text(fields, raw_input)
    return any(keyword in haystack for keyword in _HIGH_RISK_FUNCTION_KEYWORDS)


def _safety_search_text(fields: JsonObject, raw_input: JsonObject) -> str:
    pieces: list[str] = []
    raw_text = raw_input.get("text")
    if isinstance(raw_text, str):
        pieces.append(raw_text)
    for name in (
        "goal_summary",
        "objective_description",
        "motif_pattern",
        "binding_partner",
        "target_ligand",
    ):
        value = fields.get(name)
        if isinstance(value, str):
            pieces.append(value)
    return "\n".join(pieces).lower()


def _build_human_summary(session: TaskIntakeSession) -> str:
    fields = {name: field.value for name, field in session.draft.fields.items()}
    task_kind = fields.get("task_kind", "unknown task")
    objective = fields.get("objective_type", "unspecified objective")
    pieces = [f"{task_kind} / {objective}", f"status={session.status.value}"]
    if session.missing_required_fields:
        pieces.append(f"missing={', '.join(session.missing_required_fields)}")
    if session.ambiguous_fields:
        pieces.append(f"ambiguous={', '.join(session.ambiguous_fields)}")
    if session.warnings:
        pieces.append(f"warnings={len(session.warnings)}")
    return "; ".join(pieces)


def _build_confirmed_spec(
    session: TaskIntakeSession,
    *,
    confirmed_by: str,
    acknowledged_warnings: list[str],
) -> ConfirmedTaskSpec:
    fields = {name: field.value for name, field in session.draft.fields.items()}
    objective: JsonObject = {}
    inputs: JsonObject = {}
    constraints: JsonObject = {}
    initial_artifacts: list[JsonObject] = []
    registry = _registry_fields()

    for field_name, value in fields.items():
        maps_to = registry[field_name]["maps_to"]
        if maps_to.startswith("objective."):
            objective[maps_to.split(".", 1)[1]] = value
        elif maps_to.startswith("inputs."):
            inputs[maps_to.split(".", 1)[1]] = value
        elif maps_to.startswith("constraints."):
            constraints[maps_to.split(".", 1)[1]] = value
        elif maps_to == "initial_artifacts":
            initial_artifacts = _artifact_refs_from_value(value)

    goal = _build_goal(fields)
    metadata: JsonObject = {
        "intake_id": session.intake_id,
        "field_registry_version": TASK_FIELD_REGISTRY_VERSION,
        "support_level": _support_level_for(fields),
        "planner_capability_hints": cast(JsonValue, _capability_hints_for(fields)),
        "confirmed_by": confirmed_by,
        "input_mode": _input_mode(session),
        "acknowledged_warnings": cast(JsonValue, list(acknowledged_warnings)),
        "safety_check": cast(JsonValue, session.safety_check.model_dump(mode="json")),
        "intake_audit_events": cast(
            JsonValue,
            [
                cast(JsonObject, event.model_dump(mode="json"))
                for event in session.audit_events
            ],
        ),
        "raw_query": str(session.raw_input.get("text") or ""),
        "unmapped_text": cast(JsonValue, list(session.unmapped_text)),
        "intake_summary": {
            "field_count": len(session.draft.fields),
            "ambiguous_fields": cast(JsonValue, list(session.ambiguous_fields)),
            "missing_required_fields": cast(
                JsonValue,
                list(session.missing_required_fields),
            ),
        },
    }
    if "intent_draft_id" in session.raw_input:
        metadata["intent_draft_id"] = session.raw_input["intent_draft_id"]

    return ConfirmedTaskSpec(
        goal=goal,
        objective=objective,
        inputs=inputs,
        constraints=constraints,
        initial_artifacts=initial_artifacts,
        metadata=metadata,
    )


def _build_goal(fields: JsonObject) -> str:
    goal_summary = fields.get("goal_summary") or fields.get("objective_description")
    if isinstance(goal_summary, str) and goal_summary.strip():
        return goal_summary.strip()
    task_kind = fields.get("task_kind", "de_novo_design")
    objective = fields.get("objective_type", "protein design")
    length_range = fields.get("length_range")
    if isinstance(length_range, list) and len(length_range) == 2:
        return (
            f"{task_kind} for {objective} "
            f"with length {length_range[0]}-{length_range[1]} aa"
        )
    return f"{task_kind} for {objective}"


def _support_level_for(fields: JsonObject) -> str:
    task_kind = fields.get("task_kind", "de_novo_design")
    profile = _task_profiles().get(
        str(task_kind),
        _task_profiles()["de_novo_design"],
    )
    return str(profile["support_level"])


def _capability_hints_for(fields: JsonObject) -> list[str]:
    task_kind = fields.get("task_kind", "de_novo_design")
    profile = _task_profiles().get(
        str(task_kind),
        _task_profiles()["de_novo_design"],
    )
    return list(profile["capability_hints"])


def _input_mode(session: TaskIntakeSession) -> str:
    has_text = bool(session.raw_input.get("text"))
    has_structured = bool(session.raw_input.get("structured_fields"))
    if has_text and has_structured:
        return "mixed_with_confirmation"
    if has_text:
        return "natural_language_with_confirmation"
    return "structured_with_confirmation"
