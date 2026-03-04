from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.models.contracts import (
    ProteinDesignTask,
    Decision,
    DecisionChoice,
    PendingActionStatus,
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
from src.workflow.context import WorkflowContext

app = FastAPI(title="Protein Design Agent System (Mini Demo)", version="0.5.2")

# 简单的内存存储，之后可以换成数据库或文件
TASK_STORE: Dict[str, TaskRecord] = {}
RUNTIME_INIT: Optional[RuntimeInitResult] = None


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
    goal: str = Field(..., description="蛋白质设计任务目标(自然语言)")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="结构化约束")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DecisionSubmitRequest(BaseModel):
    """提交人工决策的请求体"""

    choice: DecisionChoice = Field(..., description="决策选择")
    selected_candidate_id: Optional[str] = Field(
        None, description="当choice为accept时必填"
    )
    decided_by: str = Field(..., description="决策者标识")
    comment: Optional[str] = Field(None, description="可选的决策备注")


@app.get("/health")
async def health() -> Dict[str, Any]:
    runtime = _ensure_runtime_initialized()
    return {
        "status": "ok",
        "task_count": len(TASK_STORE),
        "kg_tool_count": runtime.tool_count,
        "paths": {
            "kg": str(runtime.paths.kg_path),
            "output": str(runtime.paths.output_dir),
            "data": str(runtime.paths.data_dir),
            "logs": str(runtime.paths.log_dir),
            "snapshots": str(runtime.paths.snapshot_dir),
        },
    }


@app.post("/tasks", response_model=TaskRecord)
async def create_task(req: TaskCreateRequest):
    """创建一个任务并同步执行"""

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
    record = None
    for task_record in TASK_STORE.values():
        if (
            task_record.pending_action
            and task_record.pending_action.pending_action_id == pending_action_id
        ):
            record = task_record
            break

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
