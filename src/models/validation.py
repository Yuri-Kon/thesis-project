from __future__ import annotations

from dataclasses import dataclass, field
import math
from collections.abc import Callable, Mapping
from typing import TypeGuard, cast

from src.models.contracts import (
    ACTION_SCORE_METADATA_KEY,
    Decision,
    DecisionChoice,
    FINAL_SCORE_METADATA_KEY,
    PendingAction,
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanStep,
    ProteinDesignTask,
    RERANK_REASON_METADATA_KEY,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
    SHADOW_SCORE_METADATA_KEY,
    STATIC_SCORE_METADATA_KEY,
    JsonMap,
)
from src.kg.kg_client import ToolKGError, load_tool_kg
from src.adapters.registry import get_adapter

ALLOWED_DECISION_CHOICES = {
    PendingActionType.PLAN_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.REPLAN,
        DecisionChoice.CANCEL,
    },
    PendingActionType.PATCH_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.REPLAN,
        DecisionChoice.CANCEL,
    },
    PendingActionType.REPLAN_CONFIRM: {
        DecisionChoice.ACCEPT,
        DecisionChoice.CONTINUE,
        DecisionChoice.CANCEL,
    },
}

KgLoader = Callable[[], JsonMap]


def _is_str_object_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    if not isinstance(value, Mapping):
        return False
    mapping = cast(Mapping[object, object], value)
    return all(isinstance(key, str) for key in mapping)


def _as_json_map(value: object) -> JsonMap:
    if not _is_str_object_mapping(value):
        return {}
    return dict(value)


def _as_json_map_list(value: object) -> list[JsonMap]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [_as_json_map(item) for item in items if _is_str_object_mapping(item)]


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item for item in items if isinstance(item, str)]


class DecisionValidationError(ValueError):
    """Decision 与 PendingAction 约束冲突时抛出。"""


class CandidateSetValidationError(ValueError):
    """CandidateSetOutput 契约校验失败时抛出。"""


REQUIRED_SCORE_BREAKDOWN_FIELDS = frozenset(
    {"feasibility", "objective", "risk", "cost", "overall"}
)
REQUIRED_SHADOW_RERANK_METADATA_FIELDS = frozenset(
    {
        STATIC_SCORE_METADATA_KEY,
        RUNTIME_ADJUSTMENT_METADATA_KEY,
        FINAL_SCORE_METADATA_KEY,
        RERANK_REASON_METADATA_KEY,
    }
)
REQUIRED_S5_INPUT_FIELDS = frozenset({"candidates", "metrics"})
REQUIRED_S5_OUTPUT_FIELDS = frozenset(
    {"score_breakdown", "top_k", "default_recommendation", "explanation"}
)
REQUIRED_S5_WEIGHT_FIELDS = frozenset(
    {
        "feasibility",
        "objective",
        "risk",
        "cost",
        "confidence",
        "tool_readiness",
        "tool_coverage",
    }
)
REQUIRED_TOOL_METADATA_WITH_DEFAULTS = frozenset(
    {"tool_id", "capability_id", "io_type", "adapter_mode"}
)
ALLOWED_EXECUTION_BACKENDS = frozenset(
    {"python", "nextflow", "external_api", "remote_model_service"}
)
REFERENCE_PREFIX = "S"


@dataclass(frozen=True)
class CandidateExecutionIssue:
    """单条候选可执行性失败项。"""

    code: str
    message: str
    step_id: str | None = None
    tool_id: str | None = None
    capability_id: str | None = None
    io_type: str | None = None
    details: JsonMap = field(default_factory=dict)

    def as_dict(self) -> JsonMap:
        return {
            "code": self.code,
            "message": self.message,
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "capability_id": self.capability_id,
            "io_type": self.io_type,
            "details": dict(self.details),
        }


class CandidateExecutionValidationError(ValueError):
    """候选可执行性硬约束校验失败。"""

    def __init__(self, issues: list[CandidateExecutionIssue]):
        self.issues: list[CandidateExecutionIssue] = list(issues)
        if self.issues:
            first = self.issues[0]
            super().__init__(f"{first.code}: {first.message}")
        else:
            super().__init__("candidate execution validation failed")


