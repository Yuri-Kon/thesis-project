# Planner Score/Gate (W10-03)

This note documents the minimal scoring and gate policy for issue #140.

## Score Breakdown

Planner candidate scoring keeps required v1 keys and adds tool dimensions:

- Required keys:
  - `feasibility`
  - `objective`
  - `risk`
  - `cost`
  - `overall`
- Added keys:
  - `confidence`
  - `tool_readiness`
  - `tool_coverage`
  - `fallback_depth`

`objective` includes a small boost when payload contains objective scoring tools
(for example `objective_ranker` / `objective_scoring` capability).

## Risk/Cost Mapping

Risk and cost are derived from:

- adapter mode (`local/remote/hybrid/mock/unknown`)
- capability type (for example `structure_prediction`, `quality_qc`)
- base tool attributes (`safety_level`, `cost`)

This mapping is used for both:

- candidate `risk_level` / `cost_estimate` labels
- score components (`risk`, `cost`)

## HITL Gate

Gate is evaluated on the top-ranked candidate.

Hard conditions to enter `WAITING_*`:

- explicit confirm flags:
  - `require_plan_confirm`
  - `require_patch_confirm`
  - `require_replan_confirm`
- `risk_level == high`
- `confidence < min_candidate_confidence` (default `0.0`, configurable)
- `cost_estimate == high` and `overall < high_cost_min_overall` (only when threshold is configured)

Default policy:

- `plan`: auto by default (`require_plan_confirm=false`)
- `patch`: auto by default (`require_patch_confirm=false`)
- `replan`: auto by default (`require_replan_confirm=false`)
