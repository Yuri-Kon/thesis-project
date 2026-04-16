# Evidence Template Notes

## Chart Template

每张图表至少补齐以下信息：

- 标题：图表要表达的命题
- 图表文件：`reports/<report_pack>/charts/<chart_id>.<ext>`
- 数据源说明：`reports/<report_pack>/charts/<chart_id>.sources.json`
- 上游聚合表：如 `vertical_metrics_summary.csv`
- 结论一句话：图表支撑的核心判断
- 追溯链：
  - `config_path`
  - `resolved_config_snapshot_path`
  - `run_log_index_path`
  - `aggregate_source_path`

## Case Study Template

每个案例文档建议包含以下段落：

- 背景：任务、分组、难度、run_id
- 触发点：失败/升级/止损/回退发生在什么位置
- 关键证据：
  - `run_log_index.csv`
  - `event_log`
  - `snapshot`
  - `task_report`
- 动作与原因：系统为何 patch / replan / stop
- 结果：成功、失败或止损收益
- 结论：该案例对论文或 issue 说明了什么

## Summary Row Alias

若案例或图表引用聚合表中的单行结果，建议生成稳定别名：

- `summary-row-<task_key>-<group_id>`
- `summary-row-overall-<group_id>`

这样后续在 `evidence-index.json.upstream_refs` 中可以稳定引用，而不依赖临时行号。
