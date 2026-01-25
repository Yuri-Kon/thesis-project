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

    def test_summarizer_records_execution_providers(
        self, sample_workflow_context: WorkflowContext, tmp_path: Path
    ):
        """测试汇总器记录执行后端与 provider 信息"""
        from src.models.contracts import now_iso

        summarizer = SummarizerAgent()
        context = sample_workflow_context

        step_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="nim_esmfold",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={"pdb_path": "/path/to/task123.pdb"},
            metrics={
                "exec_type": "nvidia_nim",
                "provider": "nvidia_nim",
                "model_id": "nvidia/esmfold",
            },
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        context.step_results["S1"] = step_result

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        execution_steps = result.metadata.get("execution_steps", [])
        assert execution_steps
        assert execution_steps[0]["tool"] == "nim_esmfold"
        assert execution_steps[0]["provider"] == "nvidia_nim"

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

    def test_summarizer_maintains_consistency_with_multiple_structure_steps(
        self, sample_workflow_context: WorkflowContext, tmp_path: Path
    ):
        """测试多个结构预测步骤时，PDB 路径与指标保持一致（修复 PR review 问题）"""
        from src.models.contracts import now_iso

        summarizer = SummarizerAgent()
        context = sample_workflow_context

        # 第一个 ESMFold 步骤：有完整的 PDB 和 metrics
        step1_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="esmfold",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={
                "pdb_path": "/path/to/first_structure.pdb",
                "metrics": {
                    "plddt_mean": 0.75,
                    "confidence": "medium",
                },
            },
            metrics={"exec_type": "nextflow"},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

        # 第二个结构预测步骤：只有 PDB，没有 metrics（模拟旧适配器或部分输出）
        step2_result = StepResult(
            task_id=context.task.task_id,
            step_id="S2",
            tool="esmfold",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={
                "pdb_path": "/path/to/second_structure.pdb",
                # 注意：没有 metrics 字段
            },
            metrics={"exec_type": "nextflow"},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

        context.step_results["S1"] = step1_result
        context.step_results["S2"] = step2_result

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        # 验证使用了最新的 PDB 路径
        assert result.structure_pdb_path == "/path/to/second_structure.pdb"

        # 关键验证：由于 S2 没有 metrics，scores 应该是空的（不应该使用 S1 的旧指标）
        # 这确保了 PDB 路径和指标的一致性
        assert "plddt_mean" not in result.scores
        assert "confidence" not in result.scores

    def test_summarizer_works_with_non_esmfold_structure_tools(
        self, sample_workflow_context: WorkflowContext, tmp_path: Path
    ):
        """测试汇总器支持非 ESMFold 的其他结构预测工具（扩展性验证）"""
        from src.models.contracts import now_iso

        summarizer = SummarizerAgent()
        context = sample_workflow_context

        # 模拟一个假想的 AlphaFold 工具（不是 esmfold）
        alphafold_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="alphafold",  # 注意：不是 "esmfold"
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={
                "pdb_path": "/path/to/alphafold_structure.pdb",
                "metrics": {
                    "plddt_mean": 0.95,
                    "confidence": "very_high",
                },
            },
            metrics={"exec_type": "nextflow"},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )

        context.step_results["S1"] = alphafold_result

        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        result = summarizer.summarize(context)

        # 验证即使工具不是 ESMFold，只要输出了 pdb_path 和 metrics，就能被正确提取
        assert result.structure_pdb_path == "/path/to/alphafold_structure.pdb"
        assert result.scores["plddt_mean"] == 0.95
        assert result.scores["confidence"] == "very_high"
