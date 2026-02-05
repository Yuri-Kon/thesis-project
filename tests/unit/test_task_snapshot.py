import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.models.contracts import ArtifactRef, TaskSnapshot, now_iso
from src.models.db import ExternalStatus
from src.storage.snapshot_store import (
    append_snapshot,
    read_snapshots,
    read_latest_snapshot,
)


@pytest.mark.unit
def test_task_snapshot_can_construct():
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_001",
        task_id="task_001",
        state=ExternalStatus.CREATED.value,
        plan_version=1,
        step_index=0,
        artifacts={
            "log_path": "data/logs/task_001.jsonl",
            "report_ref": ArtifactRef(uri="output/report.json"),
        },
        created_at=now_iso(),
    )

    assert snapshot.step_index == 0
    assert snapshot.current_step_index == 0
    assert snapshot.plan_version == 1


@pytest.mark.unit
def test_task_snapshot_round_trip():
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_002",
        task_id="task_002",
        state=ExternalStatus.RUNNING.value,
        plan_version=2,
        step_index=3,
        artifacts={
            "metrics": {"runtime_ms": 12, "tool": "dummy"},
            "artifact_path": "output/artifacts/a.json",
        },
        created_at=now_iso(),
    )

    payload = snapshot.model_dump()
    restored = TaskSnapshot.model_validate(payload)

    assert restored.model_dump() == payload


@pytest.mark.unit
def test_task_snapshot_rejects_negative_plan_version():
    with pytest.raises(ValueError):
        TaskSnapshot(
            snapshot_id="snapshot_003",
            task_id="task_003",
            state=ExternalStatus.CREATED.value,
            plan_version=-1,
            step_index=0,
            artifacts={},
            created_at=now_iso(),
        )


@pytest.mark.unit
def test_task_snapshot_rejects_negative_step_index():
    with pytest.raises(ValueError):
        TaskSnapshot(
            snapshot_id="snapshot_004",
            task_id="task_004",
            state=ExternalStatus.CREATED.value,
            plan_version=0,
            step_index=-2,
            artifacts={},
            created_at=now_iso(),
        )


@pytest.mark.unit
def test_snapshot_append_and_read():
    """测试快照的追加写入和读取功能"""
    with TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir)
        task_id = "task_read_test_001"

        # 创建并写入第一个快照
        snapshot1 = TaskSnapshot(
            snapshot_id="snapshot_001",
            task_id=task_id,
            state=ExternalStatus.CREATED.value,
            plan_version=0,
            step_index=0,
            artifacts={},
            created_at=now_iso(),
        )
        append_snapshot(snapshot1, snapshot_dir=snapshot_dir)

        # 创建并写入第二个快照
        snapshot2 = TaskSnapshot(
            snapshot_id="snapshot_002",
            task_id=task_id,
            state=ExternalStatus.RUNNING.value,
            plan_version=1,
            step_index=2,
            artifacts={"remote_jobs": {"S1": {"job_id": "job_123"}}},
            created_at=now_iso(),
        )
        append_snapshot(snapshot2, snapshot_dir=snapshot_dir)

        # 读取所有快照
        snapshots = read_snapshots(task_id, snapshot_dir=snapshot_dir)
        assert len(snapshots) == 2
        assert snapshots[0].snapshot_id == "snapshot_001"
        assert snapshots[1].snapshot_id == "snapshot_002"
        assert snapshots[1].artifacts["remote_jobs"]["S1"]["job_id"] == "job_123"


@pytest.mark.unit
def test_read_latest_snapshot():
    """测试读取最新快照"""
    with TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir)
        task_id = "task_latest_test_001"

        # 写入多个快照
        for i in range(3):
            snapshot = TaskSnapshot(
                snapshot_id=f"snapshot_{i:03d}",
                task_id=task_id,
                state=ExternalStatus.RUNNING.value,
                plan_version=i,
                step_index=i,
                artifacts={},
                created_at=now_iso(),
            )
            append_snapshot(snapshot, snapshot_dir=snapshot_dir)

        # 读取最新快照
        latest = read_latest_snapshot(task_id, snapshot_dir=snapshot_dir)
        assert latest is not None
        assert latest.snapshot_id == "snapshot_002"
        assert latest.plan_version == 2


@pytest.mark.unit
def test_read_nonexistent_snapshot():
    """测试读取不存在的快照"""
    with TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir)
        task_id = "nonexistent_task"

        # 读取不存在的快照应返回空列表
        snapshots = read_snapshots(task_id, snapshot_dir=snapshot_dir)
        assert snapshots == []

        # 读取不存在的最新快照应返回 None
        latest = read_latest_snapshot(task_id, snapshot_dir=snapshot_dir)
        assert latest is None


@pytest.mark.unit
def test_snapshot_with_remote_job_artifacts():
    """测试带有远程作业信息的快照"""
    snapshot = TaskSnapshot(
        snapshot_id="snapshot_remote_001",
        task_id="task_remote_001",
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

    # 验证快照可以序列化和反序列化
    payload = snapshot.model_dump()
    restored = TaskSnapshot.model_validate(payload)

    assert restored.artifacts["remote_jobs"]["S1"]["job_id"] == "esmfold_job_123"
    assert restored.artifacts["remote_jobs"]["S1"]["endpoint"] == "http://example.com/esmfold"
    assert restored.artifacts["remote_jobs"]["S1"]["status"] == "running"
