# CEBRA-WP P0 实现方案讨论稿

- 生成时间：2026-05-05 02:13:58
- 阶段：计划阶段已结束；进入实现方案细化阶段
- 范围：仅整理已确认的 P0 方案，不修改业务代码
- 上游文档：
  - `docs/algorithm-and-llm/core-algorithm-code-gap-review.md`
  - `docs/algorithm-and-llm/core-algorithm-theory-v2.md`
  - `docs/algorithm-and-llm/core-algorithm-design-code-traceability.md`
  - `docs/algorithm-and-llm/core-algorithm-literature-map.md`

## 1. 已确认决策

用户已确认采用以下方案：

| P0 项 | 决策 |
|---|---|
| P0-4 action selection 主入口 | 采用 D4 方案 A：`RuntimeEvaluator` 只计算 utility，`recovery.select_workflow_action()` 作为唯一动作选择入口 |
| P0-1 feasibility 语义 | 采用统一 metadata 表达 `F_h / F_s / degraded_feasible / requires_hitl` |
| P0-2 posterior objective | 采用统一输出 `posterior_objective`，并接入 planner 主评分 |
| P0-3 action utility features | 采用确定性派生函数输出 action utility 所需特征 |
| P0-5 SID/source refs | 采用第二种统一命名：每个子对象内使用 `source_refs=[sid:..., impl:...]`；注意设计文档 SID 需要同步更新对照 |

## 2. 总体实现原则

### 2.1 不做大重构

P0 的目标不是重写 planner/recovery，而是让已有实现与 CEBRA-WP 理论对象对齐：

```text
已有工程启发式实现
  -> 显式 schema / metadata / source refs
  -> 单一动作选择边界
  -> posterior objective 接入主评分
  -> 可论文解释、可测试、可追溯
```

### 2.2 先稳定语义，再改变排序/策略

推荐实施顺序：

```text
Phase 1: P0-4 + P0-1 + P0-5 最小闭环
Phase 2: P0-2 posterior objective 接入 planner 主评分
Phase 3: P0-3 action utility 派生变量增强
```

原因：

1. P0-4 决定主流程边界。
2. P0-1/P0-5 主要是 metadata 和追踪链，风险较低。
3. P0-2 会改变候选排序，必须单独测试。
4. P0-3 会改变恢复动作选择，也应单独测试。

### 2.3 所有新字段必须可审计

新增字段应包含：

```text
value
source_refs
reason / explanation
schema_version / formula_version where useful
```

避免只有数值没有来源。

## 3. P0-4：单一 recovery-aware action selection 边界

### 3.1 目标

明确系统中只有一个主入口负责最终恢复动作选择：

```text
recovery.select_workflow_action()
```

`RuntimeEvaluator` 只负责：

```text
compute_runtime_delta()
evaluate_candidates()
compute_action_utilities()
```

不再作为主流程的最终动作选择器。

### 3.2 模块职责

#### RuntimeEvaluator

职责：计算分数和效用。

保留：

```python
RuntimeEvaluator.evaluate_candidates(...)
RuntimeEvaluator.compute_action_utilities(...)
compute_runtime_delta(...)
```

弱化或兼容保留：

```python
RuntimeEvaluator.select_action(...)
RuntimeEvaluator._should_auto_stop(...)
RuntimeEvaluator._best_utility(...)
```

初期不强删，避免破坏现有调用。可以采用以下策略：

```text
1. 主流程不再调用 RuntimeEvaluator.select_action()
2. 保留函数作为 deprecated/internal compatibility path
3. 测试覆盖主流程只从 recovery.select_workflow_action() 产生 selected_action
```

#### recovery.select_workflow_action

职责：唯一动作选择和 route 决策。

应负责：

```text
1. 接收 runtime_state_summary
2. 接收或派生 action_utilities
3. 应用 hard priorities
4. 选择 selected_action
5. 输出 WorkflowActionRoute
6. 生成 terminal_stop / HITL 相关 metadata
```

### 3.3 数据流

推荐主路径：

```text
CandidateGenerator
  -> RuntimeEvaluator.evaluate_candidates()
  -> RuntimeEvaluator.compute_action_utilities()
  -> recovery.select_workflow_action()
  -> route / candidate / HITL / terminal_stop
```

### 3.4 metadata 输出建议

动作选择结果应至少包含：

