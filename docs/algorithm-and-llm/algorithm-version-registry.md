# CEBRA-WP 算法版本 registry

## 1. 总版本

| 层级 | 版本 | 说明 | 代码位置 |
| --- | --- | --- | --- |
| 算法总版本 | `cebra_wp.v2` | 本论文核心算法的归档版本，对应 `core-algorithm-theory-v2.md` | `src/models/algorithm_versions.py` |
| 文档版本 | `core-algorithm-theory-v2` | 理论章节当前可引用版本 | `docs/algorithm-and-llm/core-algorithm-theory-v2.md` |

`cebra_wp.v2` 不替代子 schema 的版本号。它只说明当前论文算法由下列子公式/schema
组合而成；各子模块后续可以独立升级为 v2/v3，但必须重新归档到新的算法总版本。

## 2. 子公式与 schema 版本

| 子模块 | 子公式版本 | schema / payload 版本 | 实现引用 |
| --- | --- | --- | --- |
| 静态候选评分 | `static_score.v1` | `score_breakdown.v1` | `impl:planner.score_breakdown.v1` |
| posterior objective scoring | `posterior_score.v1` | `posterior_score.v1`, `posterior_objective.v1` | `impl:posterior_score.v1`, `impl:posterior_objective.v1` |
| runtime adjustment | `runtime_adjustment.v1` | `runtime_adjustment.v1` | `impl:planner.runtime_adjustment.v1` |
| action utility | `action_utility.v1` | `action_utility.v1`, `action_features.v1` | `impl:runtime_evaluator.action_utility.v1`, `impl:workflow.action_features.v1` |
| action bias | `action_bias.v1` | `action_bias.v1` | `impl:runtime_evaluator.compute_runtime_delta.v1` |

## 3. 层级关系

```text
cebra_wp.v2
├─ static_score.v1
├─ posterior_score.v1
│  ├─ posterior_score.v1
│  └─ posterior_objective.v1
├─ runtime_adjustment.v1
├─ action_utility.v1
│  ├─ action_utility.v1
│  └─ action_features.v1
└─ action_bias.v1
```

## 4. 维护规则

- 不为整理文档而重命名现有 payload 的 `schema_version`。
- 若某个子公式改变字段语义或公式含义，先升级子公式/schema 版本，再更新本 registry。
- 若多个子公式版本组合发生变化，创建新的算法总版本，例如 `cebra_wp.v3`。
- 论文正文引用算法整体时使用 `cebra_wp.v2`；复现实验或调试 payload 时引用具体子版本。
