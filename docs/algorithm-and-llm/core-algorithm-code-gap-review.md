# CEBRA-WP 当前代码差距审查（P0/P1/P2）

- 生成日期：2026-05-05
- 对应计划项：D4 `core-algorithm-code-gap-review.md`
- 审查目标：对照 D1 可追踪矩阵、D2 理论 v2 与当前实现，识别“论文理论表达 ↔ 代码实现”之间的差距。
- 审查原则：本文件只做审查和优化建议，不修改业务代码；进入实现前应先讨论方案。

## 1. 总体判断

当前代码已经具备 CEBRA-WP 的主体骨架：

1. 候选生成与 Top-K：`src/agents/candidate_generator/generator.py`
2. 硬可行性过滤：`CandidateGenerator._filter_reason()`
3. 静态评分：`src/agents/planner.py::_score_payload()` 及候选 metadata
4. Lite belief-state：`src/workflow/belief_state.py`
5. runtime rerank：`src/workflow/runtime_evaluator.py::compute_runtime_delta()`
6. action utility：`RuntimeEvaluator.compute_action_utilities()`
7. recovery action selection：`src/workflow/recovery.py::select_workflow_action()`
8. terminal stop candidate：`build_terminal_stop_candidate()`
9. posterior objective scoring：`src/adapters/objective_ranker_adapter.py`

因此，系统不是“没有算法实现”，而是存在以下问题：

- 理论对象已经分散实现，但统一命名、公式来源、schema 显式性不足；
- posterior objective scoring 与 planner 主评分之间耦合不够强；
- 一些理论派生变量已在 action utility 中使用，但实际来源多为默认值或弱规则；
- stop、runtime evaluator、recovery selector 存在部分职责重叠，需要明确主从关系；
- 当前实现更像“工程启发式集合”，还需要整理成可论文证明/解释的统一算法。

## 2. 优先级定义

| 优先级 | 定义 | 处理建议 |
|---|---|---|
| P0 | 若不处理，会影响论文中算法定义与代码实现的一致性，或导致关键理论公式无法落地 | 应在论文定稿/实验前处理 |
| P1 | 不阻断算法主线，但会削弱理论深度、实验解释力或长期可维护性 | 建议排入下一轮实现 |
| P2 | 表达、文档、实验增强项；不影响当前系统可运行性 | 视时间处理 |

## 3. P0 差距

### P0-1：`F_h` / `F_s` / `degraded_feasible` 没有显式统一建模

#### 当前证据

`CandidateGenerator.generate()` 中存在硬过滤和 soft filtered 行：

```text
filtered_rows = []
soft_filtered_rows = []
reason = self._filter_reason(...)
if reason is not None:
    if reason in {"io_not_closed", "tool_unavailable"}:
        soft_filtered_rows.append(row)
    continue
filtered_rows.append(row)
```

`_filter_reason()` 已覆盖：

```text
missing_tools
tool_not_allowed
tool_blocked
safety_level_exceeded
cost_level_exceeded
io_not_closed
tool_unavailable
```

#### 差距

理论 v2 区分：

```text
F_h(pi,C,K,h_t) ∈ {0,1}
F_s(pi,C,K,h_t) ∈ [0,1]
degraded_feasible / HITL-required
```

但当前代码中：

- `io_not_closed` 和 `tool_unavailable` 被放入 soft filtered rows；
- soft filtered rows 是否进入 `available_rows` 取决于 `_available_rows()`，但 metadata 中没有明确标注 `degraded_feasible`、`requires_hitl`、`hard_feasibility`；
- 论文中的 `F_h` 与代码中的 filter reason 映射不够显式。

#### 风险

论文若写“硬不可行候选不会自动执行”，需要代码中能清楚解释：

- 哪些是 hard infeasible；
- 哪些是 degraded feasible；
- degraded candidate 是否只允许 HITL；
- default recommendation 是否可能来自 soft filtered row。

如果不澄清，评审容易质疑公式与实现不一致。

#### 建议

新增或标准化候选 metadata：

```text
feasibility = {
  hard_feasible: bool,
  degraded_feasible: bool,
  requires_hitl: bool,
  filter_reason: str | null,
  feasibility_source: "candidate_generator.v1"
}
```

并明确策略：

```text
hard_feasible=false 且 degraded_feasible=false -> discard
hard_feasible=false 且 degraded_feasible=true -> may display, requires HITL, cannot auto-execute
hard_feasible=true -> eligible for auto default recommendation
```

实现位置建议：

