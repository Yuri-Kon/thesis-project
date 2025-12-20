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
                "state": "PLANNING",
                "reason": None,
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

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (TaskStatus.CREATED, TaskStatus.PLANNING),
            (TaskStatus.PLANNING, TaskStatus.PLANNED),
            (TaskStatus.PLANNING, TaskStatus.FAILED),
            (TaskStatus.PLANNED, TaskStatus.RUNNING),
            (TaskStatus.RUNNING, TaskStatus.WAITING_PATCH),
            (TaskStatus.RUNNING, TaskStatus.WAITING_REPLAN),
            (TaskStatus.RUNNING, TaskStatus.SUMMARIZING),
            (TaskStatus.WAITING_PATCH, TaskStatus.PATCHING),
            (TaskStatus.PATCHING, TaskStatus.RUNNING),
            (TaskStatus.PATCHING, TaskStatus.WAITING_REPLAN),
            (TaskStatus.WAITING_REPLAN, TaskStatus.REPLANNING),
            (TaskStatus.REPLANNING, TaskStatus.RUNNING),
            (TaskStatus.REPLANNING, TaskStatus.FAILED),
            (TaskStatus.SUMMARIZING, TaskStatus.DONE),
        ],
    )
    def test_transition_allows_expected_pairs(
        self, sample_task, from_status: TaskStatus, to_status: TaskStatus
    ):
        record = self._make_record(sample_task.task_id, from_status)
        context = WorkflowContext(task=sample_task, status=from_status)

        transition_task_status(context, record, to_status)

        assert context.status == to_status
        assert record.status == to_status

    @pytest.mark.parametrize(
        "start,sequence",
        [
            (
                TaskStatus.PLANNED,
                [TaskStatus.RUNNING, TaskStatus.SUMMARIZING, TaskStatus.DONE],
            ),
            (
                TaskStatus.RUNNING,
                [TaskStatus.WAITING_PATCH, TaskStatus.PATCHING, TaskStatus.RUNNING],
            ),
            (
                TaskStatus.RUNNING,
                [TaskStatus.WAITING_REPLAN, TaskStatus.REPLANNING, TaskStatus.RUNNING],
            ),
            (
                TaskStatus.REPLANNING,
                [TaskStatus.FAILED],
            ),
            (
                TaskStatus.RUNNING,
                [TaskStatus.WAITING_REPLAN, TaskStatus.REPLANNING],
            ),
        ],
    )
    def test_transition_allows_expected_sequences(
        self, sample_task, start: TaskStatus, sequence: list[TaskStatus]
    ):
        record = self._make_record(sample_task.task_id, start)
        context = WorkflowContext(task=sample_task, status=start)

        for target in sequence:
            transition_task_status(context, record, target)

        assert context.status == sequence[-1]
        assert record.status == sequence[-1]
