# 算法实验分组与 runtime policy 映射

## 1. 目的

本文档固定论文主结果组与代码 `RuntimeEvaluator.policy_mode` 的一一对应关系。
它与设计仓库 `../thesis-project.design/docs/experiment/algorithm-group-paper-mapping.md`
保持同一叙事，但以当前代码可执行的 mode 为准，供评估脚本、论文表格和测试共享。

## 2. 唯一映射表

| 代码 mode | 论文组 ID | 论文组名 | 语义 | 回答的问题 | 预期效果 | 重点指标 |
| --- | --- | --- | --- | --- | --- | --- |
| `static_top1` | `static_top1` | 静态单链基线 | 仅采用静态最高分候选，不消费运行时观测做重排 | 静态单链路是否足够支撑高代价工作流 | 成本最低但最缺少失败恢复与替代路径收益 | success_rate, high_cost_call_count, early_failure_rate |
| `static_gate` | `fixed_threshold_gate` | 静态门控基线 | 保留静态过滤/门控，但不启用运行时重排 | 简单静态门控是否已经足够 | 比 static_top1 更稳健，但无法利用运行时失败证据 | gate_pass_rate, manual_intervention_rate, wasted_call_rate |
| `dynamic_observation_only` | `dynamic_no_belief_state` | 动态观测但不使用 belief-state | 保留动态 patch/replan 观测链路，但 runtime adjustment 为 passthrough | 仅有动态观测和恢复动作、没有 belief-state 是否足够 | 可隔离恢复机制收益，但不体现 belief-state 的重排增益 | patch_success_rate, replan_success_rate, recovery_cost |
| `lite_belief_state` | `lite_belief_state` | 完整 CEBRA-WP | 启用 Lite belief-state、runtime adjustment 与 action utility | belief-state 是否带来最后一段 runtime 决策增益 | 应改善高代价调用控制、止损质量和整体成功率 | success_rate, high_cost_call_count, stop_quality, rerank_delta |

## 3. 代码约束

- `src.workflow.runtime_evaluator.RUNTIME_POLICY_ABLATION_GROUPS` 是评估脚本可读取的代码侧 SSOT。
- 新增 `policy_mode` 时，必须同步更新映射表、本文档和 `tests/unit/test_runtime_evaluator.py::TestPolicyModes`。
- `lite_belief_state` 是唯一 `full_runtime_adjustment=True` 的组。
- `static_top1` 与 `static_gate` 都禁用 rerank，但论文组名与回答的问题不同，不得混用。
- `dynamic_observation_only` 启用动态观测链路，但不使用 belief-state，也不产生非零 runtime adjustment。

## 4. 与设计文档的关系

设计仓库的论文主结果组写作名为：

```text
static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state
```

当前代码中的可执行 mode 为：

```text
static_top1 / static_gate / dynamic_observation_only / lite_belief_state
```

因此本文保留 `paper_group_id` 来连接论文名，并保留 `policy_mode` 来连接运行配置。
论文表格应展示 `paper_group_id` 或论文组名；评估配置应使用 `policy_mode`。
