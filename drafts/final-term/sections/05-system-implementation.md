# 第五章：系统实现（草稿）

> 状态：初稿 · 2026-05-11 · 目标章节文件 `chapters/05-system-implementation.tex`
> 素材来源：`drafts/final-term/implementation/`（01-06）

---

## 5.1 技术选型与工程结构

系统的工程实现围绕第 4 章定义的五层架构展开，技术选型遵循三个原则：与生物信息学工具生态兼容、支持结构化契约校验、保持控制流的显式可审计性。

后端使用 **Python 3.12** 作为主语言，**FastAPI 0.128** 构建 Web API 层，**Pydantic 2.12** 定义全部数据契约。Python 的选择使其能直接调用生物信息学工具脚本、封装远程模型 REST 服务，并通过 `uv` 管理依赖和虚拟环境。FastAPI 提供了异步接口、自动 OpenAPI 文档和请求/响应模型校验，适合作为任务创建、HITL 决策和事件查询的 API 边界。Pydantic 将任务（ProteinDesignTask）、计划（Plan/PlanStep）、步骤结果（StepResult）、待决策对象（PendingAction）、人工决策（Decision）、运行时状态（RuntimeState）和设计结果（DesignResult）全部建模为类型安全的结构化对象——任何字段缺失或类型不匹配在 API 边界即被拦截，不会进入工作流引擎。

前端使用 **React 19 + TypeScript 5.9 + Vite 7** 构建轻量工作台。TypeScript 的类型定义与后端 Pydantic 模型对齐，编辑器中的字段提示和构建阶段的类型检查减少了前后端契约漂移。Vite 提供了快速的开发服务器和产物构建，前端编译后的静态文件（`app.js`、`style.css`）由 FastAPI 直接托管，无需独立前端部署。

工作流控制采用**自定义 Workflow/FSM** 而非外部流程引擎。这一决策的原因在设计与实现阶段反复确认：系统的控制语义强依赖 `WAITING_* → PendingAction → Decision → FSM Transition` 的闭环，如果将该闭环交给 LangGraph 或 Nextflow 等外部引擎，人工确认的暂停语义和快照恢复的审计链路将更加脆弱。当前实现将外部流程引擎严格限定在单步执行后端的角色——Nextflow 的单次 run 对应单个 PlanStep（blocking），多步编排、状态决策和人工确认始终由系统的 Workflow/FSM 拥有。`AGENT_CONTRACT.md` 将此写为系统不变性："State mutation is owned by workflow control logic only"。

工具接入通过 **ToolAdapter + AdapterRegistry** 实现。AbstractBaseToolAdapter 定义了 `resolve_inputs`、`run_local`、`run_remote`、`healthcheck`、`normalize_error` 和 `estimate_cost` 六个标准方法。AdapterRegistry 维护 tool_id 到适配器实例的映射，Executor 只依赖注册表接口，不感知具体工具的命令行、容器或远程调用细节。当前实现覆盖了 ESMFold、OpenFold、ProteinMPNN、ProtGPT2、RDKitProps、DSSP、Foldseek、BLASTP、MMseqs2 和 Objective Ranker 等蛋白质设计核心工具的适配器。

存储与审计采用**本地文件系统**方案。事件日志和任务快照以 JSONL 格式写入 `data/logs/` 和 `data/snapshots/`，产物（结构文件、报告、指标）写入 `output/`。原型阶段的任务记录使用内存 `TASK_STORE` 字典保存，配合日志和快照保留审计链路。这一方案在原型和实验阶段便于快速检查事件链条和恢复上下文；论文将其表述为"原型实现"，生产化持久化（数据库或对象存储）属于后续扩展方向。

质量保证使用 **pytest** 进行行为验证（237 个用例覆盖 API、FSM、HITL、快照、恢复和安全边界），**basedpyright** 约束类型边界以减少契约漂移。

