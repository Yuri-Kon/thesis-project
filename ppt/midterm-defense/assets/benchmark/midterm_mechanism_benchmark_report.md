# midterm_mechanism_benchmark

## Summary
- generated_at: `2026-03-20T15:47:54+00:00`
- config: `configs/experiments/midterm_mechanism_benchmark.json`
- run_dir: `output/experiment/midterm-mechanism-benchmark/midterm-mechanism-benchmark-r2`
- scenarios: `17`
- passed: `17`
- pass_rate: `1.0000`
- avg_duration_sec: `2.106`

## Why This Benchmark
- Current vertical midterm results are weak on end biological effect, so this benchmark shifts the midterm evidence toward the project’s core contribution: controllable execution, HITL governance, structured recovery, routing, and summarization.
- All scenarios are reproducible integration checks that already exist in the repository and can be rerun end-to-end through `uv run pytest ...`.

## Family Summary

| family | scenarios | passed | pass_rate | avg_duration_sec | evidence_complete_rate |
|---|---:|---:|---:|---:|---:|
| Execution & Summary | 3 | 3 | 1.000 | 0.493 | 1.000 |
| Gate | 2 | 2 | 1.000 | 8.897 | 1.000 |
| HITL & Audit | 4 | 4 | 1.000 | 0.831 | 1.000 |
| Planner Routing | 3 | 3 | 1.000 | 0.471 | 1.000 |
| Recovery | 5 | 5 | 1.000 | 2.359 | 1.000 |

## Capability Coverage

| capability | scenarios | passed | pass_rate | family_count |
|---|---:|---:|---:|---:|
| candidate_scoring | 2 | 2 | 1.000 | 2 |
| decision_replay | 2 | 2 | 1.000 | 1 |
| end_to_end_execution | 2 | 2 | 1.000 | 2 |
| event_audit | 7 | 7 | 1.000 | 2 |
| failure_adaptation | 1 | 1 | 1.000 | 1 |
| failure_traceability | 1 | 1 | 1.000 | 1 |
| fsm_reconstruction | 1 | 1 | 1.000 | 1 |
| gate_control | 2 | 2 | 1.000 | 1 |
| hitl_decision | 3 | 3 | 1.000 | 1 |
| patch_recovery | 6 | 6 | 1.000 | 3 |
| planner_routing | 3 | 3 | 1.000 | 1 |
| quality_gate_recovery | 1 | 1 | 1.000 | 1 |
| replan_escalation | 3 | 3 | 1.000 | 1 |
| report_artifact | 3 | 3 | 1.000 | 1 |
| resilience | 2 | 2 | 1.000 | 2 |
| result_summarization | 3 | 3 | 1.000 | 1 |
| risk_gating | 1 | 1 | 1.000 | 1 |
| tool_fallback | 2 | 2 | 1.000 | 1 |
| waiting_gate | 3 | 3 | 1.000 | 2 |

## PPT Takeaways
- Midterm evidence should focus on mechanism validation rather than claiming final protein-design superiority.
- The strongest story is that gating, HITL, recovery, routing, end-to-end execution, and summarization now all have reproducible benchmark scenarios.
- Use the family and capability charts as the main experiment figures; add screenshots later as auxiliary evidence.

## Scenario Results

| scenario_id | family | passed | duration_sec | artifacts | signals |
|---|---|---:|---:|---:|---:|
| plan_gate_paths | Gate | 1 | 13.391 | 0/0 | 0/0 |
| patch_gate_paths | Gate | 1 | 4.404 | 0/0 | 0/0 |
| waiting_enter_event | HITL & Audit | 1 | 0.245 | 0/0 | 0/0 |
| decision_apply_events | HITL & Audit | 1 | 0.244 | 0/0 | 0/0 |
| fsm_reconstruction | HITL & Audit | 1 | 0.250 | 0/0 | 0/0 |
| six_stage_hitl_replay | HITL & Audit | 1 | 2.586 | 2/2 | 3/3 |
| s3_failure_to_replan | Recovery | 1 | 0.498 | 2/2 | 1/1 |
| layered_patch_tool_success | Recovery | 1 | 2.810 | 1/1 | 1/1 |
| layered_patch_remote_local | Recovery | 1 | 2.712 | 1/1 | 2/2 |
| patch_failure_to_replan | Recovery | 1 | 2.644 | 1/1 | 1/1 |
| high_risk_patch_to_replan | Recovery | 1 | 3.130 | 1/1 | 1/1 |
| mock_remote_full_flow | Execution & Summary | 1 | 0.502 | 1/1 | 0/0 |
| esmfold_summarizer_integration | Execution & Summary | 1 | 0.497 | 1/1 | 0/0 |
| summarizer_empty_results | Execution & Summary | 1 | 0.481 | 1/1 | 0/0 |
| dual_route_failures | Planner Routing | 1 | 0.469 | 0/0 | 0/0 |
| dual_route_recovery | Planner Routing | 1 | 0.473 | 0/0 | 0/0 |
| dual_route_exec_rate | Planner Routing | 1 | 0.472 | 0/0 | 0/0 |
