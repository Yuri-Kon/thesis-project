# Issue #221 Vertical Experiment Report (A0-A6)

- generated_at: `2026-04-16T16:29:56+00:00`
- freeze_id: `issue209-baseline-freeze-20260326`
- run_manifest: `configs/experiments/w16_issue221_experiment_matrix.json`

## Unified Metrics (effect / mechanism / cost / governance)

| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| static_top1 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 7000.00 |

## Mechanism Increment Deltas

| from | to | metric | delta | ci_low | ci_high | pairing |
| --- | --- | --- | ---: | ---: | ---: | --- |

## Offline Gate Check

| group | all_passed | failed_metrics |
| --- | --- | --- |
| static_top1 | False | patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate |

## Acceptance Mapping

- A0->A6 chain reproducibility: covered via run manifest + run_log_index + deterministic config snapshot.
- Mechanism increment evidence: provided in `mechanism_increment_deltas.csv` with CI.
- Offline thresholds: checked in `offline_gate_assessment.json`; unmet items include reasons.
- Requirement2: tool/capability slices exported in `requirement2_tool_capability_slices.csv`.
