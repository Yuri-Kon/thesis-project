# Issue: feat(runtime): derive stable action-utility features from workflow state

## 类型

- Priority: P0
- Scope: algorithm / runtime / recovery / action utility
- Phase: CEBRA-WP P0 implementation
- Body language: Chinese
- 状态：待实现
- 本文件定位：P0-3 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

CEBRA-WP 理论 v2 定义恢复动作效用：

```text
U_a(a, x_t, Π_t, h_t)
```

动作空间：

```text
A = {continue, patch_local, suffix_replan, stop}
```

当前 `RuntimeEvaluator.compute_action_utilities()` 已经实现四动作效用公式，但多个关键输入依赖默认值：

```python
local_patchability = 0.5
evidence_reusability = 0.5
prefix_preservability = 0.5
budget_relief = 0.5
goal_realignment = 0.5
safety_terminality = 0.0
intervention_value = 0.0
```

这些默认值会带来理论和工程风险：

1. 论文公式看起来完整，但实际决策可能由默认值主导；
2. `intervention_value=0.0` 会抬高 stop utility，因为 `U_stop` 包含 `0.10 * (1 - intervention_value)`；
3. 相同 failure 在 `recovery.py` 和 `runtime_evaluator.py` 中可能得到不同 action utility；
4. metadata 中缺少派生变量来源，难以审计。

本 issue 的目标是建立稳定的 `derive_action_features()`，把 action utility 需要的派生变量从 workflow state / failure context / candidate evidence 中可解释地推导出来。

## 2. 当前代码核查结论

### 2.1 RuntimeEvaluator 当前公式

文件：

```text
src/workflow/runtime_evaluator.py::RuntimeEvaluator.compute_action_utilities
```

当前读取字段：

```python
s = p_success
f_param = p_structural_failure
r_margin = recovery_margin
e_suff = evidence_sufficiency
ec = expected_remaining_cost
lp = local_patchability default 0.5
er_val = evidence_reusability default 0.5
pp = prefix_preservability default 0.5
br = budget_relief default 0.5
gr = goal_realignment default 0.5
safety_term = safety_terminality default 0.0
iv = intervention_value default 0.0
```

当前四个公式：

```text
U_continue = 0.38s + 0.14e + 0.12r - 0.22f - 0.14b
U_patch    = 0.20s + 0.24r + 0.18lp + 0.12er - 0.14f - 0.12b
U_replan   = 0.18(1-s) + 0.20f + 0.16(1-r) + 0.18pp + 0.14br + 0.14gr
U_stop     = 0.32(1-s) + 0.24b + 0.18(1-r) + 0.16safety + 0.10(1-iv)
```

### 2.2 recovery.py 已有局部派生逻辑

文件：

```text
src/workflow/recovery.py::_derive_runtime_action_features
```

当前已经派生：

```text
budget_pressure
intervention_value
prefix_preservability
local_patchability
u_stop
```

并使用：

- `stage_id`
- `failure_type`
- `retry_exhausted`
- `safety_blocked`
- `p_success`
- `p_structural_failure`
- `recovery_margin`
- `expected_remaining_cost`
- `evidence_sufficiency`

这是好的方向，但问题是：

1. 它是 `recovery.py` 内部 helper；
2. RuntimeEvaluator 仍然不知道这些派生逻辑；
3. 它没有输出 `evidence_reusability / budget_relief / goal_realignment / safety_terminality`；
4. 输出只有 float，没有 source / confidence / default-or-inferred 标记。

### 2.3 ActionUtility schema 当前支持 metadata

文件：

```text
src/models/runtime_schemas.py::ActionUtility
```

当前字段：

```python
action
utility
hard_constraints
tie_break_reason
intervention_value
budget_pressure
terminal_reason
source_refs
metadata
```

这意味着不需要立刻改 schema，也可以把派生变量来源放入：

```python
ActionUtility.metadata["derived_features"]
```

## 3. 目标

实现一个稳定、可复用、可审计的 action feature derivation 层。

目标：

