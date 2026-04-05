"""
workflow/recovery.py

Snapshot-based recovery logic for resuming interrupted tasks.

职责概述：
- 从快照恢复 WorkflowContext
- 提取远程作业上下文并支持继续执行
- 与 PlanRunner.run_plan(resume_from_existing=True) 协同
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from src.models.contracts import (
    PendingAction,
    PendingActionCandidate,
    Plan,
    PlanStep,
    ProteinDesignTask,
    RUNTIME_OBSERVATION_SUMMARY_ARTIFACT_KEY,
    RUNTIME_STATE_ARTIFACT_KEY,
    RuntimeState,
    StepResult,
    TaskSnapshot,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus
from src.models.event_log import EventLog, EventType
from src.storage.log_store import DEFAULT_LOG_DIR, read_event_logs
from src.storage.snapshot_store import read_latest_snapshot, DEFAULT_SNAPSHOT_DIR
from src.workflow.belief_state import update_runtime_state
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType
from src.workflow.runtime_policy import (
    DYNAMIC_OBSERVATION_ONLY_POLICY,
    resolve_runtime_policy,
)

__all__ = [
    "restore_context_from_snapshot",
    "recover_context_with_event_logs",
    "extract_remote_job_context",
    "RemoteJobContext",
    "RecoveryResult",
    "StructureRefinementIteration",
    "build_structure_refinement_audit",
    "persist_structure_refinement_audit",
    "S6_TRIGGER_MATRIX_VERSION",
    "get_s6_trigger_matrix",
    "WorkflowActionSelectorInput",
    "WorkflowActionSelectorResult",
    "WorkflowActionRoute",
    "select_workflow_action",
    "resolve_s6_recovery_action",
    "resolve_workflow_action_route",
    "build_terminal_stop_candidate",
    "extract_candidate_recovery_metadata",
    "is_terminal_stop_candidate",
    "resolve_terminal_stop_reason",
]

S6_TRIGGER_MATRIX_VERSION = "2026-03-16.v1"
_S6_STAGE_TRIGGER_MATRIX: dict[str, dict[str, Any]] = {
    "S1": {
        "default_action": "patch",
        "replan_failure_prefixes": ["SAFETY_"],
    },
    "S2": {
        "default_action": "patch",
        "replan_failure_prefixes": ["S2_ALL_", "S2_IO_"],
    },
    "S3": {
        "default_action": "replan",
        "replan_failure_prefixes": ["S3_"],
    },
    "S4": {
        "default_action": "patch",
        "replan_failure_prefixes": ["S4_LOOP_EXHAUSTED"],
    },
    "S5": {
        "default_action": "patch",
        "replan_failure_prefixes": ["S5_OBJECTIVE_NOT_MET", "S5_SCORE_INVALID"],
    },
}

_TERMINAL_STOP_REASON_BY_FAILURE_TYPE = {
    FailureType.SAFETY_BLOCK: "unsafe_to_continue",
    FailureType.TOOL_ERROR: "recovery_exhausted",
    FailureType.NON_RETRYABLE: "evidence_exhausted",
    FailureType.RETRYABLE: "economic_stop",
}

_PHASE_ALLOWED_ACTIONS: dict[str, frozenset[str]] = {
    "execution": frozenset({"continue", "patch_local", "suffix_replan", "stop"}),
    "patch": frozenset({"patch_local", "suffix_replan", "stop"}),
    "replan": frozenset({"continue", "suffix_replan", "stop"}),
}


@dataclass(frozen=True)
class WorkflowActionRoute:
    """统一动作到既有 recovery 闭环的映射。"""

    action: str
    mapped_flow: str
    waiting_status: InternalStatus | None = None
    terminal_policy: str | None = None
    terminal_status: InternalStatus | None = None


_WORKFLOW_ACTION_ROUTES: dict[str, WorkflowActionRoute] = {
    "continue": WorkflowActionRoute(
        action="continue",
        mapped_flow="continue",
    ),
    "patch_local": WorkflowActionRoute(
        action="patch_local",
        mapped_flow="patch",
    ),
    "suffix_replan": WorkflowActionRoute(
        action="suffix_replan",
        mapped_flow="replan",
        waiting_status=InternalStatus.WAITING_REPLAN,
    ),
    "stop": WorkflowActionRoute(
        action="stop",
        mapped_flow="stop",
        waiting_status=InternalStatus.WAITING_REPLAN,
        terminal_policy="stop",
        terminal_status=InternalStatus.FAILED,
    ),
}


def get_s6_trigger_matrix() -> dict[str, Any]:
    """返回 S6 阶段感知触发矩阵（用于审计与文档）。"""
    return {
        "version": S6_TRIGGER_MATRIX_VERSION,
        "stages": json.loads(json.dumps(_S6_STAGE_TRIGGER_MATRIX, ensure_ascii=True)),
    }


@dataclass(frozen=True)
class WorkflowActionSelectorInput:
    """统一动作选择器输入契约。"""

    phase: str = "execution"
    stage_id: str | None = None
    failure_code: str | None = None
    failure_type: FailureType | str | None = None
    retry_exhausted: bool = False
    safety_blocked: bool = False
    runtime_state_summary: dict[str, Any] | None = None
    suggested_action: str | None = None
    suggested_reason: str | None = None
    runtime_policy: str | None = None


@dataclass(frozen=True)
class WorkflowActionSelectorResult:
    """动作选择器输出契约。"""

    action: str
    mapped_flow: str
    reason: str
    evidence_source: dict[str, Any]


def resolve_workflow_action_route(action: str) -> WorkflowActionRoute:
    """返回统一动作的 recovery 映射信息。"""

    normalized = _normalize_workflow_action(action)
    if normalized is None:
        raise ValueError(f"Unsupported workflow action: {action}")
    return _WORKFLOW_ACTION_ROUTES[normalized]


def select_workflow_action(
    selector_input: WorkflowActionSelectorInput,
) -> WorkflowActionSelectorResult:
    """根据失败上下文与 runtime_state 选择既有 Workflow 的下一步动作。"""

    phase = _normalize_selector_phase(selector_input.phase)
    allowed_actions = _PHASE_ALLOWED_ACTIONS[phase]
    suggested_action = _normalize_workflow_action(selector_input.suggested_action)
    if suggested_action not in allowed_actions:
        suggested_action = None
    runtime_policy = resolve_runtime_policy(
        {"runtime_policy": selector_input.runtime_policy}
    )
    observation_only = runtime_policy == DYNAMIC_OBSERVATION_ONLY_POLICY

    runtime_summary = _normalize_runtime_state_summary(
        selector_input.runtime_state_summary
    )
    p_success = _safe_float(runtime_summary.get("p_success"), default=0.5)
    p_structural_failure = _safe_float(
        runtime_summary.get("p_structural_failure"),
        default=0.25,
    )
    recovery_margin = _safe_float(
        runtime_summary.get("recovery_margin"),
        default=0.6,
    )
    expected_remaining_cost = _safe_float(
        runtime_summary.get("expected_remaining_cost"),
        default=1.0,
    )
    cost_pressure = min(max(expected_remaining_cost, 0.0) / 5.0, 1.0)
    budget_pressure = _safe_float(
        runtime_summary.get("budget_pressure"),
        default=cost_pressure,
    )
    intervention_value = _safe_float(
        runtime_summary.get("intervention_value"),
        default=1.0,
    )
    prefix_preservability = _safe_optional_float(
        runtime_summary.get("prefix_preservability")
    )
    local_patchability = _safe_optional_float(
        runtime_summary.get("local_patchability")
    )
    u_stop = _safe_float(runtime_summary.get("u_stop"), default=0.0)
    allow_auto_stop = _safe_bool(
        runtime_summary.get("allow_auto_stop"),
        default=False,
    )

    normalized_failure_type = _normalize_failure_type(selector_input.failure_type)
    normalized_failure_code = _normalize_text(selector_input.failure_code)
    normalized_stage_id = _normalize_text(selector_input.stage_id)
    has_failure_signal = (
        normalized_failure_type is not None
        or normalized_failure_code is not None
        or bool(selector_input.retry_exhausted)
        or bool(selector_input.safety_blocked)
    )
    s6_default_action = resolve_s6_recovery_action(
        stage_id=normalized_stage_id,
        failure_code=normalized_failure_code,
        failure_type=normalized_failure_type,
        retry_exhausted=bool(selector_input.retry_exhausted),
        safety_blocked=bool(selector_input.safety_blocked),
    )

    if (
        selector_input.safety_blocked
        and "suffix_replan" in allowed_actions
        and not _should_choose_stop(
            allowed_actions=allowed_actions,
            allow_auto_stop=allow_auto_stop,
            u_stop=u_stop,
            p_success=p_success,
            budget_pressure=budget_pressure,
            recovery_margin=recovery_margin,
            intervention_value=intervention_value,
        )
    ):
        action = "suffix_replan"
        reason = "safety block disables continue and escalates to suffix replan"
        basis = "hard_priority"
    elif suggested_action is not None and not _is_hard_blocked_suggestion(
        suggested_action=suggested_action,
        safety_blocked=bool(selector_input.safety_blocked),
    ):
        action = suggested_action
        reason = selector_input.suggested_reason or (
            f"candidate/runtime suggestion selected {suggested_action}"
        )
        basis = "suggested_action"
    elif not has_failure_signal:
        action = "continue"
        if observation_only:
            reason = (
                "observation-only runtime policy saw no failure or safety signal "
                "in the current execution step"
            )
            basis = "observation_only"
        else:
            reason = "no failure or safety signal is present in the current execution step"
            basis = "default_continue"
    elif _should_choose_stop(
        allowed_actions=allowed_actions,
        allow_auto_stop=allow_auto_stop,
        u_stop=u_stop,
        p_success=p_success,
        budget_pressure=budget_pressure,
        recovery_margin=recovery_margin,
        intervention_value=intervention_value,
    ):
        action = "stop"
        reason = (
            "runtime stop threshold met; route through terminal_stop replan candidate"
        )
        basis = "action_priority"
    elif (
        phase != "replan"
        and "patch_local" in allowed_actions
        and s6_default_action == "patch"
        and (
            local_patchability is None
            or (
                local_patchability >= 0.55
                and recovery_margin >= 0.30
            )
        )
        and not (
            p_structural_failure >= 0.55
            and recovery_margin <= 0.1
        )
    ):
        action = "patch_local"
        if observation_only:
            reason = (
                "observation-only runtime policy routes the local failure "
                "through patch_local"
            )
            basis = "observation_only"
        else:
            reason = "failure still looks local and existing recovery order prefers patch"
            basis = "action_priority"
    elif (
        "suffix_replan" in allowed_actions
        and (
            s6_default_action == "replan"
            or (
                p_structural_failure >= 0.55
                and recovery_margin <= 0.1
            )
        )
    ):
        action = "suffix_replan"
        if observation_only:
            reason = (
                "observation-only runtime policy escalates to suffix_replan "
                "from the current failure signal"
            )
            basis = "observation_only"
        else:
            reason = (
                "structural failure pressure is high or trigger matrix already prefers replan"
            )
            basis = "action_priority"
    else:
        action = "continue"
        if observation_only:
            reason = (
                "observation-only runtime policy keeps the current path because "
                "the present signal does not justify escalation"
            )
            basis = "observation_only"
        else:
            reason = "current context does not justify escalating beyond the existing path"
            basis = "default_continue"

    route = resolve_workflow_action_route(action)
    return WorkflowActionSelectorResult(
        action=action,
        mapped_flow=route.mapped_flow,
        reason=reason,
        evidence_source={
            "phase": phase,
            "basis": basis,
            "stage_id": normalized_stage_id,
            "failure_code": normalized_failure_code,
            "failure_type": (
                normalized_failure_type.value
                if isinstance(normalized_failure_type, FailureType)
                else None
            ),
            "retry_exhausted": bool(selector_input.retry_exhausted),
            "s6_default_action": s6_default_action,
            "budget_pressure": budget_pressure,
            "intervention_value": intervention_value,
            "prefix_preservability": prefix_preservability,
            "local_patchability": local_patchability,
            "allow_auto_stop": allow_auto_stop,
            "u_stop": u_stop,
            "runtime_policy": runtime_policy,
            "belief_state_enabled": not observation_only,
            "runtime_state_summary": runtime_summary or None,
        },
    )


def build_terminal_stop_candidate(
    *,
    plan: Plan,
    step_id: str | None,
    failure_type: FailureType | str | None,
    failure_code: str | None,
    failure_reason: str,
    runtime_state_summary: dict[str, Any] | None = None,
    explanation: str | None = None,
) -> PendingActionCandidate:
    """构造复用 replan_confirm 闭环的 terminal_stop 候选。"""

    stop_reason = resolve_terminal_stop_reason(
        failure_type=failure_type,
        failure_code=failure_code,
    )
    preserve_prefix_until_step_index = _resolve_preserve_prefix_until_step_index(
        plan,
        step_id,
    )
    payload = plan.model_copy(deep=True)
    payload.metadata = {
        **(payload.metadata if isinstance(payload.metadata, dict) else {}),
        "replan_mode": "suffix_replan",
        "terminal_policy": "stop",
        "terminal_reason": stop_reason,
        "preserve_prefix_until_step_index": preserve_prefix_until_step_index,
    }
    metadata: dict[str, Any] = {
        "shadow_action": "stop",
        "shadow_action_reason": explanation or failure_reason,
        "replan_mode": "suffix_replan",
        "terminal_policy": "stop",
        "terminal_reason": stop_reason,
        "preserve_prefix_until_step_index": preserve_prefix_until_step_index,
    }
    if runtime_state_summary:
        metadata["runtime_state_summary"] = dict(runtime_state_summary)
    candidate_suffix = (step_id or "task").strip().lower()
    return PendingActionCandidate(
        candidate_id=f"terminal_stop_{candidate_suffix}",
        payload=payload,
        structured_payload=payload,
        summary="terminal stop candidate",
        explanation=explanation or failure_reason,
        metadata=metadata,
    )


def extract_candidate_recovery_metadata(
    candidate: PendingActionCandidate | None,
) -> dict[str, Any]:
    """合并候选和 payload 上的恢复语义元数据。"""

    if candidate is None:
        return {}
    metadata = (
        dict(candidate.metadata)
        if isinstance(candidate.metadata, dict)
        else {}
    )
    payload = candidate.structured_payload or candidate.payload
    if isinstance(payload, Plan):
        payload_metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        for key in (
            "replan_mode",
            "terminal_policy",
            "terminal_reason",
            "preserve_prefix_until_step_index",
        ):
            value = payload_metadata.get(key)
            if value is not None and key not in metadata:
                metadata[key] = value
    return metadata


def is_terminal_stop_candidate(candidate: PendingActionCandidate | None) -> bool:
    metadata = extract_candidate_recovery_metadata(candidate)
    terminal_policy = _normalize_text(metadata.get("terminal_policy"))
    replan_mode = _normalize_text(metadata.get("replan_mode"))
    return terminal_policy == "stop" or replan_mode == "terminal_stop"


def resolve_terminal_stop_reason(
    *,
    failure_type: FailureType | str | None,
    failure_code: str | None,
) -> str:
    """将 stop 候选映射到定稿约定的终止原因。"""

    normalized_type = _normalize_failure_type(failure_type)
    normalized_code = _normalize_text(failure_code) or ""
    if normalized_type == FailureType.SAFETY_BLOCK or normalized_code.startswith("SAFETY_"):
        return "unsafe_to_continue"
    if normalized_code.startswith(("SCHEMA_", "IO_", "TOOL_")):
        return "recovery_exhausted"
    if normalized_type in _TERMINAL_STOP_REASON_BY_FAILURE_TYPE:
        return _TERMINAL_STOP_REASON_BY_FAILURE_TYPE[normalized_type]
    return "economic_stop"


def resolve_s6_recovery_action(
    *,
    stage_id: str | None,
    failure_code: str | None,
    failure_type: FailureType | str | None,
    retry_exhausted: bool,
    safety_blocked: bool = False,
) -> str:
    """根据阶段与失败上下文决定优先恢复动作：patch 或 replan。"""
    if safety_blocked:
        return "replan"

    normalized_type = _normalize_failure_type(failure_type)
    if normalized_type == FailureType.SAFETY_BLOCK:
        return "replan"

    normalized_stage = (stage_id or "").strip().upper()
    stage_rule = _S6_STAGE_TRIGGER_MATRIX.get(normalized_stage)
    normalized_code = (failure_code or "").strip().upper()
    if stage_rule and normalized_code:
        for prefix in stage_rule.get("replan_failure_prefixes", []):
            if isinstance(prefix, str) and normalized_code.startswith(prefix.upper()):
                return "replan"

    if stage_rule:
        return str(stage_rule.get("default_action") or "patch")

    if normalized_type in {
        FailureType.RETRYABLE,
        FailureType.TOOL_ERROR,
        FailureType.NON_RETRYABLE,
    }:
        return "patch"
    if retry_exhausted:
        return "patch"
    return "replan"


def _normalize_selector_phase(value: str | None) -> str:
    normalized = _normalize_text(value) or "execution"
    if normalized not in _PHASE_ALLOWED_ACTIONS:
        return "execution"
    return normalized


def _normalize_workflow_action(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if normalized in _WORKFLOW_ACTION_ROUTES:
        return normalized
    return None


def _normalize_runtime_state_summary(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return dict(payload)


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _safe_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_optional_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _normalize_failure_type(value: FailureType | str | None) -> FailureType | None:
    if isinstance(value, FailureType):
        return value
    if isinstance(value, str):
        try:
            return FailureType(value)
        except ValueError:
            return None
    return None


def _is_hard_blocked_suggestion(
    *,
    suggested_action: str,
    safety_blocked: bool,
) -> bool:
    return safety_blocked and suggested_action == "continue"


def _should_choose_stop(
    *,
    allowed_actions: frozenset[str],
    allow_auto_stop: bool,
    u_stop: float,
    p_success: float,
    budget_pressure: float,
    recovery_margin: float,
    intervention_value: float,
) -> bool:
    if "stop" not in allowed_actions:
        return False
    if allow_auto_stop and u_stop >= 0.72:
        return True
    return (
        p_success <= 0.20
        and budget_pressure >= 0.85
        and recovery_margin <= 0.20
        and intervention_value <= 0.35
    )


def _resolve_preserve_prefix_until_step_index(
    plan: Plan,
    step_id: str | None,
) -> int | None:
    if not step_id:
        return None
    for index, step in enumerate(plan.steps):
        if step.id == step_id:
            return index - 1 if index > 0 else None
    return None


class RemoteJobContext:
    """远程作业上下文，用于恢复中断的远程作业

    Attributes:
        job_id: 远程作业 ID
        endpoint: 远程服务端点 URL
        step_id: 关联的步骤 ID
        status: 作业状态（pending/running/completed/failed）
        submitted_at: 提交时间戳
        metadata: 额外的元数据
    """

    def __init__(
        self,
        job_id: str,
        endpoint: str,
        step_id: str,
        *,
        status: str = "unknown",
        submitted_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.job_id = job_id
        self.endpoint = endpoint
        self.step_id = step_id
        self.status = status
        self.submitted_at = submitted_at
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，用于存入快照"""
        return {
            "job_id": self.job_id,
            "endpoint": self.endpoint,
            "step_id": self.step_id,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RemoteJobContext:
        """从字典恢复远程作业上下文"""
        return cls(
            job_id=data["job_id"],
            endpoint=data["endpoint"],
            step_id=data["step_id"],
            status=data.get("status", "unknown"),
            submitted_at=data.get("submitted_at"),
            metadata=data.get("metadata"),
        )


@dataclass(frozen=True)
class RecoveryResult:
    """恢复结果，包含上下文与回放信息"""

    context: WorkflowContext
    snapshot: TaskSnapshot
    applied_event_logs: Sequence[EventLog]
    resume_from_existing: bool


@dataclass(frozen=True)
class StructureRefinementIteration:
    """S4 精修闭环单轮审计记录。"""

    iteration: int
    source_candidate_id: str | None
    source_pdb_path: str | None
    source_plddt: float | None
    refined_candidate_id: str | None
    refined_sequence: str | None
    refined_pdb_path: str | None
    refined_plddt: float | None
    gain_vs_baseline: float | None
    gain_vs_previous: float | None
    qc_pass_count: int
    qc_fail_count: int
    status: str
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": int(self.iteration),
            "source_candidate_id": self.source_candidate_id,
            "source_pdb_path": self.source_pdb_path,
            "source_plddt": self.source_plddt,
            "refined_candidate_id": self.refined_candidate_id,
            "refined_sequence": self.refined_sequence,
            "refined_pdb_path": self.refined_pdb_path,
            "refined_plddt": self.refined_plddt,
            "gain_vs_baseline": self.gain_vs_baseline,
            "gain_vs_previous": self.gain_vs_previous,
            "qc_pass_count": int(self.qc_pass_count),
            "qc_fail_count": int(self.qc_fail_count),
            "status": self.status,
            "stop_reason": self.stop_reason,
        }


