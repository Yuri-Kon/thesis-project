# Issue: P1-5 将 Top-K diversity 从工程细节提升为理论约束

## 类型

- Priority: P1
- Scope: algorithm / candidate generation / diversity theory
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：待实现
- 本文件定位：P1-5 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

当前候选生成已经不是简单排序，而是使用 `_select_diverse_top_k()`。这是好事，因为 Top-K 不只是“选分最高的 k 个”，还承担保留替代路径、降低单一路径偏置的作用。

但理论 v2 里目前对 Top-K 的描述仍偏简：

```text
TopK_t = top_k(Pi_t, U_pi)
```

这不足以表达“多样性约束”或“替代路径保留”的理论价值。

## 2. 当前代码核查结论

### 2.1 已存在能力

`src/agents/candidate_generator/generator.py` 中确实存在 diversified top-k 选择逻辑，测试也已覆盖 Top-K 候选生成。

### 2.2 差距

1. 理论层只写 Top-K，没有显式 diversity term；
2. 工程层已经在做 diversified selection，但论文无法直接说明它解决了什么；
3. 后续实验无法清楚区分“排序收益”和“多样性收益”。

## 3. 风险

如果不补理论层，`_select_diverse_top_k()` 会被看成一个实现技巧，而不是算法部分。

## 4. 建议方案

建议把 Top-K 写成下面两种形式之一：

### 方案 A：显式 diversity penalty

```text
TopK_t = arg top-k_{π∈Π_t} [U_π(π, x_t) - λ_div · DiversityPenalty(π, TopK_{t-1})]
```

### 方案 B：能力覆盖约束

```text
TopK_t = SelectDiverseTopK(Π_t, U_π, k, capability_coverage)
```

推荐优先采用方案 B 的实现描述，方案 A 的论文表达更清晰。

## 5. 最小实现提案

### 5.1 建议记录的元数据

```python
metadata["topk_diversity"] = {
    "schema_version": "topk_diversity.v1",
    "strategy": "capability_coverage",
    "selected_by": "_select_diverse_top_k",
    "diversity_signals": [...],
}
```

### 5.2 建议文档表达

- Top-K 不是纯排序，而是“高分 + 结构多样性”的联合选择；
- 多样性优先保留不同能力、不同失败恢复路径、不同成本层级；
- 若候选过少，可退化为纯排序，但必须在 metadata 标记退化。

## 6. 测试建议

1. 候选分数相近时，Top-K 应保留不同 capability 的候选；
2. 当 diversity 信息缺失时，应可退化但可追踪；
3. `_select_diverse_top_k()` 的结果应与单纯 top-k 在某些边界样例上不同；
4. 退化路径不得悄悄改变排序语义。

## 7. 验收标准

- 理论里有明确的 diversity 表达；
- 工程实现能解释“为什么保留这些候选”；
- 实验消融可以区分 diversity 与 score ranking 的贡献。