"""PlannerAgent单元测试"""
import pytest
from src.agents.planner import PlannerAgent
from src.models.contracts import ProteinDesignTask, Plan, PlanStep, ReplanRequest


@pytest.mark.unit
class TestPlannerAgent:
    """PlannerAgent测试类"""

    def test_plan_creates_plan_with_correct_task_id(self, sample_task: ProteinDesignTask):
        """测试计划生成时task_id正确"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        assert plan.task_id == sample_task.task_id
        assert isinstance(plan, Plan)

    def test_plan_creates_single_step_by_default(self, sample_task: ProteinDesignTask):
        """测试默认生成单步计划"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        assert len(plan.steps) == 1
        assert plan.steps[0].id == "S1"
        assert plan.steps[0].tool == "esmfold"

    def test_plan_includes_sequence_from_constraints(self, sample_task: ProteinDesignTask):
        """测试计划包含约束中的序列"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        step = plan.steps[0]
        assert "sequence" in step.inputs
        assert step.inputs["sequence"] == sample_task.constraints.get("sequence")

    def test_plan_uses_default_sequence_when_missing(self):
        """测试当约束中没有序列时使用默认序列"""
        task = ProteinDesignTask(
            task_id="test_002",
            goal="测试任务",
            constraints={},  # 没有sequence
            metadata={},
        )
        planner = PlannerAgent()
        plan = planner.plan(task)
        
        step = plan.steps[0]
        assert "sequence" in step.inputs
        assert len(step.inputs["sequence"]) > 0  # 有默认值

    def test_plan_preserves_constraints(self, sample_task: ProteinDesignTask):
        """测试计划保留任务约束"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        assert plan.constraints == sample_task.constraints

    def test_plan_step_has_required_fields(self, sample_task: ProteinDesignTask):
        """测试计划步骤包含必需字段"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        step = plan.steps[0]
        assert step.id is not None
        assert step.tool is not None
        assert isinstance(step.inputs, dict)
        assert isinstance(step.metadata, dict)

    def test_replan_replaces_failed_step(self, sample_task: ProteinDesignTask):
        """测试再规划会替换失败步骤的工具"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)

        request = ReplanRequest(
            task_id=sample_task.task_id,
            original_plan=plan,
            failed_steps=[plan.steps[0].id],
            safety_events=[],
            reason="test_replan",
        )

        replanned_plan = planner.replan(request)

        assert replanned_plan.task_id == sample_task.task_id
        assert replanned_plan.steps[0].tool != plan.steps[0].tool
