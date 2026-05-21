from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class ToolChainReport(Protocol):
    description: str


class StepSummaryReport(Protocol):
    step_id: str
    tool: str
    status: str
    inputs_summary: Mapping[str, object]
    outputs_summary: Mapping[str, object]
    error_message: str | None


class SuccessReportView(Protocol):
    final_sequence: str | None
    sequence_length: int | None
    structure_pdb_path: str | None
    plddt_mean: float | None
    confidence: str | None
    objective_score: float | None
    objective_top_k: Sequence[Mapping[str, object]]
    objective_warnings: Sequence[str]
    posterior_score: Mapping[str, object]
    rank_reason: str | None


class FailureReportView(Protocol):
    failed_step_id: str | None
    failed_tool: str | None
    failure_type: str | None
    error_message: str | None
    safety_action: str | None
    safety_reason: str | None
    suggested_next_steps: Sequence[str]


class DeNovoReportView(Protocol):
    task_id: str
    task_description: str
    design_goal: str
    created_at: str
    status: str
    tool_chain: ToolChainReport
    step_summaries: Sequence[StepSummaryReport]
    success_report: SuccessReportView | None
    failure_report: FailureReportView | None


def render_de_novo_markdown(report: DeNovoReportView) -> str:
    """将 DeNovoReport 渲染为 Markdown 格式。"""

    lines: list[str] = []
    _extend_title(lines)
    _extend_task_overview(lines, report)
    _extend_tool_chain(lines, report.tool_chain)
    _extend_step_summaries(lines, report.step_summaries)
    if report.success_report:
        _extend_success_report(lines, report.success_report)
    if report.failure_report:
        _extend_failure_report(lines, report.failure_report)
    _extend_footer(lines)
    return "\n".join(lines)


def _extend_title(lines: list[str]) -> None:
    lines.append("# De Novo 蛋白设计报告")
    lines.append("")


def _extend_task_overview(lines: list[str], report: DeNovoReportView) -> None:
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


def _extend_tool_chain(lines: list[str], tool_chain: ToolChainReport) -> None:
    lines.append("## 工具链")
    lines.append("")
    if tool_chain.description:
        lines.append(f"**执行链路**: {tool_chain.description}")
    else:
        lines.append("未识别到标准工具链")
    lines.append("")


def _extend_step_summaries(
    lines: list[str],
    step_summaries: Sequence[StepSummaryReport],
) -> None:
    lines.append("## 执行步骤")
    lines.append("")
    for step in step_summaries:
        _extend_single_step(lines, step)


def _extend_single_step(lines: list[str], step: StepSummaryReport) -> None:
    step_emoji = {"success": "✅", "failed": "❌", "skipped": "⚠️"}.get(
        step.status, "❓"
    )
    lines.append(f"### {step.step_id}: {step.tool} {step_emoji}")
    lines.append("")
    if step.inputs_summary:
        _extend_mapping_section(lines, title="**输入**:", payload=step.inputs_summary)
    if step.outputs_summary:
        _extend_mapping_section(lines, title="**输出**:", payload=step.outputs_summary)
    if step.error_message:
        lines.append(f"**错误**: {step.error_message}")
        lines.append("")


def _extend_mapping_section(
    lines: list[str],
    *,
    title: str,
    payload: Mapping[str, object],
) -> None:
    lines.append(title)
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"- `{key}`:")
            for child_key, child_value in value.items():
                lines.append(f"  - `{child_key}`: {child_value}")
        else:
            lines.append(f"- `{key}`: {value}")
    lines.append("")


def _extend_success_report(lines: list[str], report: SuccessReportView) -> None:
    lines.append("## 设计结果")
    lines.append("")
    if report.final_sequence:
        lines.append(f"- **设计序列**: `{_compact_sequence(report.final_sequence)}`")
    if report.sequence_length:
        lines.append(f"- **序列长度**: {report.sequence_length} aa")
    if report.structure_pdb_path:
        lines.append(f"- **结构文件**: `{report.structure_pdb_path}`")
    if report.plddt_mean is not None:
        lines.append(f"- **pLDDT 均值**: {report.plddt_mean:.2f}")
    if report.confidence:
        lines.append(f"- **置信度等级**: {report.confidence}")
    lines.append("")
    if report.objective_score is not None or report.objective_top_k:
        _extend_objective_scoring(lines, report)


def _compact_sequence(sequence: str) -> str:
    if len(sequence) <= 60:
        return sequence
    return f"{sequence[:30]}...{sequence[-30:]}"


def _extend_objective_scoring(lines: list[str], report: SuccessReportView) -> None:
    lines.append("### 目标评分")
    lines.append("")
    if report.objective_score is not None:
        lines.append(f"- **综合目标分**: {report.objective_score:.3f}")
    if report.posterior_score:
        evidence_status = report.posterior_score.get("evidence_status") or "-"
        evidence_sufficiency = report.posterior_score.get("evidence_sufficiency")
        if isinstance(evidence_sufficiency, (int, float)):
            lines.append(
                f"- **证据充分度**: {evidence_sufficiency:.3f} ({evidence_status})"
            )
    if report.rank_reason:
        lines.append(f"- **排序理由**: {report.rank_reason}")
    if report.objective_warnings:
        lines.append(f"- **评分警告**: {'; '.join(report.objective_warnings)}")
    if report.objective_top_k:
        _extend_objective_top_k(lines, report.objective_top_k)
    lines.append("")


def _extend_objective_top_k(
    lines: list[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    lines.append("")
    lines.append("| Rank | Candidate | Score | Reason |")
    lines.append("| --- | --- | ---: | --- |")
    for row in rows:
        rank = row.get("top_k_rank") or row.get("rank") or "-"
        candidate_id = row.get("candidate_id") or row.get("id") or "-"
        score = row.get("objective_score")
        score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
        reason = row.get("rank_reason") or row.get("objective_explanation") or "-"
        lines.append(f"| {rank} | `{candidate_id}` | {score_text} | {reason} |")


def _extend_failure_report(lines: list[str], report: FailureReportView) -> None:
    lines.append("## 失败分析")
    lines.append("")
    if report.failed_step_id:
        lines.append(f"- **失败步骤**: {report.failed_step_id}")
    if report.failed_tool:
        lines.append(f"- **失败工具**: {report.failed_tool}")
    if report.failure_type:
        lines.append(f"- **失败类型**: {report.failure_type}")
    if report.error_message:
        lines.append(f"- **错误信息**: {report.error_message}")
    if report.safety_action:
        lines.append(f"- **安全判定**: {report.safety_action}")
    if report.safety_reason:
        lines.append(f"- **安全原因**: {report.safety_reason}")
    lines.append("")
    if report.suggested_next_steps:
        _extend_suggested_next_steps(lines, report.suggested_next_steps)


def _extend_suggested_next_steps(lines: list[str], steps: Sequence[str]) -> None:
    lines.append("### 建议的下一步")
    lines.append("")
    for index, step in enumerate(steps, 1):
        lines.append(f"{index}. {step}")
    lines.append("")


def _extend_footer(lines: list[str]) -> None:
    lines.append("---")
    lines.append("*此报告由 SummarizerAgent 自动生成*")
