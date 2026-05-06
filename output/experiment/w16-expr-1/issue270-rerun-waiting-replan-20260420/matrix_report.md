# Issue #221 Four-Group Experiment Matrix Report

- generated_at: `2026-04-19T17:29:29+00:00`
- freeze_id: `issue209-baseline-freeze-20260326`
- run_manifest: `output/experiment/w16-expr-1/issue270-rerun-waiting-replan-20260420/runs_manifest.json`

## Matrix Context

- config_path: `configs/experiments/w16_issue221_experiment_matrix.json`
- comparison_scope: `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`
- report_contract: `issue221_run_level_matrix`


## Unified Metrics (effect / mechanism / cost / governance)

| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_threshold_gate | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 170000.00 |
| dynamic_no_belief_state | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 287000.00 |
| lite_belief_state | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 190000.00 |

## Mechanism Increment Deltas

| from | to | metric | delta | ci_low | ci_high | pairing |
| --- | --- | --- | ---: | ---: | ---: | --- |
| fixed_threshold_gate | dynamic_no_belief_state | success | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | success | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | first_pass_success | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | first_pass_success | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | schema_valid | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | schema_valid | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | executable_plan | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | patch_event_count | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | replan_event_count | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | duration_ms | 117000.0000 | 117000.0000 | 117000.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | duration_ms | -97000.0000 | -97000.0000 | -97000.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | high_cost_call_count | 1.0000 | 1.0000 | 1.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | action_continue_count | 3.0000 | 3.0000 | 3.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_continue_count | -2.0000 | -2.0000 | -2.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | unpaired |
| fixed_threshold_gate | dynamic_no_belief_state | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_stop_count | 0.0000 | 0.0000 | 0.0000 | unpaired |

## Offline Gate Check

| group | all_passed | failed_metrics |
| --- | --- | --- |
| fixed_threshold_gate | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| dynamic_no_belief_state | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| lite_belief_state | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |

## Acceptance Mapping

- A0->A6 chain reproducibility: covered via run manifest + run_log_index + deterministic config snapshot.
- Mechanism increment evidence: provided in `mechanism_increment_deltas.csv` with CI.
- Offline thresholds: checked in `offline_gate_assessment.json`; unmet items include reasons.
- Requirement2: tool/capability slices exported in `requirement2_tool_capability_slices.csv`.
