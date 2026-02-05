"""Integration tests for EventLog integration in workflow.

This module verifies that WAITING_ENTER, WAITING_EXIT, and DECISION_APPLIED
events are properly logged during state transitions and decision application.
"""
import json
from pathlib import Path

import pytest

from src.models.contracts import (
    Decision,
    DecisionChoice,
    PendingActionStatus,
    PendingActionType,
    ProteinDesignTask,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.models.event_log import EventType
from src.workflow.context import WorkflowContext
from src.workflow.decision_apply import apply_plan_confirm_decision
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.storage.log_store import DEFAULT_LOG_DIR


@pytest.fixture
def cleanup_logs():
    """Cleanup test logs after test."""
    yield
    # Clean up test log files
    if DEFAULT_LOG_DIR.exists():
        for log_file in DEFAULT_LOG_DIR.glob("test_*.jsonl"):
            log_file.unlink()


def test_enter_waiting_state_emits_waiting_enter_event(cleanup_logs):
    """Test that enter_waiting_state emits WAITING_ENTER EventLog."""
    task = ProteinDesignTask(
        task_id="test_enter_waiting_001",
        goal="test enter waiting state logging",
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        status=InternalStatus.PLANNING,
        plan=None,
        step_results={},
        design_result=None,
        safety_events=[],
        pending_action=None,
    )
    record = TaskRecord(
        id=task.task_id,
        goal=task.goal,
        status=ExternalStatus.PLANNING,
        internal_status=InternalStatus.PLANNING,
        plan=None,
        pending_action=None,
        design_result=None,
    )

    # Build and enter WAITING_PLAN_CONFIRM state
    pending_action = build_pending_action(
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[],
        explanation="test waiting enter",
    )
    enter_waiting_state(
        context,
        record,
        pending_action,
        InternalStatus.WAITING_PLAN_CONFIRM,
        reason="test_enter_waiting",
    )

    # Read the log file
    log_file = DEFAULT_LOG_DIR / f"{task.task_id}.jsonl"
    assert log_file.exists(), "Log file should be created"

    # Parse all log entries
    log_entries = []
    with log_file.open("r") as f:
        for line in f:
            log_entries.append(json.loads(line))

    # Find WAITING_ENTER event
    waiting_enter_events = [
        e for e in log_entries if e.get("event_type") == EventType.WAITING_ENTER.value
    ]
    assert len(waiting_enter_events) == 1, "Should have exactly one WAITING_ENTER event"

    event = waiting_enter_events[0]
    assert event["task_id"] == task.task_id
    assert event["pending_action_id"] == pending_action.pending_action_id
    assert event["prev_status"] == ExternalStatus.PLANNING.value
    assert event["new_status"] == ExternalStatus.WAITING_PLAN_CONFIRM.value
    assert event["internal_status"] == InternalStatus.WAITING_PLAN_CONFIRM.value
    assert event["data"]["waiting_state"] == InternalStatus.WAITING_PLAN_CONFIRM.value
    assert event["actor_type"] == "system"


def test_decision_apply_emits_waiting_exit_and_decision_applied(cleanup_logs):
    """Test that applying a decision emits both WAITING_EXIT and DECISION_APPLIED events."""
    task = ProteinDesignTask(
        task_id="test_decision_apply_002",
        goal="test decision apply logging",
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        status=InternalStatus.WAITING_PLAN_CONFIRM,
        plan=None,
        step_results={},
        design_result=None,
        safety_events=[],
        pending_action=None,
    )
    record = TaskRecord(
        id=task.task_id,
        goal=task.goal,
        status=ExternalStatus.WAITING_PLAN_CONFIRM,
        internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
        plan=None,
        pending_action=None,
        design_result=None,
    )

    # Build pending action with a candidate plan
    from src.models.contracts import Plan, PlanStep, PendingActionCandidate

    candidate_plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="dummy_tool",
                inputs={"sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR"},
                metadata={},
            )
        ],
        constraints={},
        metadata={},
    )
    pending_action = build_pending_action(
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[
            PendingActionCandidate(
                candidate_id="candidate_1",
                payload=candidate_plan,
                summary="test plan",
                score_breakdown={},
            )
        ],
        default_suggestion="candidate_1",
        explanation="test decision apply",
    )
    context.pending_action = pending_action
    record.pending_action = pending_action

    # Apply decision to accept the plan
    decision = Decision(
        decision_id="decision_001",
        task_id=task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id="candidate_1",
        decided_by="test_user",
    )

    apply_plan_confirm_decision(context, record, decision)

    # Read the log file
    log_file = DEFAULT_LOG_DIR / f"{task.task_id}.jsonl"
    assert log_file.exists(), "Log file should be created"

    # Parse all log entries
    log_entries = []
    with log_file.open("r") as f:
        for line in f:
            log_entries.append(json.loads(line))

    # Find DECISION_APPLIED event
    decision_applied_events = [
        e
        for e in log_entries
        if e.get("event_type") == EventType.DECISION_APPLIED.value
    ]
    assert (
        len(decision_applied_events) == 1
    ), "Should have exactly one DECISION_APPLIED event"

    decision_event = decision_applied_events[0]
    assert decision_event["task_id"] == task.task_id
    assert decision_event["decision_id"] == decision.decision_id
    assert decision_event["pending_action_id"] == pending_action.pending_action_id
    assert decision_event["prev_status"] == ExternalStatus.WAITING_PLAN_CONFIRM.value
    assert decision_event["new_status"] == ExternalStatus.PLANNED.value
    assert decision_event["data"]["choice"] == DecisionChoice.ACCEPT.value
    assert decision_event["actor_type"] == "human"

    # Find WAITING_EXIT event
    waiting_exit_events = [
        e for e in log_entries if e.get("event_type") == EventType.WAITING_EXIT.value
    ]
    assert len(waiting_exit_events) == 1, "Should have exactly one WAITING_EXIT event"

    exit_event = waiting_exit_events[0]
    assert exit_event["task_id"] == task.task_id
    assert exit_event["pending_action_id"] == pending_action.pending_action_id
    assert exit_event["prev_status"] == ExternalStatus.WAITING_PLAN_CONFIRM.value
    assert exit_event["new_status"] == ExternalStatus.PLANNED.value
    assert (
        exit_event["data"]["waiting_state"] == InternalStatus.WAITING_PLAN_CONFIRM.value
    )
    assert exit_event["data"]["action_status"] == PendingActionStatus.DECIDED.value


