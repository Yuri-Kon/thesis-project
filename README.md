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
