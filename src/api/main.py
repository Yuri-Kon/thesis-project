from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from src.models.contracts import (
    ProteinDesignTask,
    DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
    Decision,
    DecisionChoice,
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    RUNTIME_STATE_SUMMARY_METADATA_KEY,
    TOOL_READINESS_METADATA_KEY,
    WAITING_RUNTIME_SUMMARY_METADATA_KEY,
)
from src.models.db import TaskRecord
from src.models.validation import (
    DecisionValidationError,
    validate_decision_for_pending_action,
)
from src.workflow.workflow import run_task_sync
from src.workflow.decision_apply import (
    apply_plan_confirm_decision,
    apply_patch_confirm_decision,
    apply_replan_confirm_decision,
    DecisionApplyError,
    DecisionConflictError,
)
from src.infra.runtime_init import RuntimeInitResult, initialize_runtime
from src.models.contracts import PendingActionType, now_iso
from src.models.db import ExternalStatus, InternalStatus
from src.models.task_intake import (
    ConfirmedTaskSpec,
    IntentDraftClarificationRequest,
    TaskIntakeConfirmRequest,
    TaskIntakeCreateRequest,
    TaskIntakePatchRequest,
    TaskIntakeSession,
    build_task_intake_schema,
    cancel_task_intake_session,
    confirm_task_intake_session,
    create_task_intake_session,
    patch_task_intake_session,
    project_confirmed_task_spec,
)
from src.storage.log_store import append_event, read_timeline_events
from src.workflow.context import WorkflowContext
from src.infra.tool_readiness import (
    build_capability_readiness_matrix,
    build_tool_readiness_snapshot,
)

API_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = API_DIR / "templates"
STATIC_DIR = API_DIR / "static"

app = FastAPI(title="Protein Design Agent System (Mini Demo)", version="0.5.2")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 简单的内存存储，之后可以换成数据库或文件
TASK_STORE: Dict[str, TaskRecord] = {}
INTAKE_STORE: Dict[str, TaskIntakeSession] = {}
RUNTIME_INIT: Optional[RuntimeInitResult] = None


class TaskIntakeAPIError(Exception):
    """Task Intake API 的稳定错误响应。"""

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        missing_fields: list[str] | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = {
            "status": status_code,
            "detail": detail,
            "missing_fields": missing_fields or [],
            "validation_errors": validation_errors or [],
            "context": context or {},
        }


@app.exception_handler(TaskIntakeAPIError)
async def _handle_task_intake_api_error(
    _request: Request,
    exc: TaskIntakeAPIError,
) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.payload)


def _path_from_env(env_key: str) -> Optional[Path]:
    raw = os.getenv(env_key)
    if raw is None or raw == "":
        return None
    return Path(raw)


def _ensure_runtime_initialized() -> RuntimeInitResult:
    global RUNTIME_INIT
    if RUNTIME_INIT is not None:
        return RUNTIME_INIT

    RUNTIME_INIT = initialize_runtime(
        kg_path=_path_from_env("PROTEIN_KG_PATH"),
        output_dir=_path_from_env("PROTEIN_OUTPUT_DIR"),
        data_dir=_path_from_env("PROTEIN_DATA_DIR"),
        log_dir=_path_from_env("PROTEIN_LOG_DIR"),
        snapshot_dir=_path_from_env("PROTEIN_SNAPSHOT_DIR"),
    )
    return RUNTIME_INIT


@app.on_event("startup")
async def _startup_init() -> None:
    _ensure_runtime_initialized()


class TaskCreateRequest(BaseModel):
    goal: Optional[str] = Field(None, description="蛋白质设计任务目标(自然语言)")
    query: Optional[str] = Field(None, description="兼容自由文本入口；会收敛为 intake")
    confirmed_task_spec: Optional[ConfirmedTaskSpec] = Field(
        None,
        description="已经确认的结构化任务输入",
    )
    constraints: Dict[str, Any] = Field(default_factory=dict, description="结构化约束")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_creation_mode(self) -> "TaskCreateRequest":
        """确保 /tasks 请求明确选择一种兼容创建模式。"""

        modes = [
            self.goal is not None,
            self.query is not None,
            self.confirmed_task_spec is not None,
        ]
        if not any(modes):
            raise ValueError("one of goal, query, or confirmed_task_spec is required")
        if sum(modes) > 1:
            raise ValueError("choose exactly one of goal, query, or confirmed_task_spec")
        return self


class TaskIntakeCancelAPIRequest(BaseModel):
    """取消 Task Intake 的 API 请求。"""

    cancelled_by: str = "api"
    reason: str | None = None


class DecisionSubmitRequest(BaseModel):
    """提交人工决策的请求体"""

    choice: DecisionChoice = Field(..., description="决策选择")
    selected_candidate_id: Optional[str] = Field(
        None, description="当choice为accept时必填"
    )
    decided_by: str = Field(..., description="决策者标识")
    comment: Optional[str] = Field(None, description="可选的决策备注")


class PendingActionSummary(BaseModel):
    pending_action_id: str = Field(..., description="PendingAction ID")
    task_id: str = Field(..., description="所属任务 ID")
    action_type: PendingActionType = Field(..., description="待决策类型")
    status: PendingActionStatus = Field(..., description="PendingAction 状态")
    created_at: str = Field(..., description="创建时间")
    candidate_count: int = Field(..., description="候选数量")
    default_suggestion: Optional[str] = Field(None, description="默认建议候选 ID")
    explanation: str = Field(..., description="待决策说明")
    summary: str = Field(..., description="候选摘要")


