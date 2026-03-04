"""数据契约模型单元测试"""
import pytest
from pydantic import ValidationError
from src.models.contracts import (
    PendingAction,
    PendingActionCandidate,
    PendingActionType,
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    RiskFlag,
    SafetyResult,
    now_iso,
)
from src.workflow.context import WorkflowContext
from src.models.db import InternalStatus


@pytest.mark.unit  # pytest标记：这是单元测试
class TestProteinDesignTask:  # 测试类：测试ProteinDesignTask模型
    """ProteinDesignTask测试类"""

    def test_task_creation_with_required_fields(self):
        """测试任务创建需要必需字段"""
        task = ProteinDesignTask(
            task_id="test_001",
            goal="测试目标",
            constraints={},
            metadata={},
        )
        
        assert task.task_id == "test_001"  # 验证task_id能够正确设置
        assert task.goal == "测试目标"  # 验证goal能够正确设置
        assert isinstance(task.constraints, dict)  # 验证constraints是字典类型
        assert isinstance(task.metadata, dict)  # 验证metadata是字典类型

    def test_task_default_constraints_and_metadata(self):
        """测试任务默认约束和元数据"""
        task = ProteinDesignTask(
            task_id="test_002",
            goal="测试",
            # 这里没有提供 constraints 和 metadata，应该使用默认值
        )
        
        assert task.constraints == {}  # 验证默认值是 空字典
        assert task.metadata == {}  # 验证默认值是 空字典


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
            failure_type=None,
            error_message=None,
            error_details={},
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
                status=status, # type: ignore
                failure_type=None,
                error_message=None,
                error_details={},
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
            status=InternalStatus.CREATED,
        )
        
        assert context.task == sample_task
        assert context.plan is None
        assert isinstance(context.step_results, dict)
        assert isinstance(context.safety_events, list)
        assert context.status == InternalStatus.CREATED


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


@pytest.mark.unit
class TestCandidateSetContracts:
    """CandidateSetOutput v1 契约测试。"""

    def test_candidate_payload_syncs_to_structured_payload(self, sample_plan: Plan):
        candidate = PendingActionCandidate(
            candidate_id="plan_a",
            payload=sample_plan,
        )

        assert candidate.payload == sample_plan
        assert candidate.structured_payload == sample_plan

    def test_candidate_structured_payload_backfills_payload(self, sample_plan: Plan):
        candidate = PendingActionCandidate(
            candidate_id="plan_b",
            structured_payload=sample_plan,
        )

        assert candidate.structured_payload == sample_plan
        assert candidate.payload == sample_plan

    def test_candidate_non_numeric_score_rejected(self, sample_plan: Plan):
        with pytest.raises(ValueError, match="score_breakdown\\.overall"):
            PendingActionCandidate(
                candidate_id="plan_c",
                payload=sample_plan,
                score_breakdown={"overall": "high"},  # type: ignore[arg-type]
            )

    def test_candidate_invalid_risk_or_cost_enum_rejected(self, sample_plan: Plan):
        with pytest.raises(ValidationError):
            PendingActionCandidate(
                candidate_id="plan_d",
                payload=sample_plan,
                risk_level="warn",  # type: ignore[arg-type]
                cost_estimate="low",
            )
        with pytest.raises(ValidationError):
            PendingActionCandidate(
                candidate_id="plan_e",
                payload=sample_plan,
                risk_level="low",
                cost_estimate="expensive",  # type: ignore[arg-type]
            )

    def test_candidate_tool_fields_sync_to_metadata(self, sample_plan: Plan):
        candidate = PendingActionCandidate(
            candidate_id="plan_tool_sync",
            payload=sample_plan,
            tool_id="esmfold",
            capability_id="structure_prediction",
            io_type="sequence_to_structure",
        )

        assert candidate.tool_id == "esmfold"
        assert candidate.capability_id == "structure_prediction"
        assert candidate.io_type == "sequence_to_structure"
        assert candidate.adapter_mode == "unknown"
        assert candidate.metadata["tool_id"] == "esmfold"
        assert candidate.metadata["capability_id"] == "structure_prediction"
        assert candidate.metadata["io_type"] == "sequence_to_structure"
        assert candidate.metadata["adapter_mode"] == "unknown"

    def test_candidate_tool_fields_can_backfill_from_metadata(self, sample_plan: Plan):
        candidate = PendingActionCandidate(
            candidate_id="plan_tool_meta",
            payload=sample_plan,
            metadata={
                "tool_id": "nim_esmfold",
                "capability_id": "structure_prediction",
                "io_type": "sequence_to_structure",
                "adapter_mode": "remote",
            },
        )

        assert candidate.tool_id == "nim_esmfold"
        assert candidate.capability_id == "structure_prediction"
        assert candidate.io_type == "sequence_to_structure"
        assert candidate.adapter_mode == "remote"

    def test_candidate_tool_metadata_conflict_rejected(self, sample_plan: Plan):
        with pytest.raises(ValueError, match="metadata\\.tool_id must match tool_id"):
            PendingActionCandidate(
                candidate_id="plan_tool_conflict",
                payload=sample_plan,
                tool_id="esmfold",
                metadata={"tool_id": "protein_mpnn"},
            )

    def test_candidate_invalid_adapter_mode_in_metadata_rejected(
        self, sample_plan: Plan
    ):
        with pytest.raises(ValueError, match="metadata\\.adapter_mode must be one of"):
            PendingActionCandidate(
                candidate_id="plan_tool_bad_mode",
                payload=sample_plan,
                metadata={
                    "tool_id": "esmfold",
                    "capability_id": "structure_prediction",
                    "io_type": "sequence_to_structure",
                    "adapter_mode": "cloud",
                },
            )

    def test_pending_action_default_recommendation_compat(self, sample_task, sample_plan):
        candidate = PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        action = PendingAction(
            pending_action_id="pa_001",
            task_id=sample_task.task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            candidates=[candidate],
            explanation="test",
            default_suggestion="plan_a",
        )

        assert action.default_suggestion == "plan_a"
        assert action.default_recommendation == "plan_a"

    def test_pending_action_conflicting_default_fields_rejected(
        self, sample_task, sample_plan
    ):
        candidate = PendingActionCandidate(candidate_id="plan_a", payload=sample_plan)
        with pytest.raises(
            ValueError,
            match="default_suggestion and default_recommendation must match",
        ):
            PendingAction(
                pending_action_id="pa_002",
                task_id=sample_task.task_id,
                action_type=PendingActionType.PLAN_CONFIRM,
                candidates=[candidate],
                explanation="test",
                default_suggestion="plan_a",
                default_recommendation="plan_b",
            )
