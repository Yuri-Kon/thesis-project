"""pytest共享fixtures和测试工具"""
from __future__ import annotations

import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, MagicMock

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    now_iso,
)
from src.workflow.context import WorkflowContext
from src.models.db import InternalStatus


@pytest.fixture
def sample_task() -> ProteinDesignTask:
    """创建示例任务"""
    return ProteinDesignTask(
        task_id="test_task_001",
        goal="设计一个长度为50的蛋白质序列",
        constraints={
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR",
            "length_range": [40, 60],
        },
        metadata={"test": True},
    )


@pytest.fixture
def sample_plan(sample_task: ProteinDesignTask) -> Plan:
    """创建示例计划"""
    return Plan(
        task_id=sample_task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="dummy_tool",
                inputs={"sequence": sample_task.constraints.get("sequence", "")},
                metadata={},
            )
        ],
        constraints=sample_task.constraints,
        metadata={},
    )


@pytest.fixture
def sample_workflow_context(sample_task: ProteinDesignTask) -> WorkflowContext:
    """创建示例工作流上下文"""
    return WorkflowContext(
        task=sample_task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.CREATED,
    )


@pytest.fixture
def sample_step_result(sample_task: ProteinDesignTask) -> StepResult:
    """创建示例步骤结果"""
    return StepResult(
        task_id=sample_task.task_id,
        step_id="S1",
        tool="dummy_tool",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={
            "note": "dummy execution",
            "sequence_length": 50,
        },
        metrics={"runtime_ms": 1, "backend": "dummy_executor"},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )


@pytest.fixture
def sample_design_result(sample_task: ProteinDesignTask, tmp_path: Path) -> DesignResult:
    """创建示例设计结果"""
    report_path = tmp_path / "reports" / f"{sample_task.task_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    return DesignResult(
        task_id=sample_task.task_id,
        sequence=sample_task.constraints.get("sequence"),
        structure_pdb_path=None,
        scores={"sequence_length": 50},
        risk_flags=[],
        report_path=str(report_path),
        metadata={"created_at": now_iso()},
    )


@pytest.fixture
def temp_report_dir(tmp_path: Path) -> Path:
    """创建临时报告目录"""
    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


@pytest.fixture
def mock_executor():
    """创建模拟的ExecutorAgent"""
    executor = Mock()
    executor.run_step = Mock(return_value=Mock(spec=StepResult))
    executor.run_plan = Mock(return_value=Mock(spec=Plan))
    return executor


@pytest.fixture
def mock_planner():
    """创建模拟的PlannerAgent"""
    planner = Mock()
    planner.plan = Mock(return_value=Mock(spec=Plan))
    return planner


@pytest.fixture
def mock_summarizer():
    """创建模拟的SummarizerAgent"""
    summarizer = Mock()
    summarizer.summarize = Mock(return_value=Mock(spec=DesignResult))
    return summarizer
