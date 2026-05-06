# Issue: docs/feat(algorithm): align implementation source refs with design SIDs

## 类型

- Priority: P0
- Scope: design traceability / metadata / documentation / auditability
- Phase: CEBRA-WP P0 implementation
- Body language: Chinese
- 状态：待实现
- 本文件定位：P0-5 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

CEBRA-WP 的论文目标要求“理论对象、数学公式、设计 SID、实现代码、运行时 metadata”之间具备稳定可追踪关系。

前置文档已经形成：

```text
docs/algorithm-and-llm/core-algorithm-design-code-traceability.md
docs/algorithm-and-llm/core-algorithm-theory-v2.md
docs/algorithm-and-llm/core-algorithm-code-gap-review.md
docs/algorithm-and-llm/implementation/2026-05-05_021358-cebra-wp-p0-implementation-decisions.md
```

其中 D1 已建立设计 SID ↔ 代码路径可追踪矩阵；D4 识别出当前实现与理论 v2 的 P0 差距。

但当前代码中的审计来源主要表现为局部字符串，例如：

```text
runtime_evaluator.action_utility.v1
runtime_evaluator.default.v1
planner.runtime_adjustment.<action>.v1
planner.runtime_adjustment.shadow_passthrough.v1
posterior_score.v1
score_breakdown.overall.static.v1
static_score+runtime_adjustment.<action>.v1
```

这些 `impl` 风格引用有工程价值，但还不能稳定回答：

```text
这个 metadata 子对象对应设计文档中的哪个 SID？
这个公式是否来自 core-algorithm-spec.md，还是 runtime-adaptation-formalization.md？
设计文档更新后，代码引用是否还能追踪？
```

因此 P0-5 的目标是建立统一的 `source_refs=[sid:..., impl:...]` 规范，并同步明确设计 SID 的新增/alias 规则。

## 2. 当前代码核查结论

### 2.1 已存在 source_refs 的模型

`src/models/runtime_schemas.py` 中已有多个 schema 支持 `source_refs`：

```text
CostSchema.source_refs
RiskSchema.source_refs
RecoverySchema.source_refs
ObservationSchema.source_refs
ActionUtility.source_refs
```

`ActionUtility` 当前字段：

```python
action: Literal["continue", "patch_local", "suffix_replan", "stop"]
utility: float
hard_constraints: list[str]
tie_break_reason: str | None
intervention_value: float
budget_pressure: float
terminal_reason: str | None
source_refs: list[str]
metadata: JsonObject
```

因此 action utility 侧不需要新增顶层字段，只需要规范填充值。

### 2.2 当前 ActionUtility source_refs

文件：

```text
src/workflow/runtime_evaluator.py::RuntimeEvaluator.compute_action_utilities
```

当前四个动作均使用：

```python
source_refs=["runtime_evaluator.action_utility.v1"]
```

默认 action utility 使用：

```python
source_refs=["runtime_evaluator.default.v1"]
```

问题：缺少 `sid:algo.schema.action_utility` 与未来 `sid:algo.action_feature_derivation`。

### 2.3 当前 runtime adjustment source

文件：

```text
src/agents/planner.py
src/workflow/runtime_evaluator.py
```

当前 `RuntimeAdjustmentSummary` 使用 `source` 字段：

```python
source="planner.runtime_adjustment.shadow_passthrough.v1"
source=f"planner.runtime_adjustment.{action}.v1"
```

`ScoreSummary` 使用：

```python
source="score_breakdown.overall.static.v1"
source=f"static_score+runtime_adjustment.{action}.v1"
source=f"score_breakdown.overall+runtime_state.{action}.v1"
```

问题：这些模型当前没有 `source_refs` 顶层字段；直接改模型可能扩大影响。P0 初版应采用 additive metadata 或在已有 `source` 旁追加 refs，不强制破坏模型。

### 2.4 当前 posterior score schema

文件：

```text
src/adapters/objective_ranker_adapter.py
```

当前：

