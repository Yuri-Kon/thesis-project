# Issue: P1-6 明确 posterior 中 binding 语义的输出策略

## 类型

- Priority: P1
- Scope: algorithm / posterior objective / evidence semantics
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：已实现
- 本文件定位：P1-6 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

`ObjectiveRankerAdapter` 的 posterior 体系目前已经支持：

- `generic_objective`
- `stability`
- `function`
- `novelty`
- `structure_quality`

但权重预设中 `binding` 已经存在，并且代码语义上又把 binding 证据折叠进了 `generic_objective`。这说明 binding 不是完全缺失，而是处在“是否应该独立暴露”的灰区。

## 2. 当前代码核查结论

### 2.1 已存在的现象

- `_OBJECTIVE_TYPE_WEIGHT_PRESETS` 有 `binding`；
- `_POSTERIOR_COMPONENTS` 里没有独立 `binding`；
- posterior payload 也没有 `binding` 字段；
- binding 证据通过 `binding_score` / `best_pose` / `docking` 代理进入 generic objective。

### 2.2 差距

当前差距不是单纯“少一个字段”，而是需要明确策略：

1. binding 是否应该成为独立 posterior component；
2. 如果不独立，代码和文档必须明确“binding proxy 属于 generic objective”；
3. 如果独立，则需要同步更新 schema、测试和 planner 接口。

## 3. 风险

如果不明确，后续会出现两个版本的理解：

- 论文以为 binding 是单独一个 component；
- 代码其实没有单独输出 binding；
- 评审时很容易被问“binding 到底去哪了”。

## 4. 建议方案

建议先保持“折叠到 generic objective”的实现，但把策略显式化：

```text
binding = generic_objective 的证据代理之一，而不是独立 component
```

同时在 posterior payload 中补一个说明字段：

```python
"binding_policy": "folded_into_generic_objective"
```

如果后续论文需要更强理论表达，再单独拆 binding component，但那属于下一轮设计决策。

## 5. 最小实现提案

### 5.1 建议 metadata

```python
posterior_score["binding_policy"] = "folded_into_generic_objective"
posterior_score["binding_evidence"] = {
    "source": "binding_score|best_pose",
    "role": "proxy",
    "target_component": "generic_objective",
    "source_fields": ["binding_score", "best_pose"],
}
```

### 5.2 建议文档说明

- 当前版本不引入独立 binding component；
- binding 证据只影响 generic objective；
- 若 future version 要拆分，必须同步升级 `schema_version`。

## 6. 测试建议

1. `binding` 证据存在时，posterior 应能记录 proxy 来源；
2. posterior payload 应能明确说明 binding 的处理策略；
3. 不应出现 `binding` 权重存在但输出缺失而没有解释的情况。

## 7. 验收标准

- binding 的语义处置有唯一结论；
- 论文表述、schema、测试三者一致；
- 不再让 binding 处于“权重存在但组件缺失”的模糊状态。
