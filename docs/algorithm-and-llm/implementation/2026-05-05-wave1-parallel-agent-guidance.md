# Wave1 Parallel Agent Guidance — CEBRA-WP P0

- Generated: 2026-05-05 16:01:55 +0800
- Purpose: machine-oriented execution guidance for three parallel coding agents.
- Audience: future Hermes/delegate_task/Codex agents, not a human-facing design explanation.
- Scope: Wave1 only — GitHub issues #334, #335, #337.
- Status: guidance file only. Do not treat this file as proof that implementation has started.

## 0. Hard execution contract

Before any agent edits code, it must read and obey, in this order:

1. `AGENT_CONTRACT.md`
2. `AGENTS.md`
3. The issue file assigned to that agent
4. This guidance file
5. Related investigation docs under `docs/algorithm-and-llm/`
6. Current code in that agent's worktree

Repository invariants from `AGENT_CONTRACT.md`:

- Schemas are compatibility contracts. Do not remove fields, rename fields, or reinterpret existing semantics.
- Extensions must be additive and backward-compatible. Prefer optional fields, `metadata`, and `metrics`.
- Do not decide key system behavior without explicit user confirmation.
- If changing FSM behavior, agent roles, recovery semantics, public contracts, or execution semantics, retrieve design fragments from `../thesis-project.design` / doc-slicer first.
- When behavior changes, add/update focused tests and run them with `uv`.

Operational constraints:

- Python 3.12.
- Use `uv` for tests/checks.
- Do not introduce broad `Any`, bare generics, broad casts, or broad ignores.
- Keep changes minimal and nearest-owning-module scoped.
- Do not touch secrets or credentials.
- Do not modify unrelated UI, API behavior, FSM states, or remote-service scripts.
- Do not commit from Codex sandbox in worktree; Hermes will inspect diff and commit manually if needed.

## 1. Wave1 worktrees and issue mapping

All three worktrees were created from `dev` HEAD `961509e feat: 添加未来issue参考依据`.

| Lane | GitHub issue | Branch | Worktree | Main objective |
|---|---:|---|---|---|
| A | #334 | `feat/p0-feasibility-metadata` | `/home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-feasibility-metadata` | Explicit `metadata.candidate_feasibility` for candidates |
| B | #335 | `feat/p0-posterior-objective` | `/home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-posterior-objective` | Connect `posterior_objective.v1` to planner objective ranking |
| C | #337 | `feat/p0-source-refs` | `/home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-source-refs` | Normalize `source_refs=[sid:..., impl:...]` traceability |

Do not edit the main `/home/yurikon/Documents/thesis/thesis-project.dev` tree during lane implementation except to update orchestration docs if explicitly requested.

## 2. Source documents to read

Each agent must read these global documents:

- `AGENT_CONTRACT.md`
- `AGENTS.md`
- `docs/algorithm-and-llm/core-algorithm-theory-v2.md`
- `docs/algorithm-and-llm/core-algorithm-design-code-traceability.md`
- `docs/algorithm-and-llm/core-algorithm-code-gap-review.md`
- `docs/algorithm-and-llm/implementation/2026-05-05_021358-cebra-wp-p0-implementation-decisions.md`

Issue-specific source of truth:

- #334: `docs/algorithm-and-llm/issues/2026-05-05-p0-02-feasibility-metadata.md`
- #335: `docs/algorithm-and-llm/issues/2026-05-05-p0-03-posterior-objective-ranking.md`
- #337: `docs/algorithm-and-llm/issues/2026-05-05-p0-05-source-refs-design-sids.md`

Important correction: older investigation/implementation docs sometimes use `metadata.feasibility`. For Wave1 implementation, the authoritative field name is:

```text
metadata.candidate_feasibility
```

This correction comes from the finalized #334 issue and #337 source-ref mapping. Do not introduce `metadata.feasibility` for candidate-level feasibility.

## 3. Shared theory-to-code anchors

