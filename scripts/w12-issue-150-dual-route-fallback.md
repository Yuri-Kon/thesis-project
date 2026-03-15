# W12 Issue #150: Dual-Route Planner Runtime Fallback

## Goal

Introduce a runtime-safe dual-route planner policy (`local default + external fallback`) without changing FSM/HITL ownership.

## Delivered Scope

- Planner dual-route routing and threshold triggers in provider layer.
- External fallback remains enabled by default.
- One-click circuit breaker via:
  - runtime config: `runtime_fallback.force_external_only=true`
  - env switch: `PLANNER_FORCE_EXTERNAL_FALLBACK=1`
- Route decision audit events with required fields:
  - `from_tool`, `to_tool`, `capability_id`, `trigger_threshold`
- Integration tests covering trigger and recovery.

## Trigger Conditions

The router can switch to external provider when any trigger hits:

1. `schema_fail_streak >= schema_fail_threshold`
2. `candidate_executable_rate < executable_rate_threshold`
3. `candidate_executable_drop >= executable_drop_threshold`
4. `consecutive_execution_failures >= consecutive_failure_threshold`
5. `sustained_high_risk >= sustained_high_risk_threshold`

## Config

Reference config:

- `configs/runtime/w12_issue150_dual_route_fallback.json`

Task-level override example (`task.constraints.runtime_fallback`):

```json
{
  "runtime_fallback": {
    "enable_dual_route": true,
    "force_external_only": false,
    "schema_fail_threshold": 2,
    "executable_rate_threshold": 0.95,
    "executable_drop_threshold": 0.05,
    "consecutive_failure_threshold": 2,
    "sustained_high_risk_threshold": 2,
    "fallback_capability": "planner_generation"
  }
}
```

## Observability

Route decisions emit `PLANNER_ROUTE_DECISION` with:

- top-level: `from_tool`, `to_tool`, `capability_id`
- `data.trigger_reason`
- `data.trigger_threshold`

## Validation

```bash
uv run pytest \
  tests/integration/test_planner_dual_route_fallback.py \
  tests/unit/test_log_store_timeline.py \
  tests/unit/test_planner_with_provider.py -q
```
