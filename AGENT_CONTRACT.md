# AGENT_CONTRACT.md

System-level behavioral contract for all automated agents operating in the repository.

This document is tool-agnostic.
It defines invairants that MUST be respected by any LLM-based coding agent (Codex, Claude Code, Cursor, etc.)

If any agent instruction conflicts with this document,
THIS DOCUMENT TAKES PRECEDENCE.

______________________________________________________________________

## 0. Project Directory

The Project is managed with Git. The usual working directory is the current one, and this directory(thesis-project.dev) is a worktree of ../thesis-project, which is on master branch.

The design documents are located in ../thesis-project.design, which is also a worktree.

Design worktree layout (for quick lookup):
- docs/: authoritative design documents and indices
  - docs/design/: core architecture and system specs (architecture, agent design, FSM, tools catalog, workflows, etc.)
  - docs/design/diagrams/: architecture diagrams in .mmd and .svg
  - docs/impl/: implementation guides and operational specs
  - docs/index/: document index and SSOT maps (index.md, index.json, topic_views.json, etc.)
  - docs/demo/: demo notes and references (README.md)
  - docs/proposal/: proposal source (main.tex)
  - docs/proposal-fix/: proposal edit artifacts (proposal.odt)
- plan/: dated planning indexes (e.g., index(1.14-2.03).md)
- shared/format/: shared document templates (proposal-format.docx)
- requirements.txt: Python requirements for the design worktree

Search in ../thesis-project.design every time before planning to code.

## 1. System Nature

This project implements an **LLM-driven, multi-agent system**
for protein design, governed by an explicit **Finite State Machine(FSM)**.

Agents are not helpers or scripts.
Agents are **system components** whose behavior is constrained
by architecture, contracts, and lifecycle rules.

Any code change MUST preserve System-level consistency.

______________________________________________________________________

## 2. FSM Is the Single Source of Truth

### 2.1 Explicit state management only

- Task state MUST be represented explicitly.
- No implicit, inferred, or out-of-band state transitions are allowed.
- Every transition MUST:
  - be defined in the FSM transition table,
  - be validated in code,
  - be logged.

### 2.2 No illegal transitions

- Agents MUST NOT:
  - skip states,
  - jump directly to terminal states,
  - mutata state outside the workflow controller.
- Terminal states(e.g. `DONE`, `FAILED`, `CANCELLED`) are immutable.

### 2.3 Design authority

FSM definitions and allowed transitions are defined in design documents(`architecture.md` and related specs).

If code behavior diverges from design documents,
**design documents win**.

______________________________________________________________________

### 3.1 PlannerAgent

- Generates plans and plan variants:
  - `Plan`
  - `PlanPatch`
  - `Replan`
- MUST NOT:
  - execute tools,
  - access runtime artifacts,
  - mutate task state directly

### 3.2 ExecutorAgent

- The ONLY agent allowed to:
  - execute tools,
  - manage retries,
  - apply patches,
  - trigger replans.
- Owns runtime execution flow.

### 3.3 SafetyAgent

- Evaluates safety and legality.
- Ouputs **evaluation only** (e.g. `ok / warn / block`).
- MUST NOT:
  - modify plans,
  - execute tools,
  - override execution results.

### 3.4 SummarizerAgent

- Aggergates execution results and artifacts.
- Produces human-facing summaries and reports.
- MUST NOT:
  - re-run tools,
  - change plans,
  - override safety decisions.

Role boundaries are **hard constraints**, not suggestions.

______________________________________________________________________

## 4. Contract-First Data Model

### 4.1 Schemas are stable contracts

- Core data models (Pydantic / schema definitions) are system contracts.
- Agents MUST NOT:
  - rename existing fields,
  - remove fields,
  - change field semantics.

### 4.2 Extension rules

- Extensions MUST be additive and backward-compatible.
- Prefer:
  - optional fields,
  - `metadata`,
  - `metrics`.

### 4.3 Step references are first-class

- References such as `"S1.sequence"` are part of the contract.
- They MUST:
  - remain symbolic at the planning level,
  - be resolved by execution/adaptation logic,
  - NOT be prematurely inlined by planners.

______________________________________________________________________

## 5. Failure Handling Is Controlled Flow

Failure is **expected**, not exceptional.

### 5.1 Standard recovery order

On step failure, agents MUST follow:

1. retry (bounded, with limits)
1. patch (minimal local modification)
1. replan (regenerate suffix, preserve successful prefix)

### 5.2 No premature task failure

- A step failure does NOT automatically mean task failure.
- `FAILED` is only valid when:
  - recovery paths are exhausted, or
  - SafetyAgent issues a permanent block.

______________________________________________________________________

## 6. Design Documents Are Authoritative

Authoritative design documents are maintained separately
(e.g. in a design worktree).

Agents MUST consult design documents before:

- introducing new states,
- modifying FSM logic,
- changing agent responsibilities,
- altering execution semantics.

When code and design disagree:
**design documents override code assumptions**.

### 6.1 Spec Access Discipline

To reduce unnecessary context and keep references precise, agents MUST
prefer deterministic spec slicing when available (e.g. via the docslice
skill under `.claude/skills/doc-slicer/`) and retrieve only the needed
SID/topic fragments instead of full-document reads.

______________________________________________________________________

## 7. Minimal Change Principle

When intent is unclear:

- prefer minimal, conservative changes,
- avoid introducing new abstractions,
- do not invent new agent behaviors,
- add tests to lock in assumptions.

Agents MUST NOT "optimize" or "simplify" the system
at the cost of violating architecture.

______________________________________________________________________

## 8. This Contract Is Non-Negotiable

This file defines system invariants.

- Tool-specific instructions (`AGENTS.md`, `CLAUDE.md`, etc.)
  MAY add operational guidance.
- Tool-specific instructions MUST NOT weaken or override this contract.

Any automated agent operating in this repository
is expected to comply with this document.
