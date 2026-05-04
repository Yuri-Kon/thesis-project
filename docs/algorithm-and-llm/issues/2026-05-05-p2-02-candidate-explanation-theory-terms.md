# Issue: P2-2 将候选解释中的工程文案提升为理论术语

## 类型

- Priority: P2
- Scope: algorithm / explanation / UI text
- Phase: CEBRA-WP P2 文档与表达增强
- Body language: Chinese
- 状态：待实现
- 本文件定位：P2-2 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

当前候选解释已经可用，但措辞偏工程。例如：

- `Local patchability keeps more recovery options available.`
- `Suffix replan still carries residual budget pressure.`

这类句子对系统调试有帮助，但论文与展示层还可以更贴近理论对象。

## 2. 当前代码核查结论

`runtime_evaluator.py` 的 `factors`、`RerankReason` 和候选 metadata 已能输出可读解释，但还缺少理论字段挂钩：

- `recovery_margin`
- `budget_pressure`
- `evidence_sufficiency`
- `ActionBias`
- `recoverability`

## 3. 风险

如果展示文案长期保持纯工程口吻：

- 论文图表和 UI 文案会脱节；
- 调试信息可读，但理论贡献不突出；
- 读者很难把系统解释和公式对象对齐。

## 4. 建议方案

对候选解释增加 `term` 与 `formula_ref`：

```python
{
    "term": "recovery_margin",
    "formula_ref": "Eq.(runtime_delta)",
    "message": "Recovery headroom and fallback depth shape the shadow rerank bonus."
}
```

建议展示层优先使用下列术语：

- `recovery_margin`
- `budget_pressure`
- `evidence_sufficiency`
- `ActionBias`
- `recoverability`

## 5. 最小实现提案

- 解释字段保留工程原文；
- 增加一层理论标签；
- UI / 日志 / 论文图表优先显示理论标签，展开时再看工程原文。

## 6. 测试建议

1. 同一条 explanation 同时带工程文案和理论术语；
2. 展示层可按需要选择简版或详版；
3. 理论术语与公式引用一致。

## 7. 验收标准

- 候选解释可以直接用于论文图注；
- 工程 debug 细节仍然保留；
- 两种表达层不互相覆盖。