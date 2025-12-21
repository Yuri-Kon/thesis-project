"""test_step_runner.py

针对 StepRunner 的行为规约进行单元测试
"""

import re
from datetime import datetime, timezone

import pytest

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.agents import safety
from src.workflow import context
from src.workflow.step_runner import StepRunner
from src.workflow.errors import FailureType, StepRunError
from src.models.contracts import ProteinDesignTask, PlanStep, StepResult
from src.workflow.context import WorkflowContext
from src.models.db import TaskStatus
from src.workflow.step_runner import StepRetryPolicy


def _resolve_inputs(step: PlanStep, context: WorkflowContext) -> dict:
    resolved = {}
    for key, val in step.inputs.items():
        if isinstance(val, str) and "." in val:
            step_id, field = val.split(".", 1)
            if step_id and step_id.startswith("S"):
                if not context.has_step_result(step_id):
                    raise ValueError(
                        f"Failed to resolve input reference '{val}' "
                        f"for step '{step.id}': step '{step_id}' not found in context"
                    )
                try:
                    resolved_value = context.get_step_output(step_id, field)
                except KeyError as exc:
                    raise ValueError(
                        f"Failed to resolve input reference '{val}' "
                        f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                    ) from exc
                resolved[key] = resolved_value
                continue
        resolved[key] = val
    return resolved


class DummyAdapter(BaseToolAdapter):
    tool_id = "dummy_tool"
    adapter_id = "dummy_adapter"

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> dict:
        return _resolve_inputs(step, context)

    def run_local(self, inputs: dict) -> tuple[dict, dict]:
        return {"dummy_output": f"executed {self.tool_id}", "inputs": inputs}, {"exec_type": "dummy"}


@pytest.fixture(autouse=True)
def dummy_adapter():
    adapter = DummyAdapter()
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()
    register_adapter(adapter)
    yield adapter
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()

def _isoformat_utc(s: str) -> bool:
    """简单校验一个字符串是否看起来像 UTC ISO-8601 时间

    不做 严格RFC检查，只检查是否能被 datetime.fromisoformat 解析
    且 tzinfo 为 UTC
    """
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return False
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) == timezone.utc.utcoffset(dt)

@pytest.fixture
def dummy_task() -> ProteinDesignTask:
    return ProteinDesignTask(
        task_id = "task_test_001",
        goal = "design a small stable protein",
        constraints = {},
        metadata={"user": "unit-test"}
    )

@pytest.fixture
def empty_context(dummy_task) -> WorkflowContext:
    """仅包含 task, 其余使用默认空结构

    要求 WorkflowContext 至少包含：

    - task
    - plan
    - step_results: Dict[str, StepResult]
    - safety_events: List
    - design_result: 可为None
    """
    return WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=TaskStatus.CREATED,
    )

def test_run_step_returns_steppresult_instance(empty_context):
    """run_step 必须返回 StepResult 实例"""

    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )

    runner = StepRunner()
    result = runner.run_step(step, empty_context)

    assert isinstance(result, StepResult)
    assert result.task_id == empty_context.task.task_id
    assert result.step_id == step.id
    assert result.tool == step.tool

def test_run_step_basic_fields_and_outputs_contract(empty_context, monkeypatch):
    """run_step 必须满足基本字段和输出契约
    
    一旦实现 run_step, 必须满足以下契约:

    - 返回 StepResult
    - task_id / step_id / tool 正确复制
    - status == "success
    with pytest.raises(NotImplementedError):
        runner.run_step(step, empty_context)"
    - outputs 至少包含
        - "dummy_output": "executed {step.tool}"
        - "inputs": 解析后的输入字典
    - metrics 至少包含
        - "exec_type": "dummy"
        - "duration_ms": int
    - risk_flags == []
    - logs_path is None
    - timestamp 是一个 UTC ISO 时间字符串
    """

    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1, "y": "text"},
        metadata={},
    )

    runner = StepRunner()

    # pytest.xfail("StepRunner.run_step not implemented yet; remover xfaile after implementation")

    result = runner.run_step(step, empty_context)

    assert isinstance(result, StepResult)
    assert result.task_id == empty_context.task.task_id
    assert result.tool == step.tool
    assert result.status == "success"

    # outputs 约定
    assert "dummy_output" in result.outputs
    assert result.outputs["dummy_output"] == f"executed {step.tool}"
    assert "inputs" in result.outputs
    assert isinstance(result.outputs["inputs"], dict)
    assert result.outputs["inputs"]["x"] == 1
    assert result.outputs["inputs"]["y"] == "text"
    assert result.failure_type is None
    assert result.error_message is None
    assert result.error_details == {}

    # metrics 约定
    assert isinstance(result.metrics, dict)
    assert result.metrics.get("exec_type") == "dummy"
    assert isinstance(result.metrics.get("duration_ms"), int)

    # 安全与日志
    assert isinstance(result.risk_flags, list)
    assert result.risk_flags == []
    assert result.logs_path is None

    # 时间戳格式
    assert isinstance(result.timestamp, str)
    assert _isoformat_utc(result.timestamp)