1. 所有 action utility 输入变量都有明确来源；
2. 默认值和推断值区分；
3. `intervention_value` 默认不再是 0.0；
4. RuntimeEvaluator 与 recovery selector 使用同一套派生结果；
5. ActionUtility metadata 可解释每个变量；
6. 不引入复杂模型，初版使用确定性规则。

## 4. 非目标

本 issue 不做：

1. 不改变四动作效用公式权重；
2. 不改变 stop threshold；
3. 不新增训练模型；
4. 不改 FSM；
5. 不重写 recovery selector；P0-4 已处理边界；
6. 不把所有派生变量写入长期 belief state；初版只作为 action selection 现场特征。

## 5. 推荐架构

### 5.1 新增 helper 所在位置

推荐新建模块：

```text
src/workflow/action_features.py
```

理由：

- `runtime_evaluator.py` 和 `recovery.py` 都需要使用；
- 避免互相 import 造成循环；
- 便于单独测试。

### 5.2 核心函数

```python
def derive_action_features(
    *,
    runtime_state: Mapping[str, object],
    stage_id: str | None = None,
    failure_type: FailureType | str | None = None,
    retry_exhausted: bool = False,
    safety_blocked: bool = False,
    candidate_summary: Mapping[str, object] | None = None,
    completed_step_count: int | None = None,
    failed_step_index: int | None = None,
) -> ActionFeatureDerivation:
    ...
```

### 5.3 返回结构

建议先用 dataclass 或 TypedDict，不必立刻 Pydantic：

```python
@dataclass(frozen=True)
class DerivedActionFeature:
    value: float
    source: Literal["observed", "inferred", "default", "unknown"]
    source_fields: tuple[str, ...]
    reason: str

@dataclass(frozen=True)
class ActionFeatureDerivation:
    values: dict[str, float]
    features: dict[str, DerivedActionFeature]
    source_refs: tuple[str, ...]
```

`values` 至少包含：

```text
budget_pressure
local_patchability
evidence_reusability
prefix_preservability
budget_relief
goal_realignment
safety_terminality
intervention_value
```

可选包含：

```text
u_stop
```

但建议不要让 `u_stop` 成为独立派生输入。`u_stop` 应由公式算出，否则会和 `compute_action_utilities()` 重复。保留 `u_stop` 仅用于 backward compatibility。

## 6. 派生规则

### 6.1 budget_pressure

优先级：

1. 如果 runtime_state 已有 `budget_pressure`，使用 observed；
2. 否则由 `expected_remaining_cost` 裁剪得到：

```text
budget_pressure = clip(expected_remaining_cost, 0.0, 1.5)
```

进入公式时再裁剪到 `[0,1]`。

### 6.2 local_patchability

高值条件：

```text
failure_type in {RETRYABLE, TOOL_ERROR}
safety_blocked == False
recovery_margin 高
p_structural_failure 低
stage_id 较早或失败局部化
```

建议初版：

```text
base = 0.45 * recovery_margin
     + 0.35 * (1 - p_structural_failure)
     + 0.20 * evidence_sufficiency
```

加成：

```text
+0.10 if failure_type in {RETRYABLE, TOOL_ERROR}
+0.05 if retry_exhausted and not safety_blocked
-0.25 if safety_blocked
-0.15 if failure_type == SAFETY_BLOCK
```

注意：`retry_exhausted` 不一定提高 local patchability。它可能说明当前步骤不能继续 retry，但仍可 patch。加成应保守，最多 +0.05。

### 6.3 evidence_reusability

来源：

```text
evidence_sufficiency
completed_step_count
candidate has posterior_objective
validated_outputs/artifact_refs exist
```

初版如果没有 artifacts 细节：

```text
evidence_reusability = 0.65 * evidence_sufficiency + 0.35 * prefix_preservability_proxy
```

若 `candidate_summary.posterior_objective.evidence_sufficiency` 存在，则使用更高置信来源。

### 6.4 prefix_preservability

高值条件：

```text
failed_step_index > 0
completed_step_count > 0
recovery_margin 高
failure localized to suffix
```

初版：

```text
prefix_base = 0.50 * recovery_margin
            + 0.30 * evidence_sufficiency
            + 0.20 * (1 - min(budget_pressure, 1.0))
```