class TaskTimelineEvent(BaseModel):
    seq: int = Field(..., description="日志行序号(稳定排序键)")
    task_id: str = Field(..., description="任务 ID")
    ts: Optional[str] = Field(None, description="事件时间戳")
    event_type: str = Field(..., description="归一化事件类型")
    source_event: Optional[str] = Field(None, description="原始事件名")
    pending_action_id: Optional[str] = None
    decision_id: Optional[str] = None
    step_id: Optional[str] = None
    tool: Optional[str] = None
    tool_id: Optional[str] = None
    adapter_id: Optional[str] = None
    execution_mode: Optional[str] = None
    capability_id: Optional[str] = None
    io_type: Optional[str] = None
    adapter_mode: Optional[str] = None
    provider: Optional[str] = None
    endpoint_type: Optional[str] = None
    remote_job_id: Optional[str] = None
    from_tool: Optional[str] = None
    to_tool: Optional[str] = None
    failure_type: Optional[str] = None
    failure_code: Optional[str] = None
    recovery_hint: Optional[str] = None
    candidate_id: Optional[str] = None
    decision_source: Optional[str] = None
    recovery_layer: Optional[str] = None
    recovery_reason: Optional[str] = None
    status: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor_type: Optional[str] = None
    summary: str = Field(..., description="事件摘要")
    highlight: bool = Field(..., description="是否属于关键高亮事件")
    data: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)


class PendingActionToolDisplay(BaseModel):
    tool_id: Optional[str] = None
    adapter_id: Optional[str] = None
    capability_id: Optional[str] = None
    io_type: Optional[str] = None
    adapter_mode: Optional[str] = None
    execution_mode: Optional[str] = None
    provider: Optional[str] = None
    endpoint_type: Optional[str] = None
    remote_job_id: Optional[str] = None
    failure_code: Optional[str] = None
    recovery_hint: Optional[str] = None
    source: str = Field(..., description="工具来源(local/remote/mock/hybrid/unknown)")
    available: bool = Field(..., description="工具信息是否可用于决策展示")
    can_fallback: bool = Field(..., description="是否可回退到备选工具")
    availability_hint: str = Field(..., description="工具可用性提示")
    readiness_status: Optional[str] = None
    degraded_reasons: list[str] = Field(default_factory=list)
    suggested_recovery: Optional[str] = None
    readiness_snapshot: Dict[str, Any] = Field(default_factory=dict)


class PendingActionCandidateDisplay(BaseModel):
    rank: int = Field(..., description="候选排名（按返回顺序）")
    candidate_id: str
    is_default: bool
    summary: str
    explanation: str
    recommendation_reason: str
    risk_level: Optional[str] = None
    cost_estimate: Optional[str] = None
    expected_effect: Optional[str] = None
    affected_steps: list[str] = Field(default_factory=list)
    recovery_semantics: Optional[str] = None
    overall_score: Optional[float] = None
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    runtime_state_summary: Dict[str, Any] = Field(default_factory=dict)
    workflow_action_reason: Optional[str] = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    tool: PendingActionToolDisplay


class PendingActionDetail(BaseModel):
    pending_action_id: str
    task_id: str
    action_type: PendingActionType
    status: PendingActionStatus
    created_at: str
    default_suggestion: Optional[str] = None
    explanation: str
    recommendation_summary: str
    runtime_state_summary: Dict[str, Any] = Field(default_factory=dict)
    workflow_action_reason: Optional[str] = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    candidates: list[PendingActionCandidateDisplay] = Field(default_factory=list)


class ToolReadinessEntry(BaseModel):
    tool_id: str
    status: str
    reason: str = ""
    error_category: Optional[str] = None
    capability_ids: list[str] = Field(default_factory=list)
    cost_prior: Optional[float] = None
    risk_prior: Optional[float] = None
    latency_prior: Optional[float] = None
    suggested_recovery: Optional[str] = None
    last_checked_at: str
    checked_at: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    metadata_profile: Optional[Dict[str, Any]] = None


class CapabilityReadinessEntry(BaseModel):
    capability_id: str
    status: str
    available_tools: list[ToolReadinessEntry] = Field(default_factory=list)
    blocked_tools: list[ToolReadinessEntry] = Field(default_factory=list)
    degraded_reasons: list[str] = Field(default_factory=list)
    last_checked_at: str
    primary_tool_id: Optional[str] = None
    fallback_tool_ids: list[str] = Field(default_factory=list)
    cost_prior: Optional[float] = None
    risk_prior: Optional[float] = None
    suggested_recovery: Optional[str] = None
    reason: str
    checked_at: Optional[str] = None
    tools: list[ToolReadinessEntry] = Field(default_factory=list)


class TaskReportDetail(BaseModel):
    task_id: str
    report_path: Optional[str] = None
    scores: Dict[str, Any] = Field(default_factory=dict)
    objective_scoring: Dict[str, Any] = Field(default_factory=dict)
    structure_similarity: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _render_react_app_html(
    *,
    task_id: Optional[str],
    view: str,
) -> str:
    template_path = TEMPLATES_DIR / "react_app.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="UI template not found")
    raw_html = template_path.read_text(encoding="utf-8")
    bootstrap_payload = json.dumps(
        {"taskId": task_id or "", "view": view},
        ensure_ascii=True,
    )
    return raw_html.replace("__REACT_BOOTSTRAP__", bootstrap_payload)


def _render_task_builder_html() -> str:
    template_path = TEMPLATES_DIR / "task_builder.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="task builder template not found")
    return template_path.read_text(encoding="utf-8")


