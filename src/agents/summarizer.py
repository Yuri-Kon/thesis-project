from __future__ import annotations
from pathlib import Path
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.contracts import DesignResult, now_iso, StepResult, SafetyResult
from src.workflow.context import WorkflowContext


# ============================================================================
# De Novo 设计报告数据模型
# ============================================================================


class StepSummary(BaseModel):
    """单个步骤的执行摘要"""

    step_id: str
    tool: str
    status: str  # "success" | "failed" | "skipped"
    inputs_summary: Dict[str, Any] = Field(default_factory=dict)
    outputs_summary: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class ToolChainInfo(BaseModel):
    """工具链信息"""

    sequence_design_tool: Optional[str] = None
    structure_prediction_tool: Optional[str] = None
    description: str = ""


class SuccessReport(BaseModel):
    """成功场景报告内容"""

    final_sequence: Optional[str] = None
    sequence_length: Optional[int] = None
    structure_pdb_path: Optional[str] = None
    plddt_mean: Optional[float] = None
    confidence: Optional[str] = None


class FailureReport(BaseModel):
    """失败场景报告内容"""

    failed_step_id: Optional[str] = None
    failed_tool: Optional[str] = None
    failure_type: Optional[str] = None
    error_message: Optional[str] = None
    safety_action: Optional[str] = None  # "allow" | "warn" | "block"
    safety_reason: Optional[str] = None
    suggested_next_steps: List[str] = Field(default_factory=list)


class DeNovoReport(BaseModel):
    """De Novo 蛋白设计任务报告"""

    task_id: str
    task_description: str
    design_goal: str
    created_at: str
    status: str  # "success" | "failed" | "partial"

    tool_chain: ToolChainInfo
    step_summaries: List[StepSummary] = Field(default_factory=list)

    # 成功或失败的详细信息（二选一）
    success_report: Optional[SuccessReport] = None
    failure_report: Optional[FailureReport] = None

    # 原始数据引用
    report_json_path: Optional[str] = None
    report_markdown_path: Optional[str] = None


