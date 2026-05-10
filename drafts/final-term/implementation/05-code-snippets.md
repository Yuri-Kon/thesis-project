# 论文可用代码片段

以下片段来自当前 `../thesis-project.dev/` 实现。论文中不宜大段铺代码，建议每节选 1 个短片段，并配合文字说明其设计意图。

## 终稿推荐使用方式

本文件是“代码片段素材库”，不是正文代码清单的直接拼接稿。进入终稿时建议只选 4 至 6 个片段，且每个片段控制在 15 至 30 行左右。每个代码清单都需要包含三部分说明：该片段解决的实现问题、对应第 4 章的设计点、以及它与测试/实验章节中证据的关系。

推荐优先级如下：

| 推荐编号 | 正文编号建议 | 片段 | 当前源码位置 | 推荐理由 | 正文位置 |
|---|---|---|---|---|---|
| S1 | 代码清单 5-1 | 任务创建请求的互斥入口校验 | `../thesis-project.dev/src/api/main.py:166` | 体现 API 边界和任务入口契约，适合连接 Task Intake 与数据校验。 | 5.2 |
| S2 | 代码清单 5-2 | ToolAdapter 抽象接口 | `../thesis-project.dev/src/adapters/base_tool_adapter.py:14` | 体现异构蛋白质工具统一接入边界，是系统实现章的关键工程证据。 | 5.6 |
| S3 | 代码清单 5-3 | WorkflowContext 写入 StepResult 并触发 RuntimeState 更新 | `../thesis-project.dev/src/workflow/context.py:90` | 体现运行时状态集中更新，连接 CEBRA-WP 的 belief-state 设计。 | 5.4 |
| S4 | 代码清单 5-4 | StepRunner 有界重试微循环 | `../thesis-project.dev/src/workflow/step_runner.py:140` | 体现 retry、failure_type 与上层 patch/replan 的边界。 | 5.4 |
| S5 | 代码清单 5-5 | RuntimeEvaluator 候选重排 | `../thesis-project.dev/src/workflow/runtime_evaluator.py:331` | 体现 CEBRA-WP 在工程中的核心落点，必须优先保留。 | 5.5 |
| S6 | 代码清单 5-6 | 进入 WAITING 状态前写入 PendingAction 与审计信息 | `../thesis-project.dev/src/workflow/pending_action.py:101` | 体现 HITL 不是 UI 临时状态，而是可恢复、可审计的工作流状态。 | 5.4/5.5 |
| S7 | 备选 | 构建任务快照 | `../thesis-project.dev/src/workflow/snapshots.py:34` | 可作为恢复与审计的补充代码清单，正文篇幅不足时放附录。 | 5.4 或附录 |

不建议正文优先展示前端 JSX 片段。前端可以通过页面结构说明、截图证据和 API 状态加载流程来证明；代码清单应优先服务系统契约、工作流控制和 CEBRA-WP 落地。

## 片段 1：任务创建请求的互斥入口校验

来源：`../thesis-project.dev/src/api/main.py:166`

```python
class TaskCreateRequest(BaseModel):
    goal: Optional[str] = Field(None, description="蛋白质设计任务目标(自然语言)")
    query: Optional[str] = Field(None, description="兼容自由文本入口；会收敛为 intake")
    confirmed_task_spec: Optional[ConfirmedTaskSpec] = Field(
        None,
        description="已经确认的结构化任务输入",
    )
    constraints: Dict[str, Any] = Field(default_factory=dict, description="结构化约束")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_creation_mode(self) -> "TaskCreateRequest":
        modes = [
            self.goal is not None,
            self.query is not None,
            self.confirmed_task_spec is not None,
        ]
        if not any(modes):
            raise ValueError("one of goal, query, or confirmed_task_spec is required")
        if sum(modes) > 1:
            raise ValueError("choose exactly one of goal, query, or confirmed_task_spec")
        return self
```

可写说明：该片段体现了 API 边界对任务创建模式的约束，防止自然语言输入、兼容输入和已确认任务规格混用，保证任务接入路径可追溯。