- `src/agents/candidate_generator/generator.py`
- `src/models/runtime_schemas.py` 或候选 metadata schema 附近

---

### P0-2：posterior objective score 与 planner 主评分未形成稳定闭环

#### 当前证据

`objective_ranker_adapter.py` 已有 posterior 组件：

```text
_POSTERIOR_COMPONENTS = (
  generic_objective,
  stability,
  novelty,
  function,
  binding,
  structure_quality,
)
```

并通过：

```text
objective_score = sum(_component_effective_score(component) * weights[key])
posterior_score = _build_posterior_score(...)
evidence_sufficiency = direct_weight + 0.5 * proxy_weight
```

同时 adapter 会写：

```text
metrics["objective_progress"]
metrics["objective_gap"]
metrics["evidence_sufficiency"]
```

#### 差距

理论 v2 中目标评分是：

```text
G_post(pi;g,o_t) = Σ λ_m(g) · ρ_m(o_t) · q_m(pi,o_t)
```

但当前 planner 静态评分中的 objective 项主要来自：

- planner payload/score metadata；
- objective ranker bonus；
- 低成本偏好/规则特征。

缺口在于：

1. `objective_ranker_adapter` 输出的 `posterior_score.aggregate_score` 没有被明确作为 `G_post` 的唯一/主要来源；
2. `evidence_sufficiency` 进入 belief-state 的路径需要确认稳定覆盖所有 workflow；
3. planner score breakdown 中 `objective` 与 posterior score 公式来源没有统一 schema；
4. `binding` 组件存在于 `_POSTERIOR_COMPONENTS`，但 `_build_posterior_score()` payload 当前只显式包含 generic/stability/function/novelty/structure_quality，需核查是否遗漏 `binding` 字段输出。

#### 风险

论文会把证据感知目标评分作为核心理论贡献之一。如果代码只是“objective_ranker 单独排候选”，而 planner 仍用弱 objective heuristic，则贡献会显得没有落到主决策链。

#### 建议

建立统一字段：

```text
metadata["posterior_objective"] = {
  aggregate_score,
  components,
  component_weights,
  evidence_sufficiency,
  evidence_status,
  source_refs
}
```

并在 planner score 中明确：

```text
score_breakdown.objective = posterior_objective.aggregate_score
score_breakdown.evidence_sufficiency = posterior_objective.evidence_sufficiency
```

若无 posterior evidence，则显式降级：

```text
objective_source = "prior_goal_fit" | "posterior_objective" | "degraded_proxy"
```

实现位置建议：

- `src/adapters/objective_ranker_adapter.py`
- `src/agents/planner.py::_score_payload()`
- `src/workflow/belief_state.py`

---

### P0-3：Action Utility 中多个派生变量目前可能长期使用默认值

#### 当前证据

`RuntimeEvaluator.compute_action_utilities()` 读取：

```text
local_patchability = state.get("local_patchability", 0.5)
evidence_reusability = state.get("evidence_reusability", 0.5)
prefix_preservability = state.get("prefix_preservability", 0.5)
budget_relief = state.get("budget_relief", 0.5)
goal_realignment = state.get("goal_realignment", 0.5)
safety_terminality = state.get("safety_terminality", 0.0)
intervention_value = state.get("intervention_value", 0.0)
```

然后计算：

```text
U_continue
U_patch_local
U_suffix_replan
U_stop
```

#### 差距

理论 v2 将这些变量作为恢复动作选择的重要输入，但当前需要确认：

- 它们是否总能从 `belief_state` 或 `recovery._derive_runtime_action_features()` 稳定产生；
- 若没有产生，默认 0.5 会让公式看似完整但实际区分度不足；
- `intervention_value` 默认 0.0 会提高 stop 倾向，因为 `U_stop` 使用 `0.10 * (1 - iv)`。

#### 风险

Action Utility 可能在论文中很漂亮，但实验中动作选择主要由 failure/safety hard priority 决定，软效用变量的贡献较弱。

#### 建议

为每个派生变量定义明确来源：

```text
local_patchability      <- failure_type, retry_count, schema_error/local_error, patch_history
prefix_preservability   <- completed_step_count, validated_outputs, failed_step_index
evidence_reusability    <- evidence_refs coverage, objective_ranker evidence_sufficiency
budget_relief           <- estimated_cost(current_suffix) - estimated_cost(replanned_suffix)
goal_realignment        <- objective_gap, missing_objective_components, candidate diversity
safety_terminality      <- safety block type, tool risk class
intervention_value      <- HITL availability, ambiguity, expected saved cost
```

实现位置建议：

