# Issue #172 Horizontal Experiment Report (E0/E1/E2)

- generated_at: `2026-04-22T04:07:37+00:00`
- freeze_id: `issue199-platform-freeze-20260412`
- run_manifest: `output/experiment/w12-expr-3/issue172-horizontal/issue172-live-qwen-flash-tunnel-r1/runs_manifest.json`

## Horizontal Context

- config_path: `configs/experiments/w16_issue172_horizontal_experiment.json`
- dataset_version: `issue170-remote-batch3-20260316`
- comparison_scope: `lite_belief_state / E0 / E1 / E2`
- report_contract: `issue172_horizontal_external_baselines`

## Lite Belief-State vs E0-E2

| group | scope | success_rate | first_pass | duration_ms_mean | high_cost_call_mean | waiting_chain_complete_rate | failure_traceable_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E0 | external | 1.0000 | 1.0000 | 251000.00 | 0.0000 | 1.0000 | 1.0000 |
| E1 | external | 0.8571 | 0.8571 | 224428.57 | 0.0000 | 1.0000 | 1.0000 |
| E2 | external | 1.0000 | 1.0000 | 260428.57 | 0.0000 | 1.0000 | 1.0000 |

## Unified Metrics (effect / mechanism / cost / governance)

| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E0 | 7 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 251000.00 |
| E1 | 7 | 0.8571 | 0.8571 | 0.8571 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 224428.57 |
| E2 | 7 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 260428.57 |

## Mechanism Increment Deltas

| from | to | metric | delta | ci_low | ci_high | pairing |
| --- | --- | --- | ---: | ---: | ---: | --- |
| E0 | E1 | success | -0.1429 | -0.4286 | 0.0000 | paired |
| E1 | E2 | success | 0.1429 | 0.0000 | 0.4286 | paired |
| E0 | E1 | first_pass_success | -0.1429 | -0.4286 | 0.0000 | paired |
| E1 | E2 | first_pass_success | 0.1429 | 0.0000 | 0.4286 | paired |
| E0 | E1 | schema_valid | -0.1429 | -0.4286 | 0.0000 | paired |
| E1 | E2 | schema_valid | 0.1429 | 0.0000 | 0.4286 | paired |
| E0 | E1 | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | executable_plan | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | duration_ms | -26571.4286 | -96714.2857 | 14000.0000 | paired |
| E1 | E2 | duration_ms | 36000.0000 | -4857.1429 | 105714.2857 | paired |
| E0 | E1 | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | action_continue_count | -0.4286 | -1.2857 | 0.0000 | paired |
| E1 | E2 | action_continue_count | 0.4286 | 0.0000 | 1.2857 | paired |
| E0 | E1 | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | action_suffix_replan_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |

## Offline Gate Check

| group | all_passed | failed_metrics |
| --- | --- | --- |
| E0 | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| E1 | False | schema_valid_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| E2 | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |


## Acceptance Mapping

- Internal reference group: `missing_internal_reference`
- E0 validates single-trajectory external baseline behavior under the same whitelist and budget lineage.
- E1 validates multi-branch candidate selection under the same dataset and cost envelope.
- E2 validates text-based recovery rounds with explicit governance logging instead of hidden retries.
- Unified metrics, rerun candidates, and traceability indexes are exported for downstream evidence-pack assembly.
