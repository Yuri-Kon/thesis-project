"""
Integration tests for snapshot recovery with remote jobs.

测试快照恢复功能，特别是远程作业的断点续传。
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, MagicMock

from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from src.engines.remote_model_service import JobStatus
from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    TaskSnapshot,
    now_iso,
)
from src.models.db import ExternalStatus
from src.storage.snapshot_store import (
    append_snapshot,
    read_latest_snapshot,
)
from src.workflow.context import WorkflowContext
from src.workflow.recovery import (
    restore_context_from_snapshot,
    extract_remote_job_context,
    RemoteJobContext,
)


@pytest.mark.integration
def test_remote_job_context_serialization():
    """测试远程作业上下文的序列化和反序列化"""
    job_ctx = RemoteJobContext(
        job_id="job_123",
        endpoint="http://example.com/esmfold",
        step_id="S1",
        status="running",
        submitted_at="2026-01-11T10:00:00+00:00",
        metadata={"retry_count": 0},
    )

    # 序列化
    data = job_ctx.to_dict()
    assert data["job_id"] == "job_123"
    assert data["endpoint"] == "http://example.com/esmfold"
    assert data["step_id"] == "S1"
    assert data["status"] == "running"
    assert data["metadata"]["retry_count"] == 0

    # 反序列化
    restored = RemoteJobContext.from_dict(data)
    assert restored.job_id == "job_123"
    assert restored.endpoint == "http://example.com/esmfold"
    assert restored.step_id == "S1"
    assert restored.status == "running"
    assert restored.metadata["retry_count"] == 0


@pytest.mark.integration
def test_extract_remote_job_context_from_snapshot():
    """测试从快照中提取远程作业上下文"""
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_001",
        task_id="task_001",
        state=ExternalStatus.RUNNING.value,
        plan_version=1,
        step_index=1,
        artifacts={
            "remote_jobs": {
                "S1": {
                    "job_id": "esmfold_job_123",
                    "endpoint": "http://example.com/esmfold",
                    "step_id": "S1",
                    "status": "running",
                    "submitted_at": "2026-01-11T10:00:00+00:00",
                }
            }
        },
        created_at=now_iso(),
    )

    # 提取远程作业上下文
    job_ctx = extract_remote_job_context(snapshot, "S1")
    assert job_ctx is not None
    assert job_ctx.job_id == "esmfold_job_123"
    assert job_ctx.endpoint == "http://example.com/esmfold"
    assert job_ctx.step_id == "S1"
    assert job_ctx.status == "running"

    # 提取不存在的步骤
    job_ctx_nonexistent = extract_remote_job_context(snapshot, "S2")
    assert job_ctx_nonexistent is None


@pytest.mark.integration
def test_restore_context_from_snapshot():
    """测试从快照恢复 WorkflowContext"""
    with TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir)
        task_id = "task_restore_001"

        # 创建任务和计划
        task = ProteinDesignTask(
            task_id=task_id,
            goal="Design a stable protein",
        )
        plan = Plan(
            task_id=task_id,
            steps=[
                PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDEF"}),
            ],
        )

        # 创建快照
        snapshot = TaskSnapshot(
            snapshot_id="snapshot_001",
            task_id=task_id,
            state=ExternalStatus.RUNNING.value,
            plan_version=1,
            step_index=0,
            completed_step_ids=[],
            artifacts={},
            created_at=now_iso(),
        )
        append_snapshot(snapshot, snapshot_dir=snapshot_dir)

        # 恢复上下文
        context = restore_context_from_snapshot(
            task=task,
            plan=plan,
            snapshot_dir=snapshot_dir,
        )

        assert context is not None
        assert context.task.task_id == task_id
        assert context.plan == plan


@pytest.mark.integration
def test_snapshot_recovery_workflow_with_mock_service():
    """测试完整的快照恢复工作流（使用 Mock 服务）"""
    with TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir)
        task_id = "task_recovery_workflow_001"
        step_id = "S1"

        # 创建任务和计划
        task = ProteinDesignTask(
            task_id=task_id,
            goal="Predict protein structure",
        )
        plan = Plan(
            task_id=task_id,
            steps=[
                PlanStep(id=step_id, tool="esmfold", inputs={"sequence": "ACDEF"}),
            ],
        )
        context = WorkflowContext(task=task, plan=plan)

        # 创建 Mock 服务
        mock_service = Mock()
        mock_service.base_url = "http://mock-esmfold.example.com"
        mock_service.submit_job = Mock(return_value="job_123")
        mock_service.poll_status = Mock(
            side_effect=[JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED]
        )
        mock_service.download_results = Mock(
            return_value={
                "pdb_path": "/tmp/output/structure.pdb",
                "metrics": {"pLDDT": 0.85},
            }
        )
        # 模拟 wait_for_completion 方法
        mock_service.wait_for_completion = Mock(return_value=JobStatus.COMPLETED)

        # 创建快照写入器
        snapshots_written = []

        def snapshot_writer(snapshot: TaskSnapshot) -> None:
            snapshots_written.append(snapshot)
            append_snapshot(snapshot, snapshot_dir=snapshot_dir)

        # 第一阶段：提交作业并写入快照
        adapter = RemoteESMFoldAdapter(
            service=mock_service,
            snapshot_writer=snapshot_writer,
            enable_snapshot=True,
        )

        # 解析输入（这会保存 context 引用）
        step = plan.steps[0]
        inputs = adapter.resolve_inputs(step, context)

        # 模拟提交作业但不等待完成（模拟中断）
        # 为了测试，我们手动调用 submit_job 并写入快照
        job_id = mock_service.submit_job(
            payload={"sequence": inputs["sequence"]},
            task_id=task_id,
            step_id=step_id,
        )
        assert job_id == "job_123"

        # 手动写入快照（模拟适配器在提交后的行为）
        from src.workflow.snapshots import build_task_snapshot

        job_ctx = RemoteJobContext(
            job_id=job_id,
            endpoint=mock_service.base_url,
            step_id=step_id,
            status="pending",
            submitted_at=now_iso(),
        )
        snapshot = build_task_snapshot(
            context,
            artifacts={
                "remote_jobs": {
                    step_id: job_ctx.to_dict(),
                }
            },
        )
        snapshot_writer(snapshot)

        # 验证快照已写入
        assert len(snapshots_written) == 1
        latest_snapshot = read_latest_snapshot(task_id, snapshot_dir=snapshot_dir)
        assert latest_snapshot is not None
        assert "remote_jobs" in latest_snapshot.artifacts
        assert step_id in latest_snapshot.artifacts["remote_jobs"]

        # 第二阶段：从快照恢复并继续执行
        # 读取快照
        recovered_snapshot = read_latest_snapshot(task_id, snapshot_dir=snapshot_dir)
        assert recovered_snapshot is not None

        # 提取远程作业上下文
        recovered_job_ctx = extract_remote_job_context(recovered_snapshot, step_id)
        assert recovered_job_ctx is not None
        assert recovered_job_ctx.job_id == "job_123"

        # 创建新的适配器实例（模拟重启）
        new_adapter = RemoteESMFoldAdapter(
            service=mock_service,
            snapshot_writer=snapshot_writer,
            enable_snapshot=False,  # 恢复时禁用快照写入
        )

        # 使用恢复的 job_id 继续执行
        outputs, metrics = new_adapter.run_remote(
            inputs=inputs,
            resume_job_id=recovered_job_ctx.job_id,
        )

        # 验证结果
        assert outputs["pdb_path"] == "/tmp/output/structure.pdb"
        assert outputs["metrics"]["pLDDT"] == 0.85
        assert metrics["job_id"] == "job_123"
        assert metrics["resumed"] is True

        # 验证 wait_for_completion 被调用（恢复后继续等待作业完成）
        mock_service.wait_for_completion.assert_called_once_with("job_123")
        # 验证 download_results 被调用
        mock_service.download_results.assert_called_once()
