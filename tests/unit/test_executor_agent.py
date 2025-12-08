"""ExecutorAgent单元测试"""
import pytest
from src.agents.executor import ExecutorAgent
from src.models.contracts import Plan, WorkflowContext, StepResult


@pytest.mark.unit
class TestExecutorAgent:
    """ExecutorAgent测试类"""

    def test_run_step_requires_plan_in_context(self, sample_workflow_context: WorkflowContext):
        """测试执行步骤需要上下文中有计划"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = None
        
        with pytest.raises(AssertionError, match="Plan must be set in context"):
            executor.run_step("S1", context)

    def test_run_step_creates_result(self, sample_plan: Plan, sample_workflow_context: WorkflowContext):
        """测试执行步骤生成结果"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = sample_plan
        
        result = executor.run_step("S1", context)
        
        assert isinstance(result, StepResult)
        assert result.task_id == context.task.task_id
        assert result.step_id == "S1"
        assert result.status == "success"

    def test_run_step_stores_result_in_context(self, sample_plan: Plan, sample_workflow_context: WorkflowContext):
        """测试步骤结果存储在上下文中"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = sample_plan
        
        result = executor.run_step("S1", context)
        
        assert "S1" in context.step_results
        assert context.step_results["S1"] == result

    def test_run_step_includes_sequence_length_in_outputs(
        self, sample_plan: Plan, sample_workflow_context: WorkflowContext
    ):
        """测试步骤输出包含序列长度"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = sample_plan
        
        # 设置步骤输入中的序列
        context.plan.steps[0].inputs["sequence"] = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR"
        
        result = executor.run_step("S1", context)
        
        assert "sequence_length" in result.outputs
        assert result.outputs["sequence_length"] == len("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR")

    def test_run_step_includes_metrics(self, sample_plan: Plan, sample_workflow_context: WorkflowContext):
        """测试步骤结果包含指标"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = sample_plan
        
        result = executor.run_step("S1", context)
        
        assert "runtime_ms" in result.metrics
        assert "backend" in result.metrics
        assert result.metrics["backend"] == "dummy_executor"

    def test_run_plan_executes_all_steps(self, sample_plan: Plan, sample_workflow_context: WorkflowContext):
        """测试执行计划运行所有步骤"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        
        # 添加多个步骤
        sample_plan.steps.append(
            sample_plan.steps[0].model_copy(update={"id": "S2"})
        )
        
        result_plan = executor.run_plan(sample_plan, context)
        
        assert len(context.step_results) == 2
        assert "S1" in context.step_results
        assert "S2" in context.step_results
        assert result_plan == sample_plan

    def test_run_plan_sets_plan_in_context(self, sample_plan: Plan, sample_workflow_context: WorkflowContext):
        """测试执行计划时设置上下文中的计划"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = None
        
        executor.run_plan(sample_plan, context)
        
        assert context.plan == sample_plan

    def test_run_step_with_missing_step_id_raises_error(
        self, sample_plan: Plan, sample_workflow_context: WorkflowContext
    ):
        """测试执行不存在的步骤ID时抛出错误"""
        executor = ExecutorAgent()
        context = sample_workflow_context
        context.plan = sample_plan
        
        with pytest.raises(StopIteration):
            executor.run_step("NONEXISTENT", context)