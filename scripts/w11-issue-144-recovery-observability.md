# W11 Issue #144: Recovery Observability Upgrade

## Goal

Enhance recovery/audit observability so training extraction, audit reconciliation, and failure diagnosis can replay key decisions and recovery nodes by task and by tool dimension.

## Scope Delivered

- Storage timeline normalization extended with recovery observability fields.
- API timeline endpoint supports filter query params for replay views.
- Recovery/decision event writes now include richer tool and decision source context.
- Legacy logs remain readable when new fields are missing.

## New Timeline Fields

Event-level normalized fields (when available):

- `tool_id`, `capability_id`, `io_type`, `adapter_mode`
- `from_tool`, `to_tool`
- `failure_type`, `failure_code`
- `candidate_id`, `decision_source`
- `recovery_layer`, `recovery_reason`

## API Query Extensions

`GET /tasks/{task_id}/events`

Optional query params:

- `event_type`
- `tool_id`
- `capability_id`
- `adapter_mode`

Example:

```bash
curl "http://127.0.0.1:8000/tasks/<task_id>/events?tool_id=esmfold&adapter_mode=remote"
```

## Event Dictionary (Recovery-Critical)

- Failure tracing:
  - `failure_type`, `failure_code`
- Candidate and decision tracing:
  - `candidate_id`, `decision_source`
- Recovery layer tracing:
  - `recovery_layer`, `recovery_reason`
- Tool-chain tracing:
  - `tool_id`, `capability_id`, `io_type`, `adapter_mode`, `from_tool`, `to_tool`

## Compatibility Note

Legacy logs without these fields are still parsed and returned with `null` values for missing observability fields. Invalid JSON lines are skipped in non-strict mode.

## Validation

- Unit tests:
  - `tests/unit/test_log_store_timeline.py`
- API behavior tests:
  - `tests/api/test_api_endpoints.py::TestTaskEndpoints::test_get_task_events_timeline_mapping_and_order`
- Integration safety net:
  - `tests/integration/test_event_log_integration.py`
