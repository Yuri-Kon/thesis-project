# W13 Issue #208 实施文档：代码基线审计与接口缺口清单

- Issue: #208
- Issue 标题：`W13-Docs-3: 代码基线审计与接口缺口清单`
- 文档状态：Draft v1
- 更新时间（本地）：2026-03-25
- 覆盖执行窗口：2026-03-24 至 2026-03-29
- 适用范围：
  - `src/agents/planner.py`
  - `src/workflow/plan_runner.py`
  - `src/workflow/patch_runner.py`
  - `src/workflow/context.py`
  - `src/models/contracts.py`
  - `src/storage/snapshot_store.py`
  - `src/storage/log_store.py`
  - `src/infra/w12_vertical_experiment.py`

## 1. 审计结论

基于当前仓库真实代码，`#208` 的核心结论不是“系统缺少 patch/replan/Top-K”，而是“系统已经具备静态候选生成、gate、patch/replan 恢复闭环、快照与事件日志骨架，但还没有把新算法需要的运行时状态估计、动作选择和证据字段做成明确契约并接入现有闭环”。

因此，后续编码 issue 不应重写 Planner 或 Workflow，而应围绕三条最小增量主线推进：

- 主线 A：补 `runtime_state / belief_state` 契约与 snapshot 持久化格式。
- 主线 B：在现有 `retry -> patch -> replan` 闭环上增加动作选择与候选重排序，不新增 FSM 语义。
- 主线 C：补实验与审计字段，使 `w12_vertical_experiment.py` 能直接比较 `静态 Top-1`、`固定阈值 gate`、`动态无 belief-state`、`Lite belief-state`。

## 2. 当前已具备能力

## 2.1 Planner 基线

`src/agents/planner.py` 已经具备以下能力：

- 已有 `plan_top_k / patch_top_k / replan_top_k`，且统一输出 `TopKResult`。
- 已有 `_score_payload` 与 `score_candidate_payload()`，能对 `Plan` / `PlanPatch` 做静态打分。
- 已有 `evaluate_top_k_gate()`，能基于 `score / risk / cost` 决定是否进入 `WAITING_*`。
- 已有 `patch()` / `replan()` 的向后兼容 fallback 路径，不会阻断旧 stub。
- 已有 suffix replan 候选生成基础，候选 metadata 中已出现 `replan_mode = "suffix_replan"`。
- 已有 `_runtime_fallback_state` 与双路 provider fallback，但它解决的是“规划 provider 退化/切换”，不是新算法的运行时状态估计。

结论：

- Planner 不缺 Top-K，也不缺静态评分骨架。
- 真正缺的是“运行时状态如何进入打分和默认建议”的接口层，而不是再造一个新的 Planner。

## 2.2 Workflow 基线

`src/workflow/plan_runner.py` 与 `src/workflow/patch_runner.py` 已经具备以下能力：

- 已有 `PlanRunner._perform_replan()`，能执行 `WAITING_REPLAN -> REPLANNING -> RUNNING` 最小闭环。
- 已有 `PatchRunner.run_step_with_patch()`，能在 step 失败后走 `patch_top_k -> gate -> auto apply / WAITING_PATCH -> escalate replan`。
- 已有 `resolve_s6_recovery_action()` 驱动的 patch 触发逻辑，说明恢复顺序已有明确入口。
- 已有 `append_event()` / `write_event_log()`，关键步骤、等待态与升级路径都会写事件日志。
- 已有 `StepResult.metrics["patch"]` 与 `StepResult.metrics["recovery"]`，能承载 patch 来源、恢复层级、升级原因等局部审计字段。
- 已有 `PendingAction` 和 WAITING 流程，适合承载高风险 patch/replan 的 HITL 确认。

结论：

- Workflow 不缺恢复闭环，也不缺等待态。
- 真正缺的是“在 patch / replan 之前，是否先 stop / continue / suffix_replan / patch_local”的统一动作选择层，以及该决策的审计字段。

## 2.3 Contracts / Snapshot 基线

`src/models/contracts.py`、`src/workflow/context.py`、`src/storage/snapshot_store.py` 已经具备以下能力：