后端模块目录结构可作为表 5-1 或代码清单整理：`src/api/` 对应输入与 API 边界，`src/agents/` 对应 Planner、Executor、Safety 和 Summarizer，`src/workflow/` 对应 FSM、PlanRunner、StepRunner、RuntimeEvaluator 和恢复控制，`src/models/` 对应 Pydantic 契约，`src/adapters/` 与 `src/kg/` 对应工具适配和能力图谱，`src/storage/` 对应日志、快照和文件产物管理。真正需要作为图插入正文的实现图放在 5.4 节和 5.5 节：运行时执行序列见图 5-1，泳道式模块协作见图 5-2。

---

## 5.2 任务接入与后端 API 实现

### 5.2.1 任务录入的渐进式确认链路

系统没有将任务创建简化为单一表单提交，而是通过 Task Intake 机制实现了"草稿 → 字段补充 → 确认 → 正式任务"的渐进式确认链路。该机制由以下 API 端点支撑：

- `GET /task-intakes/schema` 返回 132KB 的完整字段注册表，按任务种类（de_novo_design、sequence_evaluation 等）组织，每个字段标注类型、约束、是否必填和所属分组。前端 Task Builder 据此动态渲染表单。
- `POST /task-intakes` 接受自然语言 goal 或自由文本 query，创建任务草稿会话。后端将输入内容解析为初步字段，未识别的字段标记为待补充。
- `PATCH /task-intakes/{id}` 支持增量字段更新，允许用户分阶段补充约束。场景门控根据当前字段执行能力可行性预检查。
- `POST /task-intakes/{id}/confirm` 在字段收敛后执行最终验证——检查必填字段完整性、场景可行性和安全预检查——通过后生成 ConfirmedTaskSpec 并写入正式 ProteinDesignTask。

该链路的设计原因是：蛋白质设计任务的目标和约束在初始输入时常常不完整。用户可能给出"设计一个 30 残基的稳定螺旋肽"这样的自然语言描述，但长度范围、安全等级、模板结构和预算约束需要分步补充。渐进式确认避免了"一次性要求用户填写所有字段"的体验问题，也在正式执行前预留了场景可行性检查的窗口。

### 5.2.2 任务生命周期接口

`POST /tasks` 支持三种创建模式：`goal`（直接目标文本，兼容早期简易路径）、`query`（走 Task Intake 链路）和 `confirmed_task_spec`（已完成确认的结构化任务）。三种模式互斥，同时提交被拒绝。

`GET /tasks/{task_id}` 返回 TaskRecord，包含外部状态（ExternalStatus）、内部状态（InternalStatus）、任务目标、约束、当前计划、设计结果、决策历史和安全事件。双状态设计使 UI 可以展示面向用户的简洁状态（如 WAITING_PATCH_CONFIRM），同时保留执行细节状态（如 WAITING_PATCH、PATCHING）供恢复流程使用。

`GET /tasks/{task_id}/events` 支持按 event_type、tool_id、capability_id 过滤，返回 TaskTimelineEvent 列表。该接口直接读取 `data/logs/` 下的 JSONL 事件日志，不依赖内存 TASK_STORE。因此即使任务记录不在当前进程内存中（如服务重启后），只要日志文件存在，事件时间线仍可查询和展示。

`GET /tasks/{task_id}/report` 返回 TaskReportDetail，包含 sequence、structure_pdb_path、scores、objective_scoring（后验目标评分的证据加权结果）、structure_similarity 和 metadata。未进入 DONE 的任务请求该接口返回 404。

### 5.2.3 HITL 的实现接口

人在环路的工程实现集中在三个端点和两个后端模块。

`GET /pending-actions` 遍历任务记录中的 PendingAction 对象，返回仍处于 pending 状态的摘要列表。每条摘要包含 pending_action_id、task_id、action_type（plan_confirm / patch_confirm / replan_confirm）、candidate_count、default_suggestion 和 explanation。

`GET /pending-actions/{id}` 返回候选详情，供前端 PendingReviewWorkspace 渲染候选对比。详情中包含每个候选的 score_breakdown、runtime_state_summary、risk_level、cost_estimate、posterior_objective（如已有目标证据）、workflow_action_reason 和 evidence_source。这些字段直接对应第 4 章定义的候选契约，使前端可以展示"为什么推荐这个候选"的可解释信息。

