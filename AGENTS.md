# Repository Guidelines(for Codex)

> Audience: Codex / automated coding agents
> Language: Please answer user questions in CHINESE. Code and comments may be in English.

This repository implements an **LLM-driven**, **FSM-governed multi-agent system** for protein design.

The system is **contract-first**, **state-machine-driven**, and supports **retry → patch → replan** with optional **Human-in-the-Loop(HITL)** checkpoints.

Codex **MUST** follow the invariants, boundaries, and document hierarchy below.

If a request conflicts with them, **prefer a minimal compliant change** and **add or update tests**.

---

## 0) Where to Find the Design(READ FIRST)

Before making structural or behavioral changes, consult the following 
documents in order:

1. `docs/design/architecture.md`: System-level architecture, FSM, end-to-end workflow, HITL placement(**top-level source of truth**)
2. `docs/design/agent-design.md`: Responsibilities, I/O contracts, and boundaries of Planner / Executor / Safety / Summarizer.
3. `docs/design/system-implementation-design.md`: Concrete engineering design: tech stack, code structure, API/FSM alignment, storage. logging.
4. `docs/design/core-algorithm-spec.md`: PlannerAgent algorithms: Plan / Patch / Replan candidate generation, scoring, HITL gating, Decision application.

> If code behavior and documentation disagree, **the design documents win**

## 1) System Invariants(MUST NOT be violated)

### Finite State Machine(FSM) is the source of truth

- Task lifecycle is gonverned by a fixed FSM.
- **DO NOT invent new states** unless explicitly requested by user and reflected in design docs.
- **DO NOT mutate task status implicitly or out of band**.
- Every state transition MUST be:
  - explicit
  - logged
  - consistent across API, DB, and logs.

  ---

  ### Strict role separation between Agents

  - PlannerAgent
    - Generates `Plan` / `PlanPatch` / `Replan`.
    - MUST NOT execute tools or touch runtime artifacts.
  - ExecutorAgent
    - The **only** component allowed to execute tools.
    - Handles retry / patch / replan control flow.
  - SafetyAgent
    - Evaluates risk and emits `SafetyResult`(`ok`/`warn`/`bloc`) only.
    - MUST NOT modify plans or outputs.
  - SummarizerAgent
    - Aggregates results and produces reports.
    - MUST NOT re-run tools or override safety decisions.

  ---

  ### Contract-first data model(schemas are stable)

  Core contracts include(but are not limited to):

  - `ProteinDesignTask`
  - `Plan`, `PlanStep`
  - `StepResult`
  - `DesignResult`
  - `SafetyResult`, `RiskFlag`
  - `PendingAction`, `Decision`(for HITL)

  Rules:
  
  - DO NOT rename or remove exsiting fields.
  - DO NOT change field semantics.
  - Extensions MUST go into:
    - `metadata`
    - `metrics`
    - optional fields
  - Step references like `"S1.sequence"` are **part of the contract**:
    - MUST be preserved
    - MUST be resolved in adapters / execution logic
    - MUST NOT be inlined prematurtely.

  ---

  ### Failure handling is control flow, not exceptions

  A step failure does NOT imply task failue.

  Expected order:

  1. retry(bounded, with backoff)
  2. patch(local, minimal Plan changes)
  3. replan(regenerate suffix while locking successful prefix)

  Only unrecoverable failures or permanent safety block lead to `FAILED`

  ---


## 2) Project Structure (High-Level)

- `src/`
  - `agents/` — Planner / Executor / Safety / Summarizer implementations
  - `workflow/` — FSM, graph orchestration, and execution control flow
  - `models/` — Core contracts, snapshots, and database models
  - `storage/` — Artifact storage, logs, and persistence utilities
  - `api/` — FastAPI endpoints exposing task lifecycle and status
  - `kg/` — ProteinToolKG client logic and tool metadata

- `docs/`
  - Design documents (**authoritative**; see `docs/design/`)

- `tests/`
  - `unit/`, `integration/`, `api/`
  - Shared fixtures in `tests/conftest.py`

- `data/`, `output/`
  - Inputs, logs, intermediate artifacts, and final results


---

## 3) Coding Style & Conventions

- Primary language: **Python**
- Follow PEP 8 formatting with 4-space indentation
- Use type hints consistently where surrounding code does
- Prefer **small, testable functions**
- Avoid hidden side effects and implicit state mutation

### Logging

- Use structured logs where applicable, including:
  - `task_id`, `step_id`, `plan_version`, `state`, `event`
- Logs MUST remain consistent with FSM state and task snapshots
- **Do NOT log secrets** (API keys, tokens, credentials)


---

## 4) Testing Requirements (Mandatory for Behavior Changes)

Framework: `pytest`

When modifying behavior, Codex MUST add or update tests covering:

- **FSM transitions**
  - Assert valid transitions
  - Forbid invalid transitions

- **Contract changes**
  - Schema-level tests
  - Consumer compatibility tests

- **Retry / Patch / Replan logic**
  - Bounded retries with backoff
  - Patch application followed by re-execution
  - Replan triggered after patch failure or safety block
  - Prefix-lock correctness for suffix replans


---

## 5) Agent Responsibility Boundaries (Quick Reference)

| Agent | Allowed Responsibilities | Forbidden Actions |
|------|--------------------------|-------------------|
| PlannerAgent | Parse intent, query KG, generate Plan / Patch / Replan | Execute tools, mutate runtime state |
| ExecutorAgent | Execute steps, manage retry / patch / replan | Change task goal, invent schemas |
| SafetyAgent | Evaluate risks, emit SafetyResult | Execute tools, modify plans |
| SummarizerAgent | Aggregate results, generate reports | Re-run tools, override safety decisions |


---

## 6) Safe Defaults (When Unsure)

If design intent is unclear, Codex SHOULD:

- Prefer **minimal, conservative changes**
- **Do NOT** introduce new FSM states
- **Do NOT** move execution logic into Planner / Safety / Summarizer
- Centralize reference-resolution logic (adapters / step runner)
- Add tests to lock and document the chosen behavior