def test_run_step_resolves_reference_inputs(dummy_task):
    """run_step 必须正确解析引用语义的输入"""

    # 构造一个前置步骤的 StepResult
    pre_step = PlanStep(
        id="S1",
        tool="prev_tool",
        inputs={"seed":42},
        metadata={},
    )
    prev_result = StepResult(
        task_id=dummy_task.task_id,
        step_id="S1",
        tool="prev_tool",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"sequence": "AAAABBBBB"},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # 构造当前步骤，需要引用 S1.sequence
    step = PlanStep(
        id="S2",
        tool="dummy_tool",
        inputs={"seq": "S1.sequence", "k": 3},
        metadata={},
    )

    context = WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={"S1": prev_result},
        safety_events=[],
        design_result=None,
    )

    runner = StepRunner()
    # pytest.xfail("StepRunner.run_step not implemented yet; remove xfail after implementation")

    result = runner.run_step(step, context)

    assert isinstance(result, StepResult)
    resolved_inputs = result.outputs["inputs"]
    assert resolved_inputs["seq"] == "AAAABBBBB"
    assert resolved_inputs["k"] == 3

def test_run_step_invalid_reference_returns_failed_result(dummy_task):
    """对于无法解析的引用，返回 failed 的 StepResult，并标记不可重试"""

    step = PlanStep(
    id="S2",
    tool="dummy_tool",
    inputs={"bad": "S999.not_exist"},
    metadata={},
    ) 

    context = WorkflowContext(
        task=dummy_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
    )

    runner = StepRunner()

    result = runner.run_step(step, context)

    assert isinstance(result, StepResult)
    assert result.status == "failed"
    assert result.failure_type == FailureType.NON_RETRYABLE
    assert result.error_message
    assert result.metrics.get("exec_type") == "input_resolution"


def test_run_step_tool_failure_returns_failed_result(empty_context, dummy_adapter, monkeypatch):
    """工具返回已知失败时，标记为 retryable/tool failure"""
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )

    runner = StepRunner()

    def fake_exec_tool(_inputs):
        raise StepRunError(
            failure_type=FailureType.RETRYABLE,
            message="tool returned non-zero exit",
            code="TOOL_RUN_FAILED",
        )

    monkeypatch.setattr(dummy_adapter, "run_local", fake_exec_tool)

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.RETRYABLE
    assert "non-zero exit" in result.error_message
    assert result.metrics.get("exec_type") == "tool_execution"


def test_run_step_tool_exception_returns_tool_error(empty_context, dummy_adapter, monkeypatch):
    """未预期异常应标记为 TOOL_ERROR"""
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )

    runner = StepRunner()

    def crash_exec_tool(_inputs):
        raise RuntimeError("segfault")

    monkeypatch.setattr(dummy_adapter, "run_local", crash_exec_tool)

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.TOOL_ERROR
    assert "segfault" in result.error_message
    assert result.metrics.get("exec_type") == "tool_execution"


def test_run_step_missing_required_output_marks_non_retryable(empty_context, dummy_adapter, monkeypatch):
    """缺少必需输出字段时，标记为不可重试失败"""
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={"required_outputs": ["result"]},
    )

    runner = StepRunner()
    monkeypatch.setattr(dummy_adapter, "run_local", lambda _inputs: ({"some": "value"}, {}))

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.NON_RETRYABLE
    assert "Missing required output field" in result.error_message
    assert result.metrics.get("exec_type") == "tool_execution"


def test_run_step_output_type_mismatch_marks_non_retryable(empty_context, dummy_adapter, monkeypatch):
    """输出类型不符合声明时，标记为不可重试失败"""
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={"required_outputs": ["dummy_output"], "output_types": {"dummy_output": "dict"}},
    )

    runner = StepRunner()
    # dummy_output 将是字符串，与期望的 dict 不符
    monkeypatch.setattr(dummy_adapter, "run_local", lambda _inputs: ({"dummy_output": "text"}, {}))

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.NON_RETRYABLE
    assert "type mismatch" in result.error_message
    assert result.metrics.get("exec_type") == "tool_execution"


# Retry 行为测试（不涉及 FSM / Patch / Replan）

