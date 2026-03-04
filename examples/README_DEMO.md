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
