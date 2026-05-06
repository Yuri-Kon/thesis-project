# Issue #172 Horizontal Experiment Report (E0/E1/E2)

- generated_at: `2026-04-20T06:35:11+00:00`
- freeze_id: `issue199-platform-freeze-20260412`
- run_manifest: `output/experiment/w12-expr-3/issue172-horizontal/issue172-live-minimax-tunnel-r1/runs_manifest.json`

## Horizontal Context

- config_path: `configs/experiments/w16_issue172_horizontal_experiment.json`
- dataset_version: `issue170-remote-batch3-20260316`
- comparison_scope: `lite_belief_state / E0 / E1 / E2`
- report_contract: `issue172_horizontal_external_baselines`

## Lite Belief-State vs E0-E2

| group | scope | success_rate | first_pass | duration_ms_mean | high_cost_call_mean | waiting_chain_complete_rate | failure_traceable_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A6 | internal_reference | 0.0000 | 0.0000 | 0.00 | 0.0000 | 0.0000 | 1.0000 |
| E0 | external | 0.1429 | 0.1429 | 120285.71 | 0.0000 | 1.0000 | 1.0000 |
| E1 | external | 0.0000 | 0.0000 | 128000.00 | 0.0000 | 1.0000 | 1.0000 |
| E2 | external | 0.0000 | 0.0000 | 190142.86 | 0.0000 | 1.0000 | 1.0000 |

## Unified Metrics (effect / mechanism / cost / governance)

| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E0 | 7 | 0.1429 | 0.1429 | 0.7143 | 0.4286 | 0.0000 | 0.0000 | 0.0000 | 120285.71 |
| E1 | 7 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 128000.00 |
| E2 | 7 | 0.0000 | 0.0000 | 0.8571 | 0.4286 | 0.0000 | 1.0000 | 0.0000 | 190142.86 |

## Mechanism Increment Deltas

| from | to | metric | delta | ci_low | ci_high | pairing |
| --- | --- | --- | ---: | ---: | ---: | --- |
| E0 | E1 | success | -0.1429 | -0.4286 | 0.0000 | paired |
| E1 | E2 | success | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | first_pass_success | -0.1429 | -0.4286 | 0.0000 | paired |
| E1 | E2 | first_pass_success | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | schema_valid | 0.2857 | 0.0000 | 0.5714 | paired |
| E1 | E2 | schema_valid | -0.1429 | -0.4286 | 0.0000 | paired |
| E0 | E1 | executable_plan | -0.4286 | -0.8571 | -0.1429 | paired |
| E1 | E2 | executable_plan | 0.4286 | 0.1429 | 0.8571 | paired |
| E0 | E1 | patch_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | patch_event_count | 1.0000 | 0.2857 | 1.7143 | paired |
| E0 | E1 | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | replan_event_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | duration_ms | 7714.2857 | -56000.0000 | 70285.7143 | paired |
| E1 | E2 | duration_ms | 62142.8571 | 857.1429 | 118857.1429 | paired |
| E0 | E1 | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | high_cost_call_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E0 | E1 | action_continue_count | 0.4286 | -0.2857 | 1.1429 | paired |
| E1 | E2 | action_continue_count | -1.0000 | -1.7143 | -0.2857 | paired |
| E0 | E1 | action_patch_local_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | action_patch_local_count | 1.1429 | 0.2857 | 1.7143 | paired |
| E0 | E1 | action_suffix_replan_count | 0.4286 | 0.1429 | 0.8571 | paired |
| E1 | E2 | action_suffix_replan_count | -0.4286 | -0.7143 | -0.1429 | paired |
| E0 | E1 | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |
| E1 | E2 | action_stop_count | 0.0000 | 0.0000 | 0.0000 | paired |

## Offline Gate Check

| group | all_passed | failed_metrics |
| --- | --- | --- |
| E0 | False | schema_valid_rate, executable_plan_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| E1 | False | executable_plan_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |
| E2 | False | schema_valid_rate, executable_plan_rate, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |


## Acceptance Mapping

- Internal reference group: `A6`
- E0 validates single-trajectory external baseline behavior under the same whitelist and budget lineage.
- E1 validates multi-branch candidate selection under the same dataset and cost envelope.
- E2 validates text-based recovery rounds with explicit governance logging instead of hidden retries.
- Unified metrics, rerun candidates, and traceability indexes are exported for downstream evidence-pack assembly.
