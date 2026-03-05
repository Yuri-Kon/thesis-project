from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.models.contracts import (Decision, DecisionChoice, PendingAction,
                                  PendingActionCandidate, PendingActionType,
                                  Plan, PlanStep, ProteinDesignTask)
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


class DecisionValidationError(ValueError):
    """Decision 与 PendingAction 约束冲突时抛出。"""


class CandidateSetValidationError(ValueError):
    """CandidateSetOutput 契约校验失败时抛出。"""


REQUIRED_SCORE_BREAKDOWN_FIELDS = frozenset(
    {"feasibility", "objective", "risk", "cost", "overall"}
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
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
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
        self.issues = list(issues)
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

    default_id = (
        pending_action.default_recommendation or pending_action.default_suggestion
    )
    if require_default_recommendation and not default_id:
        raise CandidateSetValidationError(
            "default_recommendation is required for candidate set output"
        )
    if default_id and default_id not in seen_ids:
        raise CandidateSetValidationError(
            "default_recommendation is not in candidates"
        )


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
        raise CandidateSetValidationError(
            f"{candidate_id}.capability_id is required"
        )
    if candidate.io_type is None:
        raise CandidateSetValidationError(f"{candidate_id}.io_type is required")
    if candidate.adapter_mode is None:
        raise CandidateSetValidationError(f"{candidate_id}.adapter_mode is required")

    metadata = candidate.metadata or {}
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
            f"{pending_action.action_type.value}"
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
) -> Optional[PendingActionCandidate]:
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
) -> Optional[str]:
    """兼容不同字段命名以解析候选 ID。

    Args:
        candidate: 候选对象。

    Returns:
        候选 ID；若字段缺失则返回 None。
    """
    candidate_id = getattr(candidate, "candidate_id", None)
    if candidate_id is not None:
        return candidate_id
    return getattr(candidate, "id", None)


def validate_plan_executability(
    plan: Plan,
    task: ProteinDesignTask,
    *,
    candidate: PendingActionCandidate | None = None,
    kg_loader: Callable[[], dict] | None = None,
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

    tools = kg.get("tools", [])
    tool_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(tools, list):
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_id = tool.get("id")
            if isinstance(tool_id, str) and tool_id:
                tool_by_id[tool_id] = tool

    capability_ids = {
        entry.get("capability_id")
        for entry in kg.get("capabilities", [])
        if isinstance(entry, dict) and isinstance(entry.get("capability_id"), str)
    }
    io_type_ids = {
        entry.get("io_type_id")
        for entry in kg.get("io_types", [])
        if isinstance(entry, dict) and isinstance(entry.get("io_type_id"), str)
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

        io_config = step_tool.get("io", {})
        if not isinstance(io_config, dict):
            io_config = {}
        declared_inputs = io_config.get("inputs", {})
        if not isinstance(declared_inputs, dict):
            declared_inputs = {}

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
    tool_by_id: dict[str, dict[str, Any]],
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
    if capability_id and (not isinstance(capabilities, list) or capability_id not in capabilities):
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
    tool_io_type = None
    io_config = tool.get("io", {})
    if isinstance(io_config, dict):
        resolved = io_config.get("io_type_id")
        if isinstance(resolved, str):
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
                    f"tool '{tool_id}' uses unsupported execution backend "
                    f"'{backend}'"
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
    value: Any,
    expected_type: Any,
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
    value: Any,
    *,
    capability_id: str | None,
    io_type: str | None,
    issues: list[CandidateExecutionIssue],
) -> None:
    if key == "length_range":
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or not all(isinstance(v, int) and v > 0 for v in value)
            or value[0] > value[1]
        ):
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
    step_tool: dict[str, Any],
    capability_id: str | None,
    io_type: str | None,
    issues: list[CandidateExecutionIssue],
) -> None:
    constraints = step_tool.get("constraints", {})
    if not isinstance(constraints, dict):
        return
    limits = constraints.get("limits", {})
    if not isinstance(limits, dict):
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
        if (
            isinstance(length_range, (list, tuple))
            and len(length_range) == 2
            and all(isinstance(v, int) for v in length_range)
            and length_range[1] > int(max_length)
        ):
            issues.append(
                CandidateExecutionIssue(
                    code="CANDIDATE_RESOURCE_CONSTRAINT",
                    message=(
                        f"length_range upper bound {length_range[1]} exceeds "
                        f"tool limit {int(max_length)}"
                    ),
                    step_id=step.id,
                    tool_id=step.tool,
                    capability_id=capability_id,
                    io_type=io_type,
                    details={"limit": "max_length", "value": length_range[1]},
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


def _extract_declared_outputs(step_tool: dict[str, Any]) -> set[str]:
    io_config = step_tool.get("io", {})
    if not isinstance(io_config, dict):
        return set()
    outputs = io_config.get("outputs", {})
    result: set[str] = set()
    if isinstance(outputs, dict):
        result.update(key for key in outputs if isinstance(key, str))
    output_types = io_config.get("output_types", [])
    if isinstance(output_types, list):
        result.update(key for key in output_types if isinstance(key, str))
    return result


def _extract_fallback_outputs(step: PlanStep) -> set[str]:
    metadata = step.metadata if isinstance(step.metadata, dict) else {}
    output_types = metadata.get("output_types", {})
    if isinstance(output_types, dict):
        return {key for key in output_types if isinstance(key, str)}
    required_outputs = metadata.get("required_outputs", [])
    if isinstance(required_outputs, list):
        return {key for key in required_outputs if isinstance(key, str)}
    return set()


def _resolve_execution_backend(execution: Any) -> str | None:
    if isinstance(execution, str):
        return execution
    if isinstance(execution, dict):
        backend = execution.get("backend")
        if isinstance(backend, str):
            return backend
    return None


def _primary_capability(step_tool: dict[str, Any]) -> str | None:
    capabilities = step_tool.get("capabilities", [])
    if isinstance(capabilities, list):
        for capability in capabilities:
            if isinstance(capability, str) and capability:
                return capability
    return None


def _tool_io_type(step_tool: dict[str, Any]) -> str | None:
    io_config = step_tool.get("io", {})
    if isinstance(io_config, dict):
        io_type = io_config.get("io_type_id")
        if isinstance(io_type, str) and io_type:
            return io_type
    return None


def _parse_step_reference(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str) or "." not in value:
        return None
    step_id, field = value.split(".", 1)
    if not step_id.startswith(REFERENCE_PREFIX):
        return None
    if len(step_id) <= 1 or not step_id[1:].isdigit() or not field:
        return None
    return step_id, field


def _matches_expected_type(value: Any, expected_type: Any) -> bool:
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
        adapter_resolver(tool_id)
    except Exception:
        return False
    return True
