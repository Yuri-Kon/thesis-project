# 核心算法设计—代码可追踪性矩阵

- 生成日期：2026-05-05
- 审查范围：设计文档 `../thesis-project.design/docs/design/core-algorithm-spec.md`、`../thesis-project.design/docs/design/runtime-adaptation-formalization.md` 与当前实现 `src/**`
- 本文定位：调查计划 D1 产物，只做设计—实现对齐，不提出最终理论重写；差距优先级会在 D4 文档展开。

## 1. 总体判断

当前代码已经实现了一个可运行的 `constraint-aware / budget-aware / risk-aware / recovery-aware` 工作流规划骨架：

1. 候选集合 `Pi_t`：由 `CandidateGenerator.generate()` 统一处理 Plan/Patch/Replan Top-K。
2. 静态候选评分：由 `planner._score_payload()` 计算 `feasibility/objective/risk/cost/recovery_complexity/overall` 等指标。
3. Lite belief-state：由 `workflow.belief_state.update_runtime_state()` 维护五维运行时状态。
4. runtime adjustment：由 `workflow.runtime_evaluator.compute_runtime_delta()` 与 planner shadow rerank 接入。
5. action utility：由 `RuntimeEvaluator.compute_action_utilities()` 计算四类动作效用。
6. recovery/stop 控制：由 `workflow.recovery.select_workflow_action()` 与 `build_terminal_stop_candidate()` 接入现有 WAITING_REPLAN 闭环。

但从论文算法表达角度，当前实现更像“规则化启发式系统”，还不是严格的理论算法：

- 数学目标函数中的符号与代码权重、字段、阈值没有统一命名层；
- `Feasibility` 在设计中被称作硬约束，但代码中大多表现为过滤规则 + 连续分数，硬约束边界需要明确；
- `Utility(pi, x_t)`、`runtime_adjustment`、`ActionUtility` 三套公式之间尚未形成一个统一优化视角；
- posterior objective scoring 已有实现，但与静态 planner objective 和 belief-state evidence 更新的关系还比较松散；
- 理论依据目前主要是工程直觉，尚未映射到 POMDP/belief-state planning、budgeted/risk-sensitive planning、workflow recovery、LLM/tool-use planning、protein design objective 等文献。

## 2. source_refs / SID 追踪规范（Issue #337）

算法总版本为 `cebra_wp.v2`，子公式/schema 版本总表见
`docs/algorithm-and-llm/algorithm-version-registry.md` 和代码侧
`src.models.algorithm_versions`。`source_refs` 继续表达设计 SID 与实现引用，
不替代 payload 内部的 `schema_version`。

实现侧统一使用短字符串数组：

```python
"source_refs": ["sid:<design-sid>", "impl:<implementation-ref>"]
```

常量集中在 `src/models/source_refs.py`，运行时 metadata 不编码文档路径、URL、长公式或 `sid:...:proposed` 后缀。尚未进入设计 SSOT 的 SID 通过同模块 `design_ref_status_for()` / `PROPOSED_DESIGN_REF_STATUS` 或本文集中标注 proposed 状态。

