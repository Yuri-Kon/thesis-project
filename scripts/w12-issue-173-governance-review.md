# W12 Issue #173: Governance Metrics Review Runbook

## Goal

Generate reproducible governance evidence for:

- Audit chain completeness
- Failure traceability
- Decision replay correctness

And merge governance outputs with existing vertical experiment results.

## Inputs

- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv`
- `output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl`

## Command

```bash
uv run python scripts/evaluate_w12_issue173_governance.py
```

## Outputs

Generated in `output/experiment/w12-expr-2/issue173-governance-review/`:

- `governance_metrics_summary.json`
- `governance_metrics_by_group.csv`
- `governance_vs_vertical_comparison.csv`
- `governance_replay_sample.md`
- `governance-report.md`

## Metric Definitions

- `waiting_chain_complete_rate`:
  - Ordered `WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT` per `pending_action_id`
- `replay_success_rate`:
  - Ratio of chains replayable in strict order
- `failure_traceable_rate`:
  - `STEP_FAILED` entries containing `step_id + tool/tool_id + failure_code`
- `snapshot_linked_rate`:
  - Existence rate of `snapshot_path` declared in run index

## Troubleshooting

- Missing logs:
  - Check `event_log_path` in run index and file existence on disk.
- Zero replay rate:
  - Dataset may not include decision-applied runs; verify with demo replay sample from issue #151.
- Mismatch with vertical summary:
  - Inspect `governance_vs_vertical_comparison.csv` for per-group deltas.
