# W12 Issue #149: Offline Benchmark vs External Baseline

## Goal

Generate a reproducible offline benchmark report for candidate model `v0.3.0-rc1` against an external baseline reference, with RC Gate-B pass/fail decision.

## Input Baseline

This script reuses Week12 vertical experiment outputs:

- Summary metrics: `output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv`
- Tool/capability slices: `output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv`

Default comparison mapping:

- Candidate group: `A2`
- Baseline group: `A0`

## Run Command

```bash
uv run python scripts/evaluate_w12_issue149_offline_benchmark.py \
  --summary-csv output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv \
  --slice-csv output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv \
  --self-group A2 \
  --baseline-group A0 \
  --candidate-version v0.3.0-rc1 \
  --baseline-version external-baseline-a0 \
  --output-dir output/experiment/w12-expr-2/issue149-offline-benchmark
```

## Output

- `release_benchmark.json`
- `release_benchmark_comparison.csv`
- `release_benchmark_gate_checks.csv`
- `tool_coverage_vs_metrics.csv`
- `release-benchmark.md`

## Metric Formula and Denominator

- Schema legal rate: valid schema runs / total runs in group.
- Executable plan rate: runs without step failure / total runs in group.
- Patch minimality hit rate: parameter-level patch events / all patch events.
  - If patch events are 0, value is null and gate check fails.
- `suffix_replan` prefix retention rate: runs preserving successful prefix / suffix-replan runs.
  - If suffix-replan sample count is 0, value is null and gate check fails.

## RC Gate-B Thresholds

- Schema legal rate >= 99.5%
- Executable plan rate >= 95%
- Patch minimality hit rate >= 80%
- `suffix_replan` prefix retention rate = 100%

## Requirement-2 Merge Checks

- Per-tool / per-capability slices are exported in `tool_coverage_vs_metrics.csv`.
- Report explicitly maps coverage to candidate/baseline usage deltas.
- `release-benchmark.md` includes gate blockers when thresholds are not met.