| metadata 对象 | source refs 常量 | SID 状态 |
|---|---|---|
| `metadata.candidate_feasibility` | `SOURCE_REF_FEASIBILITY` = `sid:algo.adaptive.feasibility_filter`, `impl:candidate_generator.feasibility.v1` | `algo.adaptive.feasibility_filter` proposed |
| `metadata.static_score` / `metadata.action_score` / `score_breakdown` | `SOURCE_REF_STATIC_SCORE` = `sid:algo.adaptive.optimization_objective`, `sid:planner.algorithm.candidate_scoring`, `impl:planner.score_breakdown.v1` | existing |
| `posterior_score` / `metadata.posterior_objective` | `SOURCE_REF_POSTERIOR_OBJECTIVE` = `sid:algo.posterior_objective_scoring`, `impl:posterior_score.v1`, `impl:posterior_objective.v1` | `algo.posterior_objective_scoring` proposed |
| `metadata.runtime_adjustment` / runtime final/shadow score | `SOURCE_REF_RUNTIME_ADJUSTMENT` = `sid:planner.algorithm.runtime_adjustment_formula`, `sid:planner.algorithm.runtime_reranking`, `impl:planner.runtime_adjustment.v1` | existing |
| `ActionUtility.source_refs` | `SOURCE_REF_ACTION_UTILITY` = `sid:algo.schema.action_utility`, `sid:algo.action_feature_derivation`, `impl:runtime_evaluator.action_utility.v1`, `impl:workflow.action_features.v1` | `algo.schema.action_utility` existing; `algo.action_feature_derivation` proposed |
| default `ActionUtility.source_refs` | `SOURCE_REF_DEFAULT_ACTION_UTILITY` = `sid:algo.schema.action_utility`, `impl:runtime_evaluator.default.v1` | existing |
| recovery action selection metadata | `SOURCE_REF_ACTION_SELECTION` = `sid:algo.recovery_aware_action_selection`, `sid:planner.algorithm.action_priority_resolution`, `impl:recovery.select_workflow_action.v1` | `algo.recovery_aware_action_selection` proposed; `planner.algorithm.action_priority_resolution` existing |
| terminal stop metadata | `SOURCE_REF_TERMINAL_STOP` = `sid:algo.terminal_stop_policy`, `sid:planner.algorithm.stop_semantics`, `impl:recovery.terminal_stop.v1` | `algo.terminal_stop_policy` proposed; `planner.algorithm.stop_semantics` existing |

设计仓库 `../thesis-project.design` 未在本实现中修改；proposed SID 仍需后续设计同步。

## 3. 设计 SID ↔ 代码路径矩阵