- `WorkflowContext` 已集中持有 `task / plan / step_results / safety_events / design_result / pending_action / status`。
- `StepResult` 已有 `artifacts / metrics / error_details / risk_flags`，适合增量扩展运行时观测。
- `PendingActionCandidate.metadata` 已存在，可承载候选的运行时摘要和解释字段。
- `TaskSnapshot.artifacts` 已允许写 JSON-serializable payload 或 `ArtifactRef`，适合作为运行时状态落盘容器。
- `snapshot_store.append_snapshot()` / `read_latest_snapshot()` 已具备读写骨架，不需要重做 snapshot 子系统。

结论：

- 当前 contracts 对“加字段”是友好的。
- 真正缺的是“稳定的运行时状态 schema、命名约定、序列化位置”，而不是缺 snapshot 机制本身。

## 2.4 Experiment / Evidence 基线

`src/infra/w12_vertical_experiment.py` 已经具备以下能力：

- 已能从 `event_log_path` 提取 patch / replan / suffix replan / waiting / failure traceability 指标。
- 已能聚合 `success_rate / first_pass_success_rate / schema_valid_rate / executable_plan_rate`。
- 已能统计 `patch_minimality_hit_rate`、`suffix_replan_prefix_preservation_rate`。
- 已有 run-level 与 group-level 聚合逻辑，适合继续扩展新增字段。
- 已明确把 `event_log_path / snapshot_path / report_path` 纳入结果行，证据链骨架已存在。

结论：

- 实验脚本不缺主流程。
- 真正缺的是“运行时状态变量、shadow action、候选重排序原因”的采集与聚合字段。

## 3. 真正缺口清单

## 3.1 数据契约缺口

### 缺口 D1：缺少显式 `runtime_state / belief_state` 契约

已有基础：

- `WorkflowContext` 可增字段。
- `TaskSnapshot.artifacts` 可落 JSON。
- `StepResult.metrics` 可挂审计元数据。

新增工作：

- 在 `src/models/contracts.py` 定义稳定的 `RuntimeState` 或 `BeliefState` 数据模型。
- 在 `src/workflow/context.py` 增加 `runtime_state` 或 `belief_state` 可选字段。
- 约定 snapshot 中的持久化键，例如 `TaskSnapshot.artifacts["runtime_state"]`。

最小改动落点：

- `src/models/contracts.py`
- `src/workflow/context.py`
- `src/storage/snapshot_store.py` 的读写调用点

建议测试落点：

- `tests/unit/test_contracts.py`
- `tests/unit/test_workflow_context.py`
- `tests/integration/` 中的 snapshot 恢复用例

### 缺口 D2：缺少运行时状态摘要进入候选与等待态的稳定约定

已有基础：

- `PendingActionCandidate.metadata` 已存在。
- `PendingAction.explanation` 已存在。

新增工作：

- 约定候选 metadata 中的运行时摘要字段，例如 action score、状态快照摘要、默认建议原因。
- 约定 WAITING 时需要保留哪些最小状态摘要，以便 HITL 决策回放。

最小改动落点：

- `src/models/contracts.py`
- `src/workflow/pending_action.py`
- `src/agents/planner.py`

建议测试落点：

- `tests/unit/test_pending_action.py`
- `tests/unit/test_planner_agent.py`

## 3.2 流程接入缺口

### 缺口 F1：缺少运行时状态更新器

已有基础：

- `StepResult`、`SafetyResult`、失败上下文都已经能在 Workflow 中拿到。
- `PatchRunner` 与 `PlanRunner` 均有明确事件边界。

新增工作：

- 新增一个纯函数或轻量模块，根据 `StepResult / SafetyResult / failure context` 更新最小状态集。
- 最小状态集至少应覆盖：
  - `p_success`
  - `p_structural_failure`
  - `recovery_margin`
  - `expected_remaining_cost`

最小改动落点：

- `src/workflow/belief_state.py` 或 `src/workflow/adaptive_planning.py`
- `src/workflow/plan_runner.py`
- `src/workflow/patch_runner.py`

建议测试落点：

- `tests/unit/test_belief_state.py`
- `tests/integration/test_recovery_flow.py`

### 缺口 F2：缺少统一动作选择器

已有基础：

