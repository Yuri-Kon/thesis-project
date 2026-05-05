# Issue: P2-4 在调试/展示面板中只暴露核心理论对象

## 类型

- Priority: P2
- Scope: UI / debug / explanation surface
- Phase: CEBRA-WP P2 文档与表达增强
- Body language: Chinese
- 状态：已实现
- 本文件定位：P2-4 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

如果后续需要展示算法解释，不应该把所有中间字段都摊开。当前 UI 约束也明确：inspector 是快速概览面板，只显示状态，不展开定义列表。

因此展示层更适合只暴露少量理论对象：

- `static_score`
- `runtime_adjustment`
- `final_score`
- `selected_action`
- `action_utility`
- `evidence_sufficiency`

## 2. 当前代码核查结论

`runtime_evaluator.py` 和 `recovery.py` 已经有这些对象的来源，但展示层还没有把它们收敛成一个统一的“理论解释视图”。

## 3. 风险

如果把所有字段都直接展开：

- UI 会很快变得冗长；
- 读者抓不到主线；
- 调试面板会把理论对象和工程细节混在一起。

## 4. 建议方案

展示层只做摘要，不做展开：

```text
static_score -> runtime_adjustment -> final_score -> selected_action
```

附带少量支撑字段：

- `action_utility`
- `evidence_sufficiency`
- `budget_pressure`

## 5. 最小实现提案

- inspector 使用 chip / summary 行；
- 详细字段进入折叠区或日志；
- 不在快速面板中展示字段列表。

## 6. 测试建议

1. 面板只出现核心对象，不出现完整字段树；
2. 快速概览与详细日志分层；
3. 对象顺序稳定。

## 7. 验收标准

- 展示层不破坏现有简洁性；
- 核心理论对象可快速读懂；
- 复杂字段仍保留给日志/详情页。

## 8. 实现记录

- API 为 pending action detail 和 candidate display 增加精简 `theory_objects` 摘要，只包含核心理论对象，不把完整 runtime metadata 树下发到 Inspector 使用面。
- 前端新增 `TheoryObjectSummary`，在 Task Detail 的 Inspector 中稳定展示：
  `static_score -> runtime_adjustment -> final_score -> selected_action`。
- 支撑信号只展示 `action_utility`、`evidence_sufficiency`、`budget_pressure`。
- 原有 Runtime JSON / Score JSON 仍保留在 Runtime Context 折叠区，快速 Inspector 不展开完整字段树。