def build_structure_refinement_audit(
    *,
    task_id: str,
    step_id: str,
    source_step_id: str,
    baseline: dict[str, Any],
    iterations: Sequence[StructureRefinementIteration | dict[str, Any]],
    stop_reason: str,
    rollback_applied: bool,
    selected_candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_iterations: list[dict[str, Any]] = []
    for row in iterations:
        if isinstance(row, StructureRefinementIteration):
            normalized_iterations.append(row.to_dict())
        elif isinstance(row, dict):
            normalized_iterations.append(dict(row))

    baseline_plddt = baseline.get("plddt")
    selected_plddt = (
        selected_candidate.get("plddt")
        if isinstance(selected_candidate, dict)
        else None
    )
    gain_vs_baseline = None
    if isinstance(baseline_plddt, (int, float)) and isinstance(selected_plddt, (int, float)):
        gain_vs_baseline = round(float(selected_plddt) - float(baseline_plddt), 6)

    return {
        "stage_id": "S4",
        "task_id": task_id,
        "step_id": step_id,
        "source_step_id": source_step_id,
        "created_at": now_iso(),
        "baseline": {
            "candidate_id": baseline.get("candidate_id"),
            "sequence": baseline.get("sequence"),
            "pdb_path": baseline.get("pdb_path"),
            "plddt": baseline_plddt,
        },
        "selected_candidate": selected_candidate if isinstance(selected_candidate, dict) else None,
        "iterations": normalized_iterations,
        "summary": {
            "iteration_count": len(normalized_iterations),
            "stop_reason": stop_reason,
            "rollback_applied": bool(rollback_applied),
            "gain_vs_baseline": gain_vs_baseline,
        },
    }


def persist_structure_refinement_audit(
    *,
    task_id: str,
    step_id: str,
    audit_payload: dict[str, Any],
    artifacts_dir: Path = Path("output/artifacts"),
) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / f"s4_refinement_{task_id}_{step_id}.json"
    path.write_text(
        json.dumps(audit_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return path


def restore_context_from_snapshot(
    task: ProteinDesignTask,
    plan: Plan,
    *,
    task_id: Optional[str] = None,
    snapshot: Optional[TaskSnapshot] = None,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> Optional[WorkflowContext]:
    """从快照恢复 WorkflowContext

    Args:
        task: 原始任务对象
        plan: 当前的计划对象
        task_id: 任务 ID（如果未提供则从 task 获取）
        snapshot: 可选的快照对象（如果提供则直接使用，否则从文件读取）
        snapshot_dir: 快照目录

    Returns:
        恢复的 WorkflowContext，如果没有快照则返回 None

    Note:
        恢复的上下文将包含：
        - 原始任务对象
        - 当前计划
        - 已完成的步骤 ID 列表（从 snapshot.completed_step_ids）
        - 恢复的内部状态（从 snapshot.state）
        - 待处理的 pending_action（如果有）

        注意：step_results 会恢复为占位结果（不含真实 outputs），
        这些结果会标记 outputs_missing，以避免被当成可跳过的已完成步骤。
    """
    actual_task_id = task_id or task.task_id

    # 如果没有提供快照，从文件读取最新快照
    if snapshot is None:
        snapshot = read_latest_snapshot(
            actual_task_id,
            snapshot_dir=snapshot_dir,
        )

    # 如果没有快照，返回 None
    if snapshot is None:
        return None

    # 验证快照的 task_id 与传入的一致
    if snapshot.task_id != actual_task_id:
        raise ValueError(
            f"Snapshot task_id ({snapshot.task_id}) does not match "
            f"provided task_id ({actual_task_id})"
        )

    # 将 ExternalStatus 转换为 InternalStatus
    # 注意：这是一个简化的映射，实际可能需要更复杂的逻辑
    status_mapping = {
        ExternalStatus.CREATED.value: InternalStatus.CREATED,
        ExternalStatus.PLANNING.value: InternalStatus.PLANNING,
        ExternalStatus.WAITING_PLAN_CONFIRM.value: InternalStatus.WAITING_PLAN_CONFIRM,
        ExternalStatus.PLANNED.value: InternalStatus.PLANNED,
        ExternalStatus.RUNNING.value: InternalStatus.RUNNING,
        ExternalStatus.WAITING_PATCH_CONFIRM.value: InternalStatus.WAITING_PATCH,
        ExternalStatus.WAITING_REPLAN_CONFIRM.value: InternalStatus.WAITING_REPLAN,
        ExternalStatus.SUMMARIZING.value: InternalStatus.SUMMARIZING,
        ExternalStatus.DONE.value: InternalStatus.DONE,
        ExternalStatus.FAILED.value: InternalStatus.FAILED,
        ExternalStatus.CANCELLED.value: InternalStatus.CANCELLED,
    }
    internal_status = status_mapping.get(
        snapshot.state,
        InternalStatus.CREATED,
    )

    # 创建 WorkflowContext
    context = WorkflowContext(
        task=task,
        plan=plan,
        runtime_state=_extract_runtime_state(snapshot, plan),
        status=internal_status,
    )

    context.pending_action = _extract_pending_action(snapshot)
    _restore_completed_steps(context, plan, snapshot)

    return context


def extract_remote_job_context(
    snapshot: TaskSnapshot,
    step_id: str,
) -> Optional[RemoteJobContext]:
    """从快照的 artifacts 中提取远程作业上下文

    Args:
        snapshot: 任务快照
        step_id: 步骤 ID

    Returns:
        RemoteJobContext 对象，如果不存在则返回 None

    Note:
        远程作业上下文应存储在 snapshot.artifacts["remote_jobs"][step_id] 中
    """
    remote_jobs = snapshot.artifacts.get("remote_jobs")
    if not isinstance(remote_jobs, dict):
        return None

    job_data = remote_jobs.get(step_id)
    if not isinstance(job_data, dict):
        return None

    try:
        return RemoteJobContext.from_dict(job_data)
    except (KeyError, TypeError, ValueError):
        return None


def _extract_runtime_state(
    snapshot: TaskSnapshot,
    plan: Plan,
) -> RuntimeState | None:
    runtime_payload = snapshot.artifacts.get(RUNTIME_STATE_ARTIFACT_KEY)
    if runtime_payload is not None and not isinstance(runtime_payload, dict):
        runtime_payload = None

    if not isinstance(runtime_payload, dict):
        payload: dict[str, Any] = {}
    else:
        payload = dict(runtime_payload)

    observation_summary = snapshot.artifacts.get(
        RUNTIME_OBSERVATION_SUMMARY_ARTIFACT_KEY
    )
    bootstrap = None
    if not _has_complete_runtime_state_payload(payload):
        bootstrap = _bootstrap_runtime_state_from_snapshot(snapshot, plan)
    if bootstrap is not None:
        payload = {
            **bootstrap.model_dump(),
            **payload,
        }
        if isinstance(observation_summary, dict):
            payload["observation_summary"] = {
                **bootstrap.observation_summary,
                **observation_summary,
            }
    elif (
        "observation_summary" not in payload
        and isinstance(observation_summary, dict)
    ):
        payload["observation_summary"] = observation_summary

    if not payload:
        return None

    try:
        return RuntimeState.model_validate(payload)
    except Exception:
        return bootstrap


def _has_complete_runtime_state_payload(payload: dict[str, Any]) -> bool:
    required_keys = {
        "p_success",
        "p_structural_failure",
        "recovery_margin",
        "expected_remaining_cost",
        "last_update_source",
    }
    return required_keys.issubset(payload.keys())


def _bootstrap_runtime_state_from_snapshot(
    snapshot: TaskSnapshot,
    plan: Plan,
) -> RuntimeState | None:
    completed_steps = _resolve_completed_steps(snapshot)
    total_steps = len(plan.steps)
    if (
        completed_steps == 0
        and snapshot.state not in {
            ExternalStatus.WAITING_PLAN_CONFIRM.value,
            ExternalStatus.WAITING_PATCH_CONFIRM.value,
            ExternalStatus.WAITING_REPLAN_CONFIRM.value,
        }
        and not isinstance(
            snapshot.artifacts.get(RUNTIME_OBSERVATION_SUMMARY_ARTIFACT_KEY),
            dict,
        )
        and not isinstance(snapshot.artifacts.get(RUNTIME_STATE_ARTIFACT_KEY), dict)
    ):
        return None
    return update_runtime_state(
        previous_state=None,
        completed_steps=completed_steps,
        total_steps=total_steps,
    )


def _resolve_completed_steps(snapshot: TaskSnapshot) -> int:
    if snapshot.completed_step_ids:
        return len(snapshot.completed_step_ids)
    return max(
        int(snapshot.current_step_index or 0),
        int(snapshot.step_index or 0),
    )


def recover_context_with_event_logs(
    task: ProteinDesignTask,
    plan: Plan,
    *,
    task_id: Optional[str] = None,
    snapshot: Optional[TaskSnapshot] = None,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    log_dir: Optional[Path] = None,
) -> Optional[RecoveryResult]:
    """从快照恢复上下文，并结合 EventLog 回放对齐状态"""
    context = restore_context_from_snapshot(
        task=task,
        plan=plan,
        task_id=task_id,
        snapshot=snapshot,
        snapshot_dir=snapshot_dir,
    )
    if context is None:
        return None

    actual_snapshot = snapshot or read_latest_snapshot(
        task_id or task.task_id, snapshot_dir=snapshot_dir
    )
    if actual_snapshot is None:
        return None

    events = read_event_logs(
        actual_snapshot.task_id, log_dir=log_dir or DEFAULT_LOG_DIR
    )
    applied_events = _apply_event_log_replay(context, actual_snapshot, events)
    resume_from_existing = _should_resume_after_recovery(context)
    return RecoveryResult(
        context=context,
        snapshot=actual_snapshot,
        applied_event_logs=applied_events,
        resume_from_existing=resume_from_existing,
    )


def _restore_completed_steps(
    context: WorkflowContext,
    plan: Plan,
    snapshot: TaskSnapshot,
) -> None:
    step_ids = _resolve_completed_step_ids(plan, snapshot)
    if not step_ids:
        return
    step_lookup = {step.id: step for step in plan.steps}
    for step_id in step_ids:
        step = step_lookup.get(step_id)
        if step is None:
            continue
        context.step_results.setdefault(
            step_id,
            _build_stub_step_result(
                task_id=context.task.task_id,
                step=step,
                timestamp=snapshot.created_at or now_iso(),
            ),
        )


def _resolve_completed_step_ids(plan: Plan, snapshot: TaskSnapshot) -> list[str]:
    if snapshot.completed_step_ids:
        return list(snapshot.completed_step_ids)
    if snapshot.step_index <= 0:
        return []
    step_index = min(snapshot.step_index, len(plan.steps))
    return [step.id for step in plan.steps[:step_index]]


def _build_stub_step_result(
    *,
    task_id: str,
    step: PlanStep,
    timestamp: str,
) -> StepResult:
    return StepResult(
        task_id=task_id,
        step_id=step.id,
        tool=step.tool,
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={},
        metrics={"recovered": True, "outputs_missing": True},
        risk_flags=[],
        logs_path=None,
        timestamp=timestamp,
    )


def _extract_pending_action(snapshot: TaskSnapshot) -> Optional[PendingAction]:
    payload = snapshot.artifacts.get("pending_action")
    if not isinstance(payload, dict):
        return None
    try:
        action = PendingAction.model_validate(payload)
    except Exception:
        return None
    if snapshot.pending_action_id and action.pending_action_id != snapshot.pending_action_id:
        return None
    return action


def _apply_event_log_replay(
    context: WorkflowContext,
    snapshot: TaskSnapshot,
    events: Iterable[EventLog],
) -> list[EventLog]:
    filtered = _filter_events_after_snapshot(snapshot, events)
    pending_action = context.pending_action
    for event in filtered:
        if event.new_status is None:
            continue
        if event.event_type == EventType.WAITING_ENTER:
            context.status = _to_internal_status(event.new_status)
            if event.pending_action_id and pending_action:
                if pending_action.pending_action_id != event.pending_action_id:
                    pending_action = None
            if event.pending_action_id and pending_action is None:
                pending_action = _extract_pending_action(snapshot)
        elif event.event_type in (EventType.WAITING_EXIT, EventType.DECISION_APPLIED):
            context.status = _to_internal_status(event.new_status)
            if pending_action and event.pending_action_id:
                if pending_action.pending_action_id == event.pending_action_id:
                    pending_action = None
            else:
                pending_action = None
    if context.status not in (
        InternalStatus.WAITING_PLAN_CONFIRM,
        InternalStatus.WAITING_PATCH,
        InternalStatus.WAITING_REPLAN,
    ):
        pending_action = None
    context.pending_action = pending_action
    return filtered


def _filter_events_after_snapshot(
    snapshot: TaskSnapshot,
    events: Iterable[EventLog],
) -> list[EventLog]:
    snapshot_ts = _parse_iso(snapshot.created_at)
    if snapshot_ts is None:
        return list(events)
    filtered: list[EventLog] = []
    for event in events:
        event_ts = _parse_iso(event.ts)
        if event_ts is None or event_ts >= snapshot_ts:
            filtered.append(event)
    return filtered


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_internal_status(status: ExternalStatus) -> InternalStatus:
    mapping = {
        ExternalStatus.CREATED: InternalStatus.CREATED,
        ExternalStatus.PLANNING: InternalStatus.PLANNING,
        ExternalStatus.WAITING_PLAN_CONFIRM: InternalStatus.WAITING_PLAN_CONFIRM,
        ExternalStatus.PLANNED: InternalStatus.PLANNED,
        ExternalStatus.RUNNING: InternalStatus.RUNNING,
        ExternalStatus.WAITING_PATCH_CONFIRM: InternalStatus.WAITING_PATCH,
        ExternalStatus.WAITING_REPLAN_CONFIRM: InternalStatus.WAITING_REPLAN,
        ExternalStatus.SUMMARIZING: InternalStatus.SUMMARIZING,
        ExternalStatus.DONE: InternalStatus.DONE,
        ExternalStatus.FAILED: InternalStatus.FAILED,
        ExternalStatus.CANCELLED: InternalStatus.CANCELLED,
    }
    return mapping.get(status, InternalStatus.CREATED)


def _should_resume_after_recovery(context: WorkflowContext) -> bool:
    if context.status != InternalStatus.RUNNING:
        return False
    if not context.step_results:
        return False
    for result in context.step_results.values():
        if result.metrics.get("outputs_missing"):
            return False
    return True
