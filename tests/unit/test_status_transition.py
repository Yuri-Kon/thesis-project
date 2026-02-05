"""Task status transition entrypoint tests."""
import pytest

from src.models.contracts import now_iso
from src.models.db import (
    ExternalStatus,
    InternalStatus,
    TaskRecord,
    to_external_status,
)
from src.workflow.context import WorkflowContext
from src.workflow.status import transition_task_status


@pytest.mark.unit
class TestTaskStatusTransition:
    def _make_record(self, task_id: str, status: InternalStatus) -> TaskRecord:
        return TaskRecord(
            id=task_id,
            status=to_external_status(status),
            internal_status=status,
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
        record = self._make_record(sample_task.task_id, InternalStatus.CREATED)
        context = WorkflowContext(task=sample_task, status=InternalStatus.CREATED)
        events: list[dict] = []

        transition_task_status(
            context, record, InternalStatus.PLANNING, logger=events.append
        )

        assert context.status == InternalStatus.PLANNING
        assert record.status == ExternalStatus.PLANNING
        assert record.internal_status == InternalStatus.PLANNING
        assert events == [
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": sample_task.task_id,
                "from_status": "CREATED",
                "to_status": "PLANNING",
                "state": "PLANNING",
                "external_status": "PLANNING",
                "reason": None,
            }
        ]

    def test_transition_rejects_invalid_jump(self, sample_task):
        record = self._make_record(sample_task.task_id, InternalStatus.CREATED)
        context = WorkflowContext(task=sample_task, status=InternalStatus.CREATED)

        with pytest.raises(ValueError):
            transition_task_status(context, record, InternalStatus.RUNNING)

    def test_transition_rejects_status_mismatch(self, sample_task):
        record = self._make_record(sample_task.task_id, InternalStatus.PLANNED)
        context = WorkflowContext(task=sample_task, status=InternalStatus.CREATED)

        with pytest.raises(ValueError):
            transition_task_status(context, record, InternalStatus.PLANNING)

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (InternalStatus.CREATED, InternalStatus.PLANNING),
            (InternalStatus.PLANNING, InternalStatus.PLANNED),
            (InternalStatus.PLANNING, InternalStatus.WAITING_PLAN_CONFIRM),
            (InternalStatus.WAITING_PLAN_CONFIRM, InternalStatus.PLANNED),
            (InternalStatus.WAITING_PLAN_CONFIRM, InternalStatus.PLANNING),
            (InternalStatus.PLANNING, InternalStatus.FAILED),
            (InternalStatus.PLANNED, InternalStatus.RUNNING),
            (InternalStatus.RUNNING, InternalStatus.WAITING_PATCH),
            (InternalStatus.RUNNING, InternalStatus.WAITING_REPLAN),
            (InternalStatus.RUNNING, InternalStatus.SUMMARIZING),
            (InternalStatus.WAITING_PATCH, InternalStatus.PATCHING),
            (InternalStatus.PATCHING, InternalStatus.RUNNING),
            (InternalStatus.PATCHING, InternalStatus.WAITING_REPLAN),
            (InternalStatus.WAITING_REPLAN, InternalStatus.REPLANNING),
            (InternalStatus.REPLANNING, InternalStatus.RUNNING),
            (InternalStatus.REPLANNING, InternalStatus.FAILED),
            (InternalStatus.SUMMARIZING, InternalStatus.DONE),
        ],
    )
    def test_transition_allows_expected_pairs(
        self, sample_task, from_status: InternalStatus, to_status: InternalStatus
    ):
        record = self._make_record(sample_task.task_id, from_status)
        context = WorkflowContext(task=sample_task, status=from_status)

        transition_task_status(context, record, to_status)

        assert context.status == to_status
        assert record.status == to_external_status(to_status)
        assert record.internal_status == to_status

    @pytest.mark.parametrize(
        "start,sequence",
        [
            (
                InternalStatus.PLANNED,
                [
                    InternalStatus.RUNNING,
                    InternalStatus.SUMMARIZING,
                    InternalStatus.DONE,
                ],
            ),
            (
                InternalStatus.RUNNING,
                [
                    InternalStatus.WAITING_PATCH,
                    InternalStatus.PATCHING,
                    InternalStatus.RUNNING,
                ],
            ),
            (
                InternalStatus.RUNNING,
                [
                    InternalStatus.WAITING_REPLAN,
                    InternalStatus.REPLANNING,
                    InternalStatus.RUNNING,
                ],
            ),
            (
                InternalStatus.REPLANNING,
                [InternalStatus.FAILED],
            ),
            (
                InternalStatus.RUNNING,
                [InternalStatus.WAITING_REPLAN, InternalStatus.REPLANNING],
            ),
        ],
    )
    def test_transition_allows_expected_sequences(
        self, sample_task, start: InternalStatus, sequence: list[InternalStatus]
    ):
        record = self._make_record(sample_task.task_id, start)
        context = WorkflowContext(task=sample_task, status=start)

        for target in sequence:
            transition_task_status(context, record, target)

        assert context.status == sequence[-1]
        assert record.status == to_external_status(sequence[-1])
        assert record.internal_status == sequence[-1]