def validate_candidate_set_output(
    pending_action: PendingAction,
    *,
    require_v1_fields: bool = True,
    require_default_recommendation: bool = True,
    require_s5_fields: bool = False,
    require_shadow_rerank_fields: bool = False,
) -> None:
    """校验 CandidateSetOutput 契约（用于 Planner/HITL 输出）。

    Args:
        pending_action: 待校验的 PendingAction 对象。
        require_v1_fields: 是否要求每个候选必须包含 v1 字段集。
        require_default_recommendation: 是否要求存在默认推荐候选。

    Raises:
        CandidateSetValidationError: 候选字段或集合约束不满足。
    """
    if not pending_action.candidates:
        raise CandidateSetValidationError("candidates must not be empty")

    seen_ids: set[str] = set()
    for candidate in pending_action.candidates:
        candidate_id = _resolve_candidate_id(candidate)
        if not candidate_id:
            raise CandidateSetValidationError("candidate_id is required")
        if candidate_id in seen_ids:
            raise CandidateSetValidationError(
                f"candidate_id {candidate_id} is duplicated"
            )
        seen_ids.add(candidate_id)
        if require_v1_fields:
            _validate_candidate_v1_fields(candidate, candidate_id)
        if require_s5_fields:
            _validate_candidate_s5_fields(candidate, candidate_id)
        if require_shadow_rerank_fields:
            _validate_candidate_shadow_rerank_fields(candidate, candidate_id)

    default_id = (
        pending_action.default_recommendation or pending_action.default_suggestion
    )
    if require_default_recommendation and not default_id:
        raise CandidateSetValidationError(
            "default_recommendation is required for candidate set output"
        )
    if default_id and default_id not in seen_ids:
        raise CandidateSetValidationError("default_recommendation is not in candidates")


def _validate_candidate_v1_fields(
    candidate: PendingActionCandidate, candidate_id: str
) -> None:
    if candidate.structured_payload is None:
        raise CandidateSetValidationError(
            f"{candidate_id}.structured_payload is required"
        )
    if not candidate.score_breakdown:
        raise CandidateSetValidationError(f"{candidate_id}.score_breakdown is required")
    missing_keys = REQUIRED_SCORE_BREAKDOWN_FIELDS - set(candidate.score_breakdown)
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise CandidateSetValidationError(
            f"{candidate_id}.score_breakdown missing keys: {missing}"
        )
    if candidate.risk_level is None:
        raise CandidateSetValidationError(f"{candidate_id}.risk_level is required")
    if candidate.cost_estimate is None:
        raise CandidateSetValidationError(f"{candidate_id}.cost_estimate is required")
    if not candidate.explanation:
        raise CandidateSetValidationError(f"{candidate_id}.explanation is required")
    _validate_candidate_tool_fields(candidate, candidate_id)


def _validate_candidate_tool_fields(
    candidate: PendingActionCandidate, candidate_id: str
) -> None:
    if candidate.tool_id is None:
        raise CandidateSetValidationError(f"{candidate_id}.tool_id is required")
    if candidate.capability_id is None:
        raise CandidateSetValidationError(f"{candidate_id}.capability_id is required")
    if candidate.io_type is None:
        raise CandidateSetValidationError(f"{candidate_id}.io_type is required")
    if candidate.adapter_mode is None:
        raise CandidateSetValidationError(f"{candidate_id}.adapter_mode is required")

    metadata = _as_json_map(candidate.metadata)
    missing_metadata = [
        key
        for key in REQUIRED_TOOL_METADATA_WITH_DEFAULTS
        if key not in metadata or metadata.get(key) in (None, "")
    ]
    if missing_metadata:
        missing = ", ".join(sorted(missing_metadata))
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata missing tool keys: {missing}"
        )