CEBRA-WP theory objects relevant to Wave1:

```text
Pi_raw,t = GenerateCandidates(g, C, K, h_t)
F_h(pi, C, K, h_t) ∈ {0,1}
F_s(pi, C, K, h_t) ∈ [0,1]
G_post(pi; g, o_t) = Σ_m λ_m(g) · ρ_m(o_t) · q_m(pi, o_t)
S_static(pi, o_t) = weighted sum over feasibility/objective/risk/cost/confidence/etc.
x_t = (p_success, p_structural_failure, recovery_margin, expected_remaining_cost, evidence_sufficiency)
```

Current implementation anchors:

- Candidate Top-K: `src/agents/candidate_generator/generator.py::CandidateGenerator.generate`
- Filter reason: `src/agents/candidate_generator/generator.py::_filter_reason`
- Soft fallback selection: `src/agents/candidate_generator/generator.py::_available_rows`
- Candidate metadata build: `src/agents/candidate_generator/builder.py::_build_metadata`
- Candidate schema: `src/models/contracts.py::PendingActionCandidate`
- Static scoring: `src/agents/planner.py::_score_payload`
- Posterior score: `src/adapters/objective_ranker_adapter.py::_build_posterior_score`
- Runtime schema source refs: `src/models/runtime_schemas.py::ActionUtility`
- Runtime score summaries: `src/models/contracts.py::ScoreSummary`, `RuntimeAdjustmentSummary`

Current code facts verified before writing this file:

- `CandidateGenerator.generate()` currently computes `reason = self._filter_reason(...)`, sends `{io_not_closed, tool_unavailable}` to `soft_filtered_rows`, then uses `default_candidate = candidates[0] if candidates else None`.
- `_available_rows()` backfills normal candidates with `soft_filtered_rows` until `top_k`; if no normal rows exist, it returns all soft rows.
- `PendingActionCandidate.score_breakdown` is validated as `Dict[str, float]`; string metadata must not be placed there.
- `PendingActionCandidate.metadata` is `JsonMap = Field(default_factory=dict)` and is the right additive extension point.
- `ObjectiveRankerAdapter` currently emits `posterior_score.schema_version == "posterior_score.v1"`; `_build_posterior_score()` includes `generic_objective`, `stability`, `function`, `novelty`, and `structure_quality` fields; binding semantics must be handled carefully.
- `RuntimeEvaluator.compute_action_utilities()` currently uses `source_refs=["runtime_evaluator.action_utility.v1"]` and default utility uses `source_refs=["runtime_evaluator.default.v1"]`.
- `ScoreSummary` and `RuntimeAdjustmentSummary` currently have `source` fields but no `source_refs` field.

## 4. Parallelization policy

Wave1 is parallelizable only under these boundaries:

- #334 is mostly independent.
- #335 and #337 both may touch `src/agents/planner.py` and `src/adapters/objective_ranker_adapter.py`; their work is parallelizable in separate worktrees but not conflict-free.
- #337 should provide source-ref constants and additive fields. It must not deeply implement posterior-objective ranking logic.
- #335 may reference #337's target constants conceptually, but in its own worktree it should not assume #337 has already been merged. If it adds local source refs, use the exact same names specified here to ease conflict resolution.

Recommended final merge order after all agents finish:

1. Merge #337 source-ref constants/additive schema fields first.
2. Merge #334 feasibility metadata second.
3. Merge #335 posterior objective ranking third, resolving overlaps in `planner.py` / `objective_ranker_adapter.py` against #337 constants.

If an agent finds that its implementation requires changing FSM states, HITL semantics, action-selection ownership, or public schema names, it must stop and return a blocker instead of editing.

## 5. Lane A — #334 feasibility metadata

### 5.1 Worktree

```text
/home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-feasibility-metadata
```

### 5.2 Issue file

```text
docs/algorithm-and-llm/issues/2026-05-05-p0-02-feasibility-metadata.md
```

### 5.3 Goal

