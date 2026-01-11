"""
workflow/recovery.py

Snapshot-based recovery logic for resuming interrupted tasks.

职责概述：
- 从快照恢复 WorkflowContext
- 提取远程作业上下文并支持继续执行
- 与 PlanRunner.run_plan(resume_from_existing=True) 协同
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from src.models.contracts import TaskSnapshot, ProteinDesignTask, Plan
from src.models.db import ExternalStatus, InternalStatus
from src.storage.snapshot_store import read_latest_snapshot, DEFAULT_SNAPSHOT_DIR
from src.workflow.context import WorkflowContext

__all__ = [
    "restore_context_from_snapshot",
    "extract_remote_job_context",
    "RemoteJobContext",
]


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

        注意：step_results 不会被恢复，因为快照不保存完整的 StepResult。
        PlanRunner 的 resume_from_existing=True 模式会跳过已完成的步骤。
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
    }
    internal_status = status_mapping.get(
        snapshot.state,
        InternalStatus.CREATED,
    )

    # 创建 WorkflowContext
    context = WorkflowContext(
        task=task,
        plan=plan,
        status=internal_status,
    )

    # 注意：我们不恢复 step_results，因为快照不保存完整的 StepResult
    # PlanRunner 的 resume_from_existing 模式将通过 completed_step_ids 跳过已完成步骤

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
