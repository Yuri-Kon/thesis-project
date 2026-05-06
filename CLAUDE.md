# CLAUDE.md

Claude Code operational guidance for this repository.
AGENTS.md defines Codex-common rules; this file adds Claude-specific differences only.

## 1. Priority

1. `AGENT_CONTRACT.md` — system invariants
2. `../thesis-project.design/docs/design/` — architectural authority
3. `AGENTS.md` — common operational rules
4. This file — Claude-specific additions

Conflicts are resolved in this order.

## 2. Behavior

Claude should:
- Implement user requests precisely, respecting existing architecture and contracts
- Scope changes to files mentioned by the user or modules strictly required
- Keep side effects explicit; no hidden state mutation

Claude must not:
- Reinterpret system design, introduce new agent behaviors or FSM states
- Proactively "optimize" or "simplify" architecture
- Refactor without explicit instruction
- Substitute inference for human-confirmation steps

## 3. Coding

- Python 3.12; use `uv` for dependency and run commands
- Follow existing project style, naming, and module boundaries
- Satisfy `basedpyright`; no `Any`, bare generics, or untyped containers
- Logs consistent with execution flow; never log secrets

## 4. Testing

When behavior changes:
- Add or update focused tests
- `uv run pytest ...` to verify
- `uv run basedpyright ...` for type checks when practical

## 5. Docslice

Use the `doc-slicer` skill (see `.agents/skills/doc-slicer/SKILL.md`) to retrieve design spec fragments by SID, topic, or reference instead of full-document reads. Run `--lint` after design doc changes.

## 6. Ambiguity → Stop

When intent is unclear, prefer conservative implementation, defer to existing patterns, and request clarification before continuing.
