from __future__ import annotations
from pathlib import Path

from src.models.contracts import WorkflowContext, DesignResult, now_iso


class SummarizerAgent:
    """最小可用 SummarizerAgent: 根据已完成的步骤，生成一个简单的 DesignResult
    
    当前实现：简单汇总步骤结果，生成 JSON 报告
    后续将支持更丰富的报告格式（Markdown、HTML等）
    """

    def summarizer(self, context: WorkflowContext) -> DesignResult:
        """汇总工作流结果，生成最终设计结果
        
        Args:
            context: 工作流上下文
            
        Returns:
            DesignResult: 最终设计结果
        """
        task_id = context.task.task_id

        # 简单策略：从 step_results 中提取信息
        seq_len = None
        for r in context.step_results.values():
            if "sequence_length" in r.outputs:
                seq_len = r.outputs["sequence_length"]
                break
        
        scores = {}
        if seq_len is not None:
            scores["sequence_length"] = seq_len
        
        # 创建报告目录
        report_dir = Path("nf/output/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{task_id}.json"

        design = DesignResult(
            task_id=task_id,
            sequence=context.task.constraints.get("sequence"),
            structure_pdb_path=None,  # 当前阶段还没有真实结构
            scores=scores,
            risk_flags=[],
            report_path=str(report_path),
            metadata={
                "created_at": now_iso(),
                "step_ids": list(context.step_results.keys()),
            },
        )
        
        # 写入报告文件
        report_path.write_text(design.model_dump_json(indent=2))
        return design