| 设计 SID | 设计含义 | 主要代码位置 | 当前实现状态 | 对齐判断 |
|---|---|---|---|---|
| `algo.adaptive.problem_formulation` | 高代价、长链路、可失败、可恢复蛋白设计工作流中的动态工具链规划问题；输入 `g,c,K,x_t,o_t`，输出候选集合、默认链、patch、suffix_replan 或 stop | `src/agents/planner.py`; `src/agents/candidate_generator/generator.py`; `src/workflow/recovery.py`; `src/workflow/belief_state.py` | 已实现主要工程闭环：planner 生成候选，candidate generator 过滤/排序，workflow 根据 runtime state 选择恢复动作 | 部分对齐。工程结构完整，但论文层问题定义还没有完整落到统一形式化接口 |
| `planner.contracts.candidate_schema` | Planner 在关键节点输出候选集合 Top-K，供 HITL 使用 | `CandidateGenerator.generate()` lines 51-167; `PendingActionCandidate` in `src/models/contracts.py` | 已实现 dedupe、filter、score、Top-K、多样性选择、default recommendation | 基本对齐。需要补充候选集合数学定义和字段语义稳定表 |
| `planner.algorithm.candidate_scoring` | 静态评分：`feasibility/objective/risk/cost/recovery_complexity/overall` | `planner._score_payload()` lines 2926-3000; `_resolve_score_weights()` lines 3028-3060 | 已实现静态 score_breakdown，但额外加入 `confidence/tool_readiness/tool_coverage/fallback_depth`；`recovery_complexity` 被计算但未进入 overall 默认权重 | 部分对齐。公式结构存在，但设计项和代码项不完全一致 |
| `algo.adaptive.optimization_objective` | 总体候选效用：`Utility(pi,x_t)=alpha Feasibility + beta GoalFit - gamma Cost - delta Risk - eta RecoveryComplexity - zeta HumanInterventionCost` | `planner._score_payload()`; `runtime_evaluator.compute_runtime_delta()`; `RuntimeEvaluator.compute_action_utilities()` | 被拆成静态分数、runtime delta、动作效用三段实现 | 部分对齐。需要统一为两层效用：候选效用 `U_pi` 与控制动作效用 `U_a` |
| `planner.algorithm.runtime_state_estimation` | 五维 Lite belief-state：`p_success,p_structural_failure,recovery_margin,expected_remaining_cost,evidence_sufficiency` | `workflow.belief_state.update_runtime_state()` lines 23-228; `RuntimeState` in `contracts.py`; `runtime_policy.py` | 已实现初始化、StepResult/SafetyResult/FailureContext 更新、证据信号估计、状态持久化 | 基本对齐。理论上需解释为 belief-state 的低维充分统计/启发式近似 |
| `planner.algorithm.runtime_adjustment_formula` | 基于运行时状态对候选分数做调整 | `workflow.runtime_evaluator.compute_runtime_delta()` lines 92-171; `planner._build_runtime_shadow_decision()` lines 2539-2639 | 已实现 `delta`，由 evidence/risk/recovery/cost 等 effect 组成，clamp 到 ±0.35 | 基本对齐但设计文档 SID 内容缺失，只剩标题。需要回填正式公式与代码一致性说明 |
| `algo.schema.action_utility` | 四动作效用：continue/patch_local/suffix_replan/stop | `RuntimeEvaluator.compute_action_utilities()` lines 313-373; `ActionUtility` in `runtime_schemas.py` lines 398-450 | 代码公式与设计文档几乎一致；auto-stop 条件由 `_should_auto_stop()` 实现 | 高度对齐。需补充各派生变量来源 `lp,er,pp,br,gr,safety_term,iv` |
| `planner.algorithm.runtime_action_selection` | 动作选择与恢复感知控制：continue、patch_local、suffix_replan、stop，硬优先级优先于效用比较 | `workflow.recovery.select_workflow_action()` lines 184-410; `RuntimeEvaluator.select_action()` lines 260-311 | 已实现 phase allowed actions、safety block、suggested action、stop 门槛、patch/replan 优先级 | 基本对齐。存在两套选择路径：recovery selector 与 RuntimeEvaluator.select_action，需要明确主路径 |
| `planner.algorithm.stop_semantics` | stop 作为 terminal_stop replan candidate，复用 WAITING_REPLAN_CONFIRM，不映射 CANCELLED | `build_terminal_stop_candidate()` lines 413-458; `is_terminal_stop_candidate()` lines 489-493; `resolve_terminal_stop_reason()` lines 496-511 | 已实现 terminal_policy=stop、terminal_reason、FAILED 语义映射 | 基本对齐。需要确认最终 FSM 接受 stop 后的快照/状态写入链路 |
| 六类 Runtime Schema | Cost/Risk/Recovery/State/Observation/Action-Utility Schema | `src/models/runtime_schemas.py` | 已实现 CostSchema、RiskSchema、RecoverySchema、RuntimeStateSchema、ObservationSchema、ActionUtility 和字段映射 | 基本对齐。数学论文中应只抽象关键变量，不直接展开所有工程字段 |
| posterior objective scoring | 基于 direct/proxy/degraded evidence 的目标后验评分 | `src/adapters/objective_ranker_adapter.py` | 已实现 `_POSTERIOR_COMPONENTS`、权重 preset、component effective score、evidence_sufficiency、warnings | 部分对齐。与主 Planner objective 和 belief-state evidence 的理论连接需要加强 |

## 3. 当前算法在代码中的实际分层

### 3.1 候选生成层：`Pi_t`

主要代码：

- `src/agents/candidate_generator/generator.py:40-167`
- `src/agents/candidate_generator/builder.py`
- `src/agents/candidate_generator/filters.py`
- `src/agents/planner.py` 中构造 Plan/Patch/Replan payload 的路径

当前实际流程：

```text
raw payloads
  -> dedupe
  -> build PendingActionCandidate
  -> static score key / final score key
  -> hard/soft filter
  -> static Top-K
  -> runtime reranked Top-K when runtime_state exists
  -> default_recommendation
```

与设计的 `Pi_t` 对应关系：

```text
Pi_t = { pi_i | pi_i generated from planner payloads and survives F(pi_i,C,K,h_t) }
```

其中 `F` 当前由以下工程规则近似：

- missing tools：`missing_tools:*`
- allowed/blocked tools：`tool_not_allowed`, `tool_blocked`
- safety level：`safety_level_exceeded`
- max cost level：`cost_level_exceeded`
- I/O closure：`io_not_closed`
- tool/capability readiness：`tool_unavailable`