- Patch 和 replan 闭环已经存在。
- `resolve_s6_recovery_action()` 已证明系统接受“由规则返回动作”这一模式。

新增工作：

- 抽出统一动作选择接口，输出仅限四个动作：
  - `continue`
  - `patch_local`
  - `suffix_replan`
  - `stop`
- 将动作映射回现有闭环：
  - `continue`：继续当前流程
  - `patch_local`：复用现有 patch 路径
  - `suffix_replan`：复用现有 replan 路径，并优先 suffix candidate
  - `stop`：进入现有 WAITING / fail-fast 受控路径

最小改动落点：

- `src/workflow/plan_runner.py`
- `src/workflow/patch_runner.py`
- `src/workflow/recovery.py`

建议测试落点：

- `tests/unit/test_recovery.py`
- `tests/integration/test_plan_runner.py`
- `tests/integration/test_patch_runner.py`

### 缺口 F3：缺少“静态评分 + 运行时修正”的接缝

已有基础：

- `_score_payload()` 已有静态评分。
- `TopKResult.default_recommendation` 已能改变默认建议。

新增工作：

- 增加 shadow score / adjusted score 接口。
- 在不改变候选结构的前提下，支持运行时状态修正默认建议与 explanation。
- 初期应先支持 shadow 输出，再决定是否驱动控制流。

最小改动落点：

- `src/agents/planner.py`
- `src/models/validation.py`

建议测试落点：

- `tests/unit/test_planner_agent.py`

## 3.3 证据字段缺口

### 缺口 E1：事件日志中缺少运行时状态和动作选择审计字段

已有基础：

- `STEP_FINISHED / STEP_FAILED / RECOVERY_ESCALATED / TASK_STATUS_CHANGED` 已存在。
- `StepResult.metrics["recovery"]` 已承载局部恢复元数据。

新增工作：

- 在事件日志中补充：
  - 触发动作名称
  - action score / shadow score
  - runtime_state 摘要
  - 从何种证据得出升级或止损结论

最小改动落点：

- `src/workflow/plan_runner.py`
- `src/workflow/patch_runner.py`
- `src/storage/log_store.py`

建议测试落点：

- `tests/integration/test_event_log.py`
- `tests/integration/test_hitl_flow.py`

### 缺口 E2：快照中缺少可恢复的运行时状态摘要

已有基础：

- `TaskSnapshot.artifacts` 已允许 JSON payload。
- `read_latest_snapshot()` 已可恢复最近快照。

新增工作：

- 在 WAITING 前和关键恢复点写入最小运行时状态摘要。
- 明确恢复时优先读取 snapshot 而不是从 event log 反推。

最小改动落点：

- `src/models/contracts.py`
- `src/storage/snapshot_store.py`
- 触发 snapshot 的 workflow 调用点

建议测试落点：

- `tests/integration/test_snapshot_recovery.py`

### 缺口 E3：实验聚合缺少 belief-state / action-level 字段

已有基础：

- `extract_run_metrics()` 已会读取 event log 与 snapshot path。
- `aggregate_group_metrics()` 已具备 group summary 结构。

新增工作：

- 在 run-level 增加：
  - `action_continue_count`
  - `action_patch_local_count`
  - `action_suffix_replan_count`
  - `action_stop_count`
  - `shadow_action_agreement_rate`
  - `runtime_state_observable_rate`
- 在 group-level 增加：
  - action 分布
  - belief-state 字段完整率
  - shadow vs actual default recommendation 偏差率

最小改动落点：

- `src/infra/w12_vertical_experiment.py`

建议测试落点：

- `tests/unit/test_w12_vertical_experiment.py`

## 4. 按模块的最小改动清单

## 4.1 `src/agents/planner.py`

已有基础：

- Top-K 候选生成完整。
- 静态评分与 gate 完整。
- suffix replan 已有候选形态。

新增工作：

- 接收 `runtime_state` 作为可选输入，但保持兼容旧调用。
- 产出 shadow score / adjusted score / rerank reason。
- 修正 `default_recommendation` 的解释字段，不改候选 schema 主体。

不应做的事：

- 不重写 `TopKResult` 契约。
- 不把 Planner 变成执行器。

