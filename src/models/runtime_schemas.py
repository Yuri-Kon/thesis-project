from __future__ import annotations

import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RUNTIME_SCHEMA_VERSION = 1
RUNTIME_STATE_CORE_FIELDS = (
    "p_success",
    "p_structural_failure",
    "recovery_margin",
    "expected_remaining_cost",
    "evidence_sufficiency",
)
RUNTIME_ACTIONS = ("continue", "patch_local", "suffix_replan", "stop")
OBSERVATION_SOURCE_TYPES = (
    "step_result",
    "safety_result",
    "patch_history",
    "replan_history",
    "budget",
    "hitl_decision",
)

__all__ = [
    "ActionUtility",
    "CostSchema",
    "ObservationSchema",
    "ObservationSource",
    "RecoverySchema",
    "RiskSchema",
    "RuntimeSchemaFieldMapping",
    "RuntimeStateSchema",
    "StateSchema",
    "runtime_schema_field_mappings",
]


def _validate_unit_interval(value: float, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return normalized


def _validate_finite_float(value: float, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


def _validate_json_mapping(value: dict[str, Any], *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    try:
        json.dumps(value, ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-serializable") from exc
    return value


def _weighted_sum(weights: dict[str, float], values: dict[str, float]) -> float:
    return sum(weights[name] * values[name] for name in weights)


class RuntimeContractBase(BaseModel):
    """运行时契约模型的公共基类。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=RUNTIME_SCHEMA_VERSION)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != RUNTIME_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {RUNTIME_SCHEMA_VERSION}")
        return value


class CostSchema(RuntimeContractBase):
    """运行时成本契约，对齐 Cost Schema 的五类标准化成本分量。"""

    compute_cost: float = 0.0
    latency_cost: float = 0.0
    opportunity_cost: float = 0.0
    recovery_cost: float = 0.0
    human_cost: float = 0.0
    remaining_cost_prior: float | None = None
    expected_remaining_cost: float | None = None
    source_refs: list[str] = Field(default_factory=list)

    @field_validator(
        "compute_cost",
        "latency_cost",
        "opportunity_cost",
        "recovery_cost",
        "human_cost",
    )
    @classmethod
    def _validate_cost_component(cls, value: float, info) -> float:
        return _validate_unit_interval(value, field_name=info.field_name)

    @field_validator("remaining_cost_prior", "expected_remaining_cost")
    @classmethod
    def _validate_optional_non_negative(cls, value: float | None, info) -> float | None:
        if value is None:
            return None
        normalized = _validate_finite_float(value, field_name=info.field_name)
        if normalized < 0.0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return normalized

    def weighted_cost(self) -> float:
        """返回设计文档定义的加权成本分。"""

        return round(
            _weighted_sum(
                {
                    "compute_cost": 0.35,
                    "latency_cost": 0.25,
                    "opportunity_cost": 0.20,
                    "recovery_cost": 0.15,
                    "human_cost": 0.05,
                },
                self.model_dump(),
            ),
            6,
        )


class RiskSchema(RuntimeContractBase):
    """运行时风险契约，对齐 Risk Schema 的四类标准化风险分量。"""

    structural_risk: float = 0.0
    execution_risk: float = 0.0
    safety_risk: float = 0.0
    coupling_risk: float = 0.0
    hard_blocked: bool = False
    infeasible_reason: str | None = None
    source_refs: list[str] = Field(default_factory=list)

    @field_validator(
        "structural_risk",
        "execution_risk",
        "safety_risk",
        "coupling_risk",
    )
    @classmethod
    def _validate_risk_component(cls, value: float, info) -> float:
        return _validate_unit_interval(value, field_name=info.field_name)

    def weighted_risk(self) -> float:
        """返回设计文档定义的加权风险分。"""

        if self.hard_blocked:
            return 1.0
        return round(
            _weighted_sum(
                {
                    "structural_risk": 0.45,
                    "execution_risk": 0.25,
                    "safety_risk": 0.20,
                    "coupling_risk": 0.10,
                },
                self.model_dump(),
            ),
            6,
        )


class RecoverySchema(RuntimeContractBase):
    """运行时恢复契约，对齐 Recovery Schema。"""

    retry_budget_ratio: float = 0.0
    local_patchability: float = 0.0
    prefix_preservability: float = 0.0
    evidence_reusability: float = 0.0
    recovery_margin: float | None = None
    source_refs: list[str] = Field(default_factory=list)

    @field_validator(
        "retry_budget_ratio",
        "local_patchability",
        "prefix_preservability",
        "evidence_reusability",
    )
    @classmethod
    def _validate_recovery_component(cls, value: float, info) -> float:
        return _validate_unit_interval(value, field_name=info.field_name)

    @field_validator("recovery_margin")
    @classmethod
    def _validate_optional_recovery_margin(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return _validate_unit_interval(value, field_name="recovery_margin")

    def recoverability(self) -> float:
        """返回设计文档定义的恢复性分。"""

        return round(
            _weighted_sum(
                {
                    "retry_budget_ratio": 0.30,
                    "local_patchability": 0.30,
                    "prefix_preservability": 0.25,
                    "evidence_reusability": 0.15,
                },
                self.model_dump(),
            ),
            6,
        )

    def recovery_complexity(self) -> float:
        """返回恢复复杂度，定义为 1 - recoverability。"""

        return round(1.0 - self.recoverability(), 6)


class RuntimeStateSchema(RuntimeContractBase):
    """Lite runtime state 契约，固定第一版五个核心状态量。"""

    p_success: float = 0.5
    p_structural_failure: float = 0.25
    recovery_margin: float = 0.6
    expected_remaining_cost: float = 1.0
    evidence_sufficiency: float = 0.5
    last_update_source: str = "runtime_bootstrap"
    observation_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("p_success", "p_structural_failure", "evidence_sufficiency")
    @classmethod
    def _validate_probability(cls, value: float, info) -> float:
        return _validate_unit_interval(value, field_name=info.field_name)

    @field_validator("recovery_margin")
    @classmethod
    def _validate_recovery_margin(cls, value: float) -> float:
        return _validate_unit_interval(value, field_name="recovery_margin")

    @field_validator("expected_remaining_cost")
    @classmethod
    def _validate_expected_remaining_cost(cls, value: float) -> float:
        normalized = _validate_finite_float(value, field_name="expected_remaining_cost")
        if normalized < 0.0:
            raise ValueError("expected_remaining_cost must be >= 0")
        return normalized

    @field_validator("last_update_source")
    @classmethod
    def _validate_last_update_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("last_update_source must not be empty")
        return normalized

    @field_validator("observation_summary")
    @classmethod
    def _validate_observation_summary(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_json_mapping(value, field_name="observation_summary")

    @classmethod
    def from_snapshot_payload(cls, payload: dict[str, Any]) -> "RuntimeStateSchema":
        """从新旧 snapshot.artifacts.runtime_state 载荷恢复状态契约。"""

        if not isinstance(payload, dict):
            raise ValueError("runtime_state snapshot payload must be a mapping")
        return cls.model_validate(dict(payload))

    def to_snapshot_payload(self) -> dict[str, Any]:
        """输出 snapshot.artifacts.runtime_state 的稳定字段。"""

        return self.model_dump(exclude={"observation_summary"})

    def to_summary_payload(self) -> dict[str, Any]:
        """输出 UI/CLI/Planner/EventLog 共用的轻量状态摘要。"""

        return {
            key: getattr(self, key)
            for key in ("schema_version", *RUNTIME_STATE_CORE_FIELDS)
        }


class ObservationSource(BaseModel):
    """运行时观测来源引用，只允许来自设计文档指定来源。"""

    model_config = ConfigDict(extra="forbid")

    source_type: Literal[
        "step_result",
        "safety_result",
        "patch_history",
        "replan_history",
        "budget",
        "hitl_decision",
    ]
    ref: str
    fields: list[str] = Field(default_factory=list)

    @field_validator("ref")
    @classmethod
    def _validate_ref(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("ref must not be empty")
        return normalized


class ObservationSchema(RuntimeContractBase):
    """运行时观测契约，承载状态更新可消费的标准化观测。"""

    quality_obs: dict[str, Any] = Field(default_factory=dict)
    failure_obs: dict[str, Any] = Field(default_factory=dict)
    safety_obs: dict[str, Any] = Field(default_factory=dict)
    budget_obs: dict[str, Any] = Field(default_factory=dict)
    agreement_obs: dict[str, Any] = Field(default_factory=dict)
    progress_obs: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[ObservationSource] = Field(default_factory=list)

    @field_validator(
        "quality_obs",
        "failure_obs",
        "safety_obs",
        "budget_obs",
        "agreement_obs",
        "progress_obs",
    )
    @classmethod
    def _validate_observation_mapping(
        cls,
        value: dict[str, Any],
        info,
    ) -> dict[str, Any]:
        return _validate_json_mapping(value, field_name=info.field_name)


class ActionUtility(RuntimeContractBase):
    """动作效用契约，供 RuntimeEvaluator、EventLog 与 UI/CLI 复用。"""

    action: Literal["continue", "patch_local", "suffix_replan", "stop"]
    utility: float
    hard_constraints: list[str] = Field(default_factory=list)
    tie_break_reason: str | None = None
    intervention_value: float = 0.0
    budget_pressure: float = 0.0
    terminal_reason: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("utility")
    @classmethod
    def _validate_utility(cls, value: float) -> float:
        return _validate_unit_interval(value, field_name="utility")

    @field_validator("intervention_value", "budget_pressure")
    @classmethod
    def _validate_unit_value(cls, value: float, info) -> float:
        return _validate_unit_interval(value, field_name=info.field_name)

    @field_validator("hard_constraints", "source_refs")
    @classmethod
    def _validate_string_list(cls, value: list[str], info) -> list[str]:
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"{info.field_name} items must be strings")
            text = item.strip()
            if not text:
                raise ValueError(f"{info.field_name} items must not be empty")
            normalized.append(text)
        return normalized

    @field_validator("tie_break_reason", "terminal_reason")
    @classmethod
    def _validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must not be empty")
        return normalized

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_json_mapping(value, field_name="metadata")


class RuntimeSchemaFieldMapping(BaseModel):
    """运行时契约字段到各消费面的稳定映射。"""

    model_config = ConfigDict(extra="forbid")

    schema_name: str
    snapshot_fields: list[str] = Field(default_factory=list)
    event_fields: list[str] = Field(default_factory=list)
    planner_metadata_fields: list[str] = Field(default_factory=list)
    ui_summary_fields: list[str] = Field(default_factory=list)
    cli_summary_fields: list[str] = Field(default_factory=list)


RUNTIME_SCHEMA_FIELD_MAPPINGS: dict[str, RuntimeSchemaFieldMapping] = {
    "cost": RuntimeSchemaFieldMapping(
        schema_name="cost",
        snapshot_fields=[
            "artifacts.runtime_cost",
            "artifacts.runtime_state.expected_remaining_cost",
        ],
        event_fields=[
            "data.runtime_cost",
            "data.score_breakdown.cost",
        ],
        planner_metadata_fields=[
            "metadata.cost_schema",
            "metadata.score_breakdown.cost",
            "metadata.runtime_state_summary.expected_remaining_cost",
        ],
        ui_summary_fields=["score_breakdown.cost", "cost_estimate"],
        cli_summary_fields=["score_breakdown.cost", "cost_estimate"],
    ),
    "risk": RuntimeSchemaFieldMapping(
        schema_name="risk",
        snapshot_fields=[
            "artifacts.runtime_risk",
            "artifacts.runtime_state.p_structural_failure",
        ],
        event_fields=[
            "data.runtime_risk",
            "data.score_breakdown.risk",
        ],
        planner_metadata_fields=[
            "metadata.risk_schema",
            "metadata.score_breakdown.risk",
            "metadata.runtime_state_summary.p_structural_failure",
        ],
        ui_summary_fields=["score_breakdown.risk", "risk_level"],
        cli_summary_fields=["score_breakdown.risk", "risk_level"],
    ),
    "recovery": RuntimeSchemaFieldMapping(
        schema_name="recovery",
        snapshot_fields=[
            "artifacts.recovery_history",
            "artifacts.runtime_recovery",
            "artifacts.runtime_state.recovery_margin",
        ],
        event_fields=[
            "data.patch",
            "data.recovery",
            "data.runtime_recovery",
        ],
        planner_metadata_fields=[
            "metadata.recovery_schema",
            "metadata.recovery_semantics",
            "metadata.runtime_state_summary.recovery_margin",
        ],
        ui_summary_fields=["recovery_semantics", "affected_steps"],
        cli_summary_fields=["recovery_semantics", "affected_steps"],
    ),
    "state": RuntimeSchemaFieldMapping(
        schema_name="state",
        snapshot_fields=[
            "artifacts.runtime_state",
            "artifacts.runtime_state_summary",
            "artifacts.runtime_observation_summary",
        ],
        event_fields=[
            "data.runtime_state_summary",
            "data.waiting_runtime_summary.runtime_state_summary",
        ],
        planner_metadata_fields=[
            "metadata.runtime_state_summary",
            "metadata.waiting_runtime_summary.runtime_state_summary",
        ],
        ui_summary_fields=["runtime_state_summary"],
        cli_summary_fields=["runtime_state_summary"],
    ),
    "observation": RuntimeSchemaFieldMapping(
        schema_name="observation",
        snapshot_fields=[
            "artifacts.runtime_observation_summary",
            "artifacts.recovery_history",
        ],
        event_fields=[
            "data.evidence_refs",
            "data.workflow_action_evidence",
        ],
        planner_metadata_fields=[
            "metadata.workflow_action_evidence",
            "metadata.rerank_reason",
        ],
        ui_summary_fields=["evidence_refs", "workflow_action_reason"],
        cli_summary_fields=["evidence_refs", "workflow_action_reason"],
    ),
    "action_utility": RuntimeSchemaFieldMapping(
        schema_name="action_utility",
        snapshot_fields=[
            "artifacts.waiting_runtime_summary.action_utility",
            "artifacts.decision_summary.terminal_reason",
        ],
        event_fields=[
            "data.action_utility",
            "data.workflow_action_reason",
            "data.terminal_reason",
        ],
        planner_metadata_fields=[
            "metadata.action_utility",
            "metadata.workflow_action_reason",
            "metadata.waiting_runtime_summary.action_score",
        ],
        ui_summary_fields=[
            "default_suggestion",
            "workflow_action_reason",
            "score_breakdown",
        ],
        cli_summary_fields=[
            "default_suggestion",
            "workflow_action_reason",
            "score_breakdown",
        ],
    ),
}


def runtime_schema_field_mappings() -> dict[str, dict[str, Any]]:
    """返回 snapshot/event/planner/UI/CLI 的运行时契约字段映射。"""

    return {
        name: mapping.model_dump()
        for name, mapping in RUNTIME_SCHEMA_FIELD_MAPPINGS.items()
    }


StateSchema = RuntimeStateSchema
