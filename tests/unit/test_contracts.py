"""数据契约模型单元测试"""
import pytest
from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    WorkflowContext,
    RiskFlag,
    SafetyResult,
    now_iso,
)


@pytest.mark.unit
class TestProteinDesignTask:
    """ProteinDesignTask测试类"""

    def test_task_creation_with_required_fields(self):
        """测试任务创建需要必需字段"""
        task = ProteinDesignTask(
            task_id="test_001",
            goal="测试目标",
            constraints={},
            metadata={},
        )
        
        assert task.task_id == "test_001"
        assert task.goal == "测试目标"
        assert isinstance(task.constraints, dict)
        assert isinstance(task.metadata, dict)

    def test_task_default_constraints_and_metadata(self):
        """测试任务默认约束和元数据"""
        task = ProteinDesignTask(
            task_id="test_002",
            goal="测试",
        )
        
        assert task.constraints == {}
        assert task.metadata == {}


@pytest.mark.unit
class TestPlan:
    """Plan测试类"""

    def test_plan_creation(self, sample_task: ProteinDesignTask):
        """测试计划创建"""
        plan = Plan(
            task_id=sample_task.task_id,
            steps=[],
            constraints={},
            metadata={},
        )
        
        assert plan.task_id == sample_task.task_id
        assert isinstance(plan.steps, list)

    def test_plan_with_steps(self, sample_task: ProteinDesignTask):
        """测试包含步骤的计划"""
        step = PlanStep(
            id="S1",
            tool="dummy_tool",
            inputs={},
            metadata={},
        )
        plan = Plan(
            task_id=sample_task.task_id,
            steps=[step],
            constraints={},
            metadata={},
        )
        
        assert len(plan.steps) == 1
        assert plan.steps[0].id == "S1"


@pytest.mark.unit
class TestStepResult:
    """StepResult测试类"""

    def test_step_result_creation(self):
        """测试步骤结果创建"""
        result = StepResult(
            task_id="task_001",
            step_id="S1",
            tool="dummy_tool",
            status="success",
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        
        assert result.task_id == "task_001"
        assert result.step_id == "S1"
        assert result.status == "success"
        assert result.timestamp is not None

    def test_step_result_status_values(self):
        """测试步骤结果状态值"""
        valid_statuses = ["success", "failed", "skipped"]
        
        for status in valid_statuses:
            result = StepResult(
                task_id="task_001",
                step_id="S1",
                tool="dummy_tool",
                status=status,
                outputs={},
                metrics={},
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
            assert result.status == status


@pytest.mark.unit
class TestDesignResult:
    """DesignResult测试类"""

    def test_design_result_creation(self, tmp_path):
        """测试设计结果创建"""
        report_path = tmp_path / "report.json"
        result = DesignResult(
            task_id="task_001",
            sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR",
            structure_pdb_path=None,
            scores={},
            risk_flags=[],
            report_path=str(report_path),
            metadata={},
        )
        
        assert result.task_id == "task_001"
        assert result.sequence is not None
        assert result.report_path == str(report_path)


@pytest.mark.unit
class TestWorkflowContext:
    """WorkflowContext测试类"""

    def test_context_creation(self, sample_task: ProteinDesignTask):
        """测试工作流上下文创建"""
        context = WorkflowContext(
            task=sample_task,
            plan=None,
            step_results={},
            safety_events=[],
            design_result=None,
        )
        
        assert context.task == sample_task
        assert context.plan is None
        assert isinstance(context.step_results, dict)
        assert isinstance(context.safety_events, list)


@pytest.mark.unit
class TestRiskFlag:
    """RiskFlag测试类"""

    def test_risk_flag_creation(self):
        """测试风险标志创建"""
        flag = RiskFlag(
            level="warn",
            code="TEST_001",
            message="测试警告",
            scope="step",
            step_id="S1",
            details={},
        )
        
        assert flag.level == "warn"
        assert flag.code == "TEST_001"
        assert flag.scope == "step"
        assert flag.step_id == "S1"


@pytest.mark.unit
class TestSafetyResult:
    """SafetyResult测试类"""

    def test_safety_result_creation(self):
        """测试安全检查结果创建"""
        result = SafetyResult(
            task_id="task_001",
            phase="input",
            scope="task",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )
        
        assert result.task_id == "task_001"
        assert result.phase == "input"
        assert result.action == "allow"