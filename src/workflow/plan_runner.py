from __future__ import annotations
from typing import Any, Protocol
from src.agents.planner import PlannerAgent
from src.infra.event_log_factory import make_candidate_validation_failed
from src.models.contracts import (
    Plan,
    StepResult,
)
from src.models.validation import (
    CandidateExecutionValidationError,
    validate_plan_executability,
)
from src.models.db import (
    TaskRecord,
    InternalStatus,
    TERMINAL_INTERNAL_STATUSES,
    to_external_status,
)
from src.models.event_log import ActorType
from src.storage.log_store import append_event, write_event_log
from src.workflow.context import WorkflowContext
from src.workflow.step_runner import StepRunner
from src.workflow.patch_runner import PatchRunner, PendingPatch
from src.agents.safety import SafetyAgent
from src.workflow.status import transition_task_status
from src.workflow.snapshots import build_context_runtime_state_summary
from src.workflow.recovery import (
    resolve_workflow_action_route,
)
from src.workflow.errors import (
    FailureType,
    PlanRunError,
    StepRunError,
    classify_exception,
    is_retryable_failure,
)
from src.workflow.runtime_policy import runtime_policy_trace
from src.workflow.plan_trace_builder import build_step_trace_data
from src.workflow.plan_runner_recovery import (
    PlanRunnerRecoveryMixin,
    has_recovery_upgrade,
    should_require_replan_confirm,
)

__all__ = ["PlanRunner", "_build_step_trace_data"]


class StepRunnerLike(Protocol):
    """最小化约束的 StepRunner 接口，用于依赖注入和单元测试"""

    def run_step(self, step, context: WorkflowContext) -> StepResult:  # type: ignore
        """执行单个 PlanStep,返回 StepResult

        真实实现由 src/workflow/step_runner.StepRunner 提供
        """