修正：

```text
+0.10 if failed_step_index is not None and failed_step_index > 0
+0.08 if completed_step_count > 0
-0.15 if failed_step_index == 0
```

### 6.5 budget_relief

含义：suffix replan 是否能缓解预算压力。

初版没有精确 cost model 时，不要默认 0.5。建议：

```text
if expected_remaining_cost >= 1.0 and prefix_preservability high:
    budget_relief = 0.60
elif expected_remaining_cost >= 1.0:
    budget_relief = 0.45
else:
    budget_relief = 0.35
```

原因：replan 通常不是免费操作，不能默认认为它缓解预算。

### 6.6 goal_realignment

含义：suffix replan 是否能更好对齐目标。

来源：

```text
objective_gap
posterior_objective.evidence_status
evidence_sufficiency
p_success
```

初版：

```text
goal_realignment = clip(
    0.40 * (1 - p_success)
  + 0.30 * p_structural_failure
  + 0.30 * (1 - evidence_sufficiency),
    0, 1
)
```

如果 candidate/objective metadata 有 `objective_gap`，则用 observed：

```text
goal_realignment = max(goal_realignment, objective_gap)
```

### 6.7 safety_terminality

含义：安全问题是否倾向终止。

规则：

```text
1.0 if safety_blocked or failure_type == SAFETY_BLOCK
0.6 if blocked tool is mandatory and no fallback
0.0 otherwise
```

初版可先实现第一条。

### 6.8 intervention_value

关键决策：默认不应为 0.0。

如果没有可推断信息：

```text
intervention_value = 0.5
source = "default"
```

有上下文时：

```text
uncertainty = 1 - abs(p_success - (1 - p_structural_failure))
manual_salvageability = 0.55 * local_patchability + 0.45 * prefix_preservability
artifact_salience = 0.60 * evidence_sufficiency + 0.40 * recovery_margin
decision_gap = 0.50 + 0.25 * recovery_margin - 0.25 * min(budget_pressure, 1.0)

intervention_value = 0.30 * uncertainty
                   + 0.25 * manual_salvageability
                   + 0.25 * artifact_salience
                   + 0.20 * decision_gap
```

这基本沿用 `recovery.py` 已有逻辑，但应封装到共享 helper。

## 7. RuntimeEvaluator 接入

### 7.1 `compute_action_utilities()` 接收派生结果

推荐改成：

```python
def compute_action_utilities(
    self,
    runtime_state: RuntimeStateSchema | Mapping[str, object],
    *,
    action_features: ActionFeatureDerivation | Mapping[str, object] | None = None,
) -> dict[str, ActionUtility]:
```

如果未传入：

```python
action_features = derive_action_features(runtime_state=state)
```

### 7.2 ActionUtility metadata

每个 ActionUtility 附：

```python
metadata={
    "derived_features": {
        "local_patchability": {...},
        "evidence_reusability": {...},
        ...
    },
    "source_refs": [
        "sid:algo.action_feature_derivation",
        "impl:workflow.action_features.v1",
    ],
}
```

`source_refs` 字段本身也加入：

```python
source_refs=[
    "sid:algo.schema.action_utility",
    "sid:algo.action_feature_derivation",
    "impl:runtime_evaluator.action_utility.v1",
]
```

## 8. recovery.py 接入

P0-4 确认 `recovery.select_workflow_action()` 是唯一 action selection 入口。

因此：

1. `recovery.py::_derive_runtime_action_features` 应被迁移或替换为 `derive_action_features()`；
2. `select_workflow_action()` 应优先使用传入的 action utilities；
3. 如果需要现场计算，则调用 `derive_action_features()` 后再调用 `RuntimeEvaluator.compute_action_utilities()`；
4. stop guard 使用同一份 `intervention_value / budget_pressure`。

## 9. 默认值策略

