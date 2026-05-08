# Evidence Freeze Runbook

## 目标

在正式跑 W16 实验之前，先冻结实验、图表和案例证据的目录结构、命名规则与最小追溯链，避免结果出来后再返工整理证据包。

本冻结只定义约定，不新增实验执行语义，也不在本 issue 内生成最终图表或证据包。

## 目录结构约定

### 1. 运行期原始证据

- Event log：`data/logs/<task_id>.jsonl`
- Snapshot：`data/snapshots/<task_id>.jsonl`
- 单任务报告：`output/reports/<task_id>.json`
- 单任务指标：`output/metrics/<task_id>.json`

### 2. 实验批次产物

- 运行根目录：`output/experiment/<experiment_family>/<run_id>/`
- 必备文件：
  - `runs_manifest.json`
  - `resolved_config_snapshot.json`
  - `runs.jsonl`
  - `run_log_index.csv`
- 聚合结果：
  - `vertical_metrics_summary.csv`
  - `mechanism_increment_deltas.csv`
  - `patch_replan_breakdown.csv`
  - `high_cost_breakdown.csv`
  - `offline_gate_assessment.json`
  - `vertical_report.md`

### 3. 报告与论文证据包

- 报告根目录：`reports/<report_pack>/`
- 图表目录：`reports/<report_pack>/charts/`
- 案例目录：`reports/<report_pack>/cases/`
- 索引文件：
  - `reports/<report_pack>/evidence-index.json`
  - `reports/<report_pack>/figure_table_index.csv`

## 命名规则冻结

### Run 配置

- 实验配置：`configs/experiments/<experiment_or_pack>_<topic>.json`
- 运行配置快照：`resolved_config_snapshot.json`
- 命名重点：
  - `<experiment_or_pack>` 必须稳定指向 issue 或实验包，例如 `evidence_freeze`、`w16_matrix`
  - `<topic>` 必须体现实验主题，而不是机器名或临时备注

### Run 级文件

- 批次目录：`output/experiment/<experiment_family>/<run_id>/`
- `run_id` 推荐格式：`<experiment_family>-<purpose>-<yyyymmdd>-<suffix>`
- 日志索引：`run_log_index.csv`
- 聚合总表：`vertical_metrics_summary.csv` 或 `<summary_topic>_summary.csv`

### 图表文件

- 图表数据源说明：`charts/<chart_id>.sources.json`
- 图表图像：`charts/<chart_id>.<png|svg|pdf>`
- 图表文案：`charts/<chart_id>.md`
- `chart_id` 推荐格式：`figure-<n>-<topic>` 或 `table-<n>-<topic>`

### 案例文件

- 案例文档：`cases/<case_id>.md`
- 案例附件清单：`cases/<case_id>.artifacts.json`
- `case_id` 推荐格式：`case-<n>-<theme>`

## 版本字段冻结

后续所有 `evidence-index.json` 至少记录以下版本字段：

- `schema_version`
- `naming_convention_version`
- `freeze_id`
- `run_id`
- `report_pack`
- `generated_at`

## `evidence-index.json` 字段基线

基线文件见：

- `reports/w13-issue-210/evidence-index.baseline.json`

字段分层要求：

- 顶层元信息：
  - `schema_version`
  - `naming_convention_version`
  - `issue_id`
  - `freeze_id`
  - `run_id`
  - `report_pack`
  - `generated_at`
- 目录根信息：
  - `roots.raw_logs`
  - `roots.snapshots`
  - `roots.experiment_output`
  - `roots.report_output`
- 追溯链模板：
  - `traceability_chains.chart`
  - `traceability_chains.case_study`
- 产物清单：
  - `artifacts[]`

每条 `artifacts[]` 至少包含：

- `artifact_id`
- `artifact_type`
- `title`
- `status`
- `path`
- `run_ref`
- `source_refs`
- `upstream_refs`
- `generated_by`
- `conclusion`
- `tags`

## 最小追溯链模板

### 图表

统一链路：

`run config -> resolved config snapshot -> run manifest / run_log_index -> aggregate summary -> chart sources -> chart file`

最少要能回链到：

- `configs/experiments/...json`
- `resolved_config_snapshot.json`
- `run_log_index.csv`
- 聚合表，例如 `vertical_metrics_summary.csv`
- 图表数据源说明文件，例如 `charts/figure-1-success-latency.sources.json`

### 案例

统一链路：

`run_log_index -> event log -> snapshot -> task-level report -> case markdown`

最少要能回链到：

- `run_log_index.csv`
- `data/logs/<task_id>.jsonl`
- `data/snapshots/<task_id>.jsonl`
- `output/reports/<task_id>.json`
- `cases/<case_id>.md`

## 与既有产物的兼容关系

- `run_log_index.csv`：继续作为 run 到原始日志/快照的主索引。
- `artifact_evidence_index.csv`：保留为历史阶段性索引；后续可由 `evidence-index.json` 衍生生成。
- `figure_table_index.csv`：继续作为图表清单；后续应被 `evidence-index.json.artifacts[]` 引用，而不是单独悬空存在。

## 后续 issue 复用要求

- W16 图表、表格、案例都必须复用上述目录结构。
- 任一图表或案例若无法回链到 `run config -> log/snapshot -> aggregate -> artifact`，视为证据不合格。
- 后续若需新增字段，只允许向 `evidence-index.json` 做向后兼容的增量扩展，不重命名已冻结字段。
