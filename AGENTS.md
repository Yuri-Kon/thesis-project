# Repository Guidelines (for Codex)

# NOTE: Please answer user questions in Chinese. Code/comments may be in English.

This repository implements an **LLM-driven multi-agent workflow** for protein design.
It is **FSM-driven**, **contract-first**, and supports **retry → patch → replan** at runtime.

Codex MUST follow the invariants and boundaries below. If a request conflicts with them, prefer
a minimal compliant change and add/adjust tests.

---

## 0) System Invariants (MUST NOT be violated)

### 0.1 Finite State Machine (FSM) is the source of truth

- Task lifecycle is governed by a finite set of states (e.g. CREATED, PLANNING, PLANNED, RUNNING,
  WAITING_PATCH, PATCHING, WAITING_REPLAN, REPLANNING, SUMMARIZING, DONE, FAILED).
- **Do NOT invent new status values.**
- **Do NOT arbitrarily mutate task status** outside the allowed transitions.
- Any state transition must be explicit, logged, and consistent across API/DB/logs.

### 0.2 Strict role separation (Planner never executes tools)

- **PlannerAgent** only produces `Plan` / `PlanPatch` / `Replan` outputs.
- **ExecutorAgent** is the only component that triggers tool execution via adapters/engine.
- **SafetyAgent** only evaluates risk and returns `SafetyResult` (ok/warn/block).
- **SummarizerAgent** only aggregates results and generates reports; it does not re-run tools.

### 0.3 Contract-first data model (do not break schemas)
Core objects are contracts:
- `ProteinDesignTask`, `Plan`, `PlanStep`, `StepResult`, `DesignResult`, `SafetyResult` (and RiskFlag)

Rules:
- Do NOT rename or remove existing fields.
- Do NOT change field meanings.
- If you must extend, put extras into `metadata` / `metrics` / optional fields, and update all consumers.
- Step input references like `"S1.sequence"` are part of the contract and MUST be preserved.
  Resolve references in adapter/input-resolution logic; do not inline values prematurely.

### 0.4 Failure handling is control flow (not just exceptions)
A step failure does not immediately imply task failure.
The expected flow is:
1) retry (bounded, with backoff)
2) patch (local minimal Plan changes)
3) replan (suffix regeneration while locking successful prefix)
Only unrecoverable failures or permanent safety blocks should lead to FAILED.

---

## 1) Project Structure & Module Organization

- `src/` holds the application code. Key packages include:
  - `agents/` (Planner/Executor/Safety/Summarizer)
  - `workflow/` (plan runner / step runner / graph orchestration)
  - `models/` (contracts and typed objects)
  - `storage/` (logs/artifacts persistence)
  - `schemas/` (if present, schema validation)
  - `api/` (FastAPI endpoints / task lifecycle exposure)
  - `kg/` (ProteinToolKG client and data)

- `tests/` contains pytest suites split into:
  - `unit/`, `integration/`, and `api/`
  - Shared fixtures: `tests/conftest.py`

- Supporting materials live in:
  - `docs/`, `resources/`, `data/`, `output/`, `htmlcov/`

---

## 2) Build, Test, and Development Commands

- Install dependencies:
  - `pip install -r requirements.txt`

- Run API locally:
  - `uvicorn src.api.main:app --reload`

- Run tests:
  - `pytest`

- Full suite script (if present):
  - `bash run_tests.sh`

- Coverage (optional):
  - `pytest --cov=src --cov-report=html`

---

## 3) Coding Style & Naming Conventions

- Python is the primary language; follow 4-space indentation and PEP 8 formatting.
- Use type hints consistently where the surrounding code does.
- Naming:
  - modules: `snake_case`
  - classes: `PascalCase`
  - functions: `snake_case`
- Prefer small, testable functions. Avoid hidden side effects.

### 3.1 Logging & Observability
- Use structured logs where applicable (event, task_id, step_id, plan_version, state).
- Ensure logs remain consistent with FSM and DB snapshots.
- Do not log secrets (API keys, tokens).

---

## 4) Testing Guidelines (Required for behavior changes)

- Framework: pytest
- Markers may include: `unit`, `integration`, `api`, `slow`
- Organize tests by scope:
  - `tests/unit/`, `tests/integration/`, `tests/api/`

When modifying:
- FSM transitions: add/update tests that assert valid transitions and forbid invalid ones.
- Plan/StepResult/SafetyResult changes: add contract tests and consumer tests.
- Retry/patch/replan logic: add tests for:
  - bounded retries + backoff behavior
  - patch applied then re-execution
  - replan triggered after patch failure or safety block
  - prefix-lock correctness

---

## 5) Agent Responsibility Boundaries (Quick Reference)

| Component | Allowed Responsibilities | Forbidden Actions |
|---|---|---|
| PlannerAgent | Parse task intent/spec; query KG; generate Plan/Patch/Replan outputs | Execute tools; mutate execution history; direct file I/O as part of tool runs |
| ExecutorAgent | Execute Plan steps; manage retry/patch/replan triggers; produce StepResult; persist step summaries | Change task goal; invent new contract fields; silently skip required steps |
| SafetyAgent | Evaluate input/step/output risks; emit SafetyResult with ok/warn/block | Execute tools; modify Plan; modify StepResult outputs |
| SummarizerAgent | Aggregate results; produce DesignResult + report artifacts | Re-run tools; rewrite step history; alter safety decisions |

---

## 6) Commit & Pull Request Guidelines

- Commit messages follow Conventional Commits:
  - `type(scope): summary`
  - Examples:
    - `feat(B2): ...`
    - `refactor(workflow): ...`
    - `test(executor): ...`

- Keep changes focused.
- If behavior changes, add or update tests in the matching suite.

---

## 7) Safe Defaults for Code Changes (When Unsure)

If you are uncertain about design intent:
- Prefer minimal changes.
- Do NOT introduce new states or new required contract fields.
- Do NOT move tool execution into Planner/Safety/Summarizer.
- Add tests to lock the behavior.
- Keep reference-resolution logic centralized (e.g., adapters / step runner), not spread across agents.