Add explicit candidate feasibility metadata for each returned `PendingActionCandidate`:

```text
metadata.candidate_feasibility
```

It must map current filter reasons to CEBRA-WP feasibility concepts:

- `F_h`: hard executable feasibility predicate.
- `F_s`: soft feasibility / ranking signal.
- `degraded_feasible`: displayable fallback candidate but not auto-executable.
- `requires_hitl`: human confirmation required.

### 5.4 Required schema shape

Use this exact candidate metadata key:

```python
"candidate_feasibility": {
    "schema_version": "candidate_feasibility.v1",
    "hard_feasible": bool,
    "soft_feasible": bool,
    "degraded_feasible": bool,
    "requires_hitl": bool,
    "auto_executable": bool,
    "filter_class": "eligible" | "soft" | "hard",
    "filter_reason": str | None,
    "constraint_codes": list[str],
    "allowed_for_top_k": bool,
    "allowed_for_default_recommendation": bool,
    "source_refs": [
        "sid:algo.adaptive.feasibility_filter",
        "impl:candidate_generator.feasibility.v1",
    ],
    "design_ref_status": {
        "sid:algo.adaptive.feasibility_filter": "proposed"
    },
}
```

`auto_executable` must be derived consistently:

```text
auto_executable = hard_feasible and not requires_hitl
```

Do not store contradictory combinations.

### 5.5 Filter reason mapping

| reason | filter_class | hard_feasible | soft_feasible | degraded_feasible | requires_hitl | allowed_for_top_k | allowed_for_default_recommendation | constraint_codes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `None` | `eligible` | true | true | false | false | true | true | `[]` |
| `io_not_closed` | `soft` | false | true | true | true | true | false | `["schema.io_open"]` |
| `tool_unavailable` | `soft` | false | true | true | true | true | false | `["tool.unavailable"]` |
| `missing_tools:<ids>` | `hard` | false | false | false | false | false | false | `["tool.missing"]` |
| `tool_not_allowed` | `hard` | false | false | false | false | false | false | `["tool.not_allowed"]` |
| `tool_blocked` | `hard` | false | false | false | false | false | false | `["tool.blocked"]` |
| `safety_level_exceeded` | `hard` | false | false | false | false | false | false | `["safety.exceeded"]` |
| `cost_level_exceeded` | `hard` | false | false | false | false | false | false | `["cost.exceeded"]` |
| unknown non-null reason | `hard` | false | false | false | false | false | false | `["unknown"]` |

Unknown reason defaults to hard-infeasible for safety.

### 5.6 Implementation constraints

Modify nearest owning module first:

- Primary: `src/agents/candidate_generator/generator.py`
- Secondary only if needed: `src/agents/candidate_generator/builder.py`
- Schema/test support if needed: `src/models/runtime_schemas.py` or tests only; avoid broad public-contract changes.

Important: `builder.py::_build_metadata()` does not know the final filter reason. Do not make builder the main owner of final candidate feasibility. The final metadata must be attached in `CandidateGenerator.generate()` after `_filter_reason()` returns.

Use safe metadata copy. Do not mutate shared metadata in a way that leaks between tests/candidates. Preferred pattern:

```python
metadata = dict(candidate.metadata or {})
metadata["candidate_feasibility"] = feasibility
candidate = candidate.model_copy(update={"metadata": metadata})
```

Do not rewrite `_filter_reason()` to return a large custom object unless necessary. A small helper that maps `reason: str | None` to metadata is enough.

### 5.7 Default recommendation rule

Current code uses first selected candidate. Replace it with:

```text
default_candidate = first candidate whose metadata.candidate_feasibility.allowed_for_default_recommendation is true
```

If no such candidate exists:

- `TopKResult.default_recommendation` must be `None`.
- Explanation must indicate no hard-feasible default exists and candidates require HITL/degraded handling.
- Do not treat the first degraded candidate as auto default.