def _validate_candidate_shadow_rerank_fields(
    candidate: PendingActionCandidate, candidate_id: str
) -> None:
    metadata = candidate.metadata or {}
    missing = [
        key for key in REQUIRED_SHADOW_RERANK_METADATA_FIELDS if key not in metadata
    ]
    if missing:
        missing_keys = ", ".join(sorted(missing))
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata missing shadow rerank keys: {missing_keys}"
        )

    static_score_raw = metadata[STATIC_SCORE_METADATA_KEY]
    final_score_raw = metadata[FINAL_SCORE_METADATA_KEY]
    runtime_adjustment_raw = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
    rerank_reason_raw = metadata[RERANK_REASON_METADATA_KEY]

    if not _is_str_object_mapping(static_score_raw) or not _is_str_object_mapping(
        final_score_raw
    ):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata static/final socre must be mappings"
        )
    if not _is_str_object_mapping(runtime_adjustment_raw):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{RUNTIME_ADJUSTMENT_METADATA_KEY} must be a mapping"
        )
    if not _is_str_object_mapping(rerank_reason_raw):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{RERANK_REASON_METADATA_KEY} must be a mapping"
        )

    static_score = dict(static_score_raw)
    final_score = dict(final_score_raw)
    runtime_adjustment = dict(runtime_adjustment_raw)
    rerank_reason = dict(rerank_reason_raw)

    static_value = _coerce_float(
        static_score.get("value"),
        field_name=f"{candidate_id}.metadata.{STATIC_SCORE_METADATA_KEY}.value",
    )
    final_value = _coerce_float(
        final_score.get("value"),
        field_name=f"{candidate_id}.metadata.{FINAL_SCORE_METADATA_KEY}.value",
    )
    adjustment_value = _coerce_float(
        runtime_adjustment.get("value"),
        field_name=f"{candidate_id}.metadata.{RUNTIME_ADJUSTMENT_METADATA_KEY}.value",
    )
    overall = _coerce_float(
        candidate.score_breakdown.get("overall"),
        field_name=f"{candidate_id}.score_breakdown.overall",
    )
    if not math.isclose(static_value, overall, rel_tol=1e-6, abs_tol=1e-6):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{STATIC_SCORE_METADATA_KEY}.value must match score_breakdown.overall"
        )
    if not math.isclose(
        final_value,
        max(0.0, min(1.0, static_value + adjustment_value)),
        rel_tol=1e-6,
        abs_tol=1e-6,
    ):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{FINAL_SCORE_METADATA_KEY}.value must equal clip(static_score + runtime_adjustment, 0, 1)"
        )

    action_score_raw = metadata.get(ACTION_SCORE_METADATA_KEY)
    if _is_str_object_mapping(action_score_raw):
        action_score = dict(action_score_raw)
        action_value = _coerce_float(
            action_score.get("value"),
            field_name=f"{candidate_id}.metadata.{ACTION_SCORE_METADATA_KEY}.value",
        )
        if not math.isclose(action_value, static_value, rel_tol=1e-6, abs_tol=1e-6):
            raise CandidateSetValidationError(
                f"{candidate_id}.metadata.{ACTION_SCORE_METADATA_KEY}.value must match static_score.value"
            )

    shadow_score_raw = metadata.get(SHADOW_SCORE_METADATA_KEY)
    if _is_str_object_mapping(shadow_score_raw):
        shadow_score = dict(shadow_score_raw)
        shadow_value = _coerce_float(
            shadow_score.get("value"),
            field_name=f"{candidate_id}.metadata.{SHADOW_SCORE_METADATA_KEY}.value",
        )
        if not math.isclose(shadow_value, final_value, rel_tol=1e-6, abs_tol=1e-6):
            raise CandidateSetValidationError(
                f"{candidate_id}.metadata.{SHADOW_SCORE_METADATA_KEY}.value must match final_score.value"
            )

    if not isinstance(runtime_adjustment.get("shadow_only"), bool):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{RUNTIME_ADJUSTMENT_METADATA_KEY}.shadow_only must be a boolean"
        )
    if not isinstance(rerank_reason.get("shadow_only"), bool):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{RERANK_REASON_METADATA_KEY}.shadow_only must be a boolean"
        )
    if not rerank_reason.get("message"):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{RERANK_REASON_METADATA_KEY}.message is required"
        )
    if abs(adjustment_value) > 1e-9 and not rerank_reason.get("runtime_state_fields"):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.{RERANK_REASON_METADATA_KEY}.runtime_state_fields is required when runtime_adjustment is non-zero"
        )


def _coerce_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise CandidateSetValidationError(f"{field_name} must be numeric")
    if not isinstance(value, (int, float, str)):
        raise CandidateSetValidationError(f"{field_name} must be numeric")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise CandidateSetValidationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise CandidateSetValidationError(f"{field_name} must be finite")
    return parsed


