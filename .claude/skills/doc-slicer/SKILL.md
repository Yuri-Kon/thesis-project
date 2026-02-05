---
name: doc-slicer
description: Deterministic spec retrieval from design docs by SID/topic/ref for FSM, HITL contracts, agent responsibilities, and tool constraints.
allowed-tools: Bash(.claude/skills/doc-slicer/scripts/docslice:*), Read
---

# Doc Slicer

Use this to pull exact spec fragments from the design docs without full-file reads.

Use when you need:
- FSM states/transitions
- HITL contracts (PendingAction/Decision/TaskSnapshot)
- Agent must/must_not responsibilities
- Tool adapter constraints
- Topic bundles: hitl, planning, execution, observability

Commands:
```bash
# help
.claude/skills/doc-slicer/scripts/docslice --help

# by SID
.claude/skills/doc-slicer/scripts/docslice --sid fsm.states.waiting_plan_confirm

# by topic
.claude/skills/doc-slicer/scripts/docslice --topic hitl --max-lines 300

# by doc reference (use the real section title)
.claude/skills/doc-slicer/scripts/docslice --ref "DOC:arch#<section title>"

# lint SID markers
.claude/skills/doc-slicer/scripts/docslice --lint
```

Notes:
- Output includes metadata; add `--no-metadata` for content only.
- Requires `../thesis-project.design/docs/index/index.json` and `topic_views.json`.
- Exact match only; no fuzzy search.
