import pytest

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    PatchRequest,
    StepResult,
    now_iso,
)
from src.models.db import TaskStatus

from src.workflow.context import WorkflowContext
from src.workflow.plan_runner import PlanRunner, StepRunnerLike
from src.workflow.errors import FailureType, PlanRunError, StepRunError
from src.agents.safety import SafetyAgent
from src.agents.planner import PlannerAgent

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
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={"dummy": f"output_for_{step.id}"},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso()
        )

class FailingStepRunner(StepRunnerLike):
    """在第一次调用时抛出异常的 StepRunner, 用于验证异常传播"""

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        raise StepRunError(
            failure_type=FailureType.RETRYABLE,
            message=f"step {step.id} failed in engine",
            code="STEP_FAIL",
        )

class TimeoutStepRunner(StepRunnerLike):
    """模拟超时，可重试"""

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        raise TimeoutError("timeout in tool")


class ExplodingStepRunner(StepRunnerLike):
    """模拟未知工具异常"""

    def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
        raise RuntimeError("unexpected boom")

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
        PlanStep(id="S2", tool="tool_b", inputs={"y": "S1.dummy_output"}, metadata={}),
        PlanStep(id="S3", tool="tool_c", inputs={"z": "S2.dummy_output"}, metadata={}),
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
        # PlanRunner 会写入失败分类相关的度量（成功时为 None）
        assert "failure_type" in result.metrics
        assert result.metrics["failure_type"] is None
        assert "retryable" in result.metrics
        assert result.metrics["retryable"] is None

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

    with pytest.raises(PlanRunError) as excinfo:
        plan_runner.run_plan(single_step_plan, fresh_context)

    # 发生异常时，PlanRunner 不吞掉异常，不写入 step_results
    assert fresh_context.step_results == {}
    assert excinfo.value.failure_type == FailureType.RETRYABLE
    assert excinfo.value.step_id == "S1"
    # 此处没有 StepResult，无法验证 metrics 写入


