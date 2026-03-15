# Thesis Project Demo

Minimal end-to-end demo launcher for the multi-agent protein design workflow.

## One Command

```bash
./run_demo.sh
```

Then open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/ui/tasks/<task_id>/events`

Detailed demo usage and options:

- `examples/README_DEMO.md`

## Candidate Validation Failure Codes (Issue #141)

Execution pre-gate now hard-fails invalid candidates with these codes:

- `CANDIDATE_SCHEMA_INVALID`
- `CANDIDATE_TOOL_UNAVAILABLE`
- `CANDIDATE_IO_CLOSURE_BROKEN`
- `CANDIDATE_PARAMS_INVALID`
- `CANDIDATE_RESOURCE_CONSTRAINT`
- `CANDIDATE_ADAPTER_UNSUPPORTED`

Structured failure payload is emitted as `CANDIDATE_VALIDATION_FAILED` EventLog,
including `tool_id`, `capability_id`, and `io_type` fields when available.

## S1 Sequence Exploration Contract (Issue #155)

Planner Top-K now annotates sequence exploration candidates with explicit `S1` lineage:

- `stage_id`: `S1`
- `stage_name`: `sequence_exploration`
- `s1_contract.inputs`: `goal/length_range/prompt/template`
- `s1_contract.outputs`: `sequence/candidates/candidate_confidence/candidate_source`
- `lineage`: `primary_tool_id/selected_tool_id/fallback_tool_ids/source_tier`
- candidate metadata mirrors `stage_id`, `lineage`, `sequence_source`, `sequence_confidence`

Fallback policy:

- Primary source uses the best-ranked S1 sequence tool from ToolKG.
- Fallback source uses deterministic alternative tools (same capability first, then compatible alternatives when available).
- Top-K ordering remains deterministic.

## S2 Structure Projection Contract (Issue #156)

S2 output contract (adapter-normalized):

- `stage_id`: `S2`
- `pdb_path`: projected structure file path
- `plddt`: normalized confidence score
- `confidence`: `{plddt_mean, level}`
- `lineage`: `{stage_id, tool_id, io_type}`

Batch mapping entrypoint:

- `ExecutorAgent.project_structures_from_s1(...)` maps S1 candidates to S2 structures in batch mode.
- Keeps partial success: failed candidates are retained with failure code while successful candidates continue.
- Preserves lineage per candidate (`source_step_id`, `source_candidate_id`, upstream lineage).

S2 normalized failure codes:

- `S2_SEQUENCE_INVALID`
- `S2_OUTPUT_INVALID`
- `S2_TOOL_UNAVAILABLE`
- `S2_TOOL_EXECUTION_FAILED`
- `S2_FALLBACK_EXHAUSTED`
- `S2_ALL_CANDIDATES_FAILED`

## S3 Quality Gate Contract (Issue #157)

S3 runtime hard gate now supports batch evaluation from S2 outputs:

- Entry: `ExecutorAgent.quality_gate_from_s2(...)`
- Input: `S2.structure_results` (or single S2 structure output)
- Output:
  - `stage_id`: `S3`
  - `qc_results`: per-candidate `pass_fail + reject_codes + reject_reasons + qc_metrics`
  - `failed_samples` / `passed_samples`
  - `pass_count` / `fail_count` / `pass_fail`
  - `reject_code_counts`
  - Requirement2-aligned metadata: `capability_id=quality_qc`, `io_type=sequence_structure_to_qc_metrics`

S3 reject code enum:

- `S3_SOURCE_STRUCTURE_FAILED`
- `S3_SEQUENCE_MISSING`
- `S3_SEQUENCE_LENGTH_OUT_OF_RANGE`
- `S3_SEQUENCE_INVALID_CHAR`
- `S3_STRUCTURE_MISSING`
- `S3_PLDDT_MISSING`
- `S3_PLDDT_BELOW_THRESHOLD`
- `S3_LOW_COMPLEXITY_COMPOSITION`
- `S3_LOW_COMPLEXITY_REPEAT`
- Stage fail code: `S3_ALL_CANDIDATES_REJECTED`

Traceability:

- S3 execution emits `STEP_FINISHED/STEP_FAILED` with `data.quality_gate` summary.
- `PlanRunner` step events now include `data.failure_code` and S3 quality summary fields for downstream extraction reuse.
