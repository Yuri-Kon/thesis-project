import pytest

from src.models.contracts import ArtifactRef, TaskSnapshot, now_iso
from src.models.db import ExternalStatus


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
