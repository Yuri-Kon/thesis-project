from asyncio import taskgroups
import datetime
from unittest import result
from _pytest import runner
import pytest

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    now_iso,
)
from src.models.db import TaskStatus

from src.workflow import plan_runner
from src.workflow.context import WorkflowContext
from src.workflow.plan_runner import PlanRunner, StepRunnerLike

class DummyStepRunner(StepRunnerLike):
    """用于测试简单的 StepRunner, 记录调用顺序并返回可控的 StepResult"""

    def __init__(self) -> None:
        self.called_steps: list[str] = []
    
    def run_step(self, step, context: WorkflowContext) -> StepResult:
        self.called_steps.append(step.id)
        # 返回一个最简单的 StepResult, 字段对齐数据契约
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            outputs={"dummy": f"output_for_{step.id}"},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso()
        )

class FailingStepRunner(StepRunnerLike):
    """在第一次调用时抛出异常的 StepRunner, 用于验证异常传播"""

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        raise RuntimeError(f"step {step.id} failed in engine")

@pytest.fixture
def dummy_task() -> ProteinDesignTask:
    return ProteinDesignTask(
        task_id="task-001",
        goal="demo-goal",
        constraints={},
        metadata={},
    )

@pytest.fixture
def single_step_plan(dummy_task: ProteinDesignTask) -> Plan:
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
def multi_step_plan(dummy_task: ProteinDesignTask) -> Plan:
    steps = [
        PlanStep(id="S1", tool="tool_a", inputs={"x": 1}, metadata={}),
        PlanStep(id="S2", tool="tool_b", inputs={"y": "S1.dummy"}, metadata={}),
        PlanStep(id="S3", tool="tool_c", inputs={"z": "S2.dummy"}, metadata={}),
    ]
    return Plan(
        task_id=dummy_task.task_id,
        steps=steps,
        constraints={},
        metadata={},
    )

@pytest.fixture
def empty_plan(dummy_task: ProteinDesignTask) -> Plan:
    return Plan(
        task_id=dummy_task.task_id,
        steps=[],
        constraints={},
        metadata={},
    )

@pytest.fixture
def fresh_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的初始状态，仅有task, 其余为 空/默认"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.CREATED,
    )

@pytest.fixture
def planned_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的状态为 PLANNED，表示计划已生成"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.PLANNED,
    )

# 核心行为测试

def test_run_plan_single_step_updates_context_and_returns_plan(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:

    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)

    result_plan = plan_runner.run_plan(single_step_plan, fresh_context)

    # 返回的 plan 应该是传入的同一个对象
    assert result_plan is single_step_plan

    # context.plan 在初始为 None 时，应被设置为当前 plan
    assert fresh_context.plan is single_step_plan

    # 单步执行：StepRunner 被调用一次
    assert runner.called_steps == ["S1"]

    # 上下文中应写入对应的 StepResult
    assert "S1" in fresh_context.step_results
    step_result = fresh_context.step_results["S1"]
    assert step_result.step_id == "S1"
    assert step_result.tool == "dummy_tool"
    assert step_result.status == "success"
    assert step_result.outputs["dummy"] == "output_for_S1"


def test_run_multiple_steps_sequential_execution(
    multi_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)

    plan_runner.run_plan(multi_step_plan, fresh_context)

    # 按 steps 顺序调用 StepRunner
    assert runner.called_steps == ["S1", "S2", "S3"]

    for step in multi_step_plan.steps:
        assert step.id in fresh_context.step_results
        result = fresh_context.step_results[step.id]
        assert result.step_id == step.id
        assert result.status == "success"

def test_run_plan_does_not_overwrite_existing_plan_in_context(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:

    # 预先在 context 中放入一个 plan, 迷你上层已经放置
    existing_plan = Plan(
        task_id=fresh_context.task.task_id,
        steps=[],
        constraints={},
        metadata={"source": "existing"},
    )
    fresh_context.plan = existing_plan

    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)

    plan_runner.run_plan(single_step_plan, fresh_context)

    # v1 约定：PlanRunner 不强行覆盖已有 context.plan
    assert fresh_context.plan is existing_plan

def test_run_plan_with_empty_steps_no_step_execution(
    empty_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)

    plan_runner.run_plan(empty_plan, fresh_context)

    assert runner.called_steps == []

    assert fresh_context.plan is empty_plan

    assert fresh_context.step_results == {}

def test_run_plan_propagates_exceptions_from_step_runner(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    failing_runner = FailingStepRunner()
    plan_runner = PlanRunner(step_runner=failing_runner)

    with pytest.raises(RuntimeError):
        plan_runner.run_plan(single_step_plan, fresh_context)

    # 发生异常时，PlanRunner 不吞掉异常，不写入 step_results
    assert fresh_context.step_results == {}


# A3: TaskStatus 状态机测试

def test_run_plan_updates_status_from_planned_to_running(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """测试：当 context.status 为 PLANNED 时，PlanRunner 应将其更新为 RUNNING"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态应为 PLANNED
    assert planned_context.status == TaskStatus.PLANNED
    
    plan_runner.run_plan(single_step_plan, planned_context)
    
    # 执行后状态应为 RUNNING
    assert planned_context.status == TaskStatus.RUNNING
    # 确保步骤已执行
    assert "S1" in planned_context.step_results


def test_run_plan_does_not_change_status_if_not_planned(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    """测试：当 context.status 不是 PLANNED 时，PlanRunner 不改变状态"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 CREATED
    assert fresh_context.status == TaskStatus.CREATED
    
    plan_runner.run_plan(single_step_plan, fresh_context)
    
    # 状态应保持为 CREATED（不自动更新为 RUNNING）
    assert fresh_context.status == TaskStatus.CREATED
    # 但步骤应该已执行
    assert "S1" in fresh_context.step_results


def test_run_plan_keeps_running_status_after_completion(
    multi_step_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """测试：执行完成后，状态保持为 RUNNING"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    plan_runner.run_plan(multi_step_plan, planned_context)
    
    # 执行后状态应为 RUNNING（不是 SUMMARIZING 或 DONE）
    assert planned_context.status == TaskStatus.RUNNING
    # 确保所有步骤已执行
    assert len(planned_context.step_results) == 3


def test_run_plan_maintains_status_on_exception(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """测试：异常发生时，状态保持为 RUNNING（状态更新在步骤执行之前）"""
    failing_runner = FailingStepRunner()
    plan_runner = PlanRunner(step_runner=failing_runner)
    
    # 初始状态为 PLANNED
    assert planned_context.status == TaskStatus.PLANNED
    
    # 执行会抛出异常
    with pytest.raises(RuntimeError):
        plan_runner.run_plan(single_step_plan, planned_context)
    
    # 根据实现，状态更新在步骤执行之前
    # 所以即使步骤执行失败，状态也应该已经更新为 RUNNING
    assert planned_context.status == TaskStatus.RUNNING
    # 确保没有步骤结果被写入
    assert planned_context.step_results == {}


def test_run_plan_with_empty_steps_updates_status(
    empty_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """测试：即使步骤为空，状态也应该从 PLANNED 更新为 RUNNING"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    plan_runner.run_plan(empty_plan, planned_context)
    
    # 状态应更新为 RUNNING
    assert planned_context.status == TaskStatus.RUNNING
    # 没有步骤执行
    assert runner.called_steps == []
    assert planned_context.step_results == {}
