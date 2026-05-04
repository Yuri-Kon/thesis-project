# Issue: P1-1 统一 recovery_complexity 的理论定义与静态评分表达

## 类型

- Priority: P1
- Scope: algorithm / static scoring / recovery theory
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：待实现
- 本文件定位：P1-1 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

理论 v2 中，静态评分里需要一个与恢复难度相关的项：

```text
Rec = recovery_complexity
```

同时设计文档把它定义为 recoverability 的补量：

```text
recoverability = 0.30 * retry_budget_ratio
               + 0.30 * local_patchability
               + 0.25 * prefix_preservability
               + 0.15 * evidence_reusability
recovery_complexity = 1 - recoverability
```

当前代码里，`src/agents/candidate_generator/generator.py` 已经产出 `score_breakdown.recovery_complexity`，但其来源在不同候选类型上仍可能退化为 `1 - fallback_depth` 或局部启发式。问题不在于“有没有这个字段”，而在于它是否已经被稳定定义成一个可论文解释的理论量。

## 2. 当前代码核查结论

### 2.1 已存在的字段

`tests/unit/test_candidate_generator.py` 已经依赖：

```python
assert candidate.score_breakdown["recovery_complexity"] >= 0.0
```

`docs/algorithm-and-llm/core-algorithm-theory-v2.md` 也明确写了：

```text
Rec = score_breakdown.recovery_complexity
当前等价于 1 - fallback_depth
```

### 2.2 差距

当前的主要问题有三点：

1. `recovery_complexity` 在论文表达里是恢复复杂度，但代码里可能只是 `fallback_depth` 的近似补数；
2. 不同候选类型、不同阶段的恢复难度并不完全等价于 `fallback_depth`；
3. 若后续要做消融，必须能回答“这个项到底是由哪些恢复能力构成的”。

## 3. 风险

如果这个项不显式建模，论文中会出现如下解释断层：

- 公式写的是理论恢复复杂度；
- 实现里却只是一个单一 fallback 代理；
- 审稿人可能认为静态评分缺少足够的恢复结构信息。

## 4. 建议方案

建议把 `recovery_complexity` 固定为 recoverability 的补量，并明确来源优先级：

```text
recoverability =
  0.30 * retry_budget_ratio
+ 0.30 * local_patchability
+ 0.25 * prefix_preservability
+ 0.15 * evidence_reusability

recovery_complexity = 1 - recoverability
```

### 4.1 来源优先级

1. 若 `belief_state` 或 `runtime_state_summary` 已提供派生分量，优先使用；
2. 若缺失部分分量，用显式默认值补齐，但必须记录 `derived_from_defaults=true`；
3. 不建议再直接使用裸 `fallback_depth` 作为长期主语义，只能作为兼容回退。

### 4.2 建议写入位置

- `src/agents/candidate_generator/generator.py`
- `src/agents/planner.py::_score_payload()`
- `src/models/runtime_schemas.py`
- `docs/algorithm-and-llm/core-algorithm-theory-v2.md`（理论说明）

## 5. 最小实现提案

### 5.1 结构

```python
score_breakdown["recovery_complexity"] = 1.0 - recoverability
score_breakdown["recoverability"] = recoverability
metadata["recovery_complexity_source"] = {
    "schema_version": "recovery_complexity.v1",
    "derived_from": [
        "retry_budget_ratio",
        "local_patchability",
        "prefix_preservability",
        "evidence_reusability",
    ],
}
```

### 5.2 约束

- `recovery_complexity` 与 `fallback_depth` 不能同时作为主语义来源；
- 若继续保留 `fallback_depth`，它应只作为 `recoverability` 的一个输入项，而不是结果项；
- 所有分量需裁剪到 `[0, 1]`。

## 6. 测试建议

1. 当 `local_patchability` 提升时，`recovery_complexity` 应下降；
2. 当 `evidence_reusability` 缺失时，字段应退化但不得静默漂移；
3. 当 `retry_budget_ratio` 很低时，`recovery_complexity` 应上升；
4. `score_breakdown` 中应同时可见 `recoverability` 与 `recovery_complexity` 的关系。

## 7. 验收标准

- `recovery_complexity` 的定义在代码、测试、理论文档三处一致；
- `fallback_depth` 不再是唯一来源；
- planner 的静态评分可以引用该字段做恢复维度解释。