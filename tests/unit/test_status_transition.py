"""Task status transition entrypoint tests."""
import pytest

from src.models.contracts import now_iso
from src.models.db import TaskRecord, TaskStatus
from src.workflow.context import WorkflowContext
from src.workflow.status import transition_task_status


@pytest.mark.unit
class TestTaskStatusTransition:
    def _make_record(self, task_id: str, status: TaskStatus) -> TaskRecord:
        return TaskRecord(
            id=task_id,
            status=status,
            created_at=now_iso(),
            updated_at=now_iso(),
            goal="test",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            safety_events=[],
        )

    def test_transition_updates_context_and_record(self, sample_task):
        record = self._make_record(sample_task.task_id, TaskStatus.CREATED)
        context = WorkflowContext(task=sample_task, status=TaskStatus.CREATED)
        events: list[dict] = []

        transition_task_status(
            context, record, TaskStatus.PLANNING, logger=events.append
        )

        assert context.status == TaskStatus.PLANNING
        assert record.status == TaskStatus.PLANNING
        assert events == [
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": sample_task.task_id,
                "from_status": "CREATED",
                "to_status": "PLANNING",
            }
        ]

    def test_transition_rejects_invalid_jump(self, sample_task):
        record = self._make_record(sample_task.task_id, TaskStatus.CREATED)
        context = WorkflowContext(task=sample_task, status=TaskStatus.CREATED)

        with pytest.raises(ValueError):
            transition_task_status(context, record, TaskStatus.RUNNING)

    def test_transition_rejects_status_mismatch(self, sample_task):
        record = self._make_record(sample_task.task_id, TaskStatus.PLANNED)
        context = WorkflowContext(task=sample_task, status=TaskStatus.CREATED)

        with pytest.raises(ValueError):
            transition_task_status(context, record, TaskStatus.PLANNING)
