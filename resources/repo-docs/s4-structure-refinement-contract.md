# S4 Structure-conditioned Refinement Contract (Issue #158)

## Scope

Runtime iterative refinement loop under structural constraints:

- `S4 (protein_mpnn)` refines sequence candidates from structure context.
- Each iteration runs `S4 -> S2 -> S3` to verify structure and quality.
- Loop records lineage, gain, and stop reason for audit/replay.

## Entry

- `ExecutorAgent.refine_sequences_from_s3(...)`

## Input

- Primary: `S3.outputs.passed_samples`
- Fallback: `S3.outputs.qc_results(status=pass)` or `S3` primary row

Each baseline candidate should provide:

- `candidate_id`
- `sequence`
- `pdb_path`
- `plddt`
- `lineage` (optional)

## Loop Control

Config source (priority):

1. method args (`max_iterations`, `convergence_delta`, `max_degradation_rounds`)
2. `constraints.structure_refinement.*`
3. legacy top-level keys (`s4_max_iterations`, `s4_convergence_delta`, `s4_max_degradation_rounds`)
4. defaults: `3 / 0.01 / 1`

Stop conditions:

- `converged`: positive gain but `gain_vs_previous <= convergence_delta`
- `degradation_limit`: degradation rounds exceed `max_degradation_rounds`
- `refinement_failed`: S4 tool step failed
- `quality_gate_rejected`: S3 rejects all refined candidates
- `missing_source_pdb`
- `max_iterations_reached`

## Output Contract

`StepResult.outputs` (`stage_id=S4`) includes:

- `sequence`, `pdb_path`, `plddt` (selected best candidate)
- `refinement_iterations` (per-round lineage + gain + QC pass/fail)
- `iteration_count`, `successful_iterations`
- `stop_reason`
- `gain_metrics` (`baseline_plddt`, `final_plddt`, `delta_vs_baseline`)
- `lineage.rollback_applied`

`StepResult.artifacts` includes:

- `refinement_audit_path`: persisted JSON audit file

## Audit Persistence

Audit payload is written to:

- `output/artifacts/s4_refinement_<task_id>_<step_id>.json`

Audit contains:

- baseline snapshot
- per-iteration records
- selected candidate
- summary (`iteration_count`, `stop_reason`, `rollback_applied`, `gain_vs_baseline`)

## Compatibility

- S2/S3 interfaces are reused without schema-breaking changes.
- Existing fields remain intact; S4 adds additive metadata/artifact fields only.
