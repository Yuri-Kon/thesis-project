# Issue #222 Integration Analysis

- generated_at: `2026-04-26T13:30:34+00:00`
- source_issue: `#221`
- source_run_manifest: `output/experiment/w16-expr-1/issue221-real-full-20260418b/runs_manifest.json`
- comparison_scope: `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`

## Overall Metrics

| group | runs | success | first_pass | high_cost_mean | patch_mean | replan_mean | recovery_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| static_top1 | 7 | 1.0000 | 0.5714 | 0.2857 | 0.4286 | 0.0000 | 0.4286 |
| fixed_threshold_gate | 7 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| dynamic_no_belief_state | 7 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| lite_belief_state | 7 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Difficulty Stratification

| difficulty | group | runs | success | high_cost_mean | recovery_mean |
| --- | --- | ---: | ---: | ---: | ---: |
| easy | static_top1 | 2 | 1.0000 | 0.0000 | 0.5000 |
| easy | fixed_threshold_gate | 2 | 0.0000 | 0.0000 | 0.0000 |
| easy | dynamic_no_belief_state | 2 | 0.0000 | 0.0000 | 0.0000 |
| easy | lite_belief_state | 2 | 0.0000 | 0.0000 | 0.0000 |
| medium | static_top1 | 4 | 1.0000 | 0.5000 | 0.2500 |
| medium | fixed_threshold_gate | 4 | 0.0000 | 0.0000 | 0.0000 |
| medium | dynamic_no_belief_state | 4 | 0.0000 | 0.0000 | 0.0000 |
| medium | lite_belief_state | 4 | 0.0000 | 0.0000 | 0.0000 |
| hard | static_top1 | 1 | 1.0000 | 0.0000 | 1.0000 |
| hard | fixed_threshold_gate | 1 | 0.0000 | 0.0000 | 0.0000 |
| hard | dynamic_no_belief_state | 1 | 0.0000 | 0.0000 | 0.0000 |
| hard | lite_belief_state | 1 | 0.0000 | 0.0000 | 0.0000 |

## Output Contract

- `overall_metrics.csv`: overall success/cost/recovery summary rows.
- `difficulty_stratified_metrics.csv`: difficulty x group stratified summary rows.
- `recovery_complexity_high_cost.csv`: patch/replan/prefix/high-cost focused rows.
- `chart_summary_rows.csv`: long-form chart/table rows.
- `metric_definitions.json`: metric definitions and source mappings.
- `statistical_deltas.csv`: paired or unpaired bootstrap deltas for core metrics.

- recovery_rows: `16`
- delta_rows: `84`
