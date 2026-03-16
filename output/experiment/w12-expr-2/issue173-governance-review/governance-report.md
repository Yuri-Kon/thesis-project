# 治理复核报告（governance-review）

## 输入
- run_log_index：`output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv`
- replay_sample_log：`/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl`
- generated_at：`2026-03-15T21:07:55+00:00`

## 复现命令
- `python scripts/evaluate_w12_issue173_governance.py --run-log-index output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv --output-dir output/experiment/w12-expr-2/issue173-governance-review`

## 全局治理指标

- tasks：`84`
- logs_present_rate：`1.000000`
- snapshot_linked_rate：`1.000000`
- waiting_chain_complete_rate：`0.000000`
- replay_success_rate：`0.000000`
- failure_traceable_rate：`1.000000`

## 分组指标

| group_id | tasks | waiting_chain_complete_rate | replay_success_rate | failure_traceable_rate | snapshot_linked_rate |
|---|---:|---:|---:|---:|---:|
| A0 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| A1 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| A2 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| A3 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| A4 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| A5 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| A6 | 12 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |

## 纵向结果合并（已有值 vs 重算值）

| group_id | existing_waiting_chain_complete_rate | existing_failure_traceable_rate | recomputed_waiting_chain_complete_rate | recomputed_failure_traceable_rate |
|---|---:|---:|---:|---:|
| A0 | 0.0 | 1.0 | 0.000000 | 1.000000 |
| A1 | 0.0 | 1.0 | 0.000000 | 1.000000 |
| A2 | 0.0 | 1.0 | 0.000000 | 1.000000 |
| A3 | 0.0 | 1.0 | 0.000000 | 1.000000 |
| A4 | 0.0 | 1.0 | 0.000000 | 1.000000 |
| A5 | 0.0 | 1.0 | 0.000000 | 1.000000 |
| A6 | 0.0 | 1.0 | 0.000000 | 1.000000 |

## 治理口径说明

- `waiting_chain_complete_rate` / `replay_success_rate`：基于 `pending_action_id` 检查有序 `WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT` 链路。
- `failure_traceable_rate`：要求 `STEP_FAILED` 记录包含 `step_id`、`tool/tool_id`、`failure_code`。
- `snapshot_linked_rate`：检查 run index 指定的 `snapshot_path` 是否存在。

## 异常排查提示

- 若 `waiting_chain_complete_rate` 低：优先检查是否缺失 Decision/WAITING_EXIT 事件。
- 若 `failure_traceable_rate` 低：优先检查 step failure payload 是否缺失 `failure_code` 与工具元数据。