```python
_POSTERIOR_SCORE_SCHEMA_VERSION = "posterior_score.v1"
```

输出 `posterior_score` 内含：

```text
schema_version
objective_type
components
aggregate_score
component_weights
evidence_refs
warnings
evidence_sufficiency
evidence_status
```

问题：缺少 `source_refs`，且 P0-2 将新增 `posterior_objective.v1`，应直接带：

```text
sid:algo.posterior_objective_scoring
impl:posterior_score.v1
impl:posterior_objective.v1
```

### 2.5 当前 candidate generator metadata

文件：

```text
src/agents/candidate_generator/builder.py
src/agents/candidate_generator/generator.py
```

当前 metadata 有：

```text
candidate_generator.module
s5_contract
static_score
action_score
runtime_adjustment
final_score
rerank_reason
shadow_score
```

P0-1 将新增：

```text
metadata.candidate_feasibility
```

该子对象必须直接带 `source_refs`，否则 feasibility 的理论归属仍不可追踪。

### 2.6 recovery action selection metadata

P0-4 将 `recovery.select_workflow_action()` 确认为唯一恢复动作选择入口。

因此 P0-4 新增的 action selection metadata 必须带：

```text
sid:algo.recovery_aware_action_selection
impl:recovery.select_workflow_action.v1
```

如果涉及 stop guard / terminal stop，还应带：

```text
sid:planner.algorithm.stop_semantics
impl:recovery.terminal_stop.v1
```

## 3. 当前设计 SID 核查结论

### 3.1 设计 SSOT

核心算法 SSOT：

```text
../thesis-project.design/docs/design/core-algorithm-spec.md
```

运行时形式化支持文档：

```text
../thesis-project.design/docs/design/runtime-adaptation-formalization.md
```

SSOT 映射表：

```text
../thesis-project.design/docs/index/SSOT_MAP.md
```

SSOT_MAP 明确规定：

```text
新增 SID 后必须同时更新 index.json、topic_views.json 和 SSOT_MAP.md。
```

### 3.2 已确认存在的相关 SID

只读核查确认存在：

```text
SID:algo.adaptive.optimization_objective
SID:planner.algorithm.runtime_adjustment_formula
SID:algo.schema.action_utility
SID:planner.algorithm.action_priority_resolution
SID:planner.algorithm.stop_semantics
SID:planner.contracts.candidate_schema
SID:planner.algorithm.candidate_scoring
SID:planner.algorithm.runtime_reranking
SID:planner.algorithm.runtime_action_selection
SID:planner.algorithm.hitl_gate
SID:planner.algorithm.decision_application
SID:algo.schema.state
SID:algo.schema.observation
SID:algo.schema.recovery
```

### 3.3 P0 方案需要但当前未确认存在的 SID

以下 SID 在当前检索中未确认存在，应标记为 proposed，不能假装已经进入设计 SSOT：

```text
SID:algo.adaptive.feasibility_filter
SID:algo.posterior_objective_scoring
SID:algo.action_feature_derivation
SID:algo.recovery_aware_action_selection
SID:algo.terminal_stop_policy
```

### 3.4 设计 SID 新增建议

建议新增位置如下：

| proposed SID | 建议 SSOT 文件 | 建议位置 | 说明 |
|---|---|---|---|
| `SID:algo.adaptive.feasibility_filter` | `core-algorithm-spec.md` | §3.3 或 §5 | 候选硬约束/软降级可执行性过滤 |
| `SID:algo.posterior_objective_scoring` | `core-algorithm-spec.md` | §5 优化目标后 | 证据感知后验目标评分公式 |
| `SID:algo.action_feature_derivation` | `runtime-adaptation-formalization.md` | §3.3/§3.4 派生量定义后 | action utility 输入特征派生规则 |
| `SID:algo.recovery_aware_action_selection` | `runtime-adaptation-formalization.md` 或 `core-algorithm-spec.md` | 动作选择章节 | `HardPriority or argmax U_a` 主策略 |
| `SID:algo.terminal_stop_policy` | `core-algorithm-spec.md` §2.3 或 runtime stop 章节 | stop 终止策略 | terminal stop / stop guard 的算法语义 |

