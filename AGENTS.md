# AGENTS.md

Operational instructions for Codex in this repository.

This file defines execution guidance only.
System invariants are defined in `AGENT_CONTRACT.md` and are non-negotiable.

## 0. Quick Start Checklist (Before Any Change)

1. Read `AGENT_CONTRACT.md`.
2. If touching FSM, agent roles, contracts, or execution semantics, pull design fragments with doc-slicer:
   - `.agents/skills/doc-slicer/scripts/docslice --sid ...`
   - `.agents/skills/doc-slicer/scripts/docslice --topic ...`
   - `.agents/skills/doc-slicer/scripts/docslice --ref ...`
3. Limit scope to the user request and strictly required edits.
4. Implement minimal changes.
5. Add/update tests when behavior changes and run via `uv`.

If instructions conflict, follow this order:

1. `AGENT_CONTRACT.md`
2. Design documents in `../thesis-project.design/docs/design/`
3. `AGENTS.md`

## 1. Role In This Project

Codex is an implementation assistant, not a system designer.

Expected:

- Implement requested, scoped changes.
- Preserve architecture and contracts.
- Update tests for behavior changes.

Prohibited:

- Inventing new system behavior.
- Introducing new FSM states or new agent roles without explicit spec.
- Reinterpreting system intent beyond design documents.

## 2. Project Structure Map (Use This To Scope Edits)

Core runtime:

- `src/workflow/`: task lifecycle, status transitions, decision application, recovery.
- `src/agents/`: planner, executor, safety, summarizer implementations.
- `src/models/`: contracts and validation (`contracts.py`, `validation.py`).
- `src/storage/`: snapshots and logs.
- `src/adapters/`, `src/tools/`, `src/engines/`: tool adapters and execution backends.
- `src/infra/`: runtime infrastructure integration helpers.
- `src/llm/`: model/provider invocation abstractions.
- `src/kg/`: tool knowledge graph and capability metadata.
- `src/schemas/`: JSON schema and compatibility assets.
- `src/api/`: API schemas and endpoints.

Tests:

- `tests/unit/`: unit-level contracts, FSM, agent behavior.
- `tests/integration/`: workflow integration and recovery flows.
- `tests/api/`: endpoint contracts.
- `tests/services/`: service-level contract/integration tests.

Rule of thumb:

- Change only the nearest module that owns the behavior.
- Mirror behavior changes with tests in the corresponding test area.
- Do not broadly unignore `output/`; if specific output artifacts must be versioned, add only targeted files (for example with `git add -f <path>`).

## 3. Coding And Logging Expectations

- Primary language: Python.
- Follow existing style and typing patterns.
- Prefer small, testable functions.
- Avoid hidden side effects.
- Keep structured logging aligned with task state transitions.
- Never log secrets or credentials.

## 4. Tooling

- Use `uv` for execution and tests.
- Use Python 3.12 (`.python-version`).
- Typical commands:
  - `uv run pytest ...`
  - `uv run python ...`

## 4.1 Remote Server Baseline

When work needs the shared AutoDL remote server, use the server state verified in
`../remote-server/README.md` as the operational baseline.

- Access the server via `ssh autodl`.
- The shared account is `root`; do not assume per-user Linux accounts exist.
- Current project roots live under `/root/projects/<student_id>/`.
- The currently confirmed project root for this thesis work is `/root/projects/2022112879/`.
- The currently confirmed remote service repository is `/root/projects/2022112879/remote-model-rest`.
- The actively used Conda/Mamba installation is `/root/autodl-tmp/conda`, not `/root/miniconda3`.
- The current experiment environment is `plm` at `/root/autodl-tmp/envs/plm`.
- Remote service startup should default to the `plm` environment unless the user explicitly says otherwise.
- The currently known PLM REST and OpenFold3 REST deployments do **not** use authentication by default.
- Do not instruct users to set `PLM_REST_API_TOKEN` or `OPENFOLD3_REST_API_TOKEN` unless they explicitly ask to enable auth.
- When documenting or running remote commands, prefer:
  - `ssh autodl`
  - `conda activate plm`
  - `cd /root/projects/2022112879/remote-model-rest`
  - `python -m uvicorn services.plm_rest_server.app:app --host 0.0.0.0 --port 8100`
  - `python -m uvicorn services.openfold3_rest_server.app:app --host 0.0.0.0 --port 8200`
- Do not assume `HF_HOME`, `TRANSFORMERS_CACHE`, or `TORCH_HOME` are preconfigured on the server; set them explicitly when a task depends on redirected caches.

## 5. Scope Control And Escalation

Edit only:

- what the user asked for, and
- what is strictly necessary to make it work safely.

If a change may affect FSM transitions, agent responsibilities, or execution semantics:

- stop and ask for explicit user confirmation before proceeding.

## 6. Testing Requirements

When behavior changes:

- add/update tests,
- run relevant existing tests,
- prefer focused suites first, then broader suites for cross-cutting changes.

Minimum validation targets (as applicable):

- FSM transition validity,
- agent boundary isolation,
- retry/patch/replan behavior,
- schema compatibility.

## 7. Issues And PRs

Only prepare issues/PRs when explicitly requested.
Use `gh` only after user confirmation.

## 8. Safe Defaults

If intent is ambiguous:

- choose minimal, conservative edits,
- avoid unrelated refactors,
- avoid new abstractions unless required,
- ask before architectural changes.

## 9. Git Commit Message Convention

- Use Conventional Commits for commit messages (for example: `feat(scope): short summary`).
- Keep the subject line concise and in Conventional Commits format.
- The commit body may be written in Chinese when needed.