`POST /pending-actions/{id}/decision` 接收用户选择的 choice（accept / replan / cancel）和 selected_candidate_id。后端模块 `decision_apply.py` 执行以下校验和操作：（1）验证 pending_action_id 属于当前 task 且未决策；（2）验证 selected_candidate_id 在候选集合中；（3）根据 action_type 调用对应的应用函数——plan_confirm 将选中 Plan 写入上下文并推进到 PLANNED，patch_confirm 应用 PlanPatch 并恢复执行，replan_confirm 应用 Replan（或接受 terminal_stop 进入 FAILED）；（4）写入 DECISION_APPLIED 和 WAITING_EXIT 事件日志；（5）保存 TaskSnapshot。

## 5.3 前端工作台的页面组织

前端基于 React/Vite/TypeScript 构建，通过 FastAPI 注入的 bootstrap payload 确定当前视图。启动后，`main.tsx` 读取 `window.__INITIAL_VIEW__`，根据值（dashboard / task_builder / task_detail / event_timeline）路由到对应页面组件。全局状态通过 `apiClient` 从后端实时拉取，前端不自行推导工作流状态。

四个页面分别对应不同的操作场景：

**Dashboard** 是工作区总览。左侧导航栏提供页面切换，顶部指标卡展示待审查任务数量和能力 readiness 摘要。主区域按状态分组展示任务列表，用户可直接跳转到特定任务的详情页。

**Task Builder** 是任务录入界面。它根据 `/task-intakes/schema` 返回的字段注册表动态渲染表单，支持分组折叠和字段级校验。安全预检查面板在字段收敛过程中持续评估场景可行性，提示潜在的工具不可用、预算超限或安全风险。确认前，DraftProtectionDialog 强制用户复核所有关键字段。

**Task Detail** 聚合了单个任务的全部信息。PendingReviewWorkspace 是核心交互区域——当任务处于 WAITING_* 状态时，CandidateComparison 以卡片形式并列展示多个候选方案，每个卡片包含工具链摘要、评分分解、风险等级、成本估计和推荐理由；DecisionForm 允许用户选择候选并提交决策注释。ReportExplorer 展示最终报告，StructureViewerPanel 提供结构文件的路径入口和可视化占位区域。

**Event Timeline** 以时间线形式展示任务的全部事件。11 种高亮事件类型（STATE_TRANSITION、PENDING_ACTION_CREATED、WAITING_ENTER、DECISION_APPLIED 等）以彩色标签区分，每条事件可展开查看详情字段。该页面服务于审计和调试场景，支持按事件类型和工具过滤。

前端采用三栏布局：左侧 WorkbenchSidebar 提供导航和任务上下文，中间主区域展示当前页面，右侧 InspectorPanel 展示与当前上下文相关的摘要（任务状态、事件计数、最新事件类型、capability 覆盖等）。该布局使操作员在主操作区之外持续可见关键上下文。

## 5.4 工作流运行时与执行引擎

工作流运行时的核心执行序列如图 5-1 所示。该图从用户/API 创建任务开始，依次展示 Workflow、Planner、ToolKG、Executor、ToolAdapter、Safety 和 Storage 之间的消息关系。图中需要重点说明两点：第一，Planner 负责候选生成和工具能力约束查询，但不执行工具；第二，Executor 通过 StepRunner 和 AdapterRegistry 执行已确认的 PlanStep，并把 StepResult、EventLog 和 TaskSnapshot 写回存储层。这样，运行时执行不是一个隐式的 LLM 调用链，而是由明确对象、消息和状态持久化步骤组成的可审计过程。

> **图 5-1**：运行时执行序列图，展示任务创建、候选生成、计划确认、步骤执行、工具适配、安全审查和存储写入之间的消息顺序。来源：`paper/figures/runtime-sequence.drawio.svg` / `paper/figures/runtime-sequence.drawio.png`。

### 5.4.1 WorkflowContext：运行时的单一上下文