## 片段 2：PendingAction 摘要接口

来源：`../thesis-project.dev/src/api/main.py:1723`

```python
@app.get("/pending-actions", response_model=list[PendingActionSummary])
async def list_pending_actions(
    status: Optional[PendingActionStatus] = Query(
        default=PendingActionStatus.PENDING
    ),
    task_id: Optional[str] = Query(default=None),
) -> list[PendingActionSummary]:
    summaries: list[PendingActionSummary] = []

    for record in TASK_STORE.values():
        if task_id is not None and record.id != task_id:
            continue
        pending_action = record.pending_action
        if pending_action is None:
            continue
        if status is not None and pending_action.status != status:
            continue
        summaries.append(
            PendingActionSummary(
                pending_action_id=pending_action.pending_action_id,
                task_id=record.id,
                action_type=pending_action.action_type,
                status=pending_action.status,
                created_at=pending_action.created_at,
                candidate_count=len(pending_action.candidates),
                default_suggestion=(
                    pending_action.default_suggestion
                    or pending_action.default_recommendation
                ),
                explanation=pending_action.explanation,
                summary=_build_pending_action_summary(pending_action),
            )
        )
    return summaries
```

可写说明：该接口把所有处于等待状态的任务抽象为待审查队列，前端 Dashboard 不需要理解 FSM 内部细节，只消费 PendingAction 摘要。

## 片段 3：WorkflowContext 统一写入步骤结果并触发 RuntimeState 更新

来源：`../thesis-project.dev/src/workflow/context.py:90`

```python
class WorkflowContext(BaseModel):
    task: ProteinDesignTask
    plan: Optional[Plan] = None
    step_results: Dict[str, StepResult] = Field(default_factory=dict)
    safety_events: List[SafetyResult] = Field(default_factory=list)
    runtime_state: Optional[RuntimeState] = None
    design_result: Optional[DesignResult] = None
    pending_action: Optional[PendingAction] = None
    status: InternalStatus = InternalStatus.CREATED

    def add_step_result(self, result: StepResult) -> None:
        self.step_results[result.step_id] = result
        if not runtime_policy_uses_belief_state(self.task):
            return
        self.apply_runtime_state_update(
            step_result=result,
            failure_context=extract_failure_context(result),
        )

    def add_safety_event(self, event: SafetyResult) -> None:
        self.safety_events.append(event)
        if not runtime_policy_uses_belief_state(self.task):
            return
        self.apply_runtime_state_update(safety_result=event)
```

可写说明：WorkflowContext 既是执行上下文，也是 RuntimeState 的统一更新入口，避免各模块直接修改 belief-state。

## 片段 4：StepRunner 的重试微循环

来源：`../thesis-project.dev/src/workflow/step_runner.py:140`

```python
def run_step(self, step: PlanStep, context: WorkflowContext) -> StepResult:
    """执行单个 PlanStep（带静态重试），返回最终 StepResult"""
    last_result: StepResult | None = None
    attempt_logs: list[AttemptRecord] = []
    retried_any = False

    for attempt_idx in range(1, self._retry_policy.max_attempts + 1):
        result = self._run_once(step, context)
        self._annotate_attempt_meta(result, attempt_idx)
        attempt_logs.append(self._build_attempt_record(result, attempt_idx))
        last_result = result

        if result.status == "success":
            return self._finalize_success(result, attempt_logs)

        failure_type = self._normalize_failure_type(result.failure_type)
        retried_any = retried_any or attempt_idx > 1
        exhausted = attempt_idx >= self._retry_policy.max_attempts
        if failure_type is None or not is_retryable_failure(failure_type):
            return self._finalize_failure(result, attempt_logs, retried_any, exhausted)
        if exhausted:
            return self._finalize_failure(result, attempt_logs, retried_any, True)

        backoff_ms = self._retry_policy.backoff_ms_for(attempt_idx)
        if backoff_ms > 0:
            self._sleep_fn(backoff_ms / 1000)

    return self._finalize_failure(last_result, attempt_logs, retried_any, True)
```

