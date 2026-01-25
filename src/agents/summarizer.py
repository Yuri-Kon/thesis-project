from __future__ import annotations
from pathlib import Path
import json

from src.models.contracts import DesignResult, now_iso
from src.workflow.context import WorkflowContext


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
        
        report_dir = Path("nf/output/reports")
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
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
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
            f"  <tr><th>Metrics JSON</th><td><a href=\"{metrics_json_path}\">{metrics_json_path}</a></td></tr>",
            "</table>",
        ]
    )
