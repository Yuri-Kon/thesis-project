# Issue 231: Unified Action Selector And Recovery Mapping

## Scope

This note captures the implementation-facing contract for issue `#231` and aligns the code path with the 2026-03-29 frozen design:

- `SID:planner.algorithm.runtime_action_selection`
- `SID:planner.algorithm.action_priority_resolution`
- `SID:planner.algorithm.stop_semantics`
- `SID:fsm.states.waiting_replan_confirm`
- `SID:arch.contracts.pending_action`

## Unified Selector Interface

The unified runtime selector entrypoint is [`src/workflow/recovery.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/recovery.py):

- `WorkflowActionSelectorInput`
- `select_workflow_action(...)`
- `resolve_workflow_action_route(...)`

The selector action space is fixed to:

- `continue`
- `patch_local`
- `suffix_replan`
- `stop`

The selector remains recovery-aware instead of bypassing recovery.

## Recovery Mapping

The action-to-flow mapping is centralized in `WorkflowActionRoute`:

- `continue -> continue`
- `patch_local -> patch`
- `suffix_replan -> replan`
- `stop -> stop`

Workflow ownership remains unchanged:

- [`src/workflow/patch_runner.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/patch_runner.py) owns local patch attempts.
- [`src/workflow/plan_runner.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/plan_runner.py) owns replan escalation and WAITING entry.
- [`src/workflow/decision_apply.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/decision_apply.py) owns human decision application.

## Terminal Stop Semantics

`stop` no longer jumps directly to terminal failure from the selector path.

The implemented compatibility mapping is:

- selector chooses `stop`
- [`src/workflow/plan_runner.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/plan_runner.py) builds a `replan_confirm` `PendingAction`
- the pending action carries a `terminal_stop`-style candidate encoded as:
  - `replan_mode = "suffix_replan"`
  - `terminal_policy = "stop"`
  - `terminal_reason = economic_stop | evidence_exhausted | unsafe_to_continue | recovery_exhausted`
- task enters `WAITING_REPLAN_CONFIRM`
- if the human accepts that candidate, [`src/workflow/decision_apply.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/decision_apply.py) transitions to `FAILED`
- if the human continues, the task returns to `RUNNING`
- if the human cancels, the task transitions to `CANCELLED`

No new FSM state is introduced.

## Audit Fields

The WAITING/decision path now preserves the selector-facing audit fields needed for downstream integration:

- `workflow_action`
- `workflow_action_mapped_flow`
- `workflow_action_reason`
- `workflow_action_target`
- `terminal_policy`
- `terminal_reason`
- `replan_mode`
- `preserve_prefix_until_step_index`
- `runtime_state_summary`

These fields are surfaced through:

- [`src/workflow/pending_action.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/pending_action.py)
- [`src/workflow/decision_apply.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/decision_apply.py)

## File Mapping

Required issue landing points are now explicit:

- [`src/workflow/recovery.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/recovery.py): unified selector interface, action priority handling, action route mapping, terminal-stop candidate helper
- [`src/workflow/plan_runner.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/plan_runner.py): `stop -> WAITING_REPLAN_CONFIRM` integration
- [`src/workflow/decision_apply.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/decision_apply.py): `terminal_stop accept -> FAILED`
- [`src/workflow/pending_action.py`](/Users/yurikon/workspace/thesis/thesis-project.dev/src/workflow/pending_action.py): WAITING audit propagation

## Acceptance Checklist

- unified selector interface and fixed action space: implemented
- four actions mapped to existing recovery loop: implemented
- `terminal_stop` WAITING/Decision/FAILED boundary: implemented
- consistent with 2026-03-29 frozen design and no new FSM state: implemented
