"""数据库模型单元测试"""
import pytest
from src.models.db import (
    TaskStatus,
    StepStatus,
    TaskRecord,
    StepRecord,
    derive_task_status,
    step_result_to_record,
)
from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    SafetyResult,
    RiskFlag,
    now_iso,
)


@pytest.mark.unit
class TestTaskStatus:
    """TaskStatus枚举测试"""

    def test_task_status_values(self):
        """测试任务状态值"""
        assert TaskStatus.CREATED == "CREATED"
        assert TaskStatus.PLANNED == "PLANNED"
        assert TaskStatus.DONE == "DONE"
        assert TaskStatus.FAILED == "FAILED"

    def test_terminal_states(self):
        """测试终端状态"""
        from src.models.db import TERMINAL_STATES
        assert TaskStatus.DONE in TERMINAL_STATES
        assert TaskStatus.FAILED in TERMINAL_STATES


@pytest.mark.unit
class TestTaskRecord:
    """TaskRecord测试类"""

    def test_task_record_creation(self, sample_task: ProteinDesignTask):
        """测试任务记录创建"""
        record = TaskRecord(
            id=sample_task.task_id,
            status=TaskStatus.CREATED,
            created_at=now_iso(),
            updated_at=now_iso(),
            goal=sample_task.goal,
            constraints=sample_task.constraints,
            metadata=sample_task.metadata,
            plan=None,
            design_result=None,
            safety_events=[],
        )
        
        assert record.id == sample_task.task_id
        assert record.status == TaskStatus.CREATED
        assert record.goal == sample_task.goal


@pytest.mark.unit
class TestDeriveTaskStatus:
    """derive_task_status函数测试"""

    def test_derive_status_done_when_design_result_exists(self, sample_task: ProteinDesignTask):
        """测试有设计结果时状态为DONE"""
        design_result = DesignResult(
            task_id=sample_task.task_id,
            sequence=None,
            structure_pdb_path=None,
            scores={},
            risk_flags=[],
            report_path="test.json",
            metadata={},
        )
        
        status = derive_task_status(
            sample_task,
            None,
            {},
            [],
            design_result,
        )
        
        assert status == TaskStatus.DONE

    def test_derive_status_failed_with_failed_step(self, sample_task: ProteinDesignTask):
        """测试有失败步骤时状态为FAILED"""
        failed_result = StepResult(
            task_id=sample_task.task_id,
            step_id="S1",
            tool="dummy_tool",
            status="failed",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        
        status = derive_task_status(
            sample_task,
            None,
            {"S1": failed_result},
            [],
            None,
        )
        
        assert status == TaskStatus.FAILED

    def test_derive_status_failed_with_block_safety(self, sample_task: ProteinDesignTask):
        """测试有block安全事件时状态为FAILED"""
        safety_result = SafetyResult(
            task_id=sample_task.task_id,
            phase="output",
            scope="result",
            risk_flags=[],
            action="block",
            timestamp=now_iso(),
        )
        
        status = derive_task_status(
            sample_task,
            None,
            {},
            [safety_result],
            None,
        )
        
        assert status == TaskStatus.FAILED

    def test_derive_status_created_when_no_plan(self, sample_task: ProteinDesignTask):
        """测试没有计划时状态为CREATED"""
        status = derive_task_status(
            sample_task,
            None,
            {},
            [],
            None,
        )
        
        assert status == TaskStatus.CREATED

    def test_derive_status_planned_when_plan_exists_but_no_steps(self, sample_task: ProteinDesignTask):
        """测试有计划但无步骤执行时状态为PLANNED"""
        plan = Plan(
            task_id=sample_task.task_id,
            steps=[],
            constraints={},
            metadata={},
        )
        
        status = derive_task_status(
            sample_task,
            plan,
            {},
            [],
            None,
        )
        
        assert status == TaskStatus.PLANNED

    def test_derive_status_running_when_steps_executed(self, sample_task: ProteinDesignTask):
        """测试有步骤执行时状态为RUNNING"""
        plan = Plan(
            task_id=sample_task.task_id,
            steps=[PlanStep(id="S1", tool="dummy", inputs={}, metadata={})],
            constraints={},
            metadata={},
        )
        
        step_result = StepResult(
            task_id=sample_task.task_id,
            step_id="S1",
            tool="dummy",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        
        status = derive_task_status(
            sample_task,
            plan,
            {"S1": step_result},
            [],
            None,
        )
        
        assert status == TaskStatus.RUNNING


@pytest.mark.unit
class TestStepResultToRecord:
    """step_result_to_record函数测试"""

    def test_step_result_to_record_success(self, sample_step_result: StepResult):
        """测试成功步骤结果转换为记录"""
        record = step_result_to_record(sample_step_result)
        
        assert record.task_id == sample_step_result.task_id
        assert record.step_id == sample_step_result.step_id
        assert record.status == StepStatus.SUCCEEDED
        assert record.finished_at == sample_step_result.timestamp

    def test_step_result_to_record_failed(self):
        """测试失败步骤结果转换为记录"""
        failed_result = StepResult(
            task_id="task_001",
            step_id="S1",
            tool="dummy_tool",
            status="failed",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        
        record = step_result_to_record(failed_result)
        
        assert record.status == StepStatus.FAILED

    def test_step_result_to_record_skipped(self):
        """测试跳过步骤结果转换为记录"""
        skipped_result = StepResult(
            task_id="task_001",
            step_id="S1",
            tool="dummy_tool",
            status="skipped",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        
        record = step_result_to_record(skipped_result)
        
        assert record.status == StepStatus.SKIPPED
