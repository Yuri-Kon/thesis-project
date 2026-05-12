# 第五章 系统实现

本章在第四章系统设计的基础上说明工程实现方式。本文不提出新的底层蛋白质生成模型，而是把已有工具组织为可执行、可恢复、可审计的智能工作流。因此，本章主要讨论任务接入、候选计划生成、HITL 确认、工具执行、运行时恢复和结果审计等机制如何落实到代码模块和接口中。

蛋白质设计相关能力主要通过 AlphaFold/OpenFold、ESMFold、ProteinMPNN、ProtGPT2、Biopython 等工具或工具适配器接入，这些工具本身已有成熟研究基础[2,4–6,10,18]。因此，实现工作的重点在于把这些异构能力组织为可追踪、可恢复、可解释的工作流。

## 5.1 技术选型与工程结构

系统后端采用 Python 3.12、FastAPI 和 Pydantic 实现。Python 与生物信息学脚本、结构处理库和模型服务生态兼容，适合封装本地脚本和远程 REST 服务；FastAPI 提供请求路由、响应模型和自动接口文档；Pydantic 用于定义任务、计划、步骤结果、待决策对象和运行时状态等数据契约。对于蛋白质设计工作流而言，输入字段缺失、工具输出格式不一致、步骤间引用错误都可能导致后续高代价计算失败，因此系统将结构化校验前移到 API 和模型边界。

前端采用 React、TypeScript 和 Vite 构建轻量 Web 工作台。它不单独保存业务状态，而是通过后端 API 读取任务记录、待决策对象、事件时间线和报告结果。这样处理可以减少前端界面与后端工作流状态分叉，使 Web 页面主要承担运行时状态展示和交互入口的作用。

工作流控制采用自定义 Workflow/FSM，而不是将全局控制流交给外部流程引擎。Nextflow 等科学工作流工具在可复现计算流程中具有代表性[11]，但本文系统需要在任务执行中显式处理 `WAITING_*` 状态、PendingAction、Decision、`RuntimeState` 和 TaskSnapshot。如果全局状态变化由外部流程引擎隐式管理，HITL 暂停、快照恢复和恢复候选审计就难以统一。因此，系统将外部工具和流程后端限定在单个 PlanStep 内，把多步编排、状态迁移和人工确认保留在自定义运行时中。

表 5-1 给出了后端核心模块与论文架构层之间的对应关系。该表说明系统实现并非简单的文件目录堆叠，而是围绕任务接入、数据契约、工作流控制、工具适配和审计恢复形成分层实现。

| 实现目录 | 主要职责 | 对应设计层/模块 | 说明 |
|:--:|:--:|:--:|:--:|
| src/api/ | FastAPI 入口、任务接口、HITL 接口、前端静态入口 | 输入交互层、任务接入模块 | API 是任务、事件、报告和人工决策的统一边界。 |
| src/models/ | Pydantic 契约、状态枚举、任务记录 | 核心数据契约 | 任务、计划、步骤结果、PendingAction、`RuntimeState` 等对象均受结构化约束。 |
| src/agents/ | Planner、Executor、Safety、Summarizer | 多 Agent 协作模块 | 各 Agent 只承担明确职责，不直接越权改变全局状态。 |
| src/workflow/ | WorkflowContext、PlanRunner、StepRunner、RuntimeEvaluator、恢复与快照 | 工作流控制层、CEBRA-WP 工程承载 | FSM、HITL、重试、恢复、runtime rerank 和快照的主要实现位置。 |
| src/adapters/ | ToolAdapter、AdapterRegistry、具体工具适配器 | 工具执行与资源接入层 | 屏蔽本地工具、远程 REST 服务和脚本差异。 |
| src/kg/ | ProteinToolKG JSON 与查询逻辑 | ProteinToolKG | 为候选生成提供工具能力、I/O、成本和安全约束。 |
| src/storage/ | 事件日志、快照、文件产物管理 | 审计与恢复支撑 | EventLog 和 TaskSnapshot 支撑恢复、复核和实验证据提取。 |

表 5-1 后端核心模块与论文架构层对应关系

## 5.2 任务接入与后端 API 实现

### 5.2.1 渐进式任务录入

