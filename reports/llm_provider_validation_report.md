# LLM Provider Validation Report

- Generated at: `2026-03-19T23:18:48+08:00`
- Baseline commit before fixes: `d7aa6f9` (`feat(llm): add multi-provider planning support`)

## Scope

This report validates the newly added multi-provider planner support and the related smoke test tooling.

## Code Fixes Applied

- Isolated planner tests from real shell API keys so default-path assertions are deterministic again.
- Updated stale patch-agent expectation to match the current layered recovery policy: parameter-level retry is preferred before tool swap.
- Hardened `scripts/smoke_test_llm_providers.py` with:
  - per-provider hard timeout
  - subprocess isolation
  - structured failure capture
  - progress logging
  - JSON report output suitable for later analysis
- Added unit tests for the smoke script timeout and missing-key behavior.

## Verification Commands

```bash
uv run pytest tests/unit/test_provider_registry.py tests/unit/test_anthropic_messages_provider.py tests/unit/test_openai_compatible_provider.py tests/unit/test_planner_agent.py tests/unit/test_protein_tool_kg.py -q --durations=10
uv run pytest tests/unit/test_planner_with_provider.py tests/unit/test_planner_patch_agent.py tests/unit/test_smoke_test_llm_providers.py -q
uv run pytest tests/unit -q --durations=20
UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test_llm_providers.py --providers qwen-plus,deepseek-chat,glm-5,nemotron --per-provider-timeout 15 --output reports/llm_provider_smoke_report.json
```

## Results

### Unit tests

- `tests/unit` total: `495 passed`, `0 failed`, `1 warning`
- Total runtime: `20.97s`

Top runtime hotspots from `--durations=20`:

1. `tests/unit/test_plan_runner.py::test_auto_replan_resolves_pending_action` -> `6.69s`
2. `tests/unit/test_patch_runner.py::test_patch_runner_triggers_patch_and_records_meta` -> `2.05s`
3. `tests/unit/test_visualization_adapter.py::test_invalid_pdb_ref_enters_waiting_replan` -> `2.05s`
4. `tests/unit/test_patch_runner.py::test_patch_runner_enters_waiting_patch_when_gate_requires_hitl` -> `2.00s`
5. `tests/unit/test_plan_runner.py::test_run_plan_executes_insert_before_patch_steps` -> `2.00s`

### Real provider smoke test

Results written to [llm_provider_smoke_report.json](/home/yurikon/文档/thesis/thesis-project.dev/reports/llm_provider_smoke_report.json).

| Provider | Success | Elapsed (s) | Result |
|---|---:|---:|---|
| `qwen-plus` | No | 1.547 | `Connection error` |
| `deepseek-chat` | No | 1.269 | `Connection error` |
| `glm-5` | No | 0.026 | `Temporary failure in name resolution` |
| `nemotron` | No | 1.440 | `Connection error` |

## Bottleneck Analysis

Primary bottleneck is external connectivity, not local planner correctness.

Evidence:

- All impacted unit tests pass locally after isolation fixes.
- Smoke failures occur before any plan-quality validation and are network-facing.
- `glm-5` fails at DNS resolution almost immediately.
- `qwen-plus`, `deepseek-chat`, and `nemotron` fail with transport-level connection errors in about `1.3-1.5s`, which is consistent with outbound connectivity failure rather than model-side long inference latency.

## Conclusion

The multi-provider planning code path is locally valid and test-clean.
Current real-world unavailability is caused by this environment's inability to reach external provider endpoints, so the next experimental bottleneck to clear is network/DNS/egress access, not planner logic.
