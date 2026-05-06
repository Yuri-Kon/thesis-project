# Issue: P1-3 分离 expected_remaining_cost 与 budget_pressure 的语义与单位

## 类型

- Priority: P1
- Scope: algorithm / runtime state / cost semantics
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：待实现
- 本文件定位：P1-3 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

理论和设计文档中，`expected_remaining_cost` 与 `budget_pressure` 是两个不同概念：

```text
expected_remaining_cost: 剩余成本暴露，可超出 1
budget_pressure: 预算压力，通常归一化到 [0, 1.5]
```

但是代码里这两个量经常被直接互用，导致：

- 公式看起来一致；
- 语义其实已经混了；
- 论文里不容易解释 `b_t` 的真实来源。

## 2. 当前代码核查结论

### 2.1 已存在的处理

`src/workflow/runtime_evaluator.py` 里：

```python
budget_pressure = min(max(expected_remaining_cost, 0.0), 1.5)
cost_pressure = min(budget_pressure, 1.0)
```

`compute_action_utilities()` 也直接把 `expected_remaining_cost` 当作成本项读取。

### 2.2 差距

1. `expected_remaining_cost` 是原始估计；
2. `budget_pressure` 是标准化后的派生量；
3. 目前缺少明确 schema 区分；
4. 一些地方默认使用 `expected_remaining_cost`，一些地方使用 `budget_pressure`，可比性不足。

## 3. 风险

如果不拆开，论文中的预算压力项会面临两类质疑：

- 量纲不清：到底是“预计剩余成本”还是“压力指数”；
- 消融不清：实验里到底改的是哪个变量。

## 4. 建议方案

统一规则：

```text
expected_remaining_cost = 原始估计
budget_pressure = clip(expected_remaining_cost / budget_cap, 0, 1.5)
```

如果没有预算上限，就退化成：

```text
budget_pressure = clip(expected_remaining_cost, 0, 1.5)
```

并要求：

- `runtime_state` 中同时保留两个字段；
- `runtime_adjustment` / `action_utility` 只使用命名明确的一个字段；
- 文档里标明二者关系，不再互相偷换。

## 5. 最小实现提案

### 5.1 建议 schema

```python
runtime_state = {
    "expected_remaining_cost": 1.7,
    "budget_pressure": 1.2,
    "budget_cap": 2.0,
}
```

### 5.2 建议公式

```text
budget_pressure = clip(expected_remaining_cost / max(budget_cap, 0.1), 0, 1.5)
```

若无 `budget_cap`：

```text
budget_pressure = clip(expected_remaining_cost, 0, 1.5)
```

## 6. 测试建议

1. 相同 `expected_remaining_cost` 在不同 `budget_cap` 下应得到不同 `budget_pressure`；
2. `expected_remaining_cost` 允许大于 1，而 `budget_pressure` 应被裁剪；
3. action utility 只能消费约定好的预算字段；
4. stop guard 使用的预算量必须可追溯。

## 7. 验收标准

- 两个字段语义分开；
- 论文公式里的 `b_t` 对应唯一代码字段；
- 不再出现“同一个变量既是原始成本又是压力指数”的混用。