可写说明：该片段展示了步骤级重试与失败分类的分离。重试只处理可重试失败，耗尽后将结构化 StepResult 交给上层 patch/replan 逻辑。

## 片段 5：ToolAdapter 抽象接口

来源：`../thesis-project.dev/src/adapters/base_tool_adapter.py:14`

```python
class BaseToolAdapter(ABC):
    """ToolAdapter 抽象基类，统一工具调用入口"""

    tool_id: str
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
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support remote execution"
        )
```

可写说明：该接口将输入解析、执行和输出指标统一化，使 Executor 可以调度不同工具而不绑定工具实现细节。

## 片段 6：RuntimeEvaluator 候选重排

来源：`../thesis-project.dev/src/workflow/runtime_evaluator.py:331`

```python
def evaluate_candidates(
    self,
    candidates: list[PendingActionCandidate],
    runtime_state: RuntimeStateSchema | Mapping[str, object] | None,
) -> RuntimeEvaluation:
    """对每个候选计算 runtime_adjustment 与 final_score，按 final_score 降序重排。"""
    if not candidates:
        return RuntimeEvaluation(policy_mode=self._policy_mode)

    state = _coerce_state(runtime_state)
    static_default = _top_static_candidate(candidates)

    if policy_disables_rerank(self._policy_mode):
        return RuntimeEvaluation(
            candidates=list(candidates),
            static_default_id=static_default,
            reranked_default_id=static_default,
            rerank_applied=False,
            policy_mode=self._policy_mode,
        )

    if state is None:
        reranked = [_apply_passthrough(c) for c in candidates]
        reranked.sort(key=_final_score_key, reverse=True)
        top = reranked[0].candidate_id if reranked else None
        return RuntimeEvaluation(
            candidates=reranked,
            static_default_id=static_default,
            reranked_default_id=top,
            rerank_applied=False,
            policy_mode=self._policy_mode,
        )

    observation_only = self._policy_mode == DYNAMIC_OBSERVATION_ONLY
    reranked = [
        _apply_runtime_adjustment(c, state, observation_only=observation_only)
        for c in candidates
    ]
    reranked.sort(key=_final_score_key, reverse=True)
```

可写说明：该片段对应 CEBRA-WP 在实现层的候选重排序机制，能够区分静态基线和 Lite belief-state 策略。

## 片段 7：进入 WAITING 状态前写入 PendingAction 与审计信息

来源：`../thesis-project.dev/src/workflow/pending_action.py:101`

```python
def enter_waiting_state(
    context: WorkflowContext,
    record: TaskRecord | None,
    pending_action: PendingAction,
    to_status: InternalStatus,
    *,
    reason: Optional[str] = None,
    event_logger: EventLogger | None = None,
    snapshot_writer: SnapshotWriter | None = None,
) -> None:
    _validate_waiting_transition(context, pending_action, to_status, record)

    prev_status = to_external_status(context.status)
    new_status = _to_external_waiting_status(to_status)

    context.pending_action = pending_action
    if record is not None:
        record.pending_action = pending_action

    log_handler = event_logger or _default_event_logger
    log_handler(
        {
            "event": "PENDING_ACTION_CREATED",
            "task_id": context.task.task_id,
            "pending_action_id": pending_action.pending_action_id,
            "action_type": pending_action.action_type.value,
            "candidate_ids": [c.candidate_id for c in pending_action.candidates],
            "default_suggestion": pending_action.default_suggestion,
            "default_recommendation": pending_action.default_recommendation,
        }
    )
```

可写说明：进入等待状态前先固化 PendingAction 与审计信息，保证人工确认不是临时 UI 状态，而是可恢复的工作流状态。

## 片段 8：前端工作台统一加载后端状态

来源：`../thesis-project.dev/src/api/frontend/src/main.tsx:63`