需要注意：`io_not_closed` 和 `tool_unavailable` 当前被放入 `soft_filtered_rows`，在没有更好候选时可能回退使用。这在工程上合理，但论文中必须区分：

- hard infeasible：绝对不可执行；
- soft infeasible / degraded feasible：可展示但需要 HITL 或降级说明；
- feasible：可自动排序和默认推荐。

### 3.2 静态评分层：`S_static(pi)`

代码位置：`src/agents/planner.py:2926-3000`。

当前公式可归纳为：

```text
avg_risk = mean(tool_risk)
avg_cost = mean(tool_cost)
tool_readiness = mean(readiness)
tool_coverage = coverage(tool_ids, capabilities)
fallback_depth = fallback_depth(tool_ids, registry)
recovery_complexity = 1 - fallback_depth

feasibility = 0.5 + 0.25 * tool_coverage + 0.25 * fallback_depth
objective = 1.0 - 0.3 * avg_cost + objective_bonus
risk = 1.0 - avg_risk
cost = 1.0 - avg_cost
confidence = 0.35*feasibility + 0.25*tool_readiness + 0.2*tool_coverage + 0.2*fallback_depth

overall = sum_k w_k * component_k
```

当前 `overall` 实际使用的 component：

- feasibility
- objective
- risk
- cost
- confidence
- tool_readiness
- tool_coverage

设计文档要求的 component：

- feasibility
- objective
- risk
- cost
- recovery_complexity
- overall

差异：

1. `recovery_complexity` 被输出但没有直接作为 penalty 进入 `overall`。
2. `confidence/tool_readiness/tool_coverage/fallback_depth` 是工程增强项，设计文档尚未系统吸收。
3. `objective` 当前主要是成本反向项 + objective_ranker bonus，尚不是蛋白设计目标的真正后验期望。

建议在理论 v2 中改写为：

```text
S_static(pi) = w_f F_s(pi) + w_g G(pi;g) - w_c C(pi) - w_r R(pi) - w_rec RC(pi) + w_q Q(pi)
```

其中：

- `F_s` 是软可行性分；
- `F_h` 是硬可行性谓词，先于评分；
- `Q` 可容纳 readiness、coverage、fallback depth 等工程可靠性项。

### 3.3 运行时状态层：`x_t`

代码位置：`src/workflow/belief_state.py:23-228`。

当前五维状态：

```text
x_t = (
  p_success,
  p_structural_failure,
  recovery_margin,
  expected_remaining_cost,
  evidence_sufficiency
)
```

初始化 baseline：

```text
p_success = 0.50
p_structural_failure = 0.25
recovery_margin = 0.60
expected_remaining_cost = 1.00 or total_steps-completed_steps
evidence_sufficiency = 0.50
```

主要更新来源：

- `StepResult.status == success/failed/skipped`
- 结构性步骤 `S2/S3/S4` 或结构工具
- objective ranker 产生的 `objective_progress/objective_gap/objective_evidence_sufficiency`
- structure similarity signal
- `SafetyResult.action == warn/block`
- `RuntimeFailureContext.recovery_action == patch_local/suffix_replan/replan/stop`
- retry exhausted
- completed/total step progress

证据充分度更新：

```text
evidence_signal = 0.40 * cheap_validation_coverage
                + 0.30 * candidate_agreement
                + 0.30 * metric_completeness

evidence_sufficiency_t = 0.70 * evidence_sufficiency_{t-1}
                       + 0.30 * evidence_signal
```

对齐判断：这已经是一个可解释的 Lite belief-state，但它不是严格 Bayesian posterior。论文中不应声称它是精确后验，只应表述为：

> a low-dimensional belief surrogate / deterministic belief update used as an auditable approximation of latent workflow viability.

中文可写作：

> 低维 belief 代理状态，用确定性可审计更新近似不可观测的工作流可行性、结构性失败压力与恢复余量。

### 3.4 runtime adjustment 层：`Delta(pi,x_t)`

代码位置：

- `src/workflow/runtime_evaluator.py:92-171`
- `src/agents/planner.py:2539-2639`

当前公式可归纳为：

