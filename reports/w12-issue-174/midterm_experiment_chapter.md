# W12 中期实验章节草稿（Issue #174 Interim Pack）

- generated_at: `2026-03-19T09:42:13.662187+00:00`
- vertical_summary: `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv`
- governance_summary: `output/experiment/w12-expr-2/issue173-governance-review/governance_metrics_summary.json`
- figure_index: `reports/w12-issue-174/figure_table_index.csv`

## 1. 章节范围

- 本草稿优先服务 2026-03-19 中期报告，直接复用已完成的 #171 纵向实验与 #173 治理复核产物。
- `#172` 横向对比因外部平台依赖延期，本稿显式保留占位与风险说明，不把缺口伪装成已完成结果。
- 因此本稿适合作为“当前可展示证据包”，不应宣称已经满足 #174 的全部验收标准。

## 2. 纵向结果（A0-A6）

| 组别 | runs | 最终成功率 | 可执行 Plan 率 | Patch 最小性命中率 | suffix_replan 前缀保持率 | 平均时延(ms) |
| --- | --- | --- | --- | --- | --- | --- |
| A0 | 12 | 0.0% | 0.0% | 100.0% | - | 2000.0 |
| A1 | 12 | 0.0% | 0.0% | 100.0% | - | 2083.3 |
| A2 | 12 | 0.0% | 0.0% | 100.0% | - | 2000.0 |
| A3 | 12 | 0.0% | 100.0% | - | - | 0.0 |
| A4 | 12 | 0.0% | 100.0% | - | - | 0.0 |
| A5 | 12 | 0.0% | 100.0% | - | - | 0.0 |
| A6 | 12 | 0.0% | 100.0% | - | - | 0.0 |

结论摘要：
- 当前数据中 `schema_valid_rate` 维持高位，但 `success_rate` 在 A0-A6 全部为 0，说明实验框架已打通，方法效果尚未形成正向主结果。
- `A2 -> A3` 在 `executable_plan_rate` 上出现正向增量，但未转化为最终成功率提升；这更像执行链通路打通，而不是任务成功闭环已经成立。
- `patch_minimality_hit_rate` 在现有纵向汇总里可见，但 `suffix_replan_prefix_preservation_rate` 缺失样本，后续正式发布仍会被门禁阻断。

## 3. 机制增量证据

| 增量 | metric | delta | ci_low | ci_high |
| --- | --- | --- | --- | --- |
| A2 -> A3 | executable_plan | 1.000 | 1.000 | 1.000 |
| A2 -> A3 | patch_event_count | -1.000 | -1.000 | -1.000 |
| A0 -> A1 | duration_ms | 83.333 | 0.000 | 250.000 |
| A1 -> A2 | duration_ms | -83.333 | -250.000 | 0.000 |
| A2 -> A3 | duration_ms | -2000.000 | -2000.000 | -2000.000 |

## 4. 治理结果

| 组别 | tasks | WAITING 链完整率 | 回放成功率 | 失败可追溯率 | 快照关联率 |
| --- | --- | --- | --- | --- | --- |
| A0 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |
| A1 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |
| A2 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |
| A3 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |
| A4 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |
| A5 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |
| A6 | 12 | 0.0% | 0.0% | 100.0% | 100.0% |

- 全局 tasks: `84`
- 全局失败可追溯率: `1.0`
- 全局 WAITING 链完整率: `0.0`
- 全局回放成功率: `0.0`

治理解读：
- `failure_traceable_rate=1.0` 说明失败事件的追踪字段齐全，适合作为论文中的工程治理证据。
- `waiting_chain_complete_rate=0.0` 与 `replay_success_rate=0.0` 说明主实验批次缺少可回放的人机决策链，当前治理证据主要依赖 #151 的演示回放样例补齐。

## 5. 横向对比（E0/E1/E2）状态

E0/E1/E2 横向对比对应 issue #172。由于其依赖外部平台，当前中期窗口先显式延期，不把缺失结果伪装成已完成。

建议在中期报告中这样处理：
- 将 E0/E1/E2 明确标记为“下阶段实验”，保留表位与公平性约束说明。
- 报告正文只陈述：横向基线设计已冻结，但由于外部平台依赖，本轮未纳入主结果表。

## 6. 可直接引用的图表来源

- 表1：`output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv`
- 表2：保留空位，等待 #172 产物补齐。
- 图1/图2：由 `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv` 与机制增量 CSV 派生。
- 图3：由 `output/experiment/w12-expr-2/issue173-governance-review/governance_metrics_by_group.csv` 派生。

## 7. 风险与限制

- 当前 A0-A6 结果更能证明实验管线可复现，而不能证明方法效果优于基线。
- 主实验治理样本缺少 WAITING 链，必须结合 #151 的标准回放样例展示 HITL 审计能力。
- 横向对比缺失意味着 #174 目前只能提交中期版草稿，不能按原 issue 口径宣告完成。