Downstream `workflow/pending_action.py` may still select first candidate for WAITING event display if no default exists. That is acceptable only as display context; it must not imply automatic execution.

### 5.8 Tests

Focused tests should be in/near:

```text
tests/unit/test_candidate_generator.py
```

Required assertions:

1. Eligible candidate has `metadata.candidate_feasibility.hard_feasible == True`, `auto_executable == True`, and can be default.
2. `io_not_closed` or `tool_unavailable` candidate can appear in returned candidates as degraded fallback when normal candidates are insufficient.
3. Degraded fallback has `requires_hitl == True`, `auto_executable == False`, `allowed_for_default_recommendation == False`.
4. If only degraded candidates exist, `default_recommendation is None`.
5. Hard-infeasible reason does not enter returned `candidates`.
6. No candidate uses `metadata.feasibility` for this feature.

Run at minimum:

```bash
uv run pytest tests/unit/test_candidate_generator.py
uv run basedpyright src/agents/candidate_generator/generator.py src/agents/candidate_generator/builder.py src/models/runtime_schemas.py
```

If `builder.py` or `runtime_schemas.py` is untouched, omit it from focused basedpyright command.

### 5.9 Stop conditions

Stop and return blocker if:

- Implementing this requires changing HITL approval semantics outside candidate default recommendation.
- Implementing this requires changing FSM states or WAITING transitions.
- Existing tests assume degraded candidates may be auto-selected; report the conflict instead of silently changing broader behavior.

## 6. Lane B — #335 posterior objective ranking

### 6.1 Worktree

```text
/home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-posterior-objective
```

### 6.2 Issue file

```text
docs/algorithm-and-llm/issues/2026-05-05-p0-03-posterior-objective-ranking.md
```

### 6.3 Goal

Make posterior objective scoring a stable, auditable input to planner ranking by connecting normalized `posterior_objective.v1` to `score_breakdown["objective"]`.

Do not directly overwrite `overall`. Recompute `overall` through existing weighted sum after choosing the objective input.

### 6.4 Required schema shape

Normalize adapter output to this metadata object when available:

```python
"posterior_objective": {
    "schema_version": "posterior_objective.v1",
    "aggregate_score": float,
    "objective_type": str | None,
    "components": {
        "generic_objective": {...},
        "stability": {...},
        "function": {...},
        "novelty": {...},
        "structure_quality": {...},
        # optional/explicit policy for binding, see 6.7
    },
    "component_weights": dict[str, float],
    "evidence_sufficiency": float,
    "evidence_status": "direct" | "partial" | "degraded",
    "warnings": list[str],
    "evidence_refs": list[dict[str, object]],
    "source_refs": [
        "sid:algo.posterior_objective_scoring",
        "impl:posterior_score.v1",
        "impl:posterior_objective.v1",
    ],
    "design_ref_status": {
        "sid:algo.posterior_objective_scoring": "proposed"
    },
}
```

### 6.5 Numeric `score_breakdown` rule

`PendingActionCandidate.score_breakdown` validates all values as numeric floats. Therefore:

Allowed:

```python
score_breakdown["objective"] = 0.73
score_breakdown["evidence_sufficiency"] = 0.65
```

Forbidden:

```python
score_breakdown["objective_source"] = "posterior_objective"
score_breakdown["evidence_status"] = "direct"
```

Non-numeric provenance must go into candidate/payload metadata, e.g.:

```python
metadata["objective_score_source"] = "posterior_objective"
metadata["objective_evidence_status"] = "direct"
metadata["posterior_objective"] = normalized_posterior
```

### 6.6 Objective source policy

When `_score_payload()` can read posterior information from `payload.metadata`:

1. If posterior objective exists and `evidence_sufficiency >= 0.30`:
   - `objective = posterior_objective.aggregate_score`
   - metadata source = `posterior_objective`
2. If posterior exists but `evidence_sufficiency < 0.30`:
   - `objective = 0.70 * prior_objective + 0.30 * posterior_aggregate`
   - metadata source = `degraded_proxy`
