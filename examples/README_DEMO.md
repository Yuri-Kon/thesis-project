# One-Command Demo

This repository provides a one-command launcher for the minimal end-to-end demo:

- FastAPI input layer (`/docs`, `/health`, `/tasks`)
- Planner/Executor/Safety/Summarizer workflow chain
- Runtime resources (ProteinToolKG, logs, snapshots, output dirs)

## Quick Start

From repository root:

```bash
./run_demo.sh
```

What this does:

1. Checks runtime prerequisites (Python 3.12, `uv`, optional Nextflow).
2. Initializes runtime resources:
   - `output/`
   - `data/logs/`
   - `data/snapshots/`
   - `src/kg/protein_tool_kg.json` load check
3. Starts FastAPI service.
4. Runs smoke check:
   - `GET /health` must return `200`
   - `POST /tasks` creates a demo task
   - `GET /tasks/{id}` observes task status
   - verifies EventLog file `data/logs/{task_id}.jsonl`

After startup:

- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- HITL dashboard: `http://127.0.0.1:8000/ui`
- Event timeline: `http://127.0.0.1:8000/ui/tasks/<task_id>/events`
- Candidate compare demo (seeded, in-process preview): `uv run python examples/run_hitl_candidate_ui_demo.py`

## Issue #142 Candidate Compare Demo

Run reproducible in-process preview (no extra dependency):

```bash
uv run python examples/run_hitl_candidate_ui_demo.py
```

This seeds deterministic demo data:

- `task_id=task_demo_142`
- `pending_action_id=pa_demo_142`

Optional real HTTP UI serving (requires `uvicorn`):

```bash
uv run python examples/run_hitl_candidate_ui_demo.py --serve --port 8012
```

When served, open:

- `http://127.0.0.1:8012/ui/tasks/task_demo_142`
- `http://127.0.0.1:8012/ui/tasks/task_demo_142/events`
- `http://127.0.0.1:8012/pending-actions/pa_demo_142`

Expected checkpoints:

1. Candidate table contains rank/risk/cost/recommendation fields.
2. Tool fields are visible (`tool_id/capability_id/io_type/adapter_mode/source`).
3. One candidate is rendered as degraded when tool metadata is missing.
4. After decision submit, Decision Result shows status update and latest decision/transition event summary.

## Main Options

```bash
./run_demo.sh --port 8010 --model-backend mock --mock-tools
```

Useful flags:

- `--host`, `--port`: API bind address
- `--model-backend`: backend label for demo metadata
- `--mock-tools` / `--no-mock-tools`: toggle mock mode flag
- `--data-dir`, `--output-dir`: runtime directories
- `--kg-path`: ProteinToolKG file path
- `--smoke-test` / `--no-smoke-test`: enable/disable smoke run
- `--smoke-task-config`: task payload JSON (default `configs/demo_task.json`)
- `--exit-after-smoke`: exit after checks (useful in CI)

All arguments are implemented in `scripts/run_demo.py`.

## Cleanup

```bash
./run_demo.sh clean
```

This resets:

- `output/`
- `data/logs/`
- `data/snapshots/`

## Manual Smoke Commands

If you start demo with `--no-smoke-test`, use:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/tasks \
  -H 'content-type: application/json' \
  -d @configs/demo_task.json
curl -sS http://127.0.0.1:8000/tasks/<task_id>
```