| feature | 旧默认 | 新默认建议 | 理由 |
|---|---:|---:|---|
| local_patchability | 0.5 | inferred or 0.5 unknown | 可接受，但需标 source |
| evidence_reusability | 0.5 | inferred from evidence_sufficiency | 证据复用不应完全未知 |
| prefix_preservability | 0.5 | inferred from recovery/evidence/budget | 可从状态推断 |
| budget_relief | 0.5 | 0.35 unknown | replan 默认不应被认为省预算 |
| goal_realignment | 0.5 | inferred from failure/evidence | 目标错配可由低成功/高失败推断 |
| safety_terminality | 0.0 | 1.0 only on safety block | 保守 |
| intervention_value | 0.0 | 0.5 unknown | 避免无信息时过度推高 stop |

## 10. 测试计划

### 10.1 新增测试文件

```text
tests/unit/test_action_features.py
```

覆盖：

1. 无额外上下文时返回所有必需 feature；
2. `intervention_value` unknown 默认 0.5 或由规则推断，不是 0.0；
3. safety block 使 `safety_terminality=1.0`；
4. retryable/tool error 提高 local_patchability；
5. failed_step_index > 0 提高 prefix_preservability；
6. high budget pressure 不应让 budget_relief 默认过高；
7. 每个 feature 都有 source/source_fields/reason。

### 10.2 更新 RuntimeEvaluator 测试

当前文件：

```text
tests/unit/test_runtime_evaluator.py
```

新增/更新：

1. `compute_action_utilities()` metadata 包含 derived_features；
2. stop utility 在缺少 intervention_value 时不会因默认 0.0 被抬高；
3. 传入 explicit action_features 时优先使用 explicit；
4. source_refs 包含 `sid:algo.action_feature_derivation`。

注意：当前 `_state_dict()` 默认 `intervention_value=0.0`。测试应明确区分：

- 显式传入 0.0：尊重 observed；
- 未传入：推断或默认 0.5。

### 10.3 更新 recovery selector 测试

现有文件：

```text
tests/unit/test_recovery_selector.py
tests/integration/test_workflow_action_selector.py
```

新增断言：

- `evidence_source.action_selection.action_utility_source` 指向 shared derivation；
- safety block 仍 hard priority；
- retry exhausted 仍不直接 auto stop，除非 stop guard 条件满足。

## 11. 稳定性考虑

### 11.1 不改变公式权重

本 issue 只改变输入派生，不改变 `U_a` 权重，降低排序/动作选择突变风险。

### 11.2 显式 observed 优先

如果 runtime_state 已经给出某个 feature，应优先使用 observed 值，并标：

```text
source="observed"
```

不要用规则覆盖上游明确值。

### 11.3 区分 default 和 inferred

默认值必须标：

```text
source="default"
```

推断值标：

```text
source="inferred"
```

这样后续审查可判断算法是否过度依赖默认值。

### 11.4 避免状态膨胀

不要把所有 derived features 写入 `RuntimeStateSchema` 的必需字段。初版只进入：

```text
ActionUtility.metadata.derived_features
WorkflowActionSelectorResult.evidence_source
```

未来如果证明稳定，再考虑升级为 runtime state 字段。

## 12. 设计 SID 对照

需要补齐或确认：

```text
sid:algo.action_feature_derivation
```

现有相关 SID：

```text
sid:algo.schema.action_utility
```

对应实现：

```text
impl:workflow.action_features.v1
impl:runtime_evaluator.action_utility.v1
impl:recovery.select_workflow_action.v1
```

## 13. 验收标准

- 新增共享 `derive_action_features()`；
- RuntimeEvaluator 与 recovery selector 使用同一套派生特征；
- `intervention_value` 缺省不再是 0.0；
- 每个派生变量都有 value/source/source_fields/reason；
- ActionUtility metadata 包含 derived_features；
- 不改变四动作 utility 权重；
- stop guard 行为有回归测试；
- safety block / retry exhausted / prefix preservation 场景有测试覆盖。

## 14. 回滚策略

如果派生规则导致动作选择变化过大：

1. 保留 `derive_action_features()` 和 metadata；
2. 在 RuntimeEvaluator 中临时关闭 shared feature 使用；
3. 使用旧默认值计算 utility；
4. 但保留 metadata 输出用于观测差异。

不建议删除 shared helper，因为它是后续算法解释和论文支撑所需。
