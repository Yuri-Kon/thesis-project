# 数据一致性证据索引

更新时间：2026-05-10

本目录用于集中说明系统验证中与状态迁移、人工确认、恢复流程、快照恢复和报告产物相关的原始证据。当前不复制大批量运行产物，只建立可追溯索引；若论文附录需要固定样本，可再从下列路径抽取关键 JSONL/JSON。

完整证据编号见 `../evidence-index.md`，测试用例映射见 `../test-case-table.md`。

## 1. 已编号原始证据

| 编号 | 原始路径 | 覆盖内容 | 支撑用例 |
|---|---|---|---|
| EVD-LOG-01 | `data/logs/int_deterministic_retry_patch_to_done.jsonl`、`data/snapshots/int_deterministic_retry_patch_to_done.jsonl` | retry exhausted 后自动 patch 到 DONE 的 EventLog 与 Snapshot | TC-S12 |
| EVD-LOG-02 | `data/logs/int_layered_patch_*.jsonl`、`data/snapshots/int_layered_patch_*.jsonl` | 分层 patch、远程到本地 fallback、高风险 patch 等恢复场景 | TC-S12 |
| EVD-LOG-03 | `data/logs/int_s6_*.jsonl`、`data/snapshots/int_s6_*.jsonl` | S6 控制层 E2E、patch decision replay、matrix S3 replan、terminal stop 审计链 | TC-S12、TC-S13 |
| EVD-LOG-04 | `data/logs/task_auto_plan.jsonl`、`data/logs/task_auto_patch_repeat.jsonl`、`data/logs/task_auto_replan*.jsonl` | 自动计划、自动 patch、自动 replan 的事件链 | TC-S03、TC-S12、TC-S13 |
| EVD-LOG-05 | `output/reports/thesis-final-smoke-fourgroup-t9-clean-001_*.json` | t9 clean run 的报告 JSON | TC-S09、TC-S11 |
| EVD-LOG-06 | `output/reports/task_*.json` | 历史任务报告 JSON 集合 | TC-S09 |

## 2. 论文可引用的数据一致性结论

| 结论 | 证据编号 | 说明 |
|---|---|---|
| 等待态与恢复流程具有可审计事件链 | EVD-TEST-02、EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 | focused pytest 覆盖状态迁移、HITL、snapshot recovery；原始 JSONL 提供事件链样本 |
| retry 失败后不会绕过恢复流程直接终止 | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02 | 恢复专项测试覆盖 retry -> patch/replan；原始日志保留 patch 到 DONE 场景 |
| terminal stop 会进入 FAILED 且保留审计链 | EVD-TEST-02、EVD-TEST-03、EVD-LOG-03 | unit/integration 测试和 S6 日志共同支撑止损机制 |
| 工具执行和报告产物可追溯到 run/task | EVD-EXP-01、EVD-LOG-05、EVD-LOG-06 | t9 clean run 聚合和报告 JSON 可用于追踪 StepResult、scores、artifacts |

## 3. 后续可补固定样本

| 样本 | 建议目标路径 | 用途 |
|---|---|---|
| 等待态 snapshot 样本 | `snapshots/waiting-plan-confirm-sample.json` | 证明 `pending_action_id`、`completed_step_ids`、`artifacts.runtime_state` 持久化 |
| retry -> patch Plan diff | `plan-patch-diff/retry-patch-sample.diff` | 证明 patch 只影响目标步骤或计划后缀 |
| terminal_stop EventLog 摘要 | `event-logs/terminal-stop-sample.jsonl` | 证明 `WAITING_* -> FAILED` 与审计事件一致 |
| 正常 DONE 报告样本 | `reports/done-report-sample.json` | 证明 `DesignResult`、scores、risk flags、structure artifact 摘要完整 |
