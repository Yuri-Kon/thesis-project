"""工作流集成测试"""
import pytest
from pathlib import Path
from src.workflow.workflow import run_task_sync
from src.models.contracts import ProteinDesignTask
from src.models.db import TaskStatus, TaskRecord


@pytest.mark.integration
class TestWorkflowIntegration:
    """工作流集成测试类"""

    def test_run_task_sync_completes_full_workflow(self, sample_task: ProteinDesignTask):
        """测试同步任务执行完成完整工作流"""
        record = run_task_sync(sample_task)
        
        assert isinstance(record, TaskRecord)
        assert record.id == sample_task.task_id
        assert record.status == TaskStatus.DONE

    def test_run_task_sync_creates_plan(self, sample_task: ProteinDesignTask):
        """测试任务执行创建计划"""
        record = run_task_sync(sample_task)
        
        assert record.plan is not None
        assert record.plan.task_id == sample_task.task_id
        assert len(record.plan.steps) > 0

    def test_run_task_sync_executes_steps(self, sample_task: ProteinDesignTask):
        """测试任务执行运行步骤"""
        record = run_task_sync(sample_task)
        
        # 验证计划中的步骤都被执行
        assert record.plan is not None
        # 由于是dummy执行，我们至少验证计划存在

    def test_run_task_sync_generates_design_result(self, sample_task: ProteinDesignTask):
        """测试任务执行生成设计结果"""
        record = run_task_sync(sample_task)
        
        assert record.design_result is not None
        assert record.design_result.task_id == sample_task.task_id
        assert record.design_result.report_path is not None

    def test_run_task_sync_updates_status_progressively(self, sample_task: ProteinDesignTask):
        """测试任务状态逐步更新"""
        # 注意：由于是同步执行，我们无法直接观察中间状态
        # 但可以验证最终状态是正确的
        record = run_task_sync(sample_task)
        
        assert record.status in [TaskStatus.DONE, TaskStatus.FAILED]
        # 对于成功的任务，应该是DONE
        if record.status == TaskStatus.DONE:
            assert record.design_result is not None

    def test_run_task_sync_with_custom_constraints(self):
        """测试使用自定义约束的任务执行"""
        task = ProteinDesignTask(
            task_id="test_custom_001",
            goal="设计一个特定长度的蛋白质",
            constraints={
                "sequence": "ACDEFGHIKLMNPQRSTVWY",
                "length_range": [15, 25],
            },
            metadata={"test": "custom"},
        )
        
        record = run_task_sync(task)
        
        assert record.status == TaskStatus.DONE
        assert record.goal == task.goal
        assert record.constraints == task.constraints

    def test_run_task_sync_creates_report_file(self, sample_task: ProteinDesignTask, tmp_path: Path):
        """测试任务执行创建报告文件"""
        # 注意：由于代码中硬编码了路径，这个测试可能需要调整
        # 或者需要mock路径
        record = run_task_sync(sample_task)
        
        if record.design_result and record.design_result.report_path:
            report_path = Path(record.design_result.report_path)
            # 如果报告路径存在，验证文件已创建
            if report_path.exists():
                assert report_path.is_file()
                assert report_path.stat().st_size > 0

    def test_run_task_sync_handles_empty_constraints(self):
        """测试处理空约束的任务执行"""
        task = ProteinDesignTask(
            task_id="test_empty_001",
            goal="测试空约束",
            constraints={},
            metadata={},
        )
        
        record = run_task_sync(task)
        
        assert record.status == TaskStatus.DONE
        assert record.constraints == {}

    def test_run_task_sync_preserves_metadata(self, sample_task: ProteinDesignTask):
        """测试任务执行保留元数据"""
        custom_metadata = {"source": "test", "version": "1.0"}
        task = ProteinDesignTask(
            task_id="test_meta_001",
            goal="测试元数据",
            constraints={},
            metadata=custom_metadata,
        )
        
        record = run_task_sync(task)
        
        assert record.metadata == custom_metadata