# docslice - Deterministic Specification Slicer

A read-only, deterministic document slicer for extracting specification fragments by SID (Section Identifier) or topic from design documents.

## Purpose

`docslice` is the core tool for the skill execution mechanism in Claude Code, providing precise specification context retrieval. It enables:

**Location**: Packaged with the skill at `.claude/skills/doc-slicer/scripts/docslice`.
It auto-detects the design worktree from the repo root.

The script automatically detects its location and finds the design documentation.

- Extracting specific specification fragments by their unique identifiers
- Retrieving related specifications by topic
- Validating document structure and SID consistency
- Ensuring deterministic, reproducible output

## Installation

The script requires Python 3.6+ and no external dependencies (uses only standard library).

```bash
# Make the script executable
chmod +x .claude/skills/doc-slicer/scripts/docslice

# Optionally, add to PATH or create a symlink
ln -s $(pwd)/.claude/skills/doc-slicer/scripts/docslice /usr/local/bin/docslice
```

## Usage

### Extract by SID

Extract a specification fragment by its Section Identifier:

```bash
docslice --sid SID:arch.contracts.pending_action
docslice --sid arch.contracts.pending_action  # 'SID:' prefix is optional
```

**Output includes:**
- SID and title
- Document location (doc_key, path, line range)
- Fragment level (Section, Block, Spec-Item)
- Tags
- Full content

### Extract by Reference

Extract content using DOC:doc_key#anchor format (fallback reference):

```bash
docslice --ref "DOC:arch#分层架构"
docslice --ref "DOC:agent#Agent体系总览"
```

### Extract by Topic

Extract all specifications related to a topic:

```bash
# Extract all HITL-related specs
docslice --topic hitl

# Limit output size
docslice --topic hitl --max-lines 500
docslice --topic planning --max-chars 10000
```

**Available topics:**
- `hitl` - Human-in-the-loop mechanisms
- `planning` - Task planning specifications
- `execution` - Execution-related specs
- `observability` - Observability and logging

### Validate Structure

Lint and validate document structure:

```bash
docslice --lint
```

**Checks performed:**
- SID format compliance (domain.topic.name)
- SID uniqueness across all documents
- BEGIN/END marker pairing
- Reference validity
- Index consistency

### Options

- `--no-metadata`: Suppress metadata in output (shows only content)
- `--repo-root PATH`: Specify repository root (default: auto-detect)

## Output Format

### With Metadata (default)

```markdown
# SID: arch.overview.layers
# Title: 分层架构
# Document: arch (docs/design/architecture.md)
# Lines: 10-31
# Level: Section
# Tags: arch, overview, layers

## 分层架构
<!-- SID:arch.overview.layers -->

- 输入层：User/API：自然语言目标、约束、数据引用
...
```

### Without Metadata

```bash
docslice --sid arch.overview.layers --no-metadata
```

Outputs only the fragment content without metadata headers.

## SID Format

Section Identifiers follow the format:

```
SID:<domain>.<topic>.<name>
```

**Example:** `SID:fsm.states.waiting_plan_confirm`

- **domain**: `fsm` (finite state machine)
- **topic**: `states` (state definitions)
- **name**: `waiting_plan_confirm` (specific state)

### Recommended Domains

| Domain | Description |
|--------|-------------|
| `fsm` | Finite state machine |
| `hitl` | Human-in-the-loop |
| `planner` | Planner Agent |
| `executor` | Executor Agent |
| `tools` | Tool integration |
| `obs` | Observability |
| `storage` | Data storage |
| `safety` | Safety Agent |
| `summarizer` | Summarizer Agent |
| `arch` | Architecture |
| `api` | REST API |
| `algo` | Algorithms |
| `impl` | Implementation |

## Locator Types

The tool supports three types of locators:

### 1. Comment Marker (Simple)

```markdown
## Section Title
<!-- SID:domain.topic.name -->
Content here...
```

Extracts from the marker until the next heading or SID.

### 2. Begin/End Bounded

```markdown
<!-- SID:domain.topic.name BEGIN -->
Bounded content here...
Can span multiple paragraphs
<!-- SID:domain.topic.name END -->
```

Extracts only the content between BEGIN and END markers.

### 3. Inline Marker

```markdown
| State | Description |
|-------|-------------|
| CREATED | Task created <!-- SID:fsm.states.created --> |
```

Extracts the surrounding context (typically table rows or list items).

## Design Principles

### Deterministic

- Same input always produces identical output
- No fuzzy matching or heuristics
- Precise line-based extraction

### Read-Only

- Never modifies any documents
- Safe for concurrent execution
- Idempotent operations

### Contract-Driven

- All extraction goes through `index.json`
- Locator information is authoritative
- Structure validated by lint

## Integration with Claude Code

Claude Code uses `docslice` to:

1. Retrieve precise specification context for implementation tasks
2. Inject minimal necessary context (avoiding full document injection)
3. Ensure consistency with authoritative design documents
4. Validate compliance during development

## Testing

Run the test suite:

```bash
./scripts/test_docslice.sh
```

Tests cover:
- All locator types (comment, begin_end, inline)
- SID and reference extraction
- Topic aggregation with size limits
- Lint validation
- Deterministic output
- Error handling

## Exit Codes

- `0`: Success
- `1`: Error (invalid input, file not found, validation failure)

## Examples

### Example 1: Extract FSM State Definition

```bash
$ docslice --sid fsm.states.waiting_plan_confirm

# SID: fsm.states.waiting_plan_confirm
# Title: WAITING_PLAN_CONFIRM 状态定义
# Document: arch (docs/design/architecture.md)
# Lines: 315-315
# Level: Spec-Item
# Tags: fsm, states, hitl, planning

|`WAITING_PLAN_CONFIRM`|初始 Plan 已经生成，等待人工确认工具链与关键参数 <!-- SID:fsm.states.waiting_plan_confirm -->|
```

### Example 2: Extract All HITL Specs (Limited)

```bash
$ docslice --topic hitl --max-lines 100 2>&1 | head -30

Warning: Stopping at SID executor.hitl.patch_confirm due to max_lines limit

# SID: arch.contracts.pending_action
# Title: PendingAction 契约定义
...
```

### Example 3: Validate Documents

```bash
$ docslice --lint
✓ No errors found. All documents are valid.
```

## Architecture

```
docslice
├── DocSlice class
│   ├── Auto-detect location (main repo vs design worktree)
│   ├── Load index.json and topic_views.json
│   ├── Build SID and doc lookup tables
│   ├── Extract by SID/ref/topic
│   └── Lint validation
├── Locator-specific extractors
│   ├── _extract_section() - comment markers
│   ├── _extract_inline() - inline markers
│   ├── _extract_line_range() - begin_end markers
│   └── _extract_bounded_block() - fallback
└── Format and output
```

### Path Resolution

When run from the main repository (`thesis-project/scripts/docslice`):
1. Detects it's in the main repo (no `docs/index/index.json`)
2. Looks for design worktree at `../thesis-project.design/`
3. Uses the design worktree for all document lookups

When run from the design worktree (`thesis-project.design/scripts/docslice`):
1. Detects local `docs/index/index.json`
2. Uses current directory as repo root

## Related Documents

- [index.json](../docs/index/index.json) - Machine-readable specification index
- [topic_views.json](../docs/index/topic_views.json) - Topic-based views

## License

Part of the thesis-project design documentation system.

## Version History

- **1.0** (2026-01-01): Initial implementation
  - Support for all locator types
  - Topic extraction with size controls
  - Lint validation
  - Comprehensive test suite