def test_run_plan_classifies_timeout_as_retryable(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    runner = TimeoutStepRunner()
    plan_runner = PlanRunner(step_runner=runner)

    with pytest.raises(PlanRunError) as excinfo:
        plan_runner.run_plan(single_step_plan, fresh_context)

    assert excinfo.value.failure_type == FailureType.RETRYABLE
    assert excinfo.value.step_id == "S1"


def test_run_plan_wraps_unknown_exception_as_tool_error(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    runner = ExplodingStepRunner()
    plan_runner = PlanRunner(step_runner=runner)

    with pytest.raises(PlanRunError) as excinfo:
        plan_runner.run_plan(single_step_plan, fresh_context)

    assert excinfo.value.failure_type == FailureType.TOOL_ERROR
    assert excinfo.value.step_id == "S1"


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
    with pytest.raises(PlanRunError) as excinfo:
        plan_runner.run_plan(single_step_plan, planned_context)
    
    # 根据实现，状态更新在步骤执行之前
    # 所以即使步骤执行失败，状态也应该已经更新为 RUNNING
    assert planned_context.status == TaskStatus.RUNNING
    # 确保没有步骤结果被写入
    assert planned_context.step_results == {}
    assert excinfo.value.failure_type == FailureType.RETRYABLE
    assert excinfo.value.step_id == "S1"


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


def test_run_plan_triggers_patch_after_retry_exhausted(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """重试耗尽失败时，PlanRunner 应构造 PatchRequest 并应用 PlanPatch"""

    class TwoPhaseStepRunner(StepRunnerLike):
        def __init__(self) -> None:
            self.calls = 0

        def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
            self.calls += 1
            if self.calls == 1:
                return StepResult(
                    task_id=context.task.task_id,
                    step_id=step.id,
                    tool=step.tool,
                    status="failed",
                    failure_type=FailureType.RETRYABLE,
                    error_message="boom",
                    error_details={},
                    outputs={},
                    metrics={"retry_exhausted": True},
                    risk_flags=[],
                    logs_path=None,
                    timestamp=now_iso(),
                )
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="success",
                failure_type=None,
                error_message=None,
                error_details={},
                outputs={"dummy_output": "ok"},
                metrics={},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )

    class CapturingPlanner(PlannerAgent):
        def __init__(self) -> None:
            super().__init__(tool_registry=[])
            self.requests = []

        def patch(self, request: PatchRequest):  # type: ignore[override]
            self.requests.append(request)
            step = request.original_plan.steps[0]
            patched_step = PlanStep(
                id=step.id,
                tool="patched_tool",
                inputs=step.inputs,
                metadata=step.metadata,
            )
            op = PlanPatchOp(op="replace_step", target=step.id, step=patched_step)
            return PlanPatch(task_id=request.task_id, operations=[op], metadata={})

    runner = TwoPhaseStepRunner()
    planner = CapturingPlanner()
    plan_runner = PlanRunner(step_runner=runner, planner_agent=planner)

    returned_plan = plan_runner.run_plan(single_step_plan, planned_context)

    assert runner.calls == 2
    assert planner.requests, "Planner.patch 应被调用"
    request = planner.requests[0]
    assert "failure_type" in request.reason
    assert returned_plan.steps[0].tool == "patched_tool"
    assert planned_context.plan is returned_plan
    assert planned_context.step_results["S1"].status == "success"
    assert planned_context.step_results["S1"].tool == "patched_tool"
    patch_meta = planned_context.step_results["S1"].metrics.get("patch")
    assert patch_meta is not None
    assert patch_meta["applied"] is True
    assert patch_meta["from_tool"] == "dummy_tool"
    assert patch_meta["to_tool"] == "patched_tool"
    assert patch_meta["patched_status"] == "success"


def test_run_plan_executes_insert_before_patch_steps(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """insert_step_before 的补丁应先执行新插入步骤，再执行原目标步骤"""

    class SequencedStepRunner(StepRunnerLike):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
            self.calls.append(step.id)
            if step.id == "S1" and self.calls.count("S1") == 1:
                return StepResult(
                    task_id=context.task.task_id,
                    step_id=step.id,
                    tool=step.tool,
                    status="failed",
                    failure_type=FailureType.RETRYABLE,
                    error_message="boom",
                    error_details={},
                    outputs={},
                    metrics={"retry_exhausted": True},
                    risk_flags=[],
                    logs_path=None,
                    timestamp=now_iso(),
                )
            return StepResult(
                task_id=context.task.task_id,
                step_id=step.id,
                tool=step.tool,
                status="success",
                failure_type=None,
                error_message=None,
                error_details={},
                outputs={"dummy_output": "ok"},
                metrics={},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )

    class InsertBeforePlanner(PlannerAgent):
        def __init__(self) -> None:
            super().__init__(tool_registry=[])
            self.requests = []

        def patch(self, request: PatchRequest):  # type: ignore[override]
            self.requests.append(request)
            prep_step = PlanStep(
                id="S0",
                tool="prep_tool",
                inputs={},
                metadata={},
            )
            op = PlanPatchOp(
                op="insert_step_before",
                target="S1",
                step=prep_step,
            )
            return PlanPatch(task_id=request.task_id, operations=[op], metadata={})

    runner = SequencedStepRunner()
    planner = InsertBeforePlanner()
    plan_runner = PlanRunner(step_runner=runner, planner_agent=planner)

    returned_plan = plan_runner.run_plan(single_step_plan, planned_context)

    assert runner.calls == ["S1", "S0", "S1"]
    assert planner.requests, "Planner.patch 应被调用"
    assert returned_plan.steps[0].id == "S0"
    assert planned_context.plan is returned_plan
    assert "S0" in planned_context.step_results
    assert planned_context.step_results["S1"].status == "success"
    patch_meta = planned_context.step_results["S1"].metrics.get("patch")
    assert patch_meta and patch_meta["applied"] is True
    assert patch_meta["ops"] == ["insert_step_before"]

# A3: 完整状态机测试 - 覆盖所有状态转换场景

@pytest.fixture
def planning_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的状态为 PLANNING，表示正在规划"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.PLANNING,
    )


@pytest.fixture
def running_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的状态为 RUNNING，表示正在执行"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.RUNNING,
    )


@pytest.fixture
def summarizing_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的状态为 SUMMARIZING，表示正在汇总"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.SUMMARIZING,
    )