```python
metadata["action_selection"] = {
    "selected_action": "continue" | "patch_local" | "suffix_replan" | "stop",
    "selection_basis": "hard_priority" | "action_utility" | "default_continue" | "observation_only",
    "hard_priority_applied": bool,
    "hard_priority_reason": str | None,
    "action_utilities": {...},
    "source_refs": [
        "sid:algo.recovery_aware_action_selection",
        "impl:recovery.select_workflow_action.v1",
    ],
}
```

### 3.5 验收标准

- 主流程最终 `selected_action` 只由 `recovery.select_workflow_action()` 决定。
- `RuntimeEvaluator.compute_action_utilities()` 只提供候选动作效用，不覆盖 route。
- safety block、auto-stop guard、retry exhausted 等 hard priority 只在 recovery selector 中统一解释。
- metadata 能说明：为何选择该 action、是否 hard priority、各动作 utility 值。

### 3.6 待细化问题

1. 当前哪些调用点还在使用 `RuntimeEvaluator.select_action()`？
2. 是直接替换调用点，还是先加 deprecation warning / source ref？
3. `select_workflow_action()` 是否应直接接收 `action_utilities`，还是内部调用 `RuntimeEvaluator.compute_action_utilities()`？

初步建议：直接接收 `action_utilities`，降低模块耦合。

## 4. P0-1：统一 feasibility metadata

### 4.1 目标

让代码显式表达论文中的：

```text
F_h(pi,C,K,h_t)
F_s(pi,C,K,h_t)
degraded_feasible
requires_hitl
```

### 4.2 新 metadata schema

推荐候选 metadata 中新增：

```python
metadata["feasibility"] = {
    "schema_version": "cebra_feasibility.v1",
    "hard_feasible": True,
    "soft_feasibility": 0.82,
    "degraded_feasible": False,
    "requires_hitl": False,
    "filter_reason": None,
    "filter_class": "eligible" | "degraded" | "discarded",
    "hard_constraints": [
        "tool",
        "schema",
        "io",
        "safety",
        "cost",
        "availability",
    ],
    "source_refs": [
        "sid:algo.adaptive.feasibility_filter",
        "impl:candidate_generator.filter_reason.v1",
    ],
}
```

说明：

- `hard_feasible` 对应 `F_h`。
- `soft_feasibility` 对应 `F_s`，可复用当前 `score_breakdown.feasibility`。
- `degraded_feasible` 表示候选可展示但不允许自动执行。
- `requires_hitl` 表示必须人工确认后才能执行。
- `filter_class` 用于快速判定候选状态。

### 4.3 filter reason 分类

建议分类如下：

| filter_reason | filter_class | hard_feasible | degraded_feasible | requires_hitl | 说明 |
|---|---:|---:|---:|---:|---|
| `None` | `eligible` | true | false | false | 正常可执行 |
| `io_not_closed` | `degraded` | false | true | true | 可展示为需补输入/确认的候选，不可自动执行 |
| `tool_unavailable` | `degraded` | false | true | true | 可展示为 fallback/未来可用候选，不可自动执行 |
| `missing_tools:*` | `discarded` | false | false | false | 工具不存在，直接丢弃 |
| `tool_not_allowed` | `discarded` | false | false | false | 用户/任务不允许 |
| `tool_blocked` | `discarded` | false | false | false | 显式阻断 |
| `safety_level_exceeded` | `discarded` | false | false | false | 安全等级不可突破 |
| `cost_level_exceeded` | `discarded` | false | false | false | 硬成本约束不可突破 |

### 4.4 默认推荐规则

推荐规则：

```text
eligible candidate 可成为 default recommendation

degraded candidate 可进入候选解释/替代项，但不得成为 auto default recommendation
除非当前没有 eligible candidate 且 route 进入 HITL-only fallback

discarded candidate 不进入 Top-K 结果
```

若没有 eligible，但有 degraded：

```text
TopKResult 可返回 degraded candidates
但 default_recommendation 应标注 requires_hitl=true
explanation 必须说明 no hard-feasible candidate exists
```

这里需要后续细化：是否允许 degraded candidate 成为 `default_recommendation`？

初步建议：可以成为 UI 上的默认展示项，但必须加：

```text
default_recommendation_mode = "hitl_required"
```

不能被执行器当作自动执行默认值。

### 4.5 验收标准

- 每个进入 Top-K 的候选都有 `metadata.feasibility`。
- discarded candidate 不进入 Top-K。
- degraded candidate 必须 `requires_hitl=true`。
- 自动执行路径必须检查 `hard_feasible=true` 且 `requires_hitl=false`。
- D1 可追踪矩阵能把 `F_h/F_s` 对应到该 metadata。

## 5. P0-2：统一 posterior objective 输出并接入 planner 主评分

### 5.1 目标