`WorkflowContext` 是单个任务运行过程中的唯一上下文集散点。它持有原始 ProteinDesignTask、当前 Plan、StepResult 列表、SafetyResult 列表、RuntimeState、最终 DesignResult、当前 PendingAction 和 InternalStatus。模块间不通过全局变量或隐式状态通信，而是读取和修改 WorkflowContext 的明确字段。

RuntimeState 的更新通过 WorkflowContext 的集中入口完成——在 `add_step_result` 和 `add_safety_event` 被调用时，上下文自动触发 belief-state 更新器，从新的观测中推导 p_success、p_structural_failure、recovery_margin、expected_remaining_cost 和 evidence_sufficiency。这种集中式更新降低了运行时状态散落在多个模块中的风险，也保证了快照模块可以从 WorkflowContext 中提取一致的状态快照。

### 5.4.2 PlanRunner：计划级执行与状态推进

PlanRunner 负责完整计划的生命周期管理。它的主循环如下：

1. 校验任务 ID 与计划 ID 一致性。
2. 状态为 PLANNED 时推进到 RUNNING。
3. 执行前调用 SafetyAgent 进行任务级输入检查。若检查结果为 block，立即触发 replan 流程。
4. 按顺序遍历 Plan.steps，对每一步调用 StepRunner 执行。
5. 若某步返回 WAITING_PATCH 信号——即步骤失败、重试耗尽且 Planner 已生成 patch 候选——PlanRunner 停止遍历，创建 PendingAction(patch_confirm)，写入快照和 WAITING_ENTER 事件，将状态置为 WAITING_PATCH_CONFIRM，然后返回。后续由人工 Decision 驱动恢复。
6. 若某步返回需要 replan 的信号（安全阻断或结构性失败），PlanRunner 请求 Planner 生成 ReplanCandidate，进入 WAITING_REPLAN_CONFIRM。
7. 全部步骤成功完成后，调用 SafetyAgent 进行任务级输出检查，然后推进到 SUMMARIZING。

PlanRunner 的核心约束是：它可以推进 FSM、请求补丁或重规划、记录步骤事件，但不会绕过 PendingAction 自动应用需要人工确认的候选。

### 5.4.3 StepRunner：单步执行与错误归一化

StepRunner 将一次 PlanStep 的执行封装为稳定的 StepResult，屏蔽具体工具的异构性。其执行流程如下：

1. 按 `StepRetryPolicy` 进行有界重试（默认最多 3 次，指数退避）。
2. 每次尝试前调用 SafetyAgent 进行 pre-step 安全检查。若检测到 forbidden_motif 等触发 block 的条件，StepRunner 不调用适配器，直接返回安全阻断的 StepResult（status=failed，failure_type=safety_blocked）。该行为由两个确定性 focused test 验证：`test_run_step_safety_block_forbidden_motif_prevents_tool_execution` 确认 block 阻止了工具调用；`test_run_step_safety_warn_allows_execution_with_risk_flag` 确认 warn 放行但记录 risk flag。
3. 通过 AdapterRegistry 解析 tool_id 并获取对应的 ToolAdapter 实例。
4. 调用 `adapter.resolve_inputs` 解析步骤输入——常量直接使用，`S{id}.{field}` 引用从上游 StepResult 中提取。若引用目标不存在或类型不匹配，返回错误而不调用工具。
5. 根据适配器的 execution_mode 调用 `run_local` 或 `run_remote`。远程调用记录 provider、endpoint_type 和 remote_job_id。
6. 校验输出字段的 required outputs 和 output types。
7. 将成功或失败统一封装为 StepResult，包含 status、outputs、metrics、artifacts、risk_flags、failure_type、error_details、attempt_history、duration 和 adapter metadata。

StepRunner 的错误归一化是恢复机制的基础：无论工具是本地脚本崩溃、远程 REST 超时还是输出 schema 不匹配，上层 PlanRunner 和 CEBRA-WP 看到的都是统一的 failure_type 和 error_details 结构。这使 Planner 在生成 patch 或 replan 候选时不需要理解具体工具的异常格式。

### 5.4.4 恢复闭环的实现