注意：设计仓库是外部路径，实际修改需要单独确认；本 issue 可先作为 future implementation reference，不直接修改设计仓库。

## 4. 目标

实现统一 source refs 规范，使核心 metadata 子对象都能同时指向：

1. 理论/设计来源：`sid:<design-sid>`；
2. 实现来源：`impl:<implementation-ref>`；
3. 如 SID 尚未落入设计 SSOT，则明确标注为 `proposed`，并在文档任务中补齐。

## 5. 非目标

本 issue 不做：

1. 不改变评分公式；
2. 不改变 action selection 行为；
3. 不改变 UI 默认展示；
4. 不强行给所有历史 metadata 补齐 refs；
5. 不把 source refs 做成长对象或嵌套 provenance 图；
6. 不隐式修改设计仓库。设计仓库更新应单独执行或单独 PR。

## 6. 命名规范

### 6.1 source_refs 基本格式

每个核心 metadata 子对象使用：

```python
"source_refs": [
    "sid:<design-sid>",
    "impl:<implementation-ref>",
]
```

要求：

- 至少一个 `sid:`；
- 至少一个 `impl:`；
- `sid:` 应引用设计 SSOT 中存在的 SID；
- 如果 SID 尚未进入 SSOT，可临时使用 `sid:...`，但必须同时在 issue/traceability 中标为 `proposed`；
- `impl:` 使用稳定、短、可 grep 的实现引用；
- 不在 `source_refs` 中放文件路径、长公式、URL、自然语言解释。

### 6.2 `sid:` 规范

格式：

```text
sid:<domain>.<concept>.<object>
```

示例：

```text
sid:algo.schema.action_utility
sid:planner.algorithm.runtime_adjustment_formula
```

禁止：

```text
SID:algo.schema.action_utility   # metadata 中不用大写 SID:
algo.schema.action_utility       # 缺 sid: 前缀
sid:../path/to/doc.md            # source_refs 不直接放路径
```

### 6.3 `impl:` 规范

格式建议：

```text
impl:<module-or-component>.<object>.<version>
```

示例：

```text
impl:candidate_generator.feasibility.v1
impl:posterior_objective.v1
impl:runtime_evaluator.action_utility.v1
impl:recovery.select_workflow_action.v1
```

禁止：

```text
impl:some random helper
impl:src/workflow/recovery.py:123
```

文件路径可以放在文档或测试注释中，不放入 `source_refs`。

### 6.4 proposed SID 标记

source_refs 本身保持简短：

```python
"source_refs": [
    "sid:algo.adaptive.feasibility_filter",
    "impl:candidate_generator.feasibility.v1",
]
```

是否 proposed 放在同级 metadata：

```python
"design_ref_status": {
    "sid:algo.adaptive.feasibility_filter": "proposed"
}
```

或者 issue / traceability 文档中集中维护。

不建议写成：

```text
sid:algo.adaptive.feasibility_filter:proposed
```

因为这会破坏 SID 解析。

## 7. 核心映射表

### 7.1 Candidate feasibility

对象：

```text
metadata.candidate_feasibility
```

source refs：

```python
[
    "sid:algo.adaptive.feasibility_filter",
    "impl:candidate_generator.feasibility.v1",
]
```

当前设计 SID 状态：proposed。

fallback alias：

```text
SID:planner.contracts.candidate_schema
SID:algo.adaptive.optimization_objective
```

说明：

- 该对象对应 `F_h / F_s / requires_hitl / degraded_feasible`；
- 不应只引用 `candidate_schema`，因为它是契约，不是算法过滤规则；
- 最终应补 `algo.adaptive.feasibility_filter`。

### 7.2 Static score / S5 scoring contract

对象：

```text
metadata.static_score
metadata.s5_contract
score_breakdown
```