将 `objective_ranker_adapter.py` 的 posterior score 从“旁路排序/输出”提升为 planner 主评分中的目标项来源。

理论对应：

```text
G_post(pi;g,o_t) = Σ λ_m(g) · ρ_m(o_t) · q_m(pi,o_t)
```

### 5.2 新 metadata schema

推荐输出：

```python
metadata["posterior_objective"] = {
    "schema_version": "posterior_objective.v1",
    "aggregate_score": 0.73,
    "objective_type": "binder_design" | "stability" | "novelty" | None,
    "components": {
        "generic_objective": {...},
        "stability": {...},
        "novelty": {...},
        "function": {...},
        "binding": {...},
        "structure_quality": {...},
    },
    "component_weights": {...},
    "evidence_sufficiency": 0.65,
    "evidence_status": "direct" | "partial" | "degraded",
    "warnings": [...],
    "evidence_refs": [...],
    "source_refs": [
        "sid:algo.posterior_objective_scoring",
        "impl:posterior_score.v1",
    ],
}
```

### 5.3 planner score 接入

planner score breakdown 应明确：

```python
score_breakdown["objective"] = posterior_objective["aggregate_score"]
score_breakdown["objective_source"] = "posterior_objective"
score_breakdown["evidence_sufficiency"] = posterior_objective["evidence_sufficiency"]
```

若没有 posterior objective：

```python
score_breakdown["objective"] = prior_goal_fit
score_breakdown["objective_source"] = "prior_goal_fit"
score_breakdown["evidence_sufficiency"] = 0.0 or unknown
```

若只有 degraded/proxy：

```python
score_breakdown["objective_source"] = "degraded_proxy" | "proxy_objective"
```

### 5.4 binding component 对齐

当前 D4 提到一个重点核查项：

```text
_POSTERIOR_COMPONENTS 包含 binding
_build_posterior_score() payload 需要显式包含 binding
```

本方案要求 posterior objective 的 `components` 必须完整包含：

```text
generic_objective
stability
novelty
function
binding
structure_quality
```

### 5.5 排序风险控制

posterior objective 接入后会影响候选排序，需避免一票否决。

推荐：

```text
objective 仍作为 score_breakdown 的一个权重项
不直接覆盖 overall score
```

即：

```text
S_static(pi) = Σ w_k score_k(pi)
```

其中 objective 是 `score_k` 之一。

### 5.6 验收标准

- posterior objective 有统一 metadata。
- `binding` component 不丢失。
- planner `score_breakdown.objective` 能明确来源。
- `evidence_sufficiency` 能进入 runtime/belief-state。
- 无 posterior evidence 时不会伪装为 direct evidence。
- 排序变化有测试覆盖。

## 6. P0-3：稳定 Action Utility 派生变量来源

### 6.1 目标

为 Action Utility 中使用的派生变量提供稳定、可解释、可审计的来源。

当前公式使用：

```text
local_patchability
evidence_reusability
prefix_preservability
budget_relief
goal_realignment
safety_terminality
intervention_value
```

### 6.2 新派生函数

推荐增加或标准化函数：

```python
derive_action_features(...) -> dict[str, object]
```

输出：

```python
action_features = {
    "schema_version": "action_features.v1",
    "local_patchability": {"value": 0.7, "source": "inferred", "reason": "schema error is locally patchable"},
    "evidence_reusability": {"value": 0.6, "source": "actual", "reason": "objective evidence exists before failed step"},
    "prefix_preservability": {"value": 0.8, "source": "inferred", "reason": "failure occurs after validated prefix"},
    "budget_relief": {"value": 0.4, "source": "default", "reason": "no suffix cost estimate available"},
    "goal_realignment": {"value": 0.5, "source": "default", "reason": "objective gap unavailable"},
    "safety_terminality": {"value": 0.0, "source": "actual", "reason": "no safety block"},
    "intervention_value": {"value": 0.5, "source": "default", "reason": "HITL value unknown"},
    "source_refs": [
        "sid:algo.action_feature_derivation",
        "impl:recovery.derive_action_features.v1",
    ],
}
```

### 6.3 默认值原则

默认值不能悄悄伪装为实际信号。

推荐值：

| 特征 | unknown/default 建议 | 原因 |
|---|---:|---|
| `local_patchability` | 0.5 | 中性 |
| `evidence_reusability` | 0.5 | 中性 |
| `prefix_preservability` | 0.5 | 中性 |
| `budget_relief` | 0.4 | 没有成本证据时不要过度鼓励 replan |
| `goal_realignment` | 0.5 | 中性 |
| `safety_terminality` | 0.0 | 无 safety block 时不鼓励 stop |
| `intervention_value` | 0.5 | 避免缺省 0.0 人为推高 stop |

