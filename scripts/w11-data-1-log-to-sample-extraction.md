# W11-Data-1: 日志到训练样本抽取说明

## 目标

从运行产物中抽取训练样本，统一输出以下结构：

- `context`
- `candidates`
- `selected`
- `outcome`
- `audit_trace`

并提供样本到原始事件的映射与统计结果。

## 输入来源

- 日志：`data/logs/*.jsonl`
- 快照：`data/snapshots/*.jsonl`
- 报告：`output/reports/*.json`
- 指标：`output/metrics/*.json`
- ToolKG：`src/kg/protein_tool_kg.json`

## 使用方式

```bash
uv run python scripts/extract_training_samples.py \
  --logs-dir data/logs \
  --snapshots-dir data/snapshots \
  --reports-dir output/reports \
  --metrics-dir output/metrics \
  --tool-kg-path src/kg/protein_tool_kg.json \
  --output-dir output/training/w11-data-1
```

## 输出文件

- `samples.jsonl`：训练样本（每个 task 一条样本）
- `sample_event_mapping.jsonl`：样本与原始事件映射（逐事件）
- `stats.json`：抽取统计（总量、成功/失败、HITL 占比、工具分布）

## 关键字段

### `context`

- `task_id`
- `status_path`
- `start_status` / `end_status`
- `has_hitl`
- `time_window.first_ts/last_ts`

### `candidates`

每个候选包含：

- `candidate_id`
- `score_breakdown`
- `risk_level`
- `cost_estimate`
- `payload`
- `tool_id`
- `capability_id`
- `io_type`
- `adapter_mode`
- `tool_version`
- `source_link`
- `provider`
- `model_id`

### `selected`

- `decision_id`
- `pending_action_id`
- `choice`
- `selected_candidate_id`
- `action_type`
- `event_id`
- `ts`

### `outcome`

- `final_status`
- `result`
- `step_results`
- `step_failure_types`
- `report_path`
- `metrics_paths`

### `audit_trace`

- `event_log_path`
- `snapshot_path`
- `event_ids`
- `decision_event_ids`
- `pending_action_ids`
- `snapshot_ids`
- `decision_history`

## 可复现性说明

脚本按 `task_id` 和事件行号稳定排序输出；同一输入目录重复执行可得到一致的样本与映射结果。