当 StepRunner 返回失败且重试耗尽时，PlanRunner 调用 Planner 的 patch/replan 生成逻辑。Planner 根据失败上下文（failure_type、failed_step_id、completed_step_ids、RuntimeState）生成恢复候选。生成后，`pending_action.py` 执行进入等待状态前的准备工作：校验 PendingAction 与目标 WAITING 状态匹配，将 PendingAction 写入 context 和 TaskRecord，写入 WAITING_ENTER 事件和旧格式兼容日志，构建包含 runtime_summary、candidate、tool、capability 和 adapter 的审计数据，最后由调用方执行状态迁移。

人工提交 Decision 后，`decision_apply.py` 根据 action_type 调用对应的应用逻辑，写入决策事件和 WAITING_EXIT 事件，保存快照。整个恢复闭环——失败检测 → 候选生成 → 等待人工确认 → 决策应用 → 恢复执行——的事件链完整记录在 event log 中，可通过 `/tasks/{id}/events` 还原。

## 5.5 CEBRA-WP 的工程落点

CEBRA-WP 的运行时决策能力通过以下模块在工程中落地。

**RuntimeEvaluator** 负责将静态候选评分转化为证据感知的运行时排序。它接收候选的 static_score（来自 Planner 的 score_breakdown）和当前 RuntimeState，调用 `compute_runtime_delta` 计算每个候选的 runtime_adjustment。adjustment 综合 p_success、p_structural_failure、recovery_margin、expected_remaining_cost、evidence_sufficiency、候选风险、成本和 fallback depth，输出调整值、建议动作、动作理由和影响因子列表。最终分数 = static_score + runtime_adjustment，候选按最终分数重排。

四个策略模式——static_top1、fixed_threshold_gate、dynamic_no_belief_state、lite_belief_state——通过 RuntimeEvaluator 的策略开关控制：static_top1 无任何运行时调整，fixed_threshold_gate 仅执行固定门控不进行重排序，dynamic_no_belief_state 执行动态观测但 runtime_adjustment 为零，lite_belief_state 启用完整的 belief-state 更新和重排序。策略切换通过 runtime_policy 参数控制，同一代码基支持四种策略的实验对照。

**动作选择**将 RuntimeEvaluator 的建议动作映射到系统恢复闭环。`continue` 映射为继续执行下一步，`patch_local` 触发 PlanRunner 请求 Planner 生成 PatchCandidate 并进入 WAITING_PATCH_CONFIRM，`suffix_replan` 触发 ReplanCandidate 生成和 WAITING_REPLAN_CONFIRM，`stop` 构造 terminal_stop 语义的 ReplanCandidate。该映射确保算法的动作输出始终通过 FSM 的合法转移路径执行，不会出现算法建议绕过人工确认的情况。

**候选解释**由 Planner 在生成候选时附加。每个候选的 metadata 中包含 score_breakdown（含 feasibility、objective、risk、cost、recovery_complexity、overall 六个子维度）、runtime_adjustment（含 adjustment 值、触发因子和调整理由）、action_utility（四项动作的效用值）、runtime_state_summary 和 source_refs。这些字段通过 `/pending-actions/{id}` 接口暴露给前端 PendingReviewWorkspace，支撑论文中"可解释人工审查"的实现描述。

图 5-2 从泳道视角补充了上述工程落点：科研人员、Web UI、Task API、Planner、Executor、ToolAdapter、Safety 和 Storage 分别承担不同职责。图中 PendingAction/Decision 横跨 Web UI、API 和 Workflow，是 HITL 的工程接口；EventLog/TaskSnapshot 横跨 Executor、Storage 和恢复流程，是可恢复审计链的工程接口。该图用于解释为什么 CEBRA-WP 虽然是核心算法，但在实现上并不是一个单独 Agent，而是分布在候选生成、RuntimeEvaluator、动作映射和决策展示几个模块中。

> **图 5-2**：工作流泳道图，展示用户、前端、API、Planner、Executor、工具、安全检查和存储模块在一次任务中的职责分工。来源：`paper/figures/workflow-swimlane.drawio.svg` / `paper/figures/workflow-swimlane.drawio.png`。

