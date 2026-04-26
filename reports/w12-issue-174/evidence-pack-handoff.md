# Issue #174 W16 Evidence Pack Handoff

- issue: `#174`
- status: addon evidence index
- generated_at: `2026-04-26`
- scope: report evidence pack only

## Scope

中期报告正文已经另行完成。本文件只整理 #174 还需要交接给论文、`#152` 和 `#225` 的证据入口，不重写章节正文。

#174 当前应按 W16 末报告证据打包项理解，而不是旧版 W12 中期报告草稿。旧文件 `reports/w12-issue-174/midterm_experiment_chapter.md` 保留作历史中期草稿，不能再单独作为 #174 完成依据。

## Primary Evidence Roots

| scope | issue | path | role |
| --- | ---: | --- | --- |
| W16 internal matrix | #221 | `output/experiment/w16-expr-1/issue221-real-full-20260418b/matrix_metrics_summary.csv` | 内部四组主结果 summary fallback |
| W16 internal traceability | #221 | `output/experiment/w16-expr-1/issue221-real-full-20260418b/run_traceability_index.csv` | run config / event log / snapshot / report 回链 |
| W16 internal evidence index | #221 | `output/experiment/w16-expr-1/issue221-real-full-20260418b/evidence_index.json` | 内部矩阵证据索引 |
| W16 rerun/case pack | #223 | `output/experiment/w16-expr-1/issue270-rerun-waiting-replan-20260420/evidence_index.json` | 案例、失败分析、WAITING/replan 补充证据 |
| W12/W16 horizontal comparison | #172 | `output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/horizontal_metrics_summary.csv` | E0/E1/E2 外部对照结果表 |
| Horizontal traceability | #172 | `output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/run_traceability_index.csv` | 横向 run 级追溯 |
| Horizontal evidence index | #172 | `output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/evidence_index.json` | 横向证据索引 |
| Figure/table index | #174 | `reports/w12-issue-174/figure_table_index.csv` | 可引用图表、表格、模板入口 |
| W16 evidence templates | #224 | `docs/evidence/issue-224/evidence-index.json` | artifact/source_refs/traceability 模板 |

## Naming Rules

论文主表使用 canonical internal groups:

- `static_top1`
- `fixed_threshold_gate`
- `dynamic_no_belief_state`
- `lite_belief_state`

外部对照只作为单独表或单独段落引用:

- `E0`
- `E1`
- `E2`

历史 `A0-A6` 只保留在 W12 附录追溯、实施路线和 issue 对账中，不应混入 W16 主结果表。

## Result Package Status

| requirement | current status | evidence |
| --- | --- | --- |
| 汇总内部矩阵结果 | available | `issue221-real-full-20260418b/matrix_metrics_summary.csv` |
| 汇总横向对比结果 | available | `issue172-live-qwen-flash-tunnel-r1-attempt4-merged/horizontal_metrics_summary.csv` |
| 案例/失败分析入口 | available as evidence pack reference | `issue270-rerun-waiting-replan-20260420/evidence_index.json` |
| 图表清单 | refreshed | `reports/w12-issue-174/figure_table_index.csv` |
| 证据引用说明 | this handoff | `reports/w12-issue-174/evidence-pack-handoff.md` |
| 中期报告正文 | completed outside this addon | user-authored report, not regenerated here |

## Recommended Citation Flow

1. 章节正文引用 `reports/w12-issue-174/figure_table_index.csv` 中的 `artifact_id`。
2. 图表和表格回链到对应 `source_path`。
3. 每个统计值优先回链到 `run_traceability_index.csv` 中的 `summary_row_id` 或 run-level row。
4. 每个案例回链到 `run_config_path`、`event_log_path` 和 `snapshot_path`。
5. 如果使用 #224 模板渲染新图表，保留模板中的 `trace_ref`，不要只复制数值。

## Limits And Follow-ups

- W16-02 的独立 `overall_metrics.csv` / `difficulty_stratified_metrics.csv` 目录在当前 tracked 报告材料中没有固定版本路径；#174 可以使用 W16-01 `matrix_metrics_summary.csv` 作为 summary fallback，但正式论文图表应在生成固定 analysis run 后改指向该目录。
- #223 已关闭，但当前 repo 中主要表现为 rerun/case 证据入口；如需完整案例正文，应另补 `reports/w16-issue223/` 或在论文草稿中直接消费 #224 case template。
- 旧 `midterm_experiment_chapter.md` 中的 `#172 deferred` 是历史状态，不应再复制到新报告。
- Null 或缺失 recovery 指标必须写作未观测，不得当作 0。

## Handoff To #152 / #225

`#152` 可更新 release evidence index 与 release draft，移除“#172 deferred”的旧阻塞说法，改为引用横向结果路径和剩余限制项。

`#225` 可基于本文件继续拆分后续 issue:

- 固定 W16-02 analysis run 的版本路径。
- 补齐 case study 正文包。
- 将 #224 模板渲染为最终论文图表与表格。