def _validate_candidate_s5_fields(
    candidate: PendingActionCandidate,
    candidate_id: str,
) -> None:
    metadata = _as_json_map(candidate.metadata)
    contract_raw = metadata.get("s5_contract")
    if not _is_str_object_mapping(contract_raw):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract is required"
        )
    contract = dict(contract_raw)

    if contract.get("stage_id") != "S5":
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.stage_id must be S5"
        )
    if contract.get("stage_name") != "objective_scoring":
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.stage_name must be objective_scoring"
        )

    field_order_raw = contract.get("field_order")
    if not _is_str_object_mapping(field_order_raw):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.field_order is required"
        )
    field_order = dict(field_order_raw)
    input_fields = _as_str_list(field_order.get("inputs"))
    output_fields = _as_str_list(field_order.get("outputs"))
    if not REQUIRED_S5_INPUT_FIELDS.issubset(set(input_fields)):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.field_order.inputs missing required fields"
        )
    if not REQUIRED_S5_OUTPUT_FIELDS.issubset(set(output_fields)):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.field_order.outputs missing required fields"
        )

    declared_inputs_raw = contract.get("inputs")
    declared_outputs_raw = contract.get("outputs")
    if not _is_str_object_mapping(
        declared_inputs_raw
    ) or not REQUIRED_S5_INPUT_FIELDS.issubset(set(declared_inputs_raw)):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.inputs missing required fields"
        )
    if not _is_str_object_mapping(
        declared_outputs_raw
    ) or not REQUIRED_S5_OUTPUT_FIELDS.issubset(set(declared_outputs_raw)):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.outputs missing required fields"
        )

    weights_raw = contract.get("weights")
    if not _is_str_object_mapping(weights_raw):
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.weights is required"
        )
    weights = dict(weights_raw)
    missing_weights = REQUIRED_S5_WEIGHT_FIELDS - set(weights)
    if missing_weights:
        missing = ", ".join(sorted(missing_weights))
        raise CandidateSetValidationError(
            f"{candidate_id}.metadata.s5_contract.weights missing keys: {missing}"
        )
    for key in REQUIRED_S5_WEIGHT_FIELDS:
        value = weights.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            raise CandidateSetValidationError(
                f"{candidate_id}.metadata.s5_contract.weights.{key} must be > 0"
            )


def validate_decision_for_pending_action(
    pending_action: PendingAction,
    decision: Decision,
) -> None:
    """验证 Decision 是否可用于驱动 PendingAction。

    Args:
        pending_action: 待校验的 PendingAction。
        decision: 人工提交的 Decision。

    Raises:
        DecisionValidationError: 当 choice 非法、accept 缺少候选 ID，或候选不在列表中。
    """
    allowed_choices = ALLOWED_DECISION_CHOICES.get(pending_action.action_type)
    if allowed_choices is None:
        raise DecisionValidationError(
            f"Unsupported pending action type: {pending_action.action_type.value}"
        )
    if decision.choice not in allowed_choices:
        raise DecisionValidationError(
            f"Choice {decision.choice.value} is not allowed for "
            + f"{pending_action.action_type.value}"
        )
    if decision.choice == DecisionChoice.ACCEPT:
        if not decision.selected_candidate_id:
            raise DecisionValidationError(
                "selected_candidate_id is required for accept"
            )
        candidate = find_pending_action_candidate(
            pending_action,
            decision.selected_candidate_id,
        )
        if candidate is None:
            raise DecisionValidationError("selected_candidate_id is not in candidates")


def find_pending_action_candidate(
    pending_action: PendingAction,
    candidate_id: str,
) -> PendingActionCandidate | None:
    """在 PendingAction.candidates 中查找指定候选。

    Args:
        pending_action: 含候选列表的 PendingAction。
        candidate_id: 目标候选 ID。

    Returns:
        匹配的候选对象，未找到则返回 None。
    """
    for candidate in pending_action.candidates:
        resolved_id = _resolve_candidate_id(candidate)
        if resolved_id == candidate_id:
            return candidate
    return None


