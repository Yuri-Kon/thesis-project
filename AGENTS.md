# AGENTS.md

Instructions for Codex when operating in this repository.

This file defines **Codex-specific operational guidance**.
It does NOT redefine system behavior or architecture.

All system-level invariants are defiend in `AGENT_CONTRACT.md`
and MUST be respected.

______________________________________________________________________

## 0. Mandatory Reading (Before Any Code Change)

Before modifying code, Codex MUST read any comply with:

1. `AGENT_CONTRACT.md`: Define system-level invariants (FSM, agent boundaries, contracts)
1. Authoritative design specs via deterministic slicing (preferred):

- Use the docslice skill at `.agents/skills/doc-slicer/`
- Script: `.agents/skills/doc-slicer/scripts/docslice`
- Retrieve only the needed fragments by `--sid`, `--topic`, or `--ref`
- If the first slice is incomplete or misses the target, expand scope and retry
  (e.g., increase `--max-lines`/`--max-chars`, or try a broader `--ref`/`--topic`)
- Read full design docs only if docslice still cannot locate or capture the required spec

If any instruction conflicts:
**AGENT_CONTRACT.md and design documents take precedence.**

______________________________________________________________________

## 1. Role of Codex in This Project

Codex acts as a **coding assistant**, not a system designer.

Codex is expected to:

- implement clearly scoped changes,
- follow existing architecture and contracts,
- add tests when behavior changes,
- avoid speculative refactors or redesigns.

Codex MUST NOT:

- invent new system behavior,
- introduce new FSM states or agent roles,
- reinterpret system intent beyond design documents.

______________________________________________________________________

## 2. Scope Control

Codex should only modify code that is:

- explicitly requested by the user, or
- strictly necessary to complete the requested task.

When a change might impact:

- FSM transitions,
- agent responsibilities,
- execution semantics,
  Codex MUST stop and ask for confirmation.

______________________________________________________________________

## 3. Coding Expectations

### 3.1 Language and style

- Primary language: Python
- Follow existing project conventions
- Use type hints where present
- Prefer small, testable functions
- Avoid hidden side effects

### 3.2 Logging

- Preserve structured logging conventions
- Logs must remain consistent with task state and execution flow
- Do NOT log secrets or credentials

### 3.3 Tooling (uv)

- Package manager: uv
- Python runtime for uv: 3.12 (see `.python-version` / `requires-python`)
- Run all programs and tests through uv (e.g., `uv run ...`, `uv run pytest`)

______________________________________________________________________

## 4. Testing Requirements

When Codex changes behavior, it MUST:

- add or update relevant tests,
- ensure existing tests pass.

Test areas include (as applicable):

- FSM transition validation
- Agent behavior isolation
- Retry / patch / replan execution flow
- Schema compatibility

If tests are missing, Codex should:

- add minimal tests that lock expected behavior,
- avoid overengineering test frameworks.

______________________________________________________________________

## 5. Change Workflow (Expected)

When implementing a feature or fix, Codex should follow:

1. Understand scope from user instruction
1. Read relevant design documents
1. Implement minimal necessary changes
1. Add or update tests
1. Clearly explain what was changed and why

Large or cross-cutting changes should be broken into:

- small, reviewable commits, or
- explicitly staged steps (with user confirmation)

______________________________________________________________________

## 6. Issues and PRs (On Request, via gh)

Only draft issues or PRs when the user explicitly asks.
Use `gh` for submission and get user confirmation before any `gh` command.

Issue content must include:

- Title
- Goal
- Project context aligned with repo structure
- Core work mapped to code structure
- Acceptance criteria with verifiable checks
- Impact scope with exact files/paths
- Dependencies referencing prior issues

PR content must include:

- Base branch: `dev` unless specified
- Title
- Summary covering all branch changes and issue goals
- Background based on issue + dependencies, and why change is needed
- Key requirements restated from issue core work
- Changes: list files with 2-3 line summaries; key design decisions with code locations and optional small snippets/diagrams
- Impact: positive impact; negative impact if any; risk assessment
- Links to the current issue and relevant past issues

______________________________________________________________________

## 7. Safe Defaults

If intent is ambiguous:

- prefer minimal changes,
- do not refactor unrelated code,
- do not introduce new abstractions,
- ask the user before proceeding.

Codex should never assume it is allowed to
"improve" architecture unless explicitly instructed.

______________________________________________________________________

## 8. Summary

- `AGENTS.md` = Codex operational entrypoint
- `AGENT_CONTRACT.md` = system invariants (non-negotiable)
- Design documents = architectural authority

Codex is expected to assist implementation,
not redefine the system.