- `src/workflow/belief_state.py`
- `src/workflow/recovery.py::_derive_runtime_action_features()`
- `src/workflow/runtime_evaluator.py`

---

### P0-4：`RuntimeEvaluator.select_action()` 与 `recovery.select_workflow_action()` 职责边界需要收敛

#### 当前证据

`RuntimeEvaluator` 内有：

```text
select_action(...)
compute_action_utilities(...)
_should_auto_stop(...)
_best_utility(...)
```

`recovery.py` 也有：

```text
select_workflow_action(...)
_should_choose_stop(...)
safety_blocked hard priority
patch_local / suffix_replan routing
terminal_stop candidate construction
```

#### 差距

理论 v2 只有一个动作选择器：

```text
a_t = HardPriority(U_a,x_t,h_t,C) or argmax U_a
```

当前实现中存在两个相近入口：

- `RuntimeEvaluator.select_action()` 更偏 utility 计算；
- `recovery.select_workflow_action()` 更偏工作流路由和 hard priority。

如果两者同时参与不同路径，可能出现：

- action utility 推荐 A；
- recovery selector 因 hard priority 或 suggested_action 选择 B；
- metadata 解释不一致。

#### 风险

论文中很难解释“到底哪个模块实现了 `a_t`”。测试也容易覆盖一条路径，遗漏另一条路径。

#### 建议

明确主从关系：

方案 A（推荐）：

```text
RuntimeEvaluator.compute_action_utilities() 只负责算 U_a
recovery.select_workflow_action() 是唯一动作选择入口
```

其中 recovery selector：

1. 读取 `ActionUtility`；
2. 应用 hard priorities；
3. 生成 route / terminal_stop / HITL metadata。

方案 B：

```text
RuntimeEvaluator.select_action() 成为唯一动作选择入口
recovery.py 只负责 route/candidate construction
```

但方案 B 改动更大，不建议当前阶段采用。

---

### P0-5：设计 SID 与代码 source refs 还没有完全稳定对齐

#### 当前证据

代码中存在 source refs：

```text
runtime_evaluator.action_utility.v1
planner.runtime_adjustment.{shadow_action}.v1
score_breakdown.overall+runtime_state.{shadow_action}.v1
posterior_score.v1
```

D1 中设计 SID 包括：

```text
algo.adaptive.optimization_objective
planner.algorithm.runtime_adjustment_formula
algo.schema.action_utility
```

#### 差距

source ref 与设计 SID 不完全同名，导致追溯链需要人工解释。

#### 风险

如果论文/设计/代码要形成可审计链路，最好能从候选 metadata 直接追踪到设计对象。

#### 建议

在 metadata 中增加：

```text
design_refs = [
  "algo.adaptive.optimization_objective",
  "planner.algorithm.runtime_adjustment_formula",
  "algo.schema.action_utility"
]
```

或者统一 source ref：

```text
source_refs=["sid:algo.schema.action_utility", "impl:runtime_evaluator.action_utility.v1"]
```

## 4. P1 差距

### P1-1：静态评分公式中的 `recovery_complexity` 与权重表达不够显式

当前静态评分中有 fallback/readiness/coverage 等信号，但 D2 公式中有：

```text
- w_rec Rec(pi)
```

建议：

- 将 `recovery_complexity` 明确输出到 `score_breakdown`；
- 若当前等价于 `1 - fallback_depth`，在 metadata 中显式标注；
- 后续实验可以证明 fallback/recovery 对成功率或成本的影响。

### P1-2：runtime delta 缺少 `ActionBias` 命名层

当前 `compute_runtime_delta()` 已有：

```text
patch_local bonus
suffix_replan bonus/penalty
stop guard penalty
```

这对应 D2 中：

```text
κ_a · ActionBias(pi,x_t)
```

但代码中未统一命名为 `ActionBias`。建议把这些 bonus/penalty 汇总到 metadata：

```text
action_bias = {
  action,
  value,
  factors
}
```

这样论文公式和代码解释更一致。

### P1-3：`expected_remaining_cost` 既像成本又像 budget pressure，单位语义需要统一

当前 `compute_runtime_delta()` 中：

```text
budget_pressure = min(max(expected_remaining_cost, 0.0), 1.5)
cost_pressure = min(budget_pressure, 1.0)
```

Action Utility 中也直接用 expected_remaining_cost 形成 `b`。

建议明确：

```text
expected_remaining_cost: 原始估计，可非 [0,1]
budget_pressure: 归一化 [0,1] 或 clipped [0,1.5]
```