def _make_step_result(
    task_id: str,
    step_id: str,
    status: str,
    *,
    failure_type: FailureType | None = None,
    error_message: str | None = None,
) -> StepResult:
    """简化构造 StepResult 的助手，便于模拟 _run_once 输出"""
    return StepResult(
        task_id=task_id,
        step_id=step_id,
        tool="dummy_tool",
        status=status,
        failure_type=failure_type,
        error_message=error_message,
        error_details={},
        outputs={"dummy_output": "ok", "inputs": {}},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def test_retryable_failure_then_success(empty_context, monkeypatch):
    """第一次可重试失败，第二次成功，应立即返回成功且不再重试"""
    step = PlanStep(id="S1", tool="dummy_tool", inputs={}, metadata={})
    policy = StepRetryPolicy(max_attempts=3, backoff_schedule_ms=())
    runner = StepRunner(retry_policy=policy)

    attempts = [
        _make_step_result(empty_context.task.task_id, step.id, "failed", failure_type=FailureType.RETRYABLE, error_message="temp fail"),
        _make_step_result(empty_context.task.task_id, step.id, "success"),
    ]

    def fake_run_once(_step, _ctx):
        return attempts.pop(0)

    monkeypatch.setattr(runner, "_run_once", fake_run_once)

    result = runner.run_step(step, empty_context)

    assert result.status == "success"
    assert result.metrics.get("attempt") == 2
    assert result.metrics.get("max_attempts") == 3
    assert result.metrics.get("attempt_history")[0]["status"] == "failed"
    assert result.metrics.get("attempt_history")[1]["status"] == "success"
    # 成功路径不应标记 retried/retry_exhausted
    assert "retried" not in result.metrics
    assert "retry_exhausted" not in result.metrics


def test_retryable_failure_exhausted(empty_context, monkeypatch):
    """可重试失败且耗尽次数，最终失败并标记 retry_exhausted"""
    step = PlanStep(id="S1", tool="dummy_tool", inputs={}, metadata={})
    policy = StepRetryPolicy(max_attempts=2, backoff_schedule_ms=())
    runner = StepRunner(retry_policy=policy)

    def always_fail(_step, _ctx):
        return _make_step_result(
            empty_context.task.task_id,
            step.id,
            "failed",
            failure_type=FailureType.RETRYABLE,
            error_message="temp fail",
        )

    monkeypatch.setattr(runner, "_run_once", always_fail)

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.RETRYABLE
    assert result.metrics.get("retried") is True
    assert result.metrics.get("retry_exhausted") is True
    assert len(result.metrics.get("attempt_history")) == 2
    assert result.metrics.get("attempt_history")[-1]["attempt"] == 2


def test_non_retryable_failure_no_retry(empty_context, monkeypatch):
    """不可重试失败仅执行一次，不应设置 retried 标记"""
    step = PlanStep(id="S1", tool="dummy_tool", inputs={}, metadata={})
    runner = StepRunner(retry_policy=StepRetryPolicy(max_attempts=3, backoff_schedule_ms=()))

    def fail_once(_step, _ctx):
        return _make_step_result(
            empty_context.task.task_id,
            step.id,
            "failed",
            failure_type=FailureType.NON_RETRYABLE,
            error_message="bad input",
        )

    monkeypatch.setattr(runner, "_run_once", fail_once)

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.NON_RETRYABLE
    assert result.metrics.get("attempt") == 1
    assert result.metrics.get("max_attempts") == 3
    assert result.metrics.get("attempt_history")[0]["status"] == "failed"
    assert "retried" not in result.metrics
    assert "retry_exhausted" not in result.metrics


def test_success_no_retry(empty_context):
    """成功路径不应额外重试，attempt_history 仅一条"""
    step = PlanStep(id="S1", tool="dummy_tool", inputs={}, metadata={})
    runner = StepRunner(retry_policy=StepRetryPolicy(max_attempts=3, backoff_schedule_ms=()))

    result = runner.run_step(step, empty_context)

    assert result.status == "success"
    assert result.metrics.get("attempt") == 1
    assert result.metrics.get("max_attempts") == 3
    assert len(result.metrics.get("attempt_history")) == 1
    assert "retried" not in result.metrics
    assert "retry_exhausted" not in result.metrics


# A4: Safety Pipeline 集成测试

def test_run_step_calls_safety_pre_and_post_check(empty_context):
    """测试：StepRunner 在执行前后调用 SafetyAgent"""
    from src.agents.safety import SafetyAgent
    from src.models.contracts import SafetyResult, now_iso
    
    class MockSafetyAgent(SafetyAgent):
        def __init__(self):
            self.pre_called = False
            self.post_called = False
            self.pre_step_arg = None
            self.post_step_args = None
        
        def check_pre_step(self, step, context):
            self.pre_called = True
            self.pre_step_arg = step.id
            return SafetyResult(
                task_id=context.task.task_id,
                phase="step",
                scope=f"step:{step.id}",
                risk_flags=[],
                action="allow",
                timestamp=now_iso(),
            )
        
        def check_post_step(self, step, step_result, context):
            self.post_called = True
            self.post_step_args = (step.id, step_result.step_id)
            return SafetyResult(
                task_id=context.task.task_id,
                phase="step",
                scope=f"step:{step.id}",
                risk_flags=[],
                action="allow",
                timestamp=now_iso(),
            )
    
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )
    
    mock_safety = MockSafetyAgent()
    runner = StepRunner(safety_agent=mock_safety)
    
    # 初始时 safety_events 应为空
    assert len(empty_context.safety_events) == 0
    
    result = runner.run_step(step, empty_context)
    
    # 应该调用了 pre_step 和 post_step
    assert mock_safety.pre_called
    assert mock_safety.post_called
    assert mock_safety.pre_step_arg == "S1"
    assert mock_safety.post_step_args[0] == "S1"
    assert mock_safety.post_step_args[1] == "S1"
    
    # safety_events 应该包含 pre_step 和 post_step 的检查结果
    assert len(empty_context.safety_events) == 2
    assert empty_context.safety_events[0].phase == "step"
    assert empty_context.safety_events[0].scope == "step:S1"
    assert empty_context.safety_events[1].phase == "step"
    assert empty_context.safety_events[1].scope == "step:S1"
    
    # StepResult 的 risk_flags 应该来自 post_step 的检查结果
    assert isinstance(result.risk_flags, list)