蛋白质设计任务通常不能仅靠一句自然语言目标完整描述。用户可能输入“设计一个 30 残基的稳定短肽”，但长度范围、任务类型、结构模板、预算约束、安全限制和目标评分方式仍需要补充。为降低自由文本直接进入高代价执行的风险，系统实现了 Task Intake 链路，将任务录入拆分为草稿创建、字段补充、场景预检查和正式确认几个阶段。

后端提供 /task-intakes/schema、/task-intakes、/task-intakes/{id} 和 /task-intakes/{id}/confirm 等接口。字段注册表由后端返回，前端 Task Builder 再依据字段类型、必填状态和分组信息渲染表单。用户补充字段后，系统执行场景门控和安全预检查；只有经过确认的结构化任务规格，才会进入正式任务创建路径。

正式任务创建接口支持 goal、query 和 confirmed_task_spec 三种入口，但三者必须互斥。代码清单 5-1 展示了任务创建请求模型中的互斥校验。该校验用于保证任务来源清晰，避免自由文本、兼容入口和已确认结构化规格混杂进入同一个任务。

<table>
<caption><p>代码清单 5-1任务创建请求的互斥入口校验</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>class TaskCreateRequest(BaseModel):</p>
<p>goal: Optional[str] = Field(</p>
<p>None,</p>
<p>description="蛋白质设计任务目标(自然语言)",</p>
<p>)</p>
<p>query: Optional[str] = Field(</p>
<p>None,</p>
<p>description="兼容自由文本入口；会收敛为 intake",</p>
<p>)</p>
<p>confirmed_task_spec: Optional[ConfirmedTaskSpec] = Field(</p>
<p>None,</p>
<p>description="已经确认的结构化任务输入",</p>
<p>)</p>
<p>constraints: Dict[str, Any] = Field(</p>
<p>default_factory=dict,</p>
<p>description="结构化约束",</p>
<p>)</p>
<p>metadata: Dict[str, Any] = Field(default_factory=dict)</p>
<p>@model_validator(mode="after")</p>
<p>def _validate_creation_mode(self) -&gt; "TaskCreateRequest":</p>
<p>modes = [</p>
<p>self.goal is not None,</p>
<p>self.query is not None,</p>
<p>self.confirmed_task_spec is not None,</p>
<p>]</p>
<p>if not any(modes):</p>
<p>raise ValueError(</p>
<p>"one of goal, query, or confirmed_task_spec is required"</p>
<p>)</p>
<p>if sum(modes) &gt; 1:</p>
<p>raise ValueError(</p>
<p>"choose exactly one of goal, query, or confirmed_task_spec"</p>
<p>)</p>
<p>return self</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

代码清单 5-1 对应第四章中“任务输入需要结构化确认”的设计要求。该校验不直接提高蛋白质设计模型的能力，但可以避免任务入口语义不清导致后续计划生成和审计困难。

### 5.2.2 任务生命周期接口

正式任务创建后，系统通过任务生命周期接口暴露任务状态、事件和报告。GET /tasks/{task_id} 返回任务记录，包括外部状态、内部状态、任务目标、约束、计划、设计结果、待决策对象和安全事件。外部状态用于前端展示，例如 WAITING_PATCH_CONFIRM；内部状态保留执行细节，例如 `WAITING_PATCH` 或 PATCHING。双状态设计使 UI 保持简洁，同时保留恢复流程所需的精确状态。

GET /tasks/{task_id}/events 返回事件时间线。该接口直接读取事件日志，而不是只依赖内存任务表。因此，只要日志文件存在，服务重启后仍可还原任务的状态迁移、步骤执行、等待进入、决策应用和等待退出等事件。GET /tasks/{task_id}/report 返回最终报告摘要，包含序列、结构文件路径、评分、风险标记和目标评分结果；未完成任务请求报告时返回错误响应，避免把中间状态误认为最终结果。

### 5.2.3 HITL 接口

HITL 机制通过 PendingAction 和 Decision 建模。GET /pending-actions 返回待审查任务摘要，GET /pending-actions/{id} 返回候选详情，POST /pending-actions/{id}/decision 接收用户决策。候选详情中包含候选数量、默认建议、评分分解、运行时状态摘要、风险等级、成本估计和解释字段。前端因此可以展示“为什么推荐该候选”，而不是只提供一个缺少解释的确认按钮。

