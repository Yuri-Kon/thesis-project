"""test_step_runner.py

针对 StepRunner 的行为规约进行单元测试
"""

import re
from datetime import datetime, timezone
from unittest import result

import pytest

from src.agents import safety
from src.workflow import context
from src.workflow.step_runner import StepRunner
from src.models.contracts import ProteinDesignTask, PlanStep, StepResult
from src.workflow.context import WorkflowContext

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

def test_run_step_invalid_reference_raises_value_error(dummy_task):
    """对于无法解析的引用，抛出 ValueError"""

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

    with pytest.raises(ValueError):
        runner.run_step(step, context)