source refs：

```python
[
    "sid:algo.adaptive.optimization_objective",
    "sid:planner.algorithm.candidate_scoring",
    "impl:planner.score_breakdown.v1",
]
```

设计 SID 状态：existing。

说明：

- `algo.adaptive.optimization_objective` 对应多目标效用；
- `planner.algorithm.candidate_scoring` 对应候选评分规则；
- 两者同时引用是合理的：前者是理论公式，后者是 Planner 落地规则。

### 7.3 Posterior objective

对象：

```text
metadata.posterior_objective
posterior_score
```

source refs：

```python
[
    "sid:algo.posterior_objective_scoring",
    "impl:posterior_score.v1",
    "impl:posterior_objective.v1",
]
```

设计 SID 状态：proposed。

fallback alias：

```text
SID:algo.adaptive.optimization_objective
SID:workflow.stage.objective_scoring
```

说明：

- `workflow.stage.objective_scoring` 是工作流阶段，不是算法公式；
- `algo.posterior_objective_scoring` 应作为公式级 SID 补到 core algorithm spec。

### 7.4 Runtime adjustment

对象：

```text
metadata.runtime_adjustment
metadata.final_score
metadata.rerank_reason
metadata.shadow_score
```

source refs：

```python
[
    "sid:planner.algorithm.runtime_adjustment_formula",
    "sid:planner.algorithm.runtime_reranking",
    "impl:planner.runtime_adjustment.v1",
]
```

设计 SID 状态：existing。

兼容方式：

- 保留现有 `source="planner.runtime_adjustment.<action>.v1"`；
- 若模型不支持 `source_refs`，可在 metadata 包装层旁路添加：

```python
metadata["runtime_adjustment_source_refs"] = [...]
```

但更推荐在 summary dict 中增加 `source_refs`，前提是不破坏 Pydantic 模型。

### 7.5 Action utility

对象：

```text
ActionUtility.source_refs
ActionUtility.metadata.derived_features
```

source refs：

```python
[
    "sid:algo.schema.action_utility",
    "sid:algo.action_feature_derivation",
    "impl:runtime_evaluator.action_utility.v1",
    "impl:workflow.action_features.v1",
]
```

设计 SID 状态：

```text
algo.schema.action_utility existing
algo.action_feature_derivation proposed
```

说明：

- `algo.schema.action_utility` 是 schema/公式的现有 SID；
- `algo.action_feature_derivation` 是 P0-3 新增派生规则，应补 SID。

### 7.6 Recovery-aware action selection

对象：

```text
WorkflowActionSelectorResult.evidence_source.action_selection
```

source refs：

```python
[
    "sid:algo.recovery_aware_action_selection",
    "sid:planner.algorithm.action_priority_resolution",
    "impl:recovery.select_workflow_action.v1",
]
```

设计 SID 状态：

```text
algo.recovery_aware_action_selection proposed
planner.algorithm.action_priority_resolution existing
```

fallback alias：

```text
SID:planner.algorithm.runtime_action_selection
```

说明：

- P0-4 中确定 `recovery.select_workflow_action()` 是唯一主入口；
- 因此这里必须引用 recovery-aware action selection，而不只引用 runtime evaluator。

### 7.7 Terminal stop policy

对象：

```text
terminal_stop candidate
stop guard metadata
terminal_reason
```

source refs：

```python
[
    "sid:algo.terminal_stop_policy",
    "sid:planner.algorithm.stop_semantics",
    "impl:recovery.terminal_stop.v1",
]
```

设计 SID 状态：

```text
algo.terminal_stop_policy proposed
planner.algorithm.stop_semantics existing
```

说明：

- `planner.algorithm.stop_semantics` 已存在，可作为现阶段强引用；
- `algo.terminal_stop_policy` 可作为更细粒度 SID 补充，避免 stop guard 与 terminal stop 混在一个大块。

## 8. 推荐实现策略

### 8.1 不要一次性改所有模型

