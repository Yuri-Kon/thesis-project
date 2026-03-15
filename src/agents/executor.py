from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from src.kg.kg_client import ToolKGError, load_tool_kg
from src.models.contracts import DesignResult, Plan, PlanStep, StepResult
from src.models.db import (
    InternalStatus,
    TaskRecord,
    TERMINAL_INTERNAL_STATUSES,
    derive_task_status,
    to_external_status,
)
from src.agents.summarizer import SummarizerAgent
from src.storage.log_store import append_event
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType
from src.workflow.quality_gate import (
    QUALITY_GATE_ALL_REJECTED_CODE,
    evaluate_quality_gate_batch,
)
from src.workflow.recovery import (
    StructureRefinementIteration,
    build_structure_refinement_audit,
    persist_structure_refinement_audit,
)
from src.workflow.step_runner import StepRunner
from src.workflow.plan_runner import PlanRunner
from src.workflow.status import transition_task_status

_S4_DEFAULT_MAX_ITERATIONS = 3
_S4_DEFAULT_CONVERGENCE_DELTA = 0.01
_S4_DEFAULT_MAX_DEGRADATION_ROUNDS = 1


class ExecutorAgent:
    """计划执行者与调度器，负责执行 Plan 并调用工具适配器

    当前实现：
    - 使用 StepRunner 执行单个步骤，支持输入解析（包括引用语义）
    - 使用 PlanRunner 执行完整计划，包含安全检查、状态管理等功能
    - 通过 AdapterRegistry 调用工具（ESMFold、ProteinMPNN等）
    """

    def __init__(self, plan_runner: PlanRunner | None = None):
        """初始化 ExecutorAgent

        Args:
            plan_runner: 可选的 PlanRunner 实例。如果为 None，则创建默认实例。
        """
        self.step_runner = StepRunner()
        # 使用 PlanRunner 来执行完整计划，它包含安全检查、状态管理等功能
        self.plan_runner = plan_runner or PlanRunner(step_runner=self.step_runner)

    def run_step(self, step_id: str, context: WorkflowContext) -> StepResult:
        """执行单个步骤

        使用 StepRunner 来执行步骤，支持输入解析（包括引用语义），并通过适配器调用工具。

        Args:
            step_id: 步骤ID
            context: 工作流上下文

        Returns:
            StepResult: 步骤执行结果

        Raises:
            AssertionError: 当 context.plan 为 None 时
            StopIteration: 当 step_id 不存在时
            ValueError: 当输入引用无法解析时
        """
        assert context.plan is not None, "Plan must be set in context"
        step = next(s for s in context.plan.steps if s.id == step_id)

        # 使用 StepRunner 执行步骤，它会处理输入解析和执行逻辑
        result = self.step_runner.run_step(step, context)

        # 将结果添加到上下文中
        # 使用增强版 WorkflowContext 的 add_step_result 方法（如果可用），否则直接操作字典
        if hasattr(context, "add_step_result"):
            context.add_step_result(result)
        else:
            context.step_results[step.id] = result

        return result

    def run_plan(
        self,
        plan: Plan,
        context: WorkflowContext,
        *,
        record: TaskRecord | None = None,
        finalize_status: bool = True,
        max_replans: int = 1,
        resume_from_existing: bool = False,
    ) -> Plan:
        """执行完整计划

        使用 PlanRunner 来执行计划，它包含安全检查、状态管理等功能。

        Args:
            plan: 执行计划
            context: 工作流上下文
            record: 可选的任务记录，用于同步更新持久化状态
            finalize_status: 是否在 SUMMARIZING 后自动置为 DONE
            max_replans: 允许触发再规划的最大次数
            resume_from_existing: 是否跳过已完成步骤（用于恢复）

        Returns:
            Plan: 执行后的计划（当前实现不做修改）
        """
        # 使用 PlanRunner 执行计划，它包含安全检查、状态管理等功能
        return self.plan_runner.run_plan(
            plan,
            context,
            record=record,
            finalize_status=finalize_status,
            max_replans=max_replans,
            resume_from_existing=resume_from_existing,
        )

    def project_structures_from_s1(
        self,
        context: WorkflowContext,
        *,
        source_step_id: str = "S1",
        structure_step_id: str = "S2",
        max_candidates: int = 3,
    ) -> StepResult:
        """Batch map S1 sequence candidates into S2 structure results.

        Returns an aggregated S2 StepResult that preserves partial success.
        """
        source_result = context.get_step_result(source_step_id)
        if source_result is None:
            raise ValueError(f"Missing source step result '{source_step_id}'")

        candidates = _extract_sequence_candidates(source_result, max_candidates=max_candidates)
        template_step = _resolve_structure_step_template(
            plan=context.plan,
            structure_step_id=structure_step_id,
        )
        if template_step is None:
            raise ValueError(
                f"Missing structure projection step '{structure_step_id}' in current plan"
            )

        tool_chain = _resolve_structure_tool_chain(template_step.tool)
        structure_rows: List[Dict[str, Any]] = []
        fallback_hits = 0
        for index, candidate in enumerate(candidates):
            sequence = candidate["sequence"]
            candidate_row = {
                "candidate_index": index,
                "candidate_id": candidate["candidate_id"],
                "sequence": sequence,
                "source_score": candidate.get("score"),
                "source_metadata": candidate.get("metadata", {}),
                "stage_id": "S2",
                "status": "failed",
                "lineage": {
                    "stage_id": "S2",
                    "source_step_id": source_step_id,
                    "source_candidate_id": candidate["candidate_id"],
                    "source_candidate_index": index,
                    "upstream_lineage": candidate.get("upstream_lineage", {}),
                },
                "attempts": [],
            }
            if not _is_valid_sequence_for_projection(sequence):
                candidate_row["failure_code"] = "S2_SEQUENCE_INVALID"
                candidate_row["failure_reason"] = "sequence must be uppercase alphabetic characters"
                structure_rows.append(candidate_row)
                continue

            attempt_results: List[StepResult] = []
            for tool_id in tool_chain:
                step = _build_structure_projection_step(
                    template=template_step,
                    step_id=f"{structure_step_id}_{index + 1}_{tool_id}",
                    tool_id=tool_id,
                    sequence=sequence,
                    source_candidate_id=candidate["candidate_id"],
                )
                result = self.step_runner.run_step(step, context)
                context.add_step_result(result)
                attempt_results.append(result)
                candidate_row["attempts"].append(_build_structure_attempt_row(result))
                if result.status == "success":
                    break

            final_result = _pick_final_projection_result(attempt_results)
            if final_result is None:
                candidate_row["failure_code"] = "S2_TOOL_EXECUTION_FAILED"
                candidate_row["failure_reason"] = "structure projection produced no result"
                structure_rows.append(candidate_row)
                continue

            normalized_code = _normalize_s2_failure_code(final_result)
            if final_result.status == "success":
                outputs = final_result.outputs
                candidate_row["status"] = "success"
                candidate_row["tool_id"] = final_result.tool
                candidate_row["pdb_path"] = outputs.get("pdb_path")
                candidate_row["plddt"] = outputs.get("plddt")
                candidate_row["confidence"] = outputs.get("confidence") or outputs.get("metrics", {}).get("confidence")
                candidate_row["failure_code"] = None
                candidate_row["failure_reason"] = None
                if len(attempt_results) > 1:
                    fallback_hits += 1
                    candidate_row["fallback_used"] = True
                    candidate_row["lineage"]["fallback_from"] = attempt_results[0].tool
            else:
                candidate_row["status"] = "failed"
                candidate_row["tool_id"] = final_result.tool
                candidate_row["failure_code"] = normalized_code
                candidate_row["failure_reason"] = final_result.error_message
                if len(attempt_results) > 1:
                    candidate_row["failure_code"] = "S2_FALLBACK_EXHAUSTED"
            structure_rows.append(candidate_row)

        successful_rows = [row for row in structure_rows if row.get("status") == "success"]
        best_row = _select_best_structure_result(successful_rows)
        aggregate_status = "success" if successful_rows else "failed"
        now_iso = datetime.now(timezone.utc).isoformat()
        aggregate_outputs: Dict[str, Any] = {
            "stage_id": "S2",
            "source_step_id": source_step_id,
            "structure_results": structure_rows,
            "success_count": len(successful_rows),
            "failure_count": len(structure_rows) - len(successful_rows),
        }
        if best_row is not None:
            aggregate_outputs["pdb_path"] = best_row.get("pdb_path")
            aggregate_outputs["plddt"] = best_row.get("plddt")
            aggregate_outputs["confidence"] = best_row.get("confidence")
            aggregate_outputs["best_candidate_id"] = best_row.get("candidate_id")

        aggregate_error_details: Dict[str, Any] = {}
        aggregate_error_message = None
        aggregate_failure_type = None
        if aggregate_status == "failed":
            aggregate_failure_type = FailureType.TOOL_ERROR.value
            aggregate_error_message = "All S2 structure projections failed"
            aggregate_error_details = {
                "failure_code": "S2_ALL_CANDIDATES_FAILED",
                "phase": "structure_projection",
                "timestamp": now_iso,
            }

        aggregate_result = StepResult(
            task_id=context.task.task_id,
            step_id=structure_step_id,
            tool=template_step.tool,
            status=aggregate_status,
            failure_type=aggregate_failure_type,
            error_message=aggregate_error_message,
            error_details=aggregate_error_details,
            inputs={
                "source_step_id": source_step_id,
                "candidate_count": len(candidates),
            },
            outputs=aggregate_outputs,
            artifacts=_collect_projection_artifacts(successful_rows),
            metrics={
                "exec_type": "structure_projection_batch",
                "mapped_candidates": len(structure_rows),
                "successful_candidates": len(successful_rows),
                "fallback_hits": fallback_hits,
                "partial_success": bool(successful_rows) and len(successful_rows) < len(structure_rows),
            },
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso,
        )
        context.add_step_result(aggregate_result)
        return aggregate_result

    def quality_gate_from_s2(
        self,
        context: WorkflowContext,
        *,
        source_step_id: str = "S2",
        quality_step_id: str = "S3",
        max_candidates: int = 3,
    ) -> StepResult:
        """Run S3 quality gate against S2 batch outputs."""
        source_result = context.get_step_result(source_step_id)
        if source_result is None:
            raise ValueError(f"Missing source step result '{source_step_id}'")

        candidates = _extract_s2_candidates_for_quality_gate(
            source_result,
            max_candidates=max_candidates,
        )
        qc_batch = evaluate_quality_gate_batch(
            candidates,
            constraints=context.task.constraints,
        )
        template_step = _resolve_quality_gate_step_template(
            plan=context.plan,
            quality_step_id=quality_step_id,
        )
        tool_id = template_step.tool if template_step is not None else "biopython_qc"

        passed_rows = qc_batch["passed_samples"]
        failed_rows = qc_batch["failed_samples"]
        pass_count = int(qc_batch["pass_count"])
        fail_count = int(qc_batch["fail_count"])
        pass_fail = bool(qc_batch["pass_fail"])
        now_iso = datetime.now(timezone.utc).isoformat()
        aggregate_status = "success" if pass_fail else "failed"
        best_row = _select_best_quality_candidate(passed_rows)
        tool_lineage = sorted(
            {
                str(row["tool_id"])
                for row in qc_batch["qc_results"]
                if isinstance(row, dict) and row.get("tool_id")
            }
        )

        aggregate_outputs: Dict[str, Any] = {
            "stage_id": "S3",
            "stage_name": "quality_gate",
            "source_step_id": source_step_id,
            "qc_results": qc_batch["qc_results"],
            "passed_samples": passed_rows,
            "failed_samples": failed_rows,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_fail": pass_fail,
            "reject_code_counts": qc_batch["reject_code_counts"],
            "qc_metrics": qc_batch["qc_metrics"],
            "capability_id": "quality_qc",
            "io_type": "sequence_structure_to_qc_metrics",
            "quality_gate": {
                "status": "PASS" if pass_fail else "BLOCK",
                "reject_codes": sorted(qc_batch["reject_code_counts"].keys()),
                "capability_ids": ["quality_qc"],
                "tool_lineage": tool_lineage,
                "qc_pass": pass_fail,
            },
        }
        if best_row is not None:
            aggregate_outputs["best_candidate_id"] = best_row.get("candidate_id")
            aggregate_outputs["sequence"] = best_row.get("sequence")
            aggregate_outputs["pdb_path"] = best_row.get("pdb_path")
            aggregate_outputs["plddt"] = best_row.get("plddt")

        aggregate_error_message = None
        aggregate_error_details: Dict[str, Any] = {}
        aggregate_failure_type = None
        if aggregate_status == "failed":
            aggregate_failure_type = FailureType.NON_RETRYABLE.value
            aggregate_error_message = "All candidates rejected by S3 quality gate"
            aggregate_error_details = {
                "failure_code": QUALITY_GATE_ALL_REJECTED_CODE,
                "phase": "quality_gate",
                "timestamp": now_iso,
                "context": {
                    "reject_code_counts": qc_batch["reject_code_counts"],
                    "failed_candidate_ids": [
                        row.get("candidate_id")
                        for row in failed_rows
                        if isinstance(row, dict)
                    ],
                },
            }

        aggregate_result = StepResult(
            task_id=context.task.task_id,
            step_id=quality_step_id,
            tool=tool_id,
            status=aggregate_status,
            failure_type=aggregate_failure_type,
            error_message=aggregate_error_message,
            error_details=aggregate_error_details,
            inputs={
                "source_step_id": source_step_id,
                "candidate_count": len(candidates),
            },
            outputs=aggregate_outputs,
            artifacts={},
            metrics={
                "exec_type": "quality_gate_batch",
                "evaluated_candidates": len(candidates),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "partial_success": pass_count > 0 and fail_count > 0,
                "reject_code_counts": qc_batch["reject_code_counts"],
                "requirement2": {
                    "capability_id": "quality_qc",
                    "io_type": "sequence_structure_to_qc_metrics",
                    "qc_pass": pass_fail,
                },
            },
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso,
        )
        context.add_step_result(aggregate_result)
        append_event(
            context.task.task_id,
            {
                "event": (
                    "STEP_FINISHED"
                    if aggregate_result.status != "failed"
                    else "STEP_FAILED"
                ),
                "task_id": context.task.task_id,
                "step_id": quality_step_id,
                "tool": tool_id,
                "status": aggregate_result.status,
                "failure_type": aggregate_result.failure_type,
                "error_message": aggregate_result.error_message,
                "timestamp": aggregate_result.timestamp,
                "state": context.status.value,
                "external_status": to_external_status(context.status).value,
                "data": _build_quality_gate_trace_data(aggregate_result),
            },
        )
        return aggregate_result

    def refine_sequences_from_s3(
        self,
        context: WorkflowContext,
        *,
        source_step_id: str = "S3",
        refinement_step_id: str = "S4",
        structure_step_id: str = "S2",
        max_candidates: int = 3,
        max_iterations: int | None = None,
        convergence_delta: float | None = None,
        max_degradation_rounds: int | None = None,
    ) -> StepResult:
        """Run S4 iterative loop: refinement -> structure projection -> quality gate."""
        source_result = context.get_step_result(source_step_id)
        if source_result is None:
            raise ValueError(f"Missing source step result '{source_step_id}'")

        refinement_template = _resolve_refinement_step_template(
            plan=context.plan,
            refinement_step_id=refinement_step_id,
        )
        tool_id = refinement_template.tool if refinement_template is not None else "protein_mpnn"

        structure_template = _resolve_structure_step_template(
            plan=context.plan,
            structure_step_id=structure_step_id,
        )
        if structure_template is None:
            structure_template = PlanStep(
                id=structure_step_id,
                tool="esmfold",
                inputs={"sequence": "S4.sequence"},
                metadata={"stage_id": "S2", "stage_name": "structure_projection"},
            )

        loop_config = _resolve_s4_loop_config(
            context.task.constraints,
            max_iterations=max_iterations,
            convergence_delta=convergence_delta,
            max_degradation_rounds=max_degradation_rounds,
        )
        candidates = _extract_s3_candidates_for_refinement(
            source_result,
            max_candidates=max_candidates,
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        if not candidates:
            failed = StepResult(
                task_id=context.task.task_id,
                step_id=refinement_step_id,
                tool=tool_id,
                status="failed",
                failure_type=FailureType.NON_RETRYABLE.value,
                error_message="S4 refinement requires at least one S3 passed sample",
                error_details={
                    "failure_code": "S4_NO_BASELINE_CANDIDATE",
                    "phase": "structure_refinement",
                    "timestamp": now_iso,
                },
                inputs={"source_step_id": source_step_id},
                outputs={
                    "stage_id": "S4",
                    "stage_name": "structure_conditioned_refinement",
                    "source_step_id": source_step_id,
                    "refinement_iterations": [],
                    "iteration_count": 0,
                    "stop_reason": "missing_baseline",
                },
                metrics={
                    "exec_type": "structure_refinement_loop",
                    "max_iterations": loop_config["max_iterations"],
                    "convergence_delta": loop_config["convergence_delta"],
                    "max_degradation_rounds": loop_config["max_degradation_rounds"],
                },
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso,
            )
            context.add_step_result(failed)
            return failed

        baseline = _select_best_quality_candidate(candidates) or candidates[0]
        current_source = dict(baseline)
        baseline_plddt = _coerce_float(baseline.get("plddt"))
        previous_plddt = baseline_plddt
        best_candidate = dict(baseline)
        best_plddt = baseline_plddt
        successful_iterations = 0
        degraded_rounds = 0
        rollback_applied = False
        stop_reason = "max_iterations_reached"
        iteration_logs: list[StructureRefinementIteration] = []
        latest_refined_candidates: list[dict[str, Any]] = []

        for iteration in range(1, loop_config["max_iterations"] + 1):
            source_pdb_path = current_source.get("pdb_path")
            source_candidate_id = _as_str(current_source.get("candidate_id")) or (
                f"{source_step_id}_baseline"
            )
            source_plddt = previous_plddt
            if not isinstance(source_pdb_path, str) or not source_pdb_path:
                stop_reason = "missing_source_pdb"
                rollback_applied = successful_iterations > 0
                break

            refine_step = _build_structure_refinement_step(
                template=refinement_template,
                refinement_step_id=refinement_step_id,
                iteration=iteration,
                pdb_path=source_pdb_path,
                length_range=context.task.constraints.get("length_range"),
                source_candidate_id=source_candidate_id,
            )
            refine_result = self.step_runner.run_step(refine_step, context)
            context.add_step_result(refine_result)
            if refine_result.status != "success":
                rollback_applied = successful_iterations > 0
                stop_reason = "refinement_failed"
                iteration_logs.append(
                    StructureRefinementIteration(
                        iteration=iteration,
                        source_candidate_id=source_candidate_id,
                        source_pdb_path=_as_str(source_pdb_path),
                        source_plddt=source_plddt,
                        refined_candidate_id=None,
                        refined_sequence=None,
                        refined_pdb_path=None,
                        refined_plddt=None,
                        gain_vs_baseline=None,
                        gain_vs_previous=None,
                        qc_pass_count=0,
                        qc_fail_count=0,
                        status="failed",
                        stop_reason=stop_reason,
                    )
                )
                break

            latest_refined_candidates = _extract_refinement_sequences(
                refine_result.outputs,
                max_candidates=max_candidates,
                fallback_candidate_prefix=f"{refinement_step_id}_iter{iteration}",
            )
            if not latest_refined_candidates:
                rollback_applied = successful_iterations > 0
                stop_reason = "empty_refinement_candidates"
                iteration_logs.append(
                    StructureRefinementIteration(
                        iteration=iteration,
                        source_candidate_id=source_candidate_id,
                        source_pdb_path=_as_str(source_pdb_path),
                        source_plddt=source_plddt,
                        refined_candidate_id=None,
                        refined_sequence=None,
                        refined_pdb_path=None,
                        refined_plddt=None,
                        gain_vs_baseline=None,
                        gain_vs_previous=None,
                        qc_pass_count=0,
                        qc_fail_count=0,
                        status="failed",
                        stop_reason=stop_reason,
                    )
                )
                break

            projected_rows = []
            for candidate_index, refined_candidate in enumerate(latest_refined_candidates, start=1):
                projected_rows.append(
                    _run_structure_projection_for_refinement(
                        step_runner=self.step_runner,
                        context=context,
                        structure_template=structure_template,
                        structure_step_id=structure_step_id,
                        sequence=_as_str(refined_candidate.get("sequence")) or "",
                        refined_candidate_id=_as_str(refined_candidate.get("candidate_id"))
                        or f"{refinement_step_id}_iter{iteration}_cand{candidate_index}",
                        iteration=iteration,
                        candidate_index=candidate_index,
                    )
                )

            qc_batch = evaluate_quality_gate_batch(
                projected_rows,
                constraints=context.task.constraints,
            )
            passed_rows = qc_batch["passed_samples"]
            failed_rows = qc_batch["failed_samples"]
            best_row = _select_best_quality_candidate(passed_rows)
            if best_row is None:
                rollback_applied = successful_iterations > 0
                stop_reason = "quality_gate_rejected"
                iteration_logs.append(
                    StructureRefinementIteration(
                        iteration=iteration,
                        source_candidate_id=source_candidate_id,
                        source_pdb_path=_as_str(source_pdb_path),
                        source_plddt=source_plddt,
                        refined_candidate_id=None,
                        refined_sequence=None,
                        refined_pdb_path=None,
                        refined_plddt=None,
                        gain_vs_baseline=None,
                        gain_vs_previous=None,
                        qc_pass_count=len(passed_rows),
                        qc_fail_count=len(failed_rows),
                        status="failed_qc",
                        stop_reason=stop_reason,
                    )
                )
                break

            successful_iterations += 1
            current_plddt = _coerce_float(best_row.get("plddt"))
            gain_vs_baseline = _diff_or_none(current_plddt, baseline_plddt)
            gain_vs_previous = _diff_or_none(current_plddt, previous_plddt)
            iteration_stop_reason = None

            if (
                current_plddt is not None
                and previous_plddt is not None
                and current_plddt < previous_plddt
            ):
                degraded_rounds += 1
            else:
                degraded_rounds = 0

            if (
                current_plddt is not None
                and previous_plddt is not None
                and current_plddt < previous_plddt
                and degraded_rounds > loop_config["max_degradation_rounds"]
            ):
                rollback_applied = True
                stop_reason = "degradation_limit"
                iteration_stop_reason = stop_reason
            elif (
                current_plddt is not None
                and previous_plddt is not None
                and current_plddt >= previous_plddt
                and (current_plddt - previous_plddt) <= loop_config["convergence_delta"]
            ):
                stop_reason = "converged"
                iteration_stop_reason = stop_reason

            if current_plddt is not None and (
                best_plddt is None or current_plddt > best_plddt
            ):
                best_plddt = current_plddt
                best_candidate = dict(best_row)
            current_source = dict(best_row)
            if current_plddt is not None:
                previous_plddt = current_plddt

            iteration_logs.append(
                StructureRefinementIteration(
                    iteration=iteration,
                    source_candidate_id=source_candidate_id,
                    source_pdb_path=_as_str(source_pdb_path),
                    source_plddt=source_plddt,
                    refined_candidate_id=_as_str(best_row.get("candidate_id")),
                    refined_sequence=_as_str(best_row.get("sequence")),
                    refined_pdb_path=_as_str(best_row.get("pdb_path")),
                    refined_plddt=current_plddt,
                    gain_vs_baseline=gain_vs_baseline,
                    gain_vs_previous=gain_vs_previous,
                    qc_pass_count=len(passed_rows),
                    qc_fail_count=len(failed_rows),
                    status="success",
                    stop_reason=iteration_stop_reason,
                )
            )

            if iteration_stop_reason is not None:
                break

        selected_candidate = best_candidate if successful_iterations > 0 else None
        final_plddt = _coerce_float(
            selected_candidate.get("plddt") if isinstance(selected_candidate, dict) else None
        )
        audit_payload = build_structure_refinement_audit(
            task_id=context.task.task_id,
            step_id=refinement_step_id,
            source_step_id=source_step_id,
            baseline=baseline,
            iterations=iteration_logs,
            stop_reason=stop_reason,
            rollback_applied=rollback_applied,
            selected_candidate=selected_candidate,
        )
        audit_path = persist_structure_refinement_audit(
            task_id=context.task.task_id,
            step_id=refinement_step_id,
            audit_payload=audit_payload,
        )

        result_status = "success" if successful_iterations > 0 else "failed"
        error_message = None
        error_details: Dict[str, Any] = {}
        failure_type = None
        if result_status == "failed":
            failure_type = FailureType.NON_RETRYABLE.value
            error_message = "S4 refinement loop produced no valid candidates"
            error_details = {
                "failure_code": "S4_REFINEMENT_FAILED",
                "phase": "structure_refinement",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stop_reason": stop_reason,
            }

        result = StepResult(
            task_id=context.task.task_id,
            step_id=refinement_step_id,
            tool=tool_id,
            status=result_status,
            failure_type=failure_type,
            error_message=error_message,
            error_details=error_details,
            inputs={
                "source_step_id": source_step_id,
                "max_candidates": max_candidates,
                "max_iterations": loop_config["max_iterations"],
                "convergence_delta": loop_config["convergence_delta"],
                "max_degradation_rounds": loop_config["max_degradation_rounds"],
            },
            outputs={
                "stage_id": "S4",
                "stage_name": "structure_conditioned_refinement",
                "source_step_id": source_step_id,
                "loop_path": ["S4", "S2", "S3"],
                "lineage": {
                    "stage_id": "S4",
                    "source_step_id": source_step_id,
                    "baseline_candidate_id": baseline.get("candidate_id"),
                    "rollback_applied": rollback_applied,
                },
                "sequence": selected_candidate.get("sequence")
                if isinstance(selected_candidate, dict)
                else None,
                "pdb_path": selected_candidate.get("pdb_path")
                if isinstance(selected_candidate, dict)
                else None,
                "plddt": final_plddt,
                "candidates": latest_refined_candidates,
                "refinement_iterations": [row.to_dict() for row in iteration_logs],
                "iteration_count": len(iteration_logs),
                "successful_iterations": successful_iterations,
                "stop_reason": stop_reason,
                "gain_metrics": {
                    "baseline_plddt": baseline_plddt,
                    "final_plddt": final_plddt,
                    "delta_vs_baseline": _diff_or_none(final_plddt, baseline_plddt),
                },
            },
            artifacts={
                "refinement_audit_path": str(audit_path),
            },
            metrics={
                "exec_type": "structure_refinement_loop",
                "max_iterations": loop_config["max_iterations"],
                "convergence_delta": loop_config["convergence_delta"],
                "max_degradation_rounds": loop_config["max_degradation_rounds"],
                "rollback_applied": rollback_applied,
            },
            risk_flags=[],
            logs_path=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        context.add_step_result(result)
        append_event(
            context.task.task_id,
            {
                "event": "STEP_FINISHED" if result.status == "success" else "STEP_FAILED",
                "task_id": context.task.task_id,
                "step_id": refinement_step_id,
                "tool": tool_id,
                "status": result.status,
                "failure_type": result.failure_type,
                "error_message": result.error_message,
                "timestamp": result.timestamp,
                "state": context.status.value,
                "external_status": to_external_status(context.status).value,
                "data": _build_structure_refinement_trace_data(result),
            },
        )
        return result

    def summarize_and_finalize(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        summarizer: SummarizerAgent,
    ) -> DesignResult:
        """运行 Summarizer 并驱动 SUMMARIZING → DONE/FAILED 状态变更。"""
        transition_task_status(
            context,
            record,
            InternalStatus.SUMMARIZING,
            reason="plan_execution_completed",
        )
        try:
            design = summarizer.summarize(context)
        except Exception:
            self._mark_failed_if_needed(context, record, reason="summarizer_error")
            raise

        context.design_result = design
        if record is not None:
            record.design_result = design

        final_status = derive_task_status(
            context.task,
            context.plan,
            context.step_results,
            context.safety_events,
            context.design_result,
        )
        final_reason = (
            "summarizer_completed"
            if final_status == InternalStatus.DONE
            else "workflow_failed"
        )
        transition_task_status(
            context,
            record,
            final_status,
            reason=final_reason,
        )
        return design

    def _mark_failed_if_needed(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        *,
        reason: str,
    ) -> None:
        if context.status in TERMINAL_INTERNAL_STATUSES:
            return
        transition_task_status(
            context,
            record,
            InternalStatus.FAILED,
            reason=reason,
        )


def _resolve_structure_step_template(
    *,
    plan: Plan | None,
    structure_step_id: str,
) -> PlanStep | None:
    if plan is None:
        return None
    for step in plan.steps:
        if step.id == structure_step_id:
            return step
    return None


def _resolve_quality_gate_step_template(
    *,
    plan: Plan | None,
    quality_step_id: str,
) -> PlanStep | None:
    if plan is None:
        return None
    for step in plan.steps:
        if step.id == quality_step_id:
            return step
    return None


def _resolve_refinement_step_template(
    *,
    plan: Plan | None,
    refinement_step_id: str,
) -> PlanStep | None:
    if plan is None:
        return None
    for step in plan.steps:
        if step.id == refinement_step_id:
            return step
    for step in plan.steps:
        metadata = step.metadata if isinstance(step.metadata, dict) else {}
        if metadata.get("stage_id") == "S4":
            return step
    return None


def _extract_sequence_candidates(
    source_result: StepResult,
    *,
    max_candidates: int,
) -> List[Dict[str, Any]]:
    outputs = source_result.outputs if isinstance(source_result.outputs, dict) else {}
    candidates_raw = outputs.get("candidates")
    upstream_lineage = (
        source_result.outputs.get("lineage", {})
        if isinstance(source_result.outputs, dict)
        else {}
    )

    resolved: List[Dict[str, Any]] = []
    seen_sequences: set[str] = set()
    primary_sequence = outputs.get("sequence")
    if isinstance(primary_sequence, str) and primary_sequence and primary_sequence not in seen_sequences:
        resolved.append(
            {
                "candidate_id": f"{source_result.step_id}_candidate_primary",
                "sequence": primary_sequence,
                "score": None,
                "metadata": {"source": "primary"},
                "upstream_lineage": upstream_lineage,
            }
        )
        seen_sequences.add(primary_sequence)

    if isinstance(candidates_raw, list):
        for idx, item in enumerate(candidates_raw):
            sequence = None
            score = None
            metadata: Dict[str, Any] = {"source": "fallback"}
            if isinstance(item, dict):
                raw_seq = item.get("sequence")
                if isinstance(raw_seq, str):
                    sequence = raw_seq
                score = item.get("score")
                metadata.update({k: v for k, v in item.items() if k != "sequence"})
            elif isinstance(item, str):
                sequence = item
            if not isinstance(sequence, str) or not sequence or sequence in seen_sequences:
                continue
            resolved.append(
                {
                    "candidate_id": f"{source_result.step_id}_candidate_{idx}",
                    "sequence": sequence,
                    "score": score,
                    "metadata": metadata,
                    "upstream_lineage": upstream_lineage,
                }
            )
            seen_sequences.add(sequence)
            if len(resolved) >= max(1, max_candidates):
                break

    if not resolved:
        raise ValueError(
            f"No sequence candidates found in '{source_result.step_id}' outputs"
        )
    return resolved[: max(1, max_candidates)]


def _extract_s2_candidates_for_quality_gate(
    source_result: StepResult,
    *,
    max_candidates: int,
) -> List[Dict[str, Any]]:
    outputs = source_result.outputs if isinstance(source_result.outputs, dict) else {}
    structure_results = outputs.get("structure_results")
    resolved: List[Dict[str, Any]] = []

    if isinstance(structure_results, list):
        for idx, item in enumerate(structure_results):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row.setdefault("candidate_id", f"{source_result.step_id}_structure_{idx + 1}")
            row.setdefault("lineage", outputs.get("lineage", {}))
            row.setdefault("tool_id", row.get("tool_id") or source_result.tool)
            resolved.append(row)
            if len(resolved) >= max(1, max_candidates):
                break
    else:
        plddt = outputs.get("plddt")
        if not isinstance(plddt, (int, float)):
            confidence = outputs.get("confidence")
            if isinstance(confidence, dict) and isinstance(
                confidence.get("plddt_mean"), (int, float)
            ):
                plddt = confidence["plddt_mean"]
        row = {
            "candidate_id": f"{source_result.step_id}_primary",
            "status": source_result.status,
            "sequence": outputs.get("sequence"),
            "pdb_path": outputs.get("pdb_path"),
            "plddt": plddt,
            "tool_id": source_result.tool,
            "lineage": outputs.get("lineage", {}),
            "failure_code": _extract_failure_code(source_result),
            "failure_reason": source_result.error_message,
        }
        resolved.append(row)

    if not resolved:
        raise ValueError(
            f"No structure candidates found in '{source_result.step_id}' outputs"
        )
    return resolved[: max(1, max_candidates)]


def _extract_s3_candidates_for_refinement(
    source_result: StepResult,
    *,
    max_candidates: int,
) -> List[Dict[str, Any]]:
    outputs = source_result.outputs if isinstance(source_result.outputs, dict) else {}
    passed_rows = outputs.get("passed_samples")
    resolved: list[dict[str, Any]] = []

    if isinstance(passed_rows, list):
        for idx, item in enumerate(passed_rows):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row.setdefault("candidate_id", f"{source_result.step_id}_passed_{idx + 1}")
            resolved.append(row)
            if len(resolved) >= max(1, max_candidates):
                break
    if not resolved:
        qc_rows = outputs.get("qc_results")
        if isinstance(qc_rows, list):
            for idx, item in enumerate(qc_rows):
                if not isinstance(item, dict):
                    continue
                if item.get("status") != "pass":
                    continue
                row = dict(item)
                row.setdefault("candidate_id", f"{source_result.step_id}_qc_{idx + 1}")
                resolved.append(row)
                if len(resolved) >= max(1, max_candidates):
                    break
    if not resolved and bool(outputs.get("pass_fail")):
        plddt = outputs.get("plddt")
        if not isinstance(plddt, (int, float)):
            confidence = outputs.get("confidence")
            if isinstance(confidence, dict) and isinstance(confidence.get("plddt_mean"), (int, float)):
                plddt = confidence.get("plddt_mean")
        resolved.append(
            {
                "candidate_id": f"{source_result.step_id}_primary",
                "sequence": outputs.get("sequence"),
                "pdb_path": outputs.get("pdb_path"),
                "plddt": plddt,
                "lineage": outputs.get("lineage", {}),
            }
        )
    return resolved[: max(1, max_candidates)]


def _extract_refinement_sequences(
    outputs: Dict[str, Any],
    *,
    max_candidates: int,
    fallback_candidate_prefix: str,
) -> List[Dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    primary_sequence = outputs.get("sequence")
    primary_score = outputs.get("sequence_score")
    if isinstance(primary_sequence, str) and primary_sequence and primary_sequence not in seen:
        resolved.append(
            {
                "candidate_id": f"{fallback_candidate_prefix}_primary",
                "sequence": primary_sequence,
                "score": primary_score,
                "source": "primary",
            }
        )
        seen.add(primary_sequence)

    raw_candidates = outputs.get("candidates")
    if isinstance(raw_candidates, list):
        for idx, item in enumerate(raw_candidates):
            sequence = None
            score = None
            candidate_id = f"{fallback_candidate_prefix}_{idx + 1}"
            if isinstance(item, dict):
                raw_sequence = item.get("sequence")
                if isinstance(raw_sequence, str):
                    sequence = raw_sequence
                score = item.get("score")
                if isinstance(item.get("candidate_id"), str):
                    candidate_id = str(item.get("candidate_id"))
            elif isinstance(item, str):
                sequence = item
            if not isinstance(sequence, str) or not sequence or sequence in seen:
                continue
            resolved.append(
                {
                    "candidate_id": candidate_id,
                    "sequence": sequence,
                    "score": score,
                    "source": "candidate_list",
                }
            )
            seen.add(sequence)
            if len(resolved) >= max(1, max_candidates):
                break
    return resolved[: max(1, max_candidates)]


def _run_structure_projection_for_refinement(
    *,
    step_runner: StepRunner,
    context: WorkflowContext,
    structure_template: PlanStep,
    structure_step_id: str,
    sequence: str,
    refined_candidate_id: str,
    iteration: int,
    candidate_index: int,
) -> Dict[str, Any]:
    row = {
        "candidate_id": refined_candidate_id,
        "status": "failed",
        "sequence": sequence,
        "lineage": {
            "stage_id": "S2",
            "source_stage_id": "S4",
            "source_candidate_id": refined_candidate_id,
            "iteration": iteration,
        },
    }
    if not _is_valid_sequence_for_projection(sequence):
        row["failure_code"] = "S2_SEQUENCE_INVALID"
        row["failure_reason"] = "sequence must be uppercase alphabetic characters"
        return row

    attempts = []
    for tool_id in _resolve_structure_tool_chain(structure_template.tool):
        step = _build_structure_projection_step(
            template=structure_template,
            step_id=(
                f"{structure_step_id}_s4_{iteration}_{candidate_index}_{tool_id}"
            ),
            tool_id=tool_id,
            sequence=sequence,
            source_candidate_id=refined_candidate_id,
        )
        result = step_runner.run_step(step, context)
        context.add_step_result(result)
        attempts.append(result)
        if result.status == "success":
            break

    final_result = _pick_final_projection_result(attempts)
    if final_result is None:
        row["failure_code"] = "S2_TOOL_EXECUTION_FAILED"
        row["failure_reason"] = "structure projection produced no result"
        return row

    if final_result.status == "success":
        outputs = final_result.outputs
        row["status"] = "success"
        row["tool_id"] = final_result.tool
        row["pdb_path"] = outputs.get("pdb_path")
        row["plddt"] = outputs.get("plddt")
        row["confidence"] = outputs.get("confidence")
        row["failure_code"] = None
        row["failure_reason"] = None
    else:
        row["status"] = "failed"
        row["tool_id"] = final_result.tool
        row["failure_code"] = _normalize_s2_failure_code(final_result)
        row["failure_reason"] = final_result.error_message
        if len(attempts) > 1:
            row["failure_code"] = "S2_FALLBACK_EXHAUSTED"
    return row


def _resolve_s4_loop_config(
    constraints: Dict[str, Any],
    *,
    max_iterations: int | None,
    convergence_delta: float | None,
    max_degradation_rounds: int | None,
) -> Dict[str, Any]:
    local = (
        constraints.get("structure_refinement")
        if isinstance(constraints.get("structure_refinement"), dict)
        else {}
    )

    raw_max_iterations = (
        max_iterations
        if max_iterations is not None
        else local.get("max_iterations", constraints.get("s4_max_iterations"))
    )
    raw_convergence_delta = (
        convergence_delta
        if convergence_delta is not None
        else local.get("convergence_delta", constraints.get("s4_convergence_delta"))
    )
    raw_max_degradation = (
        max_degradation_rounds
        if max_degradation_rounds is not None
        else local.get(
            "max_degradation_rounds",
            constraints.get("s4_max_degradation_rounds"),
        )
    )

    try:
        normalized_max_iterations = int(raw_max_iterations)
    except (TypeError, ValueError):
        normalized_max_iterations = _S4_DEFAULT_MAX_ITERATIONS
    normalized_max_iterations = max(1, normalized_max_iterations)

    try:
        normalized_convergence_delta = float(raw_convergence_delta)
    except (TypeError, ValueError):
        normalized_convergence_delta = _S4_DEFAULT_CONVERGENCE_DELTA
    normalized_convergence_delta = max(0.0, normalized_convergence_delta)

    try:
        normalized_max_degradation = int(raw_max_degradation)
    except (TypeError, ValueError):
        normalized_max_degradation = _S4_DEFAULT_MAX_DEGRADATION_ROUNDS
    normalized_max_degradation = max(0, normalized_max_degradation)

    return {
        "max_iterations": normalized_max_iterations,
        "convergence_delta": normalized_convergence_delta,
        "max_degradation_rounds": normalized_max_degradation,
    }


def _build_structure_refinement_step(
    *,
    template: PlanStep | None,
    refinement_step_id: str,
    iteration: int,
    pdb_path: str,
    length_range: Any,
    source_candidate_id: str,
) -> PlanStep:
    tool_id = template.tool if isinstance(template, PlanStep) else "protein_mpnn"
    step_id = f"{refinement_step_id}_{iteration}"
    inputs = {
        "pdb_path": pdb_path,
        "source_candidate_id": source_candidate_id,
        "stage_id": "S4",
        "iteration": iteration,
    }
    if isinstance(length_range, (list, tuple)) and len(length_range) == 2:
        inputs["length_range"] = [int(length_range[0]), int(length_range[1])]
    metadata = dict(template.metadata if isinstance(template, PlanStep) else {})
    metadata.update(
        {
            "stage_id": "S4",
            "stage_name": "structure_conditioned_refinement",
            "iteration": iteration,
            "lineage": {
                "stage_id": "S4",
                "source_candidate_id": source_candidate_id,
                "source_stage_id": "S3",
            },
        }
    )
    return PlanStep(
        id=step_id,
        tool=tool_id,
        inputs=inputs,
        metadata=metadata,
    )


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _diff_or_none(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None:
        return None
    return round(current - baseline, 6)


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _resolve_structure_tool_chain(primary_tool_id: str) -> List[str]:
    candidates = [primary_tool_id]
    fallback = _find_structure_fallback_tool(primary_tool_id)
    if fallback and fallback not in candidates:
        candidates.append(fallback)
    return candidates


def _find_structure_fallback_tool(primary_tool_id: str) -> str | None:
    try:
        kg = load_tool_kg()
    except ToolKGError:
        if primary_tool_id == "nim_esmfold":
            return "esmfold"
        if primary_tool_id == "esmfold":
            return "nim_esmfold"
        return None

    tools = kg.get("tools", [])
    if not isinstance(tools, list):
        return None

    primary_entry = None
    for tool in tools:
        if isinstance(tool, dict) and tool.get("id") == primary_tool_id:
            primary_entry = tool
            break
    if not isinstance(primary_entry, dict):
        return None

    capabilities = primary_entry.get("capabilities", [])
    if not isinstance(capabilities, list):
        capabilities = []
    primary_caps = set(capabilities)
    if not primary_caps:
        return None

    fallback_candidates: List[tuple[int, str]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_id = tool.get("id")
        if not isinstance(tool_id, str) or tool_id == primary_tool_id:
            continue
        caps = tool.get("capabilities", [])
        if not isinstance(caps, list) or not primary_caps.intersection(caps):
            continue
        execution = tool.get("execution")
        is_remote = isinstance(execution, dict) and execution.get("backend") == "remote_model_service"
        fallback_candidates.append((1 if is_remote else 0, tool_id))

    if not fallback_candidates:
        return None
    fallback_candidates.sort(key=lambda row: (row[0], row[1]))
    return fallback_candidates[0][1]


def _build_structure_projection_step(
    *,
    template: PlanStep,
    step_id: str,
    tool_id: str,
    sequence: str,
    source_candidate_id: str,
) -> PlanStep:
    metadata = dict(template.metadata or {})
    metadata.update(
        {
            "stage_id": "S2",
            "stage_name": "structure_projection",
            "lineage": {
                "stage_id": "S2",
                "source_candidate_id": source_candidate_id,
            },
        }
    )
    return PlanStep(
        id=step_id,
        tool=tool_id,
        inputs={"sequence": sequence},
        metadata=metadata,
    )


def _is_valid_sequence_for_projection(sequence: str) -> bool:
    if not isinstance(sequence, str) or not sequence:
        return False
    return all(char.isalpha() and char.isupper() for char in sequence)


def _build_structure_attempt_row(result: StepResult) -> Dict[str, Any]:
    error_code = None
    if isinstance(result.error_details, dict):
        error_code = result.error_details.get("failure_code")
    return {
        "step_id": result.step_id,
        "tool_id": result.tool,
        "status": result.status,
        "failure_code": error_code,
        "error_message": result.error_message,
    }


def _pick_final_projection_result(results: Sequence[StepResult]) -> StepResult | None:
    if not results:
        return None
    for result in results:
        if result.status == "success":
            return result
    return results[-1]


def _normalize_s2_failure_code(result: StepResult) -> str:
    failure_code = None
    if isinstance(result.error_details, dict):
        failure_code = result.error_details.get("failure_code")

    if failure_code in {
        FailureCode.INPUT_RESOLUTION_FAILED.value,
        FailureCode.NIM_INVALID_INPUT.value,
    }:
        return "S2_SEQUENCE_INVALID"
    if failure_code in {
        FailureCode.OUTPUT_MISSING.value,
        FailureCode.OUTPUT_TYPE_MISMATCH.value,
        FailureCode.NIM_INVALID_RESPONSE.value,
    }:
        return "S2_OUTPUT_INVALID"
    if failure_code in {
        FailureCode.NIM_TIMEOUT.value,
        FailureCode.NIM_NETWORK_ERROR.value,
        FailureCode.NIM_AUTH_FAILED.value,
        FailureCode.REMOTE_POLL_TIMEOUT.value,
        FailureCode.REMOTE_JOB_FAILED.value,
        FailureCode.ADAPTER_NOT_FOUND.value,
    }:
        return "S2_TOOL_UNAVAILABLE"
    return "S2_TOOL_EXECUTION_FAILED"


def _select_best_structure_result(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not rows:
        return None
    ranked = sorted(
        rows,
        key=lambda row: (
            -(float(row.get("plddt")) if isinstance(row.get("plddt"), (int, float)) else -1.0),
            str(row.get("candidate_id", "")),
        ),
    )
    return ranked[0]


def _collect_projection_artifacts(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    pdb_paths = [
        row.get("pdb_path")
        for row in rows
        if isinstance(row.get("pdb_path"), str) and row.get("pdb_path")
    ]
    if not pdb_paths:
        return {}
    return {"pdb_paths": pdb_paths}


def _select_best_quality_candidate(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not rows:
        return None
    ranked = sorted(
        rows,
        key=lambda row: (
            -(float(row.get("plddt")) if isinstance(row.get("plddt"), (int, float)) else -1.0),
            str(row.get("candidate_id", "")),
        ),
    )
    return ranked[0]


def _extract_failure_code(result: StepResult) -> str | None:
    if not isinstance(result.error_details, dict):
        return None
    value = result.error_details.get("failure_code")
    if isinstance(value, FailureCode):
        return value.value
    if isinstance(value, str):
        return value
    return None


def _build_quality_gate_trace_data(result: StepResult) -> Dict[str, Any]:
    outputs = result.outputs if isinstance(result.outputs, dict) else {}
    reject_counts = outputs.get("reject_code_counts")
    failure_code = _extract_failure_code(result)
    failed_rows = outputs.get("failed_samples")
    failed_samples: list[dict[str, Any]] = []
    if isinstance(failed_rows, list):
        for item in failed_rows:
            if not isinstance(item, dict):
                continue
            failed_samples.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "reject_codes": item.get("reject_codes"),
                    "reason": item.get("reason"),
                }
            )
    return {
        "stage_id": outputs.get("stage_id"),
        "failure_code": failure_code,
        "quality_gate": {
            "pass_count": outputs.get("pass_count"),
            "fail_count": outputs.get("fail_count"),
            "pass_fail": outputs.get("pass_fail"),
            "reject_code_counts": reject_counts if isinstance(reject_counts, dict) else {},
            "failed_samples": failed_samples,
        },
    }


def _build_structure_refinement_trace_data(result: StepResult) -> Dict[str, Any]:
    outputs = result.outputs if isinstance(result.outputs, dict) else {}
    gain_metrics = outputs.get("gain_metrics")
    lineage = outputs.get("lineage")
    return {
        "stage_id": outputs.get("stage_id"),
        "stop_reason": outputs.get("stop_reason"),
        "iteration_count": outputs.get("iteration_count"),
        "successful_iterations": outputs.get("successful_iterations"),
        "gain_metrics": gain_metrics if isinstance(gain_metrics, dict) else {},
        "lineage": lineage if isinstance(lineage, dict) else {},
    }
