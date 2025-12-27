from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.models.contracts import TaskSnapshot

DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


def append_snapshot(
    snapshot: TaskSnapshot,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> None:
    """Append a TaskSnapshot entry to a jsonl file."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{snapshot.task_id}.jsonl"
    payload: Mapping[str, Any] = snapshot.model_dump()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