P0-5 应尽量 additive：

- 能直接加 `source_refs` 的对象直接加；
- 不能加顶层字段的对象，在 metadata dict 中添加 companion refs；
- 不删除已有 `source`；
- 不重命名已有 schema version。

### 8.2 建立轻量常量模块

建议新增：

```text
src/workflow/source_refs.py
```

或者如果不想新增模块，可在相关模块内部定义常量。但考虑 P0-1/P0-2/P0-3/P0-4 都会使用，推荐共享模块。

建议内容：

```python
SOURCE_REF_FEASIBILITY = (
    "sid:algo.adaptive.feasibility_filter",
    "impl:candidate_generator.feasibility.v1",
)

SOURCE_REF_POSTERIOR_OBJECTIVE = (
    "sid:algo.posterior_objective_scoring",
    "impl:posterior_score.v1",
    "impl:posterior_objective.v1",
)

SOURCE_REF_RUNTIME_ADJUSTMENT = (
    "sid:planner.algorithm.runtime_adjustment_formula",
    "sid:planner.algorithm.runtime_reranking",
    "impl:planner.runtime_adjustment.v1",
)

SOURCE_REF_ACTION_UTILITY = (
    "sid:algo.schema.action_utility",
    "sid:algo.action_feature_derivation",
    "impl:runtime_evaluator.action_utility.v1",
    "impl:workflow.action_features.v1",
)

SOURCE_REF_ACTION_SELECTION = (
    "sid:algo.recovery_aware_action_selection",
    "sid:planner.algorithm.action_priority_resolution",
    "impl:recovery.select_workflow_action.v1",
)

SOURCE_REF_TERMINAL_STOP = (
    "sid:algo.terminal_stop_policy",
    "sid:planner.algorithm.stop_semantics",
    "impl:recovery.terminal_stop.v1",
)
```

如果担心 `workflow` 层被 `adapters` 引用不合适，posterior objective 的常量可以放在 `src/infra/source_refs.py` 或 `src/models/source_refs.py`。

更稳妥推荐：

```text
src/models/source_refs.py
```

理由：

- refs 是契约/metadata 常量，不属于 workflow 执行逻辑；
- adapters/planner/workflow 都可以安全引用 models；
- 避免 adapters 反向依赖 workflow。

### 8.3 helper 函数

建议提供：

```python
def as_source_refs(*refs: str) -> list[str]:
    """返回去重后的 source_refs 列表。"""
```

要求：

- 保持输入顺序；
- 去重；
- 拒绝空字符串；
- 不做复杂验证，避免运行时成本和误伤。

如果实现者认为 helper 过度抽象，也可以只用 tuple 常量 + `list(CONST)`。

## 9. 设计文档更新策略

### 9.1 强制原则

不能长期使用不存在的 SID。

如果实现代码中加入：

```text
sid:algo.posterior_objective_scoring
```

则必须满足以下至少一项：

1. 同一实现周期补充设计仓库 SID；
2. 或在本 repo 的 traceability 文档中明确标为 proposed，并创建后续设计同步 issue；
3. 或暂时使用 existing alias，并不使用 proposed SID。

推荐第 1 种。

### 9.2 新增 SID 需要更新的设计文件

若进入设计仓库更新，应至少改：

```text
../thesis-project.design/docs/design/core-algorithm-spec.md
../thesis-project.design/docs/design/runtime-adaptation-formalization.md
../thesis-project.design/docs/index/SSOT_MAP.md
```

并根据设计仓库索引机制更新：

```text
../thesis-project.design/docs/index/index.json
../thesis-project.design/docs/index/topic_views.json
```

如果 `index.json` / `topic_views.json` 是生成产物，应使用设计仓库现有脚本生成，不手写。

### 9.3 设计仓库修改边界

设计仓库在：

```text
../thesis-project.design
```

不是当前业务代码仓库的一部分。实现阶段不得在代码 PR 中悄悄修改设计仓库。应有以下二选一：