```text
budget_pressure = clip(expected_remaining_cost, 0, 1.5)
cost_pressure = min(budget_pressure, 1.0)
margin_signal = clip(recovery_margin, -1, 1)

evidence_effect = 0.18 * (p_success - 0.5) * confidence
evidence_sufficiency_effect = 0.10 * (2*evidence_sufficiency - 1) * max(confidence, feasibility)
risk_effect = -0.16 * p_structural_failure * (1 - risk)
recovery_effect = 0.10 * recovery_margin * fallback_depth
cost_effect = -0.14 * cost_pressure * (1 - cost)

Delta = evidence_effect + evidence_sufficiency_effect + risk_effect + recovery_effect + cost_effect
```

随后按 shadow action 加修正：

```text
if patch_local:
  Delta += 0.04 * fallback_depth
if suffix_replan:
  Delta += 0.02 * feasibility - 0.03 * cost_pressure
if stop:
  Delta -= 0.12 + 0.06 * cost_pressure
Delta = clip(Delta, -0.35, 0.35)
final_score = clip(static_overall + Delta, 0, 1)
```

对齐判断：实现有完整公式，但设计文档中 `planner.algorithm.runtime_adjustment_formula` 的 SID 目前只切到了标题，缺少正文公式。需要在设计文档或论文理论 v2 中补齐。

论文建议表达：

```text
U_pi(pi,x_t) = S_static(pi) + Delta(pi,x_t)
pi_t^* = argmax_{pi in Pi_t} U_pi(pi,x_t)
```

并说明 `Delta` 是 bounded runtime correction，避免单次观测过度推翻静态结构质量。

### 3.5 动作效用层：`U_a(a,x_t)`

代码位置：`src/workflow/runtime_evaluator.py:313-373`。

代码与设计文档 `algo.schema.action_utility` 基本一致：

```text
U_continue = 0.38*s + 0.14*e + 0.12*r - 0.22*f - 0.14*b
U_patch_local = 0.20*s + 0.24*r + 0.18*lp + 0.12*er - 0.14*f - 0.12*b
U_suffix_replan = 0.18*(1-s) + 0.20*f + 0.16*(1-r) + 0.18*pp + 0.14*br + 0.14*gr
U_stop = 0.32*(1-s) + 0.24*b + 0.18*(1-r) + 0.16*st + 0.10*(1-iv)
```

变量：

- `s = p_success`
- `f = p_structural_failure`
- `r = recovery_margin`
- `e = evidence_sufficiency`
- `b = budget_pressure`
- `lp = local_patchability`
- `er = evidence_reusability`
- `pp = prefix_preservability`
- `br = budget_relief`
- `gr = goal_realignment`
- `st = safety_terminality`
- `iv = intervention_value`

主要缺口：后 7 个派生变量在设计中出现，但代码多数从 runtime state mapping 读取默认值，或在 `recovery._derive_runtime_action_features()` 里启发式推导。论文需要给出派生定义，否则公式看起来比实现更“理论化”。

### 3.6 恢复动作选择层

代码位置：`src/workflow/recovery.py:184-410`。

实际选择顺序：

1. 解析 phase allowed actions；
2. 解析 runtime policy；
3. 读取 runtime summary 五维状态；
4. 派生 `budget_pressure/intervention_value/prefix_preservability/local_patchability/u_stop`；
5. 解析 failure signal 与 S6 默认恢复动作；
6. safety blocked 且不满足 stop → suffix_replan；
7. suggested_action 可用且不被硬阻止 → suggested_action；
8. 无 failure signal → continue；
9. 满足 stop 门槛 → stop；
10. 局部可修且 S6 倾向 patch → patch_local；
11. 结构性失败或 S6 倾向 replan → suffix_replan；
12. 否则 continue。

设计对齐：硬优先级与 stop 语义基本一致。

需要在 D4 重点审查：`RuntimeEvaluator.select_action()` 与 `recovery.select_workflow_action()` 都能选择动作，但实际 workflow 主路径看起来是 recovery selector。理论文档中应避免同时宣称两个主决策器。

### 3.7 stop 语义

代码位置：

