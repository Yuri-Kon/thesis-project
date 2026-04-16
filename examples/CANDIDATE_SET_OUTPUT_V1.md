# CandidateSetOutput v1 Field Dictionary

This document defines the `CandidateSetOutput v1` field semantics used by Planner output and HITL consumption.

## Candidate fields

- `candidate_id`: stable candidate identifier.
- `structured_payload`: structured object to execute (`Plan` or `PlanPatch` in current runtime).
- `score_breakdown`: score map with required keys:
  - `feasibility`
  - `objective`
  - `risk`
  - `cost`
  - `overall`
- `risk_level`: `low | medium | high`.
- `cost_estimate`: `low | medium | high`.
- `explanation`: explanation for this candidate.
- `summary`: optional short summary for display.
- `metadata`: optional extension map.

### Tool metadata fields (Requirement-2)

Candidate tool fields are represented as top-level fields and synchronized into `metadata`:

- `tool_id`: required in v1 strict mode.
- `capability_id`: required in v1 strict mode.
- `io_type`: required in v1 strict mode.
- `adapter_mode`: optional at input, defaults to `unknown` when any tool field exists.
  - allowed values: `local | remote | mock | hybrid | unknown`

Validation policy:

- In `require_v1_fields=True`, all four tool keys must be present after normalization.
- `metadata.tool_id/capability_id/io_type/adapter_mode` must be present for downstream extraction.
- If both top-level and `metadata.*` values are provided, they must match.

## CandidateSet fields

- `candidates`: Top-K candidate list sorted by rank.
- `default_recommendation`: default recommended `candidate_id`.
- `explanation`: explanation for the whole candidate set.

## Backward compatibility policy (additive-only)

- Legacy `payload` is kept and treated as equivalent to `structured_payload`.
- Legacy `default_suggestion` is kept and treated as equivalent to `default_recommendation`.
- If both legacy/new fields are provided, they must be consistent.

## Validation expectations

- Candidate IDs must be unique in one candidate set.
- `default_recommendation` must point to an existing candidate.
- For v1 strict validation, every candidate must provide full v1 fields.
- For Requirement-2 strict validation, every candidate must provide tool metadata fields.

## Training extraction alignment (#145)

The following keys are intentionally aligned with training extraction schema naming:

- `tool_id`
- `capability_id`
- `io_type`
- `adapter_mode`