def _resolve_candidate_id(
    candidate: PendingActionCandidate,
) -> str | None:
    """兼容不同字段命名以解析候选 ID。

    Args:
        candidate: 候选对象。

    Returns:
        候选 ID；若字段缺失则返回 None。
    """
    candidate_id = getattr(candidate, "candidate_id", None)
    if isinstance(candidate_id, str):
        return candidate_id
    fallback_id = getattr(candidate, "id", None)
    if isinstance(fallback_id, str):
        return fallback_id
    return None


def validate_plan_executability(
    plan: Plan,
    task: ProteinDesignTask,
    *,
    candidate: PendingActionCandidate | None = None,
    kg_loader: KgLoader | None = None,
    adapter_resolver: Callable[[str], object] | None = None,
) -> None:
    """执行前候选可执行性硬约束校验。

    校验项:
    - 工具存在性（ToolKG 或 AdapterRegistry）
    - capability/io_type 白名单与语义一致性
    - adapter 接入方式（python/nextflow/external_api/remote_model_service）
    - I/O 闭包（引用必须可由上游产出）
    - 参数合法性与基础资源约束（类型、长度、候选数）
    """

    _ = task
    kg_loader = kg_loader or load_tool_kg
    adapter_resolver = adapter_resolver or get_adapter

    issues: list[CandidateExecutionIssue] = []
    try:
        kg = kg_loader()
    except ToolKGError as exc:
        raise CandidateExecutionValidationError(
            [
                CandidateExecutionIssue(
                    code="CANDIDATE_SCHEMA_INVALID",
                    message=f"ProteinToolKG is unavailable: {exc}",
                    details={"error": str(exc)},
                )
            ]
        ) from exc

    tool_by_id: dict[str, JsonMap] = {}
    for tool in _as_json_map_list(kg.get("tools")):
        tool_id = tool.get("id")
        if isinstance(tool_id, str) and tool_id:
            tool_by_id[tool_id] = tool
    capability_ids = {
        capability_id
        for entry in _as_json_map_list(kg.get(("capabilities")))
        if isinstance((capability_id := entry.get("capability_id")), str)
    }
    io_type_ids = {
        io_type_id
        for entry in _as_json_map_list(kg.get("io_types"))
        if isinstance((io_type_id := entry.get("io_type_id")), str)
    }

    if candidate is not None:
        _validate_candidate_tool_metadata(
            candidate=candidate,
            tool_by_id=tool_by_id,
            capability_ids=capability_ids,
            io_type_ids=io_type_ids,
            adapter_resolver=adapter_resolver,
            issues=issues,
        )

    produced_outputs_by_step: dict[str, set[str]] = {}
    step_index = {step.id: idx for idx, step in enumerate(plan.steps)}

    for idx, step in enumerate(plan.steps):
        step_tool = tool_by_id.get(step.tool)
        if step_tool is None:
            if not _has_adapter(step.tool, adapter_resolver):
                issues.append(
                    CandidateExecutionIssue(
                        code="CANDIDATE_TOOL_UNAVAILABLE",
                        message=f"tool '{step.tool}' is not found in ToolKG or adapter registry",
                        step_id=step.id,
                        tool_id=step.tool,
                    )
                )
            _validate_step_references(
                step=step,
                step_index=step_index,
                current_idx=idx,
                produced_outputs_by_step=produced_outputs_by_step,
                issues=issues,
            )
            produced_outputs_by_step[step.id] = _extract_fallback_outputs(step)
            continue

        capability_id = _primary_capability(step_tool)
        io_type = _tool_io_type(step_tool)
        backend = _resolve_execution_backend(step_tool.get("execution"))
        if backend is None or backend not in ALLOWED_EXECUTION_BACKENDS:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_ADAPTER_UNSUPPORTED",
                    message=(
                        f"tool '{step.tool}' uses unsupported execution backend "
                        f"'{backend}'"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                )
            )
        if not _has_adapter(step.tool, adapter_resolver):
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_TOOL_UNAVAILABLE",
                    message=f"tool '{step.tool}' has no registered adapter",
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                )
            )

        io_config = _as_json_map(step_tool.get("io"))
        declared_inputs = _as_json_map(io_config.get("inputs"))
        for key, expected_type in declared_inputs.items():
            if key not in step.inputs:
                issues.append(
                    CandidateExecutionIssue(
                        code="CANDIDATE_PARAMS_INVALID",
                        message=f"required input '{key}' is missing",
                        step_id=step.id,
                        tool_id=step.tool,
                        capability_id=capability_id,
                        io_type=io_type,
                    )
                )
                continue
            _validate_input_value(
                step=step,
                key=key,
                value=step.inputs[key],
                expected_type=expected_type,
                step_index=step_index,
                current_idx=idx,
                produced_outputs_by_step=produced_outputs_by_step,
                capability_id=capability_id,
                io_type=io_type,
                issues=issues,
            )

        for key, value in step.inputs.items():
            if key in declared_inputs:
                continue
            _validate_optional_params(
                step,
                key,
                value,
                capability_id=capability_id,
                io_type=io_type,
                issues=issues,
            )

        _validate_resource_limits(
            step=step,
            step_tool=step_tool,
            capability_id=capability_id,
            io_type=io_type,
            issues=issues,
        )

        produced_outputs = _extract_declared_outputs(step_tool)
        produced_outputs_by_step[step.id] = produced_outputs

    if issues:
        raise CandidateExecutionValidationError(issues)