3. If no posterior exists:
   - keep current prior heuristic objective
   - metadata source = `prior_goal_fit`

Do not keep the existing objective bonus in addition to posterior replacement if it would double-count objective_ranker. When posterior is used directly, set effective objective bonus to zero or avoid applying it.

### 6.7 Binding component policy

The issue and investigation docs disagree historically about whether `_POSTERIOR_COMPONENTS` contains a first-class `binding` component. Current verified code has `_POSTERIOR_COMPONENTS = (generic_objective, stability, function, novelty, structure_quality)` in this worktree; binding appears as a proxy under generic objective in some paths.

Therefore for Wave1:

- Do not invent a full new binding component unless current code already has it in `_POSTERIOR_COMPONENTS` after local verification.
- If binding is represented by `generic_objective` proxy evidence, add explicit metadata such as:

```python
"binding_proxy_component": "generic_objective"
```

- If the agent chooses to add a first-class `binding` component, it must update weights, score construction, outputs, and tests consistently. This is riskier and should be avoided unless the issue text demands it and current tests support it.

### 6.8 Data-flow verification gate

Before editing scoring logic, verify how posterior information reaches `_score_payload(payload: Plan | PlanPatch, ...)`.

Minimum read/search targets:

- `src/adapters/objective_ranker_adapter.py`
- `src/adapters/tool_schema_utils.py`
- `src/agents/planner.py`, especially `_score_payload()` and candidate/payload construction paths
- `src/agents/candidate_generator/builder.py`
- tests mentioning `posterior_score`, `objective_ranker`, `score_breakdown.objective`

If posterior output cannot currently enter `Plan.metadata` or `PlanPatch.metadata`, do not fake it. Return a blocker with one of these options:

- Option A: add a small propagation step from objective ranker output to payload metadata.
- Option B: restrict #335 to adapter normalization/tests only and defer planner ranking connection.
- Option C: introduce a structured scoring return object only after user confirmation.

### 6.9 Implementation constraints

Likely modified files:

- `src/adapters/objective_ranker_adapter.py`
- `src/agents/planner.py`
- Possibly `tests/unit/test_extended_tool_adapters.py`
- Possibly planner/candidate generator tests after locating current coverage

Do not modify source-ref constants if #337 owns them, unless local implementation needs temporary identical strings. If #337's `src/models/source_refs.py` is not present in this worktree, either use literal refs exactly matching this guidance or add a minimal local helper only if it will merge cleanly.

### 6.10 Tests

Required assertions:

1. Objective ranker emits both legacy `posterior_score.v1` and normalized `posterior_objective.v1` or a documented compatibility mapping.
2. Posterior object includes evidence sufficiency/status and source refs.
3. Planner objective uses posterior aggregate when evidence sufficiency is adequate.
4. Low evidence posterior is blended and marked as degraded in metadata, not directly used as full objective.
5. `score_breakdown` remains `dict[str, float]`; no string values.
6. Overall remains weighted-sum based and is not directly overwritten by posterior aggregate.

Candidate test commands after locating exact tests:

```bash
uv run pytest tests/unit/test_extended_tool_adapters.py
uv run pytest tests/unit/test_candidate_generator.py
uv run basedpyright src/adapters/objective_ranker_adapter.py src/agents/planner.py
```

If a narrower planner test exists for `_score_payload`, run that too.

### 6.11 Stop conditions

Stop and return blocker if:

- Posterior cannot be propagated to planner payload without public contract changes.
- The implementation requires changing Plan/PlanPatch public field names.
- The implementation requires sweeping completed step outputs in `_score_payload()`; issue explicitly prefers not doing this in P0 due to coupling.
- Existing tests show objective semantics are relied on as cost-only heuristic in critical paths; report before changing broadly.

## 7. Lane C — #337 source refs / SID traceability

### 7.1 Worktree

```text
/home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-source-refs
```

### 7.2 Issue file