并在 schema 中分开，避免论文公式 `b_t` 与实现字段混用。

### P1-4：belief-state 更新规则需要文档化为 `B(x_t,o_t,h_t)`

状态：已补齐。`core-algorithm-theory-v2.md §5.3` 已加入可引用的
`B(x_t,o_t,h_t)` 更新表，代码侧由
`src/workflow/belief_state.py::BELIEF_STATE_UPDATE_RULES` 承载同一组信号。

`belief_state.py` 已实现五维状态更新，论文现在明确：

- 每个观测如何影响 `p_success`；
- 哪些 failure type 提高 `p_structural_failure`；
- recovery history 如何降低 `recovery_margin`；
- evidence_sufficiency 如何平滑更新。

该表避免只有 D2 文档里有数学表达，同时给测试和论文表述提供稳定引用点。

### P1-5：Top-K diversity 的理论解释可以增强

状态：已补齐。理论 v2 已将 Top-K 写为：

```text
TopK_t = SelectDiverseTopK(Pi_t, U_pi, k, capability_coverage)
```

工程侧 `_select_diverse_top_k()` 继续使用 capability-bucket round-robin，
并在候选 metadata 中写入 `topk_diversity`，记录 `strategy`、
`selected_by`、`diversity_signals`、`selection_mode` 和退化原因。

当前候选生成使用 `_select_diverse_top_k()`，这不再只是工程点，而是 CEBRA-WP
保留替代路径、降低单一路径偏置的 Top-K 约束。

等价的论文表述可写为：

```text
TopK_t = arg top-k under U_pi with capability diversity constraint
```

或者：

```text
DiversityPenalty(pi_i, pi_j)
```

这样 Top-K 不只是排序，而是保留替代路径的探索价值。

### P1-6：`binding` posterior component 需要检查输出一致性（已补齐）

结论：当前版本不引入独立 `binding` posterior component。`_POSTERIOR_COMPONENTS`
保持为：

```text
generic_objective
stability
function
novelty
structure_quality
```

`binding` objective type 仍可作为权重预设存在，但 binding 证据通过
`binding_score` / `best_pose` 折叠为 `generic_objective` 的 proxy evidence。
为避免“权重存在但输出缺失”的歧义，posterior payload 显式记录：

```text
binding_policy = "folded_into_generic_objective"
binding_evidence = {source, role, target_component, source_fields}
```

这意味着论文/schema/测试的唯一表述是：

```text
binding ∉ M_v1
binding_evidence -> generic_objective proxy
```

若未来要新增一等 `binding` component，必须作为 schema version 升级处理。

### P1-7：实验配置与 runtime policy mode 需要对应理论消融（已补齐）

`RuntimeEvaluator` 支持：

```text
static_top1
static_gate
dynamic_observation_only
lite_belief_state
```

这是天然实验消融。当前已固定代码 mode、论文组 ID、预期行为与重点指标的映射，
代码侧 SSOT 为 `src.workflow.runtime_evaluator.RUNTIME_POLICY_ABLATION_GROUPS`，
文档侧 SSOT 为 `docs/experiment/algorithm-group-paper-mapping.md`。

| 代码 mode | 论文组 ID | 对应消融 |
|---|---|---|
| `static_top1` | `static_top1` | 静态单链基线 |
| `static_gate` | `fixed_threshold_gate` | 静态门控基线 |
| `dynamic_observation_only` | `dynamic_no_belief_state` | 动态观测但不使用 belief-state |
| `lite_belief_state` | `lite_belief_state` | 完整 CEBRA-WP |

## 5. P2 差距

### P2-1：公式版本号和文档版本号可以统一（已补齐）

当前有：

```text
posterior_score.v1
planner.runtime_adjustment.*.v1
runtime_evaluator.action_utility.v1
```

已建立三级版本表：

```text
cebra_wp.v2
├─ static_score.v1
├─ posterior_score.v1
├─ runtime_adjustment.v1
├─ action_utility.v1
└─ action_bias.v1
```

总表位置：

- `src.models.algorithm_versions`
- `docs/algorithm-and-llm/algorithm-version-registry.md`
- `docs/algorithm-and-llm/core-algorithm-theory-v2.md` §0

### P2-2：候选解释可以更贴近论文术语（已补齐）

当前解释偏工程：

```text
Local patchability keeps more recovery options available.
Suffix replan still carries residual budget pressure.
```

已在 `RuntimeAdjustmentFactor` 中补充理论字段，同时保留工程原文：

