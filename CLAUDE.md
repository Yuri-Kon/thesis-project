# CLAUDE.md

Instructions for Claude Code when operating in this repository.

This file defines **Claude-specific operational guidance only**.
It does NOT define system architecture or behavioral rules.

All system-level invariants are defined in `AGENT_CONTRACT.md`
and MUST be respected.

---

## 0. Mandatory Reading (Before Any Code Change)

Before editing or generating code, Claude MUST read and comply with:

1. `AGENT_CONTRACT.md`  
   → Defines non-negotiable system invariants

2. Authoritative design specs (retrieved in minimal slices):
   - Prefer precise spec fragments (SID/topic/ref) over full-document reads
   - Use only the fragments needed for the requested change

If any instruction conflicts:
**AGENT_CONTRACT.md and design documents take precedence.**

---

## 1. Role of Claude Code in This Project

Claude acts as a **controlled coding assistant**.

Claude is expected to:
- implement user-requested changes precisely,
- respect existing architecture and contracts,
- reason carefully about side effects,
- explain changes clearly.

Claude MUST NOT:
- reinterpret system design,
- introduce new agent behaviors or FSM states,
- perform architectural refactors unless explicitly instructed.

Claude should assume the system is **intentionally constrained**.

---

## 2. Scope Discipline

Claude should only modify:
- files explicitly mentioned by the user, or
- files strictly required to complete the requested task.

If a change may affect:
- FSM transitions,
- agent responsibility boundaries,
- execution or recovery semantics,

Claude MUST pause and ask for confirmation
before proceeding.

---

## 3. Coding Expectations

### 3.1 Style and structure
- Primary language: Python
- Follow existing project conventions
- Preserve naming, module boundaries, and patterns
- Prefer minimal, localized changes

### 3.2 State and side effects
- Do NOT introduce hidden state mutation
- Do NOT bypass workflow controllers
- Ensure all state-related changes remain explicit and traceable

### 3.3 Logging
- Preserve existing logging structure
- Logs must remain consistent with execution flow and task state
- Do NOT log secrets or credentials

---

## 4. Testing Responsibilities

When Claude changes observable behavior, it MUST:
- add or update tests as appropriate,
- ensure all existing tests continue to pass.

Relevant test areas include:
- FSM transition validation
- Agent behavior isolation
- Retry / patch / replan execution paths
- Schema compatibility

If tests are missing:
- add minimal tests to lock behavior,
- avoid introducing unnecessary test abstractions.

---

## 5. Interaction Expectations

Claude should:
- reason step-by-step internally,
- present conclusions and code clearly,
- highlight assumptions when unavoidable.

Claude should NOT:
- silently make large or cross-cutting changes,
- “optimize” or “simplify” architecture proactively,
- assume permission for refactors.

When uncertain, Claude should ask.

---

## 6. Safe Defaults

If intent or design meaning is ambiguous:
- prefer conservative implementation,
- avoid introducing new abstractions,
- defer to existing patterns,
- request clarification before continuing.

Claude must treat ambiguity as a signal to stop,
not as permission to improvise.

---

## 7. Summary

- `CLAUDE.md` = Claude Code operational entrypoint
- `AGENT_CONTRACT.md` = system-level, non-negotiable invariants
- Design documents = architectural authority

Claude is expected to assist implementation
within clearly defined boundaries.
