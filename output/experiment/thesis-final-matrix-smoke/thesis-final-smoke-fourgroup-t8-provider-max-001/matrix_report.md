# Thesis Four-Group Experiment Matrix Report

- generated_at: `2026-05-09T18:19:07+00:00`
- freeze_id: `issue209-baseline-freeze-20260326`
- run_manifest: `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/runs_manifest.json`

## Matrix Context

- config_path: `configs/experiments/thesis_final_experiment_matrix.json`
- comparison_scope: `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`
- report_contract: `thesis_run_level_matrix`


## Unified Metrics (effect / mechanism / cost / governance)

| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| static_top1 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 183000.00 |
| fixed_threshold_gate | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 290000.00 |
| dynamic_no_belief_state | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 207000.00 |
| lite_belief_state | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 253000.00 |

## Mechanism Increment Deltas

| from | to | metric | delta | ci_low | ci_high | pairing |
| --- | --- | --- | ---: | ---: | ---: | --- |
| static_top1 | fixed_threshold_gate | success | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | success | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | success | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | first_pass_success | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | first_pass_success | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | first_pass_success | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | schema_valid | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | schema_valid | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | schema_valid | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | duration_ms | 107000.0000 | 107000.0000 | 107000.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | duration_ms | -83000.0000 | -83000.0000 | -83000.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | duration_ms | 46000.0000 | 46000.0000 | 46000.0000 | paired |
| static_top1 | fixed_threshold_gate | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | action_continue_count | -2.0000 | -2.0000 | -2.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_continue_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_continue_count | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| static_top1 | fixed_threshold_gate | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |
| fixed_threshold_gate | dynamic_no_belief_state | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |
| dynamic_no_belief_state | lite_belief_state | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |

## Offline Gate Check

| group | all_passed | failed_metrics |
| --- | --- | --- |
| static_top1 | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| fixed_threshold_gate | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| dynamic_no_belief_state | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| lite_belief_state | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |

## Acceptance Mapping

- A0->A6 chain reproducibility: covered via run manifest + run_log_index + deterministic config snapshot.
- Mechanism increment evidence: provided in `mechanism_increment_deltas.csv` with CI.
- Offline thresholds: checked in `offline_gate_assessment.json`; unmet items include reasons.
- Requirement2: tool/capability slices exported in `requirement2_tool_capability_slices.csv`.
- Action-level metrics: `action_distribution_breakdown.csv` exports `continue / patch_local / suffix_replan / stop` totals, rates, and shadow/actual bias.
- Belief-state metrics: `belief_state_observability_breakdown.csv` exports the five frozen core-state observable rates and derived-field completeness.
- Naming: `canonical_group_id` preserves the paper group name while `group_aliases` links back to historical `A0-A6` or external aliases.
