"""SummarizerAgent单元测试"""
import json
import pytest
from pathlib import Path
from src.agents.summarizer import (
    SummarizerAgent,
    generate_de_novo_report,
    write_de_novo_reports,
    _is_de_novo_task,
    _render_de_novo_markdown,
    DeNovoReport,
)
from src.workflow.context import WorkflowContext
from src.models.contracts import (
    DesignResult,
    StepResult,
    ProteinDesignTask,
    Plan,
    PlanStep,
    SafetyResult,
    RiskFlag,
    now_iso,
)


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


@pytest.mark.unit
class TestDeNovoReport:
    """De Novo 设计报告测试类"""

    @pytest.fixture
    def de_novo_task(self) -> ProteinDesignTask:
        """创建 de novo 设计任务"""
        return ProteinDesignTask(
            task_id="denovo_test_001",
            goal="de_novo_design",
            constraints={
                "goal_type": "de_novo_design",
                "length_range": [50, 100],
            },
            metadata={},
        )

    @pytest.fixture
    def de_novo_context(self, de_novo_task: ProteinDesignTask) -> WorkflowContext:
        """创建 de novo 设计的工作流上下文"""
        plan = Plan(
            task_id=de_novo_task.task_id,
            steps=[
                PlanStep(id="S1", tool="protein_mpnn", inputs={"goal": "de_novo_design"}),
                PlanStep(id="S2", tool="esmfold", inputs={"sequence": "S1.sequence"}),
            ],
            constraints=de_novo_task.constraints,
            metadata={},
        )
        return WorkflowContext(
            task=de_novo_task,
            plan=plan,
            step_results={},
            safety_events=[],
        )

    def test_is_de_novo_task_with_goal_type(self, de_novo_task: ProteinDesignTask):
        """测试通过 goal_type 识别 de novo 任务"""
        assert _is_de_novo_task(de_novo_task) is True

    def test_is_de_novo_task_with_goal_string(self):
        """测试通过 goal 字符串识别 de novo 任务"""
        task = ProteinDesignTask(
            task_id="test_001",
            goal="de_novo_design",
            constraints={},
            metadata={},
        )
        assert _is_de_novo_task(task) is True

    def test_is_de_novo_task_returns_false_for_other_tasks(self, sample_task: ProteinDesignTask):
        """测试非 de novo 任务返回 False"""
        assert _is_de_novo_task(sample_task) is False

    def test_generate_de_novo_report_success(
        self, de_novo_context: WorkflowContext, tmp_path: Path
    ):
        """测试成功场景的 de novo 报告生成"""
        context = de_novo_context

        # 添加序列设计步骤结果
        mpnn_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="success",
            inputs={"goal": "de_novo_design", "length_range": [50, 100]},
            outputs={
                "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR" * 2,
                "sequence_score": -2.5,
            },
            metrics={"exec_type": "python"},
            risk_flags=[],
            timestamp=now_iso(),
        )
        context.step_results["S1"] = mpnn_result

        # 添加结构预测步骤结果
        esmfold_result = StepResult(
            task_id=context.task.task_id,
            step_id="S2",
            tool="esmfold",
            status="success",
            inputs={"sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR" * 2},
            outputs={
                "pdb_path": "/path/to/structure.pdb",
                "metrics": {
                    "plddt_mean": 0.88,
                    "confidence": "high",
                },
            },
            metrics={"exec_type": "nextflow"},
            risk_flags=[],
            timestamp=now_iso(),
        )
        context.step_results["S2"] = esmfold_result

        report = generate_de_novo_report(context)

        # 验证基本信息
        assert report.task_id == "denovo_test_001"
        assert report.status == "success"
        assert report.design_goal == "de_novo_design"

        # 验证工具链
        assert report.tool_chain.sequence_design_tool == "protein_mpnn"
        assert report.tool_chain.structure_prediction_tool == "esmfold"

        # 验证步骤摘要
        assert len(report.step_summaries) == 2
        assert report.step_summaries[0].step_id == "S1"
        assert report.step_summaries[1].step_id == "S2"

        # 验证成功报告
        assert report.success_report is not None
        assert report.success_report.sequence_length == 70
        assert report.success_report.structure_pdb_path == "/path/to/structure.pdb"
        assert report.success_report.plddt_mean == 0.88
        assert report.success_report.confidence == "high"

        # 验证没有失败报告
        assert report.failure_report is None

    def test_generate_de_novo_report_failure(
        self, de_novo_context: WorkflowContext, tmp_path: Path
    ):
        """测试失败场景的 de novo 报告生成"""
        context = de_novo_context

        # 添加失败的步骤结果
        failed_result = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="failed",
            failure_type="tool_execution_error",
            error_message="CUDA out of memory",
            inputs={"goal": "de_novo_design"},
            outputs={},
            metrics={},
            risk_flags=[],
            timestamp=now_iso(),
        )
        context.step_results["S1"] = failed_result

        report = generate_de_novo_report(context)

        # 验证状态
        assert report.status == "failed"

        # 验证失败报告
        assert report.failure_report is not None
        assert report.failure_report.failed_step_id == "S1"
        assert report.failure_report.failed_tool == "protein_mpnn"
        assert report.failure_report.failure_type == "tool_execution_error"
        assert report.failure_report.error_message == "CUDA out of memory"
        assert len(report.failure_report.suggested_next_steps) > 0

    def test_generate_de_novo_report_with_safety_block(
        self, de_novo_context: WorkflowContext
    ):
        """测试安全阻断场景的 de novo 报告生成"""
        context = de_novo_context

        # 添加安全事件
        safety_event = SafetyResult(
            task_id=context.task.task_id,
            phase="input",
            scope="task",
            risk_flags=[
                RiskFlag(
                    level="block",
                    code="BIOSECURITY_RISK",
                    message="检测到潜在的生物安全风险序列",
                    scope="input",
                )
            ],
            action="block",
            timestamp=now_iso(),
        )
        context.safety_events.append(safety_event)

        report = generate_de_novo_report(context)

        # 验证状态
        assert report.status == "failed"

        # 验证失败报告包含安全信息
        assert report.failure_report is not None
        assert report.failure_report.safety_action == "block"
        assert "生物安全风险" in report.failure_report.safety_reason

    def test_write_de_novo_reports(
        self, de_novo_context: WorkflowContext, tmp_path: Path
    ):
        """测试写入 de novo 报告文件"""
        context = de_novo_context

        # 添加成功的步骤结果
        context.step_results["S1"] = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="success",
            outputs={"sequence": "MKFLKFSLLTAV"},
            metrics={},
            risk_flags=[],
            timestamp=now_iso(),
        )

        report = generate_de_novo_report(context)
        report_dir = tmp_path / "reports"

        json_path, md_path = write_de_novo_reports(report, report_dir)

        # 验证文件创建
        assert json_path.exists()
        assert md_path.exists()

        # 验证 JSON 内容
        json_content = json.loads(json_path.read_text())
        assert json_content["task_id"] == "denovo_test_001"
        assert json_content["status"] == "success"

        # 验证 Markdown 内容
        md_content = md_path.read_text()
        assert "# De Novo 蛋白设计报告" in md_content
        assert "denovo_test_001" in md_content
        assert "✅" in md_content  # 成功状态

    def test_render_de_novo_markdown_success(self, de_novo_context: WorkflowContext):
        """测试成功场景的 Markdown 渲染"""
        context = de_novo_context
        context.step_results["S1"] = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="success",
            outputs={"sequence": "MKFLKFSLLTAV"},
            metrics={},
            risk_flags=[],
            timestamp=now_iso(),
        )

        report = generate_de_novo_report(context)
        md_content = _render_de_novo_markdown(report)

        # 验证 Markdown 结构
        assert "## 任务概览" in md_content
        assert "## 工具链" in md_content
        assert "## 执行步骤" in md_content
        assert "## 设计结果" in md_content
        assert "✅ success" in md_content

    def test_render_de_novo_markdown_failure(self, de_novo_context: WorkflowContext):
        """测试失败场景的 Markdown 渲染"""
        context = de_novo_context
        context.step_results["S1"] = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="failed",
            failure_type="tool_execution_error",
            error_message="Connection timeout",
            outputs={},
            metrics={},
            risk_flags=[],
            timestamp=now_iso(),
        )

        report = generate_de_novo_report(context)
        md_content = _render_de_novo_markdown(report)

        # 验证 Markdown 结构
        assert "## 失败分析" in md_content
        assert "### 建议的下一步" in md_content
        assert "❌ failed" in md_content
        assert "Connection timeout" in md_content

    def test_summarizer_generates_de_novo_reports(
        self, de_novo_context: WorkflowContext, tmp_path: Path, monkeypatch
    ):
        """测试 SummarizerAgent 为 de novo 任务生成专用报告"""
        import src.agents.summarizer as summarizer_module

        context = de_novo_context

        # 添加步骤结果
        context.step_results["S1"] = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="success",
            outputs={"sequence": "MKFLKFSLLTAV" * 5},
            metrics={"exec_type": "python"},
            risk_flags=[],
            timestamp=now_iso(),
        )
        context.step_results["S2"] = StepResult(
            task_id=context.task.task_id,
            step_id="S2",
            tool="esmfold",
            status="success",
            outputs={
                "pdb_path": "/path/to/output.pdb",
                "metrics": {"plddt_mean": 0.85},
            },
            metrics={"exec_type": "nextflow"},
            risk_flags=[],
            timestamp=now_iso(),
        )

        # 使用临时目录
        report_dir = tmp_path / "nf" / "output" / "reports"
        monkeypatch.setattr(
            summarizer_module,
            "Path",
            lambda p: tmp_path / p if p == "output/reports" else Path(p),
        )

        summarizer = SummarizerAgent()
        result = summarizer.summarize(context)

        # 验证 de novo 报告路径在 metadata 中
        assert "de_novo_json_path" in result.metadata
        assert "de_novo_markdown_path" in result.metadata
        assert result.metadata["report_source"] == "de_novo_markdown"

        # 验证报告文件存在
        json_path = Path(result.metadata["de_novo_json_path"])
        md_path = Path(result.metadata["de_novo_markdown_path"])
        assert json_path.exists()
        assert md_path.exists()

    def test_de_novo_report_partial_success(self, de_novo_context: WorkflowContext):
        """测试部分成功场景（第一步成功，第二步失败）"""
        context = de_novo_context

        # S1 成功
        context.step_results["S1"] = StepResult(
            task_id=context.task.task_id,
            step_id="S1",
            tool="protein_mpnn",
            status="success",
            outputs={"sequence": "MKFLKFSLLTAV"},
            metrics={},
            risk_flags=[],
            timestamp=now_iso(),
        )

        # S2 失败
        context.step_results["S2"] = StepResult(
            task_id=context.task.task_id,
            step_id="S2",
            tool="esmfold",
            status="failed",
            failure_type="tool_execution_error",
            error_message="GPU unavailable",
            outputs={},
            metrics={},
            risk_flags=[],
            timestamp=now_iso(),
        )

        report = generate_de_novo_report(context)

        # 验证部分成功状态
        assert report.status == "partial"

        # 验证同时包含成功和失败信息
        assert report.success_report is not None
        assert report.success_report.final_sequence == "MKFLKFSLLTAV"
        assert report.failure_report is not None
        assert report.failure_report.failed_step_id == "S2"