```text
term = "recovery_margin" | "budget_pressure" | "evidence_sufficiency" | "ActionBias" | "recoverability"
formula_ref = "Eq.(runtime_delta)" | "Eq.(ActionBias)"
message = 原工程解释
```

因此论文图注/UI 简版可以显示 `term + formula_ref`，调试展开层继续显示
`message`。

### P2-3：文献映射可进入代码注释/设计文档

不建议在业务代码写大量文献，但可在设计文档中补：

```text
POMDP-inspired belief surrogate
CMDP-inspired hard constraints
Evidence-weighted posterior objective
```

### P2-4：可视化/调试面板可展示理论对象

如 UI 后续需要展示算法解释，可只显示：

- `static_score`
- `runtime_adjustment`
- `final_score`
- `selected_action`
- `action_utility`
- `evidence_sufficiency`

不要在 inspector 展开复杂字段列表，避免和当前 UI 约束冲突。

### P2-5：参考文献 BibTeX 需要最终核验

D3 已说明 Semantic Scholar/API 本轮限流。论文定稿前需要补齐：

- DOI；
- 会议/期刊版本；
- arXiv version；
- BibTeX key；
- 2026 预印本是否保留。

## 6. 建议实施顺序

### 第一轮：理论一致性最小闭环（推荐先做）

1. 显式 feasibility metadata：`F_h/F_s/degraded_feasible/requires_hitl`。
2. 将 posterior objective score 统一接入 planner `score_breakdown.objective`。
3. 明确 action selection 主入口：推荐 `recovery.select_workflow_action()` 为唯一选择器。
4. 补齐 `binding` posterior 输出或说明。
5. 补充 source refs / design refs。

### 第二轮：恢复变量增强

1. 为 `local_patchability`、`prefix_preservability` 等派生变量补稳定计算。
2. 分离 `expected_remaining_cost` 与 `budget_pressure`。
3. 将 `ActionBias` 显式进入 runtime adjustment metadata。
4. 文档化 belief update table。

### 第三轮：实验与论文支撑

1. 使用 runtime policy mode 做消融。
2. 对比 static vs dynamic vs belief-state。
3. 做成本节省、无效调用减少、恢复成功率、证据充分度提升等指标。
4. 核验并整理 BibTeX。

## 7. 最小实现提案草案（供后续讨论，不在本轮执行）

### 7.1 数据结构

新增或标准化候选 metadata：

```python
feasibility = {
    "hard_feasible": True,
    "degraded_feasible": False,
    "requires_hitl": False,
    "filter_reason": None,
    "hard_constraints": ["tool", "schema", "io", "safety", "cost", "availability"],
    "source_refs": ["sid:algo.adaptive.feasibility_filter", "impl:candidate_generator.v1"],
}
```

新增 objective source：

```python
posterior_objective = {
    "aggregate_score": 0.73,
    "evidence_sufficiency": 0.65,
    "evidence_status": "partial",
    "components": {...},
    "source_refs": ["sid:algo.posterior_objective_scoring", "impl:posterior_score.v1"],
}
```

### 7.2 主流程

推荐主从关系：

```text
CandidateGenerator -> RuntimeEvaluator.evaluate_candidates -> recovery.select_workflow_action
```

其中：

- `RuntimeEvaluator` 只负责 runtime score 和 action utility；
- `recovery.select_workflow_action` 负责 hard priorities、route 与 terminal candidate；
- Planner 负责把结果写入 decision metadata。

### 7.3 测试重点

如果后续实现，建议最少补这些测试：

1. hard infeasible candidate 不会成为 default recommendation；
2. degraded feasible candidate 必须带 `requires_hitl=true`；
3. posterior objective score 能改变 planner objective score；
4. missing binding component 输出不丢失；
5. safety blocked 禁止 continue；
6. stop 只有满足 auto-stop guard 才自动选择；
7. runtime policy mode 四种模式行为可区分。

## 8. 结论

当前实现已经能支撑 CEBRA-WP 的算法雏形，尤其是 Top-K 候选、静态评分、runtime delta、Action Utility 和 terminal stop 都已有实际代码。但如果目标是提高论文理论深度并让代码成为理论的可执行证据，优先需要处理 P0：

```text
1. 显式化可行性语义；
2. 打通 posterior objective scoring 与 planner 主评分；
3. 稳定 Action Utility 派生变量来源；
4. 收敛 action selection 主入口；
5. 统一设计 SID / source refs。
```

这些修改不需要大规模重构，但需要谨慎设计 schema 和测试。建议下一步先讨论 P0-1/P0-2/P0-4 的实现方案，再让 Codex 进行小步实现。