当用户提交 Decision 后，后端会验证 PendingAction 是否属于当前任务、是否仍处于待决策状态、所选候选是否存在。验证通过后，后端根据 action type 将决策应用到 plan、局部修补或重规划，并写入决策事件和等待退出事件。这一过程保证人工决策属于工作流状态，而不是前端临时 UI 状态。

## 5.3 前端工作台实现

前端工作台包含 Dashboard、Task Builder、Task Detail 和 Event Timeline 四类页面。Dashboard 展示任务列表、状态摘要和工具能力 readiness；Task Builder 负责任务录入、字段补充和确认；Task Detail 聚合任务状态、候选审查、报告与结构产物入口；Event Timeline 用于查看任务生命周期事件。

前端启动时从后端注入的 bootstrap payload 获取当前视图和任务 ID，再通过 API 拉取任务、待决策对象、事件和报告。这一实现方式使前端无需自行推导 FSM 状态，也也不会在页面刷新或任务切换时产生独立状态源。

在 Task Detail 页面中，PendingReviewWorkspace 是 HITL 的主要交互区域。当任务进入 `WAITING_*` 状态时，前端展示候选方案对比、评分分解、运行时上下文和决策表单。用户提交决策后，前端仅向后端发送结构化 Decision，具体的计划应用、状态迁移、快照写入和事件记录均由后端工作流模块完成。

当前前端的结构展示区域主要提供结构文件路径、报告浏览和可视化入口。并不具备提供完整的三维结构分析。

## 5.4 工作流运行时与执行引擎

系统运行时的核心执行序列见图 5-1。用户通过 API 创建任务后，Workflow 创建运行时上下文，Planner 根据任务目标和 ProteinToolKG 生成候选计划，Executor 在人工确认或自动选择后执行 PlanStep。执行过程中，StepRunner 通过 ToolAdapter 解析输入、执行工具、校验输出，并把 StepResult 写回上下文。Safety 模块在输入、步骤和输出阶段提供风险判定，Storage 模块负责事件日志、快照和产物写入。

【图 5-1 运行时执行序列】

图 5-1 重点说明 Planner 与 Executor 的边界：Planner 生成候选并查询工具知识，不直接执行工具；Executor 只执行已确认的 PlanStep，并通过 StepRunner 和 ToolAdapter 与外部工具交互。这样，候选生成、人工确认、工具执行和审计记录可以分别追踪。

### 5.4.1 WorkflowContext

WorkflowContext 是单个任务运行期间的上下文对象，保存任务、当前计划、步骤结果、安全事件、`RuntimeState`、最终结果和 PendingAction。运行时状态更新不由各模块分散修改，而是通过上下文提供的统一入口触发。代码清单 5-2 展示了 StepResult 和 SafetyResult 写入时如何触发 `RuntimeState` 更新。

<table>
<caption><p>代码清单 5-2 WorkflowContext 中的 `RuntimeState` 更新入口</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>def add_step_result(self, result: StepResult) -&gt; None:</p>
<p>self.step_results[result.step_id] = result</p>
<p>if not runtime_policy_uses_belief_state(self.task):</p>
<p>return</p>
<p>self.apply_runtime_state_update(</p>
<p>step_result=result,</p>
<p>failure_context=extract_failure_context(result),</p>
<p>)</p>
<p>def add_safety_event(self, event: SafetyResult) -&gt; None:</p>
<p>self.safety_events.append(event)</p>
<p>if not runtime_policy_uses_belief_state(self.task):</p>
<p>return</p>
<p>self.apply_runtime_state_update(safety_result=event)</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

该实现对应第四章中 Lite belief-state / 轻量信念状态的设计。系统只有在任务启用相关 runtime policy 时才更新 `RuntimeState`，从而支持 static、dynamic 和 lite belief-state 等策略在同一代码基中切换。

### 5.4.2 PlanRunner 与 StepRunner

