# Issue #172 Closure Assessment

- generated_at: `2026-04-25`
- merged_run_dir: `output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged`
- supersedes: `issue172-live-qwen-flash-tunnel-r1`
- replacement_sample: `issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt4`

## What Is Now Complete

- E0 / E1 / E2 all ran under the same freeze, dataset, task set, tool whitelist, and budget lineage.
- The previously failed logical run `E1_enzyme_like_fold_r02` was rerun successfully as `attempt4`.
- `attempt4` completed on the pure `openfold` path without fallback patching.
- The merged evidence pack now reports:
  - `run_count = 21`
  - `success_count = 21`
  - `rerun_candidate_count = 0`
  - `E0/E1/E2 success_rate = 1.0`

## Evidence Paths

- Manifest: [runs_manifest.json](/home/yurikon/Documents/thesis/thesis-project.dev/output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/runs_manifest.json)
- Summary: [horizontal_metrics_summary.csv](/home/yurikon/Documents/thesis/thesis-project.dev/output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/horizontal_metrics_summary.csv)
- Validation: [validation_summary.json](/home/yurikon/Documents/thesis/thesis-project.dev/output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/validation_summary.json)
- Report: [horizontal_report.md](/home/yurikon/Documents/thesis/thesis-project.dev/output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/horizontal_report.md)
- Traceability: [run_traceability_index.csv](/home/yurikon/Documents/thesis/thesis-project.dev/output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/run_traceability_index.csv)
- Evidence index: [evidence_index.json](/home/yurikon/Documents/thesis/thesis-project.dev/output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1-attempt4-merged/evidence_index.json)
- Replacement sample log: [attempt4 jsonl](/home/yurikon/Documents/thesis/thesis-project.dev/data/logs/issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt4.jsonl)

## Fairness And Governance Notes

- Freeze lineage is preserved from `issue199-platform-freeze-20260412`.
- Tool whitelist and budget versions remain `issue199-tool-whitelist-v1` and `issue199-budget-v1`.
- Governance-facing metrics are exported in the merged pack:
  - `waiting_chain_complete_rate`
  - `failure_traceable_rate`
  - action distribution
  - patch/replan breakdown

## Residual Gaps

- `offline_gate_assessment.json` still reports `all_passed = false` for all groups because:
  - `patch_minimality_hit_rate = null`
  - `suffix_replan_prefix_preservation_rate = null`
  - these metrics are missing rather than failing on observed bad samples.
- Internal comparison is still unresolved in the generated report:
  - `reference_group_id = missing_internal_reference`
- Downstream issues remain open and are not replaced by this merged pack:
  - `#222` metrics aggregation and stratification
  - `#223` case studies and failure analysis
  - `#224` evidence index/templates
  - `#174` report evidence package
  - `#249` canonical naming/output mapping

## Closure Judgment

If issue `#172` is interpreted narrowly as the execution and traceable packaging of the external E0/E1/E2 horizontal baseline under the frozen fairness contract, this merged pack is sufficient to support closure.

If issue `#172` is interpreted strictly through the current downstream release/reporting chain, it is not fully closed yet because the merged pack still points to a missing internal reference group and the offline gate remains formally unpassed due to missing recovery metrics.
