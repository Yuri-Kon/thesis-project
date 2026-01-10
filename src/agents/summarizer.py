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
        structure_pdb_path = None
        esmfold_scores = {}

        for r in context.step_results.values():
            # 提取序列长度
            if "sequence_length" in r.outputs:
                seq_len = r.outputs["sequence_length"]

            # 提取 ESMFold 结果
            if r.tool == "esmfold":
                # 提取 PDB 路径
                if "pdb_path" in r.outputs:
                    structure_pdb_path = r.outputs["pdb_path"]

                # 提取 pLDDT 和其他指标
                if "metrics" in r.outputs:
                    metrics = r.outputs["metrics"]
                    if "plddt_mean" in metrics:
                        esmfold_scores["plddt_mean"] = metrics["plddt_mean"]
                    if "confidence" in metrics:
                        esmfold_scores["confidence"] = metrics["confidence"]

        scores = {}
        if seq_len is not None:
            scores["sequence_length"] = seq_len
        # 合并 ESMFold 的分数
        scores.update(esmfold_scores)
        
        report_dir = Path("nf/output/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_report_path = report_dir / f"{task_id}.json"

        visualization_artifacts = _extract_visualization_artifacts(context)
        preferred_report_path, report_source = _select_report_path(
            visualization_artifacts,
            report_dir,
            task_id,
        )

        design = DesignResult(
            task_id=task_id,
            sequence=context.task.constraints.get("sequence"),
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
