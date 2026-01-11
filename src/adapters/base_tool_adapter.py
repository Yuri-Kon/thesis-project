from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext

__all__ = ["BaseToolAdapter"]


class BaseToolAdapter(ABC):
    """ToolAdapter 抽象基类，统一工具调用入口

    支持本地执行（run_local）和远程执行（run_remote）两种模式。
    具体的适配器可以选择实现其中一种或两种执行方式。
    """

    # 对应 ProteinToolKG 中的 tool.id
    tool_id: str
    # 可选适配器别名，用于注册表检索
    adapter_id: str | None = None

    @abstractmethod
    def resolve_inputs(
        self, step: PlanStep, context: WorkflowContext
    ) -> Dict[str, Any]:
        """将 PlanStep.inputs 解析为工具实际输入"""

    @abstractmethod
    def run_local(
        self, inputs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """本地执行工具并返回 (outputs, metrics)"""

    def run_remote(
        self,
        inputs: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """远程执行工具并返回 (outputs, metrics)

        可选方法，适配器可以选择实现远程执行能力。
        默认实现抛出 NotImplementedError。

        Args:
            inputs: 工具输入参数
            output_dir: 可选的输出目录，用于下载远程结果

        Returns:
            (outputs, metrics): 输出字典和指标字典
                outputs 应包含:
                    - 工具特定的输出字段
                    - artifacts: 可选的产物文件列表
                metrics 应包含:
                    - exec_type: "remote"
                    - duration_ms: 执行时间（毫秒）
                    - job_id: 可选的远程作业 ID

        Raises:
            NotImplementedError: 如果适配器不支持远程执行
            StepRunError: 远程执行失败
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support remote execution"
        )