class SummarizerAgent:
    """最小可用 SummarizerAgent: 根据已完成的步骤，生成一个简单的 DesignResult

    当前实现：简单汇总步骤结果，生成 JSON 报告
    后续将支持更丰富的报告格式（Markdown、HTML等）
    """

    def summarize(self, context: WorkflowContext) -> DesignResult:
        """汇总工作流结果，生成最终设计结果

        Args:
            context: 工作流上下文

        Returns:
            DesignResult: 最终设计结果
        """
        task_id = context.task.task_id

        # 简单策略：从 step_results 中提取信息
        seq_len = None
        final_sequence = None
        structure_pdb_path = None
        structure_scores = {}  # 与结构相关的评分指标
        execution_steps: list[dict] = []

        if context.plan is not None:
            ordered_step_ids = [step.id for step in context.plan.steps]
        else:
            ordered_step_ids = list(context.step_results.keys())

        for step_id in ordered_step_ids:
            r = context.step_results.get(step_id)
            if r is None:
                continue
            # 提取序列长度
            if "sequence_length" in r.outputs:
                seq_len = r.outputs["sequence_length"]
            if "sequence" in r.outputs:
                final_sequence = r.outputs["sequence"]

            # 提取结构预测结果（通用方式，不限于特定工具）
            # 只要 outputs 包含 pdb_path，就认为是结构预测工具的输出
            if "pdb_path" in r.outputs:
                # 更新 PDB 路径
                structure_pdb_path = r.outputs["pdb_path"]

                # 重要：清空旧的结构评分，确保指标与当前 PDB 路径一致
                # 这样避免了将新结构与旧指标错误配对的问题
                structure_scores = {}

                # 提取该步骤的结构预测指标
                if "metrics" in r.outputs:
                    metrics = r.outputs["metrics"]
                    # 提取 pLDDT（结构预测置信度的标准指标）
                    if "plddt_mean" in metrics:
                        structure_scores["plddt_mean"] = metrics["plddt_mean"]
                    # 提取置信度等级（如果有）
                    if "confidence" in metrics:
                        structure_scores["confidence"] = metrics["confidence"]

            execution_steps.append(
                {
                    "step_id": r.step_id,
                    "tool": r.tool,
                    "exec_type": r.metrics.get("exec_type"),
                    "provider": r.metrics.get("provider"),
                    "model_id": r.metrics.get("model_id"),
                    "backend": r.metrics.get("backend"),
                }
            )

        scores = {}
        if seq_len is None and final_sequence is not None:
            seq_len = len(final_sequence)
        if seq_len is not None:
            scores["sequence_length"] = seq_len
        # 合并结构预测的分数
        scores.update(structure_scores)

        report_dir = Path("output/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_report_path = report_dir / f"{task_id}.json"

        visualization_artifacts = _extract_visualization_artifacts(context)
        preferred_report_path, report_source = _select_report_path(
            visualization_artifacts,
            report_dir,
            task_id,
        )

        if final_sequence is None:
            final_sequence = context.task.constraints.get("sequence")

        plan_metadata = context.plan.metadata if context.plan else {}
        plan_version = plan_metadata.get("plan_version") or plan_metadata.get("version")

        # De novo 任务：生成专用报告
        de_novo_report_paths = {}
        if _is_de_novo_task(context.task):
            de_novo_report = generate_de_novo_report(context)
            json_path, md_path = write_de_novo_reports(de_novo_report, report_dir)
            de_novo_report_paths = {
                "de_novo_json_path": str(json_path),
                "de_novo_markdown_path": str(md_path),
            }
            # 对于 de novo 任务，优先使用 Markdown 报告
            preferred_report_path = md_path
            report_source = "de_novo_markdown"

        design = DesignResult(
            task_id=task_id,
            sequence=final_sequence,
            structure_pdb_path=structure_pdb_path,  # ESMFold 生成的 PDB 文件
            scores=scores,
            risk_flags=[],
            report_path=str(preferred_report_path),
            metadata={
                "created_at": now_iso(),
                "step_ids": list(context.step_results.keys()),
                "artifacts": visualization_artifacts,
                "summary_report_path": str(summary_report_path),
                "report_source": report_source,
                "plan_metadata": plan_metadata,
                "plan_version": plan_version,
                "execution_steps": execution_steps,
                **de_novo_report_paths,
            },
        )

        summary_report_path.write_text(design.model_dump_json(indent=2))
        return design


def _extract_visualization_artifacts(context: WorkflowContext) -> dict:
    for result in context.step_results.values():
        outputs = result.outputs or {}
        if any(
            key in outputs
            for key in (
                "report_html_path",
                "plotly_html_path",
                "metrics_json_path",
                "assets_dir",
            )
        ):
            return {
                key: outputs.get(key)
                for key in (
                    "metrics_json_path",
                    "plotly_html_path",
                    "report_html_path",
                    "assets_dir",
                    "summary_stats",
                )
                if outputs.get(key) is not None
            }
    return {}


def _select_report_path(
    artifacts: dict,
    report_dir: Path,
    task_id: str,
) -> tuple[Path, str]:
    report_html_path = artifacts.get("report_html_path")
    if report_html_path:
        return Path(report_html_path), "visualization_tool"

    plotly_html_path = artifacts.get("plotly_html_path")
    metrics_json_path = artifacts.get("metrics_json_path")
    if plotly_html_path or metrics_json_path:
        fallback_path = report_dir / f"{task_id}.html"
        _write_fallback_report(
            fallback_path,
            plotly_html_path,
            metrics_json_path,
        )
        return fallback_path, "visualization_fallback"

    return report_dir / f"{task_id}.json", "summary_json"


def _write_fallback_report(
    report_path: Path,
    plotly_html_path: str | None,
    metrics_json_path: str | None,
) -> None:
    plotly_snippet = ""
    if plotly_html_path:
        plotly_snippet = Path(plotly_html_path).read_text(encoding="utf-8")

    metrics_table = _build_metrics_table(metrics_json_path)
    report_html = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8" />',
            '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
            "  <title>Visualization Report</title>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 0; background: #f6f7fb; color: #1d1f27; }",
            "    main { max-width: 1080px; margin: 0 auto; padding: 32px 20px 48px; }",
            "    section { background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08); }",
            "    table { border-collapse: collapse; width: 100%; }",
            "    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #e5e7eb; }",
            "    th { color: #374151; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <main>",
            "    <section>",
            "      <h2>B-factor Trend</h2>",
            plotly_snippet or "<p>No Plotly output available.</p>",
            "    </section>",
            "    <section>",
            "      <h2>Metrics</h2>",
            metrics_table,
            "    </section>",
            "  </main>",
            "</body>",
            "</html>",
        ]
    )
    report_path.write_text(report_html, encoding="utf-8")


