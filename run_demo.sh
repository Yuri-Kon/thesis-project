#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${1:-}" == "clean" ]]; then
  mkdir -p output data/logs data/snapshots
  find output -type f ! -name ".gitkeep" -delete
  find output -mindepth 1 -type d -empty -delete
  find data/logs -type f -name "*.jsonl" -delete
  find data/snapshots -type f -name "*.jsonl" -delete
  echo "cleaned output/, data/logs/, data/snapshots/"
  exit 0
fi

exec uv run --with uvicorn python scripts/run_demo.py "$@"