def _validate_candidate_tool_metadata(
    *,
    candidate: PendingActionCandidate,
    tool_by_id: dict[str, JsonMap],
    capability_ids: set[str],
    io_type_ids: set[str],
    adapter_resolver: Callable[[str], object],
    issues: list[CandidateExecutionIssue],
) -> None:
    tool_id = candidate.tool_id
    capability_id = candidate.capability_id
    io_type = candidate.io_type

    if capability_id and capability_id not in capability_ids:
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_SCHEMA_INVALID",
                message=f"capability_id '{capability_id}' is not in ToolKG",
                tool_id=tool_id,
                capability_id=capability_id,
                io_type=io_type,
            )
        )
    if io_type and io_type not in io_type_ids:
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_SCHEMA_INVALID",
                message=f"io_type '{io_type}' is not in ToolKG",
                tool_id=tool_id,
                capability_id=capability_id,
                io_type=io_type,
            )
        )

    if tool_id is None:
        return

    tool = tool_by_id.get(tool_id)
    if tool is None and not _has_adapter(tool_id, adapter_resolver):
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_TOOL_UNAVAILABLE",
                message=f"candidate tool '{tool_id}' is not available",
                tool_id=tool_id,
                capability_id=capability_id,
                io_type=io_type,
            )
        )
        return
    if tool is None:
        return

    capabilities = tool.get("capabilities", [])
    if capability_id and (
        not isinstance(capabilities, list) or capability_id not in capabilities
    ):
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_SCHEMA_INVALID",
                message=(
                    f"capability_id '{capability_id}' does not match tool '{tool_id}'"
                ),
                tool_id=tool_id,
                capability_id=capability_id,
                io_type=io_type,
            )
        )
    tool_io_type: str | None = None
    io_config = _as_json_map((tool.get("io")))
    resolved = io_config.get("io_type_id")
    if isinstance(resolved, str) and resolved:
        tool_io_type = resolved
    if io_type and tool_io_type and io_type != tool_io_type:
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_SCHEMA_INVALID",
                message=f"io_type '{io_type}' does not match tool '{tool_id}'",
                tool_id=tool_id,
                capability_id=capability_id,
                io_type=io_type,
            )
        )

    backend = _resolve_execution_backend(tool.get("execution"))
    if backend is None or backend not in ALLOWED_EXECUTION_BACKENDS:
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_ADAPTER_UNSUPPORTED",
                message=(
                    f"tool '{tool_id}' uses unsupported execution backend '{backend}'"
                ),
                tool_id=tool_id,
                capability_id=capability_id,
                io_type=io_type,
            )
        )