```tsx
const loadWorkspace = useCallback(
  async (nextTaskId = taskId) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const [pendingActions, readiness] = await Promise.all([
        apiClient.listPendingActions(),
        apiClient.getCapabilityReadiness(),
      ]);
      let task: TaskRecord | null = null;
      let pendingActionDetail: PendingActionDetail | null = null;
      let events: TaskTimelineEvent[] = [];
      let report: TaskReportDetail | null = null;

      if (nextTaskId) {
        task = await apiClient.getTask(nextTaskId);
        events = await apiClient.getTaskEvents(nextTaskId);
        if (task.pending_action?.pending_action_id) {
          pendingActionDetail = await apiClient.getPendingAction(task.pending_action.pending_action_id);
        }
        try {
          report = await apiClient.getTaskReport(nextTaskId);
        } catch {
          report = null;
        }
      }
```

可写说明：前端统一从后端 API 读取任务、候选、事件和报告，使 UI 成为工作流状态的展示层，而不是新的状态源。

## 片段 9：Pending Review 工作区展示运行时上下文

来源：`../thesis-project.dev/src/api/frontend/src/components/PendingReviewWorkspace.tsx:11`

```tsx
export function PendingReviewWorkspace({ detail, onDecisionSubmitted }: PendingReviewWorkspaceProps) {
  return (
    <section className="workspace-band review-workspace">
      <div className="review-main">
        <section className="panel review-context">
          <div className="panel-header">
            <h2>Runtime Context</h2>
            <span className="counter">{detail?.action_type ?? "idle"}</span>
          </div>
          {detail ? (
            <dl className="kv">
              <dt>Default</dt>
              <dd>{detail.default_suggestion ?? "none"}</dd>
              <dt>Reason</dt>
              <dd>{detail.workflow_action_reason ?? detail.explanation}</dd>
              <dt>Runtime state</dt>
              <dd><JsonDisclosure title="Runtime JSON" value={detail.runtime_state_summary} /></dd>
              <dt>Score</dt>
              <dd><JsonDisclosure title="Score JSON" value={detail.score_breakdown} /></dd>
            </dl>
          ) : null}
        </section>
        <CandidateComparison detail={detail} />
      </div>
      <DecisionForm detail={detail} onSubmitted={onDecisionSubmitted} />
    </section>
  );
}
```

可写说明：该组件把候选解释、运行时状态、候选对比和决策提交放在同一工作区，体现 HITL 与 CEBRA-WP 解释信息的结合。

## 片段 10：构建任务快照

来源：`../thesis-project.dev/src/workflow/snapshots.py:34`

```python
def build_task_snapshot(
    context: WorkflowContext,
    *,
    state_override: Optional[ExternalStatus] = None,
    pending_action_id: Optional[str] = None,
    artifacts: Optional[dict] = None,
    require_runtime_state: bool = False,
) -> TaskSnapshot:
    external_state = state_override or to_external_status(context.status)
    step_ids = list(context.step_results.keys())
    artifacts_payload = dict(artifacts or {})
    runtime_state = _resolve_runtime_state_for_snapshot(
        context,
        external_state=external_state,
        require_runtime_state=require_runtime_state,
    )
    _inject_runtime_state_artifacts(runtime_state, artifacts_payload)
    _inject_pending_action_audit_artifacts(context, artifacts_payload)
    if context.pending_action is not None:
        artifacts_payload.setdefault(
            "pending_action", context.pending_action.model_dump()
        )
    return TaskSnapshot(
        snapshot_id=f"snapshot_{uuid4().hex[:8]}",
        task_id=context.task.task_id,
        state=external_state.value,
        plan_version=_extract_plan_version(context),
        step_index=len(step_ids),
        current_step_index=len(step_ids),
        completed_step_ids=step_ids,
        artifacts=artifacts_payload,
        pending_action_id=pending_action_id,
        created_at=now_iso(),
    )
```

可写说明：快照将状态、步骤进度、runtime state 和 pending action 一并固化，是系统支持恢复与审计的关键实现。
