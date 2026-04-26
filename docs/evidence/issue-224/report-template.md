# Issue #224 Report Template

Use this template for the W16 result package, issue closeout notes, or thesis result-section drafting. Do not remove trace fields when converting to prose.

## Result Section Template

### Evidence Scope

- Evidence index: `docs/evidence/issue-224/evidence-index.json`
- W16-01 run output: `output/experiment/w16-expr-1/issue221-real-full-20260418b`
- W16-02 analysis output: `output/experiment/w16-expr-1/<analysis_run_id>`
- W16-03 case output: `reports/w16-issue223/<case_pack_id>`
- Group naming source: `../thesis-project.design/docs/experiment/algorithm-group-paper-mapping.md`

### Main Claim

Claim:

`<one sentence using Static Top-1 / Fixed Threshold Gate / Dynamic Recovery (No Belief-State) / Lite Belief-State>`

Required evidence:

| claim fragment | table_or_figure_ref | source_ref | caveat |
| --- | --- | --- | --- |
| success comparison | `table-main-internal-overall` | `overall_metrics.csv` or fallback summary |  |
| cost comparison | `figure-success-cost-recovery` | `chart_summary_rows.csv` |  |
| recovery behavior | `table-recovery-high-cost` | `recovery_complexity_high_cost.csv` |  |
| difficulty stability | `table-difficulty-stratified` | `difficulty_stratified_metrics.csv` |  |

### Paragraph Skeleton

In the canonical internal comparison, `<group display name>` is evaluated against `<group display names>` under the same task set and freeze. The primary table uses `<source table>` and keeps row-level links to `runs_manifest.json`, `run_log_index.csv`, event logs, and snapshots. The result supports `<claim>` because `<metric 1>` changes from `<value>` to `<value>`, while `<metric 2>` remains `<value or caveat>`.

For recovery behavior, cite `table-recovery-high-cost` rather than only the success table. The discussion should distinguish patch, replan, suffix replan, and high-cost failures. If any recovery metric is null because no event occurred, state that it is not observed instead of treating it as zero.

For difficulty stratification, cite `table-difficulty-stratified` and state whether the claim holds across `easy`, `medium`, and `hard` slices. Do not generalize beyond slices present in the source table.

## Case Study Template

### Case Header

- case_id: `<case-loss-control-success | case-static-vs-dynamic-contrast | case-failure-analysis>`
- case_type: `<loss_control_success | static_vs_dynamic_contrast | failure_analysis>`
- task_key: `<task key>`
- group_id: `<canonical group id>`
- run_id: `<run id>`
- source refs:
  - run_config: `<path>`
  - event_log: `<path>`
  - snapshot: `<path>`
  - run_traceability_index: `<path>`

### Selection Reason

Explain why this case was selected. Tie the reason to a row in `run_traceability_index.csv`, an aggregate metric row, or a known failure field.

### Action Path

| order | event_or_step | observed action | runtime state or shadow signal | source ref |
| ---: | --- | --- | --- | --- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

### Evidence Chain

| evidence item | path | key fields | completeness |
| --- | --- | --- | --- |
| run config |  | `group_id`, `task_key`, `runtime_policy`, `constraints_hash` |  |
| event log |  | `event`, `from_status`, `to_status`, `data.recovery`, `data.runtime_state_summary` |  |
| snapshot |  | `status`, `artifacts.runtime_state`, `artifacts.decision_summary` |  |
| report or aggregate row |  | `summary_row_id`, metric columns |  |

### Result Contrast

For contrast cases, compare canonical groups only. Use historical `A0-A6` aliases only in an appendix trace note.

| dimension | reference group | comparison group | observed difference | source ref |
| --- | --- | --- | --- | --- |
| success |  |  |  |  |
| cost |  |  |  |  |
| recovery |  |  |  |  |
| evidence completeness |  |  |  |  |

### Failure Analysis Addendum

Use this block for `case-failure-analysis`.

- failure signal:
- wrong or missing decision:
- evidence gap:
- why the gap matters for the paper claim:
- follow-up issue or mitigation:

## Closeout Checklist

- [ ] Every table value has a source row or source file path.
- [ ] Every figure panel names the input CSV/JSON file and metric column.
- [ ] Every case has run config, event log, snapshot, and traceability index references where available.
- [ ] Canonical group naming matches `algorithm-group-paper-mapping.md`.
- [ ] Null and absent recovery metrics are reported as unobserved, not as zero.
- [ ] The report states whether it used W16-02 analysis outputs or W16-01 fallback summaries.