- `src/workflow/recovery.py:413-458`：构造 terminal stop candidate；
- `src/workflow/recovery.py:489-493`：识别 terminal stop candidate；
- `src/workflow/recovery.py:496-511`：解析 terminal reason。

实现对齐设计：

```text
terminal_policy = stop
replan_mode = suffix_replan
terminal_reason in {economic_stop, evidence_exhausted, unsafe_to_continue, recovery_exhausted}
terminal_status = FAILED
```

这与设计中“不映射 CANCELLED”的语义一致。

## 4. 设计—实现不一致清单

### 4.1 Feasibility 是硬约束还是分数

设计说：

> 任一静态 infeasible 候选必须直接淘汰。

代码现状：

- missing/blocked/safety/cost/io/readiness 过滤在 `CandidateGenerator._filter_reason()` 中完成；
- `_score_payload()` 仍计算连续 `feasibility`；
- `RuntimeEvaluator.evaluate_candidates()` 只保证 `feasibility=0` 不复活；
- `io_not_closed/tool_unavailable` 有 soft fallback 机制。

建议理论 v2 分成：

```text
F_h(pi,C,K,h_t) in {0,1}      # hard feasibility predicate
F_s(pi,C,K,h_t) in [0,1]      # soft feasibility score
```

最终候选集合：

```text
Pi_t = { pi in Pi_raw | F_h(pi,C,K,h_t)=1 }
```

排序时再使用 `F_s`。

### 4.2 Objective score 的蛋白设计含义不足

设计目标中的 `GoalFit` 应表达蛋白设计目标达成度，例如稳定性、结构质量、功能、结合、novelty 等。

代码现状：

- 静态 `_score_payload().objective` 主要是 `1 - avg_cost*0.3 + objective_bonus`；
- 后验目标评分在 `objective_ranker_adapter.py` 中较丰富，但作为工具输出存在，没有统一并入 planner 静态 objective 的理论定义；
- belief-state 会消费 `objective_progress/objective_gap/objective_evidence_sufficiency`，但这条链路需要明确文档化。

建议理论 v2：把 `GoalFit` 定义为 posterior objective expectation：

```text
G(pi;g,o_t) = sum_m lambda_m(g) * q_m(pi,o_t) * rho_m(o_t)
```

其中 `q_m` 是目标维度分数，`rho_m` 是 evidence reliability/directness 权重。

### 4.3 `RecoveryComplexity` 已输出但没有明确进入静态 overall

代码输出：`recovery_complexity = 1 - fallback_depth`。

但静态 overall 默认项中使用的是 `fallback_depth`，不是 `- recovery_complexity`。

这不是错误，但论文必须统一符号：

```text
Rec(pi) = 1 - fallback_depth(pi)
```

那么使用 `+ w_fd * fallback_depth` 与使用 `- w_rec * Rec` 等价，前提是权重和常数项说明清楚。

### 4.4 两套效用函数需要统一

当前有三类分数：

1. static score：排序候选；
2. runtime adjustment/final score：运行时重排候选；
3. action utility：选择控制动作。

建议论文结构：

```text
Candidate utility:
U_pi(pi,x_t) = S_static(pi) + Delta(pi,x_t)

Control action utility:
U_a(a,x_t,Pi_t,h_t) = weighted action value under recovery constraints

Decision:
if hard_priority applies:
    select hard action
else:
    a_t = argmax_a U_a(a,x_t,Pi_t,h_t)
    pi_t^* = argmax_pi U_pi(pi,x_t) when action requires candidate selection
```

### 4.5 `runtime_adjustment_formula` 设计文档 SID 内容缺失

通过 doc-slicer 获取 `planner.algorithm.runtime_adjustment_formula` 时，只得到标题和 SID，没有公式正文。这会影响“设计—实现—论文”的可追踪性。

建议：在理论 v2 文档中先补充正式公式；如果后续要回写设计仓库，再把公式同步到 `runtime-adaptation-formalization.md`。

### 4.6 action utility 派生变量来源不足

`local_patchability/evidence_reusability/prefix_preservability/budget_relief/goal_realignment/safety_terminality/intervention_value` 在公式中重要，但代码默认值较多。

需要在 D4 检查：