## 5.6 工具适配器与能力管理

AdapterRegistry 维护 tool_id 到 ToolAdapter 实例的映射。当 StepRunner 需要执行某个 PlanStep 时，通过 tool_id 查找对应适配器；若 tool_id 未注册，返回明确的配置错误而非静默失败。

具体适配器的实现遵循统一接口，但在执行模式上存在差异。ESMFold 适配器支持本地推理和 NIM 远程推理两种模式，通过 execution_mode 参数切换。OpenFold 适配器封装 OpenFold3 REST 服务调用——将序列和配置序列化为 HTTP 请求，异步轮询作业状态，归一化返回的结构文件和置信度指标。ProtGPT2 适配器通过远程 PLM REST 服务生成候选序列。BioPython QC 适配器为本地 Python 脚本，封装了 BioPython 的序列合法性检查、结构完整性验证和低复杂度检测逻辑。

每个适配器实现 `describe_capabilities` 方法，返回 tool_id、adapter_id、execution_mode、capability 和 description。这套元数据被聚合到 `/capabilities/readiness` 接口中，供 Planner 在候选生成时参考：标记为 unavailable 的工具不会出现在可行候选的工具链中，标记为 degraded 的工具可出现在候选链中但标记 `degraded_feasible` 并强制要求人工确认。

ProteinToolKG 以 JSON 文件形式维护工具的能力图谱（`src/kg/protein_tool_kg.json`）。每个工具节点包含 id、name、capability、io（输入输出 schema）、compat（与其他工具的 I/O 兼容关系）、cost、safety_level 和 version。Planner 在候选生成时查询该图谱，匹配任务所需的能力阶段，过滤不可用和预算超限的工具，构建 I/O 闭包的工具链。图谱的 JSON 格式适合原型阶段的快速迭代——新增工具只需在 JSON 中添加节点并注册适配器，无需修改 Planner 的核心逻辑。

## 5.7 本章小结

本章描述了系统的工程实现，覆盖了技术选型、后端 API、前端工作台、工作流运行时、CEBRA-WP 工程落点和工具适配器六个方面。

（1）技术栈以 Python 3.12 + FastAPI + Pydantic 为后端核心，React 19 + TypeScript + Vite 为前端核心，自定义 Workflow/FSM 为工作流控制核心。原型阶段使用内存 TASK_STORE 和文件日志/快照存储。

（2）任务接入通过渐进式确认链路（draft → supplement → confirm → task）完成，15 个 API 端点覆盖了从任务创建到人工决策、事件查询和报告读取的完整闭环。HITL 接口以 PendingAction/Decision 为一等对象实现，前后端通过结构化契约交互。

（3）前端以四页面工作台组织：Dashboard（总览）、Task Builder（任务录入）、Task Detail（状态与决策）、Event Timeline（审计）。三栏布局使操作员在操作任务的同时持续可见关键上下文。

（4）工作流运行时以 WorkflowContext 为单一上下文，PlanRunner 管理计划级执行，StepRunner 封装单步执行和错误归一化。恢复闭环通过 PendingAction/DecisionApply 模块实现，所有状态变迁和决策事件完整记录在 event log 中。

（5）CEBRA-WP 通过 RuntimeEvaluator、belief-state 更新器和 Planner 候选生成逻辑在工程中落地，四种策略模式共享同一代码基，运行时动作映射到 FSM 合法转移路径。

（6）工具适配器通过 BaseToolAdapter 统一接口和 AdapterRegistry 注册机制实现外部工具的接入，ProteinToolKG 以 JSON 图谱形式为 Planner 提供能力驱动的工具链组合依据。

---

## 图的清单

| 图号 | 标题 | 源文件 |
|------|------|--------|
| 图 5-1 | 运行时执行序列：TaskAPI、Workflow、Planner、ToolKG、Executor、Adapter、Safety、Storage | `paper/figures/runtime-sequence.drawio.svg` |
| 图 5-2 | 工作流泳道式模块协作 | `paper/figures/workflow-swimlane.drawio.svg` |
