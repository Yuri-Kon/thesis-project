# Issue: P1-4 将 belief-state 更新规则文档化为可追踪的 B(x_t, o_t, h_t)

## 类型

- Priority: P1
- Scope: algorithm / belief-state / runtime adaptation
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：待实现
- 本文件定位：P1-4 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

理论 v2 把运行时状态写成：

```text
x_{t+1} = B(x_t, o_t, h_t)
```

其中 `B` 是 belief-state 更新器。当前 `src/workflow/belief_state.py` 已经存在确定性的 Lite belief-state 更新逻辑，而且测试也能稳定复现。但问题在于：代码能算，不代表论文里已经能解释清楚“观测如何改变每个维度”。

## 2. 当前代码核查结论

### 2.1 已实现状态维度

`RuntimeState` 主要包含：

- `p_success`
- `p_structural_failure`
- `recovery_margin`
- `expected_remaining_cost`
- `evidence_sufficiency`

### 2.2 已实现更新信号

`update_runtime_state()` 已根据：

- `step_result`
- `safety_result`
- `failure_context`
- `completed_steps`
- `total_steps`

来更新状态。

### 2.3 差距

当前差距是缺少“更新表”：

1. 哪类成功会提升 `p_success`；
2. 哪类失败会推高 `p_structural_failure`；
3. 哪类恢复动作会消耗 `recovery_margin`；
4. 哪类证据会提升 `evidence_sufficiency`；
5. 这些增减为什么是当前这个数值。

## 3. 风险

如果不补更新表，理论表达会停留在抽象层：

- 论文里写 `B`；
- 代码里是若干 if/elif；
- 读者无法从代码逆推理论。

## 4. 建议方案

在设计文档或代码 docstring 中补一张稳定的更新表，至少覆盖以下映射：

```text
success at structural step     -> p_success ↑, p_structural_failure ↓, recovery_margin ↑
failed structural step         -> p_success ↓, p_structural_failure ↑, recovery_margin ↓
retry exhausted                -> p_success ↓, recovery_margin ↓
safety warn/block              -> p_success ↓, p_structural_failure ↑, recovery_margin ↓
patch_local recovery           -> recovery_margin ↓ slightly, expected_remaining_cost ↑
suffix_replan recovery         -> p_success ↓, p_structural_failure ↑, recovery_margin ↓
objective evidence progress    -> evidence_sufficiency ↑
```

## 5. 最小实现提案

### 5.1 建议新增结构

```python
belief_update_rules = [
    {
        "signal": "step_result.success@structural",
        "delta": {"p_success": +0.16, "p_structural_failure": -0.13, "recovery_margin": +0.06},
    },
    ...
]
```

### 5.2 建议位置

- `src/workflow/belief_state.py`
- `docs/algorithm-and-llm/core-algorithm-theory-v2.md`
- `docs/algorithm-and-llm/core-algorithm-code-gap-review.md`

## 6. 测试建议

1. 不同 failure type 的更新方向应与文档一致；
2. `evidence_sufficiency` 在 objective progress 提升时应上升；
3. `retry_exhausted` 应显著降低 recovery 余量；
4. update 结果可回放且稳定。

## 7. 验收标准

- `B(x_t, o_t, h_t)` 有明确更新表；
- 代码、设计文档、测试三者一致；
- 论文中可以直接引用该表作为补充说明。