def _validate_input_value(
    *,
    step: PlanStep,
    key: str,
    value: object,
    expected_type: object,
    step_index: dict[str, int],
    current_idx: int,
    produced_outputs_by_step: dict[str, set[str]],
    capability_id: str | None,
    io_type: str | None,
    issues: list[CandidateExecutionIssue],
) -> None:
    reference = _parse_step_reference(value)
    if reference is not None:
        ref_step_id, ref_field = reference
        ref_idx = step_index.get(ref_step_id)
        if ref_idx is None or ref_idx >= current_idx:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_IO_CLOSURE_BROKEN",
                    message=(
                        f"input '{key}' references '{value}' which is not from an "
                        "upstream step"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                    details={"input_key": key, "reference": value},
                )
            )
            return

        produced = produced_outputs_by_step.get(ref_step_id, set())
        if produced and ref_field not in produced:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_IO_CLOSURE_BROKEN",
                    message=(
                        f"input '{key}' references '{value}' but field '{ref_field}' "
                        f"is not produced by step '{ref_step_id}'"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                    details={"input_key": key, "reference": value},
                )
            )
        return

    if not _matches_expected_type(value, expected_type):
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_PARAMS_INVALID",
                message=(
                    f"input '{key}' has invalid type for expected '{expected_type}'"
                ),
                step_id=step.id,
                tool_id=step.tool,
                capability_id=capability_id,
                io_type=io_type,
                details={"input_key": key, "expected_type": expected_type},
            )
        )

    _validate_optional_params(
        step,
        key,
        value,
        capability_id=capability_id,
        io_type=io_type,
        issues=issues,
    )


def _validate_step_references(
    *,
    step: PlanStep,
    step_index: dict[str, int],
    current_idx: int,
    produced_outputs_by_step: dict[str, set[str]],
    issues: list[CandidateExecutionIssue],
) -> None:
    for key, value in step.inputs.items():
        reference = _parse_step_reference(value)
        if reference is None:
            continue
        ref_step_id, ref_field = reference
        ref_idx = step_index.get(ref_step_id)
        if ref_idx is None or ref_idx >= current_idx:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_IO_CLOSURE_BROKEN",
                    message=(
                        f"input '{key}' references '{value}' which is not from an "
                        "upstream step"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    details={"input_key": key, "reference": value},
                )
            )
            continue
        produced = produced_outputs_by_step.get(ref_step_id, set())
        if produced and ref_field not in produced:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_IO_CLOSURE_BROKEN",
                    message=(
                        f"input '{key}' references '{value}' but field '{ref_field}' "
                        f"is not produced by step '{ref_step_id}'"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    details={"input_key": key, "reference": value},
                )
            )


def _validate_optional_params(
    step: PlanStep,
    key: str,
    value: object,
    *,
    capability_id: str | None,
    io_type: str | None,
    issues: list[CandidateExecutionIssue],
) -> None:
    if key == "length_range":
        invalid = True

        if isinstance(value, (list, tuple)):
            length_range = cast(list[object] | tuple[object, ...], value)
            if len(length_range) == 2:
                min_len = length_range[0]
                max_len = length_range[1]
                invalid = (
                    not isinstance(min_len, int)
                    or isinstance(min_len, bool)
                    or not isinstance(max_len, int)
                    or isinstance(max_len, bool)
                    or min_len <= 0
                    or max_len <= 0
                    or min_len > max_len
                )
        if invalid:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_PARAMS_INVALID",
                    message="length_range must be [min_len, max_len] with positive integers",
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                    details={"input_key": key},
                )
            )
    if key == "num_candidates":
        if not isinstance(value, int) or value <= 0:
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_PARAMS_INVALID",
                    message="num_candidates must be a positive integer",
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                    details={"input_key": key},
                )
            )