def _build_pending_action_summary(pending_action: PendingAction) -> str:
    if not pending_action.candidates:
        return pending_action.explanation

    snippets: list[str] = []
    for candidate in pending_action.candidates[:2]:
        text = candidate.summary or candidate.explanation or candidate.candidate_id
        snippets.append(text.strip())

    summary = " | ".join(snippets)
    hidden_count = len(pending_action.candidates) - len(snippets)
    if hidden_count > 0:
        summary = f"{summary} | +{hidden_count} more"
    return summary


def _normalize_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _build_tool_display(
    candidate: PendingActionCandidate,
) -> PendingActionToolDisplay:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    tool_id = candidate.tool_id or _normalize_text(metadata.get("tool_id"))
    capability_id = candidate.capability_id or _normalize_text(
        metadata.get("capability_id")
    )
    io_type = candidate.io_type or _normalize_text(metadata.get("io_type"))
    adapter_mode = candidate.adapter_mode or _normalize_text(
        metadata.get("adapter_mode")
    )
    adapter_id = candidate.adapter_id or _normalize_text(metadata.get("adapter_id"))
    execution_mode = candidate.execution_mode or _normalize_text(
        metadata.get("execution_mode")
    )
    provider = candidate.provider or _normalize_text(metadata.get("provider"))
    endpoint_type = candidate.endpoint_type or _normalize_text(
        metadata.get("endpoint_type")
    )
    remote_job_id = candidate.remote_job_id or _normalize_text(
        metadata.get("remote_job_id")
    )
    failure_code = _normalize_text(metadata.get("failure_code"))
    recovery_hint = _normalize_text(metadata.get("recovery_hint"))

    source = (
        adapter_mode
        if adapter_mode in {"local", "remote", "mock", "hybrid"}
        else "unknown"
    )

    missing: list[str] = []
    if tool_id is None:
        missing.append("tool_id")
    if capability_id is None:
        missing.append("capability_id")
    if io_type is None:
        missing.append("io_type")
    if adapter_mode is None:
        missing.append("adapter_mode")
    can_fallback = any(
        metadata.get(key)
        for key in (
            "fallback_tool",
            "fallback_tool_id",
            "fallback_from",
            "fallback_candidates",
            "fallback_options",
        )
    )
    fallback_depth = candidate.score_breakdown.get("fallback_depth")
    if isinstance(fallback_depth, (int, float)) and fallback_depth > 0:
        can_fallback = True

    available = source != "unknown" and not missing
    if missing:
        availability_hint = (
            f"Tool metadata missing ({', '.join(missing)}); use degraded display."
        )
    elif execution_mode == "openfold3_rest":
        availability_hint = (
            "OpenFold3 REST execution mode configured; availability depends on remote service health."
        )
    elif source == "remote":
        availability_hint = (
            "Remote adapter configured; availability depends on remote service health."
        )
    elif source == "local":
        availability_hint = "Local adapter configured."
    elif source == "mock":
        availability_hint = "Mock adapter configured for demo."
    elif source == "hybrid":
        availability_hint = "Hybrid adapter configured."
    else:
        availability_hint = "Tool source unknown; use degraded display."

    if can_fallback:
        availability_hint = f"{availability_hint} Fallback path is available."

    readiness_snapshot: dict[str, Any] = {}
    readiness_status: str | None = None
    degraded_reasons: list[str] = []
    suggested_recovery: str | None = None
    if tool_id:
        raw_snapshot = metadata.get(TOOL_READINESS_METADATA_KEY)
        if isinstance(raw_snapshot, dict) and raw_snapshot.get("tool_id") == tool_id:
            readiness_snapshot = dict(raw_snapshot)
        else:
            readiness_snapshot = build_tool_readiness_snapshot(tool_id)
        readiness_status = _normalize_text(readiness_snapshot.get("status"))
        reason = _normalize_text(readiness_snapshot.get("reason"))
        if readiness_status and readiness_status != "ready" and reason:
            degraded_reasons.append(reason)
        suggested_recovery = _normalize_text(readiness_snapshot.get("suggested_recovery"))
        if readiness_status:
            available = available and readiness_status == "ready"
            if readiness_status != "ready" and reason:
                availability_hint = f"{availability_hint} Readiness: {reason}"

    return PendingActionToolDisplay(
        tool_id=tool_id,
        adapter_id=adapter_id,
        capability_id=capability_id,
        io_type=io_type,
        adapter_mode=adapter_mode,
        execution_mode=execution_mode,
        provider=provider,
        endpoint_type=endpoint_type,
        remote_job_id=remote_job_id,
        failure_code=failure_code,
        recovery_hint=recovery_hint,
        source=source,
        available=available,
        can_fallback=can_fallback,
        availability_hint=availability_hint,
        readiness_status=readiness_status,
        degraded_reasons=degraded_reasons,
        suggested_recovery=suggested_recovery,
        readiness_snapshot=readiness_snapshot,
    )


def _build_candidate_reason(
    candidate: PendingActionCandidate,
    *,
    is_default: bool,
    tool_display: PendingActionToolDisplay,
) -> str:
    reason_parts: list[str] = []
    if is_default:
        reason_parts.append("默认推荐")
    overall = candidate.score_breakdown.get("overall")
    if isinstance(overall, (int, float)):
        reason_parts.append(f"overall={float(overall):.2f}")
    reason_parts.append(f"risk={candidate.risk_level or 'unknown'}")
    reason_parts.append(f"cost={candidate.cost_estimate or 'unknown'}")
    reason_parts.append(f"tool_source={tool_display.source}")
    if tool_display.execution_mode:
        reason_parts.append(f"execution_mode={tool_display.execution_mode}")
    if tool_display.provider:
        reason_parts.append(f"provider={tool_display.provider}")
    if tool_display.readiness_status:
        reason_parts.append(f"readiness={tool_display.readiness_status}")
    if tool_display.can_fallback:
        reason_parts.append("supports_fallback")
    return "; ".join(reason_parts)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _message_from_reason(value: Any) -> str | None:
    if isinstance(value, dict):
        message = _normalize_text(value.get("message"))
        code = _normalize_text(value.get("code"))
        return message or code
    return _normalize_text(value)