@pytest.fixture
def done_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的状态为 DONE，表示任务已完成"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.DONE,
    )


@pytest.fixture
def failed_context(dummy_task: ProteinDesignTask) -> WorkflowContext:
    """WorkflowContext 的状态为 FAILED，表示任务已失败"""
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.FAILED,
    )


def test_run_plan_from_planning_status_does_not_change_status(
    single_step_plan: Plan,
    planning_context: WorkflowContext,
) -> None:
    """测试：当 context.status 为 PLANNING 时，PlanRunner 不改变状态（应由 PlannerAgent 负责）"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 PLANNING
    assert planning_context.status == TaskStatus.PLANNING
    
    plan_runner.run_plan(single_step_plan, planning_context)
    
    # 状态应保持为 PLANNING（PlanRunner 不负责 PLANNING 状态的管理）
    assert planning_context.status == TaskStatus.PLANNING
    # 但步骤应该已执行
    assert "S1" in planning_context.step_results


def test_run_plan_from_running_status_keeps_running(
    single_step_plan: Plan,
    running_context: WorkflowContext,
) -> None:
    """测试：当 context.status 已经是 RUNNING 时，PlanRunner 保持 RUNNING 状态"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 RUNNING
    assert running_context.status == TaskStatus.RUNNING
    
    plan_runner.run_plan(single_step_plan, running_context)
    
    # 状态应保持为 RUNNING
    assert running_context.status == TaskStatus.RUNNING
    # 确保步骤已执行
    assert "S1" in running_context.step_results


def test_run_plan_from_summarizing_status_does_not_change_status(
    single_step_plan: Plan,
    summarizing_context: WorkflowContext,
) -> None:
    """测试：当 context.status 为 SUMMARIZING 时，PlanRunner 不改变状态（应由 SummarizerAgent 负责）"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 SUMMARIZING
    assert summarizing_context.status == TaskStatus.SUMMARIZING
    
    plan_runner.run_plan(single_step_plan, summarizing_context)
    
    # 状态应保持为 SUMMARIZING（PlanRunner 不负责 SUMMARIZING 状态的管理）
    assert summarizing_context.status == TaskStatus.SUMMARIZING
    # 但步骤应该已执行
    assert "S1" in summarizing_context.step_results


def test_run_plan_from_done_status_does_not_change_status(
    single_step_plan: Plan,
    done_context: WorkflowContext,
) -> None:
    """测试：当 context.status 为 DONE 时，PlanRunner 不改变状态（终端状态）"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 DONE
    assert done_context.status == TaskStatus.DONE
    
    plan_runner.run_plan(single_step_plan, done_context)
    
    # 状态应保持为 DONE（终端状态不应被改变）
    assert done_context.status == TaskStatus.DONE
    # 但步骤应该已执行（允许在终端状态下执行，但状态不变）
    assert "S1" in done_context.step_results