```text
docs/algorithm-and-llm/issues/2026-05-05-p0-05-source-refs-design-sids.md
```

### 7.3 Goal

Create a stable implementation source-ref layer so core metadata can point to both:

```text
sid:<design-sid>
impl:<implementation-ref>
```

This is traceability work. It must not change scoring behavior, action selection, or runtime policy.

### 7.4 Required new module

Create:

```text
src/models/source_refs.py
```

Recommended contents:

```python
from __future__ import annotations

DESIGN_REF_STATUS_PROPOSED = "proposed"
DESIGN_REF_STATUS_EXISTING = "existing"

SID_ADAPTIVE_OPTIMIZATION_OBJECTIVE = "sid:algo.adaptive.optimization_objective"
SID_CANDIDATE_SCORING = "sid:planner.algorithm.candidate_scoring"
SID_CANDIDATE_SCHEMA = "sid:planner.contracts.candidate_schema"
SID_FEASIBILITY_FILTER = "sid:algo.adaptive.feasibility_filter"
SID_POSTERIOR_OBJECTIVE_SCORING = "sid:algo.posterior_objective_scoring"
SID_ACTION_UTILITY_SCHEMA = "sid:algo.schema.action_utility"
SID_RUNTIME_ADJUSTMENT_FORMULA = "sid:planner.algorithm.runtime_adjustment_formula"
SID_RUNTIME_ACTION_SELECTION = "sid:planner.algorithm.runtime_action_selection"

IMPL_CANDIDATE_GENERATOR_FEASIBILITY_V1 = "impl:candidate_generator.feasibility.v1"
IMPL_PLANNER_SCORE_BREAKDOWN_V1 = "impl:planner.score_breakdown.v1"
IMPL_POSTERIOR_SCORE_V1 = "impl:posterior_score.v1"
IMPL_POSTERIOR_OBJECTIVE_V1 = "impl:posterior_objective.v1"
IMPL_RUNTIME_EVALUATOR_ACTION_UTILITY_V1 = "impl:runtime_evaluator.action_utility.v1"
IMPL_RUNTIME_EVALUATOR_DEFAULT_V1 = "impl:runtime_evaluator.default.v1"
IMPL_PLANNER_RUNTIME_ADJUSTMENT_V1 = "impl:planner.runtime_adjustment.v1"

PROPOSED_DESIGN_REFS = {
    SID_FEASIBILITY_FILTER,
    SID_POSTERIOR_OBJECTIVE_SCORING,
}

def source_refs(*refs: str) -> list[str]:
    return list(refs)

def design_ref_status(*refs: str) -> dict[str, str]:
    return {
        ref: DESIGN_REF_STATUS_PROPOSED
        for ref in refs
        if ref in PROPOSED_DESIGN_REFS
    }
```

Exact names may be adjusted to code style, but refs must match strings in this guidance.

### 7.5 Format rules

Valid source refs:

```text
sid:algo.schema.action_utility
impl:runtime_evaluator.action_utility.v1
```

Invalid:

```text
SID:algo.schema.action_utility
algo.schema.action_utility
sid:../path/to/doc.md
impl:src/workflow/recovery.py:123
sid:algo.adaptive.feasibility_filter:proposed
```

Proposed status must not be encoded into the SID string. Use same-level metadata, helper, or docs:

```python
"design_ref_status": {
    "sid:algo.adaptive.feasibility_filter": "proposed"
}
```

### 7.6 Scope limits

Allowed modifications:

- Add `source_refs` optional fields to `ScoreSummary` and `RuntimeAdjustmentSummary` using `Field(default_factory=list)`.
- Update current `ActionUtility.source_refs` assignments in `runtime_evaluator.py` to include both `sid:` and `impl:` refs.
- Update planner/runtime score summary constructors to pass `source_refs` where obvious and local.
- Add source refs to posterior score output if touching `objective_ranker_adapter.py`, but do not change posterior ranking logic.

Disallowed modifications:

- Do not modify design repository `../thesis-project.design` in this lane.
- Do not change scoring formulas.
- Do not change action selection behavior.
- Do not force every historical metadata object in the repository to have source refs.
- Do not create a nested provenance graph or large Pydantic provenance object.

### 7.7 Minimal target objects

Wave1 #337 should cover only these objects:

1. `ActionUtility.source_refs`
2. `RuntimeEvaluator` default action utility source refs
3. `ScoreSummary.source_refs` additive field
4. `RuntimeAdjustmentSummary.source_refs` additive field
5. Planner/runtime constructors that already build those summaries
6. Objective/posterior score source refs only if simple and non-behavioral

### 7.8 Tests

Create or update focused tests near existing runtime/contracts tests.

Required assertions:

1. `source_refs()` returns a list preserving exact strings.
2. All constants intended as SIDs start with `sid:`; all implementation refs start with `impl:`.
3. `ScoreSummary(value=..., source=...)` still constructs without explicitly passing `source_refs`.
4. `RuntimeAdjustmentSummary(value=..., source=...)` still constructs without explicitly passing `source_refs`.
5. `ActionUtility` objects emitted by `RuntimeEvaluator.compute_action_utilities()` include at least one `sid:` and one `impl:` in `source_refs`.
6. Proposed SID status is represented outside the SID string.

Candidate commands:

```bash
uv run pytest tests/unit/test_runtime_evaluator.py
uv run pytest tests/unit/test_runtime_schemas.py tests/unit/test_contracts.py
uv run basedpyright src/models/source_refs.py src/models/contracts.py src/workflow/runtime_evaluator.py src/agents/planner.py src/adapters/objective_ranker_adapter.py
```

If some test files do not exist, locate nearest existing tests first rather than creating broad new suites blindly.

### 7.9 Stop conditions

Stop and return blocker if:

- Adding source refs requires changing model `extra="forbid"` semantics in a breaking way.
- A target summary model is serialized/deserialized by tests that require exact dumps and would need broad snapshot updates.
- Adding source refs to posterior output would collide heavily with #335; in that case leave a TODO/comment-free minimal constants module and tests, and report merge note.

## 8. Cross-lane conflict rules

### 8.1 Field names

Canonical names:

```text
metadata.candidate_feasibility
metadata.posterior_objective
metadata.objective_score_source
metadata.objective_evidence_status
metadata.design_ref_status
source_refs
```

Do not introduce alternatives:

```text
metadata.feasibility                 # wrong for candidate feasibility in Wave1
metadata.posterior_score_normalized  # avoid unless compatibility only
score_breakdown.objective_source     # wrong because score_breakdown is numeric
```

### 8.2 Source refs strings

Canonical refs for Wave1:

```text
sid:algo.adaptive.feasibility_filter
sid:algo.posterior_objective_scoring
sid:algo.adaptive.optimization_objective
sid:planner.algorithm.candidate_scoring
sid:algo.schema.action_utility
sid:planner.algorithm.runtime_adjustment_formula
impl:candidate_generator.feasibility.v1
impl:planner.score_breakdown.v1
impl:posterior_score.v1
impl:posterior_objective.v1
impl:runtime_evaluator.action_utility.v1
impl:runtime_evaluator.default.v1
impl:planner.runtime_adjustment.v1
```

### 8.3 Scoring

- `score_breakdown` remains numeric-only.
- Do not directly overwrite `overall` with posterior aggregate.
- Recompute `overall` through existing normalized weights.
- Do not introduce new default score weights unless issue explicitly requires it.

### 8.4 HITL/default semantics

- Degraded feasibility implies `requires_hitl=true` and `auto_executable=false`.
- Degraded candidates can be shown but cannot become automatic default recommendation.
- Do not change WAITING state transitions or human-confirmation requirements.

### 8.5 Public contracts

- Add optional fields or metadata only.
- Do not rename existing fields.
- Do not remove legacy `posterior_score.v1` output.
- Do not remove existing `source` string fields from summary models.

