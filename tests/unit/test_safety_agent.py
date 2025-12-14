"""
测试 SafetyAgent 的接口和伪实现
"""
import pytest

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    SafetyResult,
    now_iso,
)

from src.agents.safety import SafetyAgent
from src.workflow.context import WorkflowContext
from src.models.db import TaskStatus


@pytest.fixture
def dummy_task() -> ProteinDesignTask:
    return ProteinDesignTask(
        task_id="task-001",
        goal="demo-goal",
        constraints={},
        metadata={},
    )


@pytest.fixture
def dummy_plan(dummy_task: ProteinDesignTask) -> Plan:
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )
    return Plan(
        task_id=dummy_task.task_id,
        steps=[step],
        constraints={},
        metadata={},
    )


@pytest.fixture
def dummy_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.CREATED,
    )


@pytest.fixture
def safety_agent() -> SafetyAgent:
    return SafetyAgent()


class TestSafetyAgent:
    """测试 SafetyAgent 的接口和伪实现"""

    def test_check_task_input_returns_safety_result(
        self, safety_agent: SafetyAgent, dummy_task: ProteinDesignTask
    ):
        """测试：check_task_input 返回 SafetyResult"""
        result = safety_agent.check_task_input(dummy_task)
        
        assert isinstance(result, SafetyResult)
        assert result.task_id == dummy_task.task_id
        assert result.phase == "input"
        assert result.scope == "task"
        assert result.action == "allow"
        assert result.risk_flags == []
        assert result.timestamp is not None

    def test_check_task_input_with_plan(
        self, safety_agent: SafetyAgent, dummy_task: ProteinDesignTask, dummy_plan: Plan
    ):
        """测试：check_task_input 可以接受可选的 plan 参数"""
        result = safety_agent.check_task_input(dummy_task, dummy_plan)
        
        assert isinstance(result, SafetyResult)
        assert result.phase == "input"

    def test_check_pre_step_returns_safety_result(
        self, safety_agent: SafetyAgent, dummy_context: WorkflowContext, dummy_plan: Plan
    ):
        """测试：check_pre_step 返回 SafetyResult"""
        step = dummy_plan.steps[0]
        result = safety_agent.check_pre_step(step, dummy_context)
        
        assert isinstance(result, SafetyResult)
        assert result.task_id == dummy_context.task.task_id
        assert result.phase == "step"
        assert result.scope == f"step:{step.id}"
        assert result.action == "allow"
        assert result.risk_flags == []
        assert result.timestamp is not None

    def test_check_post_step_returns_safety_result(
        self,
        safety_agent: SafetyAgent,
        dummy_context: WorkflowContext,
        dummy_plan: Plan,
    ):
        """测试：check_post_step 返回 SafetyResult"""
        step = dummy_plan.steps[0]
        step_result = StepResult(
            task_id=dummy_context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            outputs={"dummy": "output"},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        
        result = safety_agent.check_post_step(step, step_result, dummy_context)
        
        assert isinstance(result, SafetyResult)
        assert result.task_id == dummy_context.task.task_id
        assert result.phase == "step"
        assert result.scope == f"step:{step.id}"
        assert result.action == "allow"
        assert result.risk_flags == []
        assert result.timestamp is not None

    def test_check_final_result_returns_safety_result(
        self, safety_agent: SafetyAgent, dummy_context: WorkflowContext
    ):
        """测试：check_final_result 返回 SafetyResult"""
        result = safety_agent.check_final_result(dummy_context)
        
        assert isinstance(result, SafetyResult)
        assert result.task_id == dummy_context.task.task_id
        assert result.phase == "output"
        assert result.scope == "result"
        assert result.action == "allow"
        assert result.risk_flags == []
        assert result.timestamp is not None

    def test_check_final_result_with_design_result(
        self, safety_agent: SafetyAgent, dummy_context: WorkflowContext
    ):
        """测试：check_final_result 可以接受可选的 design_result 参数"""
        design_result = DesignResult(
            task_id=dummy_context.task.task_id,
            sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR",
            structure_pdb_path=None,
            scores={},
            risk_flags=[],
            report_path="/path/to/report.json",
            metadata={},
        )
        
        result = safety_agent.check_final_result(dummy_context, design_result)
        
        assert isinstance(result, SafetyResult)
        assert result.phase == "output"
