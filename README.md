# Thesis Project Demo

Minimal end-to-end demo launcher for the multi-agent protein design workflow.

## One Command

```bash
./run_demo.sh
```

Then open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

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