- 单独设计文档 PR/commit；
- 当前仓库 issue 中标注“设计 SID 待同步”。

## 10. 实现步骤

### Step 1：建立 source refs 常量

新增或选择位置：

```text
src/models/source_refs.py
```

定义核心 refs 常量。

### Step 2：P0-1 feasibility 引用常量

在 `metadata.candidate_feasibility.source_refs` 中使用：

```text
SOURCE_REF_FEASIBILITY
```

同时标注 proposed SID 状态。

### Step 3：P0-2 posterior objective 引用常量

在 `posterior_objective.source_refs` 中使用：

```text
SOURCE_REF_POSTERIOR_OBJECTIVE
```

保留旧 `posterior_score.schema_version`。

### Step 4：P0-3 action utility / feature derivation 引用常量

在 `ActionUtility.source_refs` 和 `ActionUtility.metadata.derived_features.source_refs` 中使用：

```text
SOURCE_REF_ACTION_UTILITY
```

如果 feature derivation 单独输出对象，也加入：

```text
impl:workflow.action_features.v1
```

### Step 5：P0-4 action selection 引用常量

在 `select_workflow_action()` 输出 evidence metadata 中加入：

```text
SOURCE_REF_ACTION_SELECTION
```

stop 相关分支另加：

```text
SOURCE_REF_TERMINAL_STOP
```

### Step 6：runtime adjustment 补 source_refs

对 `runtime_adjustment` metadata 增加 refs。

如果 `RuntimeAdjustmentSummary` 模型不能加字段，则在 model dump 后追加：

```python
payload = runtime_adjustment.model_dump()
payload["source_refs"] = list(SOURCE_REF_RUNTIME_ADJUSTMENT)
```

该方式不改模型定义，风险较小。

### Step 7：更新 D1 traceability 文档

更新：

```text
docs/algorithm-and-llm/core-algorithm-design-code-traceability.md
```

添加 source refs 映射和 proposed SID 状态。

### Step 8：必要时创建设计同步 issue

如果不立即改设计仓库，应创建后续 issue：

```text
docs/algorithm-and-llm/issues/2026-05-05-design-sid-sync.md
```

或者在本 issue 验收中保留未完成项。

## 11. 测试计划

### 11.1 source_refs helper 测试

新增：

```text
tests/unit/test_source_refs.py
```

覆盖：

- 常量中每组 refs 至少一个 `sid:`；
- 至少一个 `impl:`；
- 没有空字符串；
- helper 去重且保序。

### 11.2 candidate feasibility 测试

更新 P0-1 测试：

```python
refs = candidate.metadata["candidate_feasibility"]["source_refs"]
assert any(ref.startswith("sid:") for ref in refs)
assert any(ref.startswith("impl:") for ref in refs)
```

### 11.3 posterior objective 测试

更新 P0-2 测试：

```python
refs = posterior_objective["source_refs"]
assert "sid:algo.posterior_objective_scoring" in refs
assert "impl:posterior_objective.v1" in refs
```

### 11.4 action utility 测试

更新 P0-3 测试：

```python
refs = utilities["continue"].source_refs
assert "sid:algo.schema.action_utility" in refs
assert "impl:runtime_evaluator.action_utility.v1" in refs
```

### 11.5 action selection 测试

更新 P0-4 测试：

```python
refs = result.evidence_source["action_selection"]["source_refs"]
assert "sid:algo.recovery_aware_action_selection" in refs
assert "impl:recovery.select_workflow_action.v1" in refs
```

### 11.6 runtime adjustment 测试

更新 runtime rerank 测试：

```python
adj = candidate.metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
assert "source_refs" in adj
assert "sid:planner.algorithm.runtime_adjustment_formula" in adj["source_refs"]
```

## 12. 稳定性考虑

### 12.1 metadata 体积

`source_refs` 必须保持短字符串数组。不要嵌入：

- 文档路径；
- 长公式；
- 摘要文本；
- citation；
- URL。

### 12.2 UI/Inspector 过载

