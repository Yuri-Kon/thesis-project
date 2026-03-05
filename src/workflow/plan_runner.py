from __future__ import annotations
import json
from typing import Protocol
from src.agents.planner import PlannerAgent
from src.models.contracts import (
    PendingActionStatus,
    PendingActionType,
    Plan,
    ReplanRequest,
    StepResult,
    now_iso,
)
from src.models.db import TaskRecord, InternalStatus, TERMINAL_INTERNAL_STATUSES
from src.workflow.context import WorkflowContext
from src.workflow.step_runner import StepRunner
from src.workflow.patch_runner import PatchRunner, PendingPatch
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.agents.safety import SafetyAgent
from src.workflow.status import transition_task_status
from src.workflow.errors import (
    FailureType,
    PlanRunError,
    StepRunError,
    classify_exception,
    is_retryable_failure,
)


class StepRunnerLike(Protocol):
    """最小化约束的 StepRunner 接口，用于依赖注入和单元测试"""

    def run_step(self, step, context: WorkflowContext) -> StepResult:  # type: ignore
        """执行单个 PlanStep,返回 StepResult

        真实实现由 src/workflow/step_runner.StepRunner 提供
        """


class PlanRunner:
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
                    context.step_results[step_result.step_id] = step_result
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
                        blocked_by_safety = self._add_failed_step_safety_event(
                            step_result,
                            plan,
                            context,
                        )
                        failed_result = step_result

                if failed_result is not None:
                    failure_reason = "step_failed"
                    if failed_result.metrics.get("retry_exhausted"):
                        failure_reason = "retry_exhausted"
                    request_failure_type = self._coerce_failure_type(
                        failed_result.failure_type
                    )
                    request_code = None
                    if blocked_by_safety or request_failure_type == FailureType.SAFETY_BLOCK:
                        failure_reason = "safety_block"
                        request_failure_type = FailureType.SAFETY_BLOCK
                        request_code = "SAFETY_POST_BLOCK"
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
                and not _should_require_replan_confirm(exc)
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
                and _should_require_replan_confirm(exc)
            ):
                self._mark_failed(context, record, reason="plan_error")
            raise
        except Exception:
            self._mark_failed(context, record, reason="unhandled_exception")
            raise

    def _add_safety_event(self, context: WorkflowContext, event) -> None:
        """安全事件写入上下文，兼容两种 WorkflowContext 形态"""
        if hasattr(context, "add_safety_event"):
            context.add_safety_event(event)
        else:
            context.safety_events.append(event)

    def _add_failed_step_safety_event(
        self,
        step_result: StepResult,
        plan: Plan,
        context: WorkflowContext,
    ) -> bool:
        step = next((s for s in plan.steps if s.id == step_result.step_id), None)
        if step is None:
            return False
        safety_result = self._safety_agent.check_post_step(step, step_result, context)
        self._add_safety_event(context, safety_result)
        if safety_result.risk_flags:
            step_result.risk_flags = safety_result.risk_flags
        return safety_result.action == "block"

    def _build_replan_explanation(
        self,
        reason: str,
        failed_result: StepResult,
    ) -> str:
        failure_context = self._summarize_failure_result(failed_result)
        options = self._build_replan_options(failure_context.get("failure_code"))
        payload = {
            "reason": reason,
            "failure": failure_context,
            "options": options,
        }
        return (
            f"replan requested: {reason}; "
            f"context={json.dumps(payload, ensure_ascii=True)}"
        )

    def _build_basic_replan_explanation(self, reason: str) -> str:
        payload = {
            "reason": reason,
            "options": ["replan", "cancel"],
        }
        return (
            f"replan requested: {reason}; "
            f"context={json.dumps(payload, ensure_ascii=True)}"
        )

    def _build_replan_options(self, failure_code: object) -> list[str]:
        options = ["replan", "cancel"]
        if isinstance(failure_code, str) and failure_code.startswith("NIM_"):
            options.append("switch_to_local_esmfold")
        return options

    def _summarize_failure_result(self, result: StepResult) -> dict:
        failure_code = None
        failure_reason = result.error_message
        if result.risk_flags:
            failure_code = result.risk_flags[0].code
            if result.risk_flags[0].message:
                failure_reason = result.risk_flags[0].message
        if not failure_code and isinstance(result.error_details, dict):
            failure_code = result.error_details.get("failure_code")
        return {
            "step_id": result.step_id,
            "tool": result.tool,
            "failure_type": result.failure_type,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "risk_flags": [flag.model_dump() for flag in result.risk_flags],
        }

    def _coerce_failure_type(self, value) -> FailureType:
        """将 StepResult.failure_type 统一为 FailureType 枚举"""
        if isinstance(value, FailureType):
            return value
        if isinstance(value, str):
            try:
                return FailureType(value)
            except ValueError:
                pass
        return FailureType.NON_RETRYABLE

    def _should_skip_step(self, step, context: WorkflowContext) -> bool:
        """判断是否可跳过已成功且与当前计划一致的步骤"""
        result = context.step_results.get(step.id)
        if result is None:
            return False
        if result.status != "success":
            return False
        if result.tool != step.tool:
            return False
        return True

    def _has_patch_applied(self, step_results: list[StepResult]) -> bool:
        """判断当前批次结果中是否包含已应用的 patch"""
        for result in step_results:
            patch_meta = result.metrics.get("patch")
            if isinstance(patch_meta, dict) and patch_meta.get("applied") is True:
                return True
        return False

    def _request_replan(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
        *,
        reason: str,
        failure_type: FailureType,
        message: str,
        code: str | None = None,
        step_id: str | None = None,
        explanation: str | None = None,
    ) -> None:
        """触发 WAITING_REPLAN，并抛出 PlanRunError 交给上层处理"""
        if context.status != InternalStatus.WAITING_REPLAN:
            pending_action = build_pending_action(
                task_id=context.task.task_id,
                action_type=PendingActionType.REPLAN_CONFIRM,
                candidates=[],
                default_suggestion=None,
                explanation=explanation or f"replan requested: {reason}",
            )
            enter_waiting_state(
                context,
                record,
                pending_action,
                InternalStatus.WAITING_REPLAN,
                reason=reason,
            )
            transition_task_status(
                context,
                record,
                InternalStatus.WAITING_REPLAN,
                reason=reason,
            )
        raise PlanRunError(
            failure_type=failure_type,
            message=message,
            step_id=step_id,
            code=code,
        )

    def _perform_replan(
        self,
        plan: Plan,
        context: WorkflowContext,
        record: TaskRecord | None,
        error: PlanRunError,
    ) -> Plan:
        """执行最小再规划闭环：WAITING_REPLAN → REPLANNING → RUNNING"""
        transition_task_status(
            context,
            record,
            InternalStatus.REPLANNING,
            reason="replan_requested",
        )
        self._resolve_pending_replan_action(context, record)
        request = ReplanRequest(
            task_id=context.task.task_id,
            original_plan=plan,
            failed_steps=[error.step_id] if error.step_id else [],
            safety_events=list(context.safety_events),
            reason=str(error),
        )
        try:
            try:
                replan_top_k = self._planner.replan_top_k(
                    request,
                    k=_resolve_top_k(context.task.constraints.get("replan_top_k"), default=3),
                )
                gate = self._planner.evaluate_top_k_gate(
                    candidate_kind="replan",
                    top_k_result=replan_top_k,
                    task_constraints=context.task.constraints,
                )
                if gate.requires_hitl:
                    waiting_action = build_pending_action(
                        task_id=context.task.task_id,
                        action_type=PendingActionType.REPLAN_CONFIRM,
                        candidates=replan_top_k.candidates,
                        default_suggestion=replan_top_k.default_recommendation,
                        default_recommendation=replan_top_k.default_recommendation,
                        explanation=f"{replan_top_k.explanation} gate={gate.reason}",
                    )
                    enter_waiting_state(
                        context,
                        record,
                        waiting_action,
                        InternalStatus.WAITING_REPLAN,
                        reason=gate.reason,
                    )
                    transition_task_status(
                        context,
                        record,
                        InternalStatus.WAITING_REPLAN,
                        reason=gate.reason,
                    )
                    return plan

                selected = next(
                    (
                        candidate
                        for candidate in replan_top_k.candidates
                        if candidate.candidate_id == replan_top_k.default_recommendation
                    ),
                    replan_top_k.candidates[0] if replan_top_k.candidates else None,
                )
                if selected is None:
                    raise ValueError("replan_top_k returned empty candidates")
                payload = selected.structured_payload
                if not isinstance(payload, Plan):
                    raise ValueError("replan_top_k selected payload is not Plan")
                replanned_plan = payload
            except Exception:
                # 回退到旧 replan()，保持既有 Planner stub 兼容
                replanned_plan = self._planner.replan(request)
        except Exception as exc:
            transition_task_status(
                context,
                record,
                InternalStatus.FAILED,
                reason="replan_failed",
            )
            raise PlanRunError(
                failure_type=classify_exception(exc),
                message=f"Replan failed: {exc}",
                step_id=error.step_id,
                code="REPLAN_FAILED",
                cause=exc,
            ) from exc

        if replanned_plan.task_id != context.task.task_id:
            transition_task_status(
                context,
                record,
                InternalStatus.FAILED,
                reason="replan_failed",
            )
            raise PlanRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=(
                    "Replan produced plan with mismatched task_id: "
                    f"{replanned_plan.task_id} != {context.task.task_id}"
                ),
                step_id=error.step_id,
                code="REPLAN_TASK_MISMATCH",
            )

        context.plan = replanned_plan
        if record is not None:
            record.plan = replanned_plan

        transition_task_status(
            context,
            record,
            InternalStatus.RUNNING,
            reason="replan_succeeded",
        )
        return replanned_plan

    def _resolve_pending_replan_action(
        self,
        context: WorkflowContext,
        record: TaskRecord | None,
    ) -> None:
        action = context.pending_action
        if (
            action is None
            or action.action_type != PendingActionType.REPLAN_CONFIRM
            or action.status != PendingActionStatus.PENDING
        ):
            return
        action.status = PendingActionStatus.CANCELLED
        action.decided_at = now_iso()
        context.pending_action = action
        if record is not None:
            record.pending_action = action

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


def _should_require_replan_confirm(error: PlanRunError) -> bool:
    """SafetyAgent blocks must wait for HITL replan confirmation."""
    return (
        error.failure_type == FailureType.SAFETY_BLOCK
        or error.code in {"SAFETY_TASK_INPUT_BLOCK", "SAFETY_FINAL_BLOCK", "SAFETY_POST_BLOCK"}
    )


def _resolve_top_k(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return 1
    return parsed
