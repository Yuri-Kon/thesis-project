"""
safety.py

本模块定义 SafetyAgent 的接口和实现，负责全程安全审查。

职责概述：
- 在任务输入阶段进行安全检查（task_input）
- 在步骤执行前进行安全检查（pre_step）
- 在步骤执行后进行安全检查（post_step）
- 在最终结果阶段进行安全检查（final_result）

A4 阶段：实现接口框架和伪实现，返回 SafetyResult 占位。
"""

from __future__ import annotations

from typing import Literal, Optional

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    DesignResult,
    SafetyResult,
    RiskFlag,
    now_iso,
)
from src.workflow.context import WorkflowContext
from src.workflow.failure_codes import extract_step_failure_code_or_default

__all__ = ["SafetyAgent"]


class SafetyAgent:
    """全程安全审查者，负责输入/过程/输出的风险识别与阻断

    在任务执行的不同阶段进行安全检查：
    - task_input: 检查任务输入（任务创建后，计划执行前）
    - pre_step: 检查步骤执行前的输入（每个步骤执行前）
    - post_step: 检查步骤执行后的输出（每个步骤执行后）
    - final_result: 检查最终结果（所有步骤执行完成后）

    A4 阶段实现：
    - 提供完整的接口定义
    - 实现伪实现，返回占位的 SafetyResult
    - 后续阶段将接入真实的安全检查规则和策略

    Attributes:
        无（A4 阶段暂不需要配置）
    """

    _AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
    _DEFAULT_PLDDT_THRESHOLD = 0.7

    def check_task_input(
        self, task: ProteinDesignTask, plan: Plan | None = None
    ) -> SafetyResult:
        """检查任务输入阶段的安全性

        在任务创建后、计划执行前进行安全检查，验证：
        - 任务目标是否合法
        - 约束条件是否合理
        - 是否存在明显的安全风险

        Args:
            task: 蛋白质设计任务
            plan: 可选，已生成的计划（如果已生成）

        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作

        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=task.task_id,
            phase="input",
            scope="task",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_pre_step(self, step: PlanStep, context: WorkflowContext) -> SafetyResult:
        """检查步骤执行前的安全性

        在每个步骤执行前进行安全检查，验证：
        - 步骤输入是否符合安全规范
        - 工具选择是否安全
        - 是否存在已知的安全风险

        Args:
            step: 即将执行的计划步骤
            context: 工作流上下文，包含任务信息、已完成步骤结果等

        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作

        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
            如果 action 为 "block"，调用方应该阻止步骤执行
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def check_post_step(
        self, step: PlanStep, step_result: StepResult, context: WorkflowContext
    ) -> SafetyResult:
        """检查步骤执行后的安全性

        在每个步骤执行后进行安全检查，验证：
        - 步骤输出是否符合安全规范
        - 是否存在风险序列或结构
        - 是否违反约束条件

        Args:
            step: 已执行的计划步骤
            step_result: 步骤执行结果
            context: 工作流上下文，包含任务信息、已完成步骤结果等

        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作

        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
            如果 action 为 "block"，调用方应该考虑触发重规划
        """
        risk_flags: list[RiskFlag] = []
        action = "allow"

        if step_result.status == "failed":
            risk_flags.append(
                self._build_failure_flag(
                    step,
                    step_result,
                    failure_code=extract_step_failure_code_or_default(
                        step_result,
                        default="STEP_EXECUTION_FAILED",
                    ),
                    failure_reason=(
                        step_result.error_message or "step execution failed"
                    ),
                )
            )
            action = "block"
        elif self._is_s3_quality_gate_step(step, step_result):
            pass_count, fail_count = self._extract_s3_counts(step_result)
            if pass_count <= 0:
                risk_flags.append(
                    self._build_failure_flag(
                        step,
                        step_result,
                        failure_code="S3_ALL_CANDIDATES_REJECTED",
                        failure_reason="S3 quality gate rejected all candidates",
                    )
                )
                action = "block"
            elif fail_count > 0:
                risk_flags.append(
                    self._build_failure_flag(
                        step,
                        step_result,
                        failure_code="S3_PARTIAL_QUALITY_GATE_FAIL",
                        failure_reason=(
                            f"S3 quality gate partially rejected candidates "
                            f"(pass={pass_count}, fail={fail_count})"
                        ),
                        level="warn",
                    )
                )
                action = "warn"
        elif step.tool == "protein_mpnn":
            sequence = step_result.outputs.get("sequence")
            if not self._is_valid_sequence(sequence):
                risk_flags.append(
                    self._build_failure_flag(
                        step,
                        step_result,
                        failure_code="PROTEIN_MPNN_INVALID_SEQUENCE",
                        failure_reason="ProteinMPNN did not produce a valid sequence",
                        extra_details={"sequence": sequence},
                    )
                )
                action = "block"
        elif step.tool == "esmfold":
            plddt = self._extract_plddt(step_result)
            if plddt is not None:
                threshold = self._resolve_plddt_threshold(context, plddt)
                if plddt < threshold:
                    risk_flags.append(
                        self._build_failure_flag(
                            step,
                            step_result,
                            failure_code="ESMFOLD_LOW_PLDDT",
                            failure_reason=(
                                f"ESMFold pLDDT below threshold: {plddt} < {threshold}"
                            ),
                            extra_details={
                                "plddt": plddt,
                                "threshold": threshold,
                            },
                        )
                    )
                    action = "block"

        return SafetyResult(
            task_id=context.task.task_id,
            phase="step",
            scope=f"step:{step.id}",
            risk_flags=risk_flags,
            action=action,
            timestamp=now_iso(),
        )

    def check_final_result(
        self, context: WorkflowContext, design_result: DesignResult | None = None
    ) -> SafetyResult:
        """检查最终结果的安全性

        在所有步骤执行完成后进行最终安全检查，验证：
        - 最终设计结果是否符合安全规范
        - 是否存在高风险序列或结构
        - 是否满足所有约束条件

        Args:
            context: 工作流上下文，包含任务信息、所有步骤结果等
            design_result: 可选，已生成的最终设计结果（如果已生成）

        Returns:
            SafetyResult: 安全检查结果，包含风险标记和建议操作

        Note:
            A4 阶段返回占位结果，action 为 "allow"，risk_flags 为空
            如果 action 为 "block"，调用方应该考虑触发重规划或拒绝结果
        """
        # A4: 伪实现，返回占位结果
        return SafetyResult(
            task_id=context.task.task_id,
            phase="output",
            scope="result",
            risk_flags=[],
            action="allow",
            timestamp=now_iso(),
        )

    def _is_valid_sequence(self, sequence: object) -> bool:
        if not isinstance(sequence, str) or not sequence:
            return False
        return all(residue in self._AMINO_ACIDS for residue in sequence)

    def _extract_plddt(self, step_result: StepResult) -> Optional[float]:
        outputs = step_result.outputs or {}
        if isinstance(outputs.get("plddt"), (int, float)):
            return float(outputs["plddt"])
        metrics = outputs.get("metrics")
        if isinstance(metrics, dict) and isinstance(
            metrics.get("plddt_mean"), (int, float)
        ):
            return float(metrics["plddt_mean"])
        return None

    def _resolve_plddt_threshold(
        self,
        context: WorkflowContext,
        plddt_value: float,
    ) -> float:
        raw = (
            context.task.constraints.get("plddt_threshold")
            or context.task.constraints.get("min_plddt")
            or self._DEFAULT_PLDDT_THRESHOLD
        )
        try:
            threshold = float(raw)
        except (TypeError, ValueError):
            threshold = self._DEFAULT_PLDDT_THRESHOLD
        if plddt_value > 1.0 and threshold <= 1.0:
            return threshold * 100
        return threshold

    def _is_s3_quality_gate_step(self, step: PlanStep, step_result: StepResult) -> bool:
        metadata = step.metadata if isinstance(step.metadata, dict) else {}
        if metadata.get("stage_id") == "S3":
            return True
        outputs = step_result.outputs if isinstance(step_result.outputs, dict) else {}
        return outputs.get("stage_id") == "S3"

    def _extract_s3_counts(self, step_result: StepResult) -> tuple[int, int]:
        outputs = step_result.outputs if isinstance(step_result.outputs, dict) else {}
        pass_count = outputs.get("pass_count")
        fail_count = outputs.get("fail_count")
        if isinstance(pass_count, bool) or not isinstance(pass_count, (int, float)):
            pass_count = 0
        if isinstance(fail_count, bool) or not isinstance(fail_count, (int, float)):
            failed_rows = outputs.get("failed_samples")
            if isinstance(failed_rows, list):
                fail_count = len(failed_rows)
            else:
                fail_count = 0
        return int(pass_count), int(fail_count)

    def _build_failure_flag(
        self,
        step: PlanStep,
        step_result: StepResult,
        *,
        failure_code: str,
        failure_reason: str,
        extra_details: Optional[dict] = None,
        level: Literal["warn", "block"] = "block",
    ) -> RiskFlag:
        details = {
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "failure_type": step_result.failure_type,
            "step_id": step.id,
            "tool": step.tool,
        }
        if extra_details:
            details.update(extra_details)
        return RiskFlag(
            level=level,
            code=failure_code,
            message=failure_reason,
            scope="step",
            step_id=step.id,
            details=details,
        )