def _validate_resource_limits(
    *,
    step: PlanStep,
    step_tool: JsonMap,
    capability_id: str | None,
    io_type: str | None,
    issues: list[CandidateExecutionIssue],
) -> None:
    constraints = _as_json_map(step_tool.get("constraints"))
    limits = _as_json_map(constraints.get("limits"))
    if not limits:
        return

    max_length = limits.get("max_length")
    if isinstance(max_length, (int, float)) and max_length > 0:
        sequence = step.inputs.get("sequence")
        if isinstance(sequence, str) and _parse_step_reference(sequence) is None:
            if len(sequence) > int(max_length):
                issues.append(
                    CandidateExecutionIssue(
                        code="CANDIDATE_RESOURCE_CONSTRAINT",
                        message=(
                            f"sequence length {len(sequence)} exceeds tool limit "
                            f"{int(max_length)}"
                        ),
                        step_id=step.id,
                        tool_id=step.tool,
                        capability_id=capability_id,
                        io_type=io_type,
                        details={"limit": "max_length", "value": len(sequence)},
                    )
                )

        length_range = step.inputs.get("length_range")
        length_upper_bound: int | None = None
        if isinstance(length_range, (list, tuple)):
            length_range_items = cast(list[object] | tuple[object, ...], length_range)
            if len(length_range_items) == 2:
                upper_bound = length_range_items[1]
                if isinstance(upper_bound, int) and not isinstance(upper_bound, bool):
                    length_upper_bound = upper_bound
        if length_upper_bound is not None and length_upper_bound > int(max_length):
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_RESOURCE_CONSTRAINT",
                    message=(
                        f"length_range upper bound {length_upper_bound} exceeds "
                        f"tool limit {int(max_length)}"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                    details={"limit": "max_length", "value": length_upper_bound},
                )
            )

    max_candidates = limits.get("num_candidates_max")
    num_candidates = step.inputs.get("num_candidates")
    if (
        isinstance(max_candidates, (int, float))
        and max_candidates > 0
        and isinstance(num_candidates, int)
        and num_candidates > int(max_candidates)
    ):
        issues.append(
            CandidateExecutionIssue(
                code="CANDIDATE_RESOURCE_CONSTRAINT",
                message=(
                    f"num_candidates {num_candidates} exceeds tool limit "
                    f"{int(max_candidates)}"
                ),
                step_id=step.id,
                tool_id=step.tool,
                capability_id=capability_id,
                io_type=io_type,
                details={"limit": "num_candidates_max", "value": num_candidates},
            )
        )


def _extract_declared_outputs(step_tool: JsonMap) -> set[str]:
    io_config = _as_json_map(step_tool.get("io"))
    outputs = _as_json_map(io_config.get("outputs"))
    result: set[str] = set()
    result.update(outputs)
    result.update(_as_str_list(io_config.get("output_types")))
    return result


def _extract_fallback_outputs(step: PlanStep) -> set[str]:
    metadata = step.metadata
    output_types = _as_json_map(metadata.get("output_types"))
    if output_types:
        return set(output_types)
    required_outputs = _as_str_list(metadata.get("required_outputs"))
    if required_outputs:
        return set(required_outputs)
    return set()


def _resolve_execution_backend(execution: object) -> str | None:
    if isinstance(execution, str):
        return execution
    execution_map = _as_json_map(execution)
    backend = execution_map.get("backend")
    if isinstance(backend, str):
        return backend
    return None


def _primary_capability(step_tool: JsonMap) -> str | None:
    capabilities = step_tool.get("capabilities")
    if not isinstance(capabilities, list):
        return None
    items = cast(list[object], capabilities)
    for capability in items:
        if isinstance(capability, str) and capability:
            return capability
    return None


def _tool_io_type(step_tool: JsonMap) -> str | None:
    io_config = _as_json_map(step_tool.get("io"))
    io_type = io_config.get("io_type_id")
    if isinstance(io_type, str) and io_type:
        return io_type
    return None


def _parse_step_reference(value: object) -> tuple[str, str] | None:
    if not isinstance(value, str) or "." not in value:
        return None
    step_id, field = value.split(".", 1)
    if not step_id.startswith(REFERENCE_PREFIX):
        return None
    if len(step_id) <= 1 or not step_id[1:].isdigit() or not field:
        return None
    return step_id, field


def _matches_expected_type(value: object, expected_type: object) -> bool:
    if not isinstance(expected_type, str):
        return True
    expected = expected_type.strip().lower()
    if expected in {"path", "str", "string"}:
        return isinstance(value, str)
    if expected in {"int", "integer"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in {"float", "number"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected in {"bool", "boolean"}:
        return isinstance(value, bool)
    if expected in {"list", "array"}:
        return isinstance(value, list)
    if expected in {"dict", "object", "map"}:
        return isinstance(value, dict)
    return True


def _has_adapter(
    tool_id: str,
    adapter_resolver: Callable[[str], object],
) -> bool:
    try:
        _ = adapter_resolver(tool_id)
    except Exception:
        return False
    return True
