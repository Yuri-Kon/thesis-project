# AGENTS.md

Instructions for Codex when operating in this repository.

This file defines **Codex-specific operational guidance**.
It does NOT redefine system behavior or architecture.

All system-level invariants are defiend in `AGENT_CONTRACT.md`
and MUST be respected.

---

## 0. Mandatory Reading (Before Any Code Change)

Before modifying code, Codex MUST read any comply with:

1. `AGENT_CONTRACT.md`: Define system-level invariants (FSM, agent boundaries, contracts)
2. Authoritative design document (in design worktree):
  - `../thesis-project.design/docs/design/architecture.md`
  - `../thesis-project.design/docs/design/agent-design.md`
  - `../thesis-project.design/docs/design/system-implementation-design.md`
  - `../thesis-project.design/docs/design/core-algorithm-spec.md`
  - `../thesis-project.design/docs/design/tools-catalog.md`

If any instruction conflicts:
**AGENT_CONTRACT.md and design documents take precedence.**

---

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

---

## 2. Scope Control

Codex should only modify code that is:
- explicitly requested by the user, or
- strictly necessary to complete the requested task.

When a change might impact:
- FSM transitions,
- agent responsibilities,
- execution semantics,
Codex MUST stop and ask for confirmation.

---

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

---

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

---

## 5. Change Workflow (Expected)

When implementing a feature or fix, Codex should follow:

1. Understand scope from user instruction
2. Read relevant design documents
3. Implement minimal necessary changes
4. Add or update tests
5. Clearly explain what was changed and why

Large or cross-cutting changes should be broken into:
- small, reviewable commits, or
- explicitly staged steps (with user confirmation)

---

## 6. Safe Defaults

If intent is ambiguous:
- prefer minimal changes,
- do not refactor unrelated code,
- do not introduce new abstractions,
- ask the user before proceeding.

Codex should never assume it is allowed to
"improve" architecture unless explicitly instructed.

---

## 7. Summary

- `AGENTS.md` = Codex operational entrypoint
- `AGENT_CONTRACT.md` = system invariants (non-negotiable)
- Design documents = architectural authority

Codex is expected to assist implementation,
not redefine the system.
