# Issue: P2-1 统一公式版本号、schema 版本号与文档版本号

## 类型

- Priority: P2
- Scope: algorithm / versioning / traceability
- Phase: CEBRA-WP P2 文档与表达增强
- Body language: Chinese
- 状态：已实现
- 本文件定位：P2-1 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

当前代码和文档里同时出现了多种版本标记：

- `posterior_score.v1`
- `runtime_evaluator.action_utility.v1`
- `planner.runtime_adjustment.*.v1`
- `static_score.v1`

这些版本号本身没有错，但它们缺少一个更高层的统一命名框架。结果是：单个字段可以追踪，整套算法版本却不够清晰。

## 2. 当前代码核查结论

`runtime_evaluator.py`、`objective_ranker_adapter.py` 和理论文档中都已经在用版本字符串，但没有统一总表。

## 3. 风险

- 论文定稿后很难说明“这套算法到底是 v2 里的哪一版”；
- 代码演进后，不同子模块的版本号可能各自前进；
- 审稿/答辩时不容易讲清“主算法版本”和“子公式版本”的关系。

## 4. 建议方案

建立三级版本体系：

```text
A. 算法总版本：cebra_wp.v2
B. 子公式版本：posterior_score.v1 / action_utility.v1 / static_score.v1
C. 实现引用版本：impl:<module>.<symbol>.v1
```

## 5. 最小实现提案

在设计文档和实现文档里增加版本对照表：

```text
cebra_wp.v2
├─ static_score.v1
├─ posterior_score.v1
├─ action_utility.v1
└─ runtime_adjustment.v1
```

当前实现总表位于：

```text
src/models/algorithm_versions.py
docs/algorithm-and-llm/algorithm-version-registry.md
docs/algorithm-and-llm/core-algorithm-theory-v2.md
```

## 6. 测试建议

1. 所有对外可见的 schema payload 都有版本号；
2. 版本号命名在同类字段上保持一致；
3. 文档能从算法总版本追溯到子公式版本。

## 7. 验收标准

- 版本体系有总表；
- 子模块版本能归档到算法总版本；
- 后续论文引用时不再混乱。
