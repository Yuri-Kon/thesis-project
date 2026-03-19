# S1 Sequence Exploration Contract

This document defines the planner-side S1 (`stage_id=S1`) contract for issue `#155`.

## Scope

- Planner candidate metadata contract for sequence exploration.
- Canonical S1 input/output field names.
- Primary/fallback source lineage for deterministic Top-K candidates.

## Canonical S1 Fields

S1 metadata is attached on the sequence exploration step (`Plan.steps[0]` in de novo template):

- `metadata.stage_id`: `S1`
- `metadata.stage_name`: `sequence_exploration`
- `metadata.s1_contract.inputs`:
  - `goal`
  - `length_range`
  - `prompt`
  - `template`
- `metadata.s1_contract.outputs`:
  - `sequence`
  - `candidates`
  - `candidate_confidence`
  - `candidate_source`
- `metadata.candidate_confidence_field`: `score_breakdown.confidence`

These fields are additive and do not change existing runtime schema.

## Lineage And Source Metadata

S1 lineage is attached at `metadata.lineage` on the S1 step and copied into candidate metadata:

- `stage_id`: `S1`
- `strategy`: `toolkg_capability_topk`
- `primary_tool_id`
- `selected_tool_id`
- `fallback_tool_ids`
- `source_tier`: `primary | fallback`
- `source_reason`
- `capability_id`
- `io_type`
- `adapter_mode`

Candidate-level mirrors:

- `candidate.metadata.stage_id = S1`
- `candidate.metadata.lineage`
- `candidate.metadata.sequence_source`
- `candidate.metadata.sequence_source_tool_id`
- `candidate.metadata.sequence_confidence`

## Fallback Policy

- Primary source: best-ranked S1 sequence tool from ToolKG.
- Fallback source: alternative S1 sequence tools (same capability first, then compatible secondary source if available).
- Top-K stays deterministic and keeps existing sort key semantics.

## Requirement-2 Alignment

Requirement-2 tool fields remain unchanged and mandatory in strict mode:

- `tool_id`
- `capability_id`
- `io_type`
- `adapter_mode`

S1 lineage only extends metadata for traceability and does not replace these fields.