### 6.4 派生规则初版

#### local_patchability

高：

```text
schema_error
missing_input
parameter_validation_error
tool_argument_error
```

低：

```text
structural_failure
safety_block
repeated retry exhausted
upstream invalid output
```

#### prefix_preservability

高：

```text
failed_step_index > 0
completed_step_results not empty
validated_outputs exist
failure localized to suffix
```

低：

```text
first step failed
root input invalid
global constraint invalid
```

#### evidence_reusability

高：

```text
posterior_objective.evidence_refs exists
structure prediction metrics exist
similarity results exist
validated prefix outputs exist
```

低：

```text
failure before evidence generation
only degraded evidence exists
```

#### budget_relief

初版规则：

```text
if replanned_suffix_cost_estimate and current_suffix_cost_estimate exist:
    budget_relief = clip((current - replanned) / max(current, eps), 0, 1)
else:
    budget_relief = 0.4 default
```

#### goal_realignment

高：

```text
objective_gap high
missing objective components exist
posterior evidence_status degraded
current route does not cover required objective dimensions
```

#### safety_terminality

高：

```text
safety_blocked true and no allowed fallback
blocked tool required by current route
```

#### intervention_value

高：

```text
multiple viable candidates
ambiguous stop/replan tradeoff
degraded candidates require HITL
```

低：

```text
clear hard infeasible
budget exhausted
no viable candidate
safety terminal
```

### 6.5 ActionUtility 输入形态

`RuntimeEvaluator.compute_action_utilities()` 可以继续读 flat state，但建议 runtime state 中同时保留：

```python
runtime_state["action_features"] = action_features
runtime_state["local_patchability"] = action_features["local_patchability"]["value"]
```

这样兼容现有公式，又保留解释信息。

### 6.6 验收标准

- action utility 每个派生变量都有 value/source/reason。
- unknown/default 明确标记。
- `intervention_value` 默认不再是 0.0。
- patch/replan/stop 决策能从 action_features 解释。
- safety block 和 retry exhausted 仍由 hard priority 覆盖。

## 7. P0-5：统一 SID / source refs 命名

### 7.1 目标

采用第二种统一命名方式：每个子对象内部的 `source_refs` 同时包含设计 SID 和实现版本。

格式：

```text
sid:<design-sid>
impl:<implementation-ref>
```

### 7.2 推荐 source_refs 映射

| 子对象 | source_refs |
|---|---|
| feasibility | `sid:algo.adaptive.feasibility_filter`, `impl:candidate_generator.filter_reason.v1` |
| static score | `sid:algo.adaptive.optimization_objective`, `impl:planner.score_breakdown.v1` |
| posterior objective | `sid:algo.posterior_objective_scoring`, `impl:posterior_score.v1` |
| runtime adjustment | `sid:planner.algorithm.runtime_adjustment_formula`, `impl:planner.runtime_adjustment.v1` |
| action utility | `sid:algo.schema.action_utility`, `impl:runtime_evaluator.action_utility.v1` |
| action feature derivation | `sid:algo.action_feature_derivation`, `impl:recovery.derive_action_features.v1` |
| recovery action selection | `sid:algo.recovery_aware_action_selection`, `impl:recovery.select_workflow_action.v1` |
| terminal stop | `sid:algo.terminal_stop_policy`, `impl:recovery.terminal_stop.v1` |

### 7.3 设计文档 SID 更新要求

需要注意：部分推荐 SID 可能当前设计文档不存在或未完全展开。

后续需要在设计仓库 `../thesis-project.design/` 中同步：

1. 检查现有 SID：
   - `algo.adaptive.optimization_objective`
   - `planner.algorithm.runtime_adjustment_formula`
   - `algo.schema.action_utility`
2. 新增或映射缺失 SID：
   - `algo.adaptive.feasibility_filter`
   - `algo.posterior_objective_scoring`
   - `algo.action_feature_derivation`
   - `algo.recovery_aware_action_selection`
   - `algo.terminal_stop_policy`
3. 更新 D1 可追踪矩阵，保证设计 SID ↔ 代码 source_refs 对齐。

### 7.4 验收标准

- 所有核心 metadata 子对象都有 `source_refs`。
- 每个 `source_refs` 至少包含一个 `sid:` 和一个 `impl:`。
- 缺失设计 SID 在设计文档中补齐，或在映射表中标记 alias。
- D1 traceability 文档可直接引用这些 refs。