def _build_metrics_table(metrics_json_path: str | None) -> str:
    if not metrics_json_path:
        return "<p>No metrics file available.</p>"
    try:
        metrics = json.loads(Path(metrics_json_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "<p>Failed to load metrics.</p>"

    chain_ids = metrics.get("chain_ids", [])
    residue_count = metrics.get("residue_count", "N/A")
    chain_label = ", ".join(chain_ids) if chain_ids else "N/A"
    return "\n".join(
        [
            "<table>",
            "  <tr><th>Residues</th><td>{}</td></tr>".format(residue_count),
            "  <tr><th>Chains</th><td>{}</td></tr>".format(chain_label),
            f'  <tr><th>Metrics JSON</th><td><a href="{metrics_json_path}">{metrics_json_path}</a></td></tr>',
            "</table>",
        ]
    )


# ============================================================================
# De Novo 设计报告生成逻辑
# ============================================================================

_DE_NOVO_GOAL_TYPE = "de_novo_design"


def _extract_goal_type(task) -> str:
    """从任务中提取 goal_type（与 planner.py 逻辑保持一致）"""
    for container in (task.constraints, task.metadata):
        if isinstance(container, dict):
            goal_block = container.get("goal")
            if isinstance(goal_block, dict):
                goal_type = goal_block.get("type")
                if isinstance(goal_type, str) and goal_type:
                    return goal_type
            goal_type = container.get("goal_type")
            if isinstance(goal_type, str) and goal_type:
                return goal_type

    goal_value = task.goal
    if isinstance(goal_value, str):
        stripped = goal_value.strip()
        if stripped == _DE_NOVO_GOAL_TYPE:
            return stripped
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return ""
            if isinstance(parsed, dict):
                goal_type = parsed.get("type")
                if isinstance(goal_type, str) and goal_type:
                    return goal_type
    return ""


def _is_de_novo_task(task) -> bool:
    """判断任务是否为 de novo 设计任务"""
    return _extract_goal_type(task) == _DE_NOVO_GOAL_TYPE


def _build_step_summary(step_result: StepResult) -> StepSummary:
    """从 StepResult 构建步骤摘要"""
    # 提取关键输入（过滤掉过长的内容）
    inputs_summary = {}
    for key, value in step_result.inputs.items():
        if isinstance(value, str) and len(value) > 100:
            inputs_summary[key] = f"{value[:50]}... ({len(value)} chars)"
        else:
            inputs_summary[key] = value

    # 提取关键输出
    outputs_summary = {}
    for key, value in step_result.outputs.items():
        if key == "sequence" and isinstance(value, str):
            # 序列截断显示
            if len(value) > 50:
                outputs_summary[key] = f"{value[:20]}...{value[-20:]} ({len(value)} aa)"
            else:
                outputs_summary[key] = value
        elif key == "metrics" and isinstance(value, dict):
            # 提取关键指标
            outputs_summary[key] = {
                k: v
                for k, v in value.items()
                if k in ("plddt_mean", "confidence", "task_id", "tool")
            }
        elif key == "pdb_path":
            outputs_summary[key] = value
        elif isinstance(value, (str, int, float, bool)):
            outputs_summary[key] = value

    return StepSummary(
        step_id=step_result.step_id,
        tool=step_result.tool,
        status=step_result.status,
        inputs_summary=inputs_summary,
        outputs_summary=outputs_summary,
        error_message=step_result.error_message,
    )


def _build_tool_chain_info(context: WorkflowContext) -> ToolChainInfo:
    """从上下文构建工具链信息"""
    sequence_tool = None
    structure_tool = None

    for step_result in context.step_results.values():
        tool = step_result.tool.lower()
        # 识别序列设计工具
        if any(
            kw in tool for kw in ("mpnn", "proteinmpnn", "sequence_design", "esm_if")
        ):
            sequence_tool = step_result.tool
        # 识别结构预测工具
        elif any(kw in tool for kw in ("esmfold", "alphafold", "structure", "fold")):
            structure_tool = step_result.tool

    # 如果没有识别出来，尝试按步骤顺序推断
    if context.plan and len(context.plan.steps) >= 2:
        if sequence_tool is None:
            sequence_tool = context.plan.steps[0].tool
        if structure_tool is None:
            structure_tool = context.plan.steps[1].tool

    description = ""
    if sequence_tool and structure_tool:
        description = f"序列设计({sequence_tool}) → 结构预测({structure_tool})"
    elif sequence_tool:
        description = f"序列设计({sequence_tool})"
    elif structure_tool:
        description = f"结构预测({structure_tool})"

    return ToolChainInfo(
        sequence_design_tool=sequence_tool,
        structure_prediction_tool=structure_tool,
        description=description,
    )


def _build_success_report(context: WorkflowContext) -> SuccessReport:
    """构建成功场景报告"""
    final_sequence = None
    sequence_length = None
    structure_pdb_path = None
    plddt_mean = None
    confidence = None

    for step_result in context.step_results.values():
        outputs = step_result.outputs or {}

        # 提取序列
        if "sequence" in outputs:
            final_sequence = outputs["sequence"]
            sequence_length = len(final_sequence)

        # 提取结构预测结果
        if "pdb_path" in outputs:
            structure_pdb_path = outputs["pdb_path"]
            # 提取该步骤的指标
            metrics = outputs.get("metrics", {})
            if "plddt_mean" in metrics:
                plddt_mean = metrics["plddt_mean"]
            if "confidence" in metrics:
                confidence = metrics["confidence"]

    return SuccessReport(
        final_sequence=final_sequence,
        sequence_length=sequence_length,
        structure_pdb_path=structure_pdb_path,
        plddt_mean=plddt_mean,
        confidence=confidence,
    )


def _build_failure_report(context: WorkflowContext) -> FailureReport:
    """构建失败场景报告"""
    failed_step_id = None
    failed_tool = None
    failure_type = None
    error_message = None
    safety_action = None
    safety_reason = None
    suggested_next_steps = []

    # 查找失败的步骤
    for step_result in context.step_results.values():
        if step_result.status == "failed":
            failed_step_id = step_result.step_id
            failed_tool = step_result.tool
            failure_type = step_result.failure_type
            error_message = step_result.error_message
            break

    # 从安全事件中提取信息
    for safety_event in context.safety_events:
        if safety_event.action in ("warn", "block"):
            safety_action = safety_event.action
            # 提取安全风险原因
            for flag in safety_event.risk_flags:
                if flag.level in ("warn", "block"):
                    safety_reason = flag.message
                    break
            break

    # 生成建议的下一步
    if failure_type == "tool_execution_error":
        suggested_next_steps.append("检查工具配置和依赖环境")
        suggested_next_steps.append("尝试使用备用工具执行")
    elif failure_type == "validation_error":
        suggested_next_steps.append("检查输入参数是否符合约束")
        suggested_next_steps.append("调整设计目标或约束条件")
    elif safety_action == "block":
        suggested_next_steps.append("审查安全策略并调整输入")
        suggested_next_steps.append("联系管理员解除安全限制")
    else:
        suggested_next_steps.append("查看详细日志分析失败原因")
        suggested_next_steps.append("考虑使用 replan 功能重新规划")

    return FailureReport(
        failed_step_id=failed_step_id,
        failed_tool=failed_tool,
        failure_type=failure_type,
        error_message=error_message,
        safety_action=safety_action,
        safety_reason=safety_reason,
        suggested_next_steps=suggested_next_steps,
    )


def _determine_task_status(context: WorkflowContext) -> str:
    """判断任务最终状态"""
    has_failed = False
    has_success = False

    for step_result in context.step_results.values():
        if step_result.status == "failed":
            has_failed = True
        elif step_result.status == "success":
            has_success = True

    # 检查安全事件是否导致阻断
    for safety_event in context.safety_events:
        if safety_event.action == "block":
            return "failed"

    if has_failed:
        return "failed" if not has_success else "partial"
    return "success"


def generate_de_novo_report(context: WorkflowContext) -> DeNovoReport:
    """生成 de novo 设计任务的结构化报告"""
    task = context.task
    status = _determine_task_status(context)

    # 构建步骤摘要
    step_summaries = []
    if context.plan:
        for plan_step in context.plan.steps:
            step_result = context.step_results.get(plan_step.id)
            if step_result:
                step_summaries.append(_build_step_summary(step_result))
    else:
        for step_result in context.step_results.values():
            step_summaries.append(_build_step_summary(step_result))

    # 根据状态构建成功或失败报告
    success_report = None
    failure_report = None
    if status == "success":
        success_report = _build_success_report(context)
    else:
        failure_report = _build_failure_report(context)
        # 部分成功时也包含成功部分
        if status == "partial":
            success_report = _build_success_report(context)

    return DeNovoReport(
        task_id=task.task_id,
        task_description=task.goal,
        design_goal=_extract_goal_type(task) or "de_novo_design",
        created_at=now_iso(),
        status=status,
        tool_chain=_build_tool_chain_info(context),
        step_summaries=step_summaries,
        success_report=success_report,
        failure_report=failure_report,
    )


def _render_de_novo_markdown(report: DeNovoReport) -> str:
    """将 DeNovoReport 渲染为 Markdown 格式"""
    lines = []

    # 标题
    lines.append(f"# De Novo 蛋白设计报告")
    lines.append("")

    # 任务概览
    lines.append("## 任务概览")
    lines.append("")
    lines.append(f"- **任务 ID**: `{report.task_id}`")
    lines.append(f"- **设计目标**: {report.task_description}")
    lines.append(f"- **任务类型**: {report.design_goal}")
    lines.append(f"- **生成时间**: {report.created_at}")
    status_emoji = {"success": "✅", "failed": "❌", "partial": "⚠️"}.get(
        report.status, "❓"
    )
    lines.append(f"- **执行状态**: {status_emoji} {report.status}")
    lines.append("")

    # 工具链
    lines.append("## 工具链")
    lines.append("")
    if report.tool_chain.description:
        lines.append(f"**执行链路**: {report.tool_chain.description}")
    else:
        lines.append("未识别到标准工具链")
    lines.append("")

    # 执行步骤
    lines.append("## 执行步骤")
    lines.append("")
    for step in report.step_summaries:
        step_emoji = {"success": "✅", "failed": "❌", "skipped": "⚠️"}.get(
            step.status, "❓"
        )
        lines.append(f"### {step.step_id}: {step.tool} {step_emoji}")
        lines.append("")

        if step.inputs_summary:
            lines.append("**输入**:")
            for key, value in step.inputs_summary.items():
                lines.append(f"- `{key}`: {value}")
            lines.append("")

        if step.outputs_summary:
            lines.append("**输出**:")
            for key, value in step.outputs_summary.items():
                if isinstance(value, dict):
                    lines.append(f"- `{key}`:")
                    for k, v in value.items():
                        lines.append(f"  - `{k}`: {v}")
                else:
                    lines.append(f"- `{key}`: {value}")
            lines.append("")

        if step.error_message:
            lines.append(f"**错误**: {step.error_message}")
            lines.append("")

    # 结果
    if report.success_report:
        lines.append("## 设计结果")
        lines.append("")
        sr = report.success_report
        if sr.final_sequence:
            seq_display = sr.final_sequence
            if len(seq_display) > 60:
                seq_display = f"{seq_display[:30]}...{seq_display[-30:]}"
            lines.append(f"- **设计序列**: `{seq_display}`")
        if sr.sequence_length:
            lines.append(f"- **序列长度**: {sr.sequence_length} aa")
        if sr.structure_pdb_path:
            lines.append(f"- **结构文件**: `{sr.structure_pdb_path}`")
        if sr.plddt_mean is not None:
            lines.append(f"- **pLDDT 均值**: {sr.plddt_mean:.2f}")
        if sr.confidence:
            lines.append(f"- **置信度等级**: {sr.confidence}")
        lines.append("")

    if report.failure_report:
        lines.append("## 失败分析")
        lines.append("")
        fr = report.failure_report
        if fr.failed_step_id:
            lines.append(f"- **失败步骤**: {fr.failed_step_id}")
        if fr.failed_tool:
            lines.append(f"- **失败工具**: {fr.failed_tool}")
        if fr.failure_type:
            lines.append(f"- **失败类型**: {fr.failure_type}")
        if fr.error_message:
            lines.append(f"- **错误信息**: {fr.error_message}")
        if fr.safety_action:
            lines.append(f"- **安全判定**: {fr.safety_action}")
        if fr.safety_reason:
            lines.append(f"- **安全原因**: {fr.safety_reason}")
        lines.append("")

        if fr.suggested_next_steps:
            lines.append("### 建议的下一步")
            lines.append("")
            for i, step in enumerate(fr.suggested_next_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

    # 页脚
    lines.append("---")
    lines.append("*此报告由 SummarizerAgent 自动生成*")

    return "\n".join(lines)


def write_de_novo_reports(
    report: DeNovoReport,
    report_dir: Path,
) -> tuple[Path, Path]:
    """写入 de novo 报告文件（JSON 和 Markdown）

    Returns:
        (json_path, markdown_path): 两个报告文件的路径
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / f"{report.task_id}_denovo.json"
    md_path = report_dir / f"{report.task_id}_denovo.md"

    # 写入 JSON
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    # 写入 Markdown
    md_content = _render_de_novo_markdown(report)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
