# Issue #209 Baseline Freeze

- freeze_id: `issue209-baseline-freeze-smoke`
- generated_at: `2026-03-26T11:12:42+00:00`
- task_set_version: `issue209-taskset-v1`
- difficulty_scheme_version: `issue209-difficulty-v1`

## High-Cost Rules

| rule_id | label | stage_ids | capability_ids | tool_ids | cost_tier |
| --- | --- | --- | --- | --- | --- |
| structure_mapping | 结构映射 | S2 | structure_prediction | esmfold, nim_esmfold, openfold3 | high |
| structure_refinement | 结构条件下的序列精修 | S4 | sequence_design | protein_mpnn | high |
| heavy_objective_evaluation | 重型目标评估 | S5 | objective_scoring | - | medium_high |

## Task Catalog

| task_key | difficulty | budget_tier |
| --- | --- | --- |
| enzyme_like_fold | medium | standard |
| binding_scaffold | hard | high_cost_sensitive |
| high_solubility | easy | low_cost_first |
| secondary_balance | medium | standard |

## Baselines

| id | label | status | runtime_policy | current_repo |
| --- | --- | --- | --- | --- |
| static_top1 | 静态 Top-1 | implemented | static_single_candidate | True |
| fixed_threshold_gate | 固定阈值 gate | implemented | static_threshold_gate | True |
| dynamic_no_belief_state | 动态无 belief-state | planned | dynamic_observation_only | False |
| lite_belief_state | Lite belief-state | planned | lite_belief_state | False |

## Metrics Contract

- effect: `success_rate, first_pass_success_rate, executable_plan_rate`
- cost: `duration_ms_mean, high_cost_call_mean, high_cost_failure_mean`
- recovery: `patch_events_mean, replan_events_mean, suffix_replan_events_mean, patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate`
- governance: `waiting_chain_complete_rate, failure_traceable_rate`

## Notes

- `dynamic_no_belief_state` and `lite_belief_state` are frozen as comparison contracts even when current repo support is partial.
- High-cost call counting is aligned to the freeze rules and can be consumed by the vertical experiment evaluator.