## 8. 建议拆分 issue

建议创建 5 个 GitHub issue。

### Issue 1: `feat(algorithm): define single recovery-aware action selection boundary`

对应：P0-4。

背景：

```text
CEBRA-WP 理论中只有一个恢复动作选择器 a_t，但当前 RuntimeEvaluator 与 recovery.py 都包含动作选择逻辑。
```

解决路径：

```text
RuntimeEvaluator 只计算 U_a；recovery.select_workflow_action() 成为唯一动作选择入口。
```

### Issue 2: `feat(planner): add explicit feasibility metadata for CEBRA-WP candidates`

对应：P0-1。

背景：

```text
论文公式区分 F_h/F_s/degraded_feasible，但当前候选只通过 filter_reason 和 soft_filtered_rows 间接表达。
```

解决路径：

```text
新增 metadata.feasibility，明确 hard_feasible、soft_feasibility、degraded_feasible、requires_hitl、filter_reason、source_refs。
```

### Issue 3: `feat(objective): connect posterior objective score to planner ranking`

对应：P0-2。

背景：

```text
objective_ranker 已计算 posterior_score，但与 planner score_breakdown.objective 的闭环不足。
```

解决路径：

```text
统一 metadata.posterior_objective，并将 aggregate_score/evidence_sufficiency 接入 planner score_breakdown。
```

### Issue 4: `feat(runtime): derive stable action-utility features from workflow state`

对应：P0-3。

背景：

```text
Action Utility 使用多个派生变量，但当前可能长期使用默认值，削弱解释力。
```

解决路径：

```text
新增 derive_action_features，输出 value/source/reason，并将 flat value 兼容写入 runtime_state。
```

### Issue 5: `docs/feat(algorithm): align implementation source refs with design SIDs`

对应：P0-5。

背景：

```text
代码 source refs 与设计 SID 尚未统一，影响论文设计—实现可追踪性。
```

解决路径：

```text
每个 metadata 子对象使用 source_refs=[sid:..., impl:...]；同步更新设计文档 SID 对照。
```

## 9. 后续需要继续细化的问题清单

下一轮讨论建议按以下顺序：

### 9.1 P0-4 细化问题

1. 当前主流程里哪些位置调用 `RuntimeEvaluator.select_action()`？
2. `select_workflow_action()` 是否接收 `action_utilities` 参数？
3. stop guard 只保留在 recovery selector，还是 RuntimeEvaluator 内兼容保留但不用于主流程？
4. metadata 中 `action_selection` 应放在哪个对象上？task state、candidate metadata、还是 workflow decision summary？

### 9.2 P0-1 细化问题

1. degraded candidate 是否允许成为 `default_recommendation`？
2. 如果允许，是不是必须增加 `default_recommendation_mode="hitl_required"`？
3. `io_not_closed` 和 `tool_unavailable` 是否都属于 degraded，而不是 discarded？
4. 自动执行路径在哪里检查 `requires_hitl=false`？

### 9.3 P0-2 细化问题

1. posterior objective 是直接覆盖 `score_breakdown.objective`，还是按权重混合 prior 与 posterior？
2. `evidence_sufficiency` 的缺省值应是 0.0、0.5，还是 `unknown`？
3. binding component 当前是否实际输出？如果没有，是否作为本 issue 的必修复项？
4. objective score 改变排序后，哪些测试最能保护行为？

### 9.4 P0-3 细化问题

1. `derive_action_features()` 放在 `recovery.py`、`belief_state.py`，还是新文件？
2. 派生特征的输入对象是什么？`runtime_state_summary`、`StepResult`、`Plan`、`candidate list`？
3. unknown/default 的 schema 是否需要显式枚举？
4. `intervention_value` 默认改为 0.5 是否会影响现有 stop 测试？

### 9.5 P0-5 细化问题

1. 哪些 SID 已存在，哪些需要新增？
2. 设计文档更新是在当前 repo 记录 issue，还是同步改 `../thesis-project.design/`？
3. `source_refs` 是否进入所有 API 输出，还是只进入内部 metadata？
4. UI 是否需要展示 source refs？初步建议不展示，只保留调试/审计用途。

## 10. 本轮结论

已确认的 P0 方向可以形成实现路线：

```text
单一动作选择边界
  + 显式 feasibility metadata
  + posterior objective 主评分闭环
  + action utility 派生变量来源
  + sid/impl 双来源追踪
```

下一步不是立即编码，而是继续细化每个 issue 的具体实现边界、字段 schema、测试用例和迁移风险。