def _workflow_evidence_from_pending_action(
    pending_action: PendingAction,
) -> dict[str, Any]:
    evidence = pending_action.metadata.get("workflow_action_evidence")
    return _dict_or_empty(evidence)


def _candidate_runtime_state_summary(
    candidate: PendingActionCandidate,
    pending_evidence: dict[str, Any],
) -> dict[str, Any]:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    return (
        _dict_or_empty(metadata.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
        or _dict_or_empty(pending_evidence.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
    )


def _candidate_workflow_action_reason(
    candidate: PendingActionCandidate,
    pending_evidence: dict[str, Any],
) -> str | None:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    return (
        _message_from_reason(metadata.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or _message_from_reason(pending_evidence.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or _normalize_text(metadata.get("workflow_action_reason"))
        or _normalize_text(metadata.get("rerank_reason"))
    )


def _candidate_evidence_refs(
    candidate: PendingActionCandidate,
    pending_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    return (
        _list_of_dicts(metadata.get("evidence_refs"))
        or _list_of_dicts(pending_evidence.get("evidence_refs"))
    )


def _candidate_affected_steps(candidate: PendingActionCandidate) -> list[str]:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    explicit = _string_list(metadata.get("affected_steps")) or _string_list(
        metadata.get("affected_step_ids")
    )
    if explicit:
        return explicit

    payload = candidate.payload
    operations = getattr(payload, "operations", None)
    if not isinstance(operations, list):
        return []

    steps: list[str] = []
    for operation in operations:
        step_id = getattr(operation, "step_id", None)
        if isinstance(step_id, str) and step_id.strip():
            steps.append(step_id)
    return list(dict.fromkeys(steps))


def _candidate_expected_effect(candidate: PendingActionCandidate) -> str | None:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    return (
        _normalize_text(metadata.get("expected_effect"))
        or _normalize_text(metadata.get("expected_effect_summary"))
        or _normalize_text(metadata.get("recommendation_effect"))
    )


def _candidate_recovery_semantics(candidate: PendingActionCandidate) -> str | None:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    return (
        _normalize_text(metadata.get("recovery_semantics"))
        or _normalize_text(metadata.get("recovery_action"))
        or _normalize_text(metadata.get("recovery_layer"))
        or _normalize_text(metadata.get("workflow_action"))
        or _normalize_text(metadata.get("terminal_policy"))
    )


def _pending_runtime_state_summary(
    pending_action: PendingAction,
    pending_evidence: dict[str, Any],
) -> dict[str, Any]:
    waiting_summary = _dict_or_empty(
        pending_action.metadata.get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
    )
    return (
        _dict_or_empty(waiting_summary.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
        or _dict_or_empty(pending_evidence.get(RUNTIME_STATE_SUMMARY_METADATA_KEY))
    )


def _pending_workflow_action_reason(
    pending_action: PendingAction,
    pending_evidence: dict[str, Any],
) -> str | None:
    waiting_summary = _dict_or_empty(
        pending_action.metadata.get(WAITING_RUNTIME_SUMMARY_METADATA_KEY)
    )
    return (
        _message_from_reason(waiting_summary.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or _message_from_reason(pending_evidence.get(DEFAULT_RECOMMENDATION_REASON_METADATA_KEY))
        or _normalize_text(pending_action.metadata.get("workflow_action_reason"))
        or _normalize_text(pending_action.explanation)
    )


def _build_pending_action_detail(
    record: TaskRecord, pending_action: PendingAction
) -> PendingActionDetail:
    default_suggestion = (
        pending_action.default_suggestion or pending_action.default_recommendation
    )
    candidates: list[PendingActionCandidateDisplay] = []
    pending_evidence = _workflow_evidence_from_pending_action(pending_action)

    for index, candidate in enumerate(pending_action.candidates, start=1):
        is_default = candidate.candidate_id == default_suggestion
        summary = candidate.summary or candidate.explanation or candidate.candidate_id
        explanation = candidate.explanation or summary
        score_breakdown = {
            key: float(value)
            for key, value in candidate.score_breakdown.items()
            if isinstance(value, (int, float))
        }
        overall_score = score_breakdown.get("overall")
        tool_display = _build_tool_display(candidate)
        recommendation_reason = _build_candidate_reason(
            candidate,
            is_default=is_default,
            tool_display=tool_display,
        )
        candidates.append(
            PendingActionCandidateDisplay(
                rank=index,
                candidate_id=candidate.candidate_id,
                is_default=is_default,
                summary=summary,
                explanation=explanation,
                recommendation_reason=recommendation_reason,
                risk_level=candidate.risk_level,
                cost_estimate=candidate.cost_estimate,
                expected_effect=_candidate_expected_effect(candidate),
                affected_steps=_candidate_affected_steps(candidate),
                recovery_semantics=_candidate_recovery_semantics(candidate),
                overall_score=overall_score,
                score_breakdown=score_breakdown,
                runtime_state_summary=_candidate_runtime_state_summary(
                    candidate,
                    pending_evidence,
                ),
                workflow_action_reason=_candidate_workflow_action_reason(
                    candidate,
                    pending_evidence,
                ),
                evidence_refs=_candidate_evidence_refs(candidate, pending_evidence),
                tool=tool_display,
            )
        )

    recommendation_summary = pending_action.explanation
    if default_suggestion:
        default_candidate = next(
            (item for item in candidates if item.candidate_id == default_suggestion),
            None,
        )
        if default_candidate is not None:
            recommendation_summary = (
                f"default={default_suggestion}; {default_candidate.recommendation_reason}"
            )
        else:
            recommendation_summary = f"default={default_suggestion}; reason not found"

    return PendingActionDetail(
        pending_action_id=pending_action.pending_action_id,
        task_id=record.id,
        action_type=pending_action.action_type,
        status=pending_action.status,
        created_at=pending_action.created_at,
        default_suggestion=default_suggestion,
        explanation=pending_action.explanation,
        recommendation_summary=recommendation_summary,
        runtime_state_summary=_pending_runtime_state_summary(
            pending_action,
            pending_evidence,
        ),
        workflow_action_reason=_pending_workflow_action_reason(
            pending_action,
            pending_evidence,
        ),
        evidence_refs=_list_of_dicts(pending_evidence.get("evidence_refs")),
        score_breakdown=(
            next(
                (item.score_breakdown for item in candidates if item.is_default),
                candidates[0].score_breakdown if candidates else {},
            )
        ),
        candidates=candidates,
    )


def _find_record_by_pending_action_id(pending_action_id: str) -> Optional[TaskRecord]:
    for task_record in TASK_STORE.values():
        if (
            task_record.pending_action
            and task_record.pending_action.pending_action_id == pending_action_id
        ):
            return task_record
    return None


def _get_intake_or_404(intake_id: str) -> TaskIntakeSession:
    session = INTAKE_STORE.get(intake_id)
    if session is None:
        raise HTTPException(status_code=404, detail="task intake not found")
    return session


def _create_task_record_from_confirmed_spec(spec: ConfirmedTaskSpec) -> TaskRecord:
    goal, constraints, metadata = project_confirmed_task_spec(spec)
    task_id = f"task_{uuid4().hex[:8]}"
    timestamp = now_iso()
    record = TaskRecord(
        id=task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
        created_at=timestamp,
        updated_at=timestamp,
        goal=goal,
        constraints=constraints,
        metadata=metadata,
        plan=None,
        design_result=None,
        safety_events=[],
    )
    TASK_STORE[task_id] = record
    append_event(
        task_id,
        {
            "event": "TASK_CREATED_FROM_CONFIRMED_INTAKE",
            "task_id": task_id,
            "status": ExternalStatus.CREATED.value,
            "actor_type": "api",
            "timestamp": timestamp,
            "data": {
                "intake_id": metadata.get("intake_id"),
                "support_level": metadata.get("support_level"),
                "input_mode": metadata.get("input_mode"),
            },
        },
    )
    return record


def _task_intake_summary(session: TaskIntakeSession) -> dict[str, Any]:
    return {
        "intake_id": session.intake_id,
        "status": session.status.value,
        "human_summary": session.human_summary,
        "draft": session.draft.model_dump(mode="json"),
        "missing_required_fields": list(session.missing_required_fields),
        "ambiguous_fields": list(session.ambiguous_fields),
        "unmapped_text": list(session.unmapped_text),
        "warnings": list(session.warnings),
        "safety_check": session.safety_check.model_dump(mode="json"),
        "audit_events": [
            event.model_dump(mode="json") for event in session.audit_events
        ],
    }


def _task_intake_validation_errors(
    session: TaskIntakeSession,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for field_name, field in session.draft.fields.items():
        for warning in field.warnings:
            errors.append(
                {
                    "field": field_name,
                    "message": warning,
                    "value": field.value,
                }
            )
    for warning in session.warnings:
        if not any(error["message"] == warning for error in errors):
            errors.append({"field": None, "message": warning, "value": None})
    return errors


def _task_intake_field_validation_messages(
    session: TaskIntakeSession,
) -> list[str]:
    return [
        warning
        for field in session.draft.fields.values()
        for warning in field.warnings
    ]


def _raise_if_task_intake_field_validation_failed(
    session: TaskIntakeSession,
) -> None:
    if _task_intake_field_validation_messages(session):
        _raise_task_intake_error(session, detail="task intake validation failed")


def _raise_task_intake_error(
    session: TaskIntakeSession,
    *,
    detail: str,
    status_code: int = 422,
) -> None:
    raise TaskIntakeAPIError(
        status_code=status_code,
        detail=detail,
        missing_fields=list(session.missing_required_fields),
        validation_errors=_task_intake_validation_errors(session),
        context={
            "intake_id": session.intake_id,
            "status": session.status.value,
            "ambiguous_fields": list(session.ambiguous_fields),
            "safety_check": session.safety_check.model_dump(mode="json"),
        },
    )


def _raise_task_intake_value_error(
    *,
    detail: str,
    field_context: dict[str, Any] | None = None,
) -> None:
    raise TaskIntakeAPIError(
        status_code=422,
        detail=detail,
        validation_errors=[
            {
                "field": field_context.get("field") if field_context else None,
                "message": detail,
                "value": field_context.get("value") if field_context else None,
            }
        ],
        context=field_context or {},
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
async def get_hitl_dashboard() -> HTMLResponse:
    return HTMLResponse(_render_react_app_html(task_id=None, view="dashboard"))


@app.get("/ui/tasks/{task_id}", response_class=HTMLResponse)
async def get_task_detail_view(task_id: str) -> HTMLResponse:
    return HTMLResponse(_render_react_app_html(task_id=task_id, view="task_detail"))


@app.get("/ui/tasks/{task_id}/events", response_class=HTMLResponse)
async def get_task_event_timeline_view(task_id: str) -> HTMLResponse:
    return HTMLResponse(
        _render_react_app_html(task_id=task_id, view="event_timeline")
    )


@app.get("/ui/task-builder", response_class=HTMLResponse)
async def get_task_builder_view() -> HTMLResponse:
    return HTMLResponse(_render_react_app_html(task_id=None, view="task_builder"))


@app.get("/health")
async def health() -> Dict[str, Any]:
    runtime = _ensure_runtime_initialized()
    readiness = build_capability_readiness_matrix()
    return {
        "status": "ok",
        "task_count": len(TASK_STORE),
        "kg_tool_count": runtime.tool_count,
        "capability_readiness_count": len(readiness),
        "paths": {
            "kg": str(runtime.paths.kg_path),
            "output": str(runtime.paths.output_dir),
            "data": str(runtime.paths.data_dir),
            "logs": str(runtime.paths.log_dir),
            "snapshots": str(runtime.paths.snapshot_dir),
        },
    }


@app.get("/capabilities/readiness", response_model=list[CapabilityReadinessEntry])
async def get_capability_readiness() -> list[CapabilityReadinessEntry]:
    entries = build_capability_readiness_matrix()
    return [CapabilityReadinessEntry(**entry) for entry in entries]


@app.get("/task-intakes/schema")
async def get_task_intake_schema() -> dict[str, Any]:
    """返回 Web/CLI 共享的 Task Intake 字段注册表。"""

    return build_task_intake_schema()


@app.post("/task-intakes", response_model=TaskIntakeSession)
async def create_task_intake(req: TaskIntakeCreateRequest) -> TaskIntakeSession:
    """创建正式 Task 之前的 Task Intake 会话。"""

    intake_id = f"intake_{uuid4().hex[:8]}"
    try:
        session = create_task_intake_session(
            intake_id=intake_id,
            text=req.text,
            structured_fields=req.structured_fields,
            source=req.source,
        )
    except ValueError as exc:
        _raise_task_intake_value_error(detail=str(exc))
    _raise_if_task_intake_field_validation_failed(session)
    INTAKE_STORE[intake_id] = session
    return session


@app.get("/task-intakes/{intake_id}", response_model=TaskIntakeSession)
async def get_task_intake(intake_id: str) -> TaskIntakeSession:
    """读取 Task Intake 会话，供 Web Task Builder 刷新。"""

    return _get_intake_or_404(intake_id)


@app.patch("/task-intakes/{intake_id}", response_model=TaskIntakeSession)
async def update_task_intake(
    intake_id: str,
    req: TaskIntakePatchRequest,
) -> TaskIntakeSession:
    """更新 Task Intake 草稿字段。"""

    session = _get_intake_or_404(intake_id)
    candidate = session.model_copy(deep=True)
    try:
        updated = patch_task_intake_session(
            candidate,
            fields=req.fields,
            updated_by=req.updated_by,
        )
    except ValueError as exc:
        _raise_task_intake_value_error(
            detail=str(exc),
            field_context={"intake_id": intake_id},
        )
    _raise_if_task_intake_field_validation_failed(updated)
    INTAKE_STORE[intake_id] = updated
    return updated


@app.post("/task-intakes/{intake_id}/confirm")
async def confirm_task_intake(
    intake_id: str,
    req: TaskIntakeConfirmRequest,
) -> dict[str, Any]:
    """确认 Task Intake 并从 ConfirmedTaskSpec 创建正式 Task。"""

    session = _get_intake_or_404(intake_id)
    try:
        confirmed_spec = confirm_task_intake_session(
            session,
            confirmed_by=req.confirmed_by,
            acknowledged_warnings=req.acknowledged_warnings,
        )
    except ValueError as exc:
        _raise_task_intake_error(session, detail=str(exc))

    record = _create_task_record_from_confirmed_spec(confirmed_spec)
    return {
        "intake_id": intake_id,
        "task_id": record.id,
        "status": record.status.value,
        "human_summary": session.human_summary,
        "confirmed_task_spec": confirmed_spec.model_dump(mode="json"),
    }


@app.post("/task-intakes/{intake_id}/cancel", response_model=TaskIntakeSession)
async def cancel_task_intake(
    intake_id: str,
    req: TaskIntakeCancelAPIRequest,
) -> TaskIntakeSession:
    """取消 Task Intake，会话级审计不进入正式 Task EventLog。"""

    session = _get_intake_or_404(intake_id)
    updated = cancel_task_intake_session(
        session,
        cancelled_by=req.cancelled_by,
        reason=req.reason,
    )
    INTAKE_STORE[intake_id] = updated
    return updated


@app.post("/intent-drafts")
async def create_intent_draft(req: TaskIntakeCreateRequest) -> dict[str, Any]:
    """兼容旧 IntentDraft 创建入口，内部投影到 Task Intake。"""

    intake_id = f"intake_{uuid4().hex[:8]}"
    session = create_task_intake_session(
        intake_id=intake_id,
        text=req.text,
        structured_fields=req.structured_fields,
        source=req.source,
    )
    session.raw_input["intent_draft_id"] = intake_id
    INTAKE_STORE[intake_id] = session
    payload = _task_intake_summary(session)
    payload["intent_draft_id"] = intake_id
    return payload


@app.patch("/intent-drafts/{intent_draft_id}")
async def patch_intent_draft(
    intent_draft_id: str,
    req: IntentDraftClarificationRequest,
) -> dict[str, Any]:
    """兼容旧 IntentDraft 字段更新入口。"""

    return _apply_intent_draft_clarification(intent_draft_id, req)


@app.post("/intent-drafts/{intent_draft_id}/clarification")
@app.post("/intent-drafts/{intent_draft_id}/clarifications")
async def clarify_intent_draft(
    intent_draft_id: str,
    req: IntentDraftClarificationRequest,
) -> dict[str, Any]:
    """兼容旧 clarification 入口，内部更新同一个 intake draft。"""

    return _apply_intent_draft_clarification(intent_draft_id, req)


@app.post("/intent-drafts/{intent_draft_id}/finalize")
async def finalize_intent_draft(
    intent_draft_id: str,
    req: TaskIntakeConfirmRequest,
) -> dict[str, Any]:
    """兼容旧 finalize 入口，经 ConfirmedTaskSpec 创建正式 Task。"""

    session = _get_intake_or_404(intent_draft_id)
    try:
        confirmed_spec = confirm_task_intake_session(
            session,
            confirmed_by=req.confirmed_by,
            acknowledged_warnings=req.acknowledged_warnings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = _create_task_record_from_confirmed_spec(confirmed_spec)
    return {
        "intent_draft_id": intent_draft_id,
        "intake_id": intent_draft_id,
        "task_id": record.id,
        "status": record.status.value,
        "confirmed_task_spec": confirmed_spec.model_dump(mode="json"),
    }


def _apply_intent_draft_clarification(
    intent_draft_id: str,
    req: IntentDraftClarificationRequest,
) -> dict[str, Any]:
    session = _get_intake_or_404(intent_draft_id)
    fields = dict(req.structured_fields)
    fields.update(req.fields)
    if req.text:
        session.raw_input["clarification_text"] = req.text
    try:
        session = patch_task_intake_session(
            session,
            fields=fields,
            updated_by=req.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = _task_intake_summary(session)
    payload["intent_draft_id"] = intent_draft_id
    return payload


@app.post("/tasks")
async def create_task(req: TaskCreateRequest):
    """创建任务；兼容 goal、query 与 confirmed_task_spec 三种入口。"""

    if req.query is not None and req.confirmed_task_spec is None and req.goal is None:
        intake_id = f"intake_{uuid4().hex[:8]}"
        session = create_task_intake_session(
            intake_id=intake_id,
            text=req.query,
            structured_fields=req.constraints,
            source="legacy",
        )
        INTAKE_STORE[intake_id] = session
        payload = _task_intake_summary(session)
        payload["needs_confirmation"] = True
        payload["message"] = "free-text /tasks input was converted to task intake"
        return payload

    if req.confirmed_task_spec is not None:
        return _create_task_record_from_confirmed_spec(req.confirmed_task_spec)

    if req.goal is None:
        raise HTTPException(status_code=422, detail="goal is required")

    task_id = f"task_{uuid4().hex[:8]}"
    task = ProteinDesignTask(
        task_id=task_id,
        goal=req.goal,
        constraints=req.constraints,
        metadata=req.metadata,
    )

    record = run_task_sync(task)
    TASK_STORE[task_id] = record
    return record


@app.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str):
    """查看任务当前状态和摘要"""
    record = TASK_STORE.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return record


@app.get("/tasks/{task_id}/report", response_model=TaskReportDetail)
async def get_task_report(task_id: str) -> TaskReportDetail:
    """查看任务最终报告摘要，包含 objective scoring 闭环字段。"""

    record = TASK_STORE.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    design_result = record.design_result
    if design_result is None:
        raise HTTPException(status_code=404, detail="task report not found")
    metadata = design_result.metadata if isinstance(design_result.metadata, dict) else {}
    objective_scoring = metadata.get("objective_scoring")
    if not isinstance(objective_scoring, dict):
        objective_scoring = {}
    structure_similarity = metadata.get("structure_similarity")
    if not isinstance(structure_similarity, dict):
        structure_similarity = {}
    return TaskReportDetail(
        task_id=task_id,
        report_path=design_result.report_path,
        scores=dict(design_result.scores or {}),
        objective_scoring=objective_scoring,
        structure_similarity=structure_similarity,
        metadata=metadata,
    )


def _event_matches_filters(
    event: dict[str, Any],
    *,
    event_type: Optional[str],
    tool_id: Optional[str],
    capability_id: Optional[str],
    adapter_mode: Optional[str],
    execution_mode: Optional[str],
) -> bool:
    if event_type and event.get("event_type") != event_type:
        return False

    if tool_id:
        related_tools = {
            _normalize_text(event.get("tool")),
            _normalize_text(event.get("tool_id")),
            _normalize_text(event.get("from_tool")),
            _normalize_text(event.get("to_tool")),
        }
        related_tools.discard(None)
        if tool_id not in related_tools:
            return False

    if capability_id and event.get("capability_id") != capability_id:
        return False

    if adapter_mode and event.get("adapter_mode") != adapter_mode:
        return False

    if execution_mode and event.get("execution_mode") != execution_mode:
        return False

    return True


@app.get("/tasks/{task_id}/events", response_model=list[TaskTimelineEvent])
async def get_task_events(
    task_id: str,
    event_type: Optional[str] = Query(default=None),
    tool_id: Optional[str] = Query(default=None),
    capability_id: Optional[str] = Query(default=None),
    adapter_mode: Optional[str] = Query(default=None),
    execution_mode: Optional[str] = Query(default=None),
) -> list[TaskTimelineEvent]:
    runtime = _ensure_runtime_initialized()
    timeline = read_timeline_events(task_id, log_dir=runtime.paths.log_dir)

    if task_id not in TASK_STORE and not timeline:
        raise HTTPException(status_code=404, detail="task not found")

    highlighted = {
        "STATE_TRANSITION",
        "PENDING_ACTION_CREATED",
        "DECISION_APPLIED",
        "STEP_FINISHED",
        "STEP_FAILED",
        "WAITING_ENTER",
        "WAITING_EXIT",
        "REPLACE_TOOL",
        "PARAM_TWEAK",
        "STRUCTURE_PATCH",
        "PLANNER_ROUTE_DECISION",
        "RECOVERY_ESCALATED",
        "CANDIDATE_VALIDATION_FAILED",
    }
    return [
        TaskTimelineEvent(
            **event,
            highlight=event["event_type"] in highlighted,
        )
        for event in timeline
        if _event_matches_filters(
            event,
            event_type=_normalize_text(event_type),
            tool_id=_normalize_text(tool_id),
            capability_id=_normalize_text(capability_id),
            adapter_mode=_normalize_text(adapter_mode),
            execution_mode=_normalize_text(execution_mode),
        )
    ]


@app.get("/pending-actions", response_model=list[PendingActionSummary])
async def list_pending_actions(
    status: Optional[PendingActionStatus] = Query(
        default=PendingActionStatus.PENDING
    ),
    task_id: Optional[str] = Query(default=None),
) -> list[PendingActionSummary]:
    summaries: list[PendingActionSummary] = []

    for record in TASK_STORE.values():
        if task_id is not None and record.id != task_id:
            continue
        pending_action = record.pending_action
        if pending_action is None:
            continue
        if status is not None and pending_action.status != status:
            continue

        summaries.append(
            PendingActionSummary(
                pending_action_id=pending_action.pending_action_id,
                task_id=record.id,
                action_type=pending_action.action_type,
                status=pending_action.status,
                created_at=pending_action.created_at,
                candidate_count=len(pending_action.candidates),
                default_suggestion=(
                    pending_action.default_suggestion
                    or pending_action.default_recommendation
                ),
                explanation=pending_action.explanation,
                summary=_build_pending_action_summary(pending_action),
            )
        )

    return summaries


@app.get("/pending-actions/{pending_action_id}", response_model=PendingActionDetail)
async def get_pending_action_detail(pending_action_id: str) -> PendingActionDetail:
    record = _find_record_by_pending_action_id(pending_action_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"pending_action {pending_action_id} not found"
        )

    pending_action = record.pending_action
    if pending_action is None:
        raise HTTPException(
            status_code=404,
            detail=f"pending_action {pending_action_id} not found in task record",
        )
    return _build_pending_action_detail(record, pending_action)


@app.post("/pending-actions/{pending_action_id}/decision", response_model=TaskRecord)
async def submit_decision(pending_action_id: str, req: DecisionSubmitRequest):
    """提交人工决策以驱动 FSM 前进

    Args:
        pending_action_id: 待决策的 PendingAction ID
        req: 决策请求体

    Returns:
        更新后的 TaskRecord

    Raises:
        HTTPException: 404 当 PendingAction 未找到
        HTTPException: 400 当决策验证失败
        HTTPException: 409 当决策冲突(已决策或状态不匹配)
        HTTPException: 500 当应用决策失败
    """
    # 查找包含该 pending_action 的任务
    record = _find_record_by_pending_action_id(pending_action_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"pending_action {pending_action_id} not found"
        )

    pending_action = record.pending_action

    # 显式检查 PendingAction 状态
    if pending_action is None:
        raise HTTPException(
            status_code=404,
            detail=f"pending_action {pending_action_id} not found in task record",
        )

    if pending_action.status != PendingActionStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"PendingAction {pending_action_id} is not in PENDING status (current: {pending_action.status.value})",
        )

    # 构造 Decision 对象
    try:
        decision = Decision(
            decision_id=f"decision_{uuid4().hex[:8]}",
            task_id=record.id,
            pending_action_id=pending_action_id,
            choice=req.choice,
            selected_candidate_id=req.selected_candidate_id,
            decided_by=req.decided_by,
            comment=req.comment,
            decided_at=now_iso(),
        )
    except Exception as e:
        # Pydantic 验证错误
        raise HTTPException(status_code=400, detail=str(e))

    # 验证决策
    try:
        validate_decision_for_pending_action(pending_action, decision)
    except DecisionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 构造 WorkflowContext
    context = WorkflowContext(
        task=ProteinDesignTask(
            task_id=record.id,
            goal=record.goal,
            constraints=record.constraints or {},
            metadata=record.metadata or {},
        ),
        status=record.internal_status,
        plan=record.plan,
        step_results={},
        design_result=record.design_result,
        safety_events=[],
        pending_action=pending_action,
    )

    # 根据 action_type 路由到对应的 apply 函数
    try:
        if pending_action.action_type == PendingActionType.PLAN_CONFIRM:
            apply_plan_confirm_decision(context, record, decision)
        elif pending_action.action_type == PendingActionType.PATCH_CONFIRM:
            apply_patch_confirm_decision(context, record, decision)
        elif pending_action.action_type == PendingActionType.REPLAN_CONFIRM:
            apply_replan_confirm_decision(context, record, decision)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported action type: {pending_action.action_type.value}",
            )
    except DecisionConflictError as e:
        # 决策冲突：已决策或状态不匹配
        raise HTTPException(status_code=409, detail=str(e))
    except DecisionApplyError as e:
        # 其他决策应用失败
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to apply decision: {str(e)}"
        )

    # 返回更新后的 TaskRecord
    return record
