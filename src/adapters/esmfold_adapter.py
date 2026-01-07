"""
ESMFoldAdapter - ESMFold 结构预测工具适配器

通过 WorkflowEngineAdapter 调用 Nextflow 执行 ESMFold 预测。

设计规格（见 SID:tools.esmfold.spec）：
- 输入：单条氨基酸序列
- 输出：PDB 文件、置信度(pLDDT)
- 执行方式：nextflow（blocking）
- 模块位置：nf/modules/esmfold.nf
- 产物目录：output/pdb/, output/metrics/, output/artifacts/
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.engines.nextflow_adapter import WorkflowEngineAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext

__all__ = ["ESMFoldAdapter"]


class ESMFoldAdapter(BaseToolAdapter):
    """ESMFold 结构预测工具适配器

    使用 Nextflow 作为执行后端，通过 WorkflowEngineAdapter 调用。
    """

    tool_id = "esmfold"
    adapter_id = "esmfold"

    def __init__(
        self,
        *,
        module_path: str | Path | None = None,
        nextflow_profile: str = "test",
    ) -> None:
        """初始化 ESMFoldAdapter

        Args:
            module_path: Nextflow 模块路径，默认为 "nf/modules/esmfold.nf"
            nextflow_profile: Nextflow profile，默认为 "test"
        """
        self.module_path = Path(module_path or "nf/modules/esmfold.nf")
        self.engine = WorkflowEngineAdapter(profile=nextflow_profile)

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """解析输入参数

        支持字面量和引用语义（如 "S1.sequence"）。

        Args:
            step: 计划步骤
            context: 工作流上下文

        Returns:
            解析后的输入字典

        Raises:
            ValueError: 输入引用无法解析
        """
        resolved: Dict[str, Any] = {}

        for key, val in step.inputs.items():
            # 支持引用语义：StepID.field
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
                    # 引用前一步骤的输出
                    if not context.has_step_result(step_id):
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': step '{step_id}' not found in context"
                        )
                    try:
                        resolved_value = context.get_step_output(step_id, field)
                    except KeyError as exc:
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                        ) from exc
                    resolved[key] = resolved_value
                    continue

            # 字面量值
            resolved[key] = val

        # 验证必需的输入
        if "sequence" not in resolved:
            raise ValueError(
                f"Missing required input 'sequence' for ESMFold step '{step.id}'"
            )

        # 添加上下文信息（供 run_local 使用）
        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id

        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """执行 ESMFold 预测

        通过 WorkflowEngineAdapter 调用 Nextflow 模块。

        Args:
            inputs: 输入参数，必须包含 "sequence"

        Returns:
            (outputs, metrics): 输出字典和指标字典
                outputs 包含:
                    - pdb_path: PDB 文件路径
                    - metrics: 预测指标（pLDDT 等）
                metrics 包含:
                    - exec_type: "nextflow"
                    - duration_ms: 执行时间（毫秒）

        Raises:
            StepRunError: 执行失败
        """
        # 验证输入
        sequence = inputs.get("sequence")
        if not sequence:
            from src.workflow.errors import FailureType, StepRunError

            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Missing required input 'sequence'",
                code="ESMFOLD_MISSING_SEQUENCE",
            )

        # 获取上下文信息（如果有）
        task_id = inputs.get("task_id", "unknown")
        step_id = inputs.get("step_id", "unknown")

        # 准备 Nextflow 输入
        nf_inputs = {
            "sequence": sequence,
        }

        # 通过 WorkflowEngineAdapter 执行
        outputs, metrics = self.engine.execute(
            module_path=self.module_path,
            inputs=nf_inputs,
            task_id=task_id,
            step_id=step_id,
            tool_name=self.tool_id,
        )

        return outputs, metrics
