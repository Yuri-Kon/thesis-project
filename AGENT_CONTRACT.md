# AGENT_CONTRACT.md

System-level contract for all coding agents in this repository.

This file is tool-agnostic and defines non-negotiable invariants.
If any other instruction conflicts with this contract, this file wins.

## 0. Source Of Truth And Paths

- Code workspace: `thesis-project.dev` (this repository)
- Design workspace: `../thesis-project.design`
- Authoritative specs live in `../thesis-project.design/docs/design/`
- Index files for deterministic lookup:
  - `../thesis-project.design/docs/index/index.json`
  - `../thesis-project.design/docs/index/topic_views.json`

When a change may affect FSM, agent responsibilities, contracts, or execution semantics:

1. Read this file first.
2. Retrieve relevant spec fragments with doc-slicer before editing:
   - `.agents/skills/doc-slicer/scripts/docslice --sid ...`
   - `.agents/skills/doc-slicer/scripts/docslice --topic ...`
   - `.agents/skills/doc-slicer/scripts/docslice --ref ...`

## 1. System Invariants

This is an LLM-driven multi-agent system controlled by an explicit FSM.
All behavior changes must preserve system consistency.

### 1.1 FSM authority

- State must be explicit.
- Transitions must be legal, validated, and logged.
- State mutation is owned by workflow control logic only.
- No skipped states, no hidden transitions, no direct terminal jumps.
- Terminal states (`DONE`, `FAILED`, `CANCELLED`) are immutable.

### 1.2 Canonical lifecycle

Required state flow:

- `CREATED -> PLANNING -> WAITING_PLAN_CONFIRM -> PLANNED -> RUNNING`
- `RUNNING -> WAITING_PATCH_CONFIRM` or `WAITING_REPLAN_CONFIRM`
- `WAITING_* -> RUNNING` or `FAILED` or `CANCELLED`
- `RUNNING -> SUMMARIZING -> DONE`

`WAITING_*` states mean execution is paused pending human decision.

## 2. Agent Boundary Contract

Role boundaries are hard constraints.

### 2.1 PlannerAgent

Must:

- Produce `Plan`, `PlanPatch`, or `Replan` candidates.

Must not:

- Execute tools.
- Access runtime artifacts directly.
- Mutate task state directly.

### 2.2 ExecutorAgent

Must:

- Be the only component executing tools.
- Own retries, patch application flow, and replan triggers.
- Stop execution when entering any `WAITING_*` flow.

Must not:

- Make human decisions on candidate approval.
- Continue tool execution while in `WAITING_*`.

### 2.3 SafetyAgent

Must:

- Output evaluation only (`ok`, `warn`, `block`).

Must not:

- Execute tools.
- Modify plans.
- Override workflow results.

### 2.4 SummarizerAgent

Must:

- Aggregate outputs and produce user-facing summaries.

Must not:

- Re-run tools.
- Change plan or state decisions.

## 3. Contract-First Data Rules

Schemas are compatibility contracts.

Must not:

- Rename existing fields.
- Remove existing fields.
- Change established field semantics.

Allowed extension pattern:

- Additive, backward-compatible changes only.
- Prefer optional fields, `metadata`, and `metrics`.

Step references (for example `S1.sequence`) are first-class and must remain symbolic at planning time.

## 4. Failure Recovery Contract

Failure handling is controlled flow, not ad-hoc behavior.

Required order:

1. Retry (bounded).
2. Patch (minimal local change).
3. Replan (prefer preserving successful prefix).

A single step failure must not directly set task state to `FAILED`.
`FAILED` is valid only when recovery is exhausted or safety blocks permanently.

## 5. Persistence And Observability

- Every state transition must be logged.
- Snapshot/log persistence must be completed before entering `WAITING_*`.
- Recovery must respect latest snapshot and current task state.

## 6. Change Control

When intent is unclear:

- Make the minimal safe change.
- Do not introduce new abstractions or agent behaviors.
- Do not redesign architecture implicitly.

If a change may alter FSM, role boundaries, or execution semantics, stop and require explicit confirmation.

## 7. Testing Contract

When behavior changes, agents must:

- Add or update tests.
- Run relevant tests through `uv` (`uv run pytest ...`).

Minimum coverage focus:

- FSM transitions
- Agent boundary behavior
- Retry/patch/replan flow
- Schema compatibility

## 8. Instruction Layering

- Tool-specific files (`AGENTS.md`, `CLAUDE.md`, etc.) may add operational guidance.
- Tool-specific files must not weaken this contract.

All automated agents operating in this repository are expected to comply.