class PlanRunner(PlanRunnerRecoveryMixin):
    """PlanRunner: 顺序执行 Plan.steps, 并回写 WorkflowContext, 管理任务状态

    实现最小闭环的行为: 依次执行 Plan 中的步骤
    使用 StepRunner 执行每个步骤，并将执行结果写入 WorkflowContext
    同时管理 InternalStatus 状态转换

    Attributes:
        step_runner(StepRunner):
            通过构造函数注入的步骤执行器，需实现
            ``run_step(step, context) -> StepResult``
        safety_agent(SafetyAgent):
            通过构造函数注入的安全检查器，用于执行安全检查
            A4 阶段：已接入，执行 task_input 和 final_result 检查

    Version:
        v2(C1扩展): 在 v1 基础上增加 InternalStatus 状态管理

        完整状态机流程 (CREATED → PLANNING → PLANNED → RUNNING → ... → SUMMARIZING → DONE/FAILED):
        - CREATED → PLANNING: 由 PlannerAgent 负责（任务创建后开始规划）
        - PLANNING → PLANNED: 由 PlannerAgent 负责（规划完成，生成 Plan）
        - PLANNED → RUNNING: 由 PlanRunner 负责（开始执行计划）
        - RUNNING → WAITING_PATCH → PATCHING → RUNNING: 由 PlanRunner 负责（重试失败触发 patch）
        - RUNNING → WAITING_REPLAN → REPLANNING → RUNNING/FAILED: 由 PlanRunner 负责（安全阻断或 patch 失败触发再规划）
        - RUNNING → SUMMARIZING: 由 PlanRunner 负责（执行完成，进入汇总阶段）
        - SUMMARIZING → DONE/FAILED: 由 SummarizerAgent 或上层负责（汇总完成，任务结束）

        PlanRunner 的状态转换职责:
        - 主要职责: 当 ``context.status == PLANNED`` 时，更新为 ``RUNNING``
        - patch 流程: ``RUNNING → WAITING_PATCH → PATCHING → RUNNING``
        - replan 流程: ``RUNNING/PATCHING → WAITING_REPLAN → REPLANNING → RUNNING/FAILED``
        - 执行完成后: 当 ``context.status == RUNNING`` 时，更新为 ``SUMMARIZING``
          （若 ``finalize_status=True``，则继续更新为 ``DONE``）
        - 其他状态: 若 ``context.status`` 不是 ``PLANNED``，PlanRunner 不改变状态
          （允许上层已经设置状态的情况，例如已经是 RUNNING 或终端状态）
        - 终端状态保护: 若 ``context.status`` 为 ``DONE`` 或 ``FAILED``，保持状态不变
          （终端状态不应被 PlanRunner 改变）

        - 输入：
            - plan(Plan)
            - context(WorkflowContext)
                要求: ``context.task.task_id == plan.task_id``
                ``context.plan`` 允许为 ``None``, PlanRunner 会负责写入
                ``context.status`` 建议为 ``PLANNED``，表示计划已生成，可以开始执行
                但也支持其他状态（如 ``CREATED``, ``RUNNING`` 等），PlanRunner 会根据状态决定是否更新
        - 行为:
            1. 状态预检查与更新:
                - 若 ``context.status == PLANNED``, 则更新为 ``RUNNING``
                - 若 ``context.status`` 不是 ``PLANNED``，仍会执行步骤，但不更新状态
                   （允许上层已经设置状态的情况，例如已经是 RUNNING 或终端状态）
            2. 若 ``context.plan`` 为 ``None``, 则设置为当前 plan;
                若已有值，则不覆盖
            3. 按 ``plan.steps`` 顺序依次执行:
                - 对每个step:
                    - 调用 ``self._step_runner.run_step(step, context)``
                    - 将 StepResult 写入 ``context.step_results[step_id]``
            4. 执行完成后:
                - 若 ``context.status == RUNNING``，更新为 ``SUMMARIZING``
                - ``finalize_status=True`` 时继续更新为 ``DONE``（最小汇总实现）
            5. 异常处理:
                - 若 step_runner 抛出异常，PlanRunner 不吞掉，直接向上抛给调用方处理
                - 异常发生时，若当前不是终端态，则置为 ``FAILED``
        - 输出:
            - 返回原始 ``plan`` 对象(为未来支持 Patch/Replan 留接口)

        Future Work:
            - Patch/Replan 的策略优化与完整前缀锁定逻辑
            - 状态回滚: 未来可能需要在异常时支持状态回滚机制
    """

    def __init__(
        self,
        step_runner: StepRunnerLike | None = None,
        safety_agent: SafetyAgent | None = None,
        planner_agent: PlannerAgent | None = None,
        patch_runner: PatchRunner | None = None,
    ) -> None:
        # 默认使用真实 StepRunner, 便于生产代码
        self._step_runner: StepRunnerLike = step_runner or StepRunner()
        # A4: 默认使用真实 SafetyAgent, 便于生产代码
        self._safety_agent: SafetyAgent = safety_agent or SafetyAgent()
        # B3: 默认使用真实 PlannerAgent，用于 patch
        self._planner: PlannerAgent = planner_agent or PlannerAgent()
        # B3-5: PatchRunner，封装 patch 闭环
        self._patch_runner: PatchRunner = patch_runner or PatchRunner(
            step_runner=self._step_runner,
            planner_agent=self._planner,
        )

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
        return self._run_plan_impl(
            plan,
            context,
            record=record,
            finalize_status=finalize_status,
            max_replans=max_replans,
            resume_from_existing=resume_from_existing,
        )

    def _run_plan_impl(
        self,
        plan: Plan,
        context: WorkflowContext,
        *,
        record: TaskRecord | None = None,
        finalize_status: bool = True,
        max_replans: int = 1,
        resume_from_existing: bool = False,
    ) -> Plan:
        """执行给定的 Plan, 顺序遍历 plan.steps, 调用 StepRunner 并写入 WorkflowContext

        同时管理 InternalStatus 状态转换：
        - 如果 context.status 为 PLANNED，则更新为 RUNNING（主要职责）
        - 如果 context.status 不是 PLANNED，保持原状态不变（允许上层已设置状态）
        - 执行完成后，若 context.status 为 RUNNING，则更新为 SUMMARIZING
        - finalize_status=True 时继续更新为 DONE（最小汇总实现）

        Args:
            plan: 要执行的计划对象
            context: 工作流上下文，包含任务信息、当前状态等
            record: 可选的任务记录，用于同步更新持久化状态
            finalize_status: 是否在 SUMMARIZING 后自动置为 DONE
            max_replans: 允许触发再规划的最大次数（最小实现，默认 1）
            resume_from_existing: 是否基于既有成功结果跳过已完成步骤

        Returns:
            Plan: 返回原始 plan 对象（为未来支持 Patch/Replan 预留接口）

        Raises:
            ValueError: 当 context.task.task_id 与 plan.task_id 不一致时
            PlanRunError: 当步骤执行/安全阻断/工具异常时，携带统一失败分类

        Note:
            - 状态转换遵循完整状态机流程（含 WAITING_PATCH/PATCHING/WAITING_REPLAN/REPLANNING）
            - PlanRunner 主要负责 PLANNED → RUNNING、patch/replan 的中间态推进
            - finalize_status=True 时负责 SUMMARIZING → DONE（最小实现）
            - max_replans 为最小再规划次数控制，超过则置为 FAILED
        """
        # 基本一致性校验：task_id 必须一致
        if context.task.task_id != plan.task_id:
            raise ValueError(
                f"WorkflowContext.task.task_id ({context.task.task_id}) "
                f"does not match Plan.task_id ({plan.task_id})"
            )
        try:
            self._validate_candidate_before_execution(plan, context)

            # A3: 状态更新 - 如果状态为 PLANNED，则更新为 RUNNING
            if context.status == InternalStatus.PLANNED:
                transition_task_status(
                    context,
                    record,
                    InternalStatus.RUNNING,
                    reason="plan_execution_start",
                )

            # A4: 安全检查 - 任务输入阶段
            input_safety_result = self._safety_agent.check_task_input(
                context.task, plan
            )
            self._add_safety_event(context, input_safety_result)
            if input_safety_result.action == "block":
                self._request_replan(
                    context,
                    record,
                    reason="safety_block",
                    failure_type=FailureType.SAFETY_BLOCK,
                    message="SafetyAgent blocked task input before execution",
                    code="SAFETY_TASK_INPUT_BLOCK",
                    explanation=self._build_basic_replan_explanation(
                        "safety_block (task input blocked)"
                    ),
                )

            # 若 context.plan 为 None, 则设置为当前 plan
            if context.plan is None:
                context.plan = plan

            # 顺序执行 steps, 并将 StepResult 写回 context.step_results
            pending_patches: dict[str, PendingPatch] = {}
            step_index = 0
            while step_index < len(plan.steps):
                step = plan.steps[step_index]
                if resume_from_existing and self._should_skip_step(step, context):
                    step_index += 1
                    continue
                try:
                    outcome = self._patch_runner.run_step_with_patch(
                        plan,
                        step_index,
                        context,
                        record=record,
                    )
                except StepRunError as exc:
                    raise PlanRunError.from_step_error(step.id, exc) from exc
                except Exception as exc:
                    failure_type = classify_exception(exc)
                    raise PlanRunError(
                        failure_type=failure_type,
                        message=(
                            f"Unexpected error when executing step {step.id}: {exc}"
                        ),
                        step_id=step.id,
                        code="STEP_EXECUTION_ERROR",
                        cause=exc,
                    ) from exc

                plan = outcome.plan
                if outcome.pending_patch:
                    pending_patches[outcome.pending_patch.target_step_id] = (
                        outcome.pending_patch
                    )
                if context.status == InternalStatus.WAITING_PATCH:
                    return plan

                failed_result: StepResult | None = None
                blocked_by_safety = False
                for step_result in outcome.step_results:
                    pending_patch = pending_patches.pop(step_result.step_id, None)
                    if pending_patch and "patch" not in step_result.metrics:
                        self._patch_runner.attach_patch_meta(
                            step_result,
                            pending_patch,
                        )
                    self._add_step_result(context, step_result)
                    self._ensure_step_workflow_action(context, step_result)
                    self._emit_step_event(context, step_result)
                    # 读取失败分类与可重试标记，供日志/上层使用（不改变控制流）
                    step_result.metrics.setdefault(
                        "failure_type", step_result.failure_type
                    )
                    step_result.metrics.setdefault(
                        "retryable",
                        is_retryable_failure(step_result.failure_type)
                        if step_result.failure_type is not None
                        else None,
                    )
                    if step_result.status == "failed":
                        if not has_recovery_upgrade(step_result):
                            blocked_by_safety = self._add_failed_step_safety_event(
                                step_result,
                                plan,
                                context,
                            )
                        failed_result = step_result

                if failed_result is not None:
                    workflow_action = self._extract_workflow_action(failed_result)
                    action_route = None
                    if workflow_action:
                        action_route = resolve_workflow_action_route(workflow_action)
                    failure_reason = "step_failed"
                    patch_meta = failed_result.metrics.get("patch")
                    recovery_meta = failed_result.metrics.get("recovery")
                    if isinstance(patch_meta, dict) and patch_meta.get("applied") is True:
                        failure_reason = "patch_failed"
                    elif failed_result.metrics.get("retry_exhausted"):
                        failure_reason = "retry_exhausted"
                    if isinstance(recovery_meta, dict):
                        upgrade_reason = recovery_meta.get("upgrade_reason")
                        if isinstance(upgrade_reason, str) and upgrade_reason:
                            failure_reason = upgrade_reason
                    request_failure_type = self._coerce_failure_type(
                        failed_result.failure_type
                    )
                    request_code = None
                    if blocked_by_safety or request_failure_type == FailureType.SAFETY_BLOCK:
                        failure_reason = "safety_block"
                        request_failure_type = FailureType.SAFETY_BLOCK
                        request_code = "SAFETY_POST_BLOCK"
                    elif action_route and action_route.action == "suffix_replan":
                        failure_reason = "suffix_replan_requested"
                        request_code = "SUFFIX_REPLAN_REQUESTED"
                    elif action_route and action_route.action == "stop":
                        self._request_stop(
                            context,
                            record,
                            failure_type=request_failure_type,
                            message=(
                                f"Adaptive selector requested stop after "
                                f"step {failed_result.step_id} failed"
                            ),
                            step_id=failed_result.step_id,
                            explanation=self._build_stop_explanation(failed_result),
                            failed_result=failed_result,
                        )
                    explanation = self._build_replan_explanation(
                        failure_reason,
                        failed_result,
                    )
                    self._request_replan(
                        context,
                        record,
                        reason=failure_reason,
                        failure_type=request_failure_type,
                        message=(
                            f"Step {failed_result.step_id} failed "
                            f"(failure_type={failed_result.failure_type}, "
                            f"error={failed_result.error_message})"
                        ),
                        step_id=failed_result.step_id,
                        explanation=explanation,
                        code=request_code,
                    )

                if (
                    context.status == InternalStatus.PATCHING
                    and self._has_patch_applied(outcome.step_results)
                ):
                    transition_task_status(
                        context,
                        record,
                        InternalStatus.RUNNING,
                        reason="patch_applied",
                    )

                # 成功或 patch 成功后推进下一步
                step_index = outcome.next_step_index

            # A4: 安全检查 - 最终结果阶段
            final_safety_result = self._safety_agent.check_final_result(
                context, context.design_result
            )
            self._add_safety_event(context, final_safety_result)
            if final_safety_result.action == "block":
                self._request_replan(
                    context,
                    record,
                    reason="safety_block",
                    failure_type=FailureType.SAFETY_BLOCK,
                    message="SafetyAgent blocked final result",
                    code="SAFETY_FINAL_BLOCK",
                    explanation=self._build_basic_replan_explanation(
                        "safety_block (final result blocked)"
                    ),
                )

            # A3: 执行完成后，推进 SUMMARIZING（必要时继续 DONE）
            if context.status == InternalStatus.RUNNING:
                transition_task_status(
                    context,
                    record,
                    InternalStatus.SUMMARIZING,
                    reason="plan_completed",
                )
                if finalize_status:
                    transition_task_status(
                        context,
                        record,
                        InternalStatus.DONE,
                        reason="summarizer_placeholder",
                    )

            # 返回原始 plan(为未来支持 Patch/Replan 预留接口)
            return plan
        except PlanRunError as exc:
            if (
                context.status == InternalStatus.WAITING_REPLAN
                and max_replans > 0
                and not should_require_replan_confirm(exc)
            ):
                replanned_plan = self._perform_replan(plan, context, record, exc)
                if context.status == InternalStatus.WAITING_REPLAN:
                    return replanned_plan
                return self.run_plan(
                    replanned_plan,
                    context,
                    record=record,
                    finalize_status=finalize_status,
                    max_replans=max_replans - 1,
                    resume_from_existing=True,
                )
            if not (
                context.status == InternalStatus.WAITING_REPLAN
                and should_require_replan_confirm(exc)
            ):
                self._mark_failed(context, record, reason="plan_error")
            raise
        except Exception:
            self._mark_failed(context, record, reason="unhandled_exception")
            raise

    def _validate_candidate_before_execution(
        self,
        plan: Plan,
        context: WorkflowContext,
    ) -> None:
        """执行前硬门禁：候选不可执行时直接阻断。"""
        constraints = context.task.constraints if isinstance(context.task.constraints, dict) else {}
        enforce_flag = constraints.get("enforce_candidate_validation")
        if isinstance(enforce_flag, bool):
            should_enforce = enforce_flag
        else:
            metadata = plan.metadata if isinstance(plan.metadata, dict) else {}
            should_enforce = "kg_explanation" in metadata
        if not should_enforce:
            return

        try:
            validate_plan_executability(plan, context.task)
        except CandidateExecutionValidationError as exc:
            first_issue = exc.issues[0] if exc.issues else None
            failure_code = (
                first_issue.code if first_issue is not None else "CANDIDATE_SCHEMA_INVALID"
            )
            write_event_log(
                make_candidate_validation_failed(
                    task_id=context.task.task_id,
                    failure_code=failure_code,
                    failures=[issue.as_dict() for issue in exc.issues],
                    actor_type=ActorType.WORKFLOW,
                    internal_status=context.status,
                    data={
                        "plan_task_id": plan.task_id,
                        "step_count": len(plan.steps),
                    },
                )
            )
            raise PlanRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"Candidate validation hard-failed before execution: {exc}",
                code=failure_code,
            ) from exc

    def _add_safety_event(self, context: WorkflowContext, event) -> None:
        """安全事件写入上下文，兼容两种 WorkflowContext 形态"""
        if hasattr(context, "add_safety_event"):
            context.add_safety_event(event)
        else:
            context.safety_events.append(event)

    def _add_step_result(self, context: WorkflowContext, result: StepResult) -> None:
        """步骤结果写入上下文，优先复用 WorkflowContext 辅助方法。"""
        if hasattr(context, "add_step_result"):
            context.add_step_result(result)
        else:
            context.step_results[result.step_id] = result

    def _mark_failed(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        *,
        reason: str,
    ) -> None:
        """将任务状态置为 FAILED（仅对非终态生效）"""
        if context.status in TERMINAL_INTERNAL_STATUSES:
            return
        transition_task_status(
            context,
            record,
            InternalStatus.FAILED,
            reason=reason,
        )

    def _emit_step_event(
        self,
        context: WorkflowContext,
        step_result: StepResult,
    ) -> None:
        event_name = "STEP_FINISHED" if step_result.status != "failed" else "STEP_FAILED"
        event_payload = {
            "event": event_name,
            "task_id": context.task.task_id,
            "step_id": step_result.step_id,
            "tool": step_result.tool,
            "status": step_result.status,
            "failure_type": step_result.failure_type,
            "error_message": step_result.error_message,
            "timestamp": step_result.timestamp,
            "state": context.status.value,
            "external_status": to_external_status(context.status).value,
        }
        event_data = build_step_trace_data(step_result)
        event_data.update(runtime_policy_trace(context.task))
        runtime_state_summary = build_context_runtime_state_summary(context)
        if runtime_state_summary is not None:
            event_data["runtime_state_summary"] = runtime_state_summary
        if event_data:
            event_payload["data"] = event_data
        append_event(
            context.task.task_id,
            event_payload,
        )


def _build_step_trace_data(step_result: StepResult) -> dict[str, Any]:
    return build_step_trace_data(step_result)
