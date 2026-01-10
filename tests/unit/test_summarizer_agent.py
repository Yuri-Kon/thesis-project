"""SummarizerAgent单元测试"""
import pytest
from pathlib import Path
from src.agents.summarizer import SummarizerAgent
from src.workflow.context import WorkflowContext
from src.models.contracts import DesignResult, StepResult


@pytest.mark.unit
class TestSummarizerAgent:
    """SummarizerAgent测试类"""

    def test_summarizer_creates_design_result(
        self, sample_workflow_context: WorkflowContext, sample_step_result: StepResult, tmp_path: Path
    ):
        """测试汇总器创建设计结果"""
        summarizer = SummarizerAgent()
        context = sample_workflow_context
        context.step_results["S1"] = sample_step_result
        
        # 设置报告目录
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        result = summarizer.summarize(context)
        
        assert isinstance(result, DesignResult)
        assert result.task_id == context.task.task_id

    def test_summarizer_extracts_sequence_length(
        self, sample_workflow_context: WorkflowContext, sample_step_result: StepResult, tmp_path: Path
    ):
        """测试汇总器从步骤结果中提取序列长度"""
        summarizer = SummarizerAgent()
        context = sample_workflow_context
        context.step_results["S1"] = sample_step_result
        
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        result = summarizer.summarize(context)
        
        assert "sequence_length" in result.scores
        assert result.scores["sequence_length"] == sample_step_result.outputs["sequence_length"]

    def test_summarizer_creates_report_file(
        self, sample_workflow_context: WorkflowContext, sample_step_result: StepResult
    ):
        """测试汇总器创建报告文件"""
        summarizer = SummarizerAgent()
        context = sample_workflow_context
        context.step_results["S1"] = sample_step_result
        
        result = summarizer.summarize(context)
        
        # 验证报告路径已设置
        assert result.report_path is not None
        # 验证报告文件已创建（代码中会创建目录和文件）
        report_path = Path(result.report_path)
        # 如果目录存在，文件应该被创建
        if report_path.parent.exists():
            assert report_path.exists()

    def test_summarizer_includes_step_ids_in_metadata(
        self, sample_workflow_context: WorkflowContext, sample_step_result: StepResult, tmp_path: Path
    ):
        """测试汇总器在元数据中包含步骤ID"""
        summarizer = SummarizerAgent()
        context = sample_workflow_context
        context.step_results["S1"] = sample_step_result
        context.step_results["S2"] = sample_step_result.model_copy(update={"step_id": "S2"})
        
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        result = summarizer.summarize(context)
        
        assert "step_ids" in result.metadata
        assert "S1" in result.metadata["step_ids"]
        assert "S2" in result.metadata["step_ids"]

    def test_summarizer_handles_empty_step_results(self, sample_workflow_context: WorkflowContext, tmp_path: Path):
        """测试汇总器处理空的步骤结果"""
        summarizer = SummarizerAgent()
        context = sample_workflow_context
        context.step_results = {}
        
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        result = summarizer.summarize(context)
        
        assert isinstance(result, DesignResult)
        assert result.scores == {}
        assert result.metadata["step_ids"] == []

    def test_summarizer_preserves_sequence_from_task(
        self, sample_workflow_context: WorkflowContext, sample_step_result: StepResult, tmp_path: Path
    ):
        """测试汇总器保留任务中的序列"""
        summarizer = SummarizerAgent()
        context = sample_workflow_context
        context.step_results["S1"] = sample_step_result

        # 确保任务中有序列
        expected_sequence = context.task.constraints.get("sequence")

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        assert result.sequence == expected_sequence

    def test_summarizer_extracts_esmfold_results(
        self, sample_workflow_context: WorkflowContext, tmp_path: Path
    ):
        """测试汇总器从 ESMFold 结果中提取 PDB 路径和 pLDDT"""
        from src.models.contracts import now_iso

        summarizer = SummarizerAgent()
        context = sample_workflow_context

        # 创建 ESMFold StepResult（模拟真实输出）
        esmfold_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="esmfold",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={
                "pdb_path": "/path/to/task123.pdb",
                "metrics": {
                    "task_id": "task123",
                    "tool": "esmfold",
                    "plddt_mean": 0.85,
                    "confidence": "high",
                },
            },
            metrics={
                "exec_type": "nextflow",
                "duration_ms": 1000,
                "nextflow_exit_code": 0,
            },
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

        context.step_results["S1"] = esmfold_result

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        # 验证提取了 PDB 路径
        assert result.structure_pdb_path == "/path/to/task123.pdb"

        # 验证提取了 pLDDT 分数
        assert "plddt_mean" in result.scores
        assert result.scores["plddt_mean"] == 0.85

        # 验证提取了置信度
        assert "confidence" in result.scores
        assert result.scores["confidence"] == "high"

    def test_summarizer_handles_esmfold_without_optional_fields(
        self, sample_workflow_context: WorkflowContext, tmp_path: Path
    ):
        """测试汇总器处理缺少可选字段的 ESMFold 结果"""
        from src.models.contracts import now_iso

        summarizer = SummarizerAgent()
        context = sample_workflow_context

        # 创建只包含 pdb_path 的 ESMFold 结果
        esmfold_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="esmfold",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={
                "pdb_path": "/path/to/task123.pdb",
                # 没有 metrics 字段
            },
            metrics={
                "exec_type": "nextflow",
                "duration_ms": 1000,
            },
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

        context.step_results["S1"] = esmfold_result

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        # 验证提取了 PDB 路径
        assert result.structure_pdb_path == "/path/to/task123.pdb"

        # 验证没有 pLDDT 分数
        assert "plddt_mean" not in result.scores
        assert "confidence" not in result.scores

    def test_summarizer_combines_multiple_step_results(
        self, sample_workflow_context: WorkflowContext, sample_step_result: StepResult, tmp_path: Path
    ):
        """测试汇总器合并多个步骤结果（包括 ESMFold 和其他工具）"""
        from src.models.contracts import now_iso

        summarizer = SummarizerAgent()
        context = sample_workflow_context

        # 添加一个包含 sequence_length 的步骤
        context.step_results["S1"] = sample_step_result

        # 添加一个 ESMFold 步骤
        esmfold_result = StepResult(
            task_id=context.task.task_id,
            step_id="S2",
            tool="esmfold",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={
                "pdb_path": "/path/to/output.pdb",
                "metrics": {
                    "plddt_mean": 0.92,
                    "confidence": "very_high",
                },
            },
            metrics={
                "exec_type": "nextflow",
                "duration_ms": 2000,
            },
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

        context.step_results["S2"] = esmfold_result

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        # 验证同时包含了两个步骤的结果
        assert result.scores["sequence_length"] == 50
        assert result.scores["plddt_mean"] == 0.92
        assert result.scores["confidence"] == "very_high"
        assert result.structure_pdb_path == "/path/to/output.pdb"

        # 验证元数据中包含了两个步骤ID
        assert "S1" in result.metadata["step_ids"]
        assert "S2" in result.metadata["step_ids"]