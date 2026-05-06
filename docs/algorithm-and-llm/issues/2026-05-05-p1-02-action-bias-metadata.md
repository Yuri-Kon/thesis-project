# Issue: P1-2 显式引入 ActionBias 命名层并统一 runtime adjustment 元数据

## 类型

- Priority: P1
- Scope: algorithm / runtime adjustment / action selection explanation
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：待实现
- 本文件定位：P1-2 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

理论 v2 在动作效用之外，还引入一个小幅修正项：

```text
U_a = ... + κ_a · ActionBias(π, x_t)
```

它的意义不是替代主效用，而是把“局部恢复更顺手”“停下更合理”“某些动作对当前状态有额外偏置”这类信号显式命名。

当前 `src/workflow/runtime_evaluator.py::compute_runtime_delta()` 已经在做类似事情，但结果被分散为 `bonus / penalty / factor`，并没有统一叫做 `ActionBias`。这样论文能写公式，但实现链路很难一眼看出这个偏置在哪里产生、在哪里消耗。

## 2. 当前代码核查结论

### 2.1 已有行为

`compute_runtime_delta()` 中已有三类偏置：

- `patch_local` 的 recovery bonus；
- `suffix_replan` 的 replan bonus / penalty；
- `stop` 的 guard penalty。

同时它会写入：

- `RuntimeAdjustmentSummary`
- `RerankReason`
- `factors`

### 2.2 差距

当前差距主要在“命名层”而不是“数值层”：

1. 这些偏置没有统一聚合成一个 `ActionBias` 结构；
2. `RerankReason.factors` 里虽然有 factor，但缺少统一父项；
3. planner 侧如果要解释 runtime adjustment，很难把这些小修正归到同一个理论对象。

## 3. 风险

如果不统一命名层，后续论文容易变成：

- 主公式写 `ActionBias`；
- 代码里却是 `patch_bonus`、`stop_penalty`、`replan_bonus` 三套散装名字。

这会让审稿人觉得理论和实现之间缺少中间层。

## 4. 建议方案

把现有偏置统一包装为：

```text
action_bias = {
  action: "continue" | "patch_local" | "suffix_replan" | "stop",
  value: float,
  factors: [...],
  source_refs: [...]
}
```

并在 runtime adjustment metadata 中记录：

```text
runtime_adjustment.action_bias
runtime_adjustment.formula_version = "v1"
runtime_adjustment.source_refs
```

## 5. 最小实现提案

### 5.1 结构

```python
action_bias = {
    "action": action,
    "value": round(delta, 6),
    "factors": [
        {"category": "cost", "signal": "cost_pressure", ...},
        {"category": "recovery", "signal": "fallback_depth", ...},
    ],
    "source_refs": ["sid:planner.algorithm.runtime_adjustment_formula", "impl:runtime_evaluator.compute_runtime_delta.v1"],
}
```

### 5.2 约束

- `ActionBias` 只表示“动作级别小幅修正”，不重写主评分；
- `ActionBias` 不应与 `runtime_adjustment.value` 重复表达两次不同数值；
- factor 的 message 要能对应论文解释句，而不是纯工程日志。

## 6. 测试建议

1. `patch_local`、`suffix_replan`、`stop` 三种 action 都能生成 `action_bias`；
2. `ActionBias.value` 与 `runtime_adjustment.value` 一致；
3. `RerankReason` 中可以直接追溯到 `action_bias.factors`；
4. 在不同 `runtime_policy` 下，偏置结构保持稳定。

## 7. 验收标准

- 论文里的 `ActionBias` 有唯一代码承载点；
- factor 解释不再分散在多个字段里；
- runtime adjustment 的理论对象、代码对象、测试对象一致。