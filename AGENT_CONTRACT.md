# AGENT_CONTRACT.md

System contract for all coding agents in this repository.
This file is non-negotiable. If another instruction conflicts with it, this file wins.

## 1. Sources Of Truth

- Code workspace: `thesis-project.dev`
- Design workspace: `../thesis-project.design`
- Authoritative design specs: `../thesis-project.design/docs/design/`
- Deterministic spec lookup:
  - `../thesis-project.design/docs/index/index.json`
  - `../thesis-project.design/docs/index/topic_views.json`
  - `.agents/skills/doc-slicer/scripts/docslice --sid|--topic|--ref ...`

Before changing FSM behavior, agent responsibilities, public contracts, or execution semantics, retrieve the relevant design fragments with doc-slicer.

## 2. Human Decision Boundary

Agents must not decide key system behavior on their own.

Stop and ask for explicit user confirmation before:

- adding, removing, renaming, or reinterpreting FSM states or transitions;
- changing when human confirmation is required or skipped;
- changing agent role boundaries or which component owns a decision;
- changing public schema field names, meanings, or compatibility behavior;
- changing retry, patch, replan, cancellation, failure, or terminal-state semantics;
- introducing new architecture, execution modes, or safety policies not covered by design specs.

When intent is unclear, make only the smallest safe implementation change. Do not infer missing product or architecture decisions.

## 3. FSM Invariants

This project is an LLM-driven multi-agent system controlled by an explicit FSM.

- State must be explicit, validated, persisted, and logged.
- State mutation is owned by workflow control logic only.
- No hidden transitions, skipped states, or direct terminal jumps.
- Terminal states (`DONE`, `FAILED`, `CANCELLED`) are immutable.
- `WAITING_*` states mean execution is paused pending a human decision.

Canonical external lifecycle:

```text
CREATED -> PLANNING -> (WAITING_PLAN_CONFIRM | PLANNED) -> RUNNING
RUNNING -> (WAITING_PATCH_CONFIRM | WAITING_REPLAN_CONFIRM | SUMMARIZING)
WAITING_*_CONFIRM -> (RUNNING | FAILED | CANCELLED)
RUNNING -> SUMMARIZING -> DONE
```

Internal recovery states may exist only as specified and must map back to external states.

## 4. Agent Role Boundaries

- `PlannerAgent`: produces `Plan`, `PlanPatch`, or `Replan` candidates only. It must not execute tools, inspect runtime artifacts directly, or mutate state.
- `ExecutorAgent`: is the only tool executor. It owns bounded retries, patch application flow, and replan triggers. It must stop tool execution in any `WAITING_*` flow and must not approve human decisions.
- `SafetyAgent`: outputs evaluation only (`ok`, `warn`, `block`). It must not execute tools, edit plans, or override workflow results.
- `SummarizerAgent`: aggregates outputs into user-facing summaries. It must not re-run tools or change plans/state.

## 5. Data And Recovery Contracts

- Schemas are compatibility contracts: do not remove fields, rename fields, or change established semantics.
- Extensions must be additive and backward-compatible. Prefer optional fields, `metadata`, and `metrics`.
- Step references such as `S1.sequence` stay symbolic at planning time.
- Failure recovery order is bounded retry, then minimal patch, then replan while preserving successful prefix when possible.
- A single step failure must not directly set the task to `FAILED`; failure is valid only after recovery is exhausted or safety blocks permanently.
- Snapshot/log persistence must complete before entering `WAITING_*`.

## 6. Testing Contract

When behavior changes, add or update tests and run relevant checks with `uv`.
Minimum focus, as applicable: FSM transitions, agent boundaries, retry/patch/replan flow, and schema compatibility.