- 哪些变量来自 `runtime_summary`；
- 哪些变量来自 `recovery._derive_runtime_action_features()`；
- 哪些变量目前只是默认值；
- 是否需要在论文中把未实现变量标注为 derived heuristic / optional signal。

## 5. 建议的论文算法结构映射

后续 D2 理论 v2 可以采用以下章节结构。

### 5.1 Problem Setting

```text
Given goal g, constraints C, tool capability graph K, execution history h_t,
and observations o_t, select a workflow/control action that maximizes expected
scientific utility under cost, risk, and recoverability constraints.
```

中文：

> 给定设计目标、约束、工具能力图、执行历史与运行时观测，系统需要在预算、风险和可恢复性约束下，选择下一条工具链候选或恢复控制动作。

### 5.2 Candidate Space

```text
Pi_raw = G(g,C,K,h_t)
Pi_t = { pi in Pi_raw | F_h(pi,C,K,h_t)=1 }
```

其中 `G` 对应 planner/candidate generator，`F_h` 对应 hard filter。

### 5.3 Static Utility

```text
S_static(pi) = w_f F_s(pi) + w_g G(pi;g) - w_c C(pi) - w_r R(pi) - w_rec Rec(pi) + w_q Q(pi)
```

### 5.4 Belief State Update

```text
x_t = (s_t, f_t, r_t, c_t, e_t)
x_{t+1} = clip(A x_t + B phi(o_t,h_t))
```

当前代码是手写规则，可在论文中抽象为 deterministic belief surrogate update。

### 5.5 Runtime Candidate Utility

```text
U_pi(pi,x_t) = clip(S_static(pi) + Delta(pi,x_t), 0, 1)
```

### 5.6 Control Action Utility

```text
A = {continue, patch_local, suffix_replan, stop}
a_t = argmax_a U_a(a,x_t,Pi_t,h_t)
```

硬优先级覆盖：safety block、schema violation、retry exhausted、prefix preservability、auto-stop gate。

### 5.7 Decision Output

输出之一：

- continue with current/default candidate；
- patch_local；
- suffix_replan；
- terminal_stop candidate；
- HITL confirmation if stop is not auto-permitted。

## 6. D4 需要重点验证的代码问题

1. `RuntimeEvaluator.select_action()` 是否实际被主 workflow 使用，还是只有 `recovery.select_workflow_action()` 生效。
2. `recovery._derive_runtime_action_features()` 中派生变量是否与 action utility 公式一致。
3. `objective_ranker_adapter` 的 `posterior_score.evidence_sufficiency` 是否稳定进入 `StepResult.metrics`，再进入 belief-state。
4. `score_breakdown.recovery_complexity` 是否应进入 `_DEFAULT_SCORE_WEIGHTS`，或在论文中解释为与 `fallback_depth` 等价。
5. `io_not_closed/tool_unavailable` soft fallback 是否需要在论文中定义为 degraded feasible。
6. `stop` 被接受后的最终 FSM 状态与 `terminal_reason` 是否完整落盘。
7. runtime policy `dynamic_observation_only` 与 `lite_belief_state` 的实验对照是否与论文实验设计一致。

## 7. 当前可追踪性结论

当前系统已经具备 CEBRA-WP 的工程雏形：

```text
candidate generation -> hard/soft constraint filtering -> static scoring
-> lite belief-state update -> runtime rerank -> recovery-aware action selection
-> HITL / stop / patch / suffix replan
```

但论文算法还需要进一步深化为一个统一、可证明边界清晰的形式化方法：

1. 把候选效用 `U_pi` 和控制动作效用 `U_a` 分层；
2. 把 hard feasibility 与 soft feasibility 分离；
3. 把 posterior objective scoring 纳入 GoalFit；
4. 把 Lite belief-state 明确表述为 deterministic belief surrogate，而不是严格 Bayesian posterior；
5. 把恢复控制动作解释为 constrained recovery policy；
6. 用相关论文支撑：POMDP/belief-state planning、budgeted/risk-aware planning、LLM tool-use planning、scientific workflow recovery、protein design objective/reward modeling。

这些内容将在后续 D2/D3/D4 文档中展开。
