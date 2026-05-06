# Issue #230 Action / Belief-State Aggregation Metrics

## Design Baseline

- Core belief-state fields: `p_success`, `p_structural_failure`, `recovery_margin`, `expected_remaining_cost`, `evidence_sufficiency`.
- Derived audit fields: `budget_pressure`, `intervention_value`, `goal_misalignment`, `local_patchability`, `prefix_preservability`.
- Action space: `continue`, `patch_local`, `suffix_replan`, `stop`.
- Canonical internal paper groups: `static_top1`, `fixed_threshold_gate`, `dynamic_no_belief_state`, `lite_belief_state`.
- External comparison groups keep canonical ids `E0`, `E1`, `E2`.

## Naming Contract

`src/infra/w12_vertical_experiment.py` now emits:

- `group_id`: the current aggregation key, which may be a historical id or canonical paper id depending on `group_order`.
- `canonical_group_id`: normalized paper-facing id.
- `group_alias`: run-level back link from historical alias to canonical id.
- `group_aliases`: group-level list of historical aliases folded into a canonical group.

Historical mappings:

- `A0 -> static_top1`
- `A3 -> fixed_threshold_gate`
- `A4/A5 -> dynamic_no_belief_state`
- `A6 -> lite_belief_state`
- `react_single_trajectory/tot_multi_branch/reflexion_recovery -> E0/E1/E2`

## Run-Level Fields

Action fields:

- `action_continue_count`
- `action_patch_local_count`
- `action_suffix_replan_count`
- `action_stop_count`

Shadow/actual fields:

- `shadow_action_observation_count`
- `shadow_action_agreement_count`
- `shadow_action_agreement_rate`
- `shadow_actual_bias_count`
- `shadow_actual_bias_rate`

Belief-state observability fields:

- `belief_state_observation_count`
- `belief_state_core_observed_count`
- `belief_state_core_completeness`
- `belief_state_core_complete`
- `belief_state_derived_observed_count`
- `belief_state_derived_completeness`
- `belief_state_sources`

For each core and derived field, the run row also includes:

- `belief_state_<field>`
- `belief_state_<field>_observed`

## Group-Level Fields

Summary rows include:

- `belief_state_observable_rate`
- `belief_state_core_complete_rate`
- `belief_state_core_completeness_mean`
- `belief_state_derived_completeness_mean`
- `belief_state_<core_field>_observable_rate`
- `belief_state_<derived_field>_observable_rate`
- `action_<action>_mean`
- `action_<action>_rate`
- `shadow_action_agreement_rate`
- `shadow_actual_bias_rate`

`action_distribution_breakdown.csv` includes action totals/rates plus shadow/actual agreement and bias.

`belief_state_observability_breakdown.csv` includes group-level core-field and derived-field observable rates.

## Source Mapping

The unified aggregation script reads all baselines through the same inputs:

- Event log: `data.runtime_state_summary`, `data.waiting_runtime_summary.runtime_state_summary`, `data.recovery.runtime_state_summary`, logged action names, shadow action, and shadow score.
- Snapshot: `artifacts.runtime_state` and `artifacts.decision_summary`.
- Summary row: optional `runtime_state` or `runtime_state_summary` fields already present in a manifest row.

No separate aggregation script is needed for internal A0-A6 groups, canonical paper groups, or external E0/E1/E2 comparisons.
