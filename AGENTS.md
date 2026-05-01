# AGENTS.md

Operational guidance for Codex in this repository.
System invariants live in `AGENT_CONTRACT.md` and override this file.

## 1. Before Changing Code

1. Read `AGENT_CONTRACT.md`.
2. Keep the change scoped to the user request and the nearest owning module.
3. If the task touches FSM, agent roles, contracts, recovery, or execution semantics, use doc-slicer to retrieve the relevant design fragments before editing:
   - `.agents/skills/doc-slicer/scripts/docslice --sid ...`
   - `.agents/skills/doc-slicer/scripts/docslice --topic ...`
   - `.agents/skills/doc-slicer/scripts/docslice --ref ...`
4. If the change would require a key system decision, stop and ask the user. Do not decide it yourself.

Instruction priority:

1. `AGENT_CONTRACT.md`
2. Design docs in `../thesis-project.design/docs/design/`
3. This file

## 2. Scope Map

- `src/workflow/`: lifecycle, status transitions, decisions, recovery.
- `src/agents/`: planner, executor, safety, summarizer.
- `src/models/`: contracts and validation.
- `src/storage/`: snapshots and logs.
- `src/adapters/`, `src/tools/`, `src/engines/`: tool adapters and execution backends.
- `src/infra/`, `src/llm/`, `src/kg/`, `src/schemas/`, `src/api/`: integration, providers, capability metadata, schemas, API surface.
- `tests/unit/`, `tests/integration/`, `tests/api/`, `tests/services/`: mirror behavior changes in the matching test area.

Do not broadly unignore `output/`; if an output artifact must be versioned, add only the specific file.

## 3. Coding Rules

- Primary language: Python 3.12; use `uv` for commands.
- Follow existing style and typing patterns.
- New or edited docstrings should use Google style Chinese.
- Prefer small, testable functions and explicit side effects.
- Keep structured logs aligned with task state transitions.
- Never log secrets or credentials.
- Preserve public contracts; do not rename, remove, or reinterpret schema fields just to simplify implementation.

Typing baseline:

- Write Python to satisfy the repository `basedpyright` configuration.
- Do not introduce new `Any`, bare generics, untyped containers, broad casts, or broad ignores.
- Use precise domain types or explicit JSON aliases; validate opaque values at boundaries.
- Do not weaken `pyproject.toml` type-checker settings unless explicitly asked.

## 4. Validation

When behavior changes:

- add or update focused tests;
- run relevant tests with `uv run pytest ...`;
- run focused `uv run basedpyright ...` for touched Python modules when practical.

Prefer focused suites first, then broader suites for cross-cutting changes.

## 5. Remote Server Work

Use `../remote-server/README.md` as the operational baseline for AutoDL or remote model services.

Current high-level assumptions:

- connect with `ssh autodl`;
- project root is `/root/projects/2022112879/`;
- remote service repository is `/root/projects/2022112879/remote-model-rest`;
- Conda/Mamba root is `/root/autodl-tmp/conda`;
- default environment is `plm`;
- long-lived services should use `tmux` sessions such as `plm_rest` and `openfold3_rest`;
- do not enable or suggest REST auth tokens unless the user asks for auth.

Check the remote baseline document before relying on exact startup commands, ports, model paths, or cache paths.

## 6. Git And GitHub

- Prepare issues, PRs, or `gh` operations only when explicitly requested.
- Use Conventional Commits for commits, for example `feat(scope): short summary`.
- Commit bodies may be Chinese when useful.

## 7. Safe Defaults

- Choose minimal, conservative edits.
- Avoid unrelated refactors and new abstractions unless required.
- Ask before architectural or behavioral changes.
- Never let the AI approve human-confirmation steps, recovery decisions, or other key system decisions by inference.