PlanRunner 负责计划级执行和 FSM 状态推进。它在计划开始执行前检查任务和计划的一致性，进入运行状态后按顺序执行 PlanStep。若执行过程中出现可修复失败，PlanRunner 会请求局部修补候选并进入 WAITING_PATCH_CONFIRM；若出现结构性失败或安全阻断，则请求后缀重规划候选并进入 WAITING_REPLAN_CONFIRM。PlanRunner 可以推进合法状态迁移，但不会绕过 PendingAction 自动应用需要人工确认的候选。

StepRunner 是单步执行的最小单元。它负责有界重试、安全检查、工具适配、输入解析、工具调用、输出校验和错误归一化。代码清单 5-3 展示了 StepRunner 的有界重试微循环。该循环只对可重试失败进行重试；当失败不可重试或重试耗尽时，StepRunner 返回结构化 StepResult，由上层恢复逻辑决定是否进入 `patch_local`、`suffix_replan` 或 stop。

<table>
<caption><p>代码清单 5-3 StepRunner 的有界重试微循环</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>def run_step(self, step: PlanStep, context: WorkflowContext) -&gt; StepResult:</p>
<p>"""执行单个 PlanStep（带静态重试），返回最终 StepResult"""</p>
<p>last_result: StepResult | None = None</p>
<p>attempt_logs: list[AttemptRecord] = []</p>
<p>retried_any = False</p>
<p>for attempt_idx in range(1, self._retry_policy.max_attempts + 1):</p>
<p>result = self._run_once(step, context)</p>
<p>self._annotate_attempt_meta(result, attempt_idx)</p>
<p>attempt_logs.append(self._build_attempt_record(result, attempt_idx))</p>
<p>last_result = result</p>
<p>if result.status == "success":</p>
<p>return self._finalize_success(result, attempt_logs)</p>
<p>failure_type = self._normalize_failure_type(result.failure_type)</p>
<p>retried_any = retried_any or attempt_idx &gt; 1</p>
<p>exhausted = attempt_idx &gt;= self._retry_policy.max_attempts</p>
<p>if failure_type is None or not is_retryable_failure(failure_type):</p>
<p>return self._finalize_failure(result, attempt_logs, retried_any, exhausted)</p>
<p>if exhausted:</p>
<p>return self._finalize_failure(result, attempt_logs, retried_any, True)</p>
<p>backoff_ms = self._retry_policy.backoff_ms_for(attempt_idx)</p>
<p>if backoff_ms &gt; 0:</p>
<p>self._sleep_fn(backoff_ms / 1000)</p>
<p>return self._finalize_failure(last_result, attempt_logs, retried_any, True)</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

该实现使工具异常不会直接扩散到上层模块。无论底层问题来自本地脚本失败、远程服务超时，还是输出字段缺失，PlanRunner 和 CEBRA-WP 接收到的都是统一的 failure_type、attempt history 和错误详情。

### 5.4.3 等待状态、审计与快照

恢复闭环的关键，是在进入等待状态前先固化待决策对象和审计信息。代码清单 5-4 展示了 enter_waiting_state 的核心逻辑：状态迁移前，系统会先校验等待状态与 PendingAction 是否匹配，再写入 context、TaskRecord 和事件日志。这样即使系统在等待人工确认期间中断，恢复后也能还原当前待决策对象、候选集合和默认建议。

<table>
<caption><p>代码清单 5-4进入 WAITING 状态前写入 PendingAction 与审计信息</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>def enter_waiting_state(</p>
<p>context: WorkflowContext,</p>
<p>record: TaskRecord | None,</p>
<p>pending_action: PendingAction,</p>
<p>to_status: InternalStatus,</p>
<p>*,</p>
<p>reason: Optional[str] = None,</p>
<p>event_logger: EventLogger | None = None,</p>
<p>snapshot_writer: SnapshotWriter | None = None,</p>
<p>) -&gt; None:</p>
<p>_validate_waiting_transition(context, pending_action, to_status, record)</p>
<p>prev_status = to_external_status(context.status)</p>
<p>new_status = _to_external_waiting_status(to_status)</p>
<p>context.pending_action = pending_action</p>
<p>if record is not None:</p>
<p>record.pending_action = pending_action</p>
<p>log_handler = event_logger or _default_event_logger</p>
<p>log_handler(</p>
<p>{</p>
<p>"event": "PENDING_ACTION_CREATED",</p>
<p>"task_id": context.task.task_id,</p>
<p>"pending_action_id": pending_action.pending_action_id,</p>
<p>"action_type": pending_action.action_type.value,</p>
<p>"candidate_ids": [c.candidate_id for c in pending_action.candidates],</p>
<p>"default_suggestion": pending_action.default_suggestion,</p>
<p>"default_recommendation": pending_action.default_recommendation,</p>
<p>}</p>
<p>)</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

