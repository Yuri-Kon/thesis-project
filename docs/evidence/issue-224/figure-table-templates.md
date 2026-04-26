# Issue #224 Figure and Table Templates

These templates are traceability-first. A rendered table or figure is paper-ready only when every value links back to `source_refs` in `evidence-index.json`.

## Table Main Internal Overall

Source priority:

1. `output/experiment/w16-expr-1/<analysis_run_id>/overall_metrics.csv`
2. fallback: `output/experiment/w16-expr-1/issue221-real-full-20260418b/matrix_metrics_summary.csv`

Required row order:

| group_id | display_name | runs | success_rate | first_pass_success_rate | duration_ms_mean | high_cost_call_mean | patch_events_mean | replan_events_mean | suffix_replan_events_mean | trace_ref |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `static_top1` | Static Top-1 |  |  |  |  |  |  |  |  | `table-main-internal-overall:<row_id>` |
| `fixed_threshold_gate` | Fixed Threshold Gate |  |  |  |  |  |  |  |  | `table-main-internal-overall:<row_id>` |
| `dynamic_no_belief_state` | Dynamic Recovery (No Belief-State) |  |  |  |  |  |  |  |  | `table-main-internal-overall:<row_id>` |
| `lite_belief_state` | Lite Belief-State |  |  |  |  |  |  |  |  | `table-main-internal-overall:<row_id>` |

Traceability notes:

- `group_id` must be canonical; historical `A0-A6` names are allowed only in appendix notes.
- `trace_ref` resolves to `evidence-index.json -> artifacts[artifact_id=table-main-internal-overall]`.
- Metric definitions should cite `metric_definitions.csv`; if using the fallback summary, cite `src/infra/w12_vertical_experiment.py` and `src/infra/w16_issue221_experiment_matrix.py`.

## Table Difficulty Stratified

Source: `output/experiment/w16-expr-1/<analysis_run_id>/difficulty_stratified_metrics.csv`.

| difficulty | group_id | display_name | runs | success_rate | duration_ms_mean | high_cost_call_mean | recovery_event_mean | trace_ref |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `easy` | `static_top1` | Static Top-1 |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `easy` | `fixed_threshold_gate` | Fixed Threshold Gate |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `easy` | `dynamic_no_belief_state` | Dynamic Recovery (No Belief-State) |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `easy` | `lite_belief_state` | Lite Belief-State |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `medium` | `static_top1` | Static Top-1 |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `medium` | `fixed_threshold_gate` | Fixed Threshold Gate |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `medium` | `dynamic_no_belief_state` | Dynamic Recovery (No Belief-State) |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `medium` | `lite_belief_state` | Lite Belief-State |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `hard` | `static_top1` | Static Top-1 |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `hard` | `fixed_threshold_gate` | Fixed Threshold Gate |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `hard` | `dynamic_no_belief_state` | Dynamic Recovery (No Belief-State) |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |
| `hard` | `lite_belief_state` | Lite Belief-State |  |  |  |  |  | `table-difficulty-stratified:<row_id>` |

Traceability notes:

- `difficulty` comes from `runs_manifest.json` task metadata.
- Missing difficulty rows must remain absent, not imputed.

## Table Recovery High Cost

Source: `output/experiment/w16-expr-1/<analysis_run_id>/recovery_complexity_high_cost.csv`.

| slice | group_id | patch_events_mean | replan_events_mean | suffix_replan_events_mean | patch_minimality_hit_rate | suffix_replan_prefix_preservation_rate | high_cost_call_mean | high_cost_failure_mean | trace_ref |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `overall:all` | `static_top1` |  |  |  |  |  |  |  | `table-recovery-high-cost:<row_id>` |
| `overall:all` | `fixed_threshold_gate` |  |  |  |  |  |  |  | `table-recovery-high-cost:<row_id>` |
| `overall:all` | `dynamic_no_belief_state` |  |  |  |  |  |  |  | `table-recovery-high-cost:<row_id>` |
| `overall:all` | `lite_belief_state` |  |  |  |  |  |  |  | `table-recovery-high-cost:<row_id>` |

Traceability notes:

- Recovery columns must be linked to event-level rows through `run_log_index.csv`.
- `suffix_replan_prefix_preservation_rate` may be null when no suffix replan sample exists; report it as `N/A`, not zero.

## Figure Success Cost Recovery

Source: `output/experiment/w16-expr-1/<analysis_run_id>/chart_summary_rows.csv`.

Recommended layout:

- Panel A: `success_rate` by canonical internal group.
- Panel B: `duration_ms_mean` and `high_cost_call_mean` by canonical internal group.
- Panel C: `patch_events_mean`, `replan_events_mean`, and `suffix_replan_events_mean` by canonical internal group.

Data contract:

| field | source column | required |
| --- | --- | --- |
| panel | derived from `metric_dimension` | yes |
| group_id | `group_id` | yes |
| metric | `metric` | yes |
| value | `value` | yes |
| trace_ref | `figure-success-cost-recovery:<metric>:<group_id>` | yes |

## Figure Difficulty Stratified

Source: `output/experiment/w16-expr-1/<analysis_run_id>/difficulty_stratified_metrics.csv`.

Recommended layout:

- Facet by `slice_value` (`easy`, `medium`, `hard`).
- Within each facet, compare the four canonical internal groups.
- Use consistent metric ordering: `success_rate`, `duration_ms_mean`, `recovery_event_mean`.

Data contract:

| field | source column | required |
| --- | --- | --- |
| facet | `slice_value` | yes |
| group_id | `group_id` | yes |
| metric | selected metric column | yes |
| value | selected metric value | yes |
| source_row | stable row id or CSV line number | yes |