def test_run_plan_from_failed_status_does_not_change_status(
    single_step_plan: Plan,
    failed_context: WorkflowContext,
) -> None:
    """测试：当 context.status 为 FAILED 时，PlanRunner 不改变状态（终端状态）"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 FAILED
    assert failed_context.status == TaskStatus.FAILED
    
    plan_runner.run_plan(single_step_plan, failed_context)
    
    # 状态应保持为 FAILED（终端状态不应被改变）
    assert failed_context.status == TaskStatus.FAILED
    # 但步骤应该已执行（允许在终端状态下执行，但状态不变）
    assert "S1" in failed_context.step_results


def test_run_plan_state_transition_planned_to_running_is_idempotent(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
) -> None:
    """测试：PLANNED → RUNNING 状态转换是幂等的（多次调用不会改变状态）"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 第一次执行：PLANNED → RUNNING
    plan_runner.run_plan(single_step_plan, planned_context)
    assert planned_context.status == TaskStatus.RUNNING
    
    # 第二次执行：应该保持 RUNNING
    plan_runner.run_plan(single_step_plan, planned_context)
    assert planned_context.status == TaskStatus.RUNNING
    
    # 确保步骤被执行了两次
    assert len(runner.called_steps) == 2
    assert runner.called_steps == ["S1", "S1"]


def test_run_plan_complete_state_flow_created_to_running(
    single_step_plan: Plan,
    fresh_context: WorkflowContext,
) -> None:
    """测试：完整状态流程 - CREATED 状态下的执行（不改变状态，但允许执行）"""
    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner)
    
    # 初始状态为 CREATED
    assert fresh_context.status == TaskStatus.CREATED
    
    # 执行计划（不改变状态，因为不是 PLANNED）
    plan_runner.run_plan(single_step_plan, fresh_context)
    
    # 状态应保持为 CREATED
    assert fresh_context.status == TaskStatus.CREATED
    # 但步骤应该已执行
    assert "S1" in fresh_context.step_results
    assert fresh_context.plan is single_step_plan


# A4: Safety Pipeline 集成测试

class MockSafetyAgent:
    """用于测试的 Mock SafetyAgent，记录调用情况"""
    
    def __init__(self):
        self.check_task_input_called = False
        self.check_pre_step_called = False
        self.check_post_step_called = False
        self.check_final_result_called = False
        self.check_task_input_args = None
        self.check_final_result_args = None
    
    def check_task_input(self, task, plan=None):
        self.check_task_input_called = True
        self.check_task_input_args = (task, plan)
        from src.models.contracts import SafetyResult, now_iso
        return SafetyResult(
            task_id=task.task_id,
            phase="input",
            scope="task",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )
    
    def check_pre_step(self, step, context):
        self.check_pre_step_called = True
        from src.models.contracts import SafetyResult, now_iso
        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )
    
    def check_post_step(self, step, step_result, context):
        self.check_post_step_called = True
        from src.models.contracts import SafetyResult, now_iso
        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )
    
    def check_final_result(self, context, design_result=None):
        self.check_final_result_called = True
        self.check_final_result_args = (context, design_result)
        from src.models.contracts import SafetyResult, now_iso
        return SafetyResult(
            task_id=context.task.task_id,
            phase="output",
            scope="result",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )


def test_plan_runner_calls_safety_check_task_input(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
):
    """测试：PlanRunner 在执行前调用 SafetyAgent.check_task_input"""
    runner = DummyStepRunner()
    mock_safety = MockSafetyAgent()
    plan_runner = PlanRunner(step_runner=runner, safety_agent=mock_safety)
    
    # 初始时 safety_events 应为空
    assert len(planned_context.safety_events) == 0
    
    plan_runner.run_plan(single_step_plan, planned_context)
    
    # 应该调用了 check_task_input
    assert mock_safety.check_task_input_called
    assert mock_safety.check_task_input_args[0] == planned_context.task
    assert mock_safety.check_task_input_args[1] == single_step_plan
    
    # safety_events 应该包含 task_input 的检查结果
    assert len(planned_context.safety_events) >= 1
    input_safety = planned_context.safety_events[0]
    assert input_safety.phase == "input"
    assert input_safety.scope == "task"


