from __future__ import annotations

from typing import Dict, List

import pytest

from src.agents.planner import PlannerAgent, ToolSpec
from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.models.contracts import ProteinDesignTask, StepResult
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext


class _FixedPlanProvider(BaseProvider):
    def __init__(self, model_name: str):
        self.config = ProviderConfig(model_name=model_name)
        self.call_count = 0

    def call_planner(self, task: ProteinDesignTask, tool_registry: List[ToolSpec]) -> Dict:
        self.call_count += 1
        tool_id = tool_registry[0].id if tool_registry else "dummy_tool"
        return {
            "task_id": task.task_id,
            "steps": [
                {
                    "id": "S1",
                    "tool": tool_id,
                    "inputs": {"sequence": task.constraints.get("sequence", "MKTAYIAK")},
                    "metadata": {},
                }
            ],
            "constraints": task.constraints,
            "metadata": {"provider": self.config.model_name},
        }


def _task_record(task: ProteinDesignTask) -> TaskRecord:
    return TaskRecord(
        id=task.task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
        goal=task.goal,
        constraints=task.constraints,
        metadata={},
    )


@pytest.mark.integration
def test_dual_route_triggers_external_on_consecutive_failures(monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr("src.agents.planner.append_event", lambda _task_id, payload: events.append(dict(payload)))

    local_provider = _FixedPlanProvider("planner_local")
    external_provider = _FixedPlanProvider("planner_external")
    planner = PlannerAgent(llm_provider=local_provider, fallback_llm_provider=external_provider)

    task = ProteinDesignTask(
        task_id="dual_route_failures_001",
        goal="test dual route fallback",
        constraints={
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLE",
            "plan_top_k": 1,
            "runtime_fallback": {
                "enable_dual_route": True,
                "consecutive_failure_threshold": 2,
                "sustained_high_risk_threshold": 2,
            },
        },
        metadata={},
    )
    context = WorkflowContext(task=task)
    context.step_results["S1"] = StepResult(
        task_id=task.task_id,
        step_id="S1",
        tool="dummy_tool",
        status="failed",
        timestamp="2026-03-16T00:00:01+00:00",
    )
    context.step_results["S2"] = StepResult(
        task_id=task.task_id,
        step_id="S2",
        tool="dummy_tool",
        status="failed",
        timestamp="2026-03-16T00:00:02+00:00",
    )

    plan = planner.plan_with_status(task, context, record=_task_record(task))

    route_meta = plan.metadata.get("planner_route", {})
    assert route_meta.get("provider_tier") == "external"
    assert route_meta.get("provider_name") == "planner_external"
    assert local_provider.call_count == 0
    assert external_provider.call_count >= 1

    route_events = [event for event in events if event.get("event") == "PLANNER_ROUTE_DECISION"]
    assert route_events
    latest = route_events[-1]
    assert latest.get("from_tool")
    assert latest.get("to_tool") == "planner_external"
    assert latest.get("capability_id") == "planner_generation"
    data = latest.get("data") or {}
    assert data.get("trigger_reason") == "consecutive_execution_failures"
    assert "consecutive_execution_failures" in data.get("trigger_threshold", "")


@pytest.mark.integration
def test_dual_route_recovers_back_to_local_after_trigger_cleared(monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr("src.agents.planner.append_event", lambda _task_id, payload: events.append(dict(payload)))

    local_provider = _FixedPlanProvider("planner_local")
    external_provider = _FixedPlanProvider("planner_external")
    planner = PlannerAgent(llm_provider=local_provider, fallback_llm_provider=external_provider)

    first_task = ProteinDesignTask(
        task_id="dual_route_recover_001",
        goal="test dual route recovery",
        constraints={
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLE",
            "plan_top_k": 1,
            "runtime_fallback": {
                "enable_dual_route": True,
                "force_external_only": True,
            },
        },
        metadata={},
    )
    first_context = WorkflowContext(task=first_task)
    first_plan = planner.plan_with_status(first_task, first_context, record=_task_record(first_task))
    assert first_plan.metadata.get("planner_route", {}).get("provider_tier") == "external"

    second_task = ProteinDesignTask(
        task_id="dual_route_recover_001",
        goal="test dual route recovery",
        constraints={
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLE",
            "plan_top_k": 1,
            "runtime_fallback": {
                "enable_dual_route": True,
                "force_external_only": False,
                "consecutive_failure_threshold": 2,
                "sustained_high_risk_threshold": 2,
                "executable_rate_threshold": 0.0,
                "executable_drop_threshold": 1.0,
            },
        },
        metadata={},
    )
    second_context = WorkflowContext(task=second_task)
    second_plan = planner.plan_with_status(second_task, second_context, record=_task_record(second_task))

    route_meta = second_plan.metadata.get("planner_route", {})
    assert route_meta.get("provider_tier") == "local"
    assert route_meta.get("provider_name") == "planner_local"
    assert local_provider.call_count >= 1

    route_events = [event for event in events if event.get("event") == "PLANNER_ROUTE_DECISION"]
    assert len(route_events) >= 2
    last = route_events[-1]
    assert last.get("from_tool") == "planner_external"
    assert last.get("to_tool") == "planner_local"


@pytest.mark.integration
def test_dual_route_switches_to_external_when_executable_rate_is_low(monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr("src.agents.planner.append_event", lambda _task_id, payload: events.append(dict(payload)))

    local_provider = _FixedPlanProvider("planner_local")
    external_provider = _FixedPlanProvider("planner_external")
    planner = PlannerAgent(llm_provider=local_provider, fallback_llm_provider=external_provider)

    rates = iter([0.2, 1.0])
    monkeypatch.setattr(planner, "_estimate_executable_rate", lambda _top_k, _task: next(rates))

    task = ProteinDesignTask(
        task_id="dual_route_exec_rate_001",
        goal="test executable rate fallback",
        constraints={
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLE",
            "plan_top_k": 1,
            "runtime_fallback": {
                "enable_dual_route": True,
                "executable_rate_threshold": 0.9,
            },
        },
        metadata={},
    )

    plan = planner.plan_with_status(task, WorkflowContext(task=task), record=_task_record(task))
    route_meta = plan.metadata.get("planner_route", {})
    assert route_meta.get("provider_tier") == "external"
    assert local_provider.call_count >= 1
    assert external_provider.call_count >= 1

    route_events = [event for event in events if event.get("event") == "PLANNER_ROUTE_DECISION"]
    assert route_events
    latest = route_events[-1]
    data = latest.get("data") or {}
    assert data.get("trigger_reason") == "candidate_executable_rate_low"
    assert "candidate_executable_rate" in data.get("trigger_threshold", "")