该代码清单说明，HITL 在系统中被实现为受控运行时状态，而不是前端组件上的临时按钮。PendingAction、Decision、EventLog 和 TaskSnapshot 共同构成了能够恢复、可复核的 HITL 机制。

## 5.5 CEBRA-WP 的工程落点

CEBRA-WP 在工程实现中不是一个单独的 Agent，而是分布在候选生成、`RuntimeState` 更新、候选重排、恢复动作映射和候选解释几个环节。Planner 生成候选及其静态评分，WorkflowContext 维护 `RuntimeState`，RuntimeEvaluator 计算 runtime adjustment 和 action utility，PlanRunner 则将动作建议映射为 continue、`patch_local`、`suffix_replan` 或 `terminal_stop` 等工作流行为。

代码清单 5-5 展示了 RuntimeEvaluator 对候选进行运行时评估和重排的入口。策略模式禁用重排时，系统返回静态默认候选；缺少 `RuntimeState` 时，仅执行 passthrough；当 Lite belief-state / 轻量信念状态可用时，系统根据 `RuntimeState` 计算 runtime adjustment，并按 final score 重新排序。

<table>
<caption><p>代码清单 5-5 RuntimeEvaluator 候选重排</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>def evaluate_candidates(</p>
<p>self,</p>
<p>candidates: list[PendingActionCandidate],</p>
<p>runtime_state: RuntimeStateSchema | Mapping[str, object] | None,</p>
<p>) -&gt; RuntimeEvaluation:</p>
<p>"""对每个候选计算 runtime_adjustment 与 final_score，按 final_score 降序重排。"""</p>
<p>if not candidates:</p>
<p>return RuntimeEvaluation(policy_mode=self._policy_mode)</p>
<p>state = _coerce_state(runtime_state)</p>
<p>static_default = _top_static_candidate(candidates)</p>
<p>if policy_disables_rerank(self._policy_mode):</p>
<p>return RuntimeEvaluation(</p>
<p>candidates=list(candidates),</p>
<p>static_default_id=static_default,</p>
<p>reranked_default_id=static_default,</p>
<p>rerank_applied=False,</p>
<p>policy_mode=self._policy_mode,</p>
<p>)</p>
<p>if state is None:</p>
<p>reranked = [_apply_passthrough(c) for c in candidates]</p>
<p>reranked.sort(key=_final_score_key, reverse=True)</p>
<p>top = reranked[0].candidate_id if reranked else None</p>
<p>return RuntimeEvaluation(</p>
<p>candidates=reranked,</p>
<p>static_default_id=static_default,</p>
<p>reranked_default_id=top,</p>
<p>rerank_applied=False,</p>
<p>policy_mode=self._policy_mode,</p>
<p>)</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

该实现对应第四章中 CEBRA-WP 的运行时重排序环节。需要强调的是，RuntimeEvaluator 只在已满足硬可行性约束的候选之间调整排序，不绕过工具存在性、schema、I/O、安全和预算硬约束。

图 5-2 从泳道视角展示各模块协作关系。科研人员通过 Web UI 创建任务并提交决策，Task API 负责请求与响应边界，Planner 生成候选，Executor 调度 StepRunner 和 ToolAdapter，Safety 提供风险信号，Storage 固化事件和快照。CEBRA-WP 贯穿其中：候选生成后参与重排，失败或风险出现时参与恢复动作选择，并通过 PendingAction 把解释信息呈现给人工决策者。

【图 5-2 工作流泳道式模块协作】