def test_plan_runner_calls_safety_check_final_result(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
):
    """测试：PlanRunner 在执行后调用 SafetyAgent.check_final_result"""
    runner = DummyStepRunner()
    mock_safety = MockSafetyAgent()
    plan_runner = PlanRunner(step_runner=runner, safety_agent=mock_safety)
    
    plan_runner.run_plan(single_step_plan, planned_context)
    
    # 应该调用了 check_final_result
    assert mock_safety.check_final_result_called
    assert mock_safety.check_final_result_args[0] == planned_context
    
    # safety_events 应该包含 final_result 的检查结果
    assert len(planned_context.safety_events) >= 2
    final_safety = planned_context.safety_events[-1]
    assert final_safety.phase == "output"
    assert final_safety.scope == "result"


def test_plan_runner_safety_events_order(
    multi_step_plan: Plan,
    planned_context: WorkflowContext,
):
    """测试：PlanRunner 的 safety_events 顺序正确（task_input 在前，final_result 在后）"""
    # 使用真实的 StepRunner，它会调用 SafetyAgent
    from src.workflow.step_runner import StepRunner
    step_runner = StepRunner()
    plan_runner = PlanRunner(step_runner=step_runner)
    
    plan_runner.run_plan(multi_step_plan, planned_context)
    
    # 至少应该有 task_input 和 final_result
    assert len(planned_context.safety_events) >= 2
    
    # 第一个应该是 task_input
    assert planned_context.safety_events[0].phase == "input"
    
    # 最后一个应该是 final_result
    assert planned_context.safety_events[-1].phase == "output"
    
    # 中间应该有步骤的 pre_step 和 post_step（由 StepRunner 添加）
    # 每个步骤会有 pre_step 和 post_step，所以中间应该有 2 * len(steps) 个 step 阶段的检查
    step_safety_events = [
        e for e in planned_context.safety_events[1:-1]
        if e.phase == "step"
    ]
    assert len(step_safety_events) == 2 * len(multi_step_plan.steps)


def test_plan_runner_blocks_when_task_input_safety_blocks(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
):
    """task_input 返回 block 时，PlanRunner 应抛出 SAFETY_BLOCK"""
    from src.models.contracts import SafetyResult, now_iso

    class BlockingSafety(SafetyAgent):
        def check_task_input(self, task, plan=None):
            return SafetyResult(
                task_id=task.task_id,
                phase="input",
                scope="task",
                risk_flags=[],
                action="block",
                timestamp=now_iso(),
            )

    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner, safety_agent=BlockingSafety())

    with pytest.raises(PlanRunError) as excinfo:
        plan_runner.run_plan(single_step_plan, planned_context)

    assert excinfo.value.failure_type == FailureType.SAFETY_BLOCK
    # 状态和步骤结果不应被更改
    assert planned_context.status == TaskStatus.PLANNED
    assert planned_context.step_results == {}
    assert planned_context.safety_events[-1].action == "block"


def test_plan_runner_blocks_on_final_safety(
    single_step_plan: Plan,
    planned_context: WorkflowContext,
):
    """最终安全检查 block 时，PlanRunner 应抛出 SAFETY_BLOCK"""
    from src.models.contracts import SafetyResult, now_iso

    class FinalBlockingSafety(SafetyAgent):
        def check_task_input(self, task, plan=None):
            return super().check_task_input(task, plan)

        def check_final_result(self, context, design_result=None):
            return SafetyResult(
                task_id=context.task.task_id,
                phase="output",
                scope="result",
                risk_flags=[],
                action="block",
                timestamp=now_iso(),
            )

    runner = DummyStepRunner()
    plan_runner = PlanRunner(step_runner=runner, safety_agent=FinalBlockingSafety())

    with pytest.raises(PlanRunError) as excinfo:
        plan_runner.run_plan(single_step_plan, planned_context)

    assert excinfo.value.failure_type == FailureType.SAFETY_BLOCK
    # 步骤已执行，但最终安全阻断
    assert "S1" in planned_context.step_results
    assert planned_context.safety_events[-1].action == "block"
