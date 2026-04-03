# Issue 217: Runtime Rerank And Default Recommendation Promotion

## Scope

This note captures the implementation-facing contract for issue `#217` on top of the shadow rerank interface that already exists in the current branch.

The relevant frozen design baseline is:

- `SID:planner.algorithm.runtime_reranking`
- `SID:planner.algorithm.runtime_adjustment_formula`
- `SID:planner.algorithm.candidate_scoring`

## What Changed

Planner now promotes runtime `final_score` from an audit-only field into the effective ranking signal whenever `runtime_state` is present.

- without `runtime_state`:
  - ranking still uses `static_score`
  - `default_recommendation_reason.selection_basis = static_score`
- with `runtime_state`:
  - ranking uses `final_score`
  - `default_recommendation` points to the reranked top candidate
  - `default_recommendation_reason.selection_basis = final_score`
  - `default_recommendation_reason.static_candidate_id` records the displaced static default when rerank changes the winner

This keeps `TopKResult` and `PendingActionCandidate` top-level structure unchanged.

## Ranking Boundary

The effective Top-K flow is now:

1. compute `static_score`
2. compute `runtime_adjustment`
3. derive `final_score = clip(static_score + runtime_adjustment, 0, 1)`
4. use `final_score` as the sort key when `runtime_state` exists
5. keep stable tie-breaking and capability-bucket round-robin selection

For patch candidates, existing recovery-layer precedence remains ahead of score ordering; runtime rerank only replaces the score component inside that existing ordering rule.

## Default Recommendation Audit

Default recommendation audit is carried by:

- `default_recommendation_reason.selection_basis`
- `default_recommendation_reason.rerank_applied`
- `default_recommendation_reason.static_candidate_id`
- `default_recommendation_reason.static_score_gap`
- candidate `rerank_reason`
- candidate `static_score` / `runtime_adjustment` / `final_score`

This makes the default change explainable without changing the PendingAction / Decision API contract.

## Explanation Boundary

`TopKResult.explanation` now distinguishes the active ranking basis:

- static path says ranking uses `overall`
- runtime path says ranking uses `final_score`
- runtime path also states whether the default recommendation changed and summarizes the dominant rerank reasons, including cost pressure, risk pressure, recovery margin, or evidence confidence

Candidate-level explanation continues to carry the detailed numeric signals.

## Waiting Summary Boundary

The selected candidate’s rerank evidence is now persisted into `WaitingRuntimeSummary`:

- `static_score`
- `runtime_adjustment`
- `final_score`
- `rerank_reason`
- `action_score`
- `shadow_score`

This keeps waiting-state replay and audit aligned with the promoted default recommendation.

## Acceptance Mapping

- runtime_state integrated into Top-K ordering: implemented
- corrected default recommendation output: implemented
- explanation includes rerank reasons: implemented
- ranking stability and explanation tests: implemented
