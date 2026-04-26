# Issue #233 action/runtime audit evidence

## Scope

This note summarizes repository evidence for GitHub issue
[#233](https://github.com/Yuri-Kon/thesis-project/issues/233),
`W14-Observability-3b: action/runtime 审计事件字段补齐`.

The issue asked for action/runtime audit fields covering at least step,
recovery escalation, `TASK_STATUS_CHANGED`, and WAITING-related events, with
fields consumable by experiment scripts without manual stitching.

## Verification date

Checked on 2026-04-25 from branch `issue-233-output-evidence`.

## Summary conclusion

Evidence exists, but it is split across two layers:

- `output/` contains experiment-facing derived columns and summaries that are
  directly consumed by the analysis scripts.
- Raw per-event audit fields are in `data/logs/*.jsonl`, referenced from
  `output/**/run_level_results.json*` by `event_log_path`.

No `output/issue233*` artifact was found. The evidence is therefore traceable
through the experiment outputs and their linked event logs, rather than through
a single issue-specific output file.

## Output-layer evidence

Representative output file:

- `output/experiment/w16-expr-1/issue270-rerun-20260419b/run_level_results.json`

Representative fields observed in run-level rows:

- `runtime_state_observable`
- `shadow_output_observable`
- `action_continue_count`
- `action_patch_local_count`
- `action_suffix_replan_count`
- `action_stop_count`
- `event_log_path`
- `snapshot_path`
- `run_config_path`

Example rows in that file show `runtime_state_observable: true`,
`shadow_output_observable: true`, and action-count columns for
`lite_belief_state` runs. The same rows point back to raw event logs, for
example:

- `data/logs/issue270-rerun-20260419b_lite_belief_state_enzyme_like_fold_r01.jsonl`
- `data/logs/issue270-rerun-20260419b_lite_belief_state_enzyme_like_fold_r02.jsonl`

Representative aggregate output:

- `output/experiment/w16-expr-1/issue270-rerun-20260419b/matrix_metrics_summary.json`

This aggregate includes direct experiment metrics such as:

- `runtime_state_observable_rate`
- `shadow_output_observable_rate`
- `action_continue_mean`
- `action_patch_local_mean`
- `action_suffix_replan_mean`
- `action_stop_mean`
- `shadow_action_agreement_rate`

For the `lite_belief_state` group in this artifact, the observed values include
`runtime_state_observable_rate: 1.0` and
`shadow_output_observable_rate: 0.8571428571428571`.

## Raw event-log evidence

Representative raw event log:

- `data/logs/issue270-rerun-20260419b_lite_belief_state_high_solubility_r02.jsonl`

Observed event coverage in that log:

- `STEP_FINISHED` carries `data.action_name`,
  `data.evidence_source`, `data.runtime_policy`,
  `data.belief_state_enabled`, and `data.runtime_state_summary`.
- `REPLACE_TOOL` and `STRUCTURE_PATCH` carry `data.action_name`,
  `data.action_score`, `data.shadow_score`, `data.evidence_source`,
  `data.recovery`, and `data.runtime_state_summary`.
- `RECOVERY_ESCALATED` carries `data.action_name`,
  `data.action_score`, `data.shadow_score`, `data.evidence_source`,
  `data.recovery`, and `data.runtime_state_summary`.
- `WAITING_ENTER` carries `data.action_type`, `data.action_name`,
  `data.action_score`, `data.shadow_score`, `data.evidence_source`,
  `data.runtime_policy`, `data.belief_state_enabled`,
  `data.runtime_state_summary`, and `data.waiting_state`.
- `TASK_STATUS_CHANGED` carries `data.runtime_state_summary` on relevant
  runtime-state transitions.
- `STEP_FAILED` carries failure details plus `data.action_name`,
  `data.workflow_action_reason`, `data.evidence_source`,
  `data.runtime_policy`, `data.belief_state_enabled`,
  and `data.runtime_state_summary`.

## Structured count check

A structured scan of `output/**/*.json*` found derived experiment columns but
not raw per-event audit fields:

| Field | Count in `output/**/*.json*` |
| --- | ---: |
| `runtime_state_observable` | 280 |
| `shadow_output_observable` | 280 |
| `action_continue_count` | 280 |
| `action_patch_local_count` | 280 |
| `action_suffix_replan_count` | 280 |
| `action_stop_count` | 280 |
| `action_name` | 0 |
| `action_score` | 0 |
| `shadow_score` | 0 |
| `runtime_state_summary` | 0 |
| `evidence_source` | 0 |

This is expected because raw audit fields live in event logs, while `output/`
stores experiment-level rollups and links.

A structured scan of the 120 event logs referenced by `output/**/run_level_results.json*`
found the following selected event coverage:

| Event | Count | Observed audit fields |
| --- | ---: | --- |
| `STEP_FINISHED` | 219 | `action_name`, `evidence_source`; `runtime_state_summary` in 24 rows |
| `STEP_FAILED` | 3 | `action_name`, `evidence_source`; `runtime_state_summary` in 1 row |
| `RECOVERY_ESCALATED` | 2 | `action_name`, `action_score`, `shadow_score`, `runtime_state_summary`, `evidence_source`, recovery nested score/runtime fields |
| `TASK_STATUS_CHANGED` | 669 | `runtime_state_summary` in 55 rows |
| `WAITING_ENTER` | 91 | `action_name`, `action_score`, `shadow_score`, `runtime_state_summary`, `evidence_source` |
| `DECISION_APPLIED` | 176 | action/score/shadow/runtime/evidence fields in 88 rows |
| `REPLACE_TOOL` | 2 | action/score/shadow/runtime/evidence fields plus recovery nested fields |
| `STRUCTURE_PATCH` | 2 | action/score/shadow/runtime/evidence fields plus recovery nested fields |

## Source-code traceability

The experiment-side direct-consumption logic is implemented in
`src/infra/w12_vertical_experiment.py`:

- `_runtime_state_candidates()` reads `data.runtime_state_summary`,
  `data.waiting_runtime_summary.runtime_state_summary`, and
  `data.recovery.runtime_state_summary`.
- `_has_shadow_output()` reads `data.shadow_score`,
  `data.waiting_runtime_summary.shadow_score`, and
  `data.recovery.shadow_score`.
- `_summarize_run()` computes `runtime_state_observable`,
  `shadow_output_observable`, and action counters from event rows.

The timeline/log extraction path is implemented in `src/storage/log_store.py`:

- `_extract_observability_fields()` normalizes `action_name`, `action_score`,
  `shadow_score`, `runtime_state_summary`, `waiting_runtime_summary`,
  `evidence_source`, and recovery metadata from event payloads.

Integration coverage exists in `tests/integration/test_event_log_integration.py`
for WAITING and decision events carrying:

- `action_name`
- `action_score`
- `shadow_score`
- `evidence_source`
- `runtime_state_summary`

## Evidence mapping to issue #233 requirements

| Issue requirement | Evidence status |
| --- | --- |
| Action/runtime audit field names fixed | Present in contracts/logging code and raw event logs |
| Fields land in step events | Present in `STEP_FINISHED` and `STEP_FAILED` rows |
| Fields land in recovery escalation events | Present in `RECOVERY_ESCALATED` rows |
| Fields land in `TASK_STATUS_CHANGED` events | Runtime summary present on relevant status changes |
| Fields land in WAITING-related events | Present in `WAITING_ENTER`; decision path also covered by `DECISION_APPLIED` and `WAITING_EXIT` tests |
| Experiment scripts can consume without manual stitching | Present through `run_level_results.json*` derived columns and event-log path linkage |
| Compatible with existing log paths | Present through `data/logs/*.jsonl` referenced by output rows |

## Caveat

If the evidence requirement is interpreted as "all raw audit fields must be
physically duplicated inside `output/` files", that is not currently true.
The current design keeps raw event rows in `data/logs/` and stores derived
experiment metrics plus traceability links in `output/`.
