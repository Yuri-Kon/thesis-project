# Issue 232: Planner Shadow Rerank And Adjusted Score Interface

## Scope

This note captures the implementation-facing contract for issue `#232` and aligns the current code path with the 2026-03-29 frozen design:

- `SID:planner.algorithm.candidate_scoring`
- `SID:planner.algorithm.runtime_reranking`
- `SID:planner.algorithm.runtime_adjustment_formula`
- `SID:algo.schema.cost`
- `SID:algo.schema.risk`
- `SID:algo.schema.recovery`
- `SID:tools.metadata.active_table`
- `SID:tools.metadata.derived_metrics`

## Candidate Interface

The Planner keeps `TopKResult` and `PendingActionCandidate` unchanged at the top level and lands the shadow rerank interface in candidate metadata:

- `static_score`: static prior score summary, mapped from `score_breakdown.overall`
- `runtime_adjustment`: bounded runtime correction, always marked `shadow_only=true`
- `final_score`: audited `clip(static_score + runtime_adjustment, 0, 1)` result
- `rerank_reason`: structured audit payload for cost / risk / recovery / evidence-facing reasons
- `action_score`: compatibility alias for the static score summary
- `shadow_score`: compatibility alias for the shadow `final_score`

The required implementation points are:

- [`src/agents/planner.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/agents/planner.py)
- [`src/models/validation.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/models/validation.py)
- [`src/models/contracts.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/models/contracts.py)

## Default Recommendation Boundary

Default recommendation remains static-first in this issue.

- `default_recommendation` is still chosen by deterministic static ranking.
- `default_recommendation_reason.selection_basis` is fixed to `static_score`.
- `default_recommendation_reason.shadow_candidate_id` records the shadow-best candidate when runtime_state is present.
- `default_recommendation_reason.shadow_only=true` makes it explicit that shadow rerank has not yet been promoted into control flow.

This makes `#217` able to promote `final_score` later without changing the candidate contract again.

## Runtime State Boundary

The shadow rerank path consumes only the current four stable runtime summary fields already present in code:

- `runtime_state.p_success`
- `runtime_state.p_structural_failure`
- `runtime_state.recovery_margin`
- `runtime_state.expected_remaining_cost`

No new persistent runtime state is introduced here. Future belief-state work in `#219` can extend the adjustment logic additively, but it should continue to flow through `runtime_adjustment` and `rerank_reason` instead of creating a parallel score channel.

## Tool Metadata Boundary

Planner does not read the active-tool profile table directly in this issue.

- Planner consumes candidate-level score signals such as `score_breakdown.cost`, `score_breakdown.risk`, `score_breakdown.confidence`, `score_breakdown.fallback_depth`, and `score_breakdown.feasibility`.
- `#248` should own the canonical mapping from active tool priors and derived `step_cost` / `step_risk` into those candidate-level signals.
- `rerank_reason.tool_metadata_fields` is intentionally empty today, which documents that raw tool priors have not yet been wired in at the Planner boundary.

This keeps the consumption seam explicit and avoids duplicating tool-prior formulas inside Planner.

## Acceptance Mapping

- shadow rerank / adjusted score interface: implemented via candidate metadata and validation
- default recommendation correction and explanation boundary: implemented via enriched `default_recommendation_reason`
- runtime_state seam: implemented and limited to current summary fields
- active tool metadata seam: documented as a Planner read boundary for future `#248` integration