## 9. Required final output from each agent

Each parallel agent must return a concise implementation report containing:

1. Issue number and worktree path.
2. Files changed.
3. Exact schema/metadata fields added.
4. Behavior changes, if any.
5. Tests added/updated.
6. Commands run and results.
7. Any blockers or merge conflicts expected.
8. `git diff --stat` summary.
9. Whether it touched files also likely touched by another lane.

Each agent must not claim success unless it has run relevant tests or clearly states why tests could not run.

## 10. Orchestrator post-processing checklist

After all three agents finish:

1. Inspect each worktree diff manually.
2. Verify no lane modified unrelated files.
3. Verify #334 uses `metadata.candidate_feasibility`, not `metadata.feasibility`.
4. Verify #335 has no string values in `score_breakdown`.
5. Verify #337 source refs do not encode proposed status inside the SID string.
6. Run focused tests in each worktree.
7. Merge in recommended order: #337 → #334 → #335.
8. Resolve `planner.py` and `objective_ranker_adapter.py` conflicts manually.
9. After merging all lanes, run combined focused tests:

```bash
uv run pytest tests/unit/test_candidate_generator.py
uv run pytest tests/unit/test_extended_tool_adapters.py
uv run pytest tests/unit/test_runtime_evaluator.py
uv run basedpyright src/agents/candidate_generator/generator.py src/agents/planner.py src/adapters/objective_ranker_adapter.py src/models/contracts.py src/models/runtime_schemas.py src/workflow/runtime_evaluator.py
```

10. If UI/API output relies on tracked frontend assets, build assets only if frontend source is changed. Wave1 should not touch frontend.

## 11. Agent prompt skeletons

### 11.1 Lane A prompt

```text
You are implementing GitHub issue #334 in worktree /home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-feasibility-metadata.
Read AGENT_CONTRACT.md, AGENTS.md, this guidance file, and docs/algorithm-and-llm/issues/2026-05-05-p0-02-feasibility-metadata.md.
Implement only metadata.candidate_feasibility and default_recommendation safety for degraded candidates.
Do not introduce metadata.feasibility.
Do not change FSM/HITL semantics beyond default recommendation guard.
Add focused tests in tests/unit/test_candidate_generator.py.
Run uv tests and focused basedpyright.
Return files changed, tests run, diff stat, and blockers.
```

### 11.2 Lane B prompt

```text
You are implementing GitHub issue #335 in worktree /home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-posterior-objective.
Read AGENT_CONTRACT.md, AGENTS.md, this guidance file, and docs/algorithm-and-llm/issues/2026-05-05-p0-03-posterior-objective-ranking.md.
First verify posterior_score/posterior_objective data flow into Plan/PlanPatch metadata before editing scoring logic.
Connect posterior_objective.v1 to score_breakdown.objective only if data flow is real.
Never put strings into score_breakdown; put objective source/status in metadata.
Do not overwrite overall directly; preserve weighted-sum recomputation.
Keep posterior_score.v1 compatibility.
Add focused tests and run uv tests + basedpyright.
Return files changed, tests run, diff stat, and blockers.
```

### 11.3 Lane C prompt

```text
You are implementing GitHub issue #337 in worktree /home/yurikon/Documents/thesis/thesis-project-tmp-worktree/feat-source-refs.
Read AGENT_CONTRACT.md, AGENTS.md, this guidance file, and docs/algorithm-and-llm/issues/2026-05-05-p0-05-source-refs-design-sids.md.
Create src/models/source_refs.py and add additive source_refs support to the minimal target objects only.
Do not change scoring formulas, action selection, FSM/HITL behavior, or design repository files.
Use sid:/impl: strings exactly; proposed status must be separate from SID string.
Add focused tests for constants, compatibility construction, and RuntimeEvaluator ActionUtility source_refs.
Run uv tests + basedpyright.
Return files changed, tests run, diff stat, and blockers.
```
