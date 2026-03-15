# W12 Issue #151: End-to-End Demo & Audit Replay Runbook

## Goal

Provide a reproducible demo chain with audit replay evidence:

- Candidate generation -> HITL decision -> execution recovery -> terminal output
- Audit chain verification: `PendingAction -> Decision -> EventLog`
- Tool fallback replay evidence (`from_tool -> to_tool`)

## Standard Inputs

- `examples/w12_issue151/six_stage_waiting_patch_input.json`
- `examples/w12_issue151/tool_fallback_remote_to_local_input.json`

## Reproduction Commands

```bash
uv run python scripts/run_w12_issue151_demo_audit.py
```

The script executes two deterministic integration scenarios:

1. `tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done`
2. `tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level`

## Output Artifacts

Generated under `output/demo/w12-issue-151/`:

- `release-validation.md`
- `demo-summary.json`
- `replay-record-001-six-stage-hitl.md`
- `replay-record-002-tool-fallback.md`
- `logs/int_s6_patch_decision_replay_done.jsonl`
- `logs/int_layered_patch_remote_to_local.jsonl`

## Expected Checks

- `audit_chain_pendingaction_decision_eventlog = PASS`
- `tool_fallback_switch_recorded = PASS`
- `e2e_flow_reaches_done = PASS`

## Troubleshooting

- If replay logs are missing:
  - Confirm tests pass standalone with `uv run pytest <target> -q`.
  - Confirm `data/logs/<task_id>.jsonl` exists after the test run.
- If environment has stale logs:
  - Re-run the command; each scenario clears and rewrites its task log.
- If `uv` is not available:
  - Install/activate project runtime first, then rerun.