根据项目偏好，Inspector 是快速概览面板，不应默认展开复杂定义。

因此：

- UI/Inspector 不默认展示 `source_refs`；
- 详情区、debug API、日志可展示；
- 不因为本 issue 增加 UI 噪音。

### 12.3 设计漂移

最大风险是代码引用了不存在或后来改名的 SID。

缓解：

1. 在 `core-algorithm-design-code-traceability.md` 中集中维护 SID 状态；
2. source refs 常量集中定义，避免散落；
3. 设计仓库 SID 更新后只需改常量和 traceability；
4. 测试检查 refs 格式，但不强行访问设计仓库路径，避免 CI 依赖外部仓库。

### 12.4 不破坏 Pydantic 模型

不要为了加 `source_refs` 大规模修改模型。优先：

- 已有 `source_refs` 字段：直接使用；
- 没有字段但输出是 dict：model_dump 后追加；
- 没有字段且严格模型：放在外层 metadata companion key。

## 13. 验收标准

- 核心 metadata 子对象均有 `source_refs`；
- 每个 `source_refs` 至少包含一个 `sid:` 和一个 `impl:`；
- 现有 `source` 字段不被删除、不被改名；
- `ActionUtility.source_refs` 包含 `sid:algo.schema.action_utility`；
- `runtime_adjustment` metadata 包含 `sid:planner.algorithm.runtime_adjustment_formula`；
- `posterior_objective` metadata 包含 `sid:algo.posterior_objective_scoring`；
- `candidate_feasibility` metadata 包含 `sid:algo.adaptive.feasibility_filter`；
- `action_selection` metadata 包含 `sid:algo.recovery_aware_action_selection`；
- proposed SID 在 traceability 或设计同步 issue 中明确标注；
- 不让 UI/Inspector 默认展开 refs；
- 相关单测覆盖 refs 格式和核心对象 refs 存在。

## 14. 回滚策略

如果 source refs 引发兼容问题：

1. 保留 source refs 常量模块；
2. 暂时只在 debug metadata 中输出 refs；
3. 不改已有 `source` 字段；
4. 对严格 schema 对象移除新增字段，改为外层 companion metadata。

不建议完全删除 source refs 体系，因为它是论文可追踪性和未来实现审查的基础。

## 15. 后续设计同步任务

如果执行本 issue 时不修改设计仓库，则必须创建或保留后续任务：

```text
补齐 CEBRA-WP P0 proposed SIDs 到 thesis-project.design
```

建议包含：

```text
SID:algo.adaptive.feasibility_filter
SID:algo.posterior_objective_scoring
SID:algo.action_feature_derivation
SID:algo.recovery_aware_action_selection
SID:algo.terminal_stop_policy
```

并同步更新：

```text
core-algorithm-spec.md
runtime-adaptation-formalization.md
SSOT_MAP.md
index.json
topic_views.json
```

## 16. 相关文件

代码侧：

```text
src/models/runtime_schemas.py
src/models/contracts.py
src/agents/candidate_generator/generator.py
src/agents/candidate_generator/builder.py
src/agents/planner.py
src/workflow/runtime_evaluator.py
src/workflow/recovery.py
src/adapters/objective_ranker_adapter.py
```

文档侧：

```text
docs/algorithm-and-llm/core-algorithm-design-code-traceability.md
docs/algorithm-and-llm/core-algorithm-theory-v2.md
docs/algorithm-and-llm/core-algorithm-code-gap-review.md
../thesis-project.design/docs/design/core-algorithm-spec.md
../thesis-project.design/docs/design/runtime-adaptation-formalization.md
../thesis-project.design/docs/index/SSOT_MAP.md
```

测试侧：

```text
tests/unit/test_candidate_generator.py
tests/unit/test_extended_tool_adapters.py
tests/unit/test_runtime_evaluator.py
tests/unit/test_recovery_selector.py
tests/integration/test_workflow_action_selector.py
tests/unit/test_source_refs.py
```
