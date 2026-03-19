# S3 Quality Gate Contract (Issue #157)

## Scope

Runtime hard gate for `S2 -> S3` batch candidates.

- Executor runs the QC evaluation.
- Safety only evaluates risk signals from S3 outputs.

## Entry

- `ExecutorAgent.quality_gate_from_s2(...)`

## Input

- Primary: `S2.outputs.structure_results` (batch rows)
- Fallback: single `S2` output row (`sequence/pdb_path/plddt`)

Each candidate row may contain:

- `candidate_id`
- `status`
- `sequence`
- `pdb_path`
- `plddt`
- `tool_id`
- `lineage`
- `failure_code` / `failure_reason` (when upstream failed)

## Rule Set

S3 evaluates:

1. length range
2. sequence character legality
3. structure completeness (`pdb_path`)
4. confidence completeness/threshold (`plddt`)
5. low complexity (composition + repeat run)

Constraint defaults:

- `min_length=20`
- `max_length=400`
- `min_plddt=0.7`
- `max_residue_fraction=0.7`
- `max_repeat_run=6`

Constraint overrides:

- top-level task constraints
- nested `constraints.quality_gate`

## Reject Codes

- `S3_SOURCE_STRUCTURE_FAILED`
- `S3_SEQUENCE_MISSING`
- `S3_SEQUENCE_LENGTH_OUT_OF_RANGE`
- `S3_SEQUENCE_INVALID_CHAR`
- `S3_STRUCTURE_MISSING`
- `S3_PLDDT_MISSING`
- `S3_PLDDT_BELOW_THRESHOLD`
- `S3_LOW_COMPLEXITY_COMPOSITION`
- `S3_LOW_COMPLEXITY_REPEAT`
- aggregate fail code: `S3_ALL_CANDIDATES_REJECTED`

## Output Contract

`StepResult.outputs` (`stage_id=S3`):

- `qc_results`: per-candidate
  - `pass_fail`
  - `reject_codes`
  - `reject_reasons`
  - `reason`
  - `qc_flags`
  - `qc_metrics`
- `passed_samples` / `failed_samples`
- `pass_count` / `fail_count` / `pass_fail`
- `reject_code_counts`
- `quality_gate.status` (`PASS`/`BLOCK`)
- Requirement2 alignment:
  - `capability_id=quality_qc`
  - `io_type=sequence_structure_to_qc_metrics`

Executor step status:

- `success`: at least one candidate passes S3
- `failed`: all candidates rejected (`failure_code=S3_ALL_CANDIDATES_REJECTED`)

## Traceability

S3 emits traceable fields in step events:

- `data.stage_id`
- `data.failure_code` (if any)
- `data.quality_gate` summary (`pass_count/fail_count/pass_fail/reject_code_counts/failed_samples`)
