# 工作流运行时实现

## 1. 工作流实现定位

工作流运行时是系统实现章节的核心。它把 Planner 生成的 `Plan` 转化为实际工具调用，同时维护任务状态、步骤结果、安全事件、运行时状态、待决策对象和快照。当前实现主要位于 `src/workflow/`，由 `run_task_sync`、`WorkflowContext`、`PlanRunner`、`StepRunner`、`PendingAction`、`DecisionApply`、`RuntimeEvaluator` 和 `Snapshot` 模块协同完成。

## 2. 同步任务执行入口

`workflow.py` 中的 `run_task_sync` 是原型阶段的同步执行入口。它依次创建 PlannerAgent、ExecutorAgent 和 SummarizerAgent，构造初始 `TaskRecord` 与 `WorkflowContext`，然后执行规划、执行和汇总三个阶段。若规划或执行阶段进入 `WAITING_*` 状态，则函数直接返回当前 TaskRecord，等待用户通过 Decision API 推进。

该入口适合论文表述为“最小闭环实现”：它不是生产级异步调度器，但完整串联了任务创建、计划生成、执行、人工等待和汇总路径。

## 3. WorkflowContext

`WorkflowContext` 是单个任务运行过程中的上下文对象，包含原始任务、当前计划、步骤结果、安全事件、RuntimeState、最终结果、PendingAction 和内部状态。它提供 `add_step_result` 和 `add_safety_event` 方法，在记录执行结果或安全事件时触发 RuntimeState 更新。

该设计的关键点是：RuntimeState 不由各模块随意修改，而是通过 WorkflowContext 的 helper 统一接入 belief-state 更新器。这降低了运行时状态散落在多个模块中的风险，也使快照可以从上下文中提取一致的 runtime state。

## 4. PlanRunner

`PlanRunner` 负责完整计划执行和状态推进。它在执行前校验任务 ID 与计划 ID 是否一致；当状态为 `PLANNED` 时转入 `RUNNING`；执行前调用 SafetyAgent 进行任务输入检查；随后按步骤遍历 `Plan.steps`，通过 PatchRunner/StepRunner 执行每个步骤。执行中若进入 `WAITING_PATCH`，PlanRunner 立即返回；若步骤失败，则根据失败类型、安全阻断、重试耗尽和 workflow action 请求 replan 或 stop；全部步骤完成后执行最终安全检查，并进入汇总阶段。

PlanRunner 的实现体现了系统控制边界：它可以推进 FSM，可以请求 patch/replan，可以记录步骤事件，但不会绕过 PendingAction 自动应用需要人工确认的候选。

## 5. StepRunner

`StepRunner` 是单步微循环的最小执行单元。它负责步骤级重试、pre-step 安全检查、适配器解析、输入解析、工具执行、输出校验、错误归一化、fallback 尝试和 StepResult 构造。

其核心流程如下：

1. 按 `StepRetryPolicy` 进行有限重试。
2. 每次尝试前执行 SafetyAgent pre-step 检查。
3. 通过 AdapterRegistry 获取 ToolAdapter。
4. 调用 `adapter.resolve_inputs` 解析常量与上游引用。
5. 调用 `adapter.run_local` 或适配器内部封装的远程逻辑。
6. 校验 required outputs 与 output types。
7. 将成功或失败统一封装为 StepResult，并写入 attempt history、duration、failure type、adapter metadata 等字段。

StepRunner 的价值在于把复杂工具调用规范化为稳定 StepResult，使上层 PlanRunner 和 CEBRA-WP 不需要理解具体工具异常。

## 6. PendingAction 与 DecisionApply

`pending_action.py` 负责进入等待状态前的准备工作。它校验 PendingAction 与目标 WAITING 状态是否匹配，将 PendingAction 写入 context 和 record，写入旧格式事件日志和结构化 WAITING_ENTER EventLog，并构建包含 runtime summary、candidate、tool、capability、adapter 等字段的审计数据。随后调用方再执行状态迁移。

`decision_apply.py` 负责把用户 Decision 应用到当前任务。对 plan_confirm，接受候选会把 selected Plan 写入上下文并转为 `PLANNED`；请求 replan 会回到 `PLANNING`；取消会进入 `CANCELLED`。对 patch_confirm 和 replan_confirm，模块分别应用 PlanPatch 或 Replan 候选，并写入决策事件、等待退出事件和任务快照。

这一组模块体现了人在环路的工程边界：UI 提交 Decision，后端验证状态一致性，工作流模块执行状态迁移和上下文修改。

## 7. RuntimeEvaluator 与 CEBRA-WP 落点

CEBRA-WP 的运行时决策主要落在 `runtime_evaluator.py`、`belief_state.py`、`recovery.py` 和 Planner 候选生成逻辑中。`RuntimeEvaluator` 根据候选静态分数和 RuntimeState 计算 runtime adjustment，并按 final score 重新排序。其策略模式包括 `static_top1`、`static_gate`、`dynamic_observation_only` 和 `lite_belief_state`，正好对应论文实验中的消融组。

`compute_runtime_delta` 综合成功概率、结构失败概率、恢复余量、预期剩余成本、证据充分性、候选置信度、风险、成本和 fallback depth，输出分数调整值、建议动作、动作理由和因子列表。建议动作最终映射到 `continue`、`patch_local`、`suffix_replan`、`stop` 四类恢复语义。

## 8. 快照与恢复

`snapshots.py` 中的 `build_task_snapshot` 根据 WorkflowContext 构建最小可恢复上下文，记录外部状态、计划版本、已完成步骤、当前步骤索引、产物、runtime state、runtime state summary 和 pending action。进入 WAITING 状态前写入快照，可以保证系统重启后仍能恢复到完整决策场景。

论文中可以将快照机制表述为：系统不仅记录最终结果，还保存执行中断点、计划版本和待决策上下文，从而支持长时间运行任务的恢复和审计。

## 9. 工作流可写入论文的实现要点

1. WorkflowContext 是任务运行期的单一上下文，连接计划、步骤结果、安全事件、RuntimeState 和 PendingAction。
2. PlanRunner 管理计划级执行和 FSM 状态推进，StepRunner 管理步骤级执行与错误归一化。
3. PendingAction 与 DecisionApply 将人工确认实现为后端受控状态迁移，而非 UI 自行修改状态。
4. RuntimeEvaluator 把 CEBRA-WP 的运行时证据转化为候选重排和恢复动作建议。
5. TaskSnapshot 将 runtime state 和 pending action 一并持久化，支持等待状态恢复。