## 4.2 `src/workflow/plan_runner.py`

已有基础：

- replan 请求与 WAITING_REPLAN 闭环已存在。
- step event 已有 trace data 组装点。

新增工作：

- 在 step 完成/失败、replan 触发前后更新 `runtime_state`。
- 为 suffix replan 与 stop 补充统一动作选择记录。
- 在事件日志中记录 runtime_state 摘要与 action reason。

## 4.3 `src/workflow/patch_runner.py`

已有基础：

- patch 候选生成、gate、自动应用、失败升级均完整。
- `metrics["patch"]` / `metrics["recovery"]` 已有局部恢复元信息。

新增工作：

- 在 patch 之前插入动作选择入口，但不改变 patch 闭环顺序。
- 为 `patch_high_risk`、`patch_failed`、`patch_auto_path` 补 action-level 审计。
- 将 runtime_state 写回上下文与后续 snapshot。

## 4.4 `src/workflow/context.py`

已有基础：

- Context 已集中存储任务运行期关键信息。

新增工作：

- 增加 `runtime_state` 或 `belief_state` 字段。
- 提供最小访问器或更新入口，避免各处手写 dict merge。

## 4.5 `src/models/contracts.py`

已有基础：

- 兼容性要求明确，适合 additive changes。
- `TaskSnapshot.artifacts`、`StepResult.metrics` 可扩展。

新增工作：

- 定义运行时状态 schema。
- 定义 action 审计字段 schema 或最小字段约定。
- 定义 snapshot 中运行时状态的稳定键与版本字段。

## 4.6 `src/infra/w12_vertical_experiment.py`

已有基础：

- 已有 run-level/group-level 指标汇总。
- 已有与 patch/replan/suffix/waiting/failure traceability 相关的基础字段。

新增工作：

- 扩展 action-level 与 runtime-state-level 统计。
- 让四组基线能共用同一聚合脚本，而不是分叉脚本。

## 5. 后续 Issue 入口说明

`#208` 的输出应直接供 W14/W15/W16 引用，建议入口如下：

- W14-01：优先解决 `D1`，先把 `runtime_state` 做成契约与 snapshot 挂点。
- W14-02：解决 `F1`，实现状态更新器并补 focused unit tests。
- W14-03：解决 `E1 + E2`，先补事件与快照审计字段，不急于驱动控制流。
- W14-04：解决 `F3`，只做 shadow rerank / shadow action，不修改默认执行路径。
- W15-01：解决 `F2`，把动作选择器接入 Workflow，但保持现有 FSM 与恢复顺序。
- W15-02：继续推进 `F3`，让 Planner 默认建议可受运行时修正影响。
- W15-03 / W15-04：分别形成 `动态无 belief-state` 与 `Lite belief-state` 两条动态路线。
- W16-01 ~ W16-04：基于 `E3` 扩展统一实验矩阵和证据包。

## 6. 建议验收口径

为避免后续 issue 再次偏离当前代码状态，建议沿用以下验收口径：

- 每个 issue 必须区分“复用现有能力”与“新增接口/字段”。
- 每个接口变更必须给出对应测试落点。
- 任何控制流变更都必须映射回现有 `retry -> patch -> replan` 契约，不得新增 FSM 状态。
- 任何实验结论都必须能回链到 `event_log_path + snapshot_path + report_path`。

## 7. 与 Issue #208 的逐项映射

- `列出当前已存在的 Top-K、打分、gate、patch/replan、snapshot、event log 能力`
  - 已由本文第 2 节覆盖。
- `列出新算法最小实现所缺失的数据契约、流程接入点和实验字段`
  - 已由本文第 3 节覆盖。
- `按模块输出最小改动清单和建议测试落点`
  - 已由本文第 4 节覆盖。
- `将结果沉淀为可被 issue 直接引用的接口缺口清单`
  - 已由本文第 5 节与第 6 节覆盖。

## 8. 结论

当前仓库最值得保留的部分是：Top-K、gate、patch/replan、WAITING、snapshot、event log 这套骨架已经足够支撑新算法的 Lite 版接入。后续工作的重点应是补 contracts、接入 runtime_state、增加 action-level observability，而不是重做 Planner 或 Workflow。
