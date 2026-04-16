# W12 Issue #173：治理指标复核操作手册

## 目标

生成可复现的治理证据，用于评估：

- 审计链完整性
- 失败可追溯性
- 决策回放正确性

并将治理输出与既有纵向实验结果合并对照。

## 输入

- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv`
- `output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl`

## 命令

```bash
uv run python scripts/evaluate_w12_issue173_governance.py
```

## 输出

生成目录：`output/experiment/w12-expr-2/issue173-governance-review/`

- `governance_metrics_summary.json`
- `governance_metrics_by_group.csv`
- `governance_vs_vertical_comparison.csv`
- `governance_replay_sample.md`
- `governance-report.md`

## 指标定义

- `waiting_chain_complete_rate`：
  - 按 `pending_action_id` 检查有序 `WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT`
- `replay_success_rate`：
  - 严格顺序可回放链路占比
- `failure_traceable_rate`：
  - `STEP_FAILED` 中包含 `step_id + tool/tool_id + failure_code` 的占比
- `snapshot_linked_rate`：
  - run index 声明的 `snapshot_path` 在磁盘存在的占比

## 排障

- 日志缺失：
  - 检查 run index 中 `event_log_path` 与磁盘文件是否存在
- 回放成功率为 0：
  - 数据集中可能缺少 decision-applied 样本，可结合 #151 的 demo 回放样例核对
- 与纵向结果不一致：
  - 查看 `governance_vs_vertical_comparison.csv` 的分组差异
