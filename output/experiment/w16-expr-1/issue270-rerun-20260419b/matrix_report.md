# Issue #221 Four-Group Experiment Matrix Report

- generated_at: `2026-04-19T16:57:29+00:00`
- freeze_id: `issue209-baseline-freeze-20260326`
- run_manifest: `output/experiment/w16-expr-1/issue270-rerun-20260419b/runs_manifest.json`

## Matrix Context

- config_path: `configs/experiments/w16_issue221_experiment_matrix.json`
- comparison_scope: `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`
- report_contract: `issue221_run_level_matrix`


## Unified Metrics (effect / mechanism / cost / governance)

| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_threshold_gate | 7 | 0.8571 | 0.7143 | 1.0000 | 0.8571 | 0.4286 | 0.0000 | 0.0000 | 188000.00 |
| dynamic_no_belief_state | 7 | 0.8571 | 0.5714 | 1.0000 | 0.8571 | 0.5714 | 0.4286 | 0.0000 | 208142.86 |
| lite_belief_state | 7 | 0.8571 | 0.1429 | 1.0000 | 0.8571 | 0.2857 | 0.4286 | 0.0000 | 130142.86 |

## Mechanism Increment Deltas

| from | to | metric | delta | ci_low | ci_high | pairing |
| --- | --- | --- | ---: | ---: | ---: | --- |
| fixed_threshold_gate | dynamic_no_belief_state | success | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | success | 0.0000 | -0.4286 | 0.4286 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | first_pass_success | -0.1429 | -0.5714 | 0.2857 | paired |
| dynamic_no_belief_state | lite_belief_state | first_pass_success | -0.4286 | -0.8571 | 0.1429 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | schema_valid | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | schema_valid | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | executable_plan | 0.0000 | -0.4286 | 0.4286 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | patch_event_count | 0.4286 | 0.0000 | 1.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | patch_event_count | 0.0000 | -0.8571 | 0.8571 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | duration_ms | 20142.8571 | -22571.4286 | 64428.5714 | paired |
| dynamic_no_belief_state | lite_belief_state | duration_ms | -78000.0000 | -138571.4286 | -17714.2857 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | high_cost_call_count | 0.1429 | -0.2857 | 0.5714 | paired |
| dynamic_no_belief_state | lite_belief_state | high_cost_call_count | -0.2857 | -0.7143 | 0.2857 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_continue_count | 0.8571 | -1.1429 | 2.4286 | paired |
| dynamic_no_belief_state | lite_belief_state | action_continue_count | -2.4286 | -4.1429 | -0.8571 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_patch_local_count | 0.5714 | 0.0000 | 1.4286 | paired |
| dynamic_no_belief_state | lite_belief_state | action_patch_local_count | 0.0000 | -1.2857 | 1.2857 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_suffix_replan_count | 0.0000 | -0.4286 | 0.4286 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |

## Offline Gate Check

| group | all_passed | failed_metrics |
| --- | --- | --- |
| fixed_threshold_gate | False | executable_plan_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| dynamic_no_belief_state | False | executable_plan_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| lite_belief_state | False | executable_plan_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |

## Acceptance Mapping

- A0->A6 chain reproducibility: covered via run manifest + run_log_index + deterministic config snapshot.
- Mechanism increment evidence: provided in `mechanism_increment_deltas.csv` with CI.
- Offline thresholds: checked in `offline_gate_assessment.json`; unmet items include reasons.
- Requirement2: tool/capability slices exported in `requirement2_tool_capability_slices.csv`.