def test_fsm_reconstruction_from_logs(cleanup_logs):
    """Test that logs can reconstruct FSM state transitions."""
    task = ProteinDesignTask(
        task_id="test_fsm_reconstruction_003",
        goal="test FSM reconstruction from logs",
        constraints={},
        metadata={},
    )
    context = WorkflowContext(
        task=task,
        status=InternalStatus.PLANNING,
        plan=None,
        step_results={},
        design_result=None,
        safety_events=[],
        pending_action=None,
    )

    # Build and enter WAITING_PLAN_CONFIRM
    pending_action = build_pending_action(
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[],
        explanation="test FSM reconstruction",
    )
    enter_waiting_state(
        context,
        None,
        pending_action,
        InternalStatus.WAITING_PLAN_CONFIRM,
        reason="entering_waiting_for_plan",
    )

    # Read the log file and verify we can reconstruct the state machine
    log_file = DEFAULT_LOG_DIR / f"{task.task_id}.jsonl"
    log_entries = []
    with log_file.open("r") as f:
        for line in f:
            log_entries.append(json.loads(line))

    # Extract state transitions from logs
    state_transitions = []
    for entry in log_entries:
        if entry.get("event") == "TASK_STATUS_CHANGED":
            state_transitions.append(
                (entry["from_status"], entry["to_status"], entry.get("reason"))
            )
        elif entry.get("event_type") == EventType.WAITING_ENTER.value:
            state_transitions.append(
                (
                    entry["prev_status"],
                    entry["new_status"],
                    "WAITING_ENTER",
                )
            )

    # Verify we can see the state transition sequence
    assert len(state_transitions) >= 1, "Should have at least one state transition"

    # Verify WAITING_ENTER is present in the log
    waiting_transitions = [
        t for t in state_transitions if t[2] == "WAITING_ENTER"
    ]
    assert len(waiting_transitions) == 1, "Should have exactly one WAITING_ENTER transition"
    assert waiting_transitions[0][0] == ExternalStatus.PLANNING.value
    assert waiting_transitions[0][1] == ExternalStatus.WAITING_PLAN_CONFIRM.value
