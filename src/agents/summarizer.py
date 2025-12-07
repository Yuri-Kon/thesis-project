from __future__ import annotations
from pathlib import Path

from src.models.contracts import WorkflowContext, DesignResult, now_iso

class SummarizerAgent:
    """最小可用 SummarizerAgent: 根据已完成的步骤，生成一个简单的 DesignResult"""

    def summarizer(self, context: WorkflowContext) -> DesignResult:
        task_id = context.task.task_id

        # 简单策略：从 step_results 中找到第一个包含 "sequence_length" 的结果

        seq_len = None
        for r in context.step_results.values():
            if "sequence_length" in r.outputs:
                seq_len = r.outputs["sequence_length"]
                break
        scores = {}
        if seq_len is not None:
            scores["sequence_length"] = seq_len
        
        report_dir = Path("nf/output/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{task_id}.json"

        design = DesignResult(
            task_id=task_id,
            sequence=context.task.constraints.get("sequence"),
            structure_pdb_path=None, # 当前阶段还没有真实结构
            risk_flags=[],
            report_path=str(report_path),
            metadata={
                "created_at": now_iso(),
                "step_ids": list(context.step_results.keys()),
            },
        )
        report_path.write_text(design.model_dump_json(indent=2))
        return design