图 5-2 说明了控制面和执行面的分离。CEBRA-WP 影响候选排序和恢复动作，但实际状态迁移由 Workflow/FSM 执行；工具调用仍由 Executor 和 ToolAdapter 完成；人工确认仍通过 PendingAction/Decision 进入系统。

## 5.6 工具适配器与能力管理

上述运行时决策最终需要落到具体工具调用，因此还需说明工具适配层如何为 Executor 提供统一边界。

蛋白质设计工具链具有明显异构性：有的工具是本地 Python 脚本，有的工具依赖命令行环境，有的工具通过远程 REST 服务提供能力。为了避免 Executor 绑定具体工具实现，系统通过 BaseToolAdapter 定义统一工具接口。代码清单 5-6 展示了适配器抽象基类的核心方法。

<table>
<caption><p>代码清单 5-6 ToolAdapter 抽象接口</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>class BaseToolAdapter(ABC):</p>
<p>"""ToolAdapter 抽象基类，统一工具调用入口"""</p>
<p>tool_id: str</p>
<p>adapter_id: str | None = None</p>
<p>@abstractmethod</p>
<p>def resolve_inputs(</p>
<p>self, step: PlanStep, context: WorkflowContext</p>
<p>) -&gt; Dict[str, Any]:</p>
<p>"""将 PlanStep.inputs 解析为工具实际输入"""</p>
<p>@abstractmethod</p>
<p>def run_local(</p>
<p>self, inputs: Dict[str, Any]</p>
<p>) -&gt; Tuple[Dict[str, Any], Dict[str, Any]]:</p>
<p>"""本地执行工具并返回 (outputs, metrics)"""</p>
<p>def run_remote(</p>
<p>self,</p>
<p>inputs: Dict[str, Any],</p>
<p>output_dir: Optional[Path] = None,</p>
<p>) -&gt; Tuple[Dict[str, Any], Dict[str, Any]]:</p>
<p>raise NotImplementedError(</p>
<p>f"{self.__class__.__name__} does not support remote execution"</p>
<p>)</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

该接口将输入解析、执行模式和输出指标统一到同一抽象层。对于 Executor 而言，不同工具都表现为“接收结构化输入，返回 outputs 和 metrics”的适配器。具体工具内部是调用 Biopython、远程 OpenFold 服务还是序列生成模型，对上层工作流保持透明。

AdapterRegistry 维护 tool_id 到适配器实例的映射。StepRunner 执行某个 PlanStep 时，先通过 tool_id 找到适配器，再调用 resolve_inputs 解析常量输入和上游步骤引用。若工具未注册、上游引用缺失或输出类型不匹配，系统返回结构化失败，不会静默跳过或继续执行。

ProteinToolKG 以 JSON 形式保存工具能力、输入输出、兼容关系、成本、安全级别和版本信息。Planner 在候选生成时查询 ProteinToolKG，根据任务所需能力组合工具链，过滤不可用工具、预算超限工具或 I/O 闭包不成立的候选。这一实现使新增工具主要通过更新 ProteinToolKG 和注册适配器完成，而不需要修改 Planner 的核心流程。

## 5.7 本章小结

本章从工程角度说明了系统实现方式。系统后端以 Python、FastAPI 和 Pydantic 为基础，前端以 React、TypeScript 和 Vite 构建工作台；工作流控制采用自定义 Workflow/FSM，使 HITL、快照恢复和事件审计保持显式可控。

任务接入方面，系统通过 Task Intake 和互斥任务创建入口将自然语言目标逐步收敛为结构化任务。运行时方面，WorkflowContext、PlanRunner 和 StepRunner 分别承担上下文管理、计划级状态推进和步骤级工具执行。恢复方面，PendingAction、Decision、EventLog 和 TaskSnapshot 共同保证等待状态能够审计、能够恢复。算法落地方面，CEBRA-WP 通过 RuntimeEvaluator、`RuntimeState` 更新和恢复动作映射参与候选重排和运行时决策。工具接入方面，ToolAdapter 和 ProteinToolKG 将异构蛋白质设计工具封装为统一能力。

本章上述实现模块，是第六章测试与验证的对象基础。第六章将围绕 API 合约、FSM/HITL、快照恢复、前端与 CLI 可用性，以及 retry、局部修补、后缀重规划和安全边界展开验证。
