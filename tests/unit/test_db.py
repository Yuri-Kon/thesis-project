"""数据库模型单元测试"""
import pytest
from src.models.db import (
    ExternalStatus,
    InternalStatus,
    StepStatus,
    TaskRecord,
    StepRecord,
    derive_task_status,
    step_result_to_record,
    to_external_status,
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
    """ExternalStatus / InternalStatus 枚举测试"""

    def test_task_status_values(self):
        """测试 ExternalStatus 状态值"""
        expected_external = {
            "CREATED",
            "PLANNING",
            "WAITING_PLAN_CONFIRM",
            "PLANNED",
            "RUNNING",
            "WAITING_PATCH_CONFIRM",
            "WAITING_REPLAN_CONFIRM",
            "SUMMARIZING",
            "DONE",
            "FAILED",
            "CANCELLED",
        }
        expected_internal = {
            "CREATED",
            "PLANNING",
            "WAITING_PLAN_CONFIRM",
            "PLANNED",
            "RUNNING",
            "WAITING_PATCH",
            "PATCHING",
            "WAITING_REPLAN",
            "REPLANNING",
            "SUMMARIZING",
            "DONE",
            "FAILED",
            "CANCELLED",
        }

        assert set(ExternalStatus.__members__.keys()) == expected_external
        assert {status.value for status in ExternalStatus} == expected_external
        assert set(InternalStatus.__members__.keys()) == expected_internal
        assert {status.value for status in InternalStatus} == expected_internal

    def test_terminal_states(self):
        """测试终端状态"""
        from src.models.db import (
            TERMINAL_EXTERNAL_STATUSES,
            TERMINAL_INTERNAL_STATUSES,
        )

        assert TERMINAL_EXTERNAL_STATUSES == {
            ExternalStatus.DONE,
            ExternalStatus.FAILED,
            ExternalStatus.CANCELLED,
        }
        assert TERMINAL_INTERNAL_STATUSES == {
            InternalStatus.DONE,
            InternalStatus.FAILED,
            InternalStatus.CANCELLED,
        }

    def test_internal_to_external_mapping(self):
        """测试内部状态到外部语义状态映射"""
        assert (
            to_external_status(InternalStatus.WAITING_PATCH)
            == ExternalStatus.WAITING_PATCH_CONFIRM
        )
        assert (
            to_external_status(InternalStatus.PATCHING)
            == ExternalStatus.WAITING_PATCH_CONFIRM
        )
        assert (
            to_external_status(InternalStatus.WAITING_REPLAN)
            == ExternalStatus.WAITING_REPLAN_CONFIRM
        )
        assert (
            to_external_status(InternalStatus.REPLANNING)
            == ExternalStatus.WAITING_REPLAN_CONFIRM
        )
        assert (
            to_external_status(InternalStatus.RUNNING)
            == ExternalStatus.RUNNING
        )


@pytest.mark.unit
class TestTaskRecord:
    """TaskRecord测试类"""

    def test_task_record_creation(self, sample_task: ProteinDesignTask):
        """测试任务记录创建"""
        record = TaskRecord(
            id=sample_task.task_id,
            status=ExternalStatus.CREATED,
            internal_status=InternalStatus.CREATED,
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
        assert record.status == ExternalStatus.CREATED
        assert record.internal_status == InternalStatus.CREATED
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
        
        assert status == InternalStatus.DONE

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
        
        assert status == InternalStatus.FAILED

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
        
        assert status == InternalStatus.FAILED

    def test_derive_status_created_when_no_plan(self, sample_task: ProteinDesignTask):
        """测试没有计划时状态为CREATED"""
        status = derive_task_status(
            sample_task,
            None,
            {},
            [],
            None,
        )
        
        assert status == InternalStatus.CREATED

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
        
        assert status == InternalStatus.PLANNED

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
        
        assert status == InternalStatus.RUNNING


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