def test_run_step_safety_events_added_to_context(empty_context):
    """测试：StepRunner 将 SafetyResult 添加到 context.safety_events"""
    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )
    
    initial_safety_events_count = len(empty_context.safety_events)
    runner = StepRunner()
    
    result = runner.run_step(step, empty_context)
    
    # safety_events 应该增加了 2 个（pre_step 和 post_step）
    assert len(empty_context.safety_events) == initial_safety_events_count + 2
    
    # 最后两个应该是 step 阶段的检查
    assert empty_context.safety_events[-2].phase == "step"
    assert empty_context.safety_events[-1].phase == "step"


def test_run_step_pre_safety_block_raises(empty_context):
    """pre_step 返回 block 时，应返回 failed StepResult，分类 SAFETY_BLOCK"""
    from src.agents.safety import SafetyAgent
    from src.models.contracts import SafetyResult, now_iso

    class BlockingSafety(SafetyAgent):
        def check_pre_step(self, step, context):
            return SafetyResult(
                task_id=context.task.task_id,
                phase="step",
                scope=f"step:{step.id}",
                risk_flags=[],
                action="block",
                timestamp=now_iso(),
            )

    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )

    runner = StepRunner(safety_agent=BlockingSafety())

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.SAFETY_BLOCK
    assert result.error_message
    assert result.metrics.get("exec_type") == "safety_precheck"
    # block 事件仍然写入 context
    assert empty_context.safety_events[-1].action == "block"


def test_run_step_post_safety_block_raises(empty_context):
    """post_step 返回 block 时，应返回 failed StepResult，分类 SAFETY_BLOCK"""
    from src.agents.safety import SafetyAgent
    from src.models.contracts import SafetyResult, now_iso

    class BlockingAfterSafety(SafetyAgent):
        def check_pre_step(self, step, context):
            return SafetyResult(
                task_id=context.task.task_id,
                phase="step",
                scope=f"step:{step.id}",
                risk_flags=[],
                action="allow",
                timestamp=now_iso(),
            )

        def check_post_step(self, step, step_result, context):
            return SafetyResult(
                task_id=context.task.task_id,
                phase="step",
                scope=f"step:{step.id}",
                risk_flags=[],
                action="block",
                timestamp=now_iso(),
            )

    step = PlanStep(
        id="S1",
        tool="dummy_tool",
        inputs={"x": 1},
        metadata={},
    )

    runner = StepRunner(safety_agent=BlockingAfterSafety())

    result = runner.run_step(step, empty_context)

    assert result.status == "failed"
    assert result.failure_type == FailureType.SAFETY_BLOCK
    assert result.error_message
    assert result.metrics.get("exec_type") == "safety_postcheck"
    # pre/post 安全事件都应写入
    assert len(empty_context.safety_events) == 2
    assert empty_context.safety_events[1].action